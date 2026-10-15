# Portfolio package

[Live website](https://infernomics.nickcloud.dev/) · [Website screenshot](../assets/infernomics-website.png)

## 60–90 second demo script

1. **0–15 s — Frame the problem.** “Infernomics asks how much latency and spend a model configuration costs, and whether it actually completes the workload. This release uses saved, inspectable runs, so exploring it does not trigger a paid API call.”
2. **15–35 s — Show the explorer.** “These are three output limits for the same model snapshot and 20 prompts. Median latency uses completed attempts. Cost is an estimate from observed tokens and a dated USD list price. The completion column matters: at 50 tokens, only 6 of 20 completed.”
3. **35–60 s — Compare one prompt.** Open **Compare** on prompt 3 (“Give 3 bullet points on why caching can reduce inference cost”). The 50- and 100-token responses ended incomplete while the 200-token response completed. “These cards show the exact response, recorded tokens, latency, and estimated cost. Quality was not scored, so I do not call one answer best.”
4. **60–75 s — Estimate a workload.** Set 1,000 requests/day, 1,000 input tokens, 500 output tokens. “At the listed $0.15 / $0.60 per million tokens, that is $13.50 per 30-day month, before discounts or other charges.”
5. **75–90 s — Close with engineering judgment.** Open **Methodology**. “The Python runner stays offline; the public app is static on Cloudflare Pages. The next milestone is a quality-scored multi-model dataset with tighter provenance.”

## CV description

Built Infernomics, a TypeScript/React benchmark explorer and workload cost calculator backed by 60 archived OpenAI inference attempts. Added validated Python export, matched-prompt comparisons, transparent USD list-price calculations, and Cloudflare Pages deployment. Surfaced 28 output-cap incomplete attempts that the legacy dashboard did not distinguish.

## LinkedIn description

Infernomics is my open-source inference decision desk. It turns archived LLM runs into an inspectable explorer, response comparison, and monthly cost estimate. The first release deliberately covers one model and three output limits. It shows a practical lesson from the data: cheaper and faster configurations may truncate many responses. The frontend is TypeScript/React; Python handles offline benchmarking and a validated public data export. Source: https://github.com/QinnniQ/infernomics
