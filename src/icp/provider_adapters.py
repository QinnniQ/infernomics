"""Explicitly gated hosted adapters. Importing this module never sends requests."""
from __future__ import annotations

import json
import os
import time
import hashlib
import hmac
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen

GEMINI_MODEL = "gemini-3.1-flash-lite"
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/"


class PaidInferenceDisabled(RuntimeError):
    """A paid provider is present for architecture review only."""


@dataclass(frozen=True)
class AnthropicAdapter:
    model: str = "claude-haiku-4-5-20251001"

    def generate(self, *args: object, **kwargs: object) -> dict:
        raise PaidInferenceDisabled("Anthropic API execution is disabled; no paid request was sent")


@dataclass(frozen=True)
class XAIAdapter:
    model: str = "grok-4.6"

    def generate(self, *args: object, **kwargs: object) -> dict:
        raise PaidInferenceDisabled("xAI API execution is disabled; no paid request was sent")


@dataclass(frozen=True)
class FreeTierAttestation:
    """Human-confirmed status from AI Studio, not a programmatic billing guarantee."""

    project_id: str
    model: str
    verified_on: str
    tier: str
    billing: str
    model_available: bool
    api_key_sha256: str
    remaining_requests_today: int

    @classmethod
    def load(cls, path: Path) -> "FreeTierAttestation":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(**data)

    def validate(self, project_id: str, api_key: str) -> None:
        if not project_id or self.project_id != project_id or self.model != GEMINI_MODEL:
            raise ValueError("Project ID and allowlisted Gemini model must match the local attestation")
        if self.tier != "Free" or self.billing != "Disabled" or self.model_available is not True:
            raise ValueError("AI Studio must confirm Free tier, billing disabled, and model availability")
        if self.verified_on != date.today().isoformat():
            raise ValueError("Reconfirm project eligibility in AI Studio today before any request")
        if type(self.remaining_requests_today) is not int or self.remaining_requests_today < 1:
            raise ValueError("A positive confirmed remaining free-tier request quota is required")
        if not hmac.compare_digest(self.api_key_sha256, hashlib.sha256(api_key.encode()).hexdigest()):
            raise ValueError("API key does not match the key manually verified for this free-tier project")


@dataclass
class GeminiFreeTierAdapter:
    """Text-only free-tier path; caller must opt in and attest exact project status."""

    project_id: str
    attestation: FreeTierAttestation | None = None
    execute: bool = False
    requests_sent: int = 0

    def generate(self, model: str, prompt: str, *, temperature: float = 0,
                 max_output_tokens: int = 128, timeout: float = 30) -> dict:
        if model != GEMINI_MODEL or not prompt.strip() or not 1 <= max_output_tokens <= 128 or not 0 <= temperature <= 2 or timeout < 5:
            raise ValueError("Only allowlisted text model and bounded output are supported")
        payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                   "generationConfig": {"temperature": temperature, "maxOutputTokens": max_output_tokens}}
        if not self.execute:
            return {"mode": "dry-run", "provider": "Google", "model": model,
                    "projectId": self.project_id, "requestShape": payload, "networkRequests": 0}
        if self.attestation is None:
            raise ValueError("Current local free-tier project attestation required")
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise ValueError("GEMINI_API_KEY is required only for opted-in execution")
        self.attestation.validate(self.project_id, key)
        if self.requests_sent >= self.attestation.remaining_requests_today:
            raise ValueError("Confirmed free-tier request allowance exhausted")
        self.requests_sent += 1  # Count an attempted request even if the provider returns an error.
        request = Request(GEMINI_ENDPOINT + model + ":generateContent", json.dumps(payload).encode("utf-8"),
                          {"Content-Type": "application/json", "x-goog-api-key": key}, method="POST")
        start = time.perf_counter_ns()
        with urlopen(request, timeout=timeout) as response:
            data = json.load(response)
        wall_ms = (time.perf_counter_ns() - start) / 1_000_000
        candidate = (data.get("candidates") or [{}])[0]
        parts = (candidate.get("content") or {}).get("parts") or []
        text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
        usage = data.get("usageMetadata") or {}
        return {"mode": "hosted-api-measurement", "provider": "Google", "model": model,
                "projectId": self.project_id, "response": text, "finishReason": candidate.get("finishReason"),
                "wallMs": round(wall_ms, 3), "inputTokens": usage.get("promptTokenCount"),
                "outputTokens": usage.get("candidatesTokenCount"),
                "thinkingTokens": usage.get("thoughtsTokenCount"),
                "billing": "free-tier-attested", "networkRequests": 1}
