# Release progress and checks

## Milestones

1. **Audit complete:** seven chat runs / 140 items located; three documented sweep runs selected; four runs with missing cap excluded. No Git-tracked `.env` or database found. Raw archive is ignored. Old price and quality claims were reviewed.
2. **Foundation complete:** read-only export, static React/TypeScript application, shareable filters, responsive design, and dated pricing metadata.
3. **Core complete:** explorer, run inspector, matched-prompt comparison, and monthly calculator. Incomplete statuses are explicit.
4. **Methodology complete:** product method section, README, architecture diagram, case study, demo script, and portfolio copy.
5. **Verification:** see command results below; browser and accessibility checks recorded when run.
6. **Deployment complete:** Cloudflare Pages built Git commit `58020f7` from `main` on 15 October 2026 and published the static site at [infernomics.nickcloud.dev](https://infernomics.nickcloud.dev/). Git integration is active; rollback steps are documented in the README.

## Public delivery check

Cloudflare reported a successful build and deployment from `web` using Node.js 22.16.0, `npm run build`, and `dist`. The Pages URL returned HTTP 200. After the custom domain was activated, Cloudflare and Google public DNS resolved `infernomics.nickcloud.dev`; HTTPS returned HTTP 200 with the expected Infernomics title and versioned CSS/JavaScript asset paths. This is a delivery check, not a full browser regression test on the public site.

## Local checks

On 15 October 2026, a clean local `npm ci` from the committed lockfile, ESLint, TypeScript checking, seven Vitest cases, and a production Vite build passed. `npm audit --omit=dev` found zero reported vulnerabilities. Python 3.13 `compileall`, a runner import check, `git diff --check`, and a two-pass deterministic export check passed. The source/ignore scan found no Git-tracked `.env`, SQLite archive, or credential-like string in release files.

Browser checks on the locally served production build covered desktop and a 390 px mobile viewport. Filtering reduced the result table to the selected cap and updated the URL; the 100-token run inspector opened and closed with Escape; the default comparison showed two incomplete responses and one completed response to the same prompt; the calculator returned $0.90 for 2,000 monthly requests, 1,000 input tokens, and 500 output tokens. A direct `#comparison` link scrolled after React mounted. Tab focus reached the skip link. No page-wide horizontal overflow was measured at 390 px or 1280 px. These are focused checks, not a full WCAG 2.2 AA certification.

Lighthouse 13.5.0 against localhost measured **desktop performance 100 / accessibility 100** (FCP 0.5 s, LCP 0.5 s, TBT 0 ms, CLS 0) and **mobile performance 88 / accessibility 100** on the final text build (FCP 2.4 s, LCP 2.4 s, TBT 290 ms, CLS 0). A prior mobile run of the same layout measured performance 94 / accessibility 100, showing run-to-run variability. These are simulated local audit scores, not field data. The final production bundle was 298.29 kB JavaScript (89.92 kB gzip) and 21.07 kB CSS (5.47 kB gzip). The contrast issue in an earlier audit was corrected before the 100 accessibility audits.

Run from `web`: `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`. Run the exporter only where the original ignored SQLite archive is available. The committed JSON makes a clean checkout independent of that archive.

## Remaining limitations

- One model only; no cross-model answer to the product's central question yet.
- Chat quality unavailable; completion is a separate status, not an evaluation score.
- Small convenience prompt sample, incomplete historic settings/retries/code version, and limited comparability across sequential execution times.
- USD list-price estimates are dated, exclude discounts and taxes, and are not bills.
- No live inference or public API is exposed.
