# Engineering case study: Infernomics

## Problem

Cost, latency, completion, and answer quality all matter when selecting an LLM configuration. The original repository collected useful Python experiments but presented archived CSVs in a Streamlit dashboard with unsupported cost and quality comparisons. A portfolio visitor had no fast way to inspect the underlying responses or understand what had actually been measured.

## Evidence assessment

The SQLite archive contains seven chat runs (140 items), all for `gpt-4o-mini`. Three runs record the same 20-prompt dataset and output limits of 50, 100, and 200 tokens. The provider response metadata identifies the resolved snapshot. Four older runs omit the output cap. The RAG judge CSV has aggregate scores for a different task and cannot support side-by-side chat response comparison. No chat quality evaluation or historical pricing source exists.

The checked-in chat runner imported a nonexistent `estimate_cost`, preventing new runs until corrected. The archived `cost_estimate` fields are zero; their original cause is unknown, so we did not treat them as evidence. The old summaries also missed provider-level incomplete statuses. Inspecting those statuses revealed that 28 of 60 documented sweep attempts were incomplete at the output cap. This changed the product narrative: the smallest cap looks cheap and fast but completes only six of 20 prompts.

## Decisions and trade-offs

1. **Publish a static, curated snapshot.** A read-only exporter validates matching prompts, model alias, resolved snapshot, and cap. It emits the minimum needed per-item fields and omits raw provider metadata. Static Cloudflare Pages hosting makes the public app useful with zero provider calls.
2. **Separate observed and derived values.** Token use, latency, status, and response text are archived observations. USD request cost is recalculated from a dated official list price. The workload calculator uses the same formula, with no automatic discount.
3. **Compare conditions honestly.** The comparison accepts matched runs on one model snapshot and dataset. It presents side-by-side response text and visibly unavailable quality. It does not rank models or normalize unrelated RAG judge scores.
4. **Keep latency denominators visible.** The median uses completed responses only and shows its sample count. Incomplete counts stay adjacent, since excluding them can bias apparent speed.
5. **Keep Python offline.** NumPy, SQLite, local files, and paid provider calls remain in manually run benchmark scripts. No account, server, or request-time inference is needed for the public release.

## Result and next evidence milestone

The implemented UI offers an explorer, exact run inspection, matched-prompt comparison, and monthly cost estimate with source and assumptions. It is designed to let a visitor understand the project quickly while preserving enough detail for an engineer to audit calculations.

The next empirical milestone is a multi-model run with explicit model snapshots, full generation settings, versioned prompts, task-appropriate scoring, retries, and original pricing metadata. Until then, cross-model recommendations and claims about quality remain out of scope.
