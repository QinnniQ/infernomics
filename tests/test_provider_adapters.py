from datetime import date
import hashlib
import io
import json

import pytest

from icp.provider_adapters import (AnthropicAdapter, FreeTierAttestation,
                                   GeminiFreeTierAdapter, PaidInferenceDisabled,
                                   XAIAdapter, GEMINI_MODEL)


def test_paid_adapters_cannot_execute_even_with_credentials(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("XAI_API_KEY", "test")
    for adapter in (AnthropicAdapter(), XAIAdapter()):
        with pytest.raises(PaidInferenceDisabled):
            adapter.generate("prompt")


def test_gemini_default_is_network_free(monkeypatch):
    monkeypatch.setattr("icp.provider_adapters.urlopen", lambda *a, **kw: pytest.fail("network attempted"))
    result = GeminiFreeTierAdapter("unconfirmed").generate(GEMINI_MODEL, "Reply READY.")
    assert result["networkRequests"] == 0 and result["mode"] == "dry-run"


def test_gemini_requires_exact_current_free_tier_attestation(monkeypatch):
    monkeypatch.setattr("icp.provider_adapters.urlopen", lambda *a, **kw: pytest.fail("network attempted"))
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    bad = FreeTierAttestation("project-a", GEMINI_MODEL, date.today().isoformat(), "Paid", "Enabled", True, hashlib.sha256(b"test").hexdigest(), 1)
    with pytest.raises(ValueError, match="Free tier"):
        GeminiFreeTierAdapter("project-a", bad, True).generate(GEMINI_MODEL, "test")
    with pytest.raises(ValueError, match="attestation"):
        GeminiFreeTierAdapter("project-b", bad, True).generate(GEMINI_MODEL, "test")
    good = FreeTierAttestation("project-a", GEMINI_MODEL, date.today().isoformat(), "Free", "Disabled", True, "0" * 64, 1)
    with pytest.raises(ValueError, match="API key"):
        GeminiFreeTierAdapter("project-a", good, True).generate(GEMINI_MODEL, "test")


def test_gemini_adapter_enforces_attested_request_budget(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    calls = []
    def fake_open(request, timeout):
        calls.append(request.full_url)
        return io.BytesIO(json.dumps({"candidates": [{"content": {"parts": [{"text": "READY"}]}, "finishReason": "STOP"}]}).encode())
    monkeypatch.setattr("icp.provider_adapters.urlopen", fake_open)
    attestation = FreeTierAttestation("project-a", GEMINI_MODEL, date.today().isoformat(), "Free", "Disabled", True, hashlib.sha256(b"test").hexdigest(), 1)
    adapter = GeminiFreeTierAdapter("project-a", attestation, True)
    assert adapter.generate(GEMINI_MODEL, "Reply READY.")["response"] == "READY"
    with pytest.raises(ValueError, match="allowance exhausted"):
        adapter.generate(GEMINI_MODEL, "Reply READY.")
    assert len(calls) == 1
