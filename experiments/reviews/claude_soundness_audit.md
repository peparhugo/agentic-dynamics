# Soundness Audit — AI FinOps Framework (Pre-Launch, One-Way Door Review)

**Auditor:** Claude (claude-fable-5), independent code + data + claims review
**Date:** 2026-08-09
**Scope:** `src/instrument/` (15 modules), `scripts/` (analysis pipeline), `experiments/configs/` (34), `experiments/lab_books/` (8 + README), `experiments/results/_results_summary.json`, `_trajectory_aggregate.json`, `experiments/inventory.json`, `firebase/public/` (8 pages, data.js, app.js)
**Method:** Every claim traced to its generating code and data file. Suspected code bugs verified by execution, not just inspection.

---

## Executive Summary

**Verdict: NEEDS REVISION BEFORE ANY PUBLIC CLAIM.**

The genuinely strong parts of this work — real per-session cost/token accounting from the opencode DB, a novel perturbation-robustness instrument concept, artifact bundling for verification, an honest provenance taxonomy — are being buried under a layer of claims the data cannot support. The single most dangerous problem: **the shipped dataset contains zero test executions (`test_results: None` for all 227 entries), yet the website repeatedly claims "93.2% overall test pass rate (987/1059 tests) from real pytest/jest execution — no heuristic estimation."** Every "correctness" number driving the headline conclusions is a 5-signal keyword heuristic (`solution.py:_estimate_correctness`) that awards ~0.8–1.0 to any non-trivial code. This is checkable by anyone who opens `_results_summary.json` — which ships in the repo.

There are also three verified crash bugs in the pip-installable instrument, a fabricated "Executive Dashboard," arithmetic errors in the enterprise savings tables, a wrong Anthropic cache-write price underpinning the "Cache Tax" claim, contradictory flail-rate numbers between the shipped data and the shipped prose, and lab-book "Expected Output" (pre-execution guesses) apparently published as findings.

The 69× cost gap is real as an *observed average cost ratio in this corpus* and is the defensible core of the whole project. Almost everything layered on top of it needs caveats, relabeling, or removal.

---

## 1. CLAIM VERIFICATION

Legend for my assessment: ✅ traceable and correctly tagged · ⚠️ traceable but mislabeled/miscontextualized · ❌ not supported by shipped data.

### 1.1 ❌ "Test Pass Rate 93.2% — 987/1059 tests across 203 reports" (index.html:65) / "93.2% overall test pass rate (987/1059 tests) from real pytest/jest execution — no heuristic estimation" (evidence.html:144, :231)

- `experiments/results/_results_summary.json`: **all 227 entries have `test_results: null`.** The summary was generated with `--no-tests` (or all test runs failed). Verified programmatically.
- Consequently every `correctness` field in the summary is `solution.py:_estimate_correctness` — a keyword-presence heuristic (has `def`, has `import`, contains the string "error" anywhere, has `return`, length > 200 chars → up to 1.0).
- The deployed `data.js` knows this: every model's `pass_rate` is tagged `[H]` ("92% [H]", "100% [H]"...), and `derived.overall_pass_rate` is **"90.3% [H]"**. At runtime, `app.js` will replace the hardcoded "93.2%" with "90.3% [H]" — while the static caption "987/1059 tests across 203 reports" and the sentence "no heuristic estimation" remain. The page will visibly contradict itself.
- The per-model test counts hardcoded in evidence.html:135–142 (e.g., Claude "100% (240/241)", GPT-5.6 "100% (166/166)", DeepSeek "87% (438/506)") are untraceable to any shipped artifact. If they came from an earlier tests-enabled run, that run's output is not in the repo.

**This is the #1 launch blocker.** Either re-run `analyze_worktrees.py` with tests enabled and regenerate everything, or delete every "test pass rate" claim and label correctness [H] everywhere it appears.

### 1.2 ❌ "The numbers are not estimates. They're measured." (index.html:54)

Directly contradicted by the site's own data: correctness [H], escape [H], strategy [H], energy [X] built on invented constants (see 1.9), pass rates [H]. Costs and tokens from the opencode DB are genuinely [M] — say *that*, not this.

### 1.3 ⚠️ The 69× cost gap ($0.016 vs $1.08/session)

- Traceable: `data.js` `derived.cost_gap_computation` = "$1.0847 / $0.0158 = 68.7×". Cost values come from the opencode DB (`cost > 0` sessions) — this is a real [M] measurement of *what was spent*.
- **Not controlled for task mix.** DeepSeek n=119 entries includes ~20 solo tasks Claude never ran (web_crawler, social_graph, twitter_timeline, mint_financial...). Claude n=44 skews to url_shortener/perturbation tasks. The lab books' per-task comparison shows the ratio ranges 10.5×–105.8× by task. An average across unmatched task mixes should not be presented as "identical task" (accelerator.html:209 says "Identical task. Cheapest model vs. most expensive.").
- Headline number drifts across pages: $1.08 (hero), $1.01 (index table), $1.06 (evidence), $1.0847 (data.js). Claude total spend: $47.54 (inventory, 47 sessions), $42.52 (evidence table), $42.30 (lab_task_routing). These are different frames (all sessions vs game-report subset) presented without labels.
- Verdict: **defensible as [M] "observed average per-session cost ratio in our corpus, task mix not matched"** — indefensible as "same output, 69× different cost."

