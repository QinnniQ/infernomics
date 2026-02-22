from __future__ import annotations

import csv
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
from openai import OpenAI
from rich.console import Console
from rich.table import Table

from icp.cache import FileCache
from icp.config import get_settings
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


def clear_dir(path: Path) -> None:
    # Delete cache files for a clean run
    if not path.exists():
        return
    for p in path.rglob("*"):
        if p.is_file():
            p.unlink()
    # remove empty dirs
    for p in sorted(path.rglob("*"), reverse=True):
        if p.is_dir():
            try:
                p.rmdir()
            except OSError:
                pass


def run_workload_with_target_hit_rate(
    *,
    client: OpenAI,
    cache: FileCache,
    prompts: list[str],
    model: str,
    max_output_tokens: int,
    target_hit_rate: float,
    cache_hit_latency_ms: float = 5.0,
    seed: int = 42,
) -> dict:
    """
    Approach:
      - First, "prime" the cache with ALL prompts (one billed call per prompt).
      - Then run a second pass where each prompt is:
          - served from cache with probability = target_hit_rate
          - forced to be a cache MISS (billed) with probability = 1 - target_hit_rate
        (We force misses by bypassing cache lookup.)
    This gives us controlled hit rates while keeping prompts constant.
    """
    rng = random.Random(seed)

    # ---- Prime pass (fill cache deterministically) ----
    prime_cost = 0.0
    prime_lat_ms = []
    prime_billed_tokens = 0

    for prompt in prompts:
        key = cache.make_key(model=model, max_output_tokens=max_output_tokens, prompt=prompt)
        if cache.get(key) is not None:
            continue  # already primed
        r = run_one_chat(client, model=model, prompt=prompt, max_output_tokens=max_output_tokens)
        prime_cost += float(r.cost_estimate or 0.0)
        pt = int(r.prompt_tokens or 0)
        ct = int(r.completion_tokens or 0)
        tt = int(r.total_tokens or (pt + ct))
        prime_billed_tokens += tt
        prime_lat_ms.append(float(r.latency_ms or 0.0))
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
                "latency_ms": r.latency_ms,
                "cached_at_utc": datetime.now(timezone.utc).isoformat(),
            },
        )

    # ---- Measured pass (controlled hit rate) ----
    totals = {
        "n": 0,
        "hits": 0,
        "misses": 0,
        "errors": 0,
        "billed_total_tokens": 0,
        "billed_cost": 0.0,
        "lat_ms": [],
    }

    for prompt in prompts:
        totals["n"] += 1
        key = cache.make_key(model=model, max_output_tokens=max_output_tokens, prompt=prompt)

        serve_from_cache = (rng.random() < target_hit_rate)
        if serve_from_cache:
            cached = cache.get(key)
            # Should exist because we primed. If not, treat as miss.
            if cached is not None:
                totals["hits"] += 1
                totals["lat_ms"].append(cache_hit_latency_ms)
                continue

        # forced miss (billed)
        totals["misses"] += 1
        t0 = time.perf_counter()
        r = run_one_chat(client, model=model, prompt=prompt, max_output_tokens=max_output_tokens)
        totals["lat_ms"].append((time.perf_counter() - t0) * 1000.0)

        if r.error:
            totals["errors"] += 1

        pt = int(r.prompt_tokens or 0)
        ct = int(r.completion_tokens or 0)
        tt = int(r.total_tokens or (pt + ct))

        totals["billed_total_tokens"] += tt
        totals["billed_cost"] += float(r.cost_estimate or 0.0)

        # update cache (not strictly needed)
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
                "latency_ms": r.latency_ms,
                "cached_at_utc": datetime.now(timezone.utc).isoformat(),
            },
        )

    avg_ms = sum(totals["lat_ms"]) / max(1, totals["n"])
    hit_rate_real = totals["hits"] / max(1, totals["n"])

    return {
        "target_hit_rate": target_hit_rate,
        "hit_rate_real": hit_rate_real,
        "avg_ms": avg_ms,
        "billed_cost": totals["billed_cost"],
        "billed_cost_per_req": totals["billed_cost"] / max(1, totals["n"]),
        "billed_total_tokens": totals["billed_total_tokens"],
        "errors": totals["errors"],
        # Prime stats are useful to mention but not part of measured run
        "prime_cost": prime_cost,
        "prime_billed_tokens": prime_billed_tokens,
        "prime_avg_ms": (sum(prime_lat_ms) / max(1, len(prime_lat_ms))) if prime_lat_ms else 0.0,
        "n": totals["n"],
    }


