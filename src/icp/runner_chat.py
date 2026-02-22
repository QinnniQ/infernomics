from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from openai import OpenAI
from .pricing import estimate_cost

@dataclass
class ChatResult:
    output_text: Optional[str]
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    total_tokens: Optional[int]
    cost_estimate: float
    latency_ms: float
    error: Optional[str]
    raw: Dict[str, Any]

def run_one_chat(client: OpenAI, model: str, prompt: str, max_output_tokens: int = 200) -> ChatResult:
    t0 = time.perf_counter()
    try:
        resp = client.responses.create(
            model=model,
            input=prompt,
            max_output_tokens=max_output_tokens,
        )
        latency_ms = (time.perf_counter() - t0) * 1000.0

        # The SDK provides output_text convenience in examples. :contentReference[oaicite:2]{index=2}
        output_text = getattr(resp, "output_text", None)

        usage = getattr(resp, "usage", None)
        prompt_tokens = getattr(usage, "input_tokens", None) if usage else None
        completion_tokens = getattr(usage, "output_tokens", None) if usage else None
        total_tokens = getattr(usage, "total_tokens", None) if usage else None

        cost = estimate_cost(
            model=model,
            prompt_tokens=int(prompt_tokens or 0),
            completion_tokens=int(completion_tokens or 0),
        )

        raw = resp.model_dump() if hasattr(resp, "model_dump") else dict(resp)

        return ChatResult(
            output_text=output_text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_estimate=cost,
            latency_ms=latency_ms,
            error=None,
            raw=raw,
        )
    except Exception as e:
        latency_ms = (time.perf_counter() - t0) * 1000.0
        return ChatResult(
            output_text=None,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            cost_estimate=0.0,
            latency_ms=latency_ms,
            error=str(e),
            raw={"error": str(e)},
        )
