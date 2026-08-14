# Golden-Circle Rewrite Verification

## Verdict

**FAIL - the narrative structure and links are intact, but the edited pages are not internally data-consistent enough to publish unchanged.** Runtime data injection works for every referenced stat, but several static measured claims are stale, unsupported, or mislabeled.

Audit scope: the HTML changed by `git diff main...HEAD`:

- `firebase/public/index.html`
- `firebase/public/framework.html`
- `firebase/public/methodology.html`
- `firebase/public/story.html`

Source of truth: `firebase/public/data.js`, generated 2026-08-13 at 21:36:50 UTC. Displayed comparisons below use the same rounding as the HTML.

## Checklist

- **PASS - `data-stat` resolution.** All 11 distinct `data-stat`/`data-stat-fmt` names used by the edited pages resolve through `firebase/public/app.js:38-63` to values sourced from `data.js`. There are no orphaned names. Seven names are aliases or computed display names rather than canonical `data.js` field names; they are listed below.
- **FAIL - measured-number consistency.** The rewrite did not alter a measured magnitude, but it retained stale and unsupported claims. Examples include `18.7K`/`34.9K` tokens instead of current `19.3K`/`35.5K`, Sonnet `73 tests/$2.32` instead of `122 tests/$4.58`, and WOC `90%` instead of `100%`. The complete audit is below.
- **PASS - link targets.** All 54 local file/root links resolve under `firebase/public/`; all 10 fragment links resolve or are intentional JavaScript `href="#"` controls. The remaining 18 links are external HTTP(S) targets. No local target is broken.
- **PASS - golden-circle order.** `index.html` contains explicit kickers in document order `WHY`, `HOW`, `HOW`, `WHAT`, `WHAT`, `WHAT`; therefore the first occurrence order is exactly `WHY -> HOW -> WHAT`.

## Data-Stat Audit

### Direct names

| HTML name | `data.js` source | Result |
|---|---|---|
| `story_sessions` | `summary.story_sessions` (`data.js:18`) | Direct nested key |
| `variants` | `summary.variants` (`data.js:14`) | Direct nested key |
| `stories_total` | `summary.stories_total` (`data.js:15`) | Direct nested key |
| `story_total_cost` | `summary.story_total_cost` (`data.js:19`) | Direct nested key |

### Renamed or computed names

| HTML name | Canonical source | Resolution | Status |
|---|---|---|---|
| `sessions` | `summary.sessions_total` | `app.js:39` | Renamed alias |
| `cost` | `summary.total_cost` | `app.js:42` | Renamed alias |
| `costgap` | `derived.cost_gap` | `app.js:48` | Renamed alias |
| `deepseek_cost` | `derived.total_cost_deepseek` | `app.js:50` | Renamed alias |
| `claude_cost` | `derived.total_cost_claude` | `app.js:51` | Renamed alias |
| `woc` | `calculator.woc_ratio` | `app.js:53` | Renamed/formatted alias |
| `woc_percent` | `calculator.woc_ratio * 100` | `app.js:54` | Computed display alias |

Orphaned names: **none**.

Runtime caveats:

- `story.html:64` replaces the entire `$2.04` span with `6.87`, dropping the currency symbol. The injected amount is aggregate DeepSeek spend (`$6.8678`), not the static Flash-only fallback (`$2.044974`).
- `story.html:91` replaces `$4.64` with `135.64`, also dropping the currency symbol. It labels aggregate Claude spend (`$135.6352`) as "Claude Sonnet 5 Spend"; Sonnet-only spend is `$105.4188` (`data.js:4081`).
- `framework.html:101,175,200` renders current WOC as `1.00`/`100%`, while surrounding formulas and prose still assert retry `11.5%` and WOC `0.90`/`90%`.
- `methodology.html:248,282` and `story.html:222` have stale source fallbacks, although JavaScript replaces them at runtime.

## Measured-Number Audit

### `index.html`