### 1.4 ⚠️ "Both models produce ~11,000 generated tokens per session. Same computational effort."

- The ~11K token claim is traceable: trajectory aggregate shows Claude output 11,092; DeepSeek output 8,819 + 2,267 reasoning = 11,086. Fine as [M] for *generated* tokens.
- "Same computational effort" is contradicted by the project's **own** energy model (`efficiency.py:24` `ARCH_RATIO ≈ 13.5×` more active params per token for Claude) and ignores the input side (DeepSeek reads 223K cache tokens/session vs Claude 144K + 22.5K writes). Pick one story: either the architectures differ ~14× in per-token compute (your energy section) or they're "the same computational effort" (your homepage). Both can't be published.

### 1.5 ❌ Flail-rate table (evidence.html:112–121) and accelerator claims (accelerator.html:169, :311)

Three mutually contradictory sets of numbers are shipping simultaneously:

| Model | evidence.html static / accelerator prose | lab_flail_triggers.md **executed Results** (:87) | shipped data.js `narration_rate` |
|---|---|---|---|
| Claude | **44%** | 11.4% | 11% |
| GPT-5-mini | **58%** | 8% | 8% |
| GPT-5-nano | **100%** | 14% | 14% |
| DeepSeek | 3% | 8.4% | 8% |

The static HTML numbers match the lab book's **"Expected Output" section** (`lab_flail_triggers.md:56-61`) — the hypothesized table written *before* the analysis ran — not the executed results. Publishing pre-registered guesses as findings is the kind of error that ends credibility if a reviewer diffs the lab book against the website. The story page (story.html:106) uses a third mix: "Claude: 11%. DeepSeek: 8%. GPT-5-nano: 100%" — two executed numbers and one imagined one in the same sentence.

Additionally, the executed lab book **undercuts the causal story**: "Manifold perturbation entries had zero flail... Narration failure entries are separate from the perturbation dataset" (`lab_flail_triggers.md:96`). The site's framing — "when the model can't figure out the correct requirement, it flails" — is not what your own analysis found. Flail sessions are overwhelmingly the `unknown`-class sessions (broken/misc), not perturbation responses.

### 1.6 ❌ "Grit-routed strategy: 95% correctness at $0.12/session — 17 task types" (index.html:58, databricks.html:95)

Traceable to `lab_task_routing.md`, but this is an **in-sample simulation**: the best model per task was selected using the same data on which the strategy is then scored, per-task cells have n=1–4, and "correctness" is the keyword heuristic. There is no holdout, no actual router, no new sessions. Presenting it under "Our measurement" on databricks.html is a provenance violation — this is [H]-derived [C] at best, and overfit.

### 1.7 ❌ "On 12 of 15 overlapping tasks, the cheaper model is MORE correct" (databricks.html:79)

The lab book (`lab_claude_audit.md:89-90`) says: DeepSeek leads **7**/15, tied 5/15, Claude 3/15. 7 wins + 5 ties = 12 "not worse," not 12 "MORE correct." This overstates your own result. Also note the two lab books disagree on the hypothesis outcome for the same comparison (lab 1: "Null hypothesis: Rejected"; lab 3: "Not rejected") — the H0s are worded differently but a reviewer will read this as motivated flexibility.

### 1.8 ❌ The "Cache Tax": "Claude writes 22,500 tokens to cache per session at $15/Mtok... 100× pricing difference" (evidence.html:147, accelerator.html:278–281, framework.html:115)

- The 22.5K cache-write tokens/session is real [M] (trajectory aggregate: 22,523).
- **$15/Mtok is not Anthropic's cache-write price.** Your own `efficiency.py:44` prices Anthropic cache_write at **$3.75**/Mtok (which matches Anthropic's public 1.25× input pricing). `build_data.py:50` uses $15. Two internal price tables disagree, and the public-facing one is ~4× wrong.
- The "100×" compares Claude cache **writes** to DeepSeek cache **reads** — different operations at different providers. The honest comparisons are read-vs-read (~$3.00 vs $0.14 ≈ 21×) or write-vs-nothing.
- Related error: "Claude bills reasoning as output tokens at $10/Mtok" (evidence.html:104, :185) — your own table says Claude output is $15/Mtok; $10 is the OpenAI figure.

### 1.9 ⚠️ Energy claims ("[X] TokenPowerBench")

- `efficiency.py:30-32` uses 0.08 / 0.23 / 0.47 J/token for prompt/output/reasoning, citing "TokenPowerBench: 0.1–2.0 J/tok range." **0.08 is below the cited range's floor**, and the 2× multiplier for reasoning tokens is invented (a reasoning token is a forward pass like any other). These are [H] constants wearing an [X] tag.
- `claude_active_params: 500B — provenance "X"` (data.js:937) is not externally sourced; Anthropic has never disclosed parameter counts. This is a guess labeled as external fact, and it drives the 14× ARCH_RATIO used in bounded-energy claims.
- The IEA 1.6%/yr EPM baseline is a legitimate [X].

### 1.10 ❌ WOC = 0.90 "measured first-pass success rate" (index.html:59, databricks.html:111, accelerator.html:211)

