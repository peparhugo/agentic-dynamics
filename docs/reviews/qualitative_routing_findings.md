---
status: accepted
---

# qualitative_routing_findings — what the review corpus says about routing

**Workflow:** `qualitative_routing_analysis` (spec `workflows/repository/qualitative_routing_analysis.yaml@0.1`) · **Phase:** p2 (findings) ·
**Input:** `experiments/results/qualitative_routing/qualitative_routing_compute.json` (p1's committed computation) ·
**Date:** 2026-08-29

This doc turns p1's computed per-model qualitative profiles into routing findings. It cites p1's
numbers only — the computation is `scripts/archive/compute_qualitative_routing.py`, re-runnable and
committed alongside its output. **The findings are the deliverable; no routing-code change is made
here — the code follows only after the operator's sign-off.**

Provenance tags follow the repo convention: **[M]** measured field, **[C]** computed (by p1's
script), **[H]** heuristic (the keyword theme-matching), **[P]** policy/prior (the quantitative
campaign verdicts + the status-quo router).

---

## 1. Methodology (disclosed)

### 1.1 The corpus

| surface | files | what it carries |
|---|---|---|
| `experiments/results/reviews/review_*.json` | 339 | flash-authored commit reviews (problems/strengths/summary + numeric texture) |
| `experiments/results/reviews_blind/*.json` | 71 | blind reviews — 69 with `model: "unknown"`, 2 with `model` absent (the **'?'-model files**) |
| `experiments/results/analysis/analysis_*.json` | 243 | per-story post-hoc analysis (solution tests_passed/total, correctness) |
| `experiments/results/stories/**/*.json` | 321 | story results (subject `model`, `perturbation_condition`, `summary.all_successful`) |

Total commit reviews: **2,014** across 410 review files [C].

### 1.2 The subject-model join (the load-bearing semantic)

The review file's top-level `model` field is the **reviewer**, not the subject.
`scripts/review_all.py` hard-codes `MODEL = "deepseek/deepseek-v4-flash"` and writes it into every
review file. The model whose work is actually reviewed is recovered by joining `review.story_id →
story.model` (p1's `subject_model_join`). **Every** commit review in the corpus carries
`reviewer_model == "deepseek/deepseek-v4-flash"` [M] — so:

> **The "per-model profile" is flash's assessment of each model. For flash itself it is
> self-review.** This is the reviewer-model bias, and it weights every number below.

### 1.3 The theme-matching patterns (quoted from p1's script)

Theme counts are keyword matches over the problems' text (category + description for the flash
reviews' dict problems; the raw string for the blind reviews' string problems), case-insensitive
substring regex. A problem may match several themes, so per-theme rates are **non-exclusive** and
must not be summed. The patterns, verbatim [C]:

| theme | patterns (regex, case-insensitive) |
|---|---|
| hygiene/cleanup | `\.gitignore`, `node_modules`, `\bdist\b`, `cleanup`, `hygiene`, `unused`, `dead code`, `duplication`, `duplicated`, `smell`, `deprecated`, `lockfile`, `committed\b`, `leftover`, `stale` |
| scope | `scope creep`, `out of scope`, `beyond the scope`, `scope`, `greenfield`, `wholesale`, `unrelated`, `throwaway`, `dead-end`, `rewrite`, `bloat` |
| no-op | `no changes`, `no-op`, `noop`, `empty commit`, `nothing changed`, `does nothing`, `no effect` |
| timeout | `timeout`, `timed out`, `hang`, `stall`, `deadlock`, `blocking the event loop` |
| spec-drift | `off-spec`, `spec drift`, `drift`, `deviate`, `does not match the spec`, `missing requirement`, `not in the spec`, `contradicts the spec`, `unrequested`, `requirement\b` |
| tests | `test`, `coverage`, `untested`, `pytest`, `jest`, `assertion`, `no test`, `test suite` |
| wrong-approach | `wrong approach`, `wrong-approach`, `incorrect approach`, `misguided`, `misconceiv`, `should instead`, `rethink`, `replaced the`, `discards the`, `wholesale-replaced`, `anti-pattern`, `mis-`, `misapply` |

**Disclosed limits of the matching [H]:** keyword substring matching has false positives (e.g.
`scope` in "scoped") and false negatives (unanticipated reviewer phrasing) — these are heuristic
buckets over free text, not a taxonomy. `wrong-approach` overlaps `scope` (a wholesale rewrite is
both), so the rates are intentionally non-exclusive.

### 1.4 The numeric fields' semantics [M]

`architectural_fit`, `convention_adherence` ∈ [0,1] — flash's per-commit scores; means are over
the available values (never a missing-as-zero). `introduces_technical_debt` is a boolean; the debt
**rate** is `P(debt=true)` over a model's commit reviews. `better_or_worse` ∈
{better, neutral, worse, unclear}.

### 1.5 Coverage floors

A **profile claim** requires **n ≥ 10 commit reviews**; below that a model is "insufficiently
covered". On the current corpus no canonical model is below the floor — the smallest is
`openai/gpt-5.6-sol` at **184** commit reviews [C]. The floor therefore does not bind; the binding
limits are the single-reviewer bias (§1.2) and the outcome caveat (§4), not the counts.

---

## 2. Per-model qualitative profiles

All numbers are p1's `profiles.*` [C]. Reviewer is `deepseek/deepseek-v4-flash` for every row.

| subject model | files | commit reviews | archfit | conven | debt | better | worse | worse% |
|---|---|---|---|---|---|---|---|---|
| deepseek/deepseek-v4-flash | 40 | 197 | 0.760 | 0.688 | 0.579 | 138 | 19 | 9.6% |
| deepseek/deepseek-v4-pro | 88 | 421 | 0.747 | 0.713 | 0.689 | 283 | 49 | 11.6% |
| openai/gpt-5.6-luna | 80 | 387 | 0.758 | 0.723 | 0.651 | 284 | 35 | 9.0% |
| openai/gpt-5.6-sol | 37 | 184 | 0.736 | 0.678 | 0.592 | 134 | 17 | 9.2% |
| openai/gpt-5.6-terra | 40 | 200 | 0.747 | 0.694 | 0.600 | 145 | 20 | 10.0% |
| anthropic/claude-haiku-4-5 | 61 | 305 | 0.765 | 0.748 | 0.603 | 152 | 36 | 11.8% |
| anthropic/claude-sonnet-5 | 46 | 230 | **0.830** | **0.769** | **0.335** | 155 | **9** | **3.9%** |

**Coverage** (stories | analyzed | reviewed | uncovered) [C] — every model is reviewed (flash
reviewed all 321 stories); the tail is on the *analysis* side, not the review side:

| subject model | stories | analyzed | reviewed | uncovered |
|---|---|---|---|---|
| flash | 40 | 31 | 40 | 0 |
| pro | 53 | 51 | 53 | 0 |
| luna | 46 | 36 | 46 | 0 |
| sol | 37 | 30 | 37 | 0 |
| terra | 40 | 30 | 40 | 0 |
| haiku | 61 | 27 | 61 | 0 |
| sonnet | 44 | 28 | 44 | 0 |

**Problem-theme distribution** (top themes per model; counts are non-exclusive problem matches) [C]:

| subject model | tests | hygiene/cleanup | timeout | scope | spec-drift | wrong-approach | no-op |
|---|---|---|---|---|---|---|---|
| flash | 242 | 134 | 52 | 54 | 19 | 14 | 2 |
| pro | 345 | 282 | 120 | 65 | 26 | **5** | 13 |
| luna | 259 | 188 | 114 | 42 | 30 | 11 | 9 |
| sol | 167 | 99 | 62 | 58 | 16 | 8 | 6 |
| terra | 180 | 133 | 72 | 50 | 17 | 13 | 8 |
| haiku | 299 | 238 | 114 | 75 | 27 | 8 | 14 |
| sonnet | 181 | 97 | 68 | 40 | 21 | **2** | 3 |

**Strengths themes** are dominated by `tests` and `hygiene/cleanup` for every model (e.g. flash:
tests 156, hygiene 127) [C]. The **summary-text sample-read** (`top_summaries.*`) is nearly uniform
across models — flash's story-review voice describing "textbook-coherent / quality-rising /
greenfield → … → cross-cutting" arcs with "the sole material cost being …" — i.e. a
correctness-praise floor, not a per-model discriminator.

---

## 3. Routing implications (scoped to the evidence)

The status quo router (`agentic_dynamics/control/routing.py:recommend_route`) consumes only the
quantitative entries (cost + correctness) and recommends a cheapest-qualified default + an
escalate target. It does **not** read the review corpus. The qualitative signal is therefore
complementary, and the quantitative walls — **2c NON-INFERIOR** (the informational boundary) and
**2d / 2e / 2f REFUTE** (the abstention walls: capture 1/3 < 2/3, flag-cost ceiling vacuous,
flag-cost $0.000634) [P] — stand and are not re-opened here. The status quo is the baseline in
every row.

| task type | status quo baseline | qualitative texture supports | verdict |
|---|---|---|---|
| **volume cells** (high-volume story cells) | flash default (cheapest-qualified on the cost-per-success frontier: ≤ $0.17/story, ≥ 96.8% [M]) | flash's profile is mid-pack (archfit 0.760, debt 0.579); its failures are hygiene/tests-heavy with wrong-approach a minority (14 theme matches across 197 commit reviews). No qualitative reason to leave the quantitative default. | **KEEP flash** |
| **frontier reasoning** (escalation target) | pro (highest-correctness) | pro is the most-reviewed (421) and has the lowest wrong-approach count (5 theme matches across 421 commit reviews) — the most "conventional" reasoner in flash's eyes. No signal to demote it. | **KEEP pro** |
| **the review layer** (commit/story review — today 100% flash) | not a routing input (flash reviews everything, human-facing) | the review layer's numeric scores do **not** track the outcome (§4, F3): archfit vs `all_successful` r = −0.46. Its scores must not be wired into the router as a correctness proxy. | **GATE** (hold; do not feed review scores into routing) |
| **wrapper phases** (interpretation-heavy workflow phases) | pro (this workflow's own run_shape) | the multi-session story corpus does not cover wrapper phases — no qualitative evidence exists. | **KEEP pro** |
| **sonnet** (cross-cutting) | held — no policy consumes sonnet until a clean re-run (caveat) | sonnet has the cleanest flash-scored texture (archfit 0.830, debt 0.335) *when it completes*, but its completion is unmeasured (session-limit deaths). | **GATE** (hold, pending the clean re-run) |

**Net posture: KEEP ×3, GATE ×2, SHIFT ×0.** The qualitative corpus does not justify moving any
model off its current route. The two gates are "don't wire review scores into routing" (a guard
against a plausible but unsupported change) and "keep sonnet held" (already the status quo).

---

## 4. Honest limits (each stated where it bounds a claim)

1. **The single-reviewer bias.** All 2,014 commit reviews are flash-authored [M]; flash's own
   profile is self-review. Every cross-model comparison in §2 is therefore *flash's view*, not an
   independent measurement. This bounds F1–F4: the profiles are reliable as "flash's reading", not
   as ground truth.
2. **The "13 uncovered" does not reproduce — the coverage tail is different from stated.** The
   provisional current-state said "13 old '?'-model stories lack reviews". p1 finds **0** stories
   lacking a review (all 321 stories have a flash review) [C]. The real coverage tail is instead:
   **88 stories without an analysis file** (haiku 34, sonnet 16, terra 10, luna 10, flash 9,
   sol 7, pro 2), **18 orphan reviews** (review files whose story result was removed, all trivially
   "neutral / 1.0 / no problems"), **2 '?'-model files** (`reviews_blind/review_3d249683eef3.json`,
   `reviews_blind/review_b366ecdc6f88.json` — both luna), and **69 blind "unknown" reviews**. The
   comparison is one-sided, but it is not missing reviews.
3. **The mixed-effect caveat bounds F2 and the sign of F3.** `claude-haiku-4-5` / `claude-sonnet-5`
   per-condition outcomes confound capability with CLI/backend timeouts
   (`docs/reviews/cross_models_mixed_effect_caveat.md` [H]); sonnet's re-measurement died at the
   session limit. sonnet's high archfit / low debt is therefore a *conditional* ("clean when it
   completes"), and the negative review-score↔outcome correlation (F3) is partly inflated by the
   caveated Claude runs. No per-condition mechanism is claimed for the Claude pair.
4. **The theme matching is heuristic [H]** (§1.3) — false positives/negatives are possible; the
   "tests"/"hygiene" dominance (F4) is a directional texture, not a precise taxonomy.
5. **Wrapper phases are outside the corpus.** No routing claim about wrapper phases rests on the
   qualitative corpus; that row is KEEP by absence of evidence, not by positive support.

---

## 5. Findings summary

**F1 — the review corpus is a single model's monologue (self-review for flash).**
All 2,014 commit reviews carry `reviewer_model = "deepseek/deepseek-v4-flash"` [M]; the review
file's `model` field is the reviewer, not the subject (p1's `subject_model_join`). For flash's own
197 commit reviews this is self-review. *Cited:* `qualitative_routing_compute.json` →
`profiles.*.reviewer_models` (each `{deepseek/deepseek-v4-flash: n}`), `methodology.subject_model_join`.

**F2 — sonnet-5 has the cleanest flash-scored code *when it completes*, but its completion is
unmeasured.** sonnet: archfit 0.830 (max), conven 0.769 (max), debt 0.335 (min, roughly half every
other model's), worse-rate 3.9% (min) [C] — bounded by the caveat (CLI timeouts; re-measurement
died at the session limit). *Cited:* `profiles.anthropic/claude-sonnet-5.*`,
`docs/reviews/cross_models_mixed_effect_caveat.md`.

**F3 — the review layer's numeric scores do not track the outcome the router cares about.**
`mean_architectural_fit` vs `all_successful` r = −0.4615 (n=321); vs `test_executed_success`
r = −0.5893 (n=233); `mean_convention_adherence` vs `all_successful` r = −0.4133, vs
`test_executed_success` r = −0.5095 [C]. A higher flash score predicts *lower* success — the sign
is partly the caveated Claude runs (high score, low completion), so the practical reading is "the
review score is not a correctness proxy", not "flash inverts the truth". *Cited:*
`correlations.score_vs_outcome.*`.

**F4 — the models fail on the edges (untested changes + repo hygiene), not on wrong approaches.**
Across all 7 models the problem themes are dominated by `tests` (167–345 matches) and
`hygiene/cleanup` (97–282); `wrong-approach` is a small minority (2–14 matches; the per-condition
wrong-approach rate is 2.5% clean / 3.1% bad_seed / 3.5% early_degrade [C]). The failures are
measurable hygiene and coverage gaps, not "the model solved the wrong problem". *Cited:*
`profiles.*.problem_themes`, `correlations.condition_rates.*`.

### Recommended routing posture

KEEP flash for volume cells; KEEP pro for frontier reasoning and wrapper phases; GATE the review
layer (do not wire its scores into the router); GATE sonnet (hold pending the clean re-run).
No code change is made here.

### What measurement would firm each finding

- **F1/F3** — one independent (non-flash) review pass over a sample of flash *and* peer stories
  would turn "flash's monologue" into a two-reviewer comparison and would separate the review-score
  signal from the reviewer identity. This is the single highest-value next measurement.
- **F2** — the already-mandated clean sonnet re-run (post session-limit) turns sonnet's conditional
  ceiling into a measured rate.
- **F4** — a per-commit `test_executed_success`/`hygiene` join (review problem → the story's own
  test pass) would confirm whether the "tests/hygiene" edge failures are outcome-relevant or merely
  cosmetic.

---

*This doc is the deliverable; the routing code is unchanged pending operator sign-off.*
