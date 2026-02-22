from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from openai import OpenAI

from icp.pricing import estimate_llm_cost


@dataclass
class JudgeResult:
    quality_0_5: int
    grounded_0_5: int
    follows_instructions: bool
    notes: str

    judge_prompt_tokens: int
    judge_completion_tokens: int
    judge_total_tokens: int
    judge_cost_estimate: float
    judge_latency_ms: float

    error: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None


def _extract_json_object(text: str) -> Optional[dict]:
    """
    Robustly extract the first JSON object from a string.
    """
    if not text:
        return None

    # Fast path: whole string is JSON
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    # Try to find the first {...} block
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        return None

    candidate = m.group(0)
    try:
        obj = json.loads(candidate)
        if isinstance(obj, dict):
            return obj
    except Exception:
        return None

    return None


def judge_answer(
    *,
    client: OpenAI,
    judge_model: str,
    question: str,
    answer: str,
    context: str,
    max_output_tokens: int = 200,
    temperature: float = 0.0,
) -> JudgeResult:
    """
    LLM-as-judge rubric:
      - quality_0_5: overall helpfulness/correctness relative to context + question
      - grounded_0_5: how well answer is supported by provided context
      - follows_instructions: uses citations [doc_id], says "I don't know" if missing, etc.
    Returns strict JSON (best-effort) and accounts for judge cost.
    """
    rubric = (
        "You are a strict evaluator for a RAG system.\n"
        "Evaluate the ANSWER to the QUESTION using ONLY the provided CONTEXT.\n\n"
        "Return ONLY valid JSON with keys:\n"
        "  quality_0_5 (int 0-5)\n"
        "  grounded_0_5 (int 0-5)\n"
        "  follows_instructions (bool)\n"
        "  notes (string, <= 200 chars)\n\n"
        "Scoring guidance:\n"
        "- quality_0_5: correctness + completeness given the context.\n"
        "- grounded_0_5: does the answer make claims supported by context? penalize unsupported claims.\n"
        "- follows_instructions: uses citations like [doc_01], avoids outside knowledge, says 'I don't know' if needed.\n"
    )

    judge_input = (
        f"{rubric}\n"
        f"QUESTION:\n{question}\n\n"
        f"CONTEXT:\n{context}\n\n"
        f"ANSWER:\n{answer}\n"
    )

    t0 = time.perf_counter()
    try:
        resp = client.responses.create(
            model=judge_model,
            input=judge_input,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )
        latency_ms = (time.perf_counter() - t0) * 1000.0

        out_text = getattr(resp, "output_text", "") or ""
        obj = _extract_json_object(out_text)

        usage = getattr(resp, "usage", None)
        in_tok = int(getattr(usage, "input_tokens", 0) or 0) if usage else 0
        out_tok = int(getattr(usage, "output_tokens", 0) or 0) if usage else 0
        tot_tok = int(getattr(usage, "total_tokens", 0) or 0) if usage else (in_tok + out_tok)

        judge_cost = estimate_llm_cost(judge_model, in_tok, out_tok)

        if not obj:
            return JudgeResult(
                quality_0_5=0,
                grounded_0_5=0,
                follows_instructions=False,
                notes="Judge JSON parse failed",
                judge_prompt_tokens=in_tok,
                judge_completion_tokens=out_tok,
                judge_total_tokens=tot_tok,
                judge_cost_estimate=judge_cost,
                judge_latency_ms=latency_ms,
                error="judge_json_parse_failed",
                raw={"output_text": out_text},
            )

        # Clamp + coerce
        q = int(obj.get("quality_0_5", 0))
        g = int(obj.get("grounded_0_5", 0))
        q = max(0, min(5, q))
        g = max(0, min(5, g))
        fi = bool(obj.get("follows_instructions", False))
        notes = str(obj.get("notes", ""))[:200]

        raw = resp.model_dump() if hasattr(resp, "model_dump") else {"output_text": out_text}

        return JudgeResult(
            quality_0_5=q,
            grounded_0_5=g,
            follows_instructions=fi,
            notes=notes,
            judge_prompt_tokens=in_tok,
            judge_completion_tokens=out_tok,
            judge_total_tokens=tot_tok,
            judge_cost_estimate=judge_cost,
            judge_latency_ms=latency_ms,
            error=None,
            raw=raw,
        )

    except Exception as e:
        latency_ms = (time.perf_counter() - t0) * 1000.0
        return JudgeResult(
            quality_0_5=0,
            grounded_0_5=0,
            follows_instructions=False,
            notes="Judge exception",
            judge_prompt_tokens=0,
            judge_completion_tokens=0,
            judge_total_tokens=0,
            judge_cost_estimate=0.0,
            judge_latency_ms=latency_ms,
            error=str(e),
            raw={"error": str(e)},
        )
