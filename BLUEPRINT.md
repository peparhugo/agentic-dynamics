# Blueprint — Audit Correction Pass

Generated from the full end-to-end audit. Each item is traceable to a specific section of the audit, a specific file, and actionable as a discrete unit of work.

Legend: [x] done. Phases must run sequentially.

---

## Phase 1 — Correctness Pipeline Fix (P0)

### 1.1 Reorder `analyze_worktree()` pipeline
**Audit §3 | File: `scripts/analyze_worktrees.py:380-741`**

- [x] Move test execution (lines 630-640) to immediately after AST profiling, before basin/strategy
- [x] Feed canonical correctness from test results (or heuristic fallback) to `measure_basin_escape()`
- [x] Feed canonical correctness to `classify_strategy()`
- [x] Recompute `solution.composite_score` after correctness is settled
- [x] For Python tests (line 103): change `"ok": total > 0` to `"ok": r.returncode == 0 and total > 0`
- [x] For TS tests (lines 169-176): handle edge case `ok: True, total: 0` → now returns `ok: False`
- [x] Always overwrite `solution.correctness_score` from test results when tests exist, regardless of `ok`

### 1.2 Add evaluator provenance to `SolutionMetrics`
**Audit §4 | File: `src/instrument/solution.py`**

- [x] Add field `evaluator_source: str = "unavailable"`
- [x] Add field `evaluator_independent: bool = False`
- [x] Valid values: `"agent_authored_test"` | `"heuristic"` | `"compile_check"` | `"unavailable"`
- [x] Preserve in `to_dict()` output

### 1.3 Set evaluator provenance in `analyze_worktree()`
**Audit §4 | File: `scripts/analyze_worktrees.py`**

- [x] When tests run: set `solution.evaluator_source = "agent_authored_test"`, `evaluator_independent = False`
- [x] After heuristic evaluation: set `solution.evaluator_source = "heuristic"` (tests override if they run)
- [x] Write `evaluator_source` into the `metrics` dict returned by `analyze_worktree()`

### 1.4 Fix `build_data.py` pass_rate computation
**Audit §4 | File: `scripts/build_data.py`**

- [x] Read `evaluator_source` from each entry
- [x] When mixed sources: pass_rate shows `[mixed]` tag
- [x] When test-only: `[tests]` tag
- [x] When heuristic-only: `[H]` tag (never silently collapses sources)
- [x] Update `_provenance` dict on `pass_rate` key to reflect mixed sources (`"H"` / `"M/C"` / `"M"`)

### 1.5 Data lineage regression tests
**Audit §15 | File: `tests/test_correctness_lineage.py` (new)**

- [x] Test: heuristic 0.8 + failing tests → canonical correctness = 0.0, source = "agent_authored_test"
- [x] Test: heuristic 0.5 + no tests available → correctness = heuristic, source = "heuristic"
- [x] Test: pipeline ordering → `basin.correctness` receives post-test value
- [x] Test: narration_failure path still works
- [x] Test: build_data pass_rate: test-only vs heuristic-only vs mixed sources
- [x] 11 tests total, all passing

### 1.6 GitHub Actions CI
**Audit §15 | File: `.github/workflows/pytest.yml` (new)**

- [x] `pytest` on push to `main`
- [x] `build_data.py --dry-run` integrity check
- [x] Core tests (perturb, pricing, correctness_lineage) run in CI

---

## Phase 2 — Regenerate Entire Corpus

**Audit §26 item 2**

```bash
python scripts/inventory.py refresh
python scripts/analyze_worktrees.py           # regenerates 224+ game reports
python scripts/analyze_trajectories.py
python scripts/lab_claude_audit.py
python scripts/lab_grit_matrix.py
python scripts/lab_correctness_premium.py
python scripts/lab_flail_triggers.py
python scripts/lab_tool_archetypes.py
python scripts/lab_task_routing.py
python scripts/lab_basin_topology.py
python scripts/lab_survival_horizon.py
python scripts/lab_reasoning_divergence.py
python scripts/lab_semantic_clusters.py
python scripts/lab_cross_model_reasoning.py
python scripts/lab_basin_topology_neo4j.py
python scripts/lab_opencode_meta_analysis.py
python scripts/lab_sonar_quality.py
python scripts/build_data.py                  # regenerates data.js
python scripts/generate_manifest.py
```

