from __future__ import annotations

import csv
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI
from rich.console import Console
from rich.table import Table

from icp.config import get_settings
from icp.rag.rag_index import load_index
from icp.rag.rag_runner import run_one_rag, _build_rag_prompt  # ok for internal reuse
from icp.metrics.judge import judge_answer

console = Console()

QUESTIONS_PATH = Path("data/eval_sets/chat_prompts.jsonl")


def read_questions(path: Path) -> list[str]:
    qs: list[str] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            qs.append(json.loads(line)["prompt"])
    return qs


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    v = sorted(values)
    k = int(round((p / 100.0) * (len(v) - 1)))
    return float(v[k])


def main() -> None:
    settings = get_settings()
    model = settings.model
    embed_model = settings.embed_model

    # Judge model (keep same as generator for now)
    JUDGE_MODEL = model

    store = load_index(Path("outputs/rag/index.json"))
    questions = read_questions(QUESTIONS_PATH)

    MAX_OUTPUT_TOKENS = 100
    TOP_KS = [1, 3, 5]

    client = OpenAI()
    results: list[dict] = []

    for top_k in TOP_KS:
        run_id = str(uuid.uuid4())

        lat_ms: list[float] = []
        in_toks = 0
        out_toks = 0
        total_toks = 0
        llm_cost = 0.0
        embed_cost = 0.0
        errors = 0

        # Judge aggregates
        judge_quality_sum = 0
        judge_grounded_sum = 0
        judge_follows_sum = 0
        judge_cost_total = 0.0
        judge_lat_ms: list[float] = []
        judge_errors = 0

        for q in questions:
            r = run_one_rag(
                client=client,
                model=model,
                embed_model=embed_model,
                store=store,
                question=q,
                top_k=top_k,
                max_output_tokens=MAX_OUTPUT_TOKENS,
            )

            lat_ms.append(r.latency_ms)
            if r.error:
                errors += 1

            pt = int(r.prompt_tokens or 0)
            ct = int(r.completion_tokens or 0)
            tt = int(r.total_tokens or (pt + ct))
            in_toks += pt
            out_toks += ct
            total_toks += tt
            llm_cost += float(r.llm_cost_estimate or 0.0)
            embed_cost += float(r.embed_cost_estimate or 0.0)

            # Build the exact context we sent (for judge)
            # We reconstruct by running retrieval again via the store query path inside runner,
            # but simplest: rebuild the prompt from current retrieval.
            # We'll reuse the runner’s retrieval logic by doing a small “prompt rebuild”:
            # (cheap enough for Track A)
            # -> We can only judge if we provide context; here we provide the exact prompt "Context:" section.
            # We'll pass the prompt itself as "context" to judge.
            answer_text = r.answer_text or ""
            prompt_for_judge = r.raw.get("input", None)  # may be absent
            # fallback: rebuild prompt using the same helper (contexts are embedded in it)
            if not prompt_for_judge:
                # minimal fallback context text: we can’t easily extract the exact contexts from raw,
                # so we re-run the build step by reconstructing prompt using current store retrieval.
                # (We’ll just rebuild the prompt via helper by retrieving now.)
                # NOTE: This is fine for Track A; later we can return contexts from run_one_rag.
                from icp.rag.rag_runner import embed_query  # local import to avoid cycles
                q_vec, _, _ = embed_query(client, embed_model, q)
                hits = store.query(q_vec, top_k=top_k)
                contexts = []
                for idx, score in hits:
                    ch = store.chunks[idx]
                    contexts.append({"doc_id": ch.doc_id, "title": ch.title, "text": ch.text, "score": score})
                prompt_for_judge = _build_rag_prompt(q, contexts)

            # Judge call
            j = judge_answer(
                client=client,
                judge_model=JUDGE_MODEL,
                question=q,
                answer=answer_text,
                context=prompt_for_judge,
                max_output_tokens=200,
                temperature=0.0,
            )

            judge_quality_sum += j.quality_0_5
            judge_grounded_sum += j.grounded_0_5
            judge_follows_sum += 1 if j.follows_instructions else 0
            judge_cost_total += float(j.judge_cost_estimate or 0.0)
            judge_lat_ms.append(j.judge_latency_ms)
            if j.error:
                judge_errors += 1

        n = len(questions)
        avg_ms = sum(lat_ms) / max(1, n)
        p95_ms = percentile(lat_ms, 95)

        cost_total = llm_cost + embed_cost
        cost_per_req = cost_total / max(1, n)

        # Judge metrics
        quality_avg = judge_quality_sum / max(1, n)
        grounded_avg = judge_grounded_sum / max(1, n)
        follows_rate = judge_follows_sum / max(1, n)
        judge_avg_ms = sum(judge_lat_ms) / max(1, len(judge_lat_ms))
        judge_cost_per_req = judge_cost_total / max(1, n)

        # Combined "end-to-end including eval" (useful for benchmarking pipelines)
        total_with_eval = cost_total + judge_cost_total
        total_with_eval_per_req = total_with_eval / max(1, n)

        results.append(
            {
                "run_id": run_id,
                "model": model,
                "embed_model": embed_model,
                "judge_model": JUDGE_MODEL,
                "max_output_tokens": MAX_OUTPUT_TOKENS,
                "top_k": top_k,
                "n": n,
                "errors": errors,
                "prompt_tokens": in_toks,
                "completion_tokens": out_toks,
                "total_tokens": total_toks,
                "avg_ms": avg_ms,
                "p95_ms": p95_ms,
                "llm_cost_total": llm_cost,
                "embed_cost_total": embed_cost,
                "cost_total": cost_total,
                "cost_per_req": cost_per_req,
                # judge
                "judge_quality_avg_0_5": quality_avg,
                "judge_grounded_avg_0_5": grounded_avg,
                "judge_follows_rate": follows_rate,
                "judge_cost_total": judge_cost_total,
                "judge_cost_per_req": judge_cost_per_req,
                "judge_avg_ms": judge_avg_ms,
                "judge_errors": judge_errors,
                # end-to-end
                "cost_total_including_eval": total_with_eval,
                "cost_per_req_including_eval": total_with_eval_per_req,
            }
        )

    table = Table(title=f"ICP — RAG top_k + Judge (max_output_tokens={MAX_OUTPUT_TOKENS})")
    table.add_column("top_k", justify="right")
    table.add_column("Q avg", justify="right")
    table.add_column("G avg", justify="right")
    table.add_column("follow %", justify="right")
    table.add_column("€ / req", justify="right")
    table.add_column("€ eval/req", justify="right")
    table.add_column("€ all/req", justify="right")
    table.add_column("avg ms", justify="right")
    table.add_column("errors", justify="right")

    for r in results:
        table.add_row(
            str(r["top_k"]),
            f'{r["judge_quality_avg_0_5"]:.2f}',
            f'{r["judge_grounded_avg_0_5"]:.2f}',
            f'{r["judge_follows_rate"]*100:.1f}%',
            f'{r["cost_per_req"]:.6f}',
            f'{r["judge_cost_per_req"]:.6f}',
            f'{r["cost_per_req_including_eval"]:.6f}',
            f'{r["avg_ms"]:.1f}',
            str(r["errors"]),
        )

    console.print(table)

    out_dir = Path("outputs/reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"rag_topk_judge_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        for r in results:
            w.writerow(r)

    console.print(f"\nSaved CSV report to: {csv_path}")


if __name__ == "__main__":
    main()