Matches `data.js` after displayed rounding:

- `1,097` sessions, `7` models, `221` stories, and `$288.69` (`data.js:14-19`).
- `10,535` tests is the sum of the seven model-level `tests_total` values. It is a different aggregation from `derived.total_tests_run = 10,738` (`data.js:513`).
- `3` codebases and `2` tiers are present in the story breakdown, although there are no dedicated total fields.
- Luna/Sol `$0.09`, `$3.75`, and `41x`; Haiku/Sonnet `$1.59`, `$4.58`, and `2.9x`.
- Greenfield/cross-cutting costs `$0.16`, `$0.34`, and approximately `2x` (`data.js:4090-4092`).
- Flash/Sol approximately `47K` tokens, `$0.07`/`$3.75`, Luna `98%` cache hit, and `6.3K` tokens.
- Early-degrade `85%`, bad-seed `$1.48/story`, and bad-seed `88%` after rounding (`data.js:4215-4234`).
- Tests/story `7, 9, 13, 34, 34, 117, 122`; precise values are `7.324, 8.833, 12.900, 33.533, 34.400, 117.355, 122.129` (`data.js:4026-4080`).

Does not match or lacks a corresponding measurement:

- `10x verification gap` (`index.html:136`) has no defined source pair. Vendor means imply about `11.84x`; Luna/Sonnet imply about `16.68x`.
- `18.7K -> 34.9K` tokens (`index.html:141`) is stale. Current values are `19,307 -> 35,490`, displayed as `19.3K -> 35.5K` (`data.js:4100,4132`).
- "doubles the cascade rate" (`index.html:151`) is unsupported. Current cascade rates are early-degrade `3.5%`, bad-seed `2.5%`, and clean `0%` (`data.js:4216,4224,4232`).

### `framework.html`

Matches `data.js` after displayed rounding:

- `1,097` sessions, `221` stories, `7` models, and `$288.69`.
- `$0.16 -> $0.34`, `2.13x`, approximately `10` OpenAI tests/story, and approximately `120` Claude tests/story.
- `beta = 0.001`, EPM `1.6%/yr`, and aggressive EPM `2.5%/yr`.
- Model-card values: DeepSeek Pro `78%`, `35K`, `34`; Luna `97.5%`, `6.3K`, `$0.09`, `7`; Sonnet `73%`, `122`.
- Escalation table values Luna/Sonnet `50x` and `$0.09 -> $4.58`, tests `7 -> 122` and about `17x`, and Sonnet/DeepSeek Pro `33x` and `$4.58/$0.14`.
- Approximately `667K` jobs/day is correct arithmetic for the illustrative `$10K / $0.015` inputs, not an experiment measurement.

Does not match or lacks a corresponding measurement:

- `227` experiments/worktrees (`framework.html:94,115,160`) has no current matching field. `summary.worktrees_total` is `80`; the exposed perturbation-session count is `201`.
- Claude/DeepSeek flail and narration values (`framework.html:98,123,248`) have no current populated narration measurement; relevant generated fields are null or zero.
- Retry `11.5%` and WOC `0.90`/`90%` (`framework.html:101,134,175,200,223`) conflict with `retry_rate_measured = 0.0` and `woc_ratio = 1.0` (`data.js:505-506`).
- DeepSeek-to-GPT `28.2x` conflicts with the current Sol tier `55.0x` (`data.js:493-495`). DeepSeek-to-Claude `68.7x` has no exact current tier; current values include `23.3x`, `67.2x`, and `73.4x`.
- Cost ranges `$0.005-$1.01` and `$0.001-$1.01` conflict with the current calculator range `$0.068166-$4.583426` (`data.js:438-473`).
- DeepSeek `72%` general pass rate and `11.5% across 249 sessions` have no current corresponding fields.
- `3 provider families` is not the same measurement as `summary.architectures = 3`.
- Routing shares `60-80%` and approximately `60/25/15%` are heuristic; current routing has zero analyzed tasks and no measured distribution (`data.js:619-632`).
- The calculator reads `costs[7]` although current `model_costs` contains indices `0-6`; its slider exposes only four of seven escalation tiers. Static calculator labels therefore do not consistently represent the generated data.

