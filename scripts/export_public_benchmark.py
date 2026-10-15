"""Export the comparable saved chat sweep without publishing provider response metadata.

This script is read-only with respect to outputs/results.sqlite. It deliberately
excludes older runs whose generation cap was not recorded.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "outputs/results.sqlite"
DATASET = ROOT / "data/eval_sets/chat_prompts.jsonl"
DEST = ROOT / "web/src/data/benchmark.json"
CAPS = {50, 100, 200}


def export() -> dict:
    if not DB.exists():
        raise FileNotFoundError(f"Saved benchmark database missing: {DB}")
    prompts = [json.loads(line)["prompt"] for line in DATASET.read_text(encoding="utf-8").splitlines()]
    conn = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    runs = []
    for run in conn.execute("SELECT * FROM runs ORDER BY created_at_utc"):
        meta = json.loads(run["meta_json"])
        cap = meta.get("max_output_tokens")
        if meta.get("workload") != "chat" or cap not in CAPS:
            continue
        items = []
        response_models = set()
        rows = conn.execute("SELECT * FROM results WHERE run_id=? ORDER BY idx", (run["run_id"],)).fetchall()
        if len(rows) != len(prompts) or [row["prompt"] for row in rows] != prompts:
            raise ValueError(f"Prompt set mismatch in {run['run_id']}")
        for row in rows:
            raw = json.loads(row["raw_json"])
            if raw.get("max_output_tokens") != cap or not str(raw.get("model", "")).startswith(run["model"]):
                raise ValueError(f"Model or cap mismatch in {run['run_id']} item {row['idx']}")
            response_models.add(raw["model"])
            items.append({
                "id": f"{run['run_id']}:{row['idx']}",
                "index": row["idx"],
                "prompt": row["prompt"],
                "response": row["output_text"],
                "inputTokens": row["prompt_tokens"],
                "outputTokens": row["completion_tokens"],
                "latencyMs": round(row["latency_ms"], 3) if row["latency_ms"] is not None else None,
                "status": "error" if row["error"] else raw.get("status", "unknown"),
                "incompleteReason": (raw.get("incomplete_details") or {}).get("reason"),
                "error": bool(row["error"]),
            })
        if len(response_models) != 1:
            raise ValueError(f"More than one response model in {run['run_id']}")
        runs.append({
            "id": run["run_id"],
            "executedAt": run["created_at_utc"],
            "provider": "OpenAI",
            "model": run["model"],
            "resolvedModel": response_models.pop(),
            "task": "General chat prompts",
            "datasetVersion": "chat-prompts-sha256:" + hashlib.sha256(DATASET.read_bytes()).hexdigest(),
            "maxOutputTokens": cap,
            "items": items,
        })
    if {run["maxOutputTokens"] for run in runs} != CAPS or len(runs) != 3:
        raise ValueError("Expected exactly one saved run for each output-token cap")
    conn.close()
    payload = {
        "schemaVersion": 1,
        "source": "outputs/results.sqlite (local archive; raw provider responses excluded)",
        "pricing": {
            "currency": "USD",
            "inputPerMillion": 0.15,
            "outputPerMillion": 0.60,
            "verifiedOn": "2026-10-15",
            "sourceUrl": "https://developers.openai.com/api/docs/models/gpt-4o-mini",
            "note": "Current standard text list price. Recalculated estimates, not historical invoices or the archived zero cost field. No caching or batch discounts.",
        },
        "runs": runs,
    }
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    result = export()
    print(f"Exported {len(result['runs'])} runs / {sum(len(r['items']) for r in result['runs'])} observations to {DEST}")