- [x] All 14 lab scripts re-run
- [x] All 224+ game reports regenerated
- [x] `_results_summary.json` regenerated
- [x] `data.js` regenerated
- [x] Verify ~35 buggy entries are fixed (correctness 0.8/strategy "exploratory" but tests 0/1)

---

## Phase 3 — Pricing, Infrastructure & Code Drift Fixes

### 3.1 Snapshot pricing by date
**Audit §12 | Files: `src/instrument/efficiency.py:37-50`, `scripts/_constants.py:16-29`**

- [x] Add `# Pricing snapshot: 2026-03 (experiment billing date)` above both `PROVIDER_PRICING` dicts
- [x] Add `HISTORICAL_EXPERIMENT_PRICING` dict (current values: DeepSeek 0.27/1.10, Anthropic 3/15, OpenAI 1.25/10)
- [x] Add `CURRENT_REFERENCE_PRICING` dict (DeepSeek 0.435/0.87, Anthropic 10/50, OpenAI 5/30)
- [x] Update `test_pricing.py` to test historical snapshot separately from current reference

### 3.2 Fix architecture constants
**Audit §7 | File: `src/instrument/efficiency.py:17-25`**

- [x] `DEEPSEEK_ACTIVE_PARAMS`: 37e9 → 49e9 (publicly disclosed per audit)
- [x] `CLAUDE_EST_ACTIVE_PARAMS`: change comment from "Dense, undisclosed" → "Undisclosed — placeholder; not independently verifiable"
- [x] Remove `ARCH_RATIO` and `HARDWARE_RATIO` (derived from unverifiable assumptions)
- [x] Add `_ENERGY_MODEL_AVAILABLE = False` with docstring: "Energy estimates are modeled scenarios, not measured quantities"

### 3.3 Normalize OpenCode event schemas
**Audit §14 | Files: `src/instrument/opencode.py`, `scripts/analyze_trajectories.py`**

- [x] Add `normalize_opencode_event(event, schema_version: int) -> dict`
- [x] Handle v1: `reasoning`, `tool`, `step-start`, `step-finish`
- [x] Handle v2: `tool_use`, `step_finish`, nested `part`
- [x] Regression fixtures in `tests/test_opencode_events.py` (new)

### 3.4 Fix Neo4j operator population
**Audit §13 | File: `src/instrument/graph.py:77-88`**

- [x] Replace `swap_modality` → `reverse_causality`
- [x] Replace `parse_structural_shift` → `force_abandonment`
- [x] Replace `inject_false_premises` → `inject_false_premise`
- [x] Replace `inject_recursion` → `inject_contradiction`
- [x] Update `tests/test_graph.py` to verify graph taxonomy matches `perturb.py` exactly

### 3.5 Add missing pyproject.toml dependencies
**Audit §16 | File: `pyproject.toml`**

- [x] Add `scikit-learn>=1.3`, `pytest>=7.0`
- [x] Update description: `"reasoning topology instrument"` → `"Agent economics measurement instrument — how does coding-agent cost and outcome change as specification quality degrades?"`

### 3.6 Fix reproduce.sh
**Audit §16 | File: `scripts/reproduce.sh:24`**

- [x] Remove `--no-tests` flag
- [x] Add lab analysis step after worktree analysis
- [x] Update header comment to accurately describe what's reproduced

---

## Phase 4 — Library & Scientific Identity

### 4.1 Update `__init__.py` package identity
**Audit §8 | File: `src/instrument/__init__.py:1-11`**

- [x] Replace "Reasoning topology instrument" → "Agent economics measurement instrument"
- [x] Replace "measures search dynamics" → "measures how coding-agent cost and verified outcome change as specification quality degrades"
- [x] Remove H0/H1 hypothesis language from library docstring

### 4.2 Reclassify perturbation operators
**Audit §7 | File: `src/instrument/perturb.py:600-662`**

- [x] Replace "manifold"/"semantic" classification with three-way taxonomy:
  - **Specification corruption**: `inject_false_premise`, `inject_contradiction`, `remove_critical_constraint`, `inject_phantom_success`
  - **Objective mutation**: `invert_constraint`, `inject_competing_goal`
  - **Process perturbation**: `force_abandonment`, `reverse_causality`, `inject_alien_vocab`, `shift_framing`
- [x] Update `perturbation_class` field in each operator
- [x] Update `analyze_worktrees.py:549-551` pert_class detection logic
- [x] Update `build_data.py:421-463` operator comparison