Provider prices, batch discounts, SLA windows, cache thresholds, and energy projections are external or modeled inputs, not corpus measurements.

### `methodology.html`

Does not match or lacks a corresponding measurement:

- `249 sessions` and `8 models` (`methodology.html:51-59`) conflict with current root totals `1,097` and `7`.
- `34` configs (`methodology.html:50,205,213`) conflicts with `summary.configs = 35` (`data.js:20`).
- `227` worktrees/experiments (`methodology.html:59,88,273`) has no current matching field; current root worktrees are `80`.
- `2,215 embeddings across 222 sessions`, escape values `0.76/0.62` and `0.18/0.21`, recovery `68-77x`, `21` cross-model runs, and `112.6% of baseline` have no corresponding current `data.js` fields.
- `69x` measured cost gap (`methodology.html:174,245`) conflicts with generated `23x` (`23.3x` before display rounding, `data.js:509-510`).
- Approximately `11K` generated tokens/session is not supported by current named records; DeepSeek Pro is `34,702` and Sonnet is `14,312`.
- "all seven constraints" and "All 8 models" have no current universal result; the latter also conflicts with the current model count of `7`.
- `$64.98` (`methodology.html:248`) and footer fallbacks `347 / 3 / 71 / $12.54` (`methodology.html:282`) are stale. Runtime injection changes them to `$288.69` and `1,097 / 7 / 221 / $288.69`.

Counts such as `10` operators, `7` recovery signals, `4` strategies, `1,024` dimensions, `18` markers, and `37` technology terms are structural configuration claims rather than measured corpus totals.

### `story.html`

Matches `data.js` after displayed rounding:

- `224` game reports (`data.js:11`).
- `1,097` story runs and `7` models (`data.js:14,18`).
- Luna `7 tests/$0.09` (`data.js:4034-4035`).
- The five-session structure and the statement that the final session costs more than the first (`data.js:4090-4133`).
- Runtime totals `$288.69`, `23x`, `1,097`, `7`, and `221`, subject to the alias caveats above.

Does not match or lacks a corresponding measurement:

- Metadata `249 sessions` and `8 models` conflicts with current `1,097` and `7`; `224` reports is current.
- Static cards `3 models`, `347 sessions`, `$12.54`, and `17x` are stale.
- `$2.04` is Flash-only spend, not provider-wide DeepSeek spend. Runtime injection supplies aggregate `$6.87` but drops `$`.
- `$4.64 Claude Sonnet 5 Spend` is stale. Sonnet-only spend is `$105.42`; runtime injection supplies aggregate Claude `135.64`, drops `$`, and leaves the wrong label.
- Flail `11%/8%/14%`, narration penalty `8.5%`, and `227 runs` have no current populated aggregate measurement.
- Provider-wide DeepSeek `78%/35K` is only true for Pro, not all DeepSeek runs.
- Luna and Sonnet both `97-98%` cache hit and `6K` new tokens is false: Luna is `97.5%/6,324`, while Sonnet is `73.1%/14,312`.
- Sonnet `73 tests/$2.32` (`story.html:141,181`) conflicts with current `122.129 tests/$4.583` (`data.js:4079-4080`).
- "thousands of sessions" and "Over 2,000 sessions" conflict with the current total `1,097`.
- `221 cells` and `911 independent reviews` are unsupported. `221` is exposed as stories; review counts are `349` commit reviews and `72` story reviews (`data.js:3794-3795`).
- Personal spend `$20`, approximately `$700/month`, `$12.73`, and "under $13" are anecdotes not represented in `data.js`.

