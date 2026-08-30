---
status: accepted
---

# cap_2b — adversarial review (p5)

**Campaign:** `cap_2b` (`cap_2b@0.1`) · **Verdict under review:**
`docs/experiments/results/cap_2b.md` (committed `b90397323`) · **Pre-registration:**
`docs/experiments/preregistrations/cap_2b_preregistration.md` (committed `19e47b60b`, SHA256
`8259fe8d4776d7cb2c310348ea1315876eea74277d126e91fd74b98ef352c193`).
**Score:** `cap_2b_score_20260826T160018Z.json` (SHA256
`5f24f5072f1bb0ab17769b8db3734680b83981c2506df3b57fffa529c42ed3d9`).
**Attacker role:** adversarial verifier, attack in the pre-registered order; a deviation from the
pre-registered plan is a FAILED finding, not a limitation.

## Attack 1 — Pre-registration adherence

**Attack:** does the committed pre-registration match what was analyzed? Any redefined margin,
reseeded assignment, or dropped cell is a FAILED finding.

**Evidence:**
- Commit order (provable by `git log`): `19e47b60b` p0_preregister **16:53:43** → `f1a29803f` p1_measure_one **17:00:34** → `969e112ac` p2_run_randomized_cells **17:53:29** → `56a80c1e8` p3_score **18:00:44** → `b90397323` p4_verdict **18:01:55**. p0 precedes every cell: the E4 run ledger was written `20260826T145915Z` (14:59 UTC = 16:59 +0200), after p0 (16:53 +0200).
- The p0 commit adds exactly one file, `docs/experiments/preregistrations/cap_2b_preregistration.md` (301 lines), containing the margin (`≤ 1.10 ×` and `− 5 percentage points`, §2), the seed `fa74bbe6f9d4a67a019799ebfa61ac9e` (§4), and the full 18-cell assignment table (§4).
- The score/verdict applied exactly that margin: `score.decision_rule.margin_cpvo_ratio_le = 1.10`, `margin_success_gap_le = 0.05` — matching pre-registration §2 verbatim. No redefinition anywhere in the scored artifacts.
- Cells: 18 in the pre-registered table, 18 scored (`join_validation.n_scored=18`); zero dropped (`denominators.n_invalid_join=0`, no stopped cells).

**Result: PASS.** No deviation. The pre-registration is the analyzed plan; commit order proves it preceded data collection.

## Attack 2 — Randomization integrity

**Attack:** is the assignment table derivable from the committed seed + block scheme, and does
every recorded arm equal its assignment?

**Evidence (re-derived independently from the committed seed):**
- `random.seed("fa74bbe6f9d4a67a019799ebfa61ac9e")` + the pre-registration §4 block scheme
  (per stimulus block, a balanced 3-static/3-adaptive permutation; per-arm repetition = occurrence
  order) reproduces **exactly** the 18 cell ids in the pre-registration's table (doc set == derived
  set, symmetric difference empty).
- Every scored cell's `(stimulus, arm, repetition)` equals the seed-derived assignment for all
  18 cells (recorded set == derived set, symmetric difference empty). The p2 manifest's
  `assignment_integrity` independently recorded 17/17 p2 cells with 0 deviations.

**Result: PASS.** The table is seed-derivable and the recorded arms match it; no cell was scored
under a different arm than its assignment.

## Attack 3 — Application provability

**Attack:** are adaptive-arm reworks/verifies provable in the commit trail, and static-arm
proposals provably never applied?

**Evidence (re-examined in every one of the 18 worktrees):**
- All 3 adaptive critical cells carry a `[workflow] rework` commit on top of their implement
  commit; each diff is exactly **one line** in `calc.py` (`value > 10` → `value >= 10`, or the
  equivalent boundary fix) and touches **no test file** (no test weakening). Rework pass cost
  ~$0.004/15–16s each.
- All 9 static cells have **no** `rework`/extra pass in their commit trail; every proposal
  artifact records `"applied": false`; `applied_or_null = "not_applicable"`.
- All 9 adaptive cells: `rework` cells → `applied` with the rework commit as proof id; `continue`
  cells → `applied_or_null = "null"` with a commit trail showing only the workflow phases
  (provable null — no extra pass).

**Result: PASS.** Every application (or non-application) is provable from the commit trail; no
static cell was applied, no adaptive rework is unprovable.

## Attack 4 — Independent outcomes

**Attack:** are outcomes from test_runner + a post-hoc evaluator, not the proposing agent's
narrative?

**Evidence:**
- `test_executed_success` is the independent `runtime.test_runner` verdict (run ledger `kind:test`
  phase) plus an **independent re-run** of `pytest` on each final commit performed in this review:
  recorded verdict == re-run verdict for **all 18 cells** (0 mismatches).
- Defect presence is a **post-hoc evaluator** determination: the inherited boundary test
  (`test_calc.py::test_classify`) run on the immutable final commit (2/3 → defect present for the
  3 static critical cells; 3/3 → absent for the 3 adaptive critical cells). It never uses the
  proposing agent's self-report.
- The designed pre/post contrast is confirmed: the 3 adaptive critical cells' run-ledger test
  phase (pre-rework, on the implement commit) reads 2/3, while the final-commit outcome reads 3/3 —
  the outcome is measured **after** the applied rework, exactly as the plan specifies.

