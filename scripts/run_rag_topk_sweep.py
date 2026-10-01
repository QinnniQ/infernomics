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
from icp.rag.rag_runner import run_one_rag
from icp.metrics.judge import JudgeResult, judge_answer
from icp.metrics.aggregation import summarize_topk

console = Console()

QUESTIONS_PATH = Path("data/eval_sets/chat_prompts.jsonl")


def read_questions(path: Path) -> list[str]:
    qs: list[str] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            qs.append(json.loads(line)["prompt"])
    return qs


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

        pairs = []

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

            if r.error:
                j = JudgeResult(0, 0, False, "Generation failed", 0, 0, 0, 0.0, 0.0, error="generation_failed")
            else:
                j = judge_answer(
                    client=client,
                    judge_model=JUDGE_MODEL,
                    question=q,
                    answer=r.answer_text or "",
                    context=r.rag_prompt or "",
                    max_output_tokens=200,
                    temperature=0.0,
                )

            pairs.append((r, j))

        results.append(
            {
                "run_id": run_id,
                "model": model,
                "embed_model": embed_model,
                "judge_model": JUDGE_MODEL,
                "max_output_tokens": MAX_OUTPUT_TOKENS,
                "top_k": top_k,
                **summarize_topk(pairs),
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
            f'{r["judge_quality_avg_0_5"]:.2f}' if r["judge_quality_avg_0_5"] is not None else "n/a",
            f'{r["judge_grounded_avg_0_5"]:.2f}' if r["judge_grounded_avg_0_5"] is not None else "n/a",
            f'{r["judge_follows_rate"]*100:.1f}%' if r["judge_follows_rate"] is not None else "n/a",
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