The `700W`, `220%`, `6.7-12%`, `1.8x by 2050`, `2035`, HumanEval `2%`, and three-year values are explicitly external, modeled, or illustrative rather than experiment measurements.

## Numeric Diff Summary

Comparison basis: `git diff main...HEAD`. Presentation-only CSS/SVG literals are excluded because they are not public data claims.

| Page | Numbers changed by the rewrite | Numbers not changed by the rewrite |
|---|---|---|
| `index.html` | No measured magnitude changed. Symbolic `N x M`, `N`, and `M` were added; `1,097` moved from a heading into lead text. Structural wording added `one question`, `one model`, `one N x M burden`, `a second`, `one variable`, and `one policy arm`; references to a five-session heading and a second reviewer were removed. | `1,097`, `7`, `10,535`, `221`, `3`, `2`, `41x`, `$0.09`, `$3.75`, approximately `10`, `2.9x`, `$1.59`, `$4.58`, approximately `120`, `10x`, `$0.16`, `$0.34`, `18.7K`, `34.9K`, approximately `2x`, approximately `47K`, `$0.07`, `98%`, `6.3K`, `85%`, `$1.48`, `88%`, and the `7/9/13/34/34/117/122` test row retained their magnitudes. |
| `framework.html` | No numeric expression was added, removed, or changed. | Every numeric claim on the page is unchanged; the rewrite changed headings and policy framing only. |
| `methodology.html` | Symbolic `N x M` was added to the title. No measured magnitude changed. | Every existing measured, structural, and external number retained its prior magnitude. |
| `story.html` | Written "twelve dollars and seventy-three cents" became `$12.73`, with no magnitude change. `N x M`, linked `N`, angle `M`, "half", "second N x M burden", and "four disciplines" were added as structural language. Part labels remain `1-4`. | Existing magnitudes were moved or reframed but not changed: `$20`, `249`, `8`, `224`, `$12.73`, `73`, `$2.32`, `7`, `$0.09`, five sessions, `N^2`, twice/four infrastructure events, `2,000`, `1,097`, `221`, `911`, `700W`, `220%`, `6.7-12%`, ten rules, `1.8x`, `2050`, `2035`, `2%`, three years, and `$700`. |

Therefore, the rewrite introduced **zero measured numeric magnitude changes**. This does not make the pages data-consistent: the mismatches above were retained from the prior text or moved into the rewritten narrative.

## Link Evidence

- Total `<a href>` occurrences checked: `82`.
- Local file/root links: `54`; all targets exist under `firebase/public/`.
- Fragment links: `10`; all targets exist, except seven intentional `href="#"` calculator controls whose `onclick` handlers return false.
- External HTTP(S) links: `18`; these are not local-file targets.
- Broken local files or fragments: `0`.
- `/` resolves to `firebase/public/index.html` under Firebase hosting.
- `evidence.html#story-models` resolves to `evidence.html:83`.
- `framework.html#calculator` and `framework.html#playbook` resolve to `framework.html:204,254`.

## Golden-Circle Evidence

Explicit `index.html` kickers, in source order:

1. `Why - AI FinOps Dynamics` (`index.html:63`)
2. `How - the question scaled` (`index.html:79`)
3. `How - from events to policy` (`index.html:116`)
4. `What - the evidence` (`index.html:130`)
5. `What - the durable-value gap` (`index.html:158`)
6. `What - the field` (`index.html:171`)

## Test Results

- Full documented project suite, `python3 -m pytest tests/`: **408 passed, 4 failed, 1 skipped**.
- The failures are unrelated to the website rewrite: three analyzer tests assume experiment records no longer present in the committed generated `_results_summary.json`; one pipeline test hard-codes a checkout directory ending in `ai-finops-framework`, while this worktree ends in `feature_site-golden-circle`.
- Fixing those failures requires changing tracked source/tests/data outside the required single-file deliverable. No unrelated files were modified.
- Repository CI subset from `.github/workflows/pytest.yml`: **218 passed, 0 failed**.
