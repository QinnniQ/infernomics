from types import SimpleNamespace

import pytest

from icp.metrics.aggregation import summarize_topk
from icp.metrics.judge import JudgeResult, judge_answer
from icp.rag.rag_runner import RagResult


def rag(*, error=None):
    return RagResult("answer", 100, 20, 120, 0.002, 0.001, 50, error, {})


def judge(*, quality=4, error=None, cost=0.003):
    return JudgeResult(quality, 3, True, "ok", 50, 10, 60, cost, 25, error=error)


def test_topk_aggregation_separates_inference_and_evaluation_cost():
    result = summarize_topk([(rag(), judge()), (rag(), judge(quality=2, error="bad_json"))])
    assert result["n"] == 2
    assert result["judge_valid_n"] == 1
    assert result["judge_errors"] == 1
    assert result["judge_quality_avg_0_5"] == 4
    assert result["llm_cost_total"] == pytest.approx(0.004)
    assert result["embed_cost_total"] == pytest.approx(0.002)
    assert result["judge_cost_total"] == pytest.approx(0.006)
    assert result["cost_per_req"] == pytest.approx(0.003)
    assert result["cost_per_req_including_eval"] == pytest.approx(0.006)


def test_topk_aggregation_empty_and_failed_judges():
    assert summarize_topk([])["cost_per_req_including_eval"] == 0
    result = summarize_topk([(rag(error="generation_failed"), judge(error="generation_failed", cost=0))])
    assert result["errors"] == 1
    assert result["judge_quality_avg_0_5"] is None
    assert result["judge_valid_n"] == 0


def test_judge_records_usage_even_when_json_is_invalid():
    response = SimpleNamespace(
        output_text="not JSON",
        usage=SimpleNamespace(input_tokens=100, output_tokens=20, total_tokens=120),
    )
    client = SimpleNamespace(responses=SimpleNamespace(create=lambda **kwargs: response))
    result = judge_answer(client=client, judge_model="gpt-4o-mini", question="q", answer="a", context="c")
    assert result.error == "judge_json_parse_failed"
    assert result.judge_total_tokens == 120
    assert result.judge_cost_estimate == pytest.approx(100 * 0.14 / 1_000_000 + 20 * 0.56 / 1_000_000)


def test_judge_parses_and_clamps_scores():
    response = SimpleNamespace(
        output_text='prefix {"quality_0_5": 9, "grounded_0_5": -2, "follows_instructions": true, "notes": "ok"} suffix',
        usage=None,
        model_dump=lambda: {"id": "sample"},
    )
    client = SimpleNamespace(responses=SimpleNamespace(create=lambda **kwargs: response))
    result = judge_answer(client=client, judge_model="gpt-4o-mini", question="q", answer="a", context="c")
    assert result.error is None
    assert (result.quality_0_5, result.grounded_0_5) == (5, 0)
    assert result.follows_instructions is True


def test_invalid_judge_schema_keeps_billable_usage():
    response = SimpleNamespace(
        output_text='{"quality_0_5": 4, "grounded_0_5": 3, "follows_instructions": "false"}',
        usage=SimpleNamespace(input_tokens=100, output_tokens=20, total_tokens=120),
    )
    client = SimpleNamespace(responses=SimpleNamespace(create=lambda **kwargs: response))
    result = judge_answer(client=client, judge_model="gpt-4o-mini", question="q", answer="a", context="c")
    assert result.error == "judge_invalid_schema"
    assert result.judge_cost_estimate > 0
