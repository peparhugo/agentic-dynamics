# Blueprint v3 — AI FinOps Dynamics: Actual State & Next Steps

> **Superseded by `BLUEPRINT_v3.md`** — this doc ends at v0.9 / pre-spec next-steps. The
> ExperimentSpec + Compiler design (information-acquisition machine) is the current roadmap.
> See `code_reviews/2026-08-14_experiment-spec-and-compiler-design.md`.

**Status:** v0.9 complete. 26 cells, 122 sessions, 100% success, $0.19 DeepSeek spend. Lab Book 14 published.

---

## Part 1: Completed (v0.5 → v0.9)

### v0.5 — Instrument Core + Site Fixes

- [x] Round 1: Audit bugs (P0) — 5 fixes
- [x] Round 2: Site consistency + release hygiene (P1) — 12 fixes
- [x] Round 3: Golden Circle + value reframing — homepage, README, metadata
- [x] Package: reasoning-instrument → ai-finops-dynamics, heavy deps → optional
- [x] Deployed at ai-finops-rulebook.web.app

### v0.6 — Story Format + Analysis

| Module | Lines | Purpose | Tests |
|--------|-------|---------|-------|
| `mutation.py` | 313 | Flash V4 mutation compiler, 20 operators | 16 |
| `language.py` | 259 | tree-sitter multi-language (Python, TS, Go, Rust) | 12 |
| `story.py` | 1019 | Multi-session orchestrator, 3 built-in stories, auto-recovery | 20 |
| `commit_analysis.py` | 515 | Per-commit AST diff (git-based, fast), convention scoring | 11 |
| `review.py` | 554 | Agent review pool (commit, story, test gen, cross-model) | 12 |

### v0.7 — Architecture Analysis

| Module | Lines | Purpose | Tests |
|--------|-------|---------|-------|
| `entropy.py` | 353 | 5-dimension architectural entropy | 14 |
| `codebase_graph.py` | 356 | In-memory import graph metrics (no Neo4j required) | 11 |

### v0.8 — LSP + Conventions

| Module | Lines | Purpose | Tests |
|--------|-------|---------|-------|
| `lsp_diagnostics.py` | 400 | Multi-tool LSP (pyright, mypy, tsc, go-vet, cargo-check) | 18 |

### v0.9 — Experiment Pipeline & Execution

**Built:**
- PerturbationCondition enum (CLEAN, BAD_SEED, EARLY_DEGRADE, LATE_DEGRADE)
- condition_to_mutations() — maps conditions to mutation artifacts
- run_story.py CLI: --condition, --codebase-quality, --tier flags
- notification_service story (3rd built-in)
- 4 deterministic bad codebase variants (Python + TS × tier1 + tier2)
- 4 seed codebases (Python + TS × tier1 + tier2)
- Redis queue infrastructure (docker-compose + enqueue + worker + monitor)
- `--session --fork` auto-recovery in story.py _run_session()
- `recover_stories.py` — post-hoc session continuation

**Experiment executed:**
- 26 cells (4 missing: notification_service × tier2 — workers exited early)
- 122 sessions across 3 stories, 2 tiers, 2 qualities, 3 conditions
- 100% success after timeout recovery (8/8 original timeouts recovered)
- $0.1854 total DeepSeek spend (includes fork continuation costs)
- Flash V4 review agent ran on all 26 final session commits

**Lab experiment documented:**
- Lab Book 14: Multi-Session Story Review
- `experiments/lab_books/lab_story_review.md` — full methodology + results
- `scripts/lab_story_review.py` — analysis script
- `experiments/results/lab_story_review.json` — machine-readable output

**CI:** 14 test modules, 168 tests passing.

---

## Part 2: Deviations from Blueprint v2

| Blueprint v2 Said | Actual | Why |
|-------------------|--------|-----|
| 30 cells, 150 sessions | 26 cells, 122 sessions | 4 notification_service tier2 cells not enqueued |
| ~$3 cost | $0.19 | DeepSeek cheaper than estimated; fork costs included |
| Post-hoc timeout recovery script | Auto-recovery in `_run_session()` | `opencode run --session --fork` built in |
| 3 models by v1.0 | DeepSeek-only | User strategy: prove pipeline on cheapest model first |
| Flash V4 codebase mutators at runtime | Deterministic pre-generated bad variants | Flash V4 too slow for runtime codebase mutations |
| Docker Compose worker pool for production | Sequential + host-level Redis (batch_stories.py fallback) | Redis workers crashed from bash timeouts |

---

## Part 3: Current v0.9 Results

### By Condition

| Condition | Cells | Success | Avg Arch Fit | Avg Cost |
|-----------|-------|---------|-------------|----------|
| CLEAN | 17 | 100% | 0.75 | $0.009 |
| EARLY_DEGRADE | 8 | 100% | 0.69 | $0.003 |
| BAD_SEED | 1 | 100% | 0.88 | $0.003 |

### By Story

| Story | Cells | Success | Avg Correctness | Avg Cost |
|-------|-------|---------|-----------------|----------|
| task_manager_api | 11 | 100% | 0.72 | $0.012 |
| notification_service | 5 | 100% | 0.80 | $0.005 |
| static_site_gen | 10 | 100% | 0.80 | $0.003 |

**Note on static_site_gen convention:** Scores of 0.14-0.16 are a measurement artifact — the convention checker uses Python patterns on TypeScript files. Fix pending.

