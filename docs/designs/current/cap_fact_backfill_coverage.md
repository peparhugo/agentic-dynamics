---
status: accepted
---
# CAP Fact Backfill — Corpus Inventory (Stage 1, p1)

**Spec:** `workflows/repository/cap_fact_backfill.yaml` (phase `p1_corpus_inventory`)
**Branch:** `feature/cap-fact-backfill`
**Date:** 2026-08-24 (re-audit 2026-08-24) · **Model:** deepseek/deepseek-v4-flash (single-model, `--backend opencode`)
**Question:** Enumerate the full experiment corpus exhaustively — workflow runs, story cells,
summary entries — record shape variance per source, and publish the master artifact table.

**Planned sections:** §1 master artifact table (p1) · §2 variance report (p1) · §3 per-predicate
coverage table (p2) · §4 E1-E4 evaluability (p2) · §5 additive derivation (p3) · §6 backfill run
record (p4) · §7 verification (p5) · §8 adversarial review + release verdict (p6).

---

## 3. Per-predicate coverage table (p2)

Registry truth: `FACT_PREDICATES` (`src/agentic_dynamics/control/facts.py`) currently holds **39
predicates** — the "29" in the pre-addendum design predates the I8/I9/I10 additions
(`pattern`, 7 `checkpoint_*`, 2 `profile_*`). This table covers all 39; the 13-predicate minimum
list from the spec is a strict subset (marked **★**).

**Verdict rule (coverage is truth, no force-derive):** per predicate, over its natural host
family — **PRODUCED** when the host family's raw source is present on 100% of units; **PARTIAL**
when 0 < n_available < n_total (gap named); **UNOBSERVED** when n_available == 0 (finding +
named instrumentation gap; for workload predicates a *structural zero* — e.g. no spec is
superseded — is recorded as such, never fabricated). Every n_available/n_total is reproduced from
the §1 census command (workflow: 455 phases / 125 runs; story: 1112 sessions / 227 cells; summary:
144 entries; spec index: 103 specs). For emit-gated predicates (facts emitted only on a non-empty
value), n_available counts the **emit-ready** units — the count the reducer will actually produce —
not bare key presence.

**Re-audit corrections (2026-08-24, against the live corpus + reducers):** §3a `phase_commit`
downgraded PRODUCED → **PARTIAL** (reducer `attempt_facts.py:195` emits only on non-empty
`commit_hash`; 207/455 workflow phases carry an empty string — 179 ok + 28 failed — and 1/1112
story session has none); §3b `current_commit` count 224/227 stands but the 3 gap cells are
**claude-sonnet-5 zero-session cells** (mutation commit failure), not deepseek-v4-pro; §3d
`allowed_models` is **16/103** (was 11/103). All other verdicts unchanged.

### 3a. Attempt-scope predicates (`attempt_facts/v1`)

| Predicate | Workflow (455 phases) | Story (1112 sessions) | Summary (0 attempts) | Verdict | Gap / finding |
|---|---|---|---|---|---|
| **★ phase_status** | 455/455 (`status`) | 1112/1112 (`exit_code` proxy) | 0 | **PRODUCED** | — |
| **★ phase_test_verified** | 7/455 (`test_executed_success` non-null) | 92/227 cells (40%) | 0 | **PARTIAL** | only the 7 test-kind phases carry a bool; agent phases stamp `None`; story carries it cell-level only |
| **★ attempt_cost_usd** | 455/455 | 1112/1112 | 0 | **PRODUCED** | — |
| **★ attempt_tokens_in** | 448/455 (`tokens.in`) | 0/1112 | 0 | **PARTIAL** | story sessions record flat `total_tokens`, no in/out split; 7 test-kind phases have `tokens={}` |
| **★ attempt_tokens_out** | 448/455 (`tokens.out`) | 0/1112 | 0 | **PARTIAL** | same as above |
| **★ attempt_model** | 455/455 | 1112/1112 (via cell, 227/227) | 144/144 | **PRODUCED** | — |
| **★ phase_commit** | 248/455 (`commit_hash` non-empty; 207 empty-string) | 1111/1112 (1 session empty) | 0 | **PARTIAL** | reducer emits only on non-empty commit; 207 workflow phases (179 ok + 28 failed) + 1 story session record no commit |
| **★ attempt_cache_hit_rate** | 401/455 (`cache_hit_rate`; 388 non-zero) | 227/227 cells (summary rollup) | 0 | **PARTIAL** | 54 pre-instrumentation workflow phases lack cache fields; story value is a cell-level rollup, not per-session |
| **★ attempt_confidence** | 355/455 (78%) | 401/1112 (36%; 44 explicit nulls) | 0 | **PARTIAL** | 100 workflow phases (failed-before-call + pre-instrumentation) + 711 story sessions lack confidence |