def main() -> None:
    settings = get_settings()
    model = settings.model
    prompts = read_prompts(PROMPTS_PATH)

    MAX_OUTPUT_TOKENS = 100
    HIT_RATES = [0.0, 0.25, 0.50, 0.75, 1.0]

    client = OpenAI()
    cache_dir = Path("outputs/cache/prompt_cache_sweep")
    cache = FileCache(cache_dir)

    console.print(f"Model: {model}")
    console.print(f"max_output_tokens: {MAX_OUTPUT_TOKENS}")
    console.print(f"Prompts: {len(prompts)}")
    console.print(f"Cache dir: {cache_dir}\n")

    results = []

    # Important: keep cache between hit-rate runs (we want primed cache)
    # But start from a clean cache for reproducibility.
    clear_dir(cache_dir)
    cache = FileCache(cache_dir)

    for hr in HIT_RATES:
        console.print(f"Running target hit rate: {int(hr*100)}%")
        r = run_workload_with_target_hit_rate(
            client=client,
            cache=cache,
            prompts=prompts,
            model=model,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            target_hit_rate=hr,
            cache_hit_latency_ms=5.0,
            seed=42,
        )
        results.append(r)

    # Table
    table = Table(title="ICP — Cache Hit Rate Sweep (Billed Cost)")
    table.add_column("Target hit")
    table.add_column("Real hit", justify="right")
    table.add_column("Avg ms", justify="right")
    table.add_column("€ billed / req", justify="right")
    table.add_column("€ billed total", justify="right")
    table.add_column("Errors", justify="right")

    for r in results:
        table.add_row(
            f'{int(r["target_hit_rate"]*100)}%',
            f'{r["hit_rate_real"]*100:.1f}%',
            f'{r["avg_ms"]:.1f}',
            f'{r["billed_cost_per_req"]:.6f}',
            f'{r["billed_cost"]:.6f}',
            str(r["errors"]),
        )

    console.print(table)

    # Save CSV
    out_dir = Path("outputs/reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"cache_hit_rate_sweep_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "model",
                "max_output_tokens",
                "n",
                "target_hit_rate",
                "hit_rate_real",
                "avg_ms",
                "billed_cost",
                "billed_cost_per_req",
                "billed_total_tokens",
                "errors",
                "prime_cost",
                "prime_billed_tokens",
                "prime_avg_ms",
            ],
        )
        w.writeheader()
        for r in results:
            w.writerow(
                {
                    "model": model,
                    "max_output_tokens": MAX_OUTPUT_TOKENS,
                    "n": r["n"],
                    "target_hit_rate": r["target_hit_rate"],
                    "hit_rate_real": r["hit_rate_real"],
                    "avg_ms": r["avg_ms"],
                    "billed_cost": r["billed_cost"],
                    "billed_cost_per_req": r["billed_cost_per_req"],
                    "billed_total_tokens": r["billed_total_tokens"],
                    "errors": r["errors"],
                    "prime_cost": r["prime_cost"],
                    "prime_billed_tokens": r["prime_billed_tokens"],
                    "prime_avg_ms": r["prime_avg_ms"],
                }
            )

    console.print(f"\nSaved CSV report to: {csv_path}")

    # Plot: cost per req vs hit rate
    x = [r["hit_rate_real"] * 100 for r in results]
    y_cost = [r["billed_cost_per_req"] for r in results]
    y_ms = [r["avg_ms"] for r in results]

    plt.figure()
    plt.plot(x, y_cost, marker="o")
    plt.xlabel("Cache hit rate (%)")
    plt.ylabel("Billed cost per request (€)")
    plt.title("ICP — Billed Cost vs Cache Hit Rate")
    cost_png = out_dir / "cache_cost_curve.png"
    plt.savefig(cost_png, dpi=200, bbox_inches="tight")
    plt.show()

    plt.figure()
    plt.plot(x, y_ms, marker="o")
    plt.xlabel("Cache hit rate (%)")
    plt.ylabel("Average latency (ms)")
    plt.title("ICP — Latency vs Cache Hit Rate")
    lat_png = out_dir / "cache_latency_curve.png"
    plt.savefig(lat_png, dpi=200, bbox_inches="tight")
    plt.show()

    console.print(f"Saved plots to: {cost_png} and {lat_png}")


if __name__ == "__main__":
    main()
