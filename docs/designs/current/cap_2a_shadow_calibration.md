---
status: accepted
---
# cap_2a — Shadow calibration: 2b gate verdict

Date: 2026-08-25 · Branch: `feature/cap-2a-shadow-calibration` · Campaign: `cap_2a_shadow_calibration`

## Provenance

- **Source revision:** `e61c709ebd3f9cf4c731ea0b731ac09e787a6343` (the campaign's recorded source revision; every cell worktree was cut from this revision)
- **Spec version:** `0.2` (`workflows/repository/cap_2a_shadow_calibration.yaml`)
- **Candidate-manifest SHA256:** `6b8bbab62c868a236c72cf9b6d71201dfde91484cf7ffbca8e89a20a5336c315`
- **p4 scoring JSON:** `experiments/results/cap_2a_score_20260825T222430Z.json`
  - SHA256: `3862c784b337aea135087711bacad614e115d82604cdf6b107ca0a3277adc197`

Every number below cites a field in that p4 JSON (`<section>.<field>`), and the input-artifact
hashes inside it are re-verified in the Guard section.

## Cells table

| cell_id | spec / path | model · backend | baseline → analyzed | graph_status | forecast / actual cost | duration | proposal (action·depth·scope) | proposal validity | realized outcome · depth · symbol-set | status | blast-radius error |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `cap2a_p2_registry_canonicalize` | `workflows/operations/registry_canonicalize.yaml` | `deepseek/deepseek-v4-pro` · opencode | `e61c709eb` → `bccb17514`, `fb1ca291e`, `c2ed5270e` | `unavailable` (graph requested, population impractical; delta-only fallback) | forecast $0.1872 (historical index) / **actual $0.202402** | ~1119s total (implement ~300s · test 463.47s · verify 356.18s) | none — seam refused (`code_change_risk` never produced) | n/a (no proposal emitted) | not adjudicated — no independent outcome record | **invalid** (`proposal_missing`, `graph_unavailable`) | **null** — no predicted impacted count (graph unavailable), never encoded as 0 |
| `cap2a_p3_labbook_refresh` | `workflows/operations/labbook_refresh.yaml` | `deepseek/deepseek-v4-pro` · opencode | — (never ran) | `not_requested` | forecast $0.404804 (p2×2, FORECAST) / actual — | — | none | n/a | — | **not-run** | null — not run |
| `cap2a_p3_queue_steer` | `workflows/operations/queue_steer.yaml` | `deepseek/deepseek-v4-pro` · opencode | — (never ran) | `not_requested` | forecast $0.404804 (p2×2, FORECAST) / actual — | — | none | n/a | — | **not-run** | null — not run |

Source of per-cell rows: `cells[]` in the p4 JSON; cost/duration detail: `experiments/results/cap_2a/p2_phase_ledger.json`.

## Analysis

Reported exactly as `aggregates` in the p4 JSON — no denominator is used that is not printed:

- **Proposal hit-rate:** `n_hits / n_scored` = `0 / 0` — **undefined** (`aggregates.hit_rate = null`, `aggregates.hit_rate_n = 0`).
- **Wilson 95% interval:** `aggregates.wilson_95 = null` — cannot be computed at n = 0.
- **Denominators (printed separately):**
  - `n_scored = 0` (`aggregates.n_scored`)
  - `n_hits = 0` (`aggregates.n_hits`)
  - `n_unknown_outcome = 0` (`aggregates.n_unknown_outcome`)
  - `n_invalid_join = 0` (`aggregates.n_invalid_join`)
  - `n_not_run = 2` (`aggregates.n_not_run`)
  - `n_proposal_missing = 1` (`aggregates.n_proposal_missing`)
- **Graph-down rate:** `graph_down_n / graph_down_denominator` = `1 / 1` = **1.0** (`aggregates.graph_unavailable_rate`) — the one cell that ran had an unusable graph.
- **Outcome-recorded rate:** `0.0` (`aggregates.outcome_recorded_rate`) — no ran cell produced an independent outcome record.
- **Proposal-validation rate:** `0.0` (`aggregates.proposal_validation_rate`) — no proposal was emitted, hence none validated.
- **Predicted-vs-observed blast radius:** `aggregates.blast_radius = { n_available: 0, mean: null, median: null }` — no cell has a predicted impacted-symbol count (graph unavailable); error is null (graph-flagged), never 0.
- **Risk calibration:** `aggregates.risk_calibration = []` — empty; no `code_change_risk` was ever produced, so no bucket-vs-rework table exists.

## Verdict

**The raw 2b calibration threshold (proposal hit-rate ≥ 0.6) is NOT met.** Hit-rate is
**undefined** at `n = 0` (`aggregates.hit_rate = null`; `aggregates.hit_rate_n = 0`), and the
Wilson 95% interval is not computable (`aggregates.wilson_95 = null`). This is not a small
sample that fails to reach 0.6 — it is a **zero-scored** sample: no cell produced a complete
`verify_code_change` proposal to score, so the gate cannot be evaluated at all.

**Blocker (why there are zero valid outcomes):** the adaptive verifier was never exercised,
because its proposal seam refuses to emit. The seam requires `code_change_risk` as an
`on_missing: halt` fact, and `code_change_risk` is never minted by the wired runtime:
`run_workflow.py`'s `_run_change_analysis` injects no sonar/lsp into `ChangeInput` (so the
sonar/lsp risk terms are always absent), and the remaining cells change no Python symbols (so
the tests-ratio term is deferred) while the graph leg (impacted term) is impractical at
full-repo scale. Verified concretely in p2/p3: `build_verify_proposal` raises `ValueError` on
the delta-only facts a data-only cell produces.

