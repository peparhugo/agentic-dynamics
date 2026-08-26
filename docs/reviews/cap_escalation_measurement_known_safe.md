---
status: accepted
---

# cap_escalation_measurement — known-safe attacks

**Role:** adversarial verifier (p4). **Source revision:** `bc4c2c573`.

This companion file records the non-falsifying attacks that were attempted — what was tried,
the evidence, and why each attempt did not falsify the measured E_x result.

## Attempted attacks and why they did not falsify

### A1. "The escalation session just deleted the failing test" — not supported
- **Tried:** `git diff efe33b6fb8ad… HEAD -- test_calc.py` on both escalation worktrees.
- **Evidence:** 0 lines changed in `test_calc.py` on both `45b11f7` (sol) and `f44aa04` (sonnet).
  The diff on each final commit is `calc.py | 2 +-` only — the boundary line.
- **Why safe:** the inherited test suite is byte-identical to the source commit; the tests pass
  against the corrected code rather than being weakened or removed.

### A2. "The fix hides the defect by changing a different file / a different symbol" — not supported
- **Tried:** `git diff --stat efe33b6fb8ad… HEAD` and the change-analysis seam's
  `realized_symbol_set` on both cells.
- **Evidence:** `calc.py | 2 +-` on both; the change-analysis seam recorded the neighborhood as
  `{classify}` on both cells.
- **Why safe:** the only changed symbol is `classify`, the symbol that contains the escaped
  defect; `classify(10.0)` returns `'mid-a'` on both final commits (direct-import check).

### A3. "The denominator is the forecast, inflating E_x" — not supported
- **Tried:** re-reading the denominator's provenance: the phase ledger's
  `total_measured_cost_usd` vs `forecast_cost_usd`.
- **Evidence:** `total_measured_cost_usd = 0.008949` (measured), `forecast_cost_usd = 0.017018`.
  The E_x denominator used is $0.008949 — the measured value — and its SHA256
  (`ed385510052c2867de04844b8391215a60c9bfc5702fb7da6f2d41cd62091c81`) re-verifies.
- **Why safe:** the denominator is the cell's true measured cost, matching the rerun3 score
  JSON's `cost_usd` field for the same cell ($0.008949).

### A4. "E_x was copied from a prior doc rather than computed" — not supported
- **Tried:** recomputing E_x from the two phase ledgers and the original cell ledger.
- **Evidence:** `0.102619 / 0.008949 = 11.4671`, `0.111982 / 0.008949 = 12.5134` — both computed
  here, not copied. Every number in the p3 score JSON traces to a ledger field in the
  `validation_note`.
- **Why safe:** the arithmetic is reproduced independently from the same ledger fields.

### A5. "The base defect cost was copied from the docs, so the loss table is not comparable" — not supported
- **Tried:** re-deriving the base downstream defect cost from the rerun3 score JSON's
  asymmetric_loss block instead of the supplement's printed $0.004021.
- **Evidence:** `0.11258800000000001 / 28.0 = 0.004021` — the re-derivation reproduces the docs
  value exactly, so all four loss-table columns rest on the same base.
- **Why safe:** the base is identical across the measured / 3.1 / 28 columns; only the
  multiplier differs, so the columns are comparable.

### A6. "A tier is secretly not-run but reported" — not supported
- **Tried:** checking p1 auth status and each cell's outcome record.
- **Evidence:** p1 recorded both escalation models authenticated (opencode OpenAI oauth present;
  `claude auth status` loggedIn=true). Both cells produced outcome records with a real final
  commit, `defect_fixed=true`, `tests_passing=true`, and a non-zero measured fix cost. No tier is
  flagged not-run; none is estimated.
- **Why safe:** every reported model has a real, verified run behind it.

### A7. "The session was seeded with the gate arm's fixed code" — not supported
- **Tried:** comparing the source worktree contents and the session transcripts' file reads.
- **Evidence:** both escalation worktrees were fresh clones checked out at the defect commit
  `efe33b6fb8ad`; at that commit the tree is exactly `.gitignore`, `calc.py` (with the defect),
  `test_calc.py`. The session transcripts (`session.jsonl`) open with the read of the defective
  `calc.py` and the failing pytest output.
- **Why safe:** the inherited codebase is exactly what a downstream session would receive — the
  broken code + failing tests, nothing else.

### A8. "The measured cost is a billed claim with no artifact" — not supported
- **Tried:** hashing the phase ledgers and checking the implement-phase `cost_usd` field.
- **Evidence:** both phase ledgers are committed under
  `experiments/results/cap_escalation_measurement/` with re-verifiable SHA256s
  (`76f20f34599e…` sol, `6afad2c7f07e…` sonnet); the cost is the implement phase's `cost_usd`
  measured by the run ledger (token-accounted at openai-sol / anthropic-sonnet5 pricing).
- **Why safe:** the number is a recorded, hash-bound ledger field, not a self-report.

## Result

None of the eight non-falsifying attacks landed. The measured E_x (11.47 sol / 12.51 sonnet)
and the loss-table recomputation stand.