### 4.3 Operationally define Grit
**Audit §6 | File: `src/instrument/basin.py` docstring**

- [x] Add operational definition block:
  ```
  Grit(s) = P(verified_success | perturbation_strength=s)
  Grit retention: R(s) = G(s) / G(0)
  Grit AUC: area under outcome-retention curve
  Recovery premium: ΔC = C(successful_perturbed) / C(successful_baseline)
  ```

### 4.4 Remove "dense" architecture labels — Python & Markdown
**Audit §7, finding 6**

- [x] `src/instrument/efficiency.py:19` — remove "Dense" from comment
- [x] `scripts/lab_basin_topology.py:53,157` — "SFT/Dense signature" → "provider family behavioral cluster"
- [x] `experiments/lab_books/lab_basin_topology.md:58` — "Small dense models" → "Small provider-family models"
- [x] `experiments/lab_books/lab_cross_model_reasoning.md:30` — "MoE vs Dense" → "provider family differences"
- [x] `experiments/lab_books/lab_reasoning_divergence.md:91` — "SFT/dense models" → "SFT-trained models"

### 4.5 Remove "latent space"/"latent reasoning" — Python & Markdown
**Audit §8, finding 7**

- [x] `scripts/analyze_trajectories.py:15` — "GRPO latent reasoning" → "GRPO reasoning surfaced as exposed text events (causal mechanism not confirmed by this experiment)"
- [x] `experiments/lab_books/lab_cross_model_reasoning.md:107` — "GRPO latent reasoning" → "observed reasoning-text patterns (causal architecture not established)"

---

## Phase 5 — Lab Script Corrections

### 5.1 Rename "significance" thresholds
**Audit §26 item 5, finding 1**

- [x] `scripts/lab_correctness_premium.py:137` — `"significance_threshold"` → `"tie_threshold"`, value note added
- [x] `scripts/lab_correctness_premium.py:175` — `"Significance:"` → `"Tie rule:"`
- [x] `scripts/lab_claude_audit.py:74,77,136` — add disclaimer that 0.05 is practical threshold
- [x] `scripts/lab_task_routing.py:91` — comment updated

### 5.2 Remove "null_hypothesis" language
**Audit §26 item 5, finding 5**

- [x] `scripts/lab_correctness_premium.py:128-136` — replace null_hypothesis with `"decision_rule"`
- [x] `experiments/lab_books/lab_correctness_premium.md:76` — "null hypothesis" → "decision criterion"
- [x] `experiments/lab_books/lab_task_routing.md:78` — "null hypothesis" → "decision rule"

---

## Phase 6 — Website Restructuring

### 6.1 Rewrite homepage
**Audit §17, §21 | File: `firebase/public/index.html`**

- [x] Hero: "What does an AI coding task cost when the specification is wrong?" → 4 numbers (249 sessions, 10 operators, 8 models, $64.98)
- [x] Remove 69× from hero
- [x] Remove "See What Databricks Missed" button (line 52)
- [x] Remove 10 rules from hero area
- [x] Section: "The missing variable" — real specifications degrade, show perturbations
- [x] Section: "The instrument" — pipeline diagram with links to source
- [x] Section: "What the corpus shows" — 3 findings only
- [x] Section: "Grit" — operational definition
- [x] Section: "Why FinOps cares" — connection to use-case economics
- [x] Bottom: Evidence | Instrument | Research Notebook | GitHub | Related Work

### 6.2 Restructure navigation across all pages
**Audit §22 | Files: all 8 HTML files in `firebase/public/`**

- [x] New nav: `Home | Instrument | Evidence | Research | Framework | Story | GitHub`
- [x] Rename `methodology.html` → serve as Instrument page
- [x] Move Accelerator out of main nav → footer link
- [x] Update all 8 nav bars consistently

### 6.3 Demote Databricks
**Audit §18 | File: `firebase/public/databricks.html`**

- [x] Line 101: Remove "On 12 of 15 overlapping tasks, the cheaper model is MORE correct"
- [x] Line 70-74: Remove "The Efficiency Frontier = Grit" equivalence
- [x] Remove "See What Databricks Missed" from `index.html:52`
- [x] Reposition as "Related Work" section
- [x] Reference actual July 2026 Databricks benchmark URL

### 6.4 Remove unvalidated Accelerator claims
**Audit §19 | File: `firebase/public/accelerator.html`**

