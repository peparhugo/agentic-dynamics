---
status: accepted
---
# cap_session_routing_prospective — verdict: the 4-arm session-policy grid, LIVE

The verdict document for the session-routing prospective campaign. The accepted design is
`docs/designs/current/cap_session_routing_prospective_design.md`; this document reports what
was measured, scores the four arms, and tests the retrospective escalation premium with live
randomized numbers.

## 1. What was measured

One small multi-phase agent_task cell (implement + test + verify against a seeded calc app)
was run as a 24-cell factorial grid — `session_policy` [continue, fork_blind, fork_cached,
escalate] × `model` [deepseek/deepseek-v4-pro, deepseek/deepseek-v4-flash] × `repetition`
[r1, r2, r3]. Cell E4 (continue / pro / r1) was measured in p1; the remaining 23 cells were
run in p2, each in a fresh worktree with a unique `FINOPS_CELL_ID`.

**Provenance** (guard: every number below cites the p3 score JSON, `per_arm.<arm>.<field>`):

| item | value |
|---|---|
| source revision (scoring) | `5e5705153dea` |
| cell spec | `workflows/operations/cap_session_policy_cell.yaml` @ `0.1` (sha256 `4aacdc48…`) |
| candidate manifest (p1) | `cap_session_policy_candidate_manifest.json` sha256 `547ad21b7c636206b347d49daf3a1b130f2d4506ae20cd05499f49f9540b594b` |
| grid execution manifest (p2, candidate-first) | `cap_session_routing_prospective_p2_execution_manifest.json` sha256 `22ce42094648d0f8e8f4a73ae9e0e3d8232c43867dbbbd01211d567bb877742d` |
| p3 score JSON | `cap_session_routing_prospective_score_20260826T160605Z.json` sha256 `288e0486d684b4f5f8809f626297ce521848de47e233d9482600dd06ae1a4402` |
| p3 validation trace | `cap_session_routing_prospective_p3_validation.json` sha256 `82563a32c927c9099d43e44cac52f457d4bc3955874d2203c2c39e3397556feb` |

All artifacts live under `experiments/results/cap_session_routing_prospective/`; run ledgers
are the immutable phase records (`cap_session_policy_phase_ledger_<cell>.json`).

## 2. Grid validation

Every cell's session behavior was validated against its assigned arm **before** scoring: the
opencode session-store fork markers were re-derived from the ledger session ids (never trusted
from the manifest) and compared to the arm's expected behavior (chained `[false, true]` for
continue/fork_cached/escalate; cold `[false, false]` for fork_blind).

- Cells scored: **24** (p3 score JSON → `validation.cells_scored`)
- Cells invalid / excluded: **0** (p3 score JSON → `validation.cells_invalid_excluded`)

## 3. Per-arm table

All four arms verified at **6/6 (100%)** on this stimulus, so per-arm cpvo equals per-cell cost
(p3 score JSON → `per_arm.<arm>.cpvo_usd` = `total_cost_usd / n_verified`).

| arm | n | verified (rate) | cpvo | total cost | cache_ratio | rework | repeated failures | mean latency | mean ctx-token growth |
|---|---|---|---|---|---|---|---|---|---|
| `continue` | 6 | 6 (1.0) | **$0.005921** | $0.035524 | 0.7752 | 0 | 0 | 144.82 s | 1.667 |
| `fork_blind` | 6 | 6 (1.0) | **$0.005322** | $0.031933 | 0.8451 | 0 | 0 | 150.05 s | 1.357 |
| `fork_cached` | 6 | 6 (1.0) | **$0.006093** | $0.036556 | 0.7606 | 0 | 0 | 145.05 s | 1.675 |
| `escalate` | 6 | 6 (1.0) | **$0.005946** | $0.035678 | 0.7788 | 0 | 0 | 147.92 s | 1.660 |

Cache utilization (p3 score JSON → `per_arm.<arm>.cache_read_tokens`): continue 387,968 ·
fork_blind 546,688 · fork_cached 364,544 · escalate 406,144 cache-read tokens across the six
ledgers per arm (with `tokens_in`: 104,222 / 91,326 / 105,874 / 105,852).

## 4. Model × policy interaction (addendum F5)

cpvo per arm–model cell, n=3 each (p3 score JSON → `arm_model_interaction.<arm>.<model>`):

| arm | pro cpvo | flash cpvo | flash / pro |
|---|---|---|---|
| `continue` | $0.008823 | $0.003019 | 0.34× |
| `fork_blind` | $0.007639 | $0.003005 | 0.39× |
| `fork_cached` | $0.009233 | $0.002952 | 0.32× |
| `escalate` | $0.008724 | $0.003169 | 0.36× |

The model effect dominates the grid: flash is ~3× cheaper than pro on every arm. The policy
effect is model-conditional — `fork_cached` is cheapest on flash ($0.002952), `fork_blind` is
cheapest on pro ($0.007639).

## 5. Retrospective comparison (n stated on both sides)

Source: `experiments/results/session_routing_retrospective.json` (retro) vs the p3 score JSON
(live). Retro absolute dollars come from full-size workflow cells; the live cell is a tiny
calibration stimulus — **absolute cpvo is not comparable across regimes**, only the ratio
within each regime.

| arm | retro cpvo (n) | live cpvo (n) |
|---|---|---|
| `continue` | n/a — never isolated (n=0) | $0.005921 (n=6) |
| `fork_blind` | n/a — never isolated (n=0) | $0.005322 (n=6) |
| `fork_cached` | **$1.2658** (n=246) | $0.006093 (n=6) |
| `escalate` | **$3.9238** (n=7) | $0.005946 (n=6) |

