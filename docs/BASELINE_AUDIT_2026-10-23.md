# Baseline audit — 23 October 2026

This records the state before the 2.0 work. The checkout was clean at `17a690e`.

## Public evidence

`web/src/data/benchmark.json` is the validated static export of three February 2026 GPT-4o-mini runs. It contains 20 identical prompts per output cap (50, 100, 200), 60 attempts total, and 28 `max_output_tokens` incomplete outcomes (14, 10, 4). The saved model snapshot is `gpt-4o-mini-2024-07-18`. Measured latency is SDK wall time. USD cost is a later list-price estimate. No chat answer quality was scored. The original SQLite archive is ignored; the committed JSON is its publication-safe record.

## Baseline architecture

- `scripts/run_sweep.py`, `src/icp/runner_chat.py`, and `src/icp/storage_sqlite.py` implement the historical commercial API path. Running it requires explicit credentials and can incur charges.
- `scripts/export_public_benchmark.py` reads SQLite and checks caps, model identity, and matching prompts before publishing `web/src/data/benchmark.json`.
- `web/src/lib/benchmark.ts` validates that snapshot and calculates medians, completion counts, pricing estimates, filtering, and comparison eligibility.
- `web/src/main.tsx` contained most UI state and presentation. `web/src/styles.css` provided a responsive light interface.
- `.github/workflows/ci.yml` checked the web app; `.github/workflows/tests.yml` checked the original Python paths.

## Baseline limits

Only one model appeared publicly, so the existing comparison was between output-token caps. Historical runs lack recorded temperature, reliable pricing at execution time, retries, and quality labels. Twenty convenience prompts cannot establish a general model ranking. The original Python test environment requires dependencies absent from the system Python; the 2.0 local modules use only the standard library.

## Local capability checked before experiments

The Windows host had Ollama 0.15.6, `phi3:latest` (2.2 GB), and `gemma3:latest` (3.3 GB) already installed. The C: drive had about 58.6 GB free and physical RAM was 16.85 GB. No model download was necessary. Ollama's local server was accessible after a sandbox permission escalation. No paid provider was invoked.
