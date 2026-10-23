"""Dry-run by default; optional private v2 Gemini benchmark with a verified free-tier project."""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from icp.local_benchmark.dataset import load_dataset
from icp.local_benchmark.evaluation import score
from icp.provider_adapters import GEMINI_MODEL, FreeTierAttestation, GeminiFreeTierAdapter

ROOT = Path(__file__).resolve().parents[1]


def plan(project_id: str, benchmark_v2: bool, max_requests: int, prompt: str) -> tuple[list[dict], str | None]:
    if not 1 <= max_requests <= 12:
        raise ValueError("At most 12 explicit free-tier requests are allowed")
    if benchmark_v2:
        rows, digest = load_dataset(ROOT / "data/eval_sets/local_v2.jsonl")
        return [row for row in rows if row["split"] == "test"][:max_requests], digest
    if max_requests != 1:
        raise ValueError("A single-prompt probe permits exactly one request")
    return [{"id": "probe", "prompt": prompt}], None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", default="unconfirmed", help="Exact project ID shown in Google AI Studio")
    parser.add_argument("--prompt", default="Reply READY.", help="Single probe prompt when --benchmark-v2 is absent")
    parser.add_argument("--benchmark-v2", action="store_true", help="Use the 12 held-out tasks from the frozen local v2 suite")
    parser.add_argument("--max-requests", type=int, default=1, help="Explicit request cap, 1–12; default one")
    parser.add_argument("--execute-free-tier", action="store_true", help="Explicit local network opt-in")
    parser.add_argument("--attestation", type=Path, default=ROOT / ".local/gemini-free-tier-attestation.json")
    args = parser.parse_args()
    items, digest = plan(args.project_id, args.benchmark_v2, args.max_requests, args.prompt)
    if not args.execute_free_tier:
        print(json.dumps({"mode": "dry-run", "provider": "Google", "model": GEMINI_MODEL,
                          "projectId": args.project_id, "plannedItemIds": [item["id"] for item in items],
                          "plannedRequests": len(items), "networkRequests": 0}, indent=2))
        return
    attestation = FreeTierAttestation.load(args.attestation)
    if attestation.remaining_requests_today < len(items):
        raise ValueError("Attested remaining free-tier quota is smaller than the requested call cap")
    # Validate once before any request. Adapter validates again for each individual call.
    import os
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ValueError("GEMINI_API_KEY is required for explicitly opted-in execution")
    attestation.validate(args.project_id, key)
    adapter = GeminiFreeTierAdapter(args.project_id, attestation, execute=True)
    result = {"schemaVersion": 3, "evidenceClass": "hosted-api-measurement",
              "model": GEMINI_MODEL, "provider": "Google", "projectId": args.project_id,
              "executedAt": datetime.now(timezone.utc).isoformat(),
              "datasetVersion": "local-v2-frozen-2026-10-23" if args.benchmark_v2 else "probe",
              "datasetSha256": digest, "split": "test" if args.benchmark_v2 else None,
              "plannedTaskCount": 12 if args.benchmark_v2 else 1, "requestCap": len(items),
              "limitations": "One project and one sequential run; no retries, tools, paid fallback or public export. Partial runs are not comparable to complete local studies.",
              "observations": []}
    # A private path is created only after all cost gates pass. No key is written.
    output = ROOT / ".local/gemini" / f"gemini-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    for index, item in enumerate(items):
        if index:
            time.sleep(65)  # Conservative project-rate spacing; no retry on 429 or any other error.
        measurement = adapter.generate(GEMINI_MODEL, item["prompt"], max_output_tokens=128)
        result["observations"].append({"itemId": item["id"], "prompt": item["prompt"],
                                       "measurement": measurement,
                                       "evaluation": score(item, measurement["response"]) if args.benchmark_v2 else None})
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"completed": index + 1, "of": len(items), "itemId": item["id"], "privateOutput": str(output)}), flush=True)


if __name__ == "__main__":
    main()