### 3b. Job-scope predicates (`job_facts/v1`)

| Predicate | Workflow (125 runs) | Story (227 cells) | Summary (144 entries) | Verdict | Gap / finding |
|---|---|---|---|---|---|
| **★ job_status** | 125/125 (`ok`) | 227/227 (`summary.all_successful`) | 0/144 | **PRODUCED** | summary entries have no ok/status field |
| **★ job_accumulated_cost_usd** | 125/125 (`total_cost_usd`) | 227/227 (`summary.total_cost`) | 144/144 (`cost`) | **PRODUCED** | — |
| job_n_phases | 125/125 (`phases`) | 227/227 (`sessions`) | 0/144 | **PRODUCED** | — |
| **★ current_commit** | 125/125 (`git_sha`) | 224/227 (last non-empty session `commit_hash`; 3 cells have zero sessions — mutation commit failure, claude-sonnet-5 bad_seed) | 0/144 | **PRODUCED** | the 3 gap cells (`task_manager_api_claude_sonnet_5_bad_seed_{d2699ca6122b,b0a1988763f8,8a623367c3f4}`) never got a session, so no commit exists to cite |

### 3c. Workflow-scope predicates (`workflow_facts/v1`) — derived from run phases, 125/125 PRODUCED

| Predicate | Workflow | Verdict |
|---|---|---|
| workflow_status | 125/125 | **PRODUCED** |
| workflow_health | 125/125 | **PRODUCED** |
| workflow_phases_completed | 125/125 | **PRODUCED** |
| workflow_phases_remaining | 125/125 | **PRODUCED** |
| projected_budget_overrun | 125/125 (needs `budget_usd` — present 103/103 specs) | **PRODUCED** |

### 3d. Workload-scope predicates (spec index / spec configs / profiles / pattern / checkpoint)

| Predicate | Host (n_total) | n_available | Verdict | Gap / finding |
|---|---|---|---|---|
| **★ spec_status** | spec index (103) | 103/103 | **PRODUCED** | — |
| spec_n_runs | spec index (103) | 103/103 | **PRODUCED** | — |
| spec_last_run_at | spec index (103) | 83/103 | **PARTIAL** | 20 specs never ran (structural, not a gap) |
| spec_latest_ok | spec index (103) | 83/103 | **PARTIAL** | same |
| spec_latest_model | spec index (103) | 83/103 | **PARTIAL** | same |
| spec_latest_cost_usd | spec index (103) | 83/103 | **PARTIAL** | same |
| spec_supersedes | spec index (103) | 0/103 | **UNOBSERVED** | structural zero — no spec supersedes another in the corpus |
| spec_superseded_by | spec index (103) | 0/103 | **UNOBSERVED** | structural zero — no spec is superseded |
| max_spend_usd | spec YAMLs (103) | 103/103 | **PRODUCED** | — |
| max_attempts | spec YAMLs (103) | 102/103 | **PARTIAL** | 1 spec declares no max_attempts |
| allowed_models | spec YAMLs (103) | 16/103 | **PARTIAL** | 16 specs declare `model_pool`/`allowed_models` (`workflows/operations`×3, `workflows/repository`×11, `workflows/research`×2) |
| domain_profile_version | profiles/v1 | 0 | **UNOBSERVED** | profiles/v1 has no producer call site (only declarations in `control/profiles.py`) |
| challenge_profile_version | profiles/v1 | 0 | **UNOBSERVED** | same |
| pattern | pattern/v1 | 0 | **UNOBSERVED** | pattern/v1 has no minting call site — nothing learns patterns yet |
| session_checkpoint | checkpoint/v1 | 0 | **UNOBSERVED** | 11 raw `context_snapshot` artifacts exist but no `checkpoint/v1` facts emitted (needs `--cap-snapshot`) |
| checkpoint_present | checkpoint/v1 | 0 | **UNOBSERVED** | same |
| checkpoint_goal_unchanged | checkpoint/v1 | 0 | **UNOBSERVED** | same |
| checkpoint_phase_unchanged | checkpoint/v1 | 0 | **UNOBSERVED** | same |
| checkpoint_model_unchanged | checkpoint/v1 | 0 | **UNOBSERVED** | same |
| model_change_required | checkpoint/v1 | 0 | **UNOBSERVED** | same |
| checkpoint_snapshot_identity | checkpoint/v1 | 0 | **UNOBSERVED** | same |

