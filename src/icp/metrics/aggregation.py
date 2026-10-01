"""Pure aggregation for a RAG retrieval-depth experiment."""

from __future__ import annotations

from collections.abc import Sequence

from icp.metrics.judge import JudgeResult
from icp.rag.rag_runner import RagResult


def percentile(values: Sequence[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return float(ordered[round((p / 100.0) * (len(ordered) - 1))])


def summarize_topk(pairs: Sequence[tuple[RagResult, JudgeResult]]) -> dict:
    """Keep generation, embedding, and judging spend separate.

    Failed judge calls may still incur cost, but cannot supply a valid score.
    """
    n = len(pairs)
    generations = [rag for rag, _ in pairs]
    judges = [judge for _, judge in pairs]
    valid_judges = [judge for judge in judges if not judge.error]

    llm_cost = sum(r.llm_cost_estimate for r in generations)
    embed_cost = sum(r.embed_cost_estimate for r in generations)
    judge_cost = sum(j.judge_cost_estimate for j in judges)
    inference_cost = llm_cost + embed_cost

    return {
        "n": n,
        "errors": sum(bool(r.error) for r in generations),
        "prompt_tokens": sum(int(r.prompt_tokens or 0) for r in generations),
        "completion_tokens": sum(int(r.completion_tokens or 0) for r in generations),
        "total_tokens": sum(int(r.total_tokens or (r.prompt_tokens or 0) + (r.completion_tokens or 0)) for r in generations),
        "avg_ms": sum(r.latency_ms for r in generations) / n if n else 0.0,
        "p95_ms": percentile([r.latency_ms for r in generations], 95),
        "llm_cost_total": llm_cost,
        "embed_cost_total": embed_cost,
        "cost_total": inference_cost,
        "cost_per_req": inference_cost / n if n else 0.0,
        "judge_quality_avg_0_5": sum(j.quality_0_5 for j in valid_judges) / len(valid_judges) if valid_judges else None,
        "judge_grounded_avg_0_5": sum(j.grounded_0_5 for j in valid_judges) / len(valid_judges) if valid_judges else None,
        "judge_follows_rate": sum(j.follows_instructions for j in valid_judges) / len(valid_judges) if valid_judges else None,
        "judge_cost_total": judge_cost,
        "judge_cost_per_req": judge_cost / n if n else 0.0,
        "judge_avg_ms": sum(j.judge_latency_ms for j in judges) / len(judges) if judges else 0.0,
        "judge_errors": len(judges) - len(valid_judges),
        "judge_valid_n": len(valid_judges),
        "cost_total_including_eval": inference_cost + judge_cost,
        "cost_per_req_including_eval": (inference_cost + judge_cost) / n if n else 0.0,
    }
