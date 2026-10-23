import copy
import json
from pathlib import Path

import pytest

from icp.local_benchmark.adapter import OllamaAdapter
from icp.local_benchmark.dataset import load_dataset
from icp.local_benchmark.evaluation import score
from icp.local_benchmark.store import validate_public

DATASET = Path(__file__).resolve().parents[1] / "data/eval_sets/local_v1.jsonl"


def test_dataset_is_versioned_unique_and_separated(tmp_path):
    items, digest = load_dataset(DATASET)
    assert len(items) == 18 and len(digest) == 64
    assert {row["split"] for row in items} == {"development", "calibration", "test"}
    assert len([row for row in items if row["split"] == "test"]) == 6
    bad = tmp_path / "bad.jsonl"
    bad.write_text(json.dumps(items[0]) + "\n" + json.dumps(items[0]), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate item ID"):
        load_dataset(bad)


@pytest.mark.parametrize("rule,response,expected", [
    ({"kind": "exact", "expected": "OK"}, " OK \n", True),
    ({"kind": "exact", "expected": "OK"}, "ok", False),
    ({"kind": "integer", "expected": 27}, "27", True),
    ({"kind": "integer", "expected": 27}, "The answer is 27", False),
    ({"kind": "json_fields", "expected": {"case": 73}}, '{"case":73,"extra":1}', True),
    ({"kind": "json_fields", "expected": {"case": 73}}, '{"case":"73"}', False),
    ({"kind": "json_fields", "expected": {"case": 73}}, "```json", False),
])
def test_objective_scoring_boundaries(rule, response, expected):
    assert score({"scoring": rule}, response)["passed"] is expected


def test_subjective_scoring_stays_unassessed():
    result = score({"scoring": {"kind": "manual", "facts": ["one fact"]}}, "any answer")
    assert result["passed"] is None
    assert result["rubric"] == ["one fact"]


def test_adapter_distinguishes_wall_and_server_metrics(monkeypatch):
    adapter = OllamaAdapter()
    monkeypatch.setattr(adapter, "request", lambda *args, **kwargs: {
        "model": "phi3:latest", "message": {"content": "27"}, "done": True, "done_reason": "stop",
        "total_duration": 2_000_000_000, "load_duration": 100_000_000,
        "prompt_eval_duration": 200_000_000, "eval_duration": 1_000_000_000,
        "prompt_eval_count": 20, "eval_count": 10})
    result = adapter.generate("phi3:latest", "prompt", temperature=0, seed=42,
                              max_output_tokens=128, context_tokens=2048, timeout=10)
    assert result["status"] == "completed"
    assert result["ollamaTotalMs"] == 2000
    assert result["tokensPerSecond"] == 10
    assert result["wallMs"] >= 0


def test_adapter_rejects_remote_host_and_corrupt_metric():
    with pytest.raises(ValueError, match="local"):
        OllamaAdapter("https://paid.example.com")
    adapter = OllamaAdapter()
    adapter.request = lambda *args, **kwargs: {"model": "phi3:latest", "message": {"content": "x"}, "eval_count": -1}
    with pytest.raises(ValueError, match="Invalid Ollama metric"):
        adapter.generate("phi3:latest", "x", temperature=0, seed=1,
                         max_output_tokens=16, context_tokens=256, timeout=10)


def _valid_export():
    meta = {"schemaVersion": 2, "runtime": "Ollama", "split": "test", "id": "experiment",
            "datasetSha256": "a" * 64, "repetitions": 1,
            "models": [{"id": model, "digest": "b" * 64, "family": model,
                        "parameterSize": "1B", "quantization": "Q4"} for model in ("a", "b")]}
    rows = [{"id": model + ":item", "experimentId": "experiment", "model": model,
             "itemId": "item", "prompt": "same prompt", "repetition": 0, "status": "completed",
             "error": None, "evaluation": {"passed": True}, "wallMs": 1,
             "inputTokens": 1, "outputTokens": 1} for model in ("a", "b")]
    return meta, rows


def test_export_rejects_mismatch_and_corruption():
    meta, rows = _valid_export()
    validate_public(meta, rows)
    bad = copy.deepcopy(rows)
    bad[1]["prompt"] = "different"
    with pytest.raises(ValueError, match="Mismatched prompt"):
        validate_public(meta, bad)
    bad = copy.deepcopy(rows)
    bad[1]["wallMs"] = -1
    with pytest.raises(ValueError, match="Corrupt wallMs"):
        validate_public(meta, bad)
    with pytest.raises(ValueError, match="coverage"):
        validate_public(meta, rows[:1])
    bad = copy.deepcopy(rows)
    bad[1]["id"] = "other-id"
    bad[1]["model"] = "a"
    with pytest.raises(ValueError, match="Duplicate model"):
        validate_public(meta, bad)