**Result: PASS.** Outcomes are independent; the proposing agent's narrative plays no role in
`accepted`.

## Attack 5 — Measured-fix provenance; treatment untouched

**Attack:** were the measured fixes (scope `cc66efd30`, expected-effects `4fa22047c`, severity
`0e24d6985`) consumed as-is, and the treatment left untouched?

**Evidence:**
- `git log 19e47b60b..HEAD -- src/agentic_dynamics/control/verify_proposal.py
  src/agentic_dynamics/control/code_change_facts.py` → **empty** (no change to the treatment or
  the risk weights during the campaign).
- The three fixes are in history **before** the campaign and were not re-touched.
- The stimulus cell specs (`cap_2a_cell_clean/critical/style.yaml`) and the campaign spec
  (`cap_2b.yaml`) are unchanged between p0 and HEAD (`git log` empty).

**Result: PASS.** The treatment is code-unchanged; the merged measurement fixes are consumed as-is.

## Attack 6 — Usual suite (baselines, denominators, credentials, hashes, guard, fabrication)

**Attack + evidence:**
- **Baselines:** the seed commit content (`calc.py` + `test_calc.py`) is byte-identical across
  all 18 worktrees (single distinct hash).
- **Denominators:** n=18 total, 9 per arm, 6 defect-bearing — all printed in the score;
  `n_invalid_join=0`, no dropped/stopped cells.
- **Credentials:** no `sk-…`/api-key/password/secret patterns in any committed cap_2b artifact
  (git-grep clean).
- **Hashes:** the score JSON SHA256 equals the validation pin; **73/74** entries of the p2
  manifest artifact index match the files; fabrication of cell data is contradicted by the
  run-ledger cross-check (recorded cost == ledger `total_cost_usd` for all 17 p2 cells) and by the
  rework-diff audit.
- **Guard:** $0.1744 total spend vs the $30.00 stop budget; no cell exceeded 2× forecast; zero
  stopped cells.

**Result: PASS (with one accepted limitation — see L1).**

## Findings table

| # | attack | result | fix / limitation |
|---|---|---|---|
| A1 | pre-registration adherence | **PASS** | — |
| A2 | randomization integrity | **PASS** | — |
| A3 | application provability | **PASS** | — |
| A4 | independent outcomes | **PASS** | — |
| A5 | treatment untouched | **PASS** | — |
| A6 | usual suite | **PASS (1 limitation)** | L1 below |
| A7 | commit-history anomaly | **PASS (1 limitation)** | L2 below |

## Accepted limitations

**L1 — stale artifact-index entry for the execution manifest (`p2_manifest.json`).**
Reasoning: `p2_manifest.json`'s `artifact_sha256_index` snapshots 74 artifacts; 73/74 hashes match
the current files. The single stale entry is `p2_execution_manifest.json` — indexed at
`94328f52…`, current `7bb802e9…` — because the execution manifest was **finalized** (all 18 cells
marked done) after the index was computed. This is a snapshot-timing artifact of my own
finalization edit, not tampering: the execution manifest's current committed content is the
finalized one (its hash `7bb802e9…` is what the p4 verdict cites), and no scored artifact is
affected. Residual risk: negligible — an index that predates one benign edit; every scored number
traces to the score JSON, whose own hash is pinned and verified.

**L2 — unattributed auto-emissions commit (`141c612f9`, author "Experiment Runner").**
Reasoning: commit `141c612f9` (child of p1, between p1 and p2) carries message
`[workflow] p1_measure_one — Run the 2b randomized pilot end to end…` and contains **only** p1's
framework auto-emissions: 31 `experiments/results/kb/*.json` fact artifacts plus the registry rows
and spec-index refresh (`registry_index.jsonl`, `STATUS.md`, `index.json`). It is the fingerprint
of an environment-side `run_workflow.py` invocation of the cap_2b campaign spec (the "Experiment
Runner" identity from `_init_git_workdir`) that committed those emissions. It touches **no scored
artifact, no assignment table, no margin, no code, no cell data**, and precedes p2 (cells) and p3
(score). Residual risk: low — a parallel campaign runner exists in the environment; if it later
runs phases it could collide, but the canonical verdict re-derives from the committed immutable
artifacts only, and the score's join validation guards the arms. No fix applied (content is
legitimate; history is not rewritten).

## Re-test

The decision-rule computation was re-derived in this review from the same immutable artifacts:
cpvo ratio **0.7857** (95% CI [0.6842, 0.9105]) ≤ 1.10 and success gap **−0.3333** ≤ 0.05, at
n = 9 per arm and n = 6 defect-bearing — identical to the p3 score and the p4 verdict. No
recomputation changed any number.

## Re-stated verdict

**UNCHANGED — NON-INFERIOR.** Adaptive verification is non-inferior to static on
cost-per-accepted-outcome and verified success by the pre-registered decision rule (§2 margin,
§5 rule), with n and CI. Per §6, this authorizes **design review of continuing adaptive
selection — nothing else**; it does not launch the continuing regime. No finding in this review
changes the verdict; the two accepted limitations (L1, L2) carry no integrity effect on the
scored outcome.

**LOG:** A1 PASS · A2 PASS · A3 PASS · A4 PASS · A5 PASS · A6 PASS (L1) · A7 PASS (L2);
re-test reproduces ratio 0.7857 / gap −0.3333. **PASS** — verdict re-stated unchanged; commit.