- r = 0.115 is the **narration-failure share of game reports** (26/227), not a retry rate. No session was ever retried by a routing system. Nothing "first-pass" was measured — 88.5% of sessions produced *some* code; heuristic correctness averaged 0.86–0.91 on those.
- **The same page contradicts itself on polarity**: accelerator.html:211 presents WOC=0.90 as good ("90% of sessions succeed first-pass"), then accelerator.html:342-357 defines WOC = overhead/primary where **WOC ≥ 0.85 is "Critical — pause autonomy."** Under the page's own second definition, 0.90 is an emergency. framework.html:96 uses a third framing ("Above 0.85: healthy"). This will be noticed.
- framework.html:313 separately claims "Retry rate 21.4%" as a "key metric from 248 experiments" — a second, different "measured" retry rate (it's 1−78.6%, where 78.6% appears nowhere in the data files).

### 1.11 ❌ "Escalation multiplier Eₘ = 28.2×/28.3× (measured)" (accelerator.html:369, framework.html:99, :129, :312)

This is the ratio of two models' average session costs (0.4474/0.0158). **No cascade was ever executed.** Calling a price ratio a "measured escalation multiplier," and "88.5% of tasks resolve at T1" (accelerator.html:372) a cascade outcome, fabricates an experiment that didn't happen. Same for "cascade strategy saves 87%" (framework.html:327) — arithmetic on assumptions, not measurement.

### 1.12 ❌ TypeScript "gap widens to 200×" and "DeepSeek 87% correctness" (evidence.html:247–254)

From `typescript_ssg_*.json`:
- **All 7 Claude runs and all 7 DeepSeek runs hit the 600s timeout** (`exit_code: -1`); GPT-5 runs completed (`exit_code: 0`). You are comparing costs of *truncated* sessions against completed ones.
- DeepSeek's TS "87% correctness" is the keyword heuristic. The stored `actual_correctness` (test-derived) for its perturbed runs: 0.0, 0.6, 0.8, 0.25, 0.0, 0.0 — most runs did **not** produce verified-working code. Claude heuristic 90% vs actual: 1.0, 0.0, 0.0, 1.0, 0.0, 0.2. The page quotes heuristic numbers for the cost story and an *actual* number when convenient ("GPT-5 collapses to 20% on shift_framing" — that's `actual_correctness=0.2`). Mixing provenance within one table without disclosure.
- $0.0006/session for DeepSeek partly reflects sessions that timed out early. "The gap widens in strictly-typed environments" is not supported; what widened is the ratio of two unreliable numbers.
- Also: `run_ts_tests` in analyze_worktrees.py invokes **jest** with `--passWithNoTests` on projects that are configured for **vitest** (every TS worktree ships `vitest.config.ts`) — so post-hoc TS "test" results are structurally unable to be right.

### 1.13 ⚠️ Constraint detection: "Both models implemented every constraint... verification is structural" (evidence.html:175–185)

`constraint_detection.py` is keyword expansion: "error handling" is detected if the string "error" appears anywhere; "audit log" matches any "log"; confidence constants (0.95/0.85/0.4) are arbitrary. Calling this "structural verification" and "dual-signal verification" oversells grep. The file-name table (auth.py, audit.py...) is plausible evidence but is presented for exactly one task; the general claim inherits keyword-matching weakness. Note also the docstring bakes the conclusion into the instrument ("DeepSeek's GRPO pattern — code without narration... Claude's pattern — narration without code"): the tool assumes what the experiment is supposed to test.

### 1.14 ⚠️ Explanation Tax numbers (README "~50% Claude / ~3% DeepSeek"; methodology "24–120%"; framework "3% to 120%")

No shipped artifact computes ε as defined ("ratio of explanatory tokens to code tokens in successful sessions"). Narration *penalty rate* exists; ε as a token ratio does not appear in `_results_summary.json`, the lab outputs, or data.js. Three different ranges circulate. Untraced headline number.

### 1.15 Count inconsistencies (⚠️ everywhere)

227 experiments / 248 sessions / 249 sessions (README) / 251 worktrees / 203 game reports / 224 game reports / 255 transcripts are used interchangeably as "n". inventory.json is internally consistent (249 experiment sessions, 227 experiment worktrees, 224 reports on disk); the prose is not. The meta description of index.html alone contains three different frames. Pick one sentence: "249 instrumented sessions; 227 analyzed worktrees; 224 game reports" and use it everywhere.

### 1.16 ⚠️ Misc factual errors

- methodology.html:238 links "OpenAI o1 System Card, 2025" to arXiv:2501.12948 — that identifier is the **DeepSeek-R1 paper**. A mislabeled citation in the "where this fits in the literature" section is a bad look.
- evidence.html:167 "Claude avg thinking ratio 0.0%" is presented as behavior ("externalizes every reasoning step"). It's missing data — the harness records zero reasoning tokens for Anthropic. Absence of instrumentation ≠ measurement of zero.
- evidence.html:267 "DeepSeek's 69% corrected rate" references a number that appears nowhere else.
- framework.html:244 "AST-verified across 2,416 Python files" — untraceable to any shipped artifact (plausible from worktrees, but nothing in the repo emits this number).
- README architecture claim "MoE, 5.5% of 671B" vs data.js note "~3% active" — inconsistent.

---

## 2. METHODOLOGY RIGOR

### 2.1 The perturbation operators do not do what the documentation says

This is the deepest methodological problem. From `perturb.py` (verified by reading every operator):

