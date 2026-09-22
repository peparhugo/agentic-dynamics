# World model — the confidence-cascade study, Phase A (retrospective + pre-registration)

Author: `confidence_cascade_study` phase `prior` (spec version `0.1`).
This document is the *inventory* the phase owes: what data actually exists, where, in what
shape, and what it can and cannot answer — written BEFORE any method is chosen, so the
plan's queries are grounded in observed coverage rather than assumed coverage.

> **How every number below was produced.** Each figure is a count over the live registry
> index or the knowledge-base artifacts, obtained by the exact commands recorded in
> `notes/plan.md` §"Queries". Nothing here is copied from prose. Where a number is quoted
> from an existing artifact (e.g. the prior cascade retrospective JSON) it is named inline.

---

## Problem

The machine's load-bearing rule: **to make policies, we need information.** The
`confidence` signal is now instrumented (`AgenticResult.confidence`,
`src/agentic_dynamics/adapters/opencode.py:113`), so the compiler no longer refuses a
`model_cascade` control arm that `requires: [confidence]`. But "instrumented" is not the
same as "informative". Phase A must answer, from data that already exists and **before**
spending a dollar on a grid:

1. **Is `confidence` calibrated against outcomes?** i.e. does P(outcome | confidence) move
   with confidence, at sample sizes large enough to fit a threshold?
2. **What does the escalation-ROI curve look like** — is there any escalation history to
   estimate it from, or is the ROI purely counterfactual?
3. **Pre-register the grid** (arms, metrics, comparison, power, falsifiers) — but only to
   the extent Phase A's effect sizes and coverage support it.

**Honesty rule (binding):** if the ledger cannot answer the calibration question, the
retrospective says so and the grid design pauses. A null feasibility result is a
first-class finding, not a failure to be papered over.

**Immediate discovery (the reason this inventory came first).** The domain context names
`experiments/results/registry_index.jsonl` as the evidence, filtered to
`source_type == 'ledger_attempt'`. That path is **gitignored and absent from this git
checkout** (`/repo`); it exists only in the live data root (`/app`). And even there, the
live registry contains **zero** `ledger_attempt` rows — the attempt-level signal is emitted
by the newer `attempt_facts/v1` reducer as `source_type == 'fact'`, not by the
`ledger_ingestion` producer. Both facts are load-bearing for the plan: the named query
returns n=0, and the actual data lives one layer over.

---

## What Exists

### 1. Two filesystem roots, one of them unversioned

| root | what it is | tracked? | relevant content |
|---|---|---|---|
| `/repo` | the git checkout this phase commits into | yes | `experiments/data_manifest.json`, `tests/fixtures/corpus/*`, the parquet, the specs, the prior docs |
| `/app` | the live data root | **no (not a git repo)** | `experiments/results/registry_index.jsonl`, `experiments/results/kb/*.json`, `experiments/results/workflows/**/*.json` |

The live registry index is `35,055,781` bytes / `55,077` lines, sha256
`cf64fc97d8352ea4ea61e260160b9aa91342d3f4a0442032944571a45da7cf5c`. It is a **lifecycle
index**: each row carries `source_type`, `source_uri`, `logical_locator`,
`knowledge_id`, `lifecycle_state`, timestamps, and a `reason` that is a *content hash* —
**never the value itself**. Values live in the kb artifacts (§3).

### 2. The attempt layer's predicate coverage (live registry, current rows)

`35,694` current `fact` rows resolve to `2,505` distinct attempts (attempt key parsed from
`source_uri == fact://attempt/<cell>:<phase>:<runhash>/<predicate>`). Coverage per
predicate, in distinct attempts:

