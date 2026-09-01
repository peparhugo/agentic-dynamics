---
status: accepted
---
# 2026-09-01 Test Suite Profile — the fat-test table, the per-family budget, the red triage, and the 132s profile

**Status: accepted** · Phase `test_suite_speed` p1 (profile + triage). Measurement only — no
fixes in this phase. The surgical-fix phase (p2) reads the fat-test table and the 132s profile
below as its input.

## Headline

The durations census over the whole suite (the prescribed command):

```bash
python3 -m pytest tests/ -q --durations=40 -p no:cacheprovider
```

| run | result | total | notes |
|---|---|---|---|
| **census 1** (clean, `--durations=40`) | **3 failed, 2955 passed, 9 skipped** | **598.64s (~10 min)** | the primary measurement |
| census 2 (`--durations=0`, full per-test) | 3 failed, 2955 passed, 9 skipped | 744.83s (~12 min) | ran under concurrent cProfile + an unrelated repo-wide pytest — ~25% inflation; used for the same-run family shares |
| profile run (single test, cProfile) | 1 passed | 134.16s | the 132s test under the profiler |

Suite size: **2,967 collected** (the workflow spec's "2,615" is stale — the suite has grown;
the grown tests are sub-second, so the headline total is unchanged).

**Concentration is the story:** the 15 tests over ~10s account for **~455s ≈ 76% of the
suite** — and the three real-subprocess/external-inference families (ollama + opencode +
workflow_runner) are **77% of the suite alone**. Speed is concentrated; the fat-test table is
the whole budget.

## (a) The fat-test table — every test over ~10s, with family share

Times are `call` durations. Census-1 is the clean measurement; census-2 is the same test in
the full-durations run. **Family share = census-2 test ÷ census-2 family total** (same-run
denominator, so the shares are internally consistent even though census 2 is inflated).

| # | test | census1 | census2 | family | family share |
|---|---|---|---|---|---|
| 1 | `test_workflow_runner.py::test_run_workflow_change_analysis_root_commit_never_fails` | 113.33s | 114.63s | test_workflow_runner | **71.5%** |
| 2 | `test_ollama_analyzer.py::TestOllamaAnalyzer::test_analyze_session_from_file` | 32.54s | 99.02s | test_ollama_analyzer | 34.0% |
| 3 | `test_ollama_analyzer.py::TestOllamaAnalyzer::test_summarize_experiment_basic` | 62.80s | 55.59s | test_ollama_analyzer | 19.1% |
| 4 | `test_ollama_analyzer.py::TestOllamaAnalyzer::test_batch_analyze_returns_string` | 41.71s | 53.24s | test_ollama_analyzer | 18.3% |
| 5 | `test_ollama_analyzer.py::TestOllamaAnalyzer::test_compare_sessions` | 38.49s | 49.46s | test_ollama_analyzer | 17.0% |
| 6 | `test_ollama_analyzer.py::TestOllamaAnalyzer::test_analyze_missing_file_does_not_crash` | 20.55s | 34.27s | test_ollama_analyzer | 11.8% |
| 7 | `test_opencode_analyzer.py::TestOpencodeAnalyzer::test_analyze_session_produces_result` | 22.52s | 42.27s | test_opencode_analyzer | 37.3% |
| 8 | `test_opencode_analyzer.py::TestOpencodeAnalyzer::test_analyze_session_loads_metrics` | 25.86s | 30.89s | test_opencode_analyzer | 27.3% |
| 9 | `test_opencode_analyzer.py::TestOpencodeAnalyzer::test_compare_sessions_produces_result` | 20.14s | 27.35s | test_opencode_analyzer | 24.2% |
| 10 | `test_opencode_analyzer.py::TestOpencodeAnalyzer::test_batch_analyze_produces_result` | 15.57s | 12.68s | test_opencode_analyzer | 11.2% |
| 11 | `test_checkpoint_mechanism.py::test_revamp3_unsigned_template_is_refused` | 13.31s | 14.03s | test_checkpoint_mechanism | 92.3% |
| 12 | `test_relabel_tree_gate.py::test_relabel_with_operator_approval_passes` | 12.31s | 13.17s | test_relabel_tree_gate | 25.2% |
| 13 | `test_relabel_tree_gate.py::test_approval_committed_during_the_phase_is_not_an_approval` | 12.57s | 13.05s | test_relabel_tree_gate | 25.0% |
| 14 | `test_relabel_tree_gate.py::test_relabel_without_approval_fails_with_identical_tree_proof` | 12.37s | 12.97s | test_relabel_tree_gate | 24.9% |
| 15 | `test_relabel_tree_gate.py::test_materialized_attempt_a_reproduces_the_exact_tree` | 10.84s | 11.91s | test_relabel_tree_gate | 22.8% |

