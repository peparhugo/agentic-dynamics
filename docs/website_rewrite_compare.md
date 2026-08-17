# Website Rewrite — Three-Model Comparison

Three independent rewrites of `firebase/public/` (branches `feature/website-rewrite-{deepseek,fable5,openai}`),
each produced by a different model from the same spec + `docs/agentic_dynamics_vision.md`.

## 1. Convergence

All three landed the identical thesis: **"AI agents don't have a price. They have dynamics."**
The positioning (business outcomes, not SaaS, not abstract) survived translation.

## 2. The three editorial identities

| Model | Identity | Diff (8 pages) | Verify |
|---|---|---|---|
| Fable 5 | balanced journalist — kept salvageable structure, rewrote numbers in place | +437 / −368 | 11 PASS |
| DeepSeek | findings-first researcher — numbered, citable findings | +600 / −3050 | 20 PASS |
| OpenAI | minimalist — gutted to a skeleton + honesty notes | +277 / −4103 | 3 FAIL (provenance) |

## 3. Story-data usage (does the rewrite keep the rich corpus?)

| Story-corpus signal | DeepSeek | Fable 5 | OpenAI |
|---|---|---|---|
| 156 stories / 772 sessions | ✓ | ✓ | ✓ (footer only) |
| snowball / compounding | ✓ | ✓ | weak |
| recovery / degradation | ✓ | ✓ | ✓ |
| condition effects | ✓ | ✓ | ✓ |
| verification / vendor | ✓ | ✓ | **0** |
| cache economics | ✓ | ✓ | weak |
| five-session arc | ✓ | ✓ | **0** |

**DeepSeek and Fable 5 build the site on the story corpus.** OpenAI kept the corpus *size* but
dropped most story-side *findings* (no vendor, no five-session arc), leaning on the thinner
single-task resample instead.

## 4. What works, per page

- **index.html → Fable 5.** Concrete, provenance-tagged headlines up front (~33× spread, premium
  failure, −0.15 correlation, self-healing). DeepSeek's index drifted to mechanism; OpenAI's is thin.
- **evidence.html → DeepSeek.** Seven clean findings (cost separates models · recovery is real but
  expensive · verification tracks vendor not price · the instrumented fields · the instrument
  self-heals). OpenAI's "Evidence boundary" honesty section is worth stealing. Fable 5 *retained*
  the old section names (refined, not rewrote).
- **methodology.html → DeepSeek (cycle + load-bearing rule) + Fable 5 (exact 3-way class names).**
  DeepSeek and OpenAI dropped the canonical class names — a consistency risk against `data.js`.
- **framework.html → Fable 5.** Kept the SVG with the least collateral damage (OpenAI trimmed it).
- **story / accelerator / databricks / glossary → Fable 5.** Balanced, narrative kept, numbers refreshed.

## 5. Flags

1. **OpenAI's 3 provenance FAILs** — a few numbers without honest tags. Do not pull those numbers.
2. **DeepSeek + OpenAI dropped the 3-way class names** — removed `manifold`/`semantic` without always
   replacing with `specification_corruption` / `objective_mutation` / `process_perturbation`.
3. **OpenAI's "Evidence boundary" + the `[M]/[C]/[H]/[X]/[P]` legend** are good honesty UX — port them in.

## 6. Cherry-pick decision

| Page | Source |
|---|---|
| index | Fable 5 |
| evidence | DeepSeek (+ OpenAI's "Evidence boundary") |
| methodology | DeepSeek (cycle) + Fable 5 (taxonomy names) |
| framework / story / accelerator / databricks / glossary | Fable 5 |
| provenance | Fable 5/DeepSeek rigor + OpenAI's legend; drop OpenAI's untagged numbers |

Assembled in branch `feature/website-rewrite-bestof` (Fable 5 base + DeepSeek evidence/methodology
+ OpenAI legend/boundary). `firebase/public/` on `main` is untouched until a human approves.