| Operator | Website/README claim | Actual implementation |
|---|---|---|
| inject_alien_vocab | "**Replace** domain terminology" (methodology.html:96) | **Appends** a labeled "directional noise" block; replaces nothing |
| invert_constraint | "**Flip a requirement** to its opposite (e.g. 'must be fast' → 'must be slow')" (methodology.html:99, story.html:99) | Appends generic "do the opposite of your instinct / avoid best practices" text; never touches an actual task constraint |
| remove_critical_constraint | "**Silently drop** a defining requirement (e.g., JWT auth)" (methodology.html:101) | **Removes nothing.** Appends "constraints are now optional/relaxed" text; all original constraints remain in the prompt |
| insert_contradiction | "Place two mutually exclusive requirements in the prompt" | Appends abstract meta-text ("Constraint A and B are mutually exclusive...") that names no actual requirements |
| reverse_causality | "Present the solution before the problem" | Prepends an instruction to read constraints first; no structural reordering occurs |

Consequences:

1. **"Constraint recovery" was never tested.** Nothing was removed, so `constraint_detection.py` measures whether models implement constraints that are *still in the prompt*. Claims like "R1 knows a constraint is missing and adds it" (constraint_detection.py docstring) have no experimental basis in this corpus.
2. The "semantic vs manifold" taxonomy is a classification of **appended boilerplate strings**, not of task-specific semantic corruption. All operators also change prompt length and add an implicit "this prompt is weird" signal — an obvious uncontrolled confound.
3. "10 **calibrated** operators" — "calibration" is indexing into 3–6 canned strings by strength. Nearly every run used strength 0.5, and `analyze_worktrees.py:490` hardcodes strength 0.5 for all post-hoc analysis regardless of what was actually run.

The operators are still a reasonable v0 stress harness. But the site describes an instrument you have not built yet.

### 2.2 The 6 recovery signals do not demonstrably measure recovery

From `recovery.py`:
- Signals are keyword lists ("let me explain", "this is because"...), qualifier lists, tech-term overlap, length ratio, and header overlap. **None were validated** against human labels, holdout data, or any ground truth. There is no evidence that a step flagged RECOVERY represents a return to a basin rather than ordinary explanation.
- **Verified bug (executed):** Signal 2 indexes the *filtered* tool-call list with the *unfiltered* step index (`recovery.py:100-104`). An identical baseline/perturbed trajectory pair gets its write step flagged "tool 'write' converges toward baseline" → RECOVERY at 0.4 confidence. Identical behavior is classified as recovery.
- Thresholds are arbitrary and asymmetric: one marker hit (0.3) flips a whole step to RECOVERY; signal 5 (0.2 max) can never trigger alone; steps with no signals default to EXPLORATION at 0.5 confidence.
- **Circularity risk:** the marker lists are precisely the style of verbose, narrating models. A model that explains more will mechanically score more RECOVERY — and the site's thesis is that narrating models (Claude) "recover via narration." The metric partially *is* the conclusion.
- Signals 4–6 compare perturbed step *i* to baseline step *i*. Agentic trajectories do not align stepwise; this positional pairing is unjustified.
- methodology.html oversells each signal ("Jaccard similarity", "frequency measured against baseline", "n-gram overlap") relative to what the code does.

### 2.3 Escape/basin metrics measure text variance, not attractor topology

`basin.py`: escape = 0.4×(tech-keyword Jaccard) + 0.3×(LOC/def-count deltas) + 0.3×(5-gram Jaccard, mislabeled "trigram"). No validation that this measures anything like an "attractor basin." In the post-hoc pipeline (`analyze_worktrees.py:476-493`), runs without a matched baseline compare code to itself (escape=0 by construction), and correctness is passed as both baseline and perturbed, making `quality_per_dollar` literally `1/cost`. The lab_grit_matrix results state the medians used for quadrant assignment were **escape=0.0 and correctness=1.0** — degenerate boundaries that make quadrant percentages (e.g., "DeepSeek 51.4% High Grit") artifacts of ties at the extremes.

`lab_basin_topology.md` then declares "Architecture signatures confirmed" (GRPO=wide-shallow, SFT=narrow-deep) from these heuristics on n=3–16 cells with an invented `basin_volume` formula. This is pattern-naming, not confirmation.

### 2.4 Strategy archetypes are largely a restatement of provider pricing

`strategy.py:140-142`: EFFICIENT requires cost ≤ $0.003/session; WASTEFUL requires cost ≥ $0.005 with low correctness; expensive means ≥ $0.01. **Absolute-dollar thresholds embed the pricing conclusion into the "behavioral" classification**: Claude can never be EFFICIENT at any behavior, DeepSeek can rarely be WASTEFUL. The evidence-page insight "no model classified as WASTEFUL or EFFICIENT — every session is CONSERVATIVE or EXPLORATORY" is a threshold artifact, not a finding. `recovery_cost.py` verdicts have the same defect ($0.001/$0.01 absolute cutoffs).

### 2.5 Confounds not accounted for

1. **Task mix per model** (§1.3) — the largest one.
2. **Harness effects**: all behavior is filtered through opencode. Tool-name accounting differs by provider (GPT models emit `apply_patch`, counted separately from `write` → "0% write" for all GPT models in lab_tool_archetypes; Claude shows "0% read"). The "tool archetype = architectural fingerprint" story is at least partly an artifact of harness plumbing.
3. **Timeouts**: TS runs — Claude/DeepSeek 100% timed out, GPT-5 completed (§1.12). Python post-hoc pytest had a 15s timeout (`analyze_worktrees.py:64`) with a 60s silent-failure dep install — effectively guaranteeing sparse/failed test evidence.
4. **Reasoning-token visibility** differs by provider (Claude: none exposed) — thinking-ratio comparisons across providers are not like-for-like.
5. **Sampling parameters** (temperature etc.) unrecorded; opencode version unpinned; `/tmp/exp_*` worktrees are the evidence base and are ephemeral.
6. **Prompt-length inflation** from every operator (§2.1).

