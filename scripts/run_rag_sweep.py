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

console = Console()

QUESTIONS_PATH = Path("data/eval_sets/chat_prompts.jsonl")  # reuse as questions for Track A

def read_questions(path: Path) -> list[str]:
    qs = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            qs.append(json.loads(line)["prompt"])
    return qs

def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    v = sorted(values)
    k = int(round((p/100.0) * (len(v)-1)))
    return float(v[k])

def main() -> None:
    settings = get_settings()
    model = settings.model
    embed_model = settings.embed_model

    store = load_index(Path("outputs/rag/index.json"))
    questions = read_questions(QUESTIONS_PATH)

    sweep = [50, 100, 200]
    TOP_K = 3

    client = OpenAI()
    results = []

    for mot in sweep:
        run_id = str(uuid.uuid4())
        lat = []
        in_toks = 0
        out_toks = 0
        total_toks = 0
        llm_cost = 0.0
        embed_cost = 0.0
        errors = 0

        for q in questions:
            r = run_one_rag(
                client=client,
                model=model,
                embed_model=embed_model,
                store=store,
                question=q,
                top_k=TOP_K,
                max_output_tokens=mot,
            )
            lat.append(r.latency_ms)
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

        avg_ms = sum(lat) / max(1, len(lat))
        p95 = percentile(lat, 95)

        results.append({
            "run_id": run_id,
            "max_output_tokens": mot,
            "top_k": TOP_K,
            "n": len(questions),
            "errors": errors,
            "prompt_tokens": in_toks,
            "completion_tokens": out_toks,
            "total_tokens": total_toks,
            "avg_ms": avg_ms,
            "p95_ms": p95,
            "llm_cost_total": llm_cost,
            "embed_cost_total": embed_cost,
            "cost_total": llm_cost + embed_cost,
            "cost_per_req": (llm_cost + embed_cost) / max(1, len(questions)),
        })

    table = Table(title="ICP — Sweep Summary (RAG)")
    table.add_column("max_out", justify="right")
    table.add_column("top_k", justify="right")
    table.add_column("tokens in/out/total", justify="right")
    table.add_column("avg ms", justify="right")
    table.add_column("p95 ms", justify="right")
    table.add_column("€ total", justify="right")
    table.add_column("€ / req", justify="right")
    table.add_column("embed €", justify="right")

    for r in results:
        table.add_row(
            str(r["max_output_tokens"]),
            str(r["top_k"]),
            f'{r["prompt_tokens"]}/{r["completion_tokens"]}/{r["total_tokens"]}',
            f'{r["avg_ms"]:.1f}',
            f'{r["p95_ms"]:.1f}',
            f'{r["cost_total"]:.6f}',
            f'{r["cost_per_req"]:.6f}',
            f'{r["embed_cost_total"]:.6f}',
        )

    console.print(table)

    out_dir = Path("outputs/reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"rag_sweep_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        for r in results:
            w.writerow(r)

    console.print(f"\nSaved CSV report to: {csv_path}")

if __name__ == "__main__":
    main()