**Additional valid outcomes needed to clear the gate:** the campaign requires at least one
(and, for a non-descriptive result, a campaign-declared minimum of) cell that produces a
complete proposal **and** a recorded non-unknown outcome. Concretely, that means:
1. Wire sonar and/or lsp measurement into `_run_change_analysis` so `code_change_risk` can be
   minted (the missing instrumentation), **or** run a cell that changes Python symbols with
   test coverage (so the tests-ratio term is measurable).
2. Record an independent realized outcome (`no_rework` / `verification_only` /
   `targeted_rework` / `broad_rework` / `unknown`) + `realized_depth` + a stable
   `realized_symbol_set`, adjudicated from the baseline's immutable commit and an independent
   test/evaluator — never the model's own narrative.

Until (1) and (2) hold for at least one cell, every future hit-rate would be `0/0`, and the
result must remain **descriptive-only** (never an authorization).

## 2b prerequisites (design §6 — restated, mandatory)

Counterfactual 2a **cannot** provide these; they are prerequisites for any 2b launch and are
unchanged by this verdict:

1. **Randomized static-vs-adaptive assignment** on live runs (2a holds the model constant and
   runs the adaptive action shadow-only — there is no control arm).
2. **Pre-registered non-inferiority margin and outcome metric**.
3. **Independent test execution** (an independent `test_runner` verdict, not the agent's
   self-report).
4. **Budget/SLA guard**.
5. **Outcome non-inferiority under adaptive control**.

2b launches **only** after (a) the p4 threshold is met **and** (b) these prerequisites are
explicitly reviewed. This phase does **not** launch a run, flip `control_route`, or arm
actuation.

## Guard — number provenance

- `n_scored`, `n_hits`, `hit_rate`, `hit_rate_n`, `wilson_95`, `n_unknown_outcome`,
  `n_invalid_join`, `n_not_run`, `n_proposal_missing`, `graph_unavailable_rate`,
  `outcome_recorded_rate`, `proposal_validation_rate`, `blast_radius`, `risk_calibration` all
  cite `aggregates.*` of `experiments/results/cap_2a_score_20260825T222430Z.json`
  (SHA256 `3862c784…adc197`).
- The p4 JSON's `input_artifacts[]` hashes are re-verified against the tree:
  `p2_candidate_manifest.json` `6b8bbab6…` ✓, `p2_cell_manifest.json` `71456ce4…` ✓,
  `p2_phase_ledger.json` `8c95e10a…` ✓, `p3_execution_manifest.json` `8d08017f…` ✓.
- No number is reported without its n, denominator, uncertainty, or flagged-cell treatment.

## Log

**PASS/FAIL: PASS** — the verdict is issued with n, denominator, uncertainty, and the blocker
stated; the gate is reported as NOT met (hit-rate undefined, n = 0) with the missing
instrumentation named, and no 2b authorization is implied.
