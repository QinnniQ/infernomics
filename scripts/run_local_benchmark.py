"""Explicit local-only benchmark CLI. Does not download models or call paid APIs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from icp.local_benchmark.runner import run
from icp.local_benchmark.store import public_export

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", default=["phi3:latest", "gemma3:latest"])
    parser.add_argument("--split", choices=["development", "calibration", "test"], default="test")
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--max-output-tokens", type=int, default=128)
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--export-id", help="Validate and publish an existing held-out experiment; no inference")
    parser.add_argument("--db", type=Path, default=ROOT / ".local/benchmarks.sqlite")
    args = parser.parse_args()
    if args.export_id:
        result = public_export(args.db, ROOT / "web/src/data/local-benchmark.json", experiment_id=args.export_id)
        print(json.dumps({"published": result["experiment"]["id"], "observations": len(result["observations"])}))
    else:
        result = run(ROOT / "data/eval_sets/local_v1.jsonl", args.db, models=args.models,
                     split=args.split, repetitions=args.repetitions, max_output_tokens=args.max_output_tokens,
                     timeout=args.timeout, dry_run=args.dry_run)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