### 2.6 Sample size and statistics

- Per-model n: DeepSeek 119, Claude 44, then 6–16 for the six GPT variants. Per-operator×model cells: n=1–9, many 1–2. Manifold-class: Claude n=3, GPT-5 n=1 — yet manifold-vs-semantic per-model comparisons are headline tables (evidence.html:221-225) with **no n shown and no intervals**.
- **There is not a single confidence interval, significance test, or effect-size calculation anywhere on the website.** The only inferential machinery in the codebase is `lab_book.py:48` — "reject H0 if manifold avg > semantic avg + 0.15" — an arbitrary delta, and `run.py`'s unused crude CI printout.
- Heuristic-correctness ceiling: three models sit at "100% [H]" with n=3–9. Ranking models on this is noise.
- "227 experiments is statistically meaningful" (methodology.html:253) is asserted, never demonstrated. For the cost claim (huge effect, n=163 relevant sessions), it plausibly is. For per-operator, per-class, routing, flail-cause, and basin claims, it is not.

---

## 3. RULE-TO-EVIDENCE MAPPING

The framework page states "Rules 1–5 are empirically grounded in 248 instrumented experiment sessions" (framework.html:89). Assessment:

| # | Rule | Support | Assessment |
|---|------|---------|------------|
| 1 | Grit | **Partial** | Cost differentials under perturbation are real [M]. But "maintains correctness" rests on keyword-heuristic correctness; "flail" is unrelated to perturbation per your own lab book (manifold flail = 0; flail sessions are the `unknown` class); and the perturbations don't degrade instructions the way claimed (§2.1). The concept is promising; the measurement doesn't yet support the rule as stated. |
| 2 | Explanation Tax | **Partial → weak** | Narration failures and output-token volumes are measured. ε itself (explanatory-to-code token ratio) is never computed anywhere in the shipped pipeline; the 3%/50%/24–120% figures are untraceable. |
| 3 | Snowball (N²) | **None** | No experiment measures context growth across sequential sessions. β=0.001 is a design parameter (data.js says so). This is a model, presented on framework.html as "measured empirically — no parameter is theoretical" (framework.html:154), which is false. |
| 4 | EPM Horizon | **None (external)** | IEA projection applied to a hypothesis. Legitimate as [X] modeling; zero experimental content. |
| 5 | First-Pass / WOC | **Not as stated** | No retries were measured. r=0.115 is narration-failure share. WOC is defined two contradictory ways on one page (§1.10). The *idea* is sound; the "measured" tag is not. |
| 6 | Batch Discount | **External** | 50% batch pricing is a provider fact [X]. No batch experiment was run. Labeled "Extension" — acceptable, keep it labeled. |
| 7 | Budget Ceiling | **Arithmetic** | An identity (Budget/Cost). Fine, needs no data; don't imply it was measured. |
| 8 | Cascade | **None** | No cascade ever executed. "28.2× measured" is a price ratio (§1.11). "<1% escalation to human" is aspiration. |
| 9 | SLA Buffer | **None** | No queues, no SLAs, no completion-time distributions measured. |
| 10 | Outcome Multiplier (BVI) | **Definitional** | A metric definition. No data exists or is claimed — but the accelerator page implies otherwise. |

Honest summary the site should adopt: **Rule 1–2 partially measured (cost side [M], quality side [H]); Rules 3–5 are models with measured cost inputs; Rules 6–10 are framework extensions with no experimental content.** The index page's "5 measured · 5 framework extensions" already overstates by 3.

---

## 4. ENTERPRISE PROJECTIONS HONESTY CHECK (accelerator.html)

**Short answer: the projections are extrapolations of per-session price ratios, presented with the visual and verbal apparatus of measurement. Two of three headline tables contain arithmetic errors, and the Executive Dashboard is fabricated.**

### 4.1 The savings table (accelerator.html:268–290)

- **Augmented Workforce row**: "Optimized $640/month — $0.016/session × 20K sessions, 10% escalation to Claude." With the stated 10% escalation: 18,000×$0.016 + 2,000×$1.08 = **$2,448/month, not $640**. The printed number ignores its own escalation assumption (~4× understatement of optimized cost; annual savings should be ~$229.8K, not $251.5K).
- **Cache Strategy row**: $3,375/month is 22.5K tokens × **$15/Mtok** × 10K sessions. Anthropic cache writes are $3.75/Mtok (your own `efficiency.py`), so the "current" cost is overstated ~4× and the $39,996/year saving is built on a wrong price.
- **Autonomous Batch row**: the printed formula "$0.016 × 105K × (1 + 0.115 × 28.3)" evaluates to **$7,147/month, not the printed $3,360**. Formula and result disagree on the same line. The formula itself (retry_rate × escalation_multiplier as a cost adder) is invented, using the narration share as a retry rate and a price ratio as an escalation multiplier.
- "How these numbers are derived... All projections documented with provenance [M] measured / [C] computed" (accelerator.html:295) — the inputs include [H] and fabricated terms; none of the three rows survives its own arithmetic.

