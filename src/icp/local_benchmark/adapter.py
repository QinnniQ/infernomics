"""Provider-neutral call contract and a localhost-only Ollama implementation."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Protocol
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:11434"


class ModelAdapter(Protocol):
    def generate(self, model: str, prompt: str, *, temperature: float, seed: int,
                 max_output_tokens: int, context_tokens: int, timeout: float) -> dict: ...


@dataclass
class OllamaAdapter:
    """Uses only the documented local HTTP API. It never pulls a model."""

    base: str = BASE

    def __post_init__(self) -> None:
        if self.base not in {BASE, "http://localhost:11434"}:
            raise ValueError("Only the local Ollama daemon is allowed")

    def request(self, route: str, payload: dict | None = None, timeout: float = 10) -> dict:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(self.base + route, body, {"Content-Type": "application/json"})
        with urlopen(request, timeout=timeout) as response:
            value = json.load(response)
        if not isinstance(value, dict):
            raise ValueError("Unexpected Ollama response")
        return value

    def installed_models(self) -> dict[str, dict]:
        data = self.request("/api/tags")
        return {m["name"]: m for m in data.get("models", []) if isinstance(m, dict) and m.get("name")}

    def version(self) -> str:
        return str(self.request("/api/version").get("version", "unknown"))

    def generate(self, model: str, prompt: str, *, temperature: float, seed: int,
                 max_output_tokens: int, context_tokens: int, timeout: float) -> dict:
        payload = {
            "model": model, "messages": [{"role": "user", "content": prompt}],
            "stream": False, "think": False,
            "options": {"temperature": temperature, "seed": seed,
                        "num_predict": max_output_tokens, "num_ctx": context_tokens},
        }
        start = time.perf_counter_ns()
        data = self.request("/api/chat", payload, timeout=timeout)
        wall_ms = (time.perf_counter_ns() - start) / 1_000_000
        if data.get("model") != model or not isinstance(data.get("message"), dict):
            raise ValueError("Ollama returned a mismatched model or malformed message")
        ns_fields = ("total_duration", "load_duration", "prompt_eval_duration", "eval_duration")
        counts = ("prompt_eval_count", "prompt_eval_cached_count", "eval_count")
        for key in (*ns_fields, *counts):
            value = data.get(key)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f"Invalid Ollama metric: {key}")
        reason = data.get("done_reason")
        status = "incomplete" if reason == "length" else "completed" if data.get("done") is True and reason == "stop" else "unknown"
        evaluation_ns = data.get("eval_duration")
        output_count = data.get("eval_count")
        return {
            "response": data["message"].get("content"), "status": status,
            "doneReason": reason, "wallMs": round(wall_ms, 3),
            "ollamaTotalMs": _ms(data.get("total_duration")),
            "loadMs": _ms(data.get("load_duration")),
            "promptMs": _ms(data.get("prompt_eval_duration")),
            "generationMs": _ms(evaluation_ns),
            "inputTokens": data.get("prompt_eval_count"),
            "cachedInputTokens": data.get("prompt_eval_cached_count"),
            "outputTokens": output_count,
            "tokensPerSecond": round(output_count * 1_000_000_000 / evaluation_ns, 3)
            if output_count is not None and evaluation_ns else None,
        }


def _ms(ns: int | None) -> float | None:
    return round(ns / 1_000_000, 3) if ns is not None else None
