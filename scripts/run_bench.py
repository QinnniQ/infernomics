from __future__ import annotations

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

def read_prompts(path: Path) -> list[str]:
    prompts: list[str] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            prompts.append(obj["prompt"])
    return prompts

def main() -> None:
    MAX_OUTPUT_TOKENS = 50
    settings = get_settings()
    model = settings.model

    prompts_path = Path("data/eval_sets/chat_prompts.jsonl")
    prompts = read_prompts(prompts_path)

    run_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    out_dir = Path("outputs/runs") / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    db = ResultsDB(Path("outputs") / "results.sqlite")
    db.insert_run(RunInfo(run_id=run_id, created_at_utc=created_at, model=model, meta={"workload": "chat"}))

    client = OpenAI()  # reads OPENAI_API_KEY from env :contentReference[oaicite:3]{index=3}

    totals = {
        "n": 0,
        "errors": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "cost": 0.0,
        "lat_ms_sum": 0.0,
        "lat_ms": [],
    }

    for i, prompt in enumerate(prompts):
        r = run_one_chat(client, model=model, prompt=prompt, max_output_tokens=MAX_OUTPUT_TOKENS)
        totals["n"] += 1
        totals["lat_ms_sum"] += r.latency_ms
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

        (out_dir / f"{i:03d}.json").write_text(json.dumps({
            "idx": i,
            "prompt": prompt,
            "output_text": r.output_text,
            "prompt_tokens": r.prompt_tokens,
            "completion_tokens": r.completion_tokens,
            "total_tokens": r.total_tokens,
            "cost_estimate": r.cost_estimate,
            "latency_ms": r.latency_ms,
            "error": r.error,
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    db.close()

    lat_sorted = sorted(totals["lat_ms"])
    def pct(p: float) -> float:
        if not lat_sorted:
            return 0.0
        k = int(round((p / 100.0) * (len(lat_sorted) - 1)))
        return float(lat_sorted[k])

    table = Table(title="Inference Cost Project — Chat Benchmark Summary")
    table.add_column("Run ID", style="cyan")
    table.add_column("Model", style="magenta")
    table.add_column("N")
    table.add_column("Errors")
    table.add_column("Tokens (in/out/total)")
    table.add_column("Avg ms")
    table.add_column("p50 ms")
    table.add_column("p95 ms")
    table.add_column("€ est.")

    avg_ms = totals["lat_ms_sum"] / max(1, totals["n"])
    table.add_row(
        run_id,
        model,
        str(totals["n"]),
        str(totals["errors"]),
        f"{totals['prompt_tokens']}/{totals['completion_tokens']}/{totals['total_tokens']}",
        f"{avg_ms:.1f}",
        f"{pct(50):.1f}",
        f"{pct(95):.1f}",
        f"{totals['cost']:.6f}",
    )
    console.print(table)

    console.print(f"\nSaved per-item JSON to: {out_dir}")
    console.print("Saved SQLite to: outputs/results.sqlite")
    console.print("\nNOTE: € estimate is 0 until you fill pricing.py for your chosen model.")

if __name__ == "__main__":
    main()
