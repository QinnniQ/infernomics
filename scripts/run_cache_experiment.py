from __future__ import annotations

import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI
from rich.console import Console
from rich.table import Table

from icp.config import get_settings
from icp.cache import FileCache
from icp.runner_chat import run_one_chat

console = Console()

PROMPTS_PATH = Path("data/eval_sets/chat_prompts.jsonl")


def read_prompts(path: Path) -> list[str]:
    prompts: list[str] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            prompts.append(obj["prompt"])
    return prompts


def run_pass(
    *,
    client: OpenAI,
    cache: FileCache,
    prompts: list[str],
    model: str,
    max_output_tokens: int,
    use_cache: bool,
    cache_hit_latency_ms: float = 5.0,  # simulate fast lookup on cache hit
) -> dict:
    """
    Pass behavior:
      - Cold pass: use_cache=False => always call API, but still writes to cache.
      - Warm pass: use_cache=True  => cache hits incur ~cache_hit_latency_ms and €0 billed cost.
    """
    totals = {
        "n": 0,
        "hits": 0,
        "misses": 0,
        "errors": 0,
        "billed_prompt_tokens": 0,
        "billed_completion_tokens": 0,
        "billed_total_tokens": 0,
        "billed_cost": 0.0,
        "lat_ms": [],
    }

    for prompt in prompts:
        totals["n"] += 1
        key = cache.make_key(model=model, max_output_tokens=max_output_tokens, prompt=prompt)

        # Warm: short-circuit on cache hit (REALISTIC billing)
        if use_cache:
            cached = cache.get(key)
            if cached is not None:
                totals["hits"] += 1
                totals["lat_ms"].append(cache_hit_latency_ms)
                # cache hits are NOT billed
                continue

        # Otherwise: miss => call API
        totals["misses"] += 1

        t0 = time.perf_counter()
        r = run_one_chat(client, model=model, prompt=prompt, max_output_tokens=max_output_tokens)
        wall_ms = (time.perf_counter() - t0) * 1000.0
        totals["lat_ms"].append(wall_ms)

        if r.error:
            totals["errors"] += 1

        pt = int(r.prompt_tokens or 0)
        ct = int(r.completion_tokens or 0)
        tt = int(r.total_tokens or (pt + ct))

        totals["billed_prompt_tokens"] += pt
        totals["billed_completion_tokens"] += ct
        totals["billed_total_tokens"] += tt
        totals["billed_cost"] += float(r.cost_estimate or 0.0)

        # Save to cache (even on cold pass)
        cache.set(
            key,
            {
                "model": model,
                "max_output_tokens": max_output_tokens,
                "prompt": prompt,
                "output_text": r.output_text,
                "prompt_tokens": r.prompt_tokens,
                "completion_tokens": r.completion_tokens,
                "total_tokens": r.total_tokens,
                "cost_estimate": r.cost_estimate,
                "latency_ms": r.latency_ms,  # model-side latency (informational)
                "cached_at_utc": datetime.now(timezone.utc).isoformat(),
            },
        )

    avg_ms = sum(totals["lat_ms"]) / max(1, totals["n"])
    hit_rate = totals["hits"] / max(1, totals["n"])

    return {
        **totals,
        "avg_ms": avg_ms,
        "hit_rate": hit_rate,
        "billed_cost_per_req": totals["billed_cost"] / max(1, totals["n"]),
    }


def main() -> None:
    settings = get_settings()
    model = settings.model

    prompts = read_prompts(PROMPTS_PATH)

    # Fixed for this experiment (edit freely)
    MAX_OUTPUT_TOKENS = 100

    client = OpenAI()
    cache = FileCache(Path("outputs/cache/prompt_cache"))

    console.print(f"Model: {model}")
    console.print(f"max_output_tokens: {MAX_OUTPUT_TOKENS}")
    console.print(f"Prompts: {len(prompts)}")
    console.print(f"Cache dir: {cache.base_dir}\n")

    cold = run_pass(
        client=client,
        cache=cache,
        prompts=prompts,
        model=model,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        use_cache=False,
    )

    warm = run_pass(
        client=client,
        cache=cache,
        prompts=prompts,
        model=model,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        use_cache=True,
    )

    table = Table(title="ICP — Cache Experiment (Prompt Cache, Billed Cost)")
    table.add_column("Pass")
    table.add_column("Hit rate", justify="right")
    table.add_column("Avg ms", justify="right")
    table.add_column("Billed tokens (in/out/total)", justify="right")
    table.add_column("€ billed total", justify="right")
    table.add_column("€ billed / req", justify="right")
    table.add_column("Errors", justify="right")

    table.add_row(
        "Cold (no cache)",
        f'{cold["hit_rate"]*100:.1f}%',
        f'{cold["avg_ms"]:.1f}',
        f'{cold["billed_prompt_tokens"]}/{cold["billed_completion_tokens"]}/{cold["billed_total_tokens"]}',
        f'{cold["billed_cost"]:.6f}',
        f'{cold["billed_cost_per_req"]:.6f}',
        str(cold["errors"]),
    )
    table.add_row(
        "Warm (cache on)",
        f'{warm["hit_rate"]*100:.1f}%',
        f'{warm["avg_ms"]:.1f}',
        f'{warm["billed_prompt_tokens"]}/{warm["billed_completion_tokens"]}/{warm["billed_total_tokens"]}',
        f'{warm["billed_cost"]:.6f}',
        f'{warm["billed_cost_per_req"]:.6f}',
        str(warm["errors"]),
    )
    console.print(table)

    saved_eur = cold["billed_cost"] - warm["billed_cost"]
    saved_ms = cold["avg_ms"] - warm["avg_ms"]

    console.print(f"\nEstimated € saved (cold - warm): {saved_eur:.6f}")
    console.print(f"Avg latency saved per request (ms): {saved_ms:.1f}")
    console.print(f"Warm cache hit rate: {warm['hit_rate']*100:.1f}%\n")

    out_dir = Path("outputs/reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"cache_experiment_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "pass",
                "model",
                "max_output_tokens",
                "n",
                "hit_rate",
                "avg_ms",
                "billed_prompt_tokens",
                "billed_completion_tokens",
                "billed_total_tokens",
                "billed_cost",
                "billed_cost_per_req",
                "errors",
            ],
        )
        w.writeheader()
        for name, r in [("cold", cold), ("warm", warm)]:
            w.writerow(
                {
                    "pass": name,
                    "model": model,
                    "max_output_tokens": MAX_OUTPUT_TOKENS,
                    "n": r["n"],
                    "hit_rate": r["hit_rate"],
                    "avg_ms": r["avg_ms"],
                    "billed_prompt_tokens": r["billed_prompt_tokens"],
                    "billed_completion_tokens": r["billed_completion_tokens"],
                    "billed_total_tokens": r["billed_total_tokens"],
                    "billed_cost": r["billed_cost"],
                    "billed_cost_per_req": r["billed_cost_per_req"],
                    "errors": r["errors"],
                }
            )

    console.print(f"Saved CSV report to: {csv_path}")


if __name__ == "__main__":
    main()