Notes:
- **#1 is exactly the workflow spec's fat test** — 113-135s across the three measurements
  (the spread is the sonar-scanner JVM, not noise). Its family share is ~71% either way.
- **The #2-#10 external-inference tests are high-variance** (e.g. #2: 32.5s ↔ 99.0s) — real
  model-call latency (Ollama `deepseek-r1:1.5b` at localhost:11434; real opencode sessions on
  `deepseek-v4-flash`). All are `pytest.mark.external`.
- The whole **test_relabel_tree_gate family is fat**: its 4 git-materialization tests are each
  ~12-13s and together are 98% of that family — real `git worktree` subprocess materialization
  of an attempt-A tree, repeated per test.
- `test_checkpoint_mechanism` is 92% one test — the revamp3 refusal test, which runs a real
  workflow run (real git + the runner) to assert the unsigned-template refusal.

## (b) The per-family time budget

From the full-durations run (census 2). **The whole suite is 6 families.** Everything else is
≤1.2s per file.

| family | time | share | tests | what it runs |
|---|---|---|---|---|
| `test_ollama_analyzer.py` | **291.6s** | **39.8%** | 5 | real Ollama model inference (`localhost:11434`, `deepseek-r1:1.5b`) — marked `external` |
| `test_workflow_runner.py` | **160.3s** | **21.9%** | 70 | the change-analysis seam's sonar-scanner legs (the 113-135s test) + the watchdog family (real subprocess agents, 2.3-5.6s each) |
| `test_opencode_analyzer.py` | **113.2s** | **15.5%** | 8 | real opencode sessions (`deepseek-v4-flash`) — marked `external` |
| `test_relabel_tree_gate.py` | **52.2s** | **7.1%** | 14 | real `git worktree` subprocess materialization (98% of it is the 4 fat tests) |
| `test_checkpoint_mechanism.py` | 15.2s | 2.1% | 12 | real workflow runs through the runner (92% is the revamp3 refusal test) |
| `test_lab_contract.py` | 14.4s | 2.0% | 5 | registry/corpus reads |
| everything else (133 files) | ≤ 10s/file | ≤ 1.5% each | — | — |

Not-fat, contrary to the workflow spec's guess: the **admission family** (`test_admission*` +
`test_lease_registry`) is ~1.2s total, and **docs_health** is ~0.4s. The store/subprocess-heavy
files are the four fat families above, not the admission/docs guard families. The sub-minute
guard family (doc_lifecycle, dependency_direction, script_classification, agent_config_render,
spec_status) is confirmed sub-minute and is a clean `fast`-marker candidate for p3.

## (c) TRIAGE THE REDS — reproduce, classify, record (not fixed in this phase)

The workflow spec recorded "2 reds observed at ~58%/~60%". The census finds **3 live
failures** — all deterministic, all reproduced twice (both full-suite runs) and in isolation.

### Red 1 — `tests/test_publication_singular_door.py::test_readme_figures_match_public_statistics`
- **Reproduce:** fails alone in 0.20s; fails at HEAD in both censuses.
- **Classification: REAL, inherited.** Deterministic, not order-dependent, not environmental.
- **Root cause:** the README "By the Numbers" table's reconstructed row
  `| Experiment + workflow specs | 163 (11 experiments + 152 workflows) |` is not present.
  The README carries `175 (11 experiments + 164 workflows)`.

### Red 2 — `tests/test_repo_hygiene.py::test_no_conflict_markers_in_tracked_files`
- **Reproduce:** fails alone in 0.20s; fails at HEAD in both censuses.
- **Classification: REAL, inherited.** Deterministic.
- **Root cause:** committed git merge-conflict markers
  (`<<<<<<< HEAD` / `=======` / `>>>>>>> 9d2c3c57d`) in
  `docs/reviews/docs_architecture_refresh_remediation.md` — 9 hunks, shipped by the merge
  `33a4e7f7d`. A genuinely un-resolved conflict artifact in history.