### 4.2 "50–70% cost reduction" and "10× throughput"

- 50–70% is called a "target" in one card and "conservative estimates based on the 248-experiment dataset" under Projected ROI (accelerator.html:472). **No organizational deployment was measured. Ever.** The corpus contains no before/after cost data for any team. The only honest statement is: "model price ratios observed in our lab imply large savings *if* quality holds at your task mix — which you must verify."
- **10× throughput** (accelerator.html:479): no throughput was measured anywhere in the corpus — no latency, no queues, no batch runs. This number has no provenance at all.
- "The framework pays for itself in the first month" (accelerator.html:488): marketing assertion inside what is framed as a research artifact.

### 4.3 The Executive Dashboard (accelerator.html:388–435) — fabricated

"$0.11/completed task", "68% batch · 32% on-demand", "T1: 47% · T2: 31% · T3: 22%", "queue depth 12", "4.3 min / 8.2 hr completion", "WOC 0.82", "78.6% first-pass", "18 months runway", "10× throughput within 5 min", "−12% under projection" — **none of these correspond to any experiment, log, or data file in this repository.** There was no queue, no tiering, no batch pipeline, no runway. They are mock-ups presented in the same visual language as measurements, on a site whose thesis is "provenance-tagged honesty." If these ship unlabeled, they are indistinguishable from invented data. Label the entire section "ILLUSTRATIVE EXAMPLE — not measured" or delete it.

### 4.4 "88.5% of tasks resolve at T1... The human sees < 5%" (accelerator.html:372)

The narration-failure complement rebranded as a cascade resolution rate for a cascade that never ran. Same for "Route 78.6% of tasks to the cheapest tier" (accelerator.html:196) — 78.6% appears in no data file.

---

## 5. CODE QUALITY (src/instrument/ + pipeline)

### 5.1 Verified crash bugs (executed during this audit)

1. **`adapter.py:106` — `InstrumentedAdapter.invoke()` raises `NameError: name 'result' is not defined` on every call.** `result` is local to the inner `_call()`. The advertised trajectory-capture adapter cannot ever have run successfully. (Also: the ThreadPoolExecutor context manager **joins the worker thread on exit**, so the "thread-level timeout so stuck LLM calls don't block experiments" docstring is false — a stuck call still blocks at `__exit__`.)
2. **`lab_book.py:64` — `persist_to_lab_book()` raises `AttributeError`** (`ExperimentRun` has no `recovery_ratio`). The advertised lab-book persistence path is dead code.
3. **`recovery.py:100-104` — signal-2 misalignment (verified):** identical baseline/perturbed trajectories are classified RECOVERY because the filtered tool list is indexed with the unfiltered step index.

That two public API functions crash on first use tells you what the missing test suite (`tests/` contains only pytest cache artifacts — **zero unit tests in the repo**) would have caught.

### 5.2 Bugs that corrupt measurements

4. **`opencode.py:396-409` — test-count accumulation:** every bash output containing "passed" *overwrites* `tests_passed` but *accumulates* `tests_total`. A model that runs pytest 3 times while iterating (10→11→12 passing) ends with 12/33 = 36% "actual correctness." **This systematically penalizes exactly the iterate-until-green behavior the standardized prompt demands**, and explains implausible `actual_correctness` values (0.25, 0.2) in the TS results. Also: the final fallback fabricates 1/1 passed if "passed" appears anywhere; `is_error` flags any output containing the substring "error" (e.g., "0 errors").
5. **`analyze_worktrees.py:105-150` — `run_ts_tests` runs jest (with `--passWithNoTests`) against vitest projects** → TS pass rates structurally wrong (§1.12).
6. **`analyze_worktrees.py:64` — 15s pytest timeout** (plus 60s silently-capped dep install) → Flask suites time out → correctness silently falls back to the keyword heuristic. This is how the flagship summary ended up with zero test results.
7. **`efficiency.py:52-65` — `get_pricing` ignores `model_id` entirely** (Haiku=Opus, nano=GPT-5.6) and silently prices unknown providers at DeepSeek rates. `experiment.py:173-179` and `run.py:126-130, 204-208` call `compute_efficiency` **without a provider** → all component costs in `run.py` outputs are computed at DeepSeek rates regardless of the model. (analyze_worktrees passes provider and overrides totals with DB cost — that path is OK for totals, but component splits are re-scaled estimates presented in evidence.html as "$18.26 cache costs" etc.)
8. **`basin.py:176` — fallback cost hardcodes DeepSeek pricing** for any model. `basin.py:183` — `constraints_total = max(met_baseline, met_perturbed)` is not a total; the denominator is wrong whenever both runs miss constraints.
9. **`trajectory.py:284-293` — embedding pairing bug:** when one side's step action is empty, `ei` still advances by 2 while only 1 (or 0) texts were appended → cosine distances computed between the wrong step pairs.
10. **`analyze_worktrees.py:477-484` — baseline self-comparison** (escape ≡ 0, novelty ≡ 0, `quality_per_dollar` ≡ 1/cost) whenever no matched baseline exists — which is every baseline row and every unmatched perturbed row.
11. **`game_report.py:205` — bogus error propagation:** cost uncertainty displayed as `mean_cost × (std_escape/mean_escape)` — escape variance used as cost variance.