Escalation premium: retro `3.9238 / 1.2658` = **3.10×** (n=7 vs n=246) · live
`0.005946 / 0.006093` = **0.976×** (n=6 vs n=6). The retro premium is a within-regime ratio;
the live "premium" is a parity ratio — see the verdict.

## 6. Flagged cells

- **Invalid cells:** none — all 24 passed the arm↔session-behavior join.
- **Escalate untriggered (flagged, never narrated):** all 6 escalate cells completed on the
  assigned model's first attempt, so the arm never fired. The mechanism is proven executable
  and ledger-provable separately (`cap_session_policy_escalate_proof_cap_sesspol_escalate_mechanism_proof.json`:
  failed implement on flash → re-run on pro in a NEW session → test → verify). The grid
  records escalate as untriggered, not estimated.
- **Analyzer/graph flags:** none — sonar + lsp reported available and `graph_status`
  `not_requested` in every cell (per-cell `analyzer_flags` all `[]`).
- **Known limitation (flagged, not silent):** in the current runner, `continue` and
  `fork_cached` share the chained-session mechanism (fork=true). Both are executed with the
  same session semantics and the arm label is the assignment; the typed no-checkpoint vs
  checkpointed-fork distinction is I10-gated. `cache_read_tokens` is not a clean arm
  discriminator (provider prefix caching serves reads even in cold sessions); the provable
  discriminators are the session-store fork markers and the runner fork flag recorded in each
  cell manifest.

## 7. Proxy mapping — what each arm executed vs the typed-checkpoint semantics

| assigned arm | what the cell executed (runner behavior, provable in the ledger) | typed-checkpoint semantics it proxies | I10 status |
|---|---|---|---|
| `continue` | fork=true — one session lineage for the whole cell; each phase resumes the prior session's context prefix (cache reuse, stale-context risk); session-store title `(fork #N)` on the follow-up phase | the no-checkpoint baseline | not-run (typed) |
| `fork_blind` | fork=false — a new COLD session per phase; no session chaining; plain session titles | fork without checkpoint | not-run (typed) |
| `fork_cached` | fork=true — a new session per phase, same model, WARM cache (chained context served as cache reads) | fork-with-checkpoint simulated by cache reuse (the retro proxy, n=246) | not-run (typed) |
| `escalate` | assigned model; a failed phase is re-run in a NEW session on the OTHER model (pro ↔ flash) — mechanism proven in the ledger (failed phase → new session → other model) | escalate-with-checkpoint | not-run (typed) |

## 8. Verdict

**Per-arm ranking (descriptive, n=6 per arm):** `fork_blind` ($0.005322) < `continue`
($0.005921) < `escalate` ($0.005946) < `fork_cached` ($0.006093). The four arms sit inside a
15% band; all verified at 100%. `fork_blind` is the lowest-cost arm, carries the lowest
context-token growth (1.357 vs ~1.67 for the chained arms) and the highest cache ratio
(0.8451) — the cold-session arm avoids context-pressure costs on this tiny stimulus. These
differences are descriptive, not effect-sized: n=3 per policy–model cell.

**The retrospective escalation premium (3.1×): not confirmed, not moved, not falsified —**
**untestable in this grid.** All six live escalate cells completed on the assigned model's
first attempt (escalate untriggered), so the live escalate cpvo ($0.005946) measures the
no-escalation-needed case, and the live 0.976× ratio is a cost-parity statement, not an
estimate of the escalation-premium hypothesis. The 3.1× premium (retro n=7 vs n=246) stands
**neither confirmed nor refuted by live randomized numbers**; it can only be tested by a cell
whose first attempt actually fails.

**Descriptive-only (no authorization):** at n=3 per policy–model cell no arm is authorized and
no policy is promoted — `session_routing_v1` stays proposal-only (shadow). The live fork_cached
number does, however, re-measure the retro proxy arm on a controlled cell at a radically lower
cost base; the premium question is the open item, not the fork_cached baseline.

**I10 typed-checkpoint arms remain not-run:** `fork_with_checkpoint` and
`escalate_with_checkpoint` (real `context_snapshot_id`) are not executable and were never
estimated. The instrumentation gap is restated in §9.

## 9. Instrumentation gap (restated)

Checkpoints have zero production capture: `checkpoint_snapshot_identity` is
declared-never-emitted (CAP I10 forward-only), so the typed checkpoint arms cannot be
measured. The evidence-spec proxies (new session + cache reuse for `fork_cached`; failed-run
then other-model run for `escalate`) are the executable stand-ins and are recorded in every
cell manifest — never silent, never estimated as the typed arms. Measuring the typed arms is
gated on I10 landing a real snapshot producer (`context_snapshot_id`), which this campaign does
not build.

## Citations

Every verdict number above cites a field of
`experiments/results/cap_session_routing_prospective/cap_session_routing_prospective_score_20260826T160605Z.json`
(`per_arm.<arm>.cpvo_usd / verified_success_rate / cache_ratio / mean_latency_s /
mean_context_token_growth / rework_total / repeated_failures_total`; `arm_model_interaction`).
Retro numbers cite `experiments/results/session_routing_retrospective.json`
(`arms.<arm>.cost_per_verified_outcome.value / .n`), with n stated on both sides. The
field-level trace is `cap_session_routing_prospective_p3_validation.json`.

**LOG: PASS.**
