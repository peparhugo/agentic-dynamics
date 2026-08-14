# OpenCode Docs Refresh — Scope

Verified drift inventory between this repo's actual code and its onboarding docs
(`AGENTS.md`, `.opencode/instructions/`, `.opencode/agents/`, `.opencode/skills/`,
`.opencode/commands/`, `.opencode/tools/`, and the four `CONTEXT.md` files), plus the
two file taxonomies needed to port the docs to the Claude Code/CLI layout.

Every line below was checked against the actual files on 2026-08-14, not taken on
faith from the drift hypothesis that seeded this investigation. Several hypothesis
claims turned out to be wrong or backwards — those corrections are called out
explicitly so the build/verify phases don't propagate the error.

---

## 1. Verified drift inventory

### 1.1 The spec/compiler is written, not proposed — CONFIRMED, repo-wide

`src/instrument/compile_experiment.py` (376 lines) and `src/instrument/experiment_spec.py`
(446 lines) both exist and are real, tested code — not stubs. `tests/test_compile_experiment.py`
(206 lines, 13 tests) and `tests/test_experiment_spec.py` (274 lines, 16 tests) exist and
exercise them (29 tests total).

**`AGENTS.md` self-contradicts within one file:**
- Line 11 (load-bearing rule): "Design: `code_reviews/2026-08-14_experiment-spec-and-compiler-design.md`
  (spec is **written**; compiler is **written**; instrumentation is step 3)."
- Line 48 (key-files section): "`src/instrument/experiment_spec.py` ... is **written**;
  `src/instrument/compile_experiment.py` (spec → DAG) is still **proposed**."

**Docs that call the compiler "proposed" / "not yet in the repo" / future-tense ("will"):**

| File | Stale line(s) |
|---|---|
| `AGENTS.md` | 48 (contradicts its own line 11) |
| `.opencode/instructions/mental-model.md` | 33, 35–37, 40–42, 140, 158, 169, 237 |
| `.opencode/instructions/conventions.md` | 13, 24, 35–38 |
| `.opencode/agents/data-analysis.md` | 53–54 |
| `.opencode/agents/instrument-dev.md` | 11, 21, 50–52 |
| `.opencode/agents/pipeline-ops.md` | 90–91 |
| `.opencode/skills/analyze/SKILL.md` | 173, 175, 179 |
| `.opencode/skills/instrument/SKILL.md` | 23, 29, 32–34, 57 (also names a nonexistent flagship spec, see 1.3) |
| `.opencode/skills/lab-books/SKILL.md` | 190, 193–194 |
| `.opencode/commands/new-exp.md` | 9 |
| `.opencode/commands/pipeline.md` | 22 |
| `.opencode/commands/run-exp.md` | 22 |
| `experiments/CONTEXT.md` | 5, 22 (frames the whole spec layer as proposed even though it inherits into working YAML — see 1.3) |
| `scripts/CONTEXT.md` | 15, 94, 96 — explicitly "Not yet written" |
| `src/instrument/CONTEXT.md` | 7, 92 — **half-corrected**: gets `experiment_spec.py` right ("written") but still calls `compile_experiment.py` "proposed" |