### 5.3 Design defects that undermine cross-model conclusions

12. `solution.py:110` — `code_quality_score` awards `min(1, 200/LOC)`: **any solution over 200 lines is penalized linearly.** Verbose models (Claude, and DeepSeek's 700-LOC outputs) are structurally scored as "lower quality." Cross-model "quality" comparisons on evidence.html inherit this bias.
13. `solution.py:172-179` — "cyclomatic complexity" counts `"and "`, `"or "` etc. **including inside prose/docstrings**, total (not per-function). It is not cyclomatic complexity; the game reports tag it [C].
14. `semantic_validation.py:100-102` — marker counts are presence-capped (max 15 regardless of length) then divided by word count → longer texts mechanically get lower "explanatory ratios." Any "marker validation accuracy" table built on this is uninterpretable.
15. `semantic_validation.py:220` — `rename_rate` counts *new* names as renames.
16. Three conflicting price tables (`efficiency.py`, `build_data.py`, framework.html playbook) — $15 vs $3.75 anthropic cache write; $10 vs $5 vs $30 OpenAI output.
17. `build_data.py:268-294` — the interactive calculator ingests "[H]" pass rates as measured `p` values, and `retry_rate_measured` is the narration share (naming encodes the overclaim).
18. Evidence base lives in `/tmp/exp_*` — a reboot destroys the primary artifacts backing a published website.

**None of the 5.1–5.2 items is cosmetic: items 4–6 alone are sufficient to explain why the "correctness" layer of this project is unreliable.**

---

## 6. ONE-WAY DOOR RISKS

Ranked by (likelihood of exposure × reputational damage). "Exposure" here usually means: anyone technical opens the repo you are publishing alongside the site.

1. **"987/1059 tests, no heuristic estimation" vs `test_results: null` × 227 in your own shipped JSON.** One tweet-sized diff ends the project's credibility. REMOVE or rerun with real test execution. *Nothing else matters until this is fixed.*
2. **Lab-book "Expected Output" numbers published as findings** (44%/58%/100% flail). The lab books shipping in the same repo contain the executed results that contradict the site. REPLACE all flail numbers with executed results (Claude 11.4%, mini 8%, nano 14%) and rewrite the narrative they supported — including the accelerator's "nano and mini cannot be trusted unsupervised" tier logic, which was built on the imagined numbers.
3. **Fabricated Executive Dashboard.** If a customer asks "where does queue depth 12 come from?" there is no answer. LABEL ILLUSTRATIVE or DELETE.
4. **Wrong Anthropic cache-write price ($15/Mtok).** Every FinOps practitioner knows cache writes are 1.25× input. The "Cache Tax 100×" headline collapses on first contact. CORRECT to $3.75 and reframe (the honest read-vs-read asymmetry, ~21×, is still a good story).
5. **Arithmetic errors in the savings table** (§4.1). CFO-facing numbers that fail their own stated formulas are worse than no numbers.
6. **"Controlled experiments, not surveys" as the anti-Databricks differentiator.** You are inviting exactly the scrutiny that reveals items 1–5. The comparison page's "No reproducibility [for them]... ours is inspectable down to individual session transcripts" makes your own inspectability the battleground. Do not ship that sentence until the repo survives inspection.
7. **Operator descriptions vs implementation** (§2.1). Any researcher who reads `perturb.py` will see "remove_critical_constraint" removes nothing. Rewrite the methodology page to describe what the operators actually do, or rewrite the operators.
8. **"Same computational effort" vs your own 14× ARCH_RATIO** — self-contradiction visible within the site.
9. **WOC polarity contradiction on one page** (healthy at 0.90 / critical at ≥0.85). Trivially screenshotted.
10. **Unverifiable claims about competitors' internals stated as fact** ("Claude = SFT imitation CoT", "500B dense", "GPT family = SFT"). Anthropic/OpenAI have not disclosed this; DeepSeek-R1's GRPO is published, the rest is inference. Hedge or cite.
11. **TS 200× claim** built on 100%-timeout sessions with near-zero verified correctness (§1.12). REMOVE or rerun with adequate timeouts and real tests.
12. **"Every term was measured empirically – no parameter is theoretical"** (framework.html:154) with β labeled `provenance: design` in your own data.js. DELETE the sentence.

**What should be removed entirely:** the Executive Dashboard numbers; "10× throughput"; "987/1059"; "no heuristic estimation"; the 200× TS claim (until rerun); "pays for itself in the first month"; "measured" qualifiers on Eₘ, WOC, retry rate, escalation resolution rates; the "(measured)" tag on the T3 cascade tier.

**What should be caveated strongly:** 69× (task-mix, n, both models' outputs unverified by tests); all correctness comparisons ([H] until tests rerun); manifold/semantic per-model splits (report n; Claude manifold n=3, GPT-5 n=1); grit-routing simulation (in-sample, n=1–4/cell); energy joules (constants below cited source range, parameter counts guessed); flail (unrelated to perturbations per own lab book).

---

## 7. GAP ANALYSIS

### What the framework misses that it should address

1. **Statistical inference, entirely.** No CIs, no tests, no power analysis, no multiple-comparison awareness across 8 models × 10 operators × tasks. Minimum bar for "research": bootstrap CIs on every cross-model number and n displayed in every table.
2. **Ground-truth validation of every heuristic layer** — correctness (vs. actual test execution), recovery signals (vs. human labels), escape (vs. human judgment of "different approach"), constraint detection (vs. manual audit on a sample). Without this, [H] metrics cannot support any ranking.
3. **Matched-task, matched-completion design.** Same tasks, same timeouts, same seeds, N≥5 repetitions per cell, all models. The corpus is large enough in total but misallocated (119 DeepSeek vs 3–9 per GPT variant).
4. **Latency/throughput measurement** — claimed in ROI, absent from data.
5. **Actual cascade/routing/batch/cache experiments** — Rules 6–9 could each be measured with the existing harness in a weekend of runs; today they're slideware.
6. **Quality beyond tests**: maintainability, security, review burden — "cheaper and passes keyword checks" is not "same output."
7. **Price-volatility handling**: pricing is a Q3-2026 snapshot hardcoded in three inconsistent tables; no dated pricing manifest.
8. **Harness independence**: replicate a subset outside opencode to separate model behavior from scaffold behavior.
9. **Session persistence for evidence** — move worktree artifacts out of `/tmp`.

### Framework vs Databricks (both directions)

| Dimension | Databricks playbook | This framework |
|---|---|---|
| Production-scale telemetry, real orgs, real workloads | ✅ (Stripe/Coinbase/Uber/Ramp scale) | ❌ toy tasks, one developer's sessions |
| Perturbation/robustness testing | ❌ | ✅ genuinely novel — the defensible differentiator |
| Harness/token tuning at scale ("50% token cut") | ✅ measured in production | ❌ asserted via model-switching only |
| Routing measured in production (">30% savings") | ✅ (their gateway) | ❌ in-sample simulation |
| Energy/long-horizon cost modeling | ❌ | ✅ but currently [H]/[X] dressed as more |
| Org rollout, budgets, governance practice | ✅ grounded in surveys | ⚠️ extrapolated well beyond data |
| Open, inspectable data | ❌ | ✅ — the strength, and currently the liability |

The framework's honest positioning is *complementary*: "Databricks measured what happens in production; we built an open instrument for the robustness dimension their playbook can't see." The current positioning ("we measured, they guessed") sets up a comparison the corpus loses.

---

## 8. OVERALL READINESS

**Scale: ready-to-publish-as-research / ready-for-internal-use / needs-revision-before-any-public-claim.**

### Verdict: **Needs revision before any public claim.**

- **As research:** Not ready. The dependent variable (correctness) is unvalidated keyword matching in the shipped dataset; the perturbation operators don't implement their documented semantics; there is no statistical inference; two lab books publish contradictory hypothesis outcomes; the site cites pre-execution expected values as results.
- **For internal use:** Substantial parts are ready today — the opencode-DB cost/token accounting, per-model spend profiles, the artifact-bundling pipeline, and the perturbation harness as a qualitative probe. Used internally with [H] labels respected, this is a useful cost lens.
- **For public launch as currently written:** The site makes verifiable false statements about its own shipped data ("no heuristic estimation"), contains fabricated dashboard metrics, and its enterprise page fails its own arithmetic. Launching invites a public, easily-documented debunking — the exact one-way door this audit was commissioned to check.

### Minimum path to a defensible launch (in order)

1. Re-run `analyze_worktrees.py` **with tests enabled**, realistic timeouts (≥120s), correct TS runner (vitest), and fixed test-count parsing (opencode.py §5.2.4). Regenerate `_results_summary.json` → `data.js`. Every correctness number on the site becomes [M] or is deleted.
2. Global find-and-fix the contradiction set: flail rates (use executed lab-book numbers), WOC polarity, retry rate (11.5% vs 21.4%), Claude spend ($47.54 vs $42.52 frames), session counts, cache-write price ($3.75), "$10/Mtok" → $15, "o1 system card" citation.
3. Delete or label ILLUSTRATIVE: Executive Dashboard, 10× throughput, 50–70% ("target" only), cascade resolution rates, "pays for itself," "(measured)" on Eₘ.
4. Fix the three savings-table calculations, or replace the table with the calculator (which at least shows its formula).
5. Rewrite methodology operator descriptions to match `perturb.py` (or vice versa), and reframe "constraint recovery" claims accordingly.
6. Add n and bootstrap CIs to every cross-model table; drop cells with n<5 from headline claims (manifold Claude n=3, GPT-5 n=1).
7. Fix the three crash bugs (adapter NameError, lab_book AttributeError, recovery signal-2) and add a minimal pytest suite; pin pricing in one dated table.
8. Reframe the Databricks page from "we proved, they surveyed" to "independent convergence + a new robustness axis."

The 69× cost observation, the ~11K generated-token parity, the cache-pricing asymmetry (correctly priced), the per-model spend profiles, and the perturbation-harness concept survive all of the above and make a strong, honest launch. The current draft does not.

---

*Appendix — verified-by-execution during audit: (a) `InstrumentedAdapter.invoke` → `NameError: name 'result' is not defined`; (b) `persist_to_lab_book` → `AttributeError: 'ExperimentRun' object has no attribute 'recovery_ratio'`; (c) identical baseline/perturbed trajectories classified RECOVERY via signal-2 index misalignment; (d) `test_results: null` for 227/227 entries in `_results_summary.json`; (e) deployed `data.js` `overall_pass_rate` = "90.3% [H]" and all model `pass_rate` values "[H]"-tagged while site prose claims "no heuristic estimation."*
