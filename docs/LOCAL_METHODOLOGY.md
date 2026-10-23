# Local benchmark protocol

The 2.0 path is manually invoked and localhost only. It uses Ollama `/api/tags`, `/api/version`, and nonstreaming `/api/chat`. The runner refuses remote base URLs and absent model tags; it never downloads weights or calls a paid provider. [Ollama's API reference](https://github.com/ollama/ollama/blob/main/docs/api.md) documents the endpoints. [Usage metrics](https://github.com/ollama/ollama/blob/main/docs/api/usage.mdx) define durations in nanoseconds and token counts.

## Evaluation suite

`data/eval_sets/local_v1.jsonl` contains 18 original, synthetic prompts, six per development, calibration, and held-out test split. Each split covers instruction following, extraction, arithmetic, summarization, technical explanation, and a fictional business task. The test set was frozen on 23 October 2026 at SHA-256 `90d17c8219a3f1f0e8589f3d5bb10516035313ffcdab435ef0fc101f54342057`. The loader rejects duplicate IDs and normalized exact prompt duplicates. This is a compact smoke-sized suite, not a statistically representative population. No model training or fine-tuning occurred.

The `exact` scorer trims outer whitespace only. `integer` requires a bare nonnegative decimal integer. `json_fields` parses JSON and checks expected keys with exact types and values, permitting extra fields. These strict checks can reject semantically correct answers that violate requested format. Manual tasks retain explicit facts for human review; they are **unscored** until reviewed. No model judge is used. A completion is a transport/generation outcome, not an answer-quality label.

`python scripts/manual_review.py --experiment-id ID` exports private JSONL rows for each subjective answer. A reviewer fills five 0–2 criteria (factual correctness, completeness, clarity, instruction adherence, practical usefulness), a boolean unsupported-statement flag, and rationale. `--validate .local/reviews/manual-review.jsonl` checks completeness. The current public snapshot does not ingest these ratings, so an unfinished or single-reviewer sheet cannot be mistaken for validated quality evidence. If published later, use at least two independent reviewers and report agreement and disagreements.

## Execution controls

Default run: installed `phi3:latest` and `gemma3:latest`, six test prompts, two repetitions when explicitly requested, one unmeasured warmup per model, temperature 0, seed 42, 128 output tokens, 2048 context tokens, thinking disabled, no retries, 180-second timeout. The runner randomizes the model–prompt–repetition order with a fixed seed. It records exact Ollama digests, size, family, parameter count, quantization, runtime version, OS/CPU/physical RAM, code revision, dataset hash, timestamp, and configuration. GPU use is not measured. Ollama chooses each model's chat template; its exact template revision is not separately captured.

The client measures wall time around `/api/chat`; Ollama supplies total, load, prompt evaluation, and generation durations. These clocks and boundaries are different, so they are separate fields. Throughput = Ollama output tokens ÷ Ollama generation duration in seconds. Nonstreaming calls do **not** measure time to first token. `done_reason=length` is incomplete, `stop` is completed, other reasons are unknown, and thrown exceptions are errors. Errors stay in the denominator. Missing measurements are null, never zero.

## Summaries and eligibility

The UI reports completed attempts / all attempts, incomplete and error counts, and objective passes / scored attempts. Median wall latency and median generation throughput use completed attempts with available measurements and show their sample counts. Manual tasks are outside the objective-check denominator. No p95 is presented at this sample size. Runs are comparable only within the same experiment, prompts, hardware record, settings, and split. Different tokenizers mean input and output token counts do not represent identical work units. The 2026 commercial API archive remains separate because execution environment and protocol differ.

## Publication and review

The local SQLite database resides in ignored `.local/benchmarks.sqlite`. `--export-id` opens it read-only and checks model provenance, matching prompt text and model coverage, repetition count, status, metrics, and evaluations. It writes only a fixed set of public fields to `web/src/data/local-benchmark.json`; hostnames, user paths, and raw Ollama payloads are omitted. Review the committed JSON before publishing. Model weights are never committed. A small test suite and two repetitions provide descriptive evidence, not population uncertainty estimates or a universal ranking.

## Model artifacts and licenses

The two already installed model identifiers and digests are captured at execution. The [Phi-3 artifact page](https://ollama.com/library/phi3%3Ainstruct) identifies an MIT license. [Gemma 3](https://ollama.com/library/gemma3) points to [Google's Gemma Terms of Use](https://ai.google.dev/gemma/terms); it is not MIT or Apache licensed. Review those terms before distributing model weights or repurposing outputs for training. This repository distributes neither model's weights nor template. For optional smaller runs, [SmolLM2 360M](https://ollama.com/library/smollm2%3A360m) is listed at 726 MB under Apache 2.0; [Qwen2.5 0.5B](https://ollama.com/library/qwen2.5%3A0.5b) is listed at 398 MB and Qwen states this size is Apache 2.0. The installed tags are mutable; the stored artifact digest is the reproducibility anchor.
