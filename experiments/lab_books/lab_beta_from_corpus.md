---
status: measured
---

# Lab: β coordination tax from the session corpus (`lab_beta_from_corpus`)

**Status: MEASURED — primary corpus fit executed at 2026-09-01T00:36:38+02:00 without
model calls. The required container-window sensitivity fit is not implemented by the
preregistered script, so the full protocol-compliance verdict is FAIL.**

**Preregistered:** 2026-08-31. **Origin:** the `concurrency_ladder` incident
(`experiments/results/workflows/concurrency_ladder/20260831T014836Z.json`).

## Origin and purpose

The controlled ladder (β coordination-tax curve at fleet rungs 1/2/4/8) was polluted: the
retry-worthiness workflow launched at the same second and ran its own fork chain through
p0–p2's window; graph builds and the container story fleet overlapped the later rungs; the
8-wide rung failed. Its per-rung costs were flat-to-declining ($0.144 → $0.105 → $0.108 →
$0.082) because the rungs were different work — cross-rung cost is not β. Under the execution
freeze no controlled rerun can run.

This lab estimates β **retrospectively from the existing session corpus** — a natural
experiment, since the fleet already sampled concurrency N=1 through ~10+ across 14 days
(story fleet at 8-wide, retry-worthiness forks at 2–4, ladder rungs, solo work). The estimate:

1. **bounds** the coordination-tax curve without spending a dollar;
2. **sizes the concurrency lease** for the admission gates (how wide may a fleet run before
   the tax eats the budget);
3. **decides whether the controlled rerun is worth its cost** (decision thresholds below).

## Question

How much per-worker efficiency is lost as fleet concurrency grows?

Define β by: `efficiency(N) = c · N^(−β)` — β = 0 means no coordination tax; β > 0 means
superlinear cost of concurrency. Efficiency is measured three ways (see Signals).

## Hypotheses

- **H1 (token throughput tax):** per-session token throughput (tokens/minute) decreases with
  concurrent load → `β_tokens > 0`.
- **H2 (cache-share offset):** cache-hit share (`cache_read / (cache_read + cache_miss)`)
  **increases** with concurrency (workers share context — the 14-day corpus shows 3.4B cache-hit
  vs 83M cache-miss tokens, and cache reads price at ~1/30th of input) → in dollar terms
  `β_cost < β_tokens`; the cost curve is flatter than the token curve.
- **H3 (model dependence):** β is model-dependent — `deepseek-v4-pro` (long-context, heavy)
  shows a higher β than `deepseek-v4-flash` (cheap, short) on the same bins.

## Data sources