### 3e. Verdict counts (39 predicates)

| Verdict | Count | Predicates |
|---|---|---|
| **PRODUCED** | 15 | phase_status, attempt_cost_usd, attempt_model, job_status, job_accumulated_cost_usd, job_n_phases, current_commit, workflow_status, workflow_health, workflow_phases_completed, workflow_phases_remaining, projected_budget_overrun, spec_status, spec_n_runs, max_spend_usd |
| **PARTIAL** | 12 | phase_test_verified, attempt_tokens_in, attempt_tokens_out, attempt_cache_hit_rate, attempt_confidence, phase_commit, spec_last_run_at, spec_latest_ok, spec_latest_model, spec_latest_cost_usd, max_attempts, allowed_models |
| **UNOBSERVED** | 12 | spec_supersedes, spec_superseded_by, domain_profile_version, challenge_profile_version, pattern, session_checkpoint, checkpoint_present, checkpoint_goal_unchanged, checkpoint_phase_unchanged, checkpoint_model_unchanged, model_change_required, checkpoint_snapshot_identity |

Of the 13 minimum predicates: **8 PRODUCED, 5 PARTIAL** (attempt_tokens_in/out, attempt_confidence,
attempt_cache_hit_rate, phase_test_verified, phase_commit), **0 UNOBSERVED**. The two genuinely missing *observable*
predicates (spec_supersedes/spec_superseded_by) are structural zeros of the corpus, not
instrumentation gaps. The three named instrumentation gaps for the backfill's additive work:
**story-session token split** (flat `total_tokens` only), **per-session test_executed_success**
(cell-level only, 92/227), **per-session confidence** (401/1112, 36%) — plus the empty-string
`commit_hash` on 207 workflow phases (emit-gated `phase_commit`).

## 4. E1-E4 evaluability (p2)

Per routing-evidence spec (E1 `cap_shadow_comparison`, E2 `cap_confidence_cascade`, E3
`cap_coverage_routing_impact`, E4 `cap_grit_strength_grid`) — which `requires_facts` each carries
(§3 coverage) and the resulting evaluability verdict.

| Experiment | Binding `requires_facts` | Coverage state | Evaluability | Blocking predicate |
|---|---|---|---|---|
| **E1** cap_shadow_comparison | attempt_cost_usd, phase_status, phase_test_verified, attempt_model | cost/status/model **PRODUCED**; `phase_test_verified` **0/3 in E1's own run** (the cap_shadow_campaign ledger has 3 agent phases, none test-kind) | **Inconclusive-by-design** — the cost/status/model/confidence dimensions are evaluable (3/3 phases), but no verified-outcome fact can be minted for the shadow run; the `verified_outcome` / `*_cost_per_verified_outcome` rules cannot produce | **phase_test_verified** |
| **E2** cap_confidence_cascade | attempt_confidence, phase_status, job_status, attempt_cost_usd, attempt_model | status/job/cost/model **PRODUCED**; `attempt_confidence` **PARTIAL** (355/455 workflow, 78%) | **Evaluable with caveat** — the retrospective cascade is estimable over the 355 confidence-carrying phases, but the 100 missing phases (failed-before-call + pre-instrumentation runs) make the confidence-gated comparison **inconclusive-by-design** for that 22% (selection-on-confidence bias) | **attempt_confidence** |
| **E3** cap_coverage_routing_impact | none — all rules `requires_facts: []` | not fact-gated; raw inputs exist (868 finding artifacts, 144 summary entries, 49 valid entry block) | **Evaluable** — coverage-corrected vs legacy routing is computed directly from the finding/summary corpus; no fact predicate blocks it | — |
| **E4** cap_grit_strength_grid | none declared (reads its own ledger) | in-ledger `perturbation_strength` **9/9** + `test_executed_success` **9/9**; grid already executed (8 cells, 9 attempts, 7 accepted, 1 failed, realized $31.27) | **Evaluable** — E4's own ledger fully covers its two binding signals; corpus-wide story coverage of those predicates is PARTIAL (92/227 cells), a gap for *future* grids, not for the completed one | — |

