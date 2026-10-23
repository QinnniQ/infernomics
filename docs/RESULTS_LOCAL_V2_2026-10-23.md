# Expanded local evaluation · 23 October 2026

Experiment `local-20261023T130517Z-a5c479c9` used the frozen `local-v2-frozen-2026-10-23` held-out split: 12 prompts, two models, one attempt per model and prompt, 24 recorded observations. Dataset SHA-256: `b6a68cc617f7d7d76c76ee73f82e6a57a1caecf3b57a56e5a17378f463d478eb`. The exact responses, timing, status and scoring rationale are in [the static snapshot](../web/src/data/local-v2-benchmark.json).

| Installed artifact | Completed / attempts | Output-limit incomplete | Objective checks passed / assessed | Median completed client wall time |
| --- | ---: | ---: | ---: | ---: |
| `phi3:latest` · digest `4f2222927938…` | 10 / 12 | 2 | 3 / 6 | 12,970 ms (n=10) |
| `gemma3:latest` · digest `a2af6cc3eb7f…` | 9 / 12 | 3 | 2 / 6 | 6,002 ms (n=9) |

The six other tasks per model have manual rubrics but no quality rating. The strict JSON extractor rejected Markdown-fenced responses for both models. One Gemma answer extracted `Station Delta` where the expected value was `Delta`. The first arithmetic task was wrong for both; Phi-3 answered the second correctly with a bare integer while Gemma answered incorrectly. These are narrow task checks, not a broad quality comparison. Incomplete responses are excluded from the displayed completed-only latency median but remain in the attempt count. There were no transport errors.

The run used Ollama 0.15.6 on the same Windows host as v1, temperature 0, seed 42, 2,048 context tokens, 128 output tokens, one separate warmup per model and shuffled execution order. It made no hosted API request. The source tree was dirty during execution (`4093beb…+dirty`), and the snapshot records that fact. No GPU, power or streaming time to first token was measured.

V1 had six held-out prompts with two repetitions (24 attempts); v2 has 12 held-out prompts with one repetition (24 attempts). Categories align, but individual tasks and denominators differ. The two sets should be viewed side by side, **never pooled into one score or interpreted as a longitudinal model improvement**. Neither set estimates production performance or supports a claim that one provider is generally faster or better. The February 2026 hosted GPT-4o-mini archive used different prompts and infrastructure and is further separated.