| predicate | attempts | note |
|---|---|---|
| `attempt_model` | 2,369 | |
| `phase_status` | 2,361 | the completion outcome (`ok` / `failed` / `awaiting`) |
| `attempt_cost_usd` | 2,315 | |
| `phase_commit` | 1,621 | |
| **`attempt_confidence`** | **1,345** | the signal under study |
| `attempt_tokens_out` | 1,152 | |
| `attempt_tokens_in` | 1,152 | |
| `attempt_cache_hit_rate` | 1,070 | |
| `phase_test_verified` | 132 | the *independent* outcome — see the gap in §Gaps |

Co-occurrence (all predicates present on the **same** attempt):

| combination | attempts |
|---|---|
| `attempt_confidence` | 1,345 |
| `attempt_confidence` + `phase_status` | **1,345** (100% paired) |
| `attempt_confidence` + `attempt_cost_usd` + `attempt_model` + `phase_status` | 1,337 |
| `attempt_tokens_in` + `attempt_tokens_out` + `attempt_cost_usd` | 1,108 |
| `phase_test_verified` | 132 |
| `phase_test_verified` + `attempt_confidence` | **4** |

### 3. The values are in the kb artifacts (joinable by `knowledge_id`)

Each registry row's `knowledge_id` names a durable artifact at
`/app/experiments/results/kb/<knowledge_id>.json` (`24,261` files). The artifact's `text`
field is a JSON string; for an attempt fact it carries
`{"predicate": ..., "value": "<v>", "value_type": ...}` (verified on
`attempt_confidence` and `phase_status`). So the numeric signal is recoverable:

```python
value = json.loads(artifact["text"])["value"]   # e.g. "0.8913", or "ok"
```

Resolving every current attempt fact this way:

| quantity | resolved value |
|---|---|
| attempts with a **confidence** value | **1,345** |
| attempts with a **phase_status** value | 2,353 (`ok` 2,140 · `failed` 211 · `awaiting` 2) |
| attempts with **both** (the calibration sample) | **1,345** |

### 4. What the calibration sample actually looks like

**Confidence distribution is extremely concentrated.** `881 / 1,345` attempts (65.5%) are
exactly `1.0`; `14` are exactly `0.0`; the remaining ~450 spread thinly over `0.17–0.99`.
There are only two large point masses.

**Calibration against completion (`phase_status == "ok"`):**

| confidence bin | n | ok | P(ok) |
|---|---|---|---|
| `[0.0]` | 14 | 0 | **0.000** |
| `[0.2]` | 4 | 4 | 1.000 |
| `[0.3]` | 2 | 2 | 1.000 |
| `[0.4]` | 5 | 5 | 1.000 |
| `[0.5]` | 12 | 11 | 0.917 |
| `[0.6]` | 29 | 28 | 0.966 |
| `[0.7]` | 80 | 78 | 0.975 |
| `[0.8]` | 156 | 152 | 0.974 |
| `[0.9]` | 137 | 132 | 0.964 |
| `[1.0]` | 906 | 876 | 0.967 |

Read plainly: the signal is **informative only at the `0.0` boundary** (0/14 complete);
above `0.2` it is flat near 0.96–0.98 and **not monotone**. This is exactly the shape a
threshold policy cannot exploit across `(0, 1)`.

**And the signal is partly definitional, not purely predictive.** Per `opencode.py:113`,
`confidence` is `0.0` on session error, else `tests_passed/tests_total` when tests ran, else
the tool-call success fraction, else `None`. A phase that errored therefore tends to get
*both* `confidence == 0.0` *and* `phase_status == "failed"` **by construction**. The
`0.0` calibration cell is largely mechanical coupling; the flat region above it is where
genuine (lack of) predictive content lives.

### 5. Escalation history: zero

Across `387` live workflow run ledgers (`201` distinct specs; `1,155` phase rows; `394`
typed `attempts` rows, `327` carrying `confidence`):

| lineage field | rows with a value |
|---|---|
| `escalation_from` / `escalation_to` | **0** |
| `parent_attempt_id` | **0** |