**Cross-cutting evaluability findings (do not block p3, but are the p3/p4 targets):**
1. **`phase_test_verified`** is the single weakest predicate for E1's verified-outcome dimension — its
   instrumentation gap is that agent phases stamp `test_executed_success: None` and story cells carry
   it cell-level only (92/227). Nothing can force-derive a verified outcome where the suite never ran
   (never-touch-inflight + coverage-is-truth).
2. **`attempt_confidence`** gates E2's fidelity at 78% (workflow) / 36% (story sessions); the story
   session gap (711 sessions without confidence) is a named p3 instrumentation target.
3. E3 and E4 are not fact-plane-gated; their evaluability is data-completeness-driven, not
   predicate-coverage-driven.

**PASS** — coverage table + verdicts + evaluability grounded entirely in the §1 master table
(no invented observations; every n_available/n_total reproduced by a shown command). In-flight
worktrees untouched.

**Re-audit (2026-08-24):** every n_available/n_total re-derived against the live corpus + reducer
emit-gates. §4 verdicts stand unchanged: E1 inconclusive-by-design (its own run's 3 phases are all
agent-kind, `phase_test_verified` 0/3 — verified from `cap_shadow_campaign/20260824T000708Z.json`),
E2 evaluable-with-caveat (355/455 confidence, 78%), E3 evaluable (not fact-gated), E4 evaluable
(in-ledger 9/9 `perturbation_strength` + 9/9 `test_executed_success`, 8 cells / 9 attempts /
$31.27). Corrections landed: `phase_commit` PARTIAL (248/455 workflow, 1111/1112 story),
`current_commit` gap attribution = 3 claude-sonnet-5 zero-session cells, `allowed_models` 16/103.

---

## 0. Corpus location (reproducibility note)

`experiments/results/workflows/` is **gitignored** (`.gitignore:27`), so a fresh checkout has zero
run ledgers (this is by design — `experiments/specs/STATUS.md` documents "missing data is normal").
The canonical run-ledger corpus lives in the **main worktree** and is exactly the path the fact
producer's `load_run_jsons()` reads (`scripts/kb_produce_facts.py:125`,
`REPO_ROOT / experiments / results / workflows`):

```
$ ls experiments/results/workflows/          # in the current (feature/cap-fact-backfill) worktree
ls: cannot access 'experiments/results/workflows/': No such file or directory
$ find /home/drseuss/ai-finops-framework/experiments/results/workflows -name '*.json' | wc -l
125
```

Every count below is produced by the single reproducible census command at the end of §1 and is
re-derivable from it. In-flight worktrees untouched (no diff; this phase reads only).

## 1. Master artifact table

Run one census over the three declared families plus the tracked E4 grid ledger
(`python3 - <<'PY' ... PY` reading the main-worktree corpus):

| Family | Location | Artifacts | Unit count | Distinct spec/story | Models |
|---|---|---|---|---|---|
| **A — workflow runs** | `experiments/results/workflows/<spec>/*.json` (gitignored; main worktree) | 125 ledger files = **125 distinct run dicts** (0 byte-duplicates) | **455 phases** (427 ok, 28 failed; 448 agent + 7 test) | 88 specs | 8 |
| **B — story cells** | `experiments/results/stories/*.json` (tracked) | 227 cell files | **1112 sessions** | 3 stories (`task_manager_api`, `static_site_gen`, `notification_service`) | 7 |
| **C — summary entries** | `experiments/results/_results_summary.json` (tracked) | 1 file, **144 entries** (107 distinct `experiment`; 144 distinct `worktree_name`) | 0 attempts (no attempt structure) | 5 models | 5 |
| **D — E4 grid ledger** (supplementary) | `experiments/results/cap_grit_grid_ledger.json` (tracked) | 1 file | **8 cells, 9 attempts** | spec `cap_grit_strength_grid@0.1` | 1 (claude-sonnet-5) |

**Workflow-run shape (per run):** `spec_name`, `spec_id`, `model`, `workdir`, `goal`, `git_sha`
(125/125), `started_at`, `ended_at`, `total_cost_usd` (125/125, **0 None**), `ok` (96/125 True),
`phases[]`. Per phase: `phase`, `kind`, `status`, `spec_id`, `model`, `duration_s`,
`commit_hash` (455/455), `error`, `tokens` (nested dict 455/455), `cost_usd` (455/455, **0 None**),
`cache_read_tokens` (401/455), `cache_write_tokens`, `cache_hit_rate`, `session_id` (401/455),
`files_created`, `files_modified`, `confidence` (364/455), `raw_prompt_hash`, `pre_phase_commit`,
`retrieval_attempt_id`, `constructor_attempt_id`, `selected_evidence_ids`, `augmentation_*`,
`fallback_mode`, `test_executed_success` (455/455), `tests_passed`, `tests_total`.