### Red 3 — `tests/test_repo_hygiene.py::test_readme_by_the_numbers_matches_public_statistics`
- **Reproduce:** fails alone in 0.20s; fails at HEAD in both censuses.
- **Classification: REAL, inherited.** Deterministic.
- **Root cause:** the same two-way publication drift as Red 1, in both directions:
  - specs: README `[175, 11, 164]` vs data.js `[163, 11, 152]` — README is **fresh** (synced to
    the current `experiments/specs/index.json`, 175 total at commit `508926082`); data.js is
    **stale** (built at `110d297f6` when the index was 163).
  - lab books: README `[20, 8, 12]` vs data.js `[21, 8, 12]` — data.js is **fresh** (the
    lab manifest has 21 entries); the README's 20 is stale.

**Triage verdict:** all three are **REAL** (deterministic, present at HEAD, reproduced across
two independent full-suite runs and isolated reruns — none flaky, none inherited-from-this-phase).
Two (Red 1 + Red 3) share one root cause — the README "By the Numbers" block and the generated
`data.js` `public_statistics` disagree because the two publication surfaces last regenerated at
different times (`data.js` at the p5_suite_and_closure build, the README at the later spec-count
sync); Red 2 is an independent hygiene violation (a merge shipped an unresolved conflict file).
Per the phase's hard rule, **none are fixed here** — p2 is the fixing phase.

## (d) The 132s test profile — the change-analysis seam on a fresh tmp repo

Target: `test_run_workflow_change_analysis_root_commit_never_fails`. Measured 113.33s (census
1), 114.63s (census 2), 134.16s under cProfile. `cProfile`:

```
run_workflow                                     133.87s
└── _run_change_analysis   (4 calls)              132.65s
    └── _call_with_deadline  (6 calls)            132.50s   ← pure thread-join wait
        ├── _sonar_evidence  (3 legs)             126.13s   ← the O(slow) step
        └── _lsp_evidence    (3 legs)               6.37s
```

**The O(slow) step is the change-analysis seam's SONAR leg — an external-service subprocess,
not a git walk, not graph contact, not evidence context.** `_sonar_evidence` →
`run_sonar_analysis` launches the real `sonar-scanner` JVM (`/home/drseuss/.local/bin/sonar-scanner`
6.2.1.4610) against the **live SonarQube at `http://localhost:9000`** (200 OK in 2ms) for every
non-root committing phase. Direct timing on a 3-line repo: **33.4s** for one scanner run. The
worktree being "fresh" is irrelevant — the scanner boot + analysis cost dominates, not repo size.

