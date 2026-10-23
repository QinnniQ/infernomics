"""CI integrity gate for both independent public evidence classes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from icp.local_benchmark.store import validate_public

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    old = json.loads((ROOT / "web/src/data/benchmark.json").read_text(encoding="utf-8"))
    assert old["schemaVersion"] == 1
    assert len(old["runs"]) == 3
    assert [r["maxOutputTokens"] for r in old["runs"]] == [50, 100, 200]
    assert all(len(run["items"]) == 20 for run in old["runs"])
    assert [sum(item["status"] == "incomplete" for item in run["items"]) for run in old["runs"]] == [14, 10, 4]
    # The archived run recorded this digest from the original CRLF file on Windows.
    # Git checks out LF on Linux, so restore those bytes before checking the archive.
    historical_bytes = (ROOT / "data/eval_sets/chat_prompts.jsonl").read_bytes()
    historical_bytes = historical_bytes.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    digest = hashlib.sha256(historical_bytes).hexdigest()
    assert all(run["datasetVersion"] == "chat-prompts-sha256:" + digest for run in old["runs"])
    local = json.loads((ROOT / "web/src/data/local-benchmark.json").read_text(encoding="utf-8"))
    assert local["schemaVersion"] == 2 and local["evidenceClass"] == "local-ollama"
    if local["experiment"] is None:
        assert local["observations"] == []
        print("Historical archive verified; local publication pending")
    else:
        validate_public(local["experiment"], local["observations"])
        assert local["experiment"]["datasetSha256"] == hashlib.sha256((ROOT / "data/eval_sets/local_v1.jsonl").read_bytes()).hexdigest()
        print(f"Historical archive and local experiment {local['experiment']['id']} verified")
    v2 = json.loads((ROOT / "web/src/data/local-v2-benchmark.json").read_text(encoding="utf-8"))
    assert v2["schemaVersion"] == 2 and v2["evidenceClass"] == "local-ollama"
    if v2["experiment"] is not None:
        validate_public(v2["experiment"], v2["observations"])
        assert v2["experiment"]["datasetVersion"] == "local-v2-frozen-2026-10-23"
        assert v2["experiment"]["datasetSha256"] == hashlib.sha256((ROOT / "data/eval_sets/local_v2.jsonl").read_bytes()).hexdigest()
        assert len({row["itemId"] for row in v2["observations"]}) == 12
    catalog = json.loads((ROOT / "web/src/data/model-catalog.v2.json").read_text(encoding="utf-8"))
    assert catalog["schemaVersion"] == 2 and len({m["id"] for m in catalog["models"]}) == len(catalog["models"])
    assert {m["provider"] for m in catalog["models"]} == {"OpenAI", "Anthropic", "Google", "xAI", "Ollama"}
    index = json.loads((ROOT / "web/src/data/evidence-index.v1.json").read_text(encoding="utf-8"))
    assert index["schemaVersion"] == 1
    by_id = {row["id"]: row for row in index["records"]}
    assert by_id["ollama-local-v1"]["sampleCount"] == len(local["observations"])
    assert by_id["ollama-local-v2"]["sampleCount"] == len(v2["observations"])
    assert by_id["provider-catalog-v2"]["modelCount"] == len(catalog["models"])
    assert by_id["gemini-free-tier"]["sampleCount"] == 0
    print("Provider catalogue, evidence classes, and v2 suite verified")


if __name__ == "__main__":
    main()