**Story-cell shape (per cell):** `story_name`, `story_id`, `codebase_path`, `language`, `model`,
`mutation_id` (227/227), `perturbation_condition`, `started_at`, `completed_at`, `worktree`,
`error` (10 non-empty), `summary` (227/227), `sessions[]`. Per session: `session_number`,
`task_type` (1112/1112), `prompt`, `commit_hash`, `commit_message`, `cost_usd` (1112/1112, **0
None**), `total_tokens` (flat scalar 1112/1112), `duration_s`, `files_changed`, `exit_code`
(1112/1112), `error`, `continuation_used` (9), `continuation_cost_usd`, `subagent_cost_usd`,
`subagent_sessions` (11), `test_count`, `test_lines`, `code_lines`, `agentic`. Cell-level
`perturbation_strength` (92/227) + `test_executed_success` (92/227) on the newer instrumentation.

**Summary-entry shape (per entry):** `experiment`, `worktree_name`, `model`, `operator` (None 95 /
perturbed 38 / baseline 11), `perturbation_class`, `narration_failure` (95 True), `cost` (144/144,
0 None), `output_tokens` (95), and the valid-entry measurement block on **49/144** entries only
(`tokens_input`/`tokens_output`/`evaluator_independent`/`test_results`/`ast`/sonar metrics —
matches `_meta.valid_entries: 49`). **No `attempts[]`, no `operators`, no `confidence`.**

**E4 grid ledger (per attempt):** `job_id`, `spec_id`, `policy_arm` (grit_retry/baseline), `model`,
`condition`, `strength`, `perturbation_strength` (9/9), `attempt_id`, `attempt_number`,
`parent_attempt_id`, `retry_reason`, `started_at`, `ended_at`, `actual_cost`, `rework_cost`,
`test_executed_success` (9/9), `status`, `story_id`, `worktree`, `mutation_id`, `result_path`.
**No confidence, no token counts.**

## 2. Variance report

**2a. Field coverage across sources** — which sources carry the four load-bearing signals:

| Signal | Workflow phase (455) | Story session (1112) | Story cell (227) | Summary entry (144) | E4 grid attempt (9) |
|---|---|---|---|---|---|
| `confidence` | **364 (80%)** | 445 (40%; 44 are `null`) | 0 | 0 | 0 |
| `cache_read_tokens` | **401 (88%)** | 0 (flat `total_tokens` only) | — | 49 (valid set) | 0 |
| `test_executed_success` | **455 (100%)** | 0 | **92 (40%)** | 0 | **9 (100%)** |
| `perturbation_strength` | 0 | 0 | **92 (40%)** | 0 (has `operator`/`perturbation_class`) | **9 (100%)** |

**2b. Tokens: flat vs nested.**
- Workflow phases: **nested** `tokens` dict (`in/out/reasoning/answer/explanation/total`) on 455/455
  — the full Explanation-Tax split is present. `cache_read_tokens` on 401/455 (the 54 without it
  are pre-cache-instrumentation runs).
- Story sessions: **flat** scalar `total_tokens` on 1112/1112, **no nested `tokens`**, no token
  split, no cache fields.
- Summary entries: flat `tokens_input`/`tokens_output`/`tokens_reasoning`/`tokens_cache_*` on the
  49 valid entries only.
- E4 grid attempts: **no token fields at all.**