There is **no observed escalation** anywhere in the corpus. `model_cascade` has no
implementation and no call site. Corroborated by `docs/reviews/workflow_metrics_findings.md`
("escalation rate — not measurable") and
`docs/reviews/retry_worthiness_findings.md` ("exactly one real retry event in the entire
corpus").

### 6. The parquet exposes **none** of the calibration fields

`/repo/experiments/data/sessions.parquet` (`1,027` rows) and `stories.parquet` (`207` rows)
are story/session aggregates. Their columns include cost, tokens, cache, `condition`,
`model`, `tests_passed/tests_total`, `all_successful`, `cascade_recovery` — and **no**
`confidence`, `perturbation_strength`, `test_executed_success`, `first_pass`, or `accepted`.
The parquet **cannot** answer the calibration question.

`python3 scripts/sync_data.py --check` currently **FAILS** in this checkout
(`resolved-input identity mismatch`, `sessions.parquet has 1027 rows, expected 0`) because
the canonical story payloads (`experiments/results/stories/*.json`) are absent here — the
parquet is a stale tracked artifact, not re-derivable from `/repo`.

### 7. Prior art already in the repo (do not duplicate)

| artifact | what it already establishes |
|---|---|
| `experiments/results/cap_cascade_retrospective.json` (schema `cap_cascade_retrospective/v1`, spec `cap_confidence_cascade@0.1`) | n=126 runs / 462 phases; confidence coverage 0.7835 (362/462); baseline **cost-per-verified-outcome = $1.8109** (n_captured 452, n_verified 434); trigger rates 1.66% / 3.59% / 10.77% at θ ∈ {0.3, 0.5, 0.7}; `null_testable = false` — the cascade *regret* is 0 by tautology because nothing was ever escalated |
| `experiments/definitions/cap_confidence_cascade.yaml` | the same finding as a compiled ExperimentSpec, with the `escalation_trigger`/`cascade_cost_per_verified_outcome` rules and the adversarial-review notes |
| `docs/reviews/cap_e2_e3_review.md` | independent re-derivation of the above; one corrected figure (θ=0.7 ok-false trigger rate is 37.5%, not 30.0%); flags that the two cascade scripts shipped with **zero tests** |
| `docs/experiments/designs/cap_grit_confidence_calibration_design.md` | the retry-threshold calibration design; explicitly records `P(test_executed_success \| confidence bin)` as **NOT measured**, and its falsifier #2 is "confidence does not calibrate" |
| `docs/experiments/results/cap_escalation_measurement.md` | measured **E_x = 11.4671** (sol) / **12.5134** (sonnet), n=1 per model — the downstream-defect multiplier, not a cascade ROI |

**The genuinely new question for Phase A** is therefore the one none of these compute:
*calibration of the measured `[H]` `confidence` against an outcome, with explicit coverage
and sample sizes* — plus a pre-registered grid whose arms and power are derived from it.

---

## Gaps

1. **The named query is a null.** `source_type == 'ledger_attempt'` matches **0** rows in
   the live registry (and the named path does not exist in `/repo`). The plan must read the
   `fact` layer + kb artifacts, and must say so explicitly rather than reporting an empty
   result as "no data".
2. **The named path is unversioned.** `/app` is not a git repo; `/repo` lacks
   `experiments/results/`. Any Phase A number is reproducible only against `/app`'s
   `registry_index.jsonl` at its recorded sha256 — the retrospective must pin that sha.
3. **The parquet is not a calibration source** and is stale in this checkout (§6).
4. **No verified outcome at scale.** `phase_test_verified` exists on `132` attempts and
   only **4** carry confidence. Calibration against *independent correctness*
   (`test_executed_success`) is **infeasible**; only calibration against the *completion*
   outcome (`phase_status`) is possible — and that outcome is partly the same signal
   `confidence` is computed from (the definitional coupling in §4).
5. **No escalation history** (§5). The escalation-ROI curve is **counterfactual only**; the
   `E_x` multiplier is n=1 and measures a *different* thing (defect-fix cost), so it must
   not be presented as a measured cascade ROI.
6. **Low variance / no separation.** 65.5% of the sample sits at exactly `1.0`; any θ in
   `(0.2, 1.0)` would escalate almost nothing new and gains nothing, while θ near `0.0`
   separates only the (definitionally coupled) error cases. A threshold policy has little
   room to act.
7. **No `first_pass` / `accepted` in the fact layer.** The pre-registration's preferred
   metrics (`first-pass`, `accepted`) are **not** retrospectively measurable; only
   `phase_status` completion is. The design doc must either redefine them onto the
   measurable signal or declare them Phase-B-only.
8. **Confounds unstratified so far.** The sample pools models, story/task identity, and run
   vintages (the registry spans weeks). Any calibration curve must be stratified or the
   pooled number is an average over a mixture.
9. **A hand-run hazard discovered during inventory:** `python3 scripts/sync_data.py check`
   (positional) **silently runs sync** and overwrote the tracked parquet with empty tables
   when the canonical payloads were absent; it was restored with `git restore`. The correct
   validator is the **`--check` flag**. The plan must forbid the positional form.

---

## Sources

Tracked (sha256 computed this phase; read-only):

| source | sha256 | role |
|---|---|---|
| `docs/architecture/current/2026-08-14_experiment-spec-and-compiler-design.md` | `85730aca…` | the spec/compiler design; `AttemptRecord` schema |
| `experiments/specs/STATUS.md` | `9380fc3c…` | the spec lifecycle index (read first) |
| `experiments/data_manifest.json` | `bf553208…` | tracked compacted registry (18,392 rows) |
| `src/agentic_dynamics/knowledge/ledger_ingestion.py` | `1b9c2a1a…` | the `ledger_attempt` producer (0 live rows) |
| `src/agentic_dynamics/control/reducers/attempt_facts.py` | `3cc35f34…` | the `attempt_facts/v1` reducer that actually emits the facts |
| `scripts/sync_data.py` | `e4c1a3cf…` | parquet builder; `--check` semantics |
| `experiments/definitions/cap_confidence_cascade.yaml` | `43c27c2e…` | prior retrospective spec |
| `experiments/definitions/cap_session_routing_evidence.yaml` | `a6ee3c35…` | prior lineage-arm spec (methods precedent) |
| `docs/experiments/designs/cap_grit_confidence_calibration_design.md` | `24a1b498…` | prior calibration design; names the gap |
| `docs/reviews/workflow_metrics_findings.md` | `4de1dab2…` | escalation "not measurable"; run-ledger absence |
| `docs/reviews/retry_worthiness_findings.md` | `f888d2ad…` | "one real retry"; confidence-cost read |
| `docs/experiments/results/cap_escalation_measurement.md` | `25dced68…` | measured E_x 11.47 / 12.51 |
| `docs/reviews/cap_e2_e3_review.md` | `dccb125e…` | independent verification of the prior retrospective |
| `tests/fixtures/corpus/registry_index.jsonl` | `4714ffaf…` | tracked registry snapshot (no values; stale vs live) |
| `workflows/repository/confidence_cascade_study.yaml` | `3e51a487…` | this workflow's own spec |

Live / unversioned (read from `/app`; the retrospective must pin the registry sha):

| source | identity | role |
|---|---|---|
| `/app/experiments/results/registry_index.jsonl` | 55,077 lines; sha256 `cf64fc97…` | the attempt-fact lifecycle index |
| `/app/experiments/results/kb/<knowledge_id>.json` | 24,261 files | the fact **values** (`text` → `value`) |
| `/app/experiments/results/workflows/**/*.json` | 387 ledgers / 201 specs | typed run attempts; escalation fields |
| `/app/experiments/results/cap_cascade_retrospective.json` | schema `cap_cascade_retrospective/v1` | prior cascade retrospective (cpvo $1.8109) |

Machine-readable form: `notes/sources.jsonl` (one JSON object per source, with sha256 and
the exact fields each contributes).