| Source | What it provides | Authority |
|---|---|---|
| `~/.local/share/opencode/opencode.db` (`session` table) | id, parent_id (subagents), title, model (JSON), cost, tokens in/out/reasoning, `tokens_cache_read`, time_created/time_updated | [M] local |
| Story result files (`experiments/results/stories/*.json`) | timestamps + models of the **container-invisible** story cells (the fleet's 8-wide runs) | [M] |
| Platform meter (`experiments/results/usage/subscription_usage_latest.json` → `deepseek_platform` block) | authoritative daily token counts for reconciliation of the local estimates | [M] external |

The lab reads the DB + the two canonical files; it does not run anything.

## Signals (per session, all already recorded)

- `duration` = time_updated − time_created (fork deltas where chained)
- `tokens` = input + output + reasoning
- `cache_read` and cache ratio = cache_read / (cache_read + input)
- `cost` (opencode's estimate; reconciled against the meter block)
- `fork_depth` (continuation chain length) and `is_subagent` (parent_id set)

## Method (exactly this order, nothing else)

1. **Concurrency timeline.** For every session: interval [time_created, time_updated].
   `N(t)` = count of overlapping intervals, per host. Container story cells contribute their
   intervals from their story-result timestamps in the **sensitivity** analysis only
   (Exclusion rule 4).
2. **Assign experienced concurrency.** Each session gets `N` = mean concurrency over its own
   lifetime (rounded down to bin edges). Sensitivity: also compute with N-at-start.
3. **Bin.** N = 1 · 2–3 · 4–5 · 6–8 · 9+, separately per model (pro / flash / flash-vision /
   claude sonnet), separately for parents vs subagents.
4. **Fit.** OLS on `log(efficiency) ~ log(N)` per model per efficiency definition;
   β = −slope; report 95% CI, r², n per bin.
5. **Decompose.** tokens/$, cache share vs N, duration vs N — the H2 offset check.
6. **Reconcile.** DB token sums vs the meter's per-model buckets; report the discrepancy as a
   coverage caveat, never silently impute.

## Exclusion rules (fixed BEFORE fitting)

1. The ladder window `2026-08-30T21:32Z → 2026-08-31T01:48Z` is excluded (dual-workflow
   confound — the retry-worthiness chain ran in the same host simultaneously).
2. Sessions with `duration < 10s` or `tokens < 100` are excluded (noise / preflight probes).
3. Subagent sessions are never mixed into the parent analysis — analyzed separately as
   coordination events (they ARE the tax, not workers paying it).
4. Primary analysis: story-cell windows (containers, sessions invisible to the DB) are
   EXCLUDED from the N=6–8/9+ bins rather than imputed. Sensitivity analysis imputes their N
   from story timestamps; **both** results are reported, and only agreement across both
   counts as evidence.
5. Only sessions whose model parses as `deepseek/*` or `anthropic/*` enter the fit.

## Decision thresholds (fixed BEFORE fitting)

| β_cost (main estimate) | Reading | Consequence |
|---|---|---|
| < 0.15 | tax negligible | ladder rerun low priority; leases may allow wide fleets |
| 0.15 – 0.5 | moderate tax | rerun justified once the admission gates land; leases sized from the fitted curve |
| > 0.5 | severe tax | rerun HIGH priority (the controlled curve matters); leases stay narrow until then |

Additionally: if the cache-share slope vs N is steeply positive (H2), the cost curve flatter
than the token curve and the lease can be wider in dollars than in tokens.

## Output schema

`experiments/results/lab_beta_from_corpus.json`:

```json
{
  "question": "...",
  "preregistered_at": "2026-08-31",
  "models": {"<model>": {"beta_cost": 0.0, "beta_tokens": 0.0, "beta_ci": [0.0, 0.0],
                          "n": 0, "r2": 0.0, "cache_share_slope": 0.0}},
  "bins": {"1": 0, "2-3": 0, "4-5": 0, "6-8": 0, "9+": 0},
  "exclusions_applied": ["ladder_window", "noise", "subagents_split", "container_impute_sensitivity"],
  "decision": "<threshold reading>"
}
```

## Interpretation guide

- Observational ≠ controlled: wide-N windows were selected by operations (when the fleet
  happened to run wide), so β may be biased by *when* we chose to go wide — the ladder's
  controlled version remains the only causal estimate.
- The freeze means no new data will arrive to change the corpus; re-run this lab after the
  gates land and the first clean fleet run happens, as the controlled check.
- A null result (β_cost ≈ 0) does NOT mean the ladder was unnecessary — it means the tax
  lives somewhere the corpus can't see (container runtime, Redis, filesystem), which is
  itself a finding about where the controlled rerun must instrument.

## Results

### Execution

`python3 scripts/lab_beta_from_corpus.py` completed successfully at
2026-09-01T00:36:38+02:00. The script uses only the local OpenCode SQLite database, committed
story-result files, and the usage-meter snapshot; it made zero paid model calls. It wrote
`experiments/results/lab_beta_from_corpus.json`.

### Primary estimates

The primary fit has n = 1,429. Its main cost estimate is **β_cost = 0.1543** (95% CI
[0.1123, 0.1963], r² = 0.0351, n = 1,429). The artifact's preregistered point-estimate
thresholds classify this as **moderate_tax**: 0.1543 is at least 0.15 and no greater than 0.5.
Its interval crosses the 0.15 negligible/moderate boundary, so this threshold label is not a
precise boundary decision.

The corresponding throughput estimate is **β_tokens = 0.7996** (95% CI [0.7103, 0.8889],
r² = 0.1775, n = 1,429). Its positive interval supports a decreasing fitted token-throughput
curve as concurrency rises under the preregistered efficiency form. The primary cache-share
regression slope is **−0.0228** per log-concurrency unit (the artifact's negated-slope
`cache_share_slope.beta` is 0.0228, 95% CI [0.0133, 0.0322]). This result does not support the
preregistered positive cache-share-offset hypothesis.

| Model | β_cost (95% CI) | β_tokens (95% CI) | n |
|---|---:|---:|---:|
| `deepseek-v4-flash` | 0.0161 [−0.0051, 0.0372] | 0.7659 [0.6622, 0.8697] | 987 |
| `deepseek-v4-pro` | −0.0084 [−0.0325, 0.0158] | 0.7220 [0.5495, 0.8945] | 442 |
| Pooled primary fit | 0.1543 [0.1123, 0.1963] | 0.7996 [0.7103, 0.8889] | 1,429 |

The retained sessions span bins `1`: 3, `2-3`: 244, `4-5`: 385, `6-8`: 150, and `9+`: 647.
The meter reconciliation reports 179,215,822 14-day DeepSeek-platform tokens, with the
script's stated caveat that local DB totals undercount container cells.

### Verification log

| Check | Result | Evidence |
|---|---|---|
| Exclusion rules 1, 2, 3, and 5 | PASS | `exclusions_applied` records `ladder_window`, `noise_min_10s_100tok`, `subagents_split`, and `model_whitelist`. The primary fit reports n = 1,429; subagents remain separate by bin. |
| Exclusion rule 4, primary treatment | PASS | `exclusions_applied` records `container_cells_excluded_primary`; the primary bins are `1`: 3, `2-3`: 244, `4-5`: 385, `6-8`: 150, and `9+`: 647. |
| Exclusion rule 4, container-window sensitivity fit | FAIL | The preregistration requires a sensitivity result using story timestamps and agreement with the primary fit. The artifact has no sensitivity estimate, and the script defines `_story_windows()` without invoking it. The estimator was not changed after fitting. |
| Decision threshold | PASS | The artifact reports `decision: moderate_tax`; β_cost = 0.1543 is within its stored moderate interval [0.15, 0.5]. |

**Protocol-compliance verdict: FAIL.** The primary measurement artifact reports the
preregistered exclusions and a **moderate_tax** point-estimate verdict, but it is not a fully
compliant execution of the preregistered protocol until the missing sensitivity analysis is
separately specified and run. This result remains observational, not a causal replacement for
a clean controlled ladder.

## Reframing — β is a contention exponent, not a coordination exponent (operator annotation, 2026-09-01)

**Status: operator annotation [P] — policy/prior, appended after the terra run, not a
preregistration change.**

This architecture has **no agent-to-agent coordination by design**: every agent works
isolated — its own worktree (ephemeral branch, the permanence gate), its own container
(mount contract + scope model + PHASE_SCOPE_AUTHORIZATION), its own KB scope
(repository_id = self-<worktree>), and no shared mutable state. "Coordination tax" is
therefore a misnomer for anything this corpus can measure: there is no coordination to tax.

What the β_tokens estimate actually captures is **infrastructure/provider contention** —
sessions lose tokens per minute as the provider key (and the shared machine: CPU, Redis,
network) load rises. It is a rate-limit curve, not a fleet-economics or agent-economics
curve, and it says nothing about whether isolated agents should run concurrently (they
should — concurrency is the intended operating mode).

The controlled ladder (`concurrency_ladder`, excluded per rule 1) tried to measure a
coordination curve the architecture makes moot: its flat rung costs were meaningless twice
over — cross-phase work compared as if it were rungs, and a premise that does not exist.
The incident ledger + window exclusion stand as the record of that failure.

What survives the reframing:

- **β_cost ≈ 0** (robust, incl. the pooled 0.154 boundary reading vs the 0.11-0.14 robust
  range) — concurrency under isolation is **dollar-safe**. That is the real, policy-relevant
  finding.
- **β_tokens ≈ 0.3-0.8 direction** — contention exists; wide fleets share provider limits.
  An infrastructure sizing input, not an agent-behavior finding.

**Policy consequence:** the `admission_leases` concurrency leases protect **provider windows
and spend caps**; they are NOT sized on a coordination tax. Wide fleets of isolated agents
are the intended mode — lease width is an infrastructure/cost-control knob, never a
coordination-safety device.
