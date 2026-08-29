---
status: accepted
---

# qualitative_routing_findings — known-safe list (p3)

**Target:** `docs/reviews/qualitative_routing_findings.md` (p2). Every item below was verified
mechanically during the adversarial review (`docs/reviews/qualitative_routing_findings_adversary.md`).
Nothing here is assumed. The adversary's verdict is **PASS** — no FAILED finding — so this list is
the complete set of non-falsifying checks plus the four recorded observations (O1–O4).

| # | attempted attack | evidence | why safe |
|---|---|---|---|
| K1 | **Fabricated F1** (claim a non-flash reviewer exists) | every commit review's `reviewer_model` across all 410 files = `deepseek/deepseek-v4-flash` (2014/2014); `scripts/review_all.py:35` hard-codes it | the single-reviewer finding is measured, not asserted |
| K2 | **Fabricated F2** (wrong sonnet numbers) | sonnet `mean_architectural_fit` 0.8303, `mean_convention_adherence` 0.7694, `debt_rate` 0.3348, `better_or_worse.worse` 9 — all equal the findings' 0.830 / 0.769 / 0.335 / 9 | sonnet's texture is cited exactly |
| K3 | **Fabricated F3** (wrong correlations) | `correlations.score_vs_outcome` = archfit vs all −0.4615 (n=321), vs test −0.5893 (n=233), conven vs all −0.4133, vs test −0.5095 — all equal the findings | the correlation numbers are computed, not invented |
| K4 | **Fabricated F4** (wrong theme ranges) | problem-theme counts: tests 167–345, hygiene 97–282, wrong-approach 2–14; condition wrong-approach rate clean 0.0251 / bad_seed 0.0308 / early_degrade 0.0346 | the edge-failure texture is cited exactly |
| K5 | **Inflated coverage** (claim some model is reviewed when it isn't) | every one of the 321 story files has a flash review; coverage table uncovered = 0 for all 7 models | the "0 uncovered" claim is real |
| K6 | **A model below the n ≥ 10 floor hiding in a claim** | smallest model = sol at 184 commit reviews | no model is "insufficiently covered"; the floor does not bind |
| K7 | **Mis-quoted theme patterns (a hidden methodology)** | the findings' §1.3 was diffed against the script's `THEME_PATTERNS` by importing the module: 0 patterns missing, all 7 themes verbatim | the methodology is quoted, not paraphrased |
| K8 | **Hidden reviewer bias** | the findings' §1.2 discloses the subject-model join and labels flash's own 197 as self-review | the bias is weighted, not swept |
| K9 | **A routing recommendation beyond the evidence** | `recommend_route` reads only cost/correctness (no review corpus); the posture is KEEP ×3 / GATE ×2 / SHIFT ×0, every GATE a guard against change | no model is moved off its route; the status quo is the baseline |
| K10 | **Contradicting the quantitative walls** | findings cite 2c NON-INFERIOR + 2d/2e/2f REFUTE (capture 1/3 < 2/3, flag-cost ceiling vacuous, $0.000634) matching the campaign docs, and propose no re-opening | the abstention walls stand |
| K11 | **Non-reproducible computation** | re-ran `compute_qualitative_routing.py`; output value-identical to the committed JSON (modulo `generated_at`) | the cited numbers reproduce |
| K12 | **Wrong coverage-tail arithmetic** | 88 unanalyzed = haiku 34 + sonnet 16 + terra 10 + luna 10 + flash 9 + sol 7 + pro 2 = 88 | the tail is stated exactly |
| K13 | **Wrong '?'-file identity** | `reviews_blind/review_3d249683eef3.json` + `review_b366ecdc6f88.json` are the only two blind files with an absent `model` field, both luna | the '?' files are named correctly |

## Non-falsifying observations (recorded, not findings)

- **O1 — 10 orphan analysis files unlisted.** The "honest limits" tail names 88 unanalyzed
  stories, 18 orphan reviews, 2 '?' files, and 69 blind reviews but omits the 10 orphan analysis
  files (analyses whose story result was removed). This is why the test-success correlation runs at
  n=233 rather than 243. No coverage-table number or finding depends on it.
- **O2 — frontier figure attributed to the family.** "≤ $0.17/story, ≥ 96.8%" is the
  flash → luna → pro family frontier (caveat), not flash alone. The "cheapest default = flash"
  framing stands.
- **O3 — "pro (highest-correctness)" is a loose label.** The router's escalation is per-task
  `best_correctness_model`; "pro" is the operator's escalation pattern. KEEP is unchanged.
- **O4 — value-identical, not byte-identical, JSON.** `generated_at` is wall-clock and `Counter`
  dicts serialize with non-deterministic key order; the reproducibility contract (headline numbers)
  is met value-wise.

## Conclusion

Every checked dimension is safe: the citations resolve exactly, the methodology is disclosed and
quoted, the coverage floors hold, the routing is scoped to the evidence with the status quo as
baseline, the quantitative walls are respected, and the computation reproduces. The four
observations are incompleteness/imprecision notes for the record; none falsifies a finding.

**LOG:** 13/13 known-safe checks PASS; 4 observations recorded. **PASS.**