- [x] Add header: "Operational hypotheses derived from research; not independently validated."
- [x] Remove all "50-70% cost reduction" claims
- [x] Remove "4-6 week implementation" timeline
- [x] Remove "autonomous workforce" language
- [x] Remove from main navigation

### 6.5 Fix Story page
**Audit §23 | File: `firebase/public/story.html`**

- [x] Line 104: Remove "Claude couldn't resist its training distribution" → replace with "I initially thought the cost difference was simply token volume..."
- [x] Lines 116-118: Replace SFT causal claims → "We observe materially different recovery and output behavior..."
- [x] Lines 118-120: Replace GRPO causal claims → "One hypothesis is that DeepSeek's GRPO training contributes..."
- [x] Line 120: Remove "Silent Inference Principle" as causal property → reframe as observed pattern

### 6.6 Fix evidence page
**Audit §8, §9, §11 | File: `firebase/public/evidence.html`**

- [x] Remove architecture labels "MoE"/"dense" from model cards
- [x] Remove "latent space"/"latent reasoning" language (lines 126, 151, 1076)
- [x] Move RVS/clustering/divergence cascade/topology → new Research page or section
- [x] Move energy model (EPM, joules) → "Modeling extensions" section
- [x] Add evaluator provenance column to all correctness displays
- [x] Add causation caveat note

### 6.7 Fix glossary
**Audit §10, §8 | File: `firebase/public/glossary.html`**

- [x] **Grit** (line 38-39): Add operational definition G(s) = P(verified_success | perturbation_strength=s)
- [x] **Silent Inference** (line 48-49): Remove GRPO causal claim; reframe as observed pattern
- [x] **GRPO** (line 73-74): Replace "Reasoning exists as vectors in latent space" → hypothesis framing
- [x] **Attractor Basin** (line 78-79): Remove "dense" label
- [x] **Strategy Archetypes** (line 93-94): Remove per-model attributions (will change post-regeneration)

### 6.8 Fix framework page
**Audit §20 | File: `firebase/public/framework.html`**

- [x] Line 86: Remove "Rules 1-5 are empirically grounded" → split into three provenance tiers
- [x] Line 100: Update footer to reflect tiered provenance
- [x] Remove "[M]" tags from Rules 3, 4, 6-10
- [x] Split rules into: Observed from instrument / Derived operational metrics / Modeling extensions
- [x] Remove architecture labels "MoE"/"dense" from all model references

### 6.9 Fix methodology page
**Audit §8 | File: `firebase/public/methodology.html`**

- [x] Line 44: Replace "probes how language models explore unfamiliar reasoning topologies" → "measures how coding-agent cost and verified outcome change as specification quality degrades"
- [x] Line 158: Remove "Claude: ~500B active (dense)"
- [x] Line 181: Remove "silent latent reasoning" language

### 6.10 Fix OG metadata across all pages
**Audit §24 | File: all 8 HTML files in `firebase/public/`**

- [x] Add `og:url` to every page
- [x] Replace inline `data:image/svg+xml` OG images with hosted 1200×627 PNG
- [x] Update `og:description` to match new positioning
- [x] Make `og:title` page-specific (e.g., "AI FinOps Dynamics — Page Name")

---

## Phase 7 — README & Repository Identity

### 7.1 Rewrite README
**Audit §17, §18, §20, §21 | File: `README.md`**

- [x] Remove Databricks badge (line 11) and first paragraph (lines 17-24)
- [x] New opening: "An open instrument measuring coding-agent economics as specification quality degrades"
- [x] Remove "The 10 Rules" table → replace with 3 key findings
- [x] Remove "deep/dense" architecture labels
- [x] Remove "69×" from header framing
- [x] Add Databricks in "Related Work" section at bottom

### 7.2 Update package identity
**Audit §21 | File: `pyproject.toml:7-8`**

- [x] name stays `reasoning-instrument` (breaking change risk)
- [x] description updated per item 4.1 above

---

## Summary

| Phase | Priority | Files affected | Blocks |
|-------|----------|---------------|--------|
| 1 | P0 | 4 existing + 2 new | Everything |
| 2 | P0 | Regeneration of all corpus | — |
| 3 | P1 | 9 existing + 1 new | — |
| 4 | P1 | 7 existing | — |
| 5 | P1 | 5 existing | — |
| 6 | P1 | 8 HTML files | — |
| 7 | P2 | 2 existing | — |

**Total: ~32 files, 7 phases. Done when every checkbox is marked.**
