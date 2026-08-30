---
status: accepted
---

# retry-worthiness — known-safe attacks

**Role:** adversarial verifier (p4). **Source revision:** `workflows/repository/retry_observational_analysis.yaml`
SHA256 `b07d86d7cac1a5cbab0db5b67e35085a02f5ee58d628b8ef0fccfdf105b12b9b`.

This companion file records the non-falsifying attacks attempted — what was tried, the raw
evidence, and why each did not falsify the findings. The one genuine discrepancy found (a
line-number precision note) is carried here rather than suppressed.

## Attempted attacks and why they did not falsify

### A1. "The rescue rate 1/1 is a fabricated numerator" — not supported
- **Tried:** re-deriving the rescue count from `cap_grit_grid_ledger.json` `cells[].attempts`
  directly, ignoring p1's chains.json.
- **Evidence:** exactly one row has `attempt_number=2`; its `test_executed_success=True`,
  `retry_reason="first_attempt_test_failure"`, `parent_attempt_id` = that cell's a1. 1/1.
- **Why safe:** the numerator and denominator both trace to ledger rows; no imputation.

### A2. "WOC 0.8889 overstates/understates the framework correction" — not supported
- **Tried:** recomputing WOC under three denominators (cells=8, attempts=9, plane=11) and the
  story corpus (r=0).
- **Evidence:** 1/1.125=0.8889, 1/1.0909=0.9167, 1/1.0=1.0 — the findings report all three and
  label the E4 figure as the retry-armed plane.
- **Why safe:** the findings do not pick a single "the" r; they report the denominators and flag
  the 0.125-vs-0.115 match as coincidental (n=8, retry deliberately armed).

### A3. "Break-even E_x = 792× is inflated by a wrong base defect cost" — not supported
- **Tried:** recomputing `0.004021` from the escalation score's own derivation string
  (`0.112588 / 28.0`) and from the `base_downstream_defect_cost_usd` field.
- **Evidence:** both give 0.004021; `3.1865708 / 0.004021 = 792.48`.
- **Why safe:** the base is the escalation score's top-level field, and the arithmetic is exact.

### A4. "The confidence 0.8462 is misattributed to the retried failure" — not supported
- **Tried:** reading the raw story sessions for the retried cell's first attempt
  (`…_bad_seed_7b38e1d32d59.json`) and the no-retry cell (`…_clean_c0e0d6871f69.json`).
- **Evidence:** session confidences [0.875, 0.65, 0.8667, 0.8125, **0.8462**] and
  [0.9, 0.7, 0.8947, 0.75, **0.8049**] respectively — the final-session values the findings quote.
- **Why safe:** the join is to the correct `result_path`, and the final-session rule is the
  right "known at failure" signal (the story's test outcome is evaluated after session 5).

### A5. "The coverage counts (2/2, 2/11, 255/120/24) are wrong" — not supported
- **Tried:** recounting attempts, failed-first, retries, and the story corpus from the filesystem.
- **Evidence:** 9 E4 + 2 probe = 11 attempt records; 2 failed-first; 1 retry; 255 story files,
  120 wired, 24 wired-failed, 0 with retry linkage.
- **Why safe:** every count re-derives exactly; the "0 retry linkage" on the story corpus is
  the load-bearing coverage caveat, and it is stated, not hidden.

### A6. "A controlled/causal claim is hiding in the prose" — not supported
- **Tried:** grepping for `caused|causes|led to|improve|reduce|randomiz|assign|treat|we ran`.
- **Evidence:** the only hits are (a) the attributed 2c quote "no confidence threshold improves
  value" and (b) interpretive "because" clauses about *why the campaign was parked*, not about
  the retry's effect.
- **Why safe:** the findings repeatedly assert the observational frame and the correlation-only
  status; the one use of "causal" describes the stimulus feature, not the retry outcome.

### A7. "The framework `C_job` equation is misquoted" — not supported
- **Tried:** diffing the findings' §4 against `docs/reviews/workflow_metrics_findings.md:102`.
- **Evidence:** byte-for-byte `WOC = 1/(1+r)`, `C_job = C₀·EPM·(1−b·0.5)·(1+r·E_x)`.
- **Why safe:** the framework correction quotes the pinned equation, not a paraphrase.

## The one discrepancy (carried, not suppressed)

- **opencode.py line number.** The findings cite `opencode.py:113`; the `confidence` property is
  at `:119`. Inherited from the grit design's §1.3 (already flagged in
  `docs/verification/cap_grit_calibration_verification.md`). The field and definition resolve;
  only the line number is six off. Does not affect any substantive claim.
