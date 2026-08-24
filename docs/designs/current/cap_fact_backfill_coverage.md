---
status: accepted
---
# CAP Fact Backfill — Corpus Inventory (Stage 1, p1)

**Spec:** `workflows/repository/cap_fact_backfill.yaml` (phase `p1_corpus_inventory`)
**Branch:** `feature/cap-fact-backfill`
**Date:** 2026-08-24 · **Model:** deepseek/deepseek-v4-flash (single-model, `--backend opencode`)
**Question:** Enumerate the full experiment corpus exhaustively — workflow runs, story cells,
summary entries — record shape variance per source, and publish the master artifact table.

**Planned sections:** §1 master artifact table (this phase) · §2 variance report (this phase) ·
§3 per-predicate coverage table (p2) · §4 E1-E4 evaluability (p2) · §5 additive derivation (p3) ·
§6 backfill run record (p4) · §7 verification (p5) · §8 adversarial review + release verdict (p6).

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
