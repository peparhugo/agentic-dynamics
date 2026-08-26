# cap_escalation_measurement — adversarial verification

**Role:** adversarial verifier (p4). **Source revision:** `bc4c2c573` (p3 score JSON committed).
**p1 verification:** `experiments/results/cap_escalation_measurement/p1_locate_verification.json`
(SHA256 of the phase ledger `ed385510052c2867de04844b8391215a60c9bfc5702fb7da6f2d41cd62091c81`).
**p2 outcome records:** `cap_esc_sol_outcome.json`, `cap_esc_sonnet_outcome.json`.
**p3 score JSON:** `cap_escalation_measurement_score_20260826T125726Z.json`.

## Findings table

| # | Attack (order) | Result | Disposition |
|---|---|---|---|
| F1 | (1) attribution — is the escalation session fixing THE escaped defect? | **PASS** | no finding; both fixes are the single-line inverted boundary comparison, test_calc.py untouched |
| F2 | (2) hints — did the session receive anything beyond the pinned goal? | **PASS** (with one provenance gap) | accepted limitation (raw_prompt_hash not recorded in the run ledger; prompt reconstructed from the immutable spec) |
| F3 | (3) denominator integrity — original cell cost is the true measured cost | **PASS** | no finding; $0.008949 `total_measured_cost_usd`, not the forecast $0.017018 |
| F4 | (4) E_x math — recompute from ledgers | **PASS** | no finding; 11.4671 and 12.5134 recomputed |
| F5 | (5) loss-table comparability — measured vs 3.1 vs 28 | **PASS** | no finding; same base defect cost $0.004021 |
| F6 | (6) usual suite — credentials/hashes/not-run/fabrication | **PASS** | no finding; hashes verify, no secrets, both tiers ran, numbers trace to ledger fields |
| F7 | (2)+(6) n=1 per escalation model | accepted | limitation (single cell per model — descriptive, no CI) |

No finding falsified the campaign's claim (the measured escalation multiplier E_x ≈ 11.5–12.5 per
model). The only accepted items are a prompt-provenance gap and the descriptive n=1.

---

## Attack-by-attack

### (1) Attribution — is the fix THE escaped defect? — **PASS**

The rerun3 critical-baseline outcome record states the ONE deliberate defect: the inverted
boundary comparison in `calc.py`'s `classify` — `elif 10 < value < 20` (strict `>`) where the
documented `[10,20)` contract requires `>= 10`, so `classify(10.0)` returns `"upper-a"` instead
of `"mid-a"` (p1 re-verified: fresh worktree at `efe33b6fb8ad` runs pytest → `test_classify`
FAILS `assert 'upper-a' == 'mid-a'`, 1 failed / 2 passed).

- **sol cell** (`cap_esc_sol_efe33b6`, final commit `45b11f7`): `git diff efe33b6… HEAD` is
  `calc.py | 2 +-` with the single change `- elif 10 < value < 20` / `+ elif value < 20`. The
  lower bound `>= 10` is implied by the preceding `elif value < 10` band, so the `[10,20)` band
  is now exactly correct.
- **sonnet cell** (`cap_esc_sonnet_efe33b6`, final commit `f44aa04`): byte-identical diff shape —
  `calc.py | 2 +-`, same one-line boundary change.
- **test_calc.py untouched in both** (`git diff … HEAD -- test_calc.py` → 0 lines): the fix did
  NOT weaken or delete the failing test. Tests pass 3/3 on both final commits, and the boundary
  holds: `classify(10.0)='mid-a'`, `classify(9.999)='low-h'`, `classify(19.999)='mid-h'`,
  `classify(20.0)='upper-a'` (verified by direct import on both worktrees).
- **Cross-check vs the rerun3 gate arm's rework** (`33211ed`, `calc.py | 2 +-`,
  `- if value > 10` / `+ if value >= 10`): same defect class — the `[10,20)` lower-bound `>` vs
  `>=` boundary. The gate's code *structure* differs (its implement phase produced a different
  `classify` body), but the defect identity and the required boundary correction match.
- **Result: PASS.** The escalation session fixed THE escaped defect — not a different breakage.
  The `realized_symbol_set` from the change-analysis seam is `{classify}` for both cells.

### (2) Hints — did the session receive anything beyond the pinned goal? — **PASS** (F2 caveat)

- **Worktree contents at the source commit** (`git ls-tree efe33b6fb8ad`): exactly `.gitignore`,
  `calc.py`, `test_calc.py`. No campaign/verifier/defect-location material was present before the
  session ran.
