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
from icp.runner_chat import run_one_chat
from icp.storage_sqlite import ResultsDB, RunInfo

console = Console()

PROMPTS_PATH = Path("data/eval_sets/chat_prompts.jsonl")

def read_prompts(path: Path) -> list[str]:
    prompts: list[str] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            prompts.append(obj["prompt"])
    return prompts

def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    v = sorted(values)
    k = int(round((p / 100.0) * (len(v) - 1)))
    return float(v[k])

def run_config(
    *,
    client: OpenAI,
    db: ResultsDB,
    prompts: list[str],
    model: str,
    max_output_tokens: int,
) -> dict:
    run_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    out_dir = Path("outputs/runs") / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    db.insert_run(
        RunInfo(
            run_id=run_id,
            created_at_utc=created_at,
            model=model,
            meta={"workload": "chat", "max_output_tokens": max_output_tokens},
        )
    )

    totals = {
        "run_id": run_id,
        "model": model,
        "max_output_tokens": max_output_tokens,
        "n": 0,
        "errors": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "cost": 0.0,
        "lat_ms": [],
    }

    for i, prompt in enumerate(prompts):
        r = run_one_chat(client, model=model, prompt=prompt, max_output_tokens=max_output_tokens)

        totals["n"] += 1
        totals["lat_ms"].append(r.latency_ms)
        if r.error:
            totals["errors"] += 1

        pt = int(r.prompt_tokens or 0)
        ct = int(r.completion_tokens or 0)
        tt = int(r.total_tokens or (pt + ct))

        totals["prompt_tokens"] += pt
        totals["completion_tokens"] += ct
        totals["total_tokens"] += tt
        totals["cost"] += float(r.cost_estimate or 0.0)

        db.insert_result(
            run_id=run_id,
            idx=i,
            prompt=prompt,
            output_text=r.output_text,
            prompt_tokens=r.prompt_tokens,
            completion_tokens=r.completion_tokens,
            total_tokens=r.total_tokens,
            cost_estimate=r.cost_estimate,
            latency_ms=r.latency_ms,
            error=r.error,
            raw=r.raw,
        )

        (out_dir / f"{i:03d}.json").write_text(
            json.dumps(
                {
                    "idx": i,
                    "prompt": prompt,
                    "output_text": r.output_text,
                    "prompt_tokens": r.prompt_tokens,
                    "completion_tokens": r.completion_tokens,
                    "total_tokens": r.total_tokens,
                    "cost_estimate": r.cost_estimate,
                    "latency_ms": r.latency_ms,
                    "error": r.error,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    avg_ms = sum(totals["lat_ms"]) / max(1, totals["n"])
    p50 = percentile(totals["lat_ms"], 50)
    p95 = percentile(totals["lat_ms"], 95)

    totals_out = {
        **totals,
        "avg_ms": avg_ms,
        "p50_ms": p50,
        "p95_ms": p95,
        "cost_per_req": (totals["cost"] / max(1, totals["n"])),
        "tokens_per_req": (totals["total_tokens"] / max(1, totals["n"])),
    }
    return totals_out

def main() -> None:
    settings = get_settings()
    model = settings.model

    prompts = read_prompts(PROMPTS_PATH)

    # Sweep values (edit freely)
    sweep = [50, 100, 200]

    db = ResultsDB(Path("outputs") / "results.sqlite")
    client = OpenAI()

    results: list[dict] = []
    for mot in sweep:
        console.print(f"\nRunning config: max_output_tokens={mot}")
        results.append(run_config(client=client, db=db, prompts=prompts, model=model, max_output_tokens=mot))

    db.close()

    # Print comparison table
    table = Table(title="ICP — Sweep Summary (Chat)")
    table.add_column("max_out", justify="right")
    table.add_column("run_id", style="cyan")
    table.add_column("tokens in/out/total", justify="right")
    table.add_column("avg ms", justify="right")
    table.add_column("p95 ms", justify="right")
    table.add_column("€ total", justify="right")
    table.add_column("€ / req", justify="right")

    for r in results:
        table.add_row(
            str(r["max_output_tokens"]),
            r["run_id"],
            f'{r["prompt_tokens"]}/{r["completion_tokens"]}/{r["total_tokens"]}',
            f'{r["avg_ms"]:.1f}',
            f'{r["p95_ms"]:.1f}',
            f'{r["cost"]:.6f}',
            f'{r["cost_per_req"]:.6f}',
        )

    console.print(table)

    # Save CSV
    out_csv = Path("outputs") / "reports"
    out_csv.mkdir(parents=True, exist_ok=True)
    csv_path = out_csv / f"sweep_chat_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"

    fieldnames = [
        "run_id",
        "model",
        "max_output_tokens",
        "n",
        "errors",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "avg_ms",
        "p50_ms",
        "p95_ms",
        "cost",
        "cost_per_req",
        "tokens_per_req",
    ]

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in results:
            w.writerow({k: r.get(k) for k in fieldnames})

    console.print(f"\nSaved CSV report to: {csv_path}")
    console.print("Saved SQLite to: outputs/results.sqlite")

if __name__ == "__main__":
    main()