**2c. Cost presence.** No `None` costs anywhere: workflow phases 455/455 present, story sessions
1112/1112 present, summary entries 144/144 present. **F1 structural-zero exposure confirmed in the
workflow family:** 35 phases record `cost_usd == 0.0`, of which **17 are `status="failed"` with an
all-zero `tokens` block** (`in/out/reasoning/answer/explanation/total` all 0) — failed-before-call
phases whose `0.0` is a *structural* zero, not a *measured* zero. (The 18 non-failed zero-cost
phases are the 7 `kind="test"` phases plus 11 zero-work agent phases.) The F1 fix (record such
phases' cost as `None`/uncaptured) is a p4 concern; p1 only measures the exposure.

**2d. Other shape variance.**
- Story `perturbation_condition` is dirty: 6 cells carry `""` and 3 carry string `"None"`
  (all deepseek-v4-pro) — a derived condition for those 9 cells must treat absent condition as
  absent, not fabricate one.
- Confidence value type in workflow phases and story sessions is `float | None` (44 story-session
  `null`s).
- 9 story sessions used `continuation_used`; 11 carry `subagent_sessions` — the session→attempt
  1:1 mapping has exceptions that per-attempt derivation must not flatten silently.
- `git_sha` present on all 125 workflow runs; `session_id` on 401/455 phases (the run-identity
  anchor for provenance).

**2e. Counts per family (the LOG).**

| Family | Runs/Cells | Sessions/Phases/Attempts | Carry confidence | Carry test_executed_success | Carry perturbation_strength |
|---|---|---|---|---|---|
| workflow runs | 125 | 455 phases | 364 | 455 | 0 |
| story cells | 227 | 1112 sessions | 445 sessions | 92 cells | 92 cells |
| summary entries | 144 | 0 attempts | 0 | 0 | 0 |
| E4 grid ledger | 8 cells | 9 attempts | 0 | 9 | 9 |

**PASS** — corpus enumerated exhaustively; every count reproduced from the census command; shape
variance recorded (F1 exposure, story-condition dirt, nested-vs-flat tokens, missing attempt
structure in the summary family, E4 ledger coverage). In-flight worktrees untouched.

**Re-audit (2026-08-24):** the census was re-run against the live corpus and every §1/§2 count is
confirmed unchanged — 125 workflow runs (96 `ok`, 455 phases = 427 ok + 28 failed; 448 agent + 7
test kind), 227 story cells (1112 sessions; 10 cells with non-empty `error`; 9 `continuation_used`;
11 `subagent_sessions`; 445 sessions with `confidence`, 44 explicit nulls; 9 condition-dirty cells
— 6 `""` + 3 `"None"`, all deepseek-v4-pro), 144 summary entries (0 attempts), E4 grid 8 cells /
9 attempts ($31.27 realized). Reproducible from the §1 census command.

---

## 5. Additive derivation (p3) — story + summary facts, ZERO reducer diffs

**GUARD met:** `git diff --stat src/agentic_dynamics/control/reducers/` is **EMPTY** — no semantic
change to any existing reducer. All derivation is producer-level projection + existing reducer
calls. In-flight worktrees untouched.

### 5.1 Files changed (producer-level only)

| File | Change |
|---|---|
| `scripts/kb_produce_facts.py` | **additive** — three evidence families (`story_session` / `story_result` / `summary_attempt`) projected onto the UNCHANGED `attempt_facts/v1` + `job_facts/v1`; `derive_story_facts` / `derive_summary_facts` / `derive_corpus_facts`; new `--corpus {story,summary,all}` CLI flag |
| `tests/test_kb_produce_facts_extension.py` | **new** — 6 hermetic tests (story fixture + summary fixture + corpus batch) |
| `src/agentic_dynamics/control/reducers/**` | **UNCHANGED** (guard: zero diffs) |

### 5.2 Evidence families (the workflow_run pattern, per artifact level)

| Family | Granularity | Projected artifact | Consumed by |
|---|---|---|---|
| `story_session` | one run per story SESSION (single-phase run) | session → phase; `run_artifact_id` hashes session fields + cell identity (distinct per session, byte-stable) | `attempt_facts/v1` → per-session attempt facts |
| `story_result` | one run per story CELL (job-level + session list) | cell aggregates (`summary.total_cost`, `ok`, last-session commit) | `job_facts/v1` → per-cell job facts |
| `summary_attempt` | one run per summary ENTRY (single-phase run) | entry → attempt; `attempt_model`/`attempt_cost_usd` always, tokens only for the 49 valid entries | `attempt_facts/v1` → per-entry attempt facts |

Identity decisions (documented in the producer docstrings):
- **Cell identity** = `wf_<story>_<condition>_<model>` — the condition folds into `spec_name`
  (via `_common.cell_id`) so clean/bad_seed/early_degrade runs of the same story+model stay in
  DISTINCT job cells, while multiple seeds of one cell share a job slot (current-per-cell
  supersession, exactly like repeated workflow runs). Condition-less cells (9, all
  deepseek-v4-pro) land in the story's unconditioned cell.
- **Job status** is read from the raw session `exit_code`s + the cell `error` field — NOT from
  `summary.all_successful`, which is observed `True` even for cells whose `error` records a
  session timeout (a data-quality trap; reading the raw exits avoids trusting it).
- **Summary is fed to `attempt_facts/v1` ONLY** — `job_facts/v1` would force a `job_status`
  ("failed") for an entry that records no `ok`, which is exactly the fabrication null-not-zero
  forbids.

### 5.3 Hermetic tests (story + summary fixtures)

`tests/test_kb_produce_facts_extension.py` — **6 passed** (hermetic `REPO_ROOT`+`REGISTRY_INDEX_PATH`
at `tmp_path`, no Redis, registry persistence simulated):
1. story derivation succeeds + ids **stable** (re-derivation → byte-identical `knowledge_id`s);
   absent fields stay absent (`attempt_tokens_in/out`, `attempt_cache_hit_rate`,
   `phase_test_verified`, and `attempt_confidence` for the `None` session are NOT emitted);
   convergence (persist → re-derive → `[]`).
2. sparse story session → only `phase_status`/`phase_commit`/`attempt_model`/`attempt_cost_usd`.
3. per-run identity: clean vs bad_seed → distinct job `entity_id`s; per-session attempts distinct.
4. summary: `attempt_model`+`attempt_cost_usd` for all; `attempt_tokens_in` only for the
   token-carrying entry; **no** `phase_status`/`phase_commit`/`attempt_confidence`/`job_status`.
5. corpus batch: workflow + story + summary in ONE `derive_fact_records` call; re-derivation
   byte-identical; evidence resolves against raw evidence OR in-batch `knowledge_id`s.
6. evidence identity: content-addressed `story_result:<run_artifact_id>`, byte-identical on-disk
   duplicates collapse (the `_run_evidence` dedup guard).

### 5.4 Dry-run smoke over the real corpus (no emission, no registry write)

```
$ python3 scripts/kb_produce_facts.py --corpus story --dry-run
story: derived 5433 fact record(s)
$ python3 scripts/kb_produce_facts.py --corpus summary --dry-run
summary: derived 386 fact record(s)
$ python3 scripts/kb_produce_facts.py --corpus all --dry-run
all: derived 6573 fact record(s)
```

Coverage reconciliation: `all` (6573) = story (5433) + summary (386) + workflow-ladder rungs
(754 = policy + spec_status + workflow facts). **The workflow-RUN family contributes 0 from this
worktree** because `experiments/results/workflows/` is gitignored and absent here — the run
ledgers live only in the main worktree (see §0). p4 must run the emission where `load_run_jsons()`
can see them (main worktree), or the ledgers must be present, to cover the workflow attempt/job
facts for all 125 runs.

### 5.5 Suite results

| Suite | Result |
|---|---|
| CAP suites (context plane, reducers, integration, adversarial) + guards (`test_context_plane_*`, `test_actuation_ingestion`, `test_fact_auto_emit*`, `test_kb_produce_facts_integration`, `test_kb_produce_facts_extension`, `test_kb_produce_registry`, `test_compile_experiment`, `test_experiment_spec`, `test_dependency_direction`, `test_data_flow`, `test_script_classification`) | **426 passed** |
| Additional fact-plane suites (`test_cap_i0_i3_adversarial`, `test_artifact_identity`, `test_ledger_*`, `test_spec_ingestion`, `test_spec_status`, `test_record_factory`, `test_generate_manifest`, `test_knowledge*`, `test_doc_lifecycle`) | **261 passed** (1 env-dependent assert — `test_emit_writes_the_artifact_before_publishing` expects `FINOPS_KB_WRITE` unset; passes cleanly with `env -u FINOPS_KB_WRITE`) |
| Reducer diff guard | **EMPTY** |

**PASS** — additive story/summary derivation landed with zero reducer diffs; fixtures hermetic;
CAP suites + guards green.

---

## 6. Backfill run record (p4) — one emit pass over the ENTIRE corpus

### 6.1 Prerequisite: the gitignored workflow ledger corpus made visible

`experiments/results/workflows/` is gitignored and absent from this worktree, so `load_run_jsons()`
saw zero workflow runs (§0). The 125 run ledgers were copied from the main worktree into this
worktree's (still gitignored, never committed) `experiments/results/workflows/` — the same path the
producer reads — so the derivation covered the full corpus: **125 workflow runs (455 phases) + 227
story cells (1112 sessions) + 144 summary entries**.

### 6.2 The run

```
$ python3 scripts/kb_produce_facts.py --corpus all          # FINOPS_KB_WRITE=1 set at the emit step only
all: derived 10812 fact record(s) (revision=304e66167602, repository-id='agentic-dynamics')
all: emitted=10812 skipped=0 (already checkpointed) total=10812
```

Derivation is PURE (no write env needed — the reducers do no I/O); `FINOPS_KB_WRITE=1` is set inside
`emit_records` for the emit step only. **Exactly one emit pass** (guard met). No model calls in the
derivation → the 402/insufficient-balance stop never applies.

### 6.3 Counts before / after

| Counter | Before | After | Delta |
|---|---|---|---|
| KB artifact files (`experiments/results/kb/`) | 2969 | 13781 | **+10812** |
| `registry_index.jsonl` rows | 830 | 12015 | **+11185** (10812 own rows + 373 supersede-predecessor marker lines) |
| fact artifacts on disk | 240 | 11052 | +10812 |
| registry fact rows | 27 | 10839 | +10812 |

### 6.4 Sample of emitted fact predicates (from the KB artifact payloads)

| Predicate | Count | | Predicate | Count |
|---|---|---|---|---|
| attempt_model | 1724 | | attempt_confidence | 773 |
| attempt_cost_usd | 1714 | | attempt_tokens_in / out | 517 / 517 |
| phase_status | 1587 | | attempt_cache_hit_rate | 419 |
| phase_commit | 1365 | | current_commit | 352 |
| job_accumulated_cost_usd | 343 | | job_status / job_n_phases | 199 / 195 |
| workflow_health / status / phases_* | 115 each | | projected_budget_overrun | 110 |
| max_spend_usd / max_attempts | 111 / 110 | | spec_status | 103 |

### 6.5 F1 fix applied (structural-zero costs → None) — verified

Producer-level sanitizer `_sanitize_run` (applied in `_run_evidence` to the evidence PAYLOAD only;
`run_artifact_id` stays computed over the raw artifact so identity is unchanged): a phase that is
agent-kind + failed + `cost_usd==0.0` + all-zero tokens is a **failed-before-call** phase → its cost
is recorded `None` (uncaptured, not a measured zero); a run whose EVERY phase is failed-before-call
gets `total_cost_usd=None` too (never executed).

- 10 runs in the corpus are all-failed-before-call (auth-failure runs: `cap_i0_i3_remediation`,
  `context_abstraction_implement`, `investing_context_seed_remediation`, `routing_kb_experiment_design`,
  `semantic_integrity_release`, `canonical_state_design`); **0 `attempt_cost_usd` / `attempt_tokens_*`
  facts cite them** (attempt-level verified by run_artifact_id), and no `projected_budget_overrun`
  derives from a never-executed run.
- All 10 cells have a cost-carrying sibling run, so their `job_accumulated_cost_usd` current heads
  are the real, non-zero sibling costs (32.79 / 34.36 / 6.34 / 50.15 / 49.52 / 71.78 / 4.84 …) —
  the never-executed run's `0.0` was never registered as a measured zero.
- Reducer diff guard still EMPTY (the sanitizer is producer-level).

### 6.6 F2 fix applied (registry rows materialized in the emit path) — verified

`emit_records` now appends the `kb-registry-v1` line shape (same fields, operation-derived
`lifecycle_state`, supersede-predecessor marker) for every emitted record, so an artifact is
registry-visible the moment it is written — no dependency on a running consumer.

- **Backfill's own emission: 10812 emitted artifacts → 10812 registry fact rows, 0 missing**
  (artifact count == registry row count for the backfill's emission, verified independently over
  `repository_id=agentic-dynamics` artifacts).
- Residual stall: **213 fact artifacts with `self-wt_*` repository_ids** (emitted at 19:24 today by
  OTHER worktrees' auto-emit hooks — `self-wt_addendum_implement`, `self-wt_paper_journal`,
  `self-wt_flash_vs_luna_*`, `self-wt_grit_grid`) predate this backfill and are **not** part of its
  emission. They belong to in-flight worktrees' scopes (never-touch-inflight) — recorded as a
  pre-existing, other-scope residual, out of scope for this fact backfill. 1948 non-fact artifacts
  (code/story/review/spec…) likewise predate and are untouched.

**PASS** — exactly one emit pass over the entire corpus; F1 structural-zero fix applied and
verified at the attempt level; F2 materialization closes the stall for the backfill's own emission
(10812 == 10812). Reducers untouched; in-flight worktrees untouched.