- **Goal text:** the pinned goal `fix the inherited codebase so its tests pass` (SHA256
  `1ec5e625…`) is the implement-phase prompt's `{goal}`; the surrounding prompt is limited to a
  neutral READ FIRST + run-pytest instruction (see the immutable `workflows/operations/cap_escalation_fix.yaml`,
  committed before both runs).
- **Environment:** `FINOPS_CELL_ID` (a scope id), `CLAUDE_BIN` (the binary path), the standard
  run_workflow env. None carry campaign/defect information. The `.instrument/session.jsonl` in
  each worktree is the runtime session transcript (created during the run, not a pre-seeded hint).
- **F2 accepted limitation:** the phase ledgers record `raw_prompt_hash: ""` (the run did not
  populate the raw-prompt hash field for these runs). The prompt actually sent is therefore
  reconstructed from the committed spec rather than from a ledger-stored hash. Residual risk:
  low — the spec is immutable and was committed before execution; nothing in the environment or
  worktree could inject campaign context.

### (3) Denominator integrity — **PASS**

E_x denominator = `total_measured_cost_usd = $0.008949` in
`cap2a_r3_critical_baseline_phase_ledger.json` (SHA256 `ed385510…`, verified), which is the
critical-baseline cell's TRUE measured cost (implement $0.00894911 + test $0.0), NOT the forecast
`$0.017018`. The rerun3 score JSON's `cost_usd` field for the same cell is also $0.008949 —
consistent across both sources.

### (4) E_x math — **PASS**

Recomputed from the ledgers: `0.102619 / 0.008949 = 11.4671` (sol),
`0.111982 / 0.008949 = 12.5134` (sonnet). Numerator = the implement-phase `cost_usd` in the
committed phase ledgers (`phase_ledger_cap_esc_sol.json`, SHA256 `76f20f34…`;
`phase_ledger_cap_esc_sonnet.json`, SHA256 `6afad2c7…` — both verified). The test phase is
deterministic and $0. Both models are the escalation-path models (no DeepSeek floor), matching
the spec's guard.

### (5) Loss-table comparability — **PASS**

Base downstream defect cost re-derived from the rerun3 score JSON asymmetric_loss block:
`0.11258800000000001 / 28.0 = $0.004021` (not trusted from the docs supplement copy). All four
loss-table columns (3.1, 11.4671, 12.5134, 28) multiply the SAME base; only the multiplier
differs. Columns are comparable.

### (6) The usual suite — **PASS**

- **Hashes:** all three ledger SHA256s re-verify (original cell ledger, both phase ledgers).
- **Credentials:** no secret material (`sk-*`, api keys, passwords) in any committed
  `cap_escalation_measurement` artifact.
- **Not-run tiers mislabeled:** none — both escalation models authenticated in p1 and ran to
  completion; no tier is flagged not-run and no number was estimated.
- **Fabricated numbers:** every E_x / loss value traces to a ledger field (see p3 `validation_note`).
- **Transient harness run:** the first sonnet attempt failed `exit_code=-2` (claude CLI not on
  PATH — 0 tokens, $0.0, no commit) and its empty ledger was removed from the corpus; the
  successful run is the one measured. This is disclosed, not hidden.

---

## F7 — descriptive n=1

Each escalation model is a single cell (n=1 per model). The measured E_x values (11.47 sol,
12.51 sonnet) are descriptive, not a distribution. The near-agreement across two different
providers/backends is suggestive, but no CI can be quoted. Recorded as an accepted limitation
with residual risk that a re-run on either model could move its E_x.

## Re-stated verdict

The measured escalation multiplier is **E_x ≈ 11.47** (openai/gpt-5.6-sol via opencode) and
**E_x ≈ 12.51** (anthropic/claude-sonnet-5 via claude_cli) — both from MEASURED dollars
(fix cost / original cell cost, denominator SHA256 `ed385510…`). The loss-table swing at the
measured values is **$0.092218 / $0.100632**, between the sourced $0.024930 (E_x=3.1) and
$0.225176 (E_x=28). The rerun3 asymmetric-loss conclusion's DIRECTION is robust at both
measured multipliers (both far above the ~1.42 break-even); the MAGNITUDE is ~10x smaller than
the E_x=28 sourced figure and ~4x larger than the 3.1 figure. **The campaign survives
adversarial verification** with one prompt-provenance limitation (F2) and the descriptive n=1
(F7); no finding falsifies the measured E_x.

**LOG:** findings F1/F3–F6 PASS, F2 + F7 accepted limitations; known-safe list in
`docs/reviews/cap_escalation_measurement_known_safe.md`. **PASS** — findings re-verified against
the tree and committed artifacts; no bare PASS.
