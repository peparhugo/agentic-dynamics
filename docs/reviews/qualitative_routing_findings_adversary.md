---
status: accepted
---

# qualitative_routing_findings — adversarial review (p3)

**Target:** `docs/reviews/qualitative_routing_findings.md` (p2, committed `166382555`).
**Computation under review:** `scripts/archive/compute_qualitative_routing.py` →
`experiments/results/qualitative_routing/qualitative_routing_compute.json` (p1, committed `7e4b5c610`).
**Attacker role:** adversarial verifier, attacking in the pre-registered order — citation honesty,
methodology honesty, coverage honesty, routing scoping, the quantitative walls, reproducibility.

**Verdict: PASS — no FAILED finding.** Four non-falsifying observations are recorded (O1–O4)
below; none changes a headline number or a routing recommendation.

---

## Attack 1 — Citation honesty (every finding's citations resolve)

**Attack:** do the four findings' cited fields exist in the committed computation, and do the
cited values match exactly?

**Evidence** (re-read `qualitative_routing_compute.json` programmatically):

| claim in findings | computed value | match |
|---|---|---|
| F1: `profiles.*.reviewer_models` all `{flash: n}` | flash 197 / pro 421 / luna 387 / sol 184 / terra 200 / haiku 305 / sonnet 230 | **PASS** |
| F1: `methodology.subject_model_join` present | present | **PASS** |
| F2: sonnet archfit 0.830 | 0.8303 | **PASS** |
| F2: sonnet conven 0.769 | 0.7694 | **PASS** |
| F2: sonnet debt 0.335 | 0.3348 | **PASS** |
| F2: sonnet worse 9 | 9 | **PASS** |
| F3: archfit vs all r −0.4615 (n=321) | r=−0.4615, n=321 | **PASS** |
| F3: archfit vs test r −0.5893 (n=233) | r=−0.5893, n=233 | **PASS** |
| F3: conven vs all r −0.4133 | r=−0.4133 | **PASS** |
| F3: conven vs test r −0.5095 | r=−0.5095 | **PASS** |
| F4: tests range 167–345 | 167–345 | **PASS** |
| F4: hygiene range 97–282 | 97–282 | **PASS** |
| F4: wrong-approach range 2–14 | 2–14 | **PASS** |
| F4: wrong-approach rate 2.5% / 3.1% / 3.5% | clean 0.0251 / bad_seed 0.0308 / early_degrade 0.0346 | **PASS** |
| coverage table (all 7 rows) | 40|31|40|0 … 44|28|44|0 | **PASS** |
| corpus: 321 / 243 / 339 / 69 / 2 / 18 / 2014 | identical | **PASS** |

**Result:** every cited field resolves to a real corpus row and the values are exact. **PASS.**

## Attack 2 — Methodology honesty (patterns quoted, bias weighted)

**Attack:** is the theme-matching methodology disclosed and quoted verbatim? Is the reviewer bias
weighted, not hidden?

**Evidence:**
- The findings' §1.3 table was diffed against the script's `THEME_PATTERNS` (imported the module
  and checked every regex string): **0 patterns missing** — all seven themes and every keyword are
  quoted verbatim.
- The limits are disclosed: keyword false positives/negatives ("heuristic, not taxonomy"),
  non-exclusive multi-theme matches, and the blind-reviews' string-vs-dict problem shape.
- The reviewer bias is weighted, not hidden: `scripts/review_all.py:35` is
  `MODEL = "deepseek/deepseek-v4-flash"`, and the corpus confirms **2014/2014** commit reviews
  carry `reviewer_model == "deepseek/deepseek-v4-flash"` — the findings' §1.2 states exactly this
  and labels flash's own 197 as self-review.

**Result:** the methodology is disclosed and the bias is weighted. **PASS.**

## Attack 3 — Coverage honesty (floors respected, the 13 + '?' files bound claims)

**Attack:** do the per-model claims respect n ≥ 10? Is the "13 uncovered" reconciliation honest?
Do the '?' files bound the claims?

**Evidence:**
- Smallest model by commit reviews is `openai/gpt-5.6-sol` at **184** — every model clears the
  n ≥ 10 floor; the findings state the floor "does not bind".
- The "13 uncovered does not reproduce" claim is **correct**: every one of the 321 story files has
  a flash review; p1's coverage table is 0 uncovered for all 7 models.
- The 2 '?'-model files (`reviews_blind/review_3d249683eef3.json`, `review_b366ecdc6f88.json`,
  both luna) are named exactly, and the 18 orphan reviews are listed.
