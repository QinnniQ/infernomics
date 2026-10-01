from types import SimpleNamespace

import pytest

from icp.cache import FileCache
from scripts import cache_hit_rate_sweep, run_cache_experiment


def test_cache_key_includes_configuration_and_round_trips(tmp_path):
    cache = FileCache(tmp_path)
    key = cache.make_key(model="m", max_output_tokens=50, prompt="p")
    assert key != cache.make_key(model="m", max_output_tokens=100, prompt="p")
    assert key != cache.make_key(model="other", max_output_tokens=50, prompt="p")
    assert cache.get(key) is None
    cache.set(key, {"output_text": "café", "cost_estimate": 0.1})
    assert cache.get(key) == {"output_text": "café", "cost_estimate": 0.1}


def test_warm_cache_avoids_billable_calls(tmp_path, monkeypatch):
    calls = []

    def fake_chat(client, model, prompt, max_output_tokens):
        calls.append(prompt)
        return SimpleNamespace(
            error=None, prompt_tokens=10, completion_tokens=5,
            total_tokens=15, cost_estimate=0.002, latency_ms=20,
            output_text="answer",
        )

    monkeypatch.setattr(run_cache_experiment, "run_one_chat", fake_chat)
    cache = FileCache(tmp_path)
    args = dict(client=None, cache=cache, prompts=["one", "two"], model="m", max_output_tokens=50)
    cold = run_cache_experiment.run_pass(**args, use_cache=False)
    warm = run_cache_experiment.run_pass(**args, use_cache=True)

    assert calls == ["one", "two"]
    assert cold["billed_cost"] == pytest.approx(0.004)
    assert cold["billed_total_tokens"] == 30
    assert warm["hit_rate"] == 1
    assert warm["billed_cost"] == 0
    assert warm["billed_total_tokens"] == 0


def test_failed_response_is_retried_instead_of_cached(tmp_path, monkeypatch):
    calls = []

    def fake_chat(client, model, prompt, max_output_tokens):
        calls.append(prompt)
        return SimpleNamespace(
            error="temporary failure" if len(calls) == 1 else None,
            prompt_tokens=10, completion_tokens=5, total_tokens=15,
            cost_estimate=0.002, latency_ms=20, output_text="answer",
        )

    monkeypatch.setattr(run_cache_experiment, "run_one_chat", fake_chat)
    cache = FileCache(tmp_path)
    args = dict(client=None, cache=cache, prompts=["one"], model="m", max_output_tokens=50)
    cold = run_cache_experiment.run_pass(**args, use_cache=False)
    warm = run_cache_experiment.run_pass(**args, use_cache=True)
    assert cold["errors"] == 1
    assert warm["hit_rate"] == 0
    assert len(calls) == 2


def test_hit_rate_sweep_separates_prime_from_measured_billing(tmp_path, monkeypatch):
    def fake_chat(client, model, prompt, max_output_tokens):
        return SimpleNamespace(
            error=None, prompt_tokens=10, completion_tokens=5,
            total_tokens=15, cost_estimate=0.002, latency_ms=20,
            output_text="answer",
        )

    monkeypatch.setattr(cache_hit_rate_sweep, "run_one_chat", fake_chat)
    cache = FileCache(tmp_path)
    args = dict(client=None, cache=cache, prompts=["one", "two"], model="m", max_output_tokens=50)
    full_hit = cache_hit_rate_sweep.run_workload_with_target_hit_rate(**args, target_hit_rate=1)
    no_hit = cache_hit_rate_sweep.run_workload_with_target_hit_rate(**args, target_hit_rate=0)
    assert full_hit["prime_cost"] == pytest.approx(0.004)
    assert full_hit["billed_cost"] == 0
    assert full_hit["hit_rate_real"] == 1
    assert no_hit["prime_cost"] == 0
    assert no_hit["billed_cost"] == pytest.approx(0.004)
    assert no_hit["hit_rate_real"] == 0