**Correction to the hypothesis** — two of the originally-listed docs don't mention the
compiler/spec at all (not stale wording, just silent): `.opencode/commands/analyze.md`
and `.opencode/commands/lab.md`. `firebase/CONTEXT.md` also never mentions it. Net: 15
of the 17 originally-named docs are confirmed stale; 3 are silent rather than wrong
(don't need a "written" correction, just could optionally gain a mention).

**Fix direction:** every occurrence above should read "written" (or be removed if it's
purely a "not yet built" framing device), matching `AGENTS.md:11` and
`src/instrument/CONTEXT.md:91`.

### 1.2 New `src/instrument/` modules — 3 of 7 are genuinely undocumented, not all 7

The hypothesis listed 7 modules as unmentioned anywhere. Verification found 4 of the 7
are already documented; only 3 are a real gap:

| Module | Lines | Purpose | Doc status |
|---|---|---|---|
| `supervisor.py` | 171 | Redis contracts for supervisor-flag records + session↔cell mapping (deliberately no OpenCode client dep, so observation can't become control) | **Undocumented** — zero mentions anywhere, including onboarding docs. (`docs/verify.md:18` mentions the *Redis key string* `supervisor_flags`, not the module.) |
| `workflow_runner.py` | 336 | Executes an `agent_task` workflow's phases inside a git worktree, committing + ledgering each phase | **Undocumented** — zero mentions |
| `test_runner.py` | 140 | Independent pytest/jest/go-test/cargo-test execution; sole source of truth for `test_executed_success`, never trusts model self-report | **Undocumented** — zero mentions |
| `streaming.py` | 123 | Line-streamed subprocess runner | Documented (`instrument-dev.md:48`, `mental-model.md:125`, `src/instrument/CONTEXT.md:74`) |
| `recovery_cost.py` | 171 | Tokens/$ cost of recovering from a perturbation | Documented (`instrument-dev.md:48`, `CONTEXT.md:60`, `README.md:94`) |
| `constraint_detection.py` | 268 | Detects explicit mentions of removed constraints in model output | Documented (`instrument-dev.md:48`, `README.md:96`, `CONTEXT.md:67`) |
| `semantic_validation.py` | 300 | 3-signal output-based perturbation classifier (no embeddings) | Documented (`scripts/CONTEXT.md:83`, `instrument-dev.md:48`, `analyze/SKILL.md:57`, `lab-books/SKILL.md:142`, `README.md:97`, `CONTEXT.md:68,144`) |

All three undocumented modules are real/active, not dead code: `supervisor.py` is
imported by `admin/server.py`, `src/instrument/live.py`, `admin/design_sessions.py`,
`scripts/supervise.py`, and tested by `tests/test_supervise.py` +
`tests/test_admin_supervisor.py`. `workflow_runner.py` is imported by
`scripts/run_workflow.py` and tested by `tests/test_workflow_runner.py`.
`test_runner.py` is imported by `workflow_runner.py` and `scripts/verify_tests.py`.

**Bonus finding:** `src/instrument/CONTEXT.md:3` claims "33 Python modules" — actual
count is **38**. Its module-reference table is missing 16 modules total (the 3 above
plus `codebase_graph.py`, `commit_analysis.py`, `embeddings.py`, `entropy.py`,
`graph.py`, `language.py`, `lsp_diagnostics.py`, `mutation.py`, `ollama_analyzer.py`,
`opencode_analyzer.py`, `review.py`, `sonar.py`, `story.py`).

### 1.3 Control Room / supervisor subsystem — REFUTED as "absent from every doc"

The hypothesis claimed the whole admin/Control Room subsystem is undocumented. This is
**false**: it's extensively covered by a design/review doc cluster —
`docs/scope.md`, `docs/spec.md`, `docs/challenge.md`, `docs/fixplan.md`, `docs/verify.md`,
`docs/review/architecture_review.md`, `docs/review/code_review.md`, and
`docs/supervisor_design.md` — which between them cite `admin/claude_agents_client.py`,
`admin/opencode_client.py`, `admin/design_sessions.py`, `admin/static/control-room-core.js`,
`admin/server.py`, `scripts/supervise.py`, and (by filename) `scripts/claude_agents_supervisor.py`.

Only two things are genuinely true:

1. **`scripts/run_workflow.py` (69 lines)** has zero mentions in any doc, including the
   design-doc cluster.
2. **The onboarding/reference layer** (`AGENTS.md`, `BLUEPRINT*.md`, `README.md`, all
   `CONTEXT.md` files, all `.opencode/**/*.md`) has zero mentions of any Control Room
   file, and its only trace of `admin/server.py` (`AGENTS.md:28`,
   `mental-model.md:209`, `scripts/CONTEXT.md:89`) describes it as a 367-line "SSE
   dashboard" with 5 routes (`/api/matrix`, `/api/status`, `/api/events`,
   `/api/routing`, `POST /api/experiments`) — stale: the file is now **1368 lines**
   with Control Room, design-session, and Claude-background-session/`/api/flags*`
   endpoints added.

`docs/supervisor_design.md` (357 lines) is itself accurate and current — it's the
scope→implement pair for `supervisor.py` + `/api/flags*` + `scripts/supervise.py`
(verified against `admin/server.py:805-806,972,999` and `scripts/supervise.py:221`) —
but it only covers that one flag-rail slice, not `design_sessions.py`,
`control-room-core.js`, or the Claude-agents client/supervisor pair.

**Fix direction:** don't write new docs for the whole subsystem (it has design docs);
add a summary of it to the onboarding layer (`mental-model.md`'s architecture section,
`AGENTS.md`'s key-files list) so newcomers don't have to find `docs/spec.md` to learn
it exists, and update the 367-line/5-route description of `admin/server.py` to match
its current 1368-line/full-endpoint reality. Add `scripts/run_workflow.py` to the
script map either way (see 1.5).

### 1.4 `.opencode/` directory names — CORRECTION to the task's own taxonomy hint

The task context describes this repo's tool paths as `.opencode/agent/*.md`,
`.opencode/command/*.md`, `.opencode/skill/*/SKILL.md` (singular). The actual
directories are **plural**: `.opencode/agents/`, `.opencode/commands/`,
`.opencode/skills/`. (OpenCode's own docs additionally support `.opencode/agent/`
singular as an alternate global convention, but this repo consistently uses plural
project-level dirs — confirm before porting.) Confirmed via directory listing: 3 files
in `.opencode/agents/` (data-analysis.md, instrument-dev.md, pipeline-ops.md), 5 in
`.opencode/commands/` (analyze.md, lab.md, new-exp.md, pipeline.md, run-exp.md), 3
`SKILL.md` files under `.opencode/skills/` (analyze/, instrument/, lab-books/), 16
`.ts` tools under `.opencode/tools/`.

### 1.5 Script map stale in `mental-model.md` — CONFIRMED, with one correction

`scripts/` has **78** `.py` files. `mental-model.md:186-211`'s "Script map" section
names only 20 individually plus one generic line covering the 19 active
`lab_*.py` + 8 deprecated `*_bge_m3.py` scripts collectively (27 more) — 47 of 78
covered at some level, 31 with zero mention (even generically).

Of the 24 scripts the hypothesis named as missing, **23 are confirmed missing**. One
is wrong: **`review_worker.py` is already named** at `mental-model.md:202`
("`scripts/review_stories.py + review_worker.py` — batch/Redis review runners").
Corrected missing list (23): `run_workflow.py`, `supervise.py`,
`claude_agents_supervisor.py`, `analysis_worker.py`, `analyze_stories.py`,
`enqueue_analysis.py`, `enqueue_reviews.py`, `finalize_reviews.py`,
`trigger_reviews.py`, `recover_stories.py`, `batch_stories.py`, `batch_run.py`,
`sweep_silent_mode.py`, `finish_sweep.py`, `remaining_batch.py`, `multi_phase.py`,
`backfill_costs.py`, `backfill_deep_metrics.py`, `backfill_story_artifacts.py`,
`compute_sonar_deltas.py`, `embed_sessions.py`, `rescore_conventions.py`,
`verify_tests.py`.

Also, `mental-model.md:206` lists `scripts/compile_experiment.py` as "[proposed] spec →
DAG" — that file **does not exist in `scripts/`** at all (the real compiler lives at
`src/instrument/compile_experiment.py`, see 1.1). This line should be deleted, not
just re-labeled "written" — it points at the wrong path entirely.

`scripts/CONTEXT.md` has its own, independent drift: it claims "74 Python scripts"
(line 3) — actually 78 — and is missing 25 scripts by exact filename even after
crediting its (better than mental-model.md's) lab_*.py table. The two docs also
disagree with each other on which scripts they cover (e.g. `generate_manifest.py`,
`plan.py`, `sync_data.py`, `backfill_sonar.py` are in mental-model.md but not in
scripts/CONTEXT.md).

### 1.6 `admin/`, `scripts/supervise.py`, `scripts/run_workflow.py`, `scripts/claude_agents_supervisor.py` — see 1.3

Folded into 1.3 above; not a separate undocumented block — the design-doc cluster
covers all of these except `run_workflow.py`.

### 1.7 `experiments/specs/` — CONFIRMED real; CONTEXT.md's "proposed" framing and flagship name are both stale

`experiments/specs/` contains exactly the 11 real `.yaml` files hypothesized, no more,
no fewer, no renames: `agentic_dynamics_story.yaml`, `claude_background_sessions.yaml`,
`code_review.yaml`, `control_room_portal.yaml`, `design_sessions.yaml`,
`evidence_narrative.yaml`, `evidence_redesign.yaml`, `fix_review_findings.yaml`,
`framework_facelift.yaml`, `site_golden_circle.yaml`, `supervisor_control_room.yaml`.

`routing_regret.yaml` does not exist anywhere in the repo (confirmed via
repo-wide `find`). It's referenced as prose only, in: `experiments/CONTEXT.md:10`
(as the section's "Flagship" example), `BLUEPRINT_v3.md:101,132,144`, the design doc
`code_reviews/2026-08-14_experiment-spec-and-compiler-design.md` (worked example
throughout), and `.opencode/skills/instrument/SKILL.md:55` (which does correctly
mark it "(proposed)").

`experiments/CONTEXT.md:5` heading — `` ## `experiments/specs/` — ExperimentSpec YAML
(proposed) `` — is stale: 11 real, non-trivial specs (5.5–8.2 KB each) already exist.
Line 10's "Flagship: `experiments/specs/routing_regret.yaml`" should be replaced with
a real example filename (e.g. `agentic_dynamics_story.yaml`) or explicitly marked as
an aspirational example, not the flagship of a directory the doc otherwise describes
as speculative.

### 1.8 `experiments/configs/plans.yaml` — CONFIRMED 6 plans; every enumeration site is missing `cross_models`

`plans.yaml` has exactly 6 top-level plans: `ci` (line 5), `deploy` (21),
`full_matrix` (40), `cross_models` (86), `feature` (140), `ship_features` (164).
`cross_models` is a real, fully-defined 9-phase plan (`flash → haiku → sonnet → sol →
terra → analyze → reviews → regenerate → deploy`).

Every place in the repo that enumerates plan names lists only the same 5, omitting
`cross_models`: `.opencode/tools/pipeline.ts:5,16`,
`.opencode/agents/pipeline-ops.md:79-81`, `scripts/CONTEXT.md:14`. (`README.md` and
`docs/*.md` don't enumerate plans at all, so they're not "wrong," just silent.)

### 1.9 Lab books — CONFIRMED for `lab.md`; REFUTED for the skill description

19 active `lab_*.py` scripts exist (27 total minus 8 `*_DEPRECATED_bge_m3.py`).
`experiments/lab_books/` holds 20 `lab_*.md` files plus a `README.md`.

- **`.opencode/commands/lab.md`** — CONFIRMED stale and internally inconsistent: line
  7 says "14 available labs" in prose, but the enumerated list at lines 15–18 contains
  only **13** names. Both figures are short of the real 19 — missing
  `cache_economics`, `condition_effects`, `quality_frontier`, `story_arc`,
  `verification_frontier`, `verification_value`.
- **`.opencode/skills/lab-books/SKILL.md`** — **REFUTED.** The hypothesis said its
  description says "14"; it actually says **"19 active lab books"** at line 3 and
  correctly enumerates all 19 in its body (lines 24–127). This file is not a drift
  source and needs no fix.
- **Bonus finding:** `experiments/lab_books/README.md` is separately stale — line 7
  claims "All 13 lab books have been executed," and its own numbered list (lines
  14–40) totals 20, including 3 entries for now-deprecated scripts and missing
  `.md` files for 2 real active scripts (`lab_sonar_quality.py`,
  `lab_think_do_coupling.py`).

### 1.10 Test files — CONFIRMED, exact diff of 12

Repo has exactly **39** `tests/test_*.py` files (not 40). `mental-model.md:213-225`
names **27** (not ~28). The exact 12 missing (39 − 27):
`test_compile_experiment.py`, `test_experiment_spec.py`, `test_workflow_runner.py`,
`test_supervise.py`, and the `test_admin_*` family (exactly 6:
`test_admin_claude_agents.py`, `test_admin_claude_agents_frontend.py`,
`test_admin_design_sessions.py`, `test_admin_frontend.py`, `test_admin_server.py`,
`test_admin_supervisor.py`) and the `test_claude_agents_*` family (exactly 2:
`test_claude_agents_client.py`, `test_claude_agents_supervisor.py` — distinct from
`test_claude_adapter.py`, which is singular/unrelated and already listed).

### 1.11 `PROVIDER_PRICING` keys — REFUTED: `anthropic-sonnet5` is real, not fictitious

`src/instrument/efficiency.py:41-85` defines **9** keys, not 8: `deepseek` (42),
`deepseek-flash` (47), `anthropic` (52), `openai` (56), **`anthropic-sonnet5` (61,
"v0.9 models — added Aug 2026")**, `anthropic-haiku` (66), `openai-luna` (71),
`openai-sol` (75), `openai-terra` (80). `anthropic-sonnet5` is also in
`CURRENT_REFERENCE_PRICING:125` and is actively resolved by
`_resolve_pricing_key():160-161` (`if "sonnet" in combined: return
"anthropic-sonnet5"`).

The hypothesis's own "current keys" list omitted this real key, and its claim that
`.opencode/skills/instrument/SKILL.md:189-190` lists a *nonexistent* key is backwards
— that line correctly lists `anthropic-sonnet5` as real. What's actually stale about
`SKILL.md:190` is that it's an *incomplete* enumeration, missing `deepseek-flash`,
`anthropic-haiku`, `openai-sol`, `openai-terra`.

**Fix direction:** update `SKILL.md:190`'s comment to list all 9 keys, don't remove
`anthropic-sonnet5`.

### 1.12 `BUILTIN_STORIES` keys — CONFIRMED

`src/instrument/story.py:1370-1374` keys are `task_manager_api`, `static_site_gen`,
`notification_service`. `conventions.md:53-54` and
`.opencode/skills/instrument/SKILL.md:147-150` both use the wrong `*_story`-suffixed
names (`task_manager_story`, `static_site_gen_story`, `notification_service_story`).
`scripts/run_story.py:48`'s own argparse help text already uses the correct names, so
the drift is confined to the two doc files.

### 1.13 `run_story` conditions/flags — CONFIRMED

`src/instrument/story.py:47-50` defines 4 conditions: `clean`, `bad_seed`,
`early_degrade`, `late_degrade`. `scripts/run_story.py:78-83`'s `--condition` choices
match all 4. `.opencode/tools/run_story.ts:4`'s `CONDITIONS` array has only 3
(`clean`, `bad_seed`, `early_degrade`) — missing `late_degrade`.

`scripts/run_story.py` additionally supports `--backend`, `--codebase`,
`--worktree-root`, `--results-dir`, `--output-limit`, `--standardize`/
`--no-standardize` (lines 56-106) — none of these are exposed by `run_story.ts`
(which only shells out `--model`, `--condition`, `--codebase-quality`, `--tier`,
`--timeout`, `--thinking-budget`).

### 1.14 Model config — CONFIRMED, `deepseek-chat` is config-only dead weight

`opencode.json:4` (`small_model`) and all 3 `.opencode/agents/*.md` files' `model:`
frontmatter say `deepseek/deepseek-chat`. That string appears **nowhere else** in the
repo (0 hits in `src/`, `scripts/`, `experiments/configs/`, or result data).
`deepseek/deepseek-v4-flash` is the model actually in use everywhere else: 209 real
result filenames under `experiments/results/stories/`, plus ~20 source/script/config
locations including `src/instrument/story.py:58`,
`src/instrument/opencode_analyzer.py:169`, `scripts/_constants.py:9`,
`experiments/configs/plans.yaml:71,91,125,159`, and `docs/redesign.md`,
`docs/narrative.md`.

### 1.15 `enqueue.ts` flags — CONFIRMED the tool is missing them; REFUTED that any doc claims otherwise

`.opencode/tools/enqueue.ts` exposes exactly two args (`dry_run` → `--dry-run`,
`clear` → `--clear`) and nothing else — confirmed no `--model`/`--missing-only`
support, both of which `scripts/enqueue.py` does support
(`scripts/enqueue.py:146-154`). However, a repo-wide grep for `--model` /
`--missing-only` near "enqueue" across all commands/instructions/skills/README/docs
found **zero** places that document `enqueue.ts` (or `enqueue.py` in general usage
examples) as having either flag — `pipeline-ops.md:63` and
`instrument/SKILL.md:205` both show `python scripts/enqueue.py` with no flags at all.
The real issue is simply that `enqueue.ts` is a thin subset of `enqueue.py`'s CLI, not
that a doc mis-documents it.

### 1.16 Instrumentation gap — STILL TRUE, do not mark resolved

`LEDGER_FIELDS` in `src/instrument/experiment_spec.py:44-96` has no `confidence`
field, no answer/explanation token split (only `tokens_in`/`tokens_out`/
`tokens_reasoning`), no per-attempt timestamp beyond `queued_at`/`leased_at`/
`started_at`/`first_token_at`/`ended_at` (i.e. no dedicated `perturbation_strength`
field — only a generic `strength` factor-level field, not the same thing), and no
`test_executed_success` field. This confirms the instrumentation-step-3 gap remains
open; only the "compiler is proposed" wording (1.1) was wrong, not this.

### 1.17 Counts summary

| Inventory | Real count | Doc claims | Gap |
|---|---|---|---|
| `scripts/*.py` | 78 | mental-model.md names ~20 individually | ~58 unnamed (31 with zero mention even generically) |
| `tests/test_*.py` | 39 | mental-model.md names 27 | 12 missing (exact list, 1.10) |
| `experiments/specs/*.yaml` | 11 | CONTEXT.md calls dir "proposed" | framing stale, not count |
| `experiments/configs/plans.yaml` plans | 6 | tool/docs list 5 | `cross_models` missing everywhere |
| Active `lab_*.py` scripts | 19 | `lab.md` says 14 (lists 13); SKILL.md correctly says 19 | `lab.md` short by 6 |
| `src/instrument/*.py` modules | 38 | CONTEXT.md says 33, table lists ~22 | 16 modules missing from table |
| `PROVIDER_PRICING` keys | 9 | SKILL.md comment lists 5 | 4 keys missing from comment (not `anthropic-sonnet5` — that one's real) |

---

## 2. OpenCode file taxonomy — as actually used in this repo

Verified against `opencode.ai/docs/` (agents, skills, commands, config, rules,
custom-tools, references, mcp-servers) and the repo's actual directory listing.

| Concept | OpenCode docs say | This repo's actual path | Notes |
|---|---|---|---|
| Rules / project instructions | `AGENTS.md` (project root); global at `~/.config/opencode/AGENTS.md` | `AGENTS.md` (58 lines) | Loaded like Cursor rules; searched upward from cwd. |
| Extended instructions | `opencode.json`'s `instructions` field (glob/remote paths) | `.opencode/instructions/mental-model.md`, `.opencode/instructions/conventions.md` | Not literal "rules" per the docs' narrow definition, but this repo's mechanism for longer reference material AGENTS.md defers to. |
| Agents (subagents/primary) | Markdown files in `.opencode/agents/` (project) or `~/.config/opencode/agents/` (global); frontmatter: `description`, `mode`, `model`, `temperature`, `permission`, `color`, `hidden` | `.opencode/agents/data-analysis.md`, `instrument-dev.md`, `pipeline-ops.md` | Plural dir, matches docs' project convention. Filename → agent id (e.g. `pipeline-ops.md` → `pipeline-ops`). |
| Commands | Markdown files in `.opencode/commands/` (project) or `~/.config/opencode/commands/` (global); frontmatter: `description`, `agent`, `model`, `subtask`; body is the prompt template with `$ARGUMENTS`/`$1`, `` !`cmd` ``, `@file` support | `.opencode/commands/analyze.md`, `lab.md`, `new-exp.md`, `pipeline.md`, `run-exp.md` | 5 commands, filename → `/command-name`. |
| Skills | `.opencode/skills/<name>/SKILL.md` (also discovers `.claude/skills/` and `.agents/skills/` for cross-tool compat); required frontmatter `name` + `description`; name must match dir name, `^[a-z0-9]+(-[a-z0-9]+)*$` | `.opencode/skills/analyze/SKILL.md`, `instrument/SKILL.md`, `lab-books/SKILL.md` | 3 skills. |
| Custom tools | `.opencode/tools/*.ts` (project) or `~/.config/opencode/tools/` (global); `tool()` helper, Zod args schema, async `execute(args, context)`; filename → tool name (or `<file>_<export>` for named exports) | `.opencode/tools/*.ts` — 16 files: `analyze_worktrees.ts`, `archive_worktrees.ts`, `backfill.ts`, `batch.ts`, `build_data.ts`, `dashboard.ts`, `enqueue.ts`, `inventory.ts`, `list_stories.ts`, `monitor.ts`, `pipeline.ts`, `run_experiment.ts`, `run_lab.ts`, `run_story.ts`, `sweep.ts`, `worker.ts` | Each wraps a `scripts/*.py` CLI via `Bun.$`. |
| Config | `opencode.json` in project root (also global/managed/remote layers; JSON/JSONC; merged not replaced); top fields incl. `model`, `small_model`, `agent`, `command`, `mcp`, `instructions`, `permission` | `opencode.json` (project root, 642 bytes) | `small_model` currently `deepseek/deepseek-chat` (stale, see 1.14). |
| MCP servers | `opencode.json`'s `"mcp"` key; `type: local` (command array) or `type: remote` (url) | Not currently configured in this repo's `opencode.json` | N/A here — no MCP servers defined project-side. |
| References | `opencode.json`/`.jsonc`, `@alias` syntax, local dirs or git repos | Not used in this repo | N/A. |

**Correction to the task's own framing:** the task context described this repo's
paths as `.opencode/agent/`, `.opencode/command/`, `.opencode/skill/` (singular). The
repo actually uses the **plural** forms throughout — verify this before authoring any
port script or find/replace.

---

## 3. Claude Code file taxonomy — cited from `code.claude.com/docs`

| Concept | Claude Code path | Key details |
|---|---|---|
| Memory / project instructions | `CLAUDE.md` (project root or `.claude/CLAUDE.md`); `CLAUDE.local.md` for personal/gitignored; `~/.claude/CLAUDE.md` for user-global; managed policy paths for org-wide | Claude Code reads `CLAUDE.md`, **not** `AGENTS.md` — for repos that keep `AGENTS.md` for other tools, the documented pattern is a `CLAUDE.md` that does `@AGENTS.md` import (or a symlink) plus Claude-specific additions below it. Target under 200 lines/file; loaded in full at launch, walking up the directory tree. |
| Path-scoped rules | `.claude/rules/*.md`, optionally with `paths:` frontmatter glob | Modular alternative to a monolithic CLAUDE.md; loads at launch (unscoped) or on-demand when a matching file is touched (scoped). Supports symlinks for cross-project sharing; user-level at `~/.claude/rules/`. |
| Auto memory | `~/.claude/projects/<project>/memory/MEMORY.md` + topic files | Claude-authored (not user-authored); machine-local; `MEMORY.md` capped at 200 lines/25KB for auto-load, topic files loaded on demand. |
| Settings | `.claude/settings.json` (team, committed), `.claude/settings.local.json` (personal, gitignored), `~/.claude/settings.json` (user) | Precedence: managed > CLI args > local > project > user. Top fields: `permissions` (allow/deny/ask), `env`, `model`, `hooks`, `agent`, `attribution`, `autoMemoryEnabled`, `autoCompactEnabled`. |
| Subagents | `.claude/agents/*.md` (project), user-level equivalent exists too | Each runs in its own context window with custom system prompt, tool access, and permissions; invoked automatically by description match or explicitly. |
| Commands / Skills | `.claude/commands/*.md` **and** `.claude/skills/<name>/SKILL.md` — as of the current docs these are unified: "Commands and skills are now the same mechanism... same `/name` invocation, plus you can bundle supporting files." Existing `.claude/commands/` files keep working; new work should target `.claude/skills/`. | Skills add: a directory for supporting files, frontmatter controlling who invokes them (user vs. Claude-auto), and Claude-initiated auto-loading when relevant. |
| MCP servers | `.mcp.json` (project scope), plus user/local scopes | Configures Model Context Protocol server connections (local command-based or remote URL-based). |
| CLI reference | `code.claude.com/docs/en/cli-reference` | Key flags: `--model`, `--effort`, `--permission-mode`, `--print`/`-p`, `--bg`, `--resume`/`-r`, `--mcp-config`, `--add-dir`, `--append-system-prompt`, `--max-budget-usd`. Commands: `claude agents`, `claude daemon status/stop`, `claude mcp`, `claude plugin`, `claude doctor`. |

**Mapping for the port phase** (OpenCode concept → Claude Code equivalent):

| OpenCode | Claude Code |
|---|---|
| `AGENTS.md` | `CLAUDE.md` (or `CLAUDE.md` importing `@AGENTS.md` if both tools must read the same file) |
| `.opencode/instructions/*.md` | `.claude/rules/*.md` (unscoped, loaded at launch — closest match to how `mental-model.md`/`conventions.md` are used today) |
| `.opencode/agents/*.md` | `.claude/agents/*.md` |
| `.opencode/commands/*.md` | `.claude/skills/<name>/SKILL.md` (commands are the legacy path; skills are the current unified mechanism and support bundling `run_story.ts`-equivalent scripts alongside) |
| `.opencode/skills/<name>/SKILL.md` | `.claude/skills/<name>/SKILL.md` (near 1:1; frontmatter differs slightly — Claude Code doesn't require the `^[a-z0-9]+(-[a-z0-9]+)*$` name/dir-match rule documented for OpenCode, but matching it anyway is harmless) |
| `.opencode/tools/*.ts` (Bun/Zod custom tools) | No direct file-based equivalent — closest is an MCP server (`.mcp.json`) exposing equivalent tools, since Claude Code doesn't have a first-class project-local custom-tool directory the way OpenCode does |
| `opencode.json` | `.claude/settings.json` (config) — model/agent/permission fields map roughly, but structure isn't identical; port field-by-field, don't copy verbatim |

---

## 4. Acceptance checklist (build phase implements, verify phase checks)

1. `AGENTS.md:48` says `compile_experiment.py` is written (matches line 11); the
   self-contradiction is gone.
2. Every doc listed in §1.1 (15 confirmed-stale files) no longer calls the spec
   compiler "proposed" / "not yet in the repo" / uses future tense ("will compile");
   all describe it as written, with a pointer to `src/instrument/compile_experiment.py`.
3. `mental-model.md`'s architecture section (or equivalent) documents `supervisor.py`,
   `workflow_runner.py`, and `test_runner.py` by name and one-line purpose (the 3
   modules confirmed genuinely undocumented in §1.2).
4. `mental-model.md` / `AGENTS.md` gains a short pointer to the Control Room /
   supervisor subsystem and its existing design docs (`docs/spec.md`, `docs/scope.md`,
   `docs/supervisor_design.md`, etc.) — not a full rewrite of those docs, just an
   onboarding-layer signpost, per §1.3.
5. `mental-model.md`'s `admin/server.py` description no longer says "SSE dashboard"
   with 5 routes; it reflects the current 1368-line file with Control Room,
   design-session, and `/api/flags*`/Claude-background-session endpoints.
6. `scripts/run_workflow.py` appears in at least one doc (script map minimum).
7. `mental-model.md`'s "Script map" section covers all 78 scripts in `scripts/`,
   individually or via an accurate collective line (no phantom
   `scripts/compile_experiment.py` entry — delete or redirect to the real
   `src/instrument/` path).
8. `scripts/CONTEXT.md`'s script count (currently "74") is corrected to 78, and its
   script table is reconciled with `mental-model.md`'s so the two docs don't disagree
   with each other on which scripts exist.
9. `experiments/CONTEXT.md:5` no longer calls `experiments/specs/` "proposed"; its
   "Flagship" example (currently the nonexistent `routing_regret.yaml`) is replaced
   with a real spec filename or explicitly marked aspirational.
10. Every plan-enumeration site (`.opencode/tools/pipeline.ts`,
    `.opencode/agents/pipeline-ops.md`, `scripts/CONTEXT.md`) lists all 6 plans
    including `cross_models`.
11. `.opencode/commands/lab.md` says "19 available labs" (not "14"/13-item list) and
    enumerates all 19, matching `.opencode/skills/lab-books/SKILL.md` (which is
    already correct and needs no change).
12. `experiments/lab_books/README.md` no longer claims "All 13 lab books have been
    executed"; its list is reconciled to the 19 real active scripts (no orphaned
    deprecated-script entries, no missing entries for `lab_sonar_quality.py` /
    `lab_think_do_coupling.py`).
13. `mental-model.md`'s "Test files" section lists (or accurately summarizes) all 39
    files in `tests/`, including the 12 confirmed-missing ones from §1.10.
14. `.opencode/skills/instrument/SKILL.md:190`'s `PROVIDER_PRICING` key comment lists
    all 9 real keys (`deepseek`, `deepseek-flash`, `anthropic`, `anthropic-sonnet5`,
    `anthropic-haiku`, `openai`, `openai-luna`, `openai-sol`, `openai-terra`) — do
    **not** remove `anthropic-sonnet5`, it's real.
15. `conventions.md:53-54` and `.opencode/skills/instrument/SKILL.md:147-150` use the
    real `BUILTIN_STORIES` keys (`task_manager_api`, `static_site_gen`,
    `notification_service`), not the `*_story`-suffixed names.
16. `.opencode/tools/run_story.ts`'s `CONDITIONS` array includes `late_degrade`
    (4 entries, matching `src/instrument/story.py`), and either exposes
    `--backend`/`--codebase`/`--worktree-root`/`--results-dir`/`--output-limit`/
    `--standardize` or explicitly documents the tool as an intentionally reduced
    subset of `scripts/run_story.py`'s CLI.
17. `opencode.json`'s `small_model` and all 3 `.opencode/agents/*.md` `model:` fields
    use `deepseek/deepseek-v4-flash` (or whatever model is actually current at fix
    time — verify against `experiments/results/stories/` filenames, not this doc,
    since model names change over time).
18. `src/instrument/CONTEXT.md`'s module count (currently "33") and module-reference
    table are updated to the real 38 modules.
19. `docs/opencode_docs_scope.md` §1.16 (instrumentation gap: `confidence`,
    answer/explanation token split, dedicated `perturbation_strength`,
    `test_executed_success`) is **not** touched by this doc-refresh work — verify
    the build phase didn't accidentally mark it resolved; it's a separate,
    still-open instrumentation task, not a doc-wording issue.
20. The `.opencode/` → Claude Code taxonomy port (§3) preserves the plural
    `.opencode/agents/`, `.opencode/commands/`, `.opencode/skills/` naming when
    mapping to `.claude/agents/`, `.claude/skills/` — don't introduce singular forms
    that don't match either tool's actual convention.
21. No doc claims `.opencode/tools/enqueue.ts` supports `--model`/`--missing-only`
    (none currently do — this is a non-issue, listed here only so verify doesn't
    flag it as unaddressed; the real fix, if any, is adding those flags to
    `enqueue.ts` itself, which is a code change outside doc-refresh scope).