- The 88-unanalyzed breakdown is correct: haiku 34 + sonnet 16 + terra 10 + luna 10 + flash 9 +
  sol 7 + pro 2 = 88.

**Observation O1 (non-falsifying):** the "honest limits" coverage-tail list omits the **10 orphan
analysis files** (`analysis_<id>.json` whose story result was removed — e.g. `4e7abddc43f1`,
`5b87673f0d7a`, both `static_site_gen`). This is the symmetric counterpart of the 18 orphan
reviews and is the reason the test-executed-success correlation runs at n=233 rather than 243. It
does not change any per-model coverage number (the coverage table's `analyzed` column counts only
stories that exist in the story corpus) and no finding depends on the omitted count.

**Result:** floors respected, the coverage tail bounds the claims; O1 is an incompleteness, not a
mis-citation. **PASS.**

## Attack 4 — Routing scoping (evidence-grounded, status quo the baseline)

**Attack:** are the keep/shift/gate recommendations grounded in the qualitative evidence, with the
status quo as baseline, and no recommendation beyond the evidence?

**Evidence:**
- The status-quo claim is accurate: `agentic_dynamics/control/routing.py:recommend_route`
  consumes only `model`/`correctness`/`cost` entries and never reads the review corpus — the
  qualitative signal is complementary by construction.
- The posture is conservative (KEEP ×3, GATE ×2, SHIFT ×0) and every GATE is a *guard against a
  change*, not a new move. No model is moved off its current route.

**Observation O2 (non-falsifying):** the "volume cells" row cites "flash default (… ≤ $0.17/story,
≥ 96.8%)". The caveat's exact wording
(`docs/reviews/cross_models_mixed_effect_caveat.md:28`) is that the **flash → luna → pro family**
sits at ≤ $0.17/story and ≥ 96.8% — flash is the cheapest end of that frontier, not the sole owner
of both figures. The "cheapest-qualified default = flash" framing is still correct.

**Observation O3 (non-falsifying):** the "frontier reasoning" row labels the escalation target
"pro (highest-correctness)". The router's escalation is per-task `best_correctness_model` (not
uniformly pro); "pro" is the operator's escalation pattern (the workflow's own `run_shape`). The
label is loose but the KEEP recommendation is unchanged by it.

**Result:** recommendations are evidence-grounded and scoped; O2/O3 are label imprecisions, not
evidence gaps. **PASS.**

## Attack 5 — The quantitative walls (2c/2d/2e/2f respected)

**Attack:** does the findings doc contradict the campaigns' verdicts?

**Evidence:**
- The findings characterize **2c NON-INFERIOR** ("the informational boundary") and
  **2d / 2e / 2f REFUTE** (capture 1/3 < 2/3, flag-cost ceiling vacuous, flag-cost $0.000634) —
  matching `docs/reviews/cap_adaptive_2c_known_safe.md` ("NON-INFERIOR; abstention: no improving
  threshold") and the 2d/2e/2f known-safe docs.
- The findings state the walls "stand and are not re-opened here" and propose no re-opening: no
  finding or recommendation touches the abstention rule.

**Result:** no contradiction; the walls stand. **PASS.**

## Attack 6 — Reproducibility (re-run reproduces the cited numbers)

**Attack:** re-run the committed script over the corpus and compare the headline numbers.

**Evidence:** `python3 scripts/archive/compute_qualitative_routing.py` re-ran clean. The re-run
output was compared value-wise to the committed JSON (after dropping the `generated_at` field):
**identical** — per-model profiles, coverage table, correlations, corpus counts all reproduce.

**Observation O4 (non-falsifying):** the JSON is value-identical but not byte-identical across
runs — `generated_at` is wall-clock, and the `problem_themes`/`better_or_worse` dicts serialize
with non-deterministic key order (Python `Counter` insertion order). The reproducibility contract
("compare at least the headline numbers") is met value-wise; a byte-for-byte diff would need a
sort-keys/stable-timestamp flag, which the script does not apply.

**Result:** the computation reproduces the cited numbers. **PASS.**

---

## Verdict

All six attacks pass. **No FAILED finding.** The findings doc is honest on citations, methodology,
coverage, routing scoping, and the quantitative walls, and its numbers reproduce from the
committed script. Four non-falsifying observations (O1–O4) are recorded for the record; they are
incompleteness/imprecision notes, not falsifications.