### Key Findings from Lab Book 14

1. **Condition does not degrade code quality.** Review scores comparable (0.69-0.75) across conditions.
2. **No cascade effects.** EARLY_DEGRADE cells maintained 100% test pass rates from session 1 to 5.
3. **Session 5 requires more time.** Cross-cutting tasks timed out at 1200s before auto-recovery was added. Now recovered automatically.
4. **Most common reviewer problems:** Infrastructure coupling (69%), missing type hints (57%), bare except blocks (46%).
5. **Review agent works at scale.** Flash V4 produces specific, quotable code reviews. 26 cells reviewed.

---

## Part 4: Current Limitations

| Limitation | Status |
|-----------|--------|
| Single model (DeepSeek V4 Pro) | No cross-model comparison |
| Single reviewer (Flash V4) | No inter-reviewer reliability |
| Convention scoring broken for TypeScript | Rules exist, not integrated |
| Binary correctness metric | Tests pass or don't — no gradation |
| 4 missing notification_service cells | Workers exited early |
| Agent-authored tests only | evaluator_independent=False |
| Codebase tiers 1-2 only (no medium/large) | Deferred |
| Go + Rust support (grammars exist, no stories) | Deferred |

---

## Part 5: Next Steps

### P0 — Fix Measurement Issues (Before Sharing)

| # | Task | Effort | Priority |
|---|------|--------|----------|
| 1 | Fix convention scoring for TypeScript — integrate `conventions/typescript.yaml` | 30 min | Blocking — current numbers are misleading |
| 2 | Complete 4 missing notification_service cells (tier2 variants) | 30 min + ~$0.01 | Completes the matrix |

### P1 — Cross-Model Comparison

| # | Task | Effort | Cost |
|---|------|--------|------|
| 3 | Run GPT-5.6 Luna (26 cells, same matrix) | 2-3 hours | ~$0.20 |
| 4 | Run Claude Sonnet 5 (26 cells, same matrix) | 3-4 hours | ~$10 |
| 5 | Cross-model review comparison lab book | 1 hour | $0 |
| 6 | Reviewer calibration (run same diff through 3 reviewers) | 30 min | ~$0.01 |

### P2 — Deeper Analysis

| # | Task | Effort |
|---|------|--------|
| 7 | Gradated correctness (parse session.jsonl for per-test results) | 1 hour |
| 8 | Add tier3_medium codebases (5000+ LOC forks) | 2 hours |
| 9 | Go + Rust story definitions | 2 hours |
| 10 | Evidence page from lab book data | 2 hours |
| 11 | Docker Compose worker pool debugging | 1 hour |
| 12 | v1.0 formal release + DOI | 1 hour |

### P3 — Scientific Rigor

| # | Task | Effort |
|---|------|--------|
| 13 | Held-out test generation (Flash V4 pre-experiment) | 1 hour |
| 14 | Inter-reviewer reliability (3 reviewers on same 10 cells) | 30 min + ~$0.05 |
| 15 | Statistical treatment (confidence intervals, effect sizes) | 2 hours |

---

## Part 6: Module Inventory

### New Modules (All Built)

```
src/instrument/mutation.py         313L   Flash V4 mutation compiler, 20 operators
src/instrument/language.py          259L   tree-sitter multi-language, 4 langs
src/instrument/story.py            1019L   Multi-session orchestrator, 3 stories, auto-recovery
src/instrument/commit_analysis.py   515L   Per-commit AST diff, convention scoring
src/instrument/review.py            554L   Agent review pool (5 agents)
src/instrument/entropy.py           353L   5-dimension architectural entropy
src/instrument/codebase_graph.py    356L   In-memory import graph metrics
src/instrument/lsp_diagnostics.py   400L   Multi-tool LSP diagnostics
```

### New Scripts

```
scripts/run_story.py         Story experiment CLI
scripts/analyze_stories.py   Post-hoc per-commit analysis
scripts/recover_stories.py   Session timeout recovery
scripts/review_stories.py    Batch review agent runner
scripts/batch_stories.py     Sequential matrix runner (fallback)
scripts/lab_story_review.py  Lab Book 14 analysis
scripts/enqueue.py           Redis job queue filler
scripts/worker.py            Redis experiment worker
scripts/monitor.py           Redis experiment monitor
```

### Assets

```
experiments/codebases/               4 seed codebases + 4 bad variants
experiments/lab_books/lab_story_review.md   Lab Book 14
experiments/results/stories/         26 story result JSONs
experiments/results/lab_story_review.json     Analysis output
conventions/python.yaml              Python convention rules
conventions/typescript.yaml          TypeScript convention rules (not yet integrated)
infrastructure/docker-compose.experiment.yml  Redis queue
```

---

## Part 7: Recommended Immediate Actions

Next session priorities, in order:

1. **Fix TypeScript convention scoring** — integrate `conventions/typescript.yaml` into `score_conventions()`. 30 minutes. Unblocks valid story-type comparisons.

2. **Complete missing 4 cells** — enqueue and run notification_service × tier2 variants. 30 minutes + ~$0.01. Completes the 30-cell matrix.

3. **Regenerate lab book** with fixed conventions and complete matrix. 5 minutes.

4. **Decide on Luna** — the first cross-model comparison is $0.20. Worth doing before Claude ($10) to validate that the pipeline works with a second model.

---

*Updated August 2026. Reflects actual built state, executed experiment, and documented deviations from Blueprint v2.*