Two nuances the profile makes explicit:
1. **The root-commit phase itself is cheap.** The test's name points at the root commit, but the
   root phase (phase 1) skips both legs — the seam's `before_rev` git read (`git ls-tree
   {full}^`) raises for a root commit (the parent revision does not exist) and
   `_run_change_analysis` degrades to `None` before the sonar/mypy legs run. The 3 sonar legs
   come from the 3 **non-root** phases (`ux_design`, `implement`, `verify`), each running a full
   scanner analysis (~33-42s) + a mypy leg (~2s each). The assertion the test actually proves —
   root-commit phases degrade to `change_analysis=None`, never fail — is the cheap part.
2. `cProfile` does not descend into worker threads (`_call_with_deadline` runs each leg in a
   `ThreadPoolExecutor`), so the sonar leg's internals were named by direct timing instead.

**p2 implication:** the cost is bounded by the seam's external legs, not by the test. A surgical
fix that keeps the assertion's proof has to make the sonar/lsp legs injectable or skippable in
unit tests (a fake analyzer already makes `analyze` cheap — the runner still pays `_sonar_evidence`
before calling it), or scope the legs' invocation; a weakened assertion is a violation.

## Measurement method (provenance)

- Census 1: the prescribed command, clean (no concurrent load). Total 598.64s.
- Census 2: `--durations=0` for the complete per-test list; ran while cProfile + an unrelated
  repo-wide pytest were also running (~25% inflation). Used only for same-run family shares and
  the per-family budget; absolute fat-test numbers are census-1.
- Profile: `python3 -m cProfile -o root_commit.prof -m pytest
  tests/test_workflow_runner.py::test_run_workflow_change_analysis_root_commit_never_fails -q`,
  analyzed with `pstats`; sonar internals confirmed by direct timing.
- Environment facts: `sonar-scanner` 6.2.1.4610 on PATH; SonarQube reachable at localhost:9000;
  Ollama reachable at localhost:11434 (all `external`-marked analyzer tests ran, none skipped).
- Configuration note (not this phase): pytest warns `Unknown config option: timeout` on every
  run — a `pyproject`/`pytest.ini` cleanup candidate for the fast-path phase (p3).

## p2-p4 results — the surgical fixes, the fast path, the gate (accepted 2026-09-01)

**p2 — surgical fixes (every fix keeps its assertion's semantic force — both directions
verified: the fixed test passes AND still fails on a deliberately broken input).**

| fix | before | after | how |
|---|---|---|---|
| `test_run_workflow_change_analysis_root_commit_never_fails` | 113.33s (the 71.5% fat test) | **0.72s** | `run_workflow(..., change_analysis_legs=False)` scopes the external sonar/lsp legs (the p1 profile's O(slow) step — real sonar-scanner + mypy subprocess windows); the seam's core proof — typed snapshots/delta + analyzer + root-commit degradation — runs identically. The legs' correctness stays covered by `test_sonar_evidence_*`/`test_lsp_evidence_*`. |
| watchdog family (9 tests) | 24.85s | **17.16s** | shorter per-step waits (0.3→0.15s) + fewer iterations in the compliant/forged tests; the stall semantics hold (a stalled agent still fails at the 1.8s threshold with STALLED evidence; a compliant agent is never killed). |
| `run_suite` scoped mode | — | — | `run_suite(..., target=[...])` runs the declared file(s)/node ids, never the whole tree. The runner's `kind: test` phase (and `test_gate`) reads the phase's `tests:` field. `retrieval_activation_augment_proof.yaml` now declares `tests: [test_calc.py]` — its 600s-wall failure mode is structurally impossible. Verified: a scoped test phase runs its 3 tests in seconds; a broken target still fails the phase. |
| `test_relabel_tree_gate.py` (4 fat tests) | 12.2-12.5s each | **~3.7s each** | the 298MB attempt-A tree is materialized ONCE per module (fixture), the replay tests hardlink-copy it (`copytree(copy_function=os.link)`); family 49.1s → 26.4s. The byte-identical-tree proof is unchanged (the tree IS `REVAMP2_TREE` by construction). |
| `test_checkpoint_mechanism.py::test_revamp3_unsigned_template_is_refused` | 13.31s | **~0.3s** | the revamp3 replay uses a minimal worktree + the REAL unsigned template content (`git show ee12c9c5b:...`); family 15.2s → 1.4s. The contract-refusal proof (`authored_after_checkpoint`) is unchanged. |

**p2 reds fixed (the p1 triage's 3 REAL failures, now green).** (1)+(3) the README/data.js
two-way publication drift: `data.js` regenerated from the current spec index + lab manifest
(175 specs / 21 labs) and the README's stale `20` lab count corrected to `21`. (2) the committed
git conflict markers in `docs/reviews/docs_architecture_refresh_remediation.md`: all 8 conflict
blocks resolved to the incoming `9d2c3c57d` side (the implemented + closure-evidence state the
merge should have shipped).

**p3 — the fast path.** The `fast` marker on 39 audited modules (the sub-minute guard family +
pure-unit families); `bash scripts/test_fast.sh` (`pytest tests/ -m fast`) runs **509 tests in
~25s** (budget: sub-3-minutes). The parallel-safety audit selected only modules with no real
subprocesses / Redis / stores / ports / real git worktrees / sleeps; the audit is now a durable
guard in `tests/test_fast_path_gate.py`. `pytest-timeout` installed — the `Unknown config option:
timeout` warning is gone.

**p4 — the gate.** `tests/test_fast_path_gate.py`: the fast path must stay under 180s (3x the
measured time — a slow-regression trip wire, not a flaky wall), every `fast`-marked module must
pass the parallel-safety audit, and the full suite must still collect on demand. Budgets
documented in `scripts/CONTEXT.md` + this doc. `test_workflow_runner.py` total: 187.04s → 38.49s.
Final deterministic (non-external) suite: **2856 passed, 0 failed, ~183s** — the 3 p1-triaged
reds are green; the fast path (509 tests) is ~25s. The whole suite incl. the external-inference
families stays runnable on demand (`python3 -m pytest tests/ -q` → 2964 passed, 9 skipped).
