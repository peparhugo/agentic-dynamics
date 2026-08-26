---
status: accepted
---

# cap_escalation_measurement — verdict

**Campaign:** `cap_escalation_measurement` (`workflows/repository/cap_escalation_measurement.yaml`).
**Wrapper:** `deepseek/deepseek-v4-flash`. **Source revision of the analysis:** `bc4c2c573`.
**Phase deliverables:** `experiments/results/cap_escalation_measurement/` (p1 verification, p2
cell manifests/outcomes/phase ledgers, p3 score JSON) + this verdict + the p4 reviews.

## Question

What does a rejected outcome actually cost downstream, in dollars? The rerun3 control
experiment's asymmetric-loss table scaled linearly with the escalation multiplier E_x, sourced
at 28 (pricing ratio) and 3.1 (handoff figure). This campaign MEASURED E_x: the critical-
baseline cell's escaped defect (immutable commit `efe33b6fb8ad`) was handed to fresh escalation
sessions whose only instruction was the pinned goal, and the measured fix cost / original cell
cost is the measured E_x.

## The escaped defect (p1 — PASS)

Verified PRESENT on the immutable commit `efe33b6fb8ad5723c7645b0bbe953227cdd7c2fc`
(`cap2a_r3_critical_baseline`, accepted=false): a fresh worktree at that commit runs the
inherited suite and `test_calc.py::test_classify` FAILS (`assert 'upper-a' == 'mid-a'`,
1 failed / 2 passed, matching the ledger's `tests_passed=2/tests_total=3`). The defect is the
inverted boundary comparison in `calc.py`'s `classify` — `elif 10 < value < 20` (strict `>` at
the `[10,20)` lower bound) misclassifies `classify(10.0)` as `'upper-a'` instead of `'mid-a'`
(the stimulus spec's ONE deliberate defect). Original cell cost (the E_x denominator):
**$0.008949** `total_measured_cost_usd` from
`cap2a_r3_critical_baseline_phase_ledger.json` (SHA256 `ed385510052c2867de04844b8391215a60c9bfc5702fb7da6f2d41cd62091c81`).
Auth checked: both escalation models AVAILABLE (openai/gpt-5.6-sol via opencode — OpenAI oauth;
anthropic/claude-sonnet-5 via claude_cli — `claude auth status` loggedIn=true).

## The escalation fix (p2 — PASS)

Each escalation cell ran in a fresh worktree checked out at the escaped-defect commit, with the
pinned goal **"fix the inherited codebase so its tests pass"** (goal SHA256
`1ec5e625334b47db5bfcb752fda783a457d5c69bfceed196ba1a3d7033b74007`) as a minimal
implement+test workflow with the `--change-analysis` seam. No extra hints.

| cell | escalation model | backend | fix cost | duration | final commit | tests | defect fixed |
|---|---|---|---|---|---|---|---|
| `cap_esc_sol_efe33b6` | openai/gpt-5.6-sol | opencode | **$0.102619** | 30.2s | `45b11f7` | 3/3 | yes (`elif 10 < value < 20` → `elif value < 20`) |
| `cap_esc_sonnet_efe33b6` | anthropic/claude-sonnet-5 | claude_cli | **$0.111982** | 15.3s | `f44aa04` | 3/3 | yes (identical one-line boundary fix) |

Both fixes are a single `calc.py | 2 +-` change to `classify`; `test_calc.py` is untouched
(no test weakening). Both phase ledgers are committed with re-verifiable SHA256s. A transient
harness error (claude CLI not on PATH, `exit_code=-2`, $0, no commit) was removed from the
corpus and is disclosed in the adversary review. Both cells ran — no tier is flagged not-run,
none estimated.

## The measured E_x (p3 — PASS)

**E_x = escalation_fix_cost_usd / original_cell_cost_usd**, both MEASURED:

| model | fix cost | original cell cost | **E_x** |
|---|---|---|---|
| openai/gpt-5.6-sol | $0.102619 | $0.008949 | **11.4671** |
| anthropic/claude-sonnet-5 | $0.111982 | $0.008949 | **12.5134** |

Base downstream defect cost re-derived from the rerun3 score JSON: `0.112588 / 28.0 = $0.004021`.

## The loss table at the measured values vs 3.1 vs 28

| E_x | baseline arm loss | gate arm value | swing | source |
|---|---|---|---|---|
| 3.1 | +$0.012465 | −$0.012465 | $0.024930 | measured escalation figure (handoff corpus) |
| **11.4671** | +$0.046109 | −$0.046109 | **$0.092218** | **MEASURED — openai/gpt-5.6-sol fix** |
| **12.5134** | +$0.050316 | −$0.050316 | **$0.100632** | **MEASURED — anthropic/claude-sonnet-5 fix** |
| 28.0 | +$0.112588 | −$0.112588 | $0.225176 | pricing ratio DeepSeek → GPT-5.6 (site economics) |

All four columns share the same base defect cost ($0.004021); only the multiplier differs.

## Resulting statement for the rerun3 asymmetric-loss conclusion

The measured E_x values (11.47 sol, 12.51 sonnet) sit **between** the two sourced multipliers
and are remarkably close to each other across two independent providers/backends. Both are far
above the ~1.42 break-even, so:

- **Direction — ROBUST.** At the measured E_x the gate arm is still ahead on the loss axis; the
  break-even (~1.42) is far below both measured values. The rerun3 control conclusion's
  direction holds with measured dollars.
- **Magnitude — ~10x smaller than the E_x=28 sourced figure, ~4x larger than the 3.1 figure.**
  The sourced 28 (DeepSeek → GPT-5.6 pricing ratio) materially overstates the downstream cost of
  this escaped defect; the measured escalation path costs ~11.5–12.5x the original cell, a swing
  of ~$0.09–$0.10 rather than the sourced $0.225. The handoff 3.1 figure understates it by ~4x.

**Limitations (recorded, not cleared):** n=1 per escalation model (descriptive, no CI); the
`raw_prompt_hash` field is empty in the phase ledgers so the session prompt is reconstructed from
the immutable spec (low residual risk); the escalation path is inherently the expensive-model
path (there is no DeepSeek floor by design).

**Verdict: PASS.** The escalation multiplier E_x is now MEASURED (11.47 sol / 12.51 sonnet) in
dollars, the loss table is recomputed at the measured values alongside the sourced 3.1 and 28,
and the rerun3 asymmetric-loss direction is confirmed robust with measured dollars. No gate is
cleared; the corrected E_x range (~11.5–12.5) is the campaign's information output.
