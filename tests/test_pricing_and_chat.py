from types import SimpleNamespace

import pytest

from icp.pricing import estimate_embed_cost, estimate_llm_cost
from icp.runner_chat import run_one_chat


def test_cost_estimates_use_both_token_classes():
    assert estimate_llm_cost("gpt-4o-mini", 1_000_000, 500_000) == pytest.approx(0.42)
    assert estimate_embed_cost("text-embedding-3-small", 500_000) == pytest.approx(0.0093)
    assert estimate_llm_cost("gpt-4o-mini", 0, 0) == 0


def test_unconfigured_model_and_invalid_usage_fail_loudly():
    with pytest.raises(ValueError, match="No LLM price"):
        estimate_llm_cost("unconfigured", 100, 10)
    with pytest.raises(ValueError, match="No embedding price"):
        estimate_embed_cost("unconfigured", 100)
    with pytest.raises(ValueError, match="non-negative"):
        estimate_llm_cost("gpt-4o-mini", -1, 0)


def test_chat_runner_records_estimated_cost_and_usage():
    response = SimpleNamespace(
        output_text="Answer",
        usage=SimpleNamespace(input_tokens=100, output_tokens=20, total_tokens=120),
        model_dump=lambda: {"id": "sample"},
    )
    client = SimpleNamespace(responses=SimpleNamespace(create=lambda **kwargs: response))

    result = run_one_chat(client, "gpt-4o-mini", "Question", max_output_tokens=50)

    assert result.error is None
    assert result.total_tokens == 120
    assert result.output_text == "Answer"
    assert result.cost_estimate == pytest.approx(100 * 0.14 / 1_000_000 + 20 * 0.56 / 1_000_000)


def test_chat_runner_surfaces_api_error():
    def fail(**kwargs):
        raise RuntimeError("API unavailable")

    client = SimpleNamespace(responses=SimpleNamespace(create=fail))
    result = run_one_chat(client, "gpt-4o-mini", "Question")
    assert result.error == "API unavailable"
    assert result.cost_estimate == 0
