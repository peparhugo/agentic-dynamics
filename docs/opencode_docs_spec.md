# OpenCode Docs Refresh — Spec

Concrete design for two coupled pieces of work: (1) fix verified drift between this
repo's onboarding docs and its actual code (`docs/opencode_docs_scope.md`), and (2) a
taxonomy port design mapping this repo's `.opencode/` layout to the Claude Code/CLI
layout (also scoped in that doc). `docs/opencode_docs_challenge.md` reviewed the scope
doc's design choices; §1 below adjudicates every one of its disagreements before the
rest of this doc proceeds, so the file-by-file plan and the mapping table already
reflect the adjudicated decisions rather than re-litigating them inline.

Every file and line cited below was re-read directly during this phase (2026-08-14),
not copied from the scope doc's citations — where my own read disagreed with scope's
line numbers or characterization, that's called out explicitly.

**Reading order for implementers:** §2 is ordered so the load-bearing files
(`AGENTS.md`, `mental-model.md` — both loaded every session) land first, `conventions.md`
/ agents / skills / commands / CONTEXT.md files / config next, and the design-doc status
header last. §3 (new tools + tool fixes) and §4 (the port mapping) both assume §2 has
already landed — the port translates the *corrected* opencode sources, not the stale
ones, and the new/fixed tools' descriptions quote the corrected plan/condition/model
names from §2, not the pre-fix ones.

---

## 1. Challenge adjudication

| # | Challenge point | Decision | Why |
|---|---|---|---|
| — | §1.1–§1.17 verified drift + §4 acceptance items 1–19 (the bulk of the scope doc) | **Adopt as scoped**, with D4/D5/D6/D7 refinements folded in below | Challenge confirms these directly against the repo (mental-model.md:33 "PARTIALLY BUILT", src/instrument/CONTEXT.md:5, AGENTS.md:11 vs :48); this phase re-confirmed all of it independently while gathering material for §2. No open disagreement on the underlying facts. |
| D1 | `.opencode/tools/*.ts` → MCP server as the port target | **Synthesize.** Keep the mapping-table row (Claude Code's own docs make MCP the closest *file-based* equivalent to a custom-tool directory, and the task requires the row to exist), but the row's **recommendation** column says: don't build one. Every `.ts` tool inspected (`backfill.ts`, `pipeline.ts`, and the 16 read in full for this phase) is a thin `Bun.$` wrapper around a `scripts/*.py` CLI; an agent with Bash access reproduces 100% of that behavior by invoking the script directly. Standing up a persistent MCP server to re-encode 16+ CLI wrappers is real infrastructure for zero behavioral gain, and it's exactly the "second copy that drifts silently" failure mode this whole refresh exists to fix (§1.1's `AGENTS.md:11`/`:48` precedent). | `docs/opencode_docs_challenge.md` §D1 |
| D2 | Commands → Skills 1:1 | **Adopt.** `.opencode/commands/*.md` → `.claude/commands/*.md`, flat, 1:1 — not `.claude/skills/`. All 5 commands (`analyze.md`, `lab.md`, `new-exp.md`, `pipeline.md`, `run-exp.md`) are single-file `$ARGUMENTS` prompt templates with nothing to bundle; converting them to skill directories is overhead with no payoff, especially once D1 removes the one thing (a tool script) that might have justified bundling. Claude Code's docs confirm existing `.claude/commands/` files keep working. | §D2 |
| D3 | New-tool-per-script as a live OpenCode-tooling gap | **Adopt, out-of-scope-flagged.** Recorded in §3.3 as a follow-up, not actioned here: 5 of 6 `backfill_*.py` scripts have no `.ts` wrapper (`backfill.ts` covers only `backfill_artifacts.py`), while the 5 `review_*`/`*_reviews.py` scripts are already folded correctly (reachable only via `pipeline.ts`'s phases) — that's the pattern to imitate. §3.1's `review.ts` design follows the fold pattern explicitly. | §D3 |
| D4 | Two independently-maintained enumerations (script map, lab list) as terminal state | **Adopt.** §2 designates one authoritative location per fact and turns the other into a pointer: `scripts/CONTEXT.md` becomes the full script table (`mental-model.md`'s "Script map" collapses to a categorized summary + pointer); `lab-books/SKILL.md` (already correct) becomes the lab list source of truth (`lab.md` drops its inline list). | §D4 |
| D5 | Duplicate full descriptions of `supervisor.py`/`workflow_runner.py`/`test_runner.py` in two docs | **Adopt.** `mental-model.md` gets a one-clause name-drop only; `src/instrument/CONTEXT.md`'s module table is the sole full description (already required by acceptance item 18). | §D5 |
| D6 | `opencode.json`/agent `model:` field verification bar | **Adopt, tightened.** Acceptance item 17 (§5) now requires the fix be justified by a real completed-run artifact (`experiments/results/stories/*deepseek-v4-flash*.json` filenames), not a source grep — grep alone would have been the wrong bar for a `PROVIDER_PRICING`-alias-style field. | §D6 |
| D7 | Flag-parity audit under-sampled (3 of 16 tools checked, all 3 had drift) | **Adopt.** §3.3 lists the 12 remaining unaudited tools explicitly as a checklist item rather than letting the 3 found instances (`run_story.ts`, `enqueue.ts`, `pipeline.ts`) look like the complete list. `batch.ts` is now a 4th checked instance (via this phase's own read, see §3.2) — real but minor (a wording overclaim, not a missing flag). | §D7 |
| D8 | Ship committed `.claude/*` files this phase | **Adopt.** Confirmed this phase: `find .claude` and `ls CLAUDE.md` both return nothing — there is no existing Claude Code surface in this repo, and §2's drift-fix is rewriting the exact opencode sources a port would translate. This spec's deliverable is the mapping design (§4) only; §4's own header restates the two gates for actually generating `.claude/*` files (drift-fix landed; explicit user go-ahead that Claude Code becomes a second supported interface). | §D8 |

---

## 2. File-by-file edit plan (drift fix)

Ordered load-bearing-first per the task's own instruction. Each entry gives the current
(stale) state and the target state; line numbers are from the 2026-08-14 read done for
this phase.

### 2.1 `AGENTS.md` (58 lines — loaded every session, `opencode.json:6`)

- **Line 48** — self-contradicts line 11. Change:
  `` `src/instrument/experiment_spec.py` (spec dataclasses + requires/produces validator) is **written**; `src/instrument/compile_experiment.py` (spec → DAG) is still proposed. ``
  →
  `` Both `src/instrument/experiment_spec.py` and `src/instrument/compile_experiment.py` are **written** — see `src/instrument/CONTEXT.md` for the module table and the ledger's still-unmeasured fields. ``
- **Key files section (after line 46)** — add one bullet per acceptance item 4, a
  signpost (not a rewrite) to the existing Control Room design-doc cluster:
  `` - `docs/supervisor_design.md` — Control Room / supervisor subsystem (flag-only rail: observe, never steer); see also `docs/spec.md`, `docs/scope.md` for the fuller design cluster. ``
- **Line 28** (Commands block) — tighten the `admin/server.py` comment, which currently
  reads `# SSE dashboard (default 8000 = ChromaDB; use FINOPS_PORT)`: append
  `` — now the Control Room portal (matrix/status/flags/design-sessions/claude-agents), see docs/supervisor_design.md ``. Don't inline the full route list here; that belongs in `scripts/CONTEXT.md` (§2.7).
- No other changes; §1.16's instrumentation gap (line 11's `confidence`/`perturbation_strength`/`test_executed_success` list) is factually current and must not be touched (acceptance item 19).

### 2.2 `.opencode/instructions/mental-model.md` (238 lines — loaded every session, `opencode.json:7`)

- **Line 33** `## The spec/compiler layer — PARTIALLY BUILT` → `## The spec/compiler layer — WRITTEN`
- **Line 35** rewrite: `` Two modules, per the design doc: `experiment_spec.py` (dataclasses, YAML loader, requires/produces validator, tests) and `compile_experiment.py` (spec → DAG). Both are **written**. ``
- **Lines 39–42** code block — change
  `` compile_experiment.py  — proposed — spec → DAG; generalizes _gen_matrix_cells + routing.simulate_strategies `` → `` compile_experiment.py  — WRITTEN — spec → DAG; generalizes _gen_matrix_cells + routing.simulate_strategies ``
- **Line 140** `### Proposed signatures (spec/compiler — not in the repo yet)` → `### Spec/compiler signatures (written — src/instrument/{experiment_spec,compile_experiment}.py)`
- **Line 169** `### Ledger (the data model rules consume) — PROPOSED` → `### Ledger (the data model rules consume) — schema WRITTEN; fields below marked UNMEASURED are the open instrumentation gap`. This wording is deliberate: it must not read as "the whole ledger is proposed" (false — `LEDGER_FIELDS` is written and tested) nor as "the gap is closed" (false — acceptance item 19 guard). Keep the inline `# ← UNMEASURED TODAY; model_cascade needs it` comment on `confidence` unchanged.
- **Architecture section (after the "Today" code block, ~line 31)** — add, per D5, a
  **one-clause** mention only (full descriptions live in `src/instrument/CONTEXT.md`,
  §2.7):
  ```
  supervisor.py ── Redis flag/session↔cell mapping contracts (no OpenCode client dep — observe only, see docs/supervisor_design.md)
  workflow_runner.py ── executes an agent_task workflow's phases inside a git worktree, committing + ledgering each
  test_runner.py ── independent pytest/jest/go-test/cargo-test runner; sole source of truth for test_executed_success
  ```
- **Lines 186–211 ("Script map")** — per D4, collapse from a partial hand-list to a
  short categorized summary plus a pointer, instead of trying to enumerate all 78:
  ```
  ## Script map

  78 scripts across 5 categories (experiment runners, post-hoc analysis, data pipeline,
  19 active lab_*.py + 8 deprecated *_bge_m3, Redis queue/review workers). Full table:
  `scripts/CONTEXT.md` (the authoritative, per-script reference — keep this pointer,
  don't re-duplicate the table here).

  Primary entry points: run.py, run_story.py, run_workflow.py, pipeline.py,
  inventory.py, build_data.py, sync_data.py, analyze_worktrees.py,
  analyze_trajectories.py, validate_session.py, enqueue.py + worker.py,
  review_all.py (+ review_stories.py/review_worker.py/trigger_reviews.py/
  enqueue_reviews.py/finalize_reviews.py), monitor.py, generate_manifest.py.

  admin/server.py — Control Room portal: SSE telemetry, routing, supervisor flags,
  design sessions, Claude background sessions (port 8000, FINOPS_PORT). Full route
  list: scripts/CONTEXT.md.
  .opencode/tools/dashboard.ts — pull tool: Redis status matrix via monitor.py --json
  ```
  This removes the phantom `scripts/compile_experiment.py — [proposed]` line (the real
  module is `src/instrument/compile_experiment.py`, a library with no CLI — see §3.1's
  `compile_experiment.ts` design for how that's handled) and satisfies acceptance items
  6 and 7 by delegating completeness to `scripts/CONTEXT.md` rather than duplicating it.
- **Lines 213–225 ("Test files")** — no other doc owns this list, so it stays here
  (not a D4 case), but hand-enumeration is still a drift trap. Replace the flat filename
  list with a categorized-by-module-family summary (core pipeline, admin/supervisor,
  claude-agents, instrument modules, spec/compiler) totaling **39** files, plus a
  literal line: `` verify current count: `ls tests/test_*.py | wc -l` ``. Explicitly
  include the 12 previously-missing files by name once, in their category
  (`test_compile_experiment.py`, `test_experiment_spec.py`, `test_workflow_runner.py`,
  `test_supervise.py`, the 6 `test_admin_*`, the 2 `test_claude_agents_*`).
- **Line 237** (Navigation table, "Task: spec/compiler → Read code_reviews/...") —
  re-verified this phase: no stale wording found here (no "proposed" or future tense).
  **No change required** — scope's original line-237 citation doesn't reproduce against
  the current file; leave as-is and don't let the build phase "fix" a line that isn't
  broken.

### 2.3 `.opencode/instructions/conventions.md` (73 lines)

- **Line 13** `## Spec/Compiler Conventions (proposed — see code_reviews/2026-08-14)` → `## Spec/Compiler Conventions (written — see code_reviews/2026-08-14)`
- **Line 24** `` Specs live in `experiments/specs/*.yaml` (proposed dir). `` → `` Specs live in `experiments/specs/*.yaml` (11 real specs, e.g. `agentic_dynamics_story.yaml`). ``
- **Lines 35–38** — rewrite from future-tense conditional to present-tense fact: `` Do NOT hand-author policy logic as a one-off in scripts. `compile_experiment.py` is written and generalizes `_gen_matrix_cells` (`pipeline.py:394`) as `experiment_matrix` and `routing.simulate_strategies` (`routing.py:98`) as `compare_arms` — route new grid/comparison work through the spec, not through direct calls to those two. ``
- **Lines 53–54** — fix `BUILTIN_STORIES` names: `` task_manager_story, static_site_gen_story, notification_service_story `` → `` task_manager_api, static_site_gen, notification_service ``

### 2.4 `.opencode/agents/*.md` (3 files)

**`data-analysis.md`**
- **Lines 53–59 ("Spec-driven phases (proposed)")** — relabel: `` The compiler (`compile_experiment.py`, proposed) reframes `` → `` The compiler (`compile_experiment.py`, written) reframes ``. The rest of the paragraph (which specific arms aren't authored yet) stays — that's the genuinely-still-open instrumentation gap, not doc drift.
- **Frontmatter `model:`** (line 4) — `deepseek/deepseek-chat` → `deepseek/deepseek-v4-flash` (see §2.8 for the verification bar).

**`instrument-dev.md`**
- **Line 11** `` Your domain is the measurement apparatus: 33 modules in `src/instrument/` plus two proposed modules (`experiment_spec.py`, `compile_experiment.py`) that are the next build target. `` → `` Your domain is the measurement apparatus: 38 modules in `src/instrument/`, including `experiment_spec.py` and `compile_experiment.py` (both written). ``
- **Line 21** `The proposed spec/compiler layer generalizes` → `The spec/compiler layer (written) generalizes`
- **Lines 50–52 ("Proposed modules — NOT yet in the repo")** — remove the "proposed" framing entirely; fold `experiment_spec.py` / `compile_experiment.py` into the regular **Module Map** list (lines 29–48) as two more rows, same format as the other entries (name, lines, purpose, key exports), not a separate speculative section.
- **Frontmatter `model:`** — same fix as data-analysis.md.

**`pipeline-ops.md`**
- **Lines 79–81** (plan enumeration) — add the missing plan: `` Plans: `ci` (...), `deploy` (...), `full_matrix` (...), `feature` (...), `ship_features` (...). `` → append `` , `cross_models` (flash → haiku → sonnet → sol → terra → analyze → reviews → regenerate → deploy) ``.
- **Lines 90–91 ("Spec/Compiler (proposed — next build target)")** → `## Spec/Compiler (written)`, same present-tense rewrite pattern as §2.3.
- **Frontmatter `model:`** — same fix.

### 2.5 `.opencode/skills/*/SKILL.md` (3 files)

**`analyze/SKILL.md`**
- **Lines 173, 175, 179** ("Measure / Compare / Writeup (proposed — spec-driven)" section) — relabel header to `(written — spec-driven)`; the phase-mapping table's "Proposed (spec-driven)" column header can stay as a column label (it's describing a target-state column, not asserting the compiler doesn't exist) but the paragraph before/after it should say "written," matching the pattern above.

**`instrument/SKILL.md`**
- **Lines 23, 29, 32–34** ("Spec & Compiler (proposed — next build target)") — relabel `proposed` → `written`; the `experiment_spec.py`/`compile_experiment.py` code block loses its "not yet in the repo" comment.
- **Line 55** — `` **Flagship spec:** `experiments/specs/routing_regret.yaml` (proposed) `` → replace with a real spec filename, e.g. `` **Example spec:** `experiments/specs/agentic_dynamics_story.yaml` (one of 11 real specs in `experiments/specs/`) ``. `routing_regret.yaml` doesn't exist anywhere as a file (confirmed by scope's repo-wide `find`); don't keep it as the flagship example even marked proposed — pick a real one.
- **Line 57** (`BUILTIN_STORIES dict keys` comment) — fix the `*_story`-suffixed names to `task_manager_api`, `static_site_gen`, `notification_service` (same fix as `conventions.md` §2.3).
- **Line 147–150** — same `BUILTIN_STORIES` key fix, second occurrence in this file.
- **Line 190** (`PROVIDER_PRICING` keys comment) — currently `` # Keys: "deepseek", "anthropic", "anthropic-sonnet5", "openai", "openai-luna" `` — expand to all 9: `` # Keys: "deepseek", "deepseek-flash", "anthropic", "anthropic-sonnet5", "anthropic-haiku", "openai", "openai-luna", "openai-sol", "openai-terra" ``. Do **not** remove `anthropic-sonnet5` — it's a real, actively-resolved key (`efficiency.py:_resolve_pricing_key`), not a hallucination.

**`lab-books/SKILL.md`**
- No change needed to its own content (already says "19 active lab books" correctly, confirmed both at the frontmatter description and line 3). Per D4, this file *becomes* the authoritative lab-list source that `lab.md` (§2.6) points to instead of re-listing.

### 2.6 `.opencode/commands/*.md` (5 files)

**`lab.md`** — per D4, don't reconcile the inline count/list, delete it:
- **Line 7** `Run a specific lab book analysis from the 14 available labs.` → `Run a specific lab book analysis. Load the "lab-books" skill for the current list (19 active labs).`
- **Lines 14–18** (the 13-name enumeration, itself short of the file's own "14" claim) — delete entirely; the command already says "First, load the 'lab-books' skill" (line 9) — that skill is now the single source of truth for the list, per D4.

**`new-exp.md`**
- **Line 9** `` > Spec direction (proposed): the `ExperimentSpec` + compiler (...) will make this command "author a spec" ``... → rewrite from a "future direction" callout to a present-tense capability note: `` > Spec direction: `compile_experiment.py` is written and can compile an `ExperimentSpec` YAML into cells, but this command still writes a config directly — no spec-authoring UI exists yet for this command specifically. Control rules (e.g. `model_cascade`/`dynamics`) still require `confidence`, which is not yet instrumented — measure before policy. `` (Distinguishes "the compiler is written" from "this specific command doesn't use it yet," which is still true and shouldn't be erased.)

**`pipeline.md`**
- **Line 22** `` Spec direction (proposed): `compile_experiment.py` will add a compile/validate phase `` → `` Spec direction: `compile_experiment.py` is written and can add a compile/validate phase (...); this command's manual chain still runs the transport-only path directly. `` — same present-tense-but-not-erasing-the-gap pattern as `new-exp.md`.

**`run-exp.md`**
- **Line 22** — same fix pattern: `` Spec direction (proposed): `compile_experiment.py` will compile `` → `` Spec direction: `compile_experiment.py` is written and can compile `` (rest of sentence unchanged).

**`analyze.md`** — confirmed silent (no compiler mention at all), not stale. No required change. Optional: one clause added to the last line pointing at `code_reviews/2026-08-14_...md`, but this is not required by any acceptance item.

### 2.7 The four `CONTEXT.md` files

**`experiments/CONTEXT.md`** (142 lines)
- **Line 5** `` ## `experiments/specs/` — ExperimentSpec YAML (proposed) `` → `` ## `experiments/specs/` — ExperimentSpec YAML (written; 11 real specs) ``
- **Line 10** `` Flagship: `experiments/specs/routing_regret.yaml` `` → same fix as `instrument/SKILL.md:55` (§2.5): replace with a real spec, e.g. `agentic_dynamics_story.yaml`. Keep the illustrative YAML snippet (lines 12–20) as-is — it's schema-accurate regardless of which file is named as the example.

**`scripts/CONTEXT.md`** (111 lines) — per D4, this becomes the **authoritative full
script table**; it gets the larger diff of the two script-map fixes.
- **Line 3** `74 Python scripts` → `78 Python scripts`
- **Line 15** (Primary Entry Points table) — the `compile_experiment.py` row currently
  reads `` [proposed] spec → DAG ... | Not yet written — see design doc ``. This is
  doubly wrong: the module is written, *and* it doesn't live in `scripts/` at all (it's
  `src/instrument/compile_experiment.py`, a pure library — no CLI). Replace the row
  with: `` `src/instrument/compile_experiment.py` (not in scripts/) | spa → DAG compiler, **written**; no standalone CLI — invoke via the `compile_experiment` tool (§3.1) or the Python API directly | Compiling a spec into a DAG ``.
- **Lines 94–96 ("Spec/Compiler (proposed — not yet written)")** — relabel header to
  `(written)`; fix the same not-in-scripts/ path issue as above in the surrounding prose.
- **Reconcile the table against `mental-model.md`'s pre-collapse content and the real
  78-file list.** Concretely, add rows (in the matching category) for the scripts
  currently present in `mental-model.md`'s old script map or the repo but absent from
  this file: `generate_manifest.py`, `plan.py` ([deprecated] — hardcoded phase
  orchestration, superseded by `pipeline.py`), `sync_data.py`, `backfill_sonar.py`,
  `backfill_costs.py`, `backfill_deep_metrics.py`, `backfill_story_artifacts.py`,
  `compute_sonar_deltas.py`, `embed_sessions.py`, `rescore_conventions.py`,
  `verify_tests.py`, `run_workflow.py`, `supervise.py`, `claude_agents_supervisor.py`,
  `analysis_worker.py`, `analyze_stories.py`, `enqueue_analysis.py`, `enqueue_reviews.py`,
  `finalize_reviews.py`, `trigger_reviews.py`, `recover_stories.py`, `batch_stories.py`.
  Each row: script name, line count, one-line purpose (pull from the script's module
  docstring / argparse `description=`, same style as existing rows). Verify the final
  table sums to 78 (`ls scripts/*.py | wc -l`).
- **Line 89** (Admin Portal table, `admin/server.py` row) — currently lists 5 routes
  (`/api/matrix`, `/api/status`, `/api/events/<cell>`, `/api/routing`,
  `POST /api/experiments`). The file has **24** routes today (confirmed via
  `grep -c '@app\.\(get\|post\)' admin/server.py`). Replace the flat 5-route list with
  a categorized summary: legacy telemetry (`/api/matrix`, `/api/status`,
  `/api/events/<cell_id>`, `/api/routing`, `POST /api/experiments`), supervisor flags
  (`/api/flags`, `POST /api/flags/<session_id>/steer`,
  `POST /api/flags/<session_id>/interrupt`), design sessions (`/api/design-sessions*`,
  6 routes), Claude background sessions (`/api/claude-agents*`, 8 routes, incl.
  `/api/claude-agents/daemon`). Add one sentence: "Full endpoint reference:
  `docs/supervisor_design.md`, `docs/spec.md`." (points at the existing design-doc
  cluster instead of re-deriving it — same discipline as §1.3 in the scope doc).

**`src/instrument/CONTEXT.md`** (186 lines)
- **Line 3** `33 Python modules` → `38 Python modules`
- **Lines 5–7** — relabel `compile_experiment.py` status header from "proposed" to
  "written," matching the fix pattern used everywhere else.
- **Module Reference table** — add 16 rows across appropriate existing category
  headers (module: category):
  `story.py` → new "Story / Multi-Session" category (or fold into Core Pipeline);
  `mutation.py`, `commit_analysis.py`, `review.py`, `entropy.py`, `codebase_graph.py`,
  `lsp_diagnostics.py` → same new category, matching how `instrument-dev.md:19`
  already groups them as "v0.6-v0.9";
  `embeddings.py`, `graph.py`, `ollama_analyzer.py`, `opencode_analyzer.py`, `sonar.py`
  → "Validation Modules" or a new "Analysis / Graph" category;
  `language.py` → Backend/Telemetry/Routing (it's the foundation module per its own
  "Adding a New Language" section later in this file);
  `supervisor.py`, `workflow_runner.py`, `test_runner.py` → new "Control Room / Workflow"
  category — this is the **one full description** of these 3 modules per D5 (don't
  duplicate in `mental-model.md`, which gets only the one-clause version, §2.2).
- **Line 92** (`compile_experiment.py` row in the spec/compiler table) — status
  `proposed` → `written`.
- **Lines 111–113** (the `AttemptRecord` UNMEASURED-field comments: `confidence`,
  `perturbation_strength`, `test_executed_success`) — **do not touch.** These are the
  genuinely-open instrumentation gap (scope §1.16, acceptance item 19); the doc-refresh
  changes the word "proposed" around the schema, not the measured/unmeasured status of
  individual fields.

**`firebase/CONTEXT.md`** (44 lines) — confirmed this phase: never mentions the
compiler/spec at all. Silent, not stale. **No required change.**

### 2.8 `opencode.json`

- **Line 4** `"small_model": "deepseek/deepseek-chat"` → `"small_model": "deepseek/deepseek-v4-flash"`.
  **Verification bar (per D6, tightened from the scope doc's grep-based bar):** confirmed
  by real completed-run artifacts, not source grep — `deepseek/deepseek-v4-flash` appears
  in actual result filenames under `experiments/results/stories/` (e.g.
  `notification_service_deepseek_deepseek-v4-flash_clean_*.json`), meaning a real API
  call resolved successfully with that exact string. `deepseek/deepseek-chat` appears
  **nowhere** else in the repo (0 hits in `src/`, `scripts/`, `experiments/configs/`, or
  result data) — it's dead config, not an intentional smaller-model choice.
- No other fields need changes. `compaction`, `subagent_depth`, `formatter`, `lsp`,
  `permission.*` are all live/accurate as read this phase — see §4 for how each ports
  (or doesn't) to Claude Code, which is a separate question from whether they're
  correct *as opencode config today* (they are).

### 2.9 `code_reviews/2026-08-14_experiment-spec-and-compiler-design.md` status header

- **Line 3** `Status: proposed (v2, corrected) · Owner: AI FinOps Dynamics instrument`
  → `Status: written (v2, corrected) — spec (experiment_spec.py) and compiler
  (compile_experiment.py) both implemented and tested; the load-bearing instrumentation
  gap (confidence, perturbation_strength, test_executed_success, answer/explanation
  token split) remains open — see §7/ledger. · Owner: AI FinOps Dynamics instrument`.
  This is the single source line every "written vs. proposed" fix elsewhere in §2
  ultimately traces back to (`AGENTS.md:11` already cites this file as ground truth) —
  fixing it last, after every doc that quotes it, ensures the citation and the cited
  fact agree once the whole pass lands, rather than fixing the source before its 15
  downstream quoters are ready to match it (order doesn't matter for correctness here
  since it's a single self-contained line, but doing it last keeps a clean single
  commit boundary: "make every doc match `AGENTS.md:11`" as the very last verification
  step).

---

## 3. New tools + tool fixes (`.opencode/tools/*.ts`)

All new tools follow the repo's existing convention: `tool()` from
`@opencode-ai/plugin`, Zod args, `Bun.$` subprocess wrapping a `scripts/*.py` CLI,
`.cwd(ctx.directory)`. Two of the nine break that convention on purpose — flagged
individually below, not hidden in the table.

### 3.1 New tools

| Tool file | Wraps | Args (zod) | Notes |
|---|---|---|---|
| `analyze_trajectories.ts` | `scripts/analyze_trajectories.py` | `limit?: number`, `model?: string`, `dry_run?: boolean` (→ `--limit`, `--model`, `--dry-run`) | Straightforward wrapper, matches `run_story.ts`'s shape. |
| `sync_data.ts` | `scripts/sync_data.py` | `mode?: enum(["sync","check","query"]).default("sync")`, `query?: string` (required when `mode="query"`, else tool returns a usage error before shelling out) | `sync` (default, no flag) → `sessions.parquet`/`stories.parquet`; `check` → `--check`; `query` → `--query <sql>`. |
| `validate_session.ts` | `scripts/validate_session.py` | `workdir?: string`, `session_id?: string`, `model?: string.default("all")` | → `--workdir`, `--session-id`, `--model`. |
| `generate_manifest.ts` | `scripts/generate_manifest.py` | `{}` (script takes no flags) | Writes `data_manifest.json` (schema version, file SHA256s, git commit, opencode version, known limitations). |
| `review.ts` | `scripts/review_all.py`, `review_stories.py`, `trigger_reviews.py`, `enqueue_reviews.py`, `finalize_reviews.py` — **folded into one tool** (D3's "fold, don't fan out" pattern, same shape as `pipeline.ts`/`worker.ts`'s `action` enum, not 5 near-duplicate tool files) | `action: enum(["all","stories","trigger","enqueue","finalize"]).default("all")`, `workers?: number`, `story?: string` (substring filter, `action="all"` only), `dry_run?: boolean` | `all` → `review_all.py [--workers N] [--story X] [--dry-run]`; `stories` → `review_stories.py [--dry-run]`; `trigger` → `REVIEW_WORKERS=<workers> python3 scripts/trigger_reviews.py` (this one **polls and spawns background workers** — same "returns immediately, work continues" contract as `worker.ts action:"start"`, not a synchronous wait); `enqueue` → `enqueue_reviews.py [--dry-run]`; `finalize` → `finalize_reviews.py`. `review_worker.py` itself (the Redis loop) is intentionally **not** independently exposed — it's spawned by `action:"trigger"`, matching how `worker.py` is only reachable via `worker.ts`'s lifecycle actions, not invoked raw. |
| `run_workflow.ts` | `scripts/run_workflow.py` | `spec: string` (required, ExperimentSpec YAML path), `goal: string` (required), `model: string` (required), `workdir: string` (required, git worktree path), `backend?: enum(["opencode","claude_cli"])`, `thinking_effort?: string.default("high")`, `thinking_budget_tokens?: number.default(0)`, `output_token_limit?: number.default(0)`, `timeout_min?: number.default(30)` (→ `--timeout <seconds>`), `no_commit?: boolean`, `resume?: boolean` | Direct 1:1 flag mapping — `run_workflow.py`'s argparse is already complete and stable (`--spec`, `--goal`, `--model`, `--workdir`, `--backend`, `--thinking-effort`, `--thinking-budget-tokens`, `--output-token-limit`, `--timeout`, `--no-commit`, `--resume`). |
| `compile_experiment.ts` | `src/instrument/compile_experiment.py` (`compile_spec()`, `validate_rules()`) + `experiment_spec.load_spec()` | `spec: string` (required, `experiments/specs/*.yaml` path), `mode?: enum(["validate","compile"]).default("validate")` | **Flagged, breaks convention.** `compile_experiment.py` has **no CLI** — it's a pure library (confirmed: no `argparse`/`ArgumentParser`/`__main__` in the file), and no `scripts/*.py` wraps it (§2.7 already fixes the doc that wrongly implied one exists). Every other tool in this directory shells to a `scripts/*.py` file; this one must instead shell to an inline `python3 -c` snippet that imports `load_spec`, then `validate_rules`/`compile_spec`, and prints JSON. Two ways to resolve this, recorded here rather than picked unilaterally: **(a)** ship the `python3 -c` inline-script tool as designed (works today, zero code changes elsewhere) — this is the docs-refresh-compatible default; **(b)** add a thin `scripts/compile_spec_cli.py` wrapper first (mirrors every other tool's shape, but is a real code change, out of scope for a doc-only pass — same "record, don't action" treatment as §3.3's backfill-tool gap). Recommend (a) now, (b) later if this tool sees real use. |
| `supervisor.ts` | `scripts/supervise.py` (the actual CLI; `src/instrument/supervisor.py` itself is the no-CLI Redis-contract library it, `admin/server.py`, `live.py`, and `design_sessions.py` all import) | `once?: boolean.default(true)` (→ `--once`), `location?: string.default(ctx.directory)` (→ `--location`) | **Default `once: true` is deliberate**, not just a sane default: every existing tool in this directory does one bounded unit of work per call (the `worker.ts action:"start"` background case is the sole controlled exception, and it's clearly a start/stop lifecycle, not silent open-ended running). **Security-relevant constraint:** this tool must only ever expose the `--once` flag-and-observe path. `supervisor.py` deliberately has no OpenCode client dependency "so observation can't become control" (scope §1.2) — do not add a mode, flag, or follow-up tool that lets an agent invoke a steering/interrupt action through this tool; that capability exists only at `admin/server.py`'s human-operated `POST /api/flags/<session_id>/steer` and `/interrupt` routes, which `control_room.ts` (below) also must not wrap. |
| `control_room.ts` | `admin/server.py`'s REST API (**HTTP `fetch`, not `Bun.$`** — the one other convention break, because this targets a running Flask server, not a CLI) | `endpoint: enum(["matrix","status","flags","routing","design_sessions","claude_agents"]).default("status")` | Requires the portal already running on `FINOPS_PORT` (default 8000) — this tool does **not** start it (that's `python admin/server.py`, unchanged). **Read-only GET endpoints only** (`/api/matrix`, `/api/status`, `/api/flags`, `/api/routing`, `/api/design-sessions`, `/api/claude-agents`). Do **not** wrap any `POST` route (`/api/flags/<id>/steer`, `/api/flags/<id>/interrupt`, `/api/design-sessions/<id>/interrupt`, `/api/claude-agents` create/stop/respawn/rm/steer) — those are the human-operator control surface, and exposing them as an agent-callable tool would let a session steer or interrupt itself or a peer session through the one channel the architecture deliberately keeps flag-only (same boundary as `supervisor.ts` above; this is the same design constraint stated twice because it's easy for a future edit to add "just one more" POST endpoint to either tool without noticing it crosses the line). SSE endpoints (`/api/events/<cell_id>`) are excluded as out of scope for a synchronous request/response tool. |

That's 9 files for 8 requested capabilities — `supervisor`/`control_room` is split into
two tools rather than one because they have fundamentally different invocation
mechanisms (subprocess vs. HTTP) and different running-process preconditions
(`supervisor.ts` needs nothing running beyond Redis; `control_room.ts` needs
`admin/server.py` already up) — folding them into one tool with a mode flag would hide
that precondition difference behind a single description string.

### 3.2 Fixes to existing tools

| Tool | Current | Fix |
|---|---|---|
| `run_story.ts` | `CONDITIONS = ["clean", "bad_seed", "early_degrade"]` (3, missing `late_degrade`) | `CONDITIONS = ["clean", "bad_seed", "early_degrade", "late_degrade"]` (4, matches `story.py:47-50` and `scripts/run_story.py --condition` choices). Also add pass-through args for the 6 flags `scripts/run_story.py` supports that the tool doesn't: `backend?: enum(["opencode","claude_cli"])`, `codebase?: string`, `worktree_root?: string`, `results_dir?: string`, `output_limit?: number`, `standardize?: boolean.default(true)` (→ `--no-standardize` when false). Acceptance item 16 accepts *either* exposing these *or* documenting the tool as an intentionally reduced subset — this spec chooses "expose them," since they're all real, already-stable `run_story.py` flags with no reason to hide. |
| `enqueue.ts` | Exposes only `dry_run`/`clear` (2 of `scripts/enqueue.py`'s flags) | Add `model?: string` (→ `--model <provider/model>`) and `missing_only?: boolean` (→ `--missing-only`), matching `scripts/enqueue.py:146-154`. Per scope §1.15, no doc currently *claims* these flags exist, so this is a pure capability gap, not a doc-vs-tool contradiction — low risk, additive only. |
| `pipeline.ts` | `plan` arg is `tool.schema.string()` (not an enum) — the value `cross_models` **already works today**, it's only the description text that's wrong | This is a prose-only fix, not a schema widen. Line 5 description: append `` , `cross_models` (flash → haiku → sonnet → sol → terra → analyze → reviews → regenerate → deploy) `` to the plan list. Line 16 `.describe()`: `"Plan name: ci, deploy, full_matrix, feature, or ship_features"` → `"Plan name: ci, deploy, full_matrix, cross_models, feature, or ship_features"`. |
| `batch.ts` | Description: `"Run parallel batch experiments across all 13 task configs using DeepSeek V4 Pro with 3 concurrent workers"` | The numbers (13 configs, 3 workers, DeepSeek V4 Pro) are **accurate** — confirmed against `scripts/batch_run.py:CONFIGS` (13 entries) and `ThreadPoolExecutor(max_workers=3)`. The word "all" is the only problem: it implies these 13 are the complete config set, but `experiments/configs/` has 34 total — `batch_run.py`'s `CONFIGS` is a fixed, hardcoded 13-config subset. Fix: `"Run parallel batch experiments across a fixed 13-config subset (scripts/batch_run.py:CONFIGS — not all 34 configs in experiments/configs/) using DeepSeek V4 Pro with 3 concurrent workers"`. |

### 3.3 Flag-parity audit backlog (D7 — explicit, not implicit)

3 of 16 existing `.ts` tools were checked for tool-vs-script flag-parity drift before
this phase (`run_story.ts`, `enqueue.ts`, `pipeline.ts`) plus `batch.ts` checked this
phase — **all 4 had real drift** (3 missing flags/enum entries, 1 misleading
description). That's a 100% hit rate on a 4-tool sample out of 16. The remaining 12
tools have **not** been checked and are listed here explicitly so the build/verify
phases don't treat §3.2's 4 fixes as the complete list:

`analyze_worktrees.ts`, `archive_worktrees.ts`, `backfill.ts`, `build_data.ts`,
`dashboard.ts`, `inventory.ts`, `list_stories.ts`, `monitor.ts`, `run_experiment.ts`,
`run_lab.ts`, `sweep.ts`, `worker.ts`.

Recommended check (same pattern used to find the 4 already-fixed instances): for each
tool, diff its Zod args + shelled flags against the wrapped script's `argparse`
`add_argument` calls. Time-box if needed; at minimum this list should survive into the
verify phase as an open item, not be silently dropped.

Separately (D3, explicitly **not** actioned this pass, code scope not doc scope):
`backfill.ts` wraps only `backfill_artifacts.py` of 6 `backfill_*.py` scripts (3 of the
other 5 — `backfill_costs.py`, `backfill_deep_metrics.py`, `backfill_story_artifacts.py`
— are independently confirmed doc-missing by §2.7's scripts/CONTEXT.md fix). If a
follow-up ever addresses this in code, the `review.ts`/`pipeline.ts` `action`-enum
pattern (fold, don't fan out) is the precedent to follow — a `target: "artifacts" |
"costs" | "deep_metrics" | "story_artifacts"` arg on `backfill.ts`, not 3 new files.

---

## 4. OpenCode → Claude Code taxonomy mapping

Two gates on generating actual `.claude/*` files, restated from §1's D8 adjudication:
**(1)** §2's drift-fix lands first, so there is one stable, correct opencode source to
translate instead of two moving targets; **(2)** an explicit decision — from the user,
not inferred here — that Claude Code becomes a supported second interface for this
repo. Until both are true, this table is the deliverable: a design/reference document,
not a generation script.

| OpenCode | Claude Code | Notes | Status |
|---|---|---|---|
| `AGENTS.md` (project root) | `CLAUDE.md` (project root) | Claude Code does not read `AGENTS.md`. Documented pattern for repos serving both tools: `CLAUDE.md` containing `@AGENTS.md` (or a symlink), plus Claude-specific additions below the import. Target under 200 lines; loaded in full at launch, walking up the directory tree. | verified-against-docs (scope §3, re-confirmed this phase) |
| `.opencode/instructions/mental-model.md`, `conventions.md` | `.claude/rules/mental-model.md`, `.claude/rules/conventions.md` | Closest match to how these two files are used today (unscoped, loaded at launch). Modular alternative to one monolithic `CLAUDE.md`; supports symlinks for cross-project sharing. | verified-against-docs |
| `.opencode/agents/*.md` (3: `data-analysis.md`, `instrument-dev.md`, `pipeline-ops.md`) | `.claude/agents/*.md` | Near-1:1 by directory shape. Frontmatter differs: opencode uses `description`/`mode`/`model`/`temperature`/`permission`/`color`/`hidden`; Claude Code subagent frontmatter is a different field set (system prompt + tool access + permissions) — field-by-field mapping, not a blind copy. | needs-verification (directory/invocation model confirmed; exact frontmatter field list not re-fetched this phase) |
| `.opencode/commands/*.md` (5: `analyze.md`, `lab.md`, `new-exp.md`, `pipeline.md`, `run-exp.md`) | `.claude/commands/*.md` — **flat, 1:1** (per D2, not `.claude/skills/`) | All 5 are single-file `$ARGUMENTS`-template prompts with no bundled files; skills' main advantage (bundling supporting files) doesn't apply once §1's D1 removes the one thing (a tool script) that might have been bundled. Claude Code's docs confirm existing `.claude/commands/` keep working — commands and skills share the `/name` invocation mechanism. | verified-against-docs (mechanism); needs-verification (confirm `.claude/commands/` isn't further deprecated between now and port time) |
| `.opencode/skills/<name>/SKILL.md` (3: `analyze/`, `instrument/`, `lab-books/`) | `.claude/skills/<name>/SKILL.md` | Near-1:1; frontmatter mostly compatible (`name` + `description` required both sides). Claude Code doesn't enforce opencode's `^[a-z0-9]+(-[a-z0-9]+)*$` name/dir-match rule, but all 3 existing names already satisfy it, so no rename needed either way. | verified-against-docs |
| `.opencode/tools/*.ts` (16 existing + 9 new from §3.1 = 25) | **No direct file-based equivalent.** Nominal target: `.mcp.json` + an MCP server exposing equivalent tools. | **Flagged — does not port cleanly, and per D1's recommendation, shouldn't be built as an MCP server at all.** All 25 tools are (or would be) thin subprocess wrappers around `scripts/*.py` CLIs; a Claude Code agent with Bash access reproduces every one of them by invoking the script directly. Recommended port target instead: fold the *knowledge* each `.ts` tool encodes (valid flags, plan names, condition lists, which script it wraps) into `.claude/rules/` or a `.claude/skills/pipeline-ops/`-style doc that documents the `scripts/*.py` invocations directly — the same content §2's fixes already produce, just addressed to Bash instead of a custom tool call. Reserve actual MCP for a future need that requires structured, non-CLI access (e.g., live Redis state queries) — none of the 25 tools need that; they all shell out already. | needs-verification (MCP-as-nominal-target confirmed against docs; "don't build it" is this doc's recommendation, not a doc-verified fact) |
| `opencode.json` (root config) | `.claude/settings.json` | Both are project-root JSON config, both merge across scope layers (opencode: project/global/managed/remote; Claude Code: managed > CLI args > local > project > user). Port field-by-field per the rows below, don't copy verbatim — the schemas aren't structurally identical. | verified-against-docs (file existence, merge-not-replace behavior) |
| `opencode.json:"model"`, `"small_model"` | `.claude/settings.json:"model"` | Roughly 1:1 concept (default model selection); Claude Code has no documented `small_model`-equivalent tier field — a fast/cheap-model preference would need to be expressed per-agent (`.claude/agents/*.md` `model:` frontmatter) rather than globally. | needs-verification |
| `opencode.json:"instructions": ["AGENTS.md", ".opencode/instructions/mental-model.md"]` | *(no equivalent field)* | **Flagged — mechanism mismatch, not a missing field.** opencode requires an explicit file list; Claude Code auto-discovers `CLAUDE.md` + `.claude/rules/*.md` by directory convention, walking up the tree — there's nothing to "port" into, the equivalent is just placing files in the conventional locations (rows above). | needs-verification |
| `opencode.json:"compaction": {auto, prune, reserved: 15000}` | `.claude/settings.json:"autoCompactEnabled"` (bool) + `"autoCompactWindow"` (int, 100000–1000000 tokens) / `/autocompact` command | Confirmed live against `code.claude.com/docs/en/settings` and `/cli-reference` this phase: `autoCompactEnabled` toggles auto-compact on/off (opencode's `auto`); `autoCompactWindow` sets the token threshold (closest analog to opencode's `reserved`, though the two aren't the same unit — opencode reserves a token budget, Claude Code sets an absolute window size); the `/autocompact` slash command and `--autocompact` CLI flag both set the same value. opencode's `prune` (whether compaction actually deletes vs. just summarizes) has no confirmed Claude Code equivalent. | **verified-against-docs** (WebFetch confirmed `autoCompactEnabled`, `autoCompactWindow`, `/autocompact` all exist as described) |
| *(not used in this repo)* `opencode.json:"references"` (`@alias` syntax, local dirs or git repos) | `.claude/settings.json:"permissions.additionalDirectories"` | Confirmed live against `code.claude.com/docs/en/cli-reference` and `/settings` this phase: `--add-dir` grants a session extra readable/editable directories; `permissions.additionalDirectories` in settings persists that grant across sessions. Conceptually the closest match to opencode's `references` (extra context sources beyond the project root), though opencode's version supports remote git repos as sources and Claude Code's is local-filesystem-directories only. This repo doesn't use `references` today, so there's nothing to migrate — row included for taxonomy completeness only. | **verified-against-docs** (WebFetch confirmed `permissions.additionalDirectories` exists and is what `--add-dir` persists into) |
| `opencode.json:"permission"` (nested per-capability object: `edit`, `bash.*`, `task`, `external_directory`, `webfetch`, `skill`, each `"allow"`/`"ask"`/`"deny"`) | `.claude/settings.json:"permissions"` (`allow`/`deny`/`ask` arrays of tool-pattern strings, e.g. `"Bash(npm run lint)"`) | **Flagged — does not port verbatim, shape differs.** opencode nests permission by capability-then-verb; Claude Code flattens to pattern-matched arrays keyed by tool name. Porting requires translating each opencode capability (`bash.*` allow-map with per-command overrides like `"git push *": "ask"`) into equivalent `Bash(...)` patterns in the `allow`/`ask` arrays, not a structural copy. | needs-verification (Claude Code's array-of-patterns shape confirmed this phase via WebFetch; full translation of this repo's specific `bash` overrides not attempted here — that's port-implementation work, not taxonomy design) |
| `opencode.json:"lsp": true`, `"formatter": true` | *(no equivalent)* | **Flagged — does not port cleanly.** No documented Claude Code project-config field toggles LSP-backed diagnostics or auto-formatting at the settings level; Claude Code's tool-use model relies on the agent invoking formatters/linters via Bash rather than a framework-level toggle. Nothing to migrate this into — note the capability gap in the port write-up rather than inventing a fake mapping. | needs-verification (absence is harder to prove than presence; based on no matching field found in the settings/CLI docs fetched this phase, not an exhaustive negative search) |
| `opencode.json:"mcp"` (unused in this repo — `type: local`/`remote` server configs) | `.mcp.json` (project scope) | Both support local (command array) and remote (URL) MCP server definitions, different file. Not populated on either side currently — see the `.opencode/tools/*.ts` row above for why this repo likely shouldn't populate it just for the port. | verified-against-docs |
| `opencode.json:"subagent_depth": 2` | *(no equivalent)* | **Flagged — does not port cleanly.** No documented Claude Code field caps subagent nesting depth; Claude Code subagents are invoked by description-match or explicitly, without a numeric depth ceiling in settings. | needs-verification |
| *(no opencode equivalent — Claude-only feature)* | `~/.claude/projects/<project>/memory/*.md` (auto memory) | One-directional: Claude Code auto-writes durable, applicable lessons to a machine-local memory directory; opencode has no equivalent mechanism to port *from*. Not a gap in the port, just asymmetric tooling — noted for completeness since the taxonomy table would otherwise silently omit a whole Claude Code concept. | verified-against-docs (this session's own memory mechanism) |

---

## 5. Acceptance checklist

**Drift fix (§2) — build phase implements, verify phase checks. Supersedes
`docs/opencode_docs_scope.md` §4 items 1–21 (this list folds in D4/D5/D6 refinements;
where wording differs from scope's original phrasing, this list is authoritative):**

1. `AGENTS.md:48` matches `AGENTS.md:11` — both say `experiment_spec.py` and `compile_experiment.py` are written. No self-contradiction remains in the file.
2. Every doc touched in §2.1–§2.6 no longer calls the spec/compiler "proposed"/"not yet in the repo"/future-tense — all present-tense "written," pointing at `src/instrument/{experiment_spec,compile_experiment}.py`. (15 files, per scope §1.1's inventory, plus the `code_reviews/...md` status header itself, §2.9.)
3. `mental-model.md`'s architecture section names `supervisor.py`, `workflow_runner.py`, `test_runner.py` with a one-clause purpose each — and does **not** duplicate `src/instrument/CONTEXT.md`'s full descriptions of the same 3 modules (D5).
4. `AGENTS.md` and `mental-model.md` each carry a short signpost to the Control Room / supervisor design-doc cluster (`docs/spec.md`, `docs/scope.md`, `docs/supervisor_design.md`) — not a rewrite of those docs.
5. `scripts/CONTEXT.md`'s `admin/server.py` description reflects the current 24-route, 1368-line reality (categorized, not a flat stale 5-route list).
6. `scripts/run_workflow.py` appears by name in `scripts/CONTEXT.md`'s script table (the authoritative location per D4) — not necessarily in `mental-model.md`, which now points at `scripts/CONTEXT.md` instead of duplicating it.
7. `mental-model.md`'s "Script map" section is a categorized summary + explicit pointer to `scripts/CONTEXT.md`, not a second attempt at a full 78-script enumeration (D4) — and contains no phantom `scripts/compile_experiment.py` entry.
8. `scripts/CONTEXT.md`'s script count reads 78 (not 74), and its table is the single complete inventory — verified by `ls scripts/*.py | wc -l`.
9. `experiments/CONTEXT.md:5` no longer calls `experiments/specs/` "proposed"; its flagship example is a real filename (e.g. `agentic_dynamics_story.yaml`), not the nonexistent `routing_regret.yaml`.
10. Every plan-enumeration site (`.opencode/tools/pipeline.ts` description + `.describe()`, `.opencode/agents/pipeline-ops.md`, `scripts/CONTEXT.md`) lists all 6 plans including `cross_models`.
11. `.opencode/commands/lab.md` no longer inline-enumerates labs; it points to the `lab-books` skill (D4), which remains the single correct source (already says "19").
12. `experiments/lab_books/README.md`'s "All 13 lab books" claim and its list (currently totaling 20 with 3 deprecated-script entries and 2 missing real ones) are reconciled to the 19 real active scripts. *(Not otherwise covered in §2 above — add to the build-phase task list; scope §1.9's bonus finding, no dedicated §2 subsection since it's outside the file set §2 was asked to cover, but still a confirmed drift item.)*
13. `mental-model.md`'s "Test files" section is a categorized summary totaling 39 (not ~27), explicitly naming the 12 previously-missing files, with a live-verification pointer (`ls tests/test_*.py | wc -l`).
14. `.opencode/skills/instrument/SKILL.md:190`'s `PROVIDER_PRICING` comment lists all 9 real keys, including `anthropic-sonnet5` (real, not removed).
15. `conventions.md` and `instrument/SKILL.md` use the real `BUILTIN_STORIES` keys (`task_manager_api`, `static_site_gen`, `notification_service`), not the `*_story`-suffixed names, in every occurrence (2 in `SKILL.md`, 1 in `conventions.md`).
16. `run_story.ts`'s `CONDITIONS` includes `late_degrade` (4 entries); the 6 additional `run_story.py` flags (`--backend`, `--codebase`, `--worktree-root`, `--results-dir`, `--output-limit`, `--standardize`) are exposed (§3.2 chose "expose," not "document as reduced subset").
17. `opencode.json`'s `small_model` and all 3 agent `model:` fields use `deepseek/deepseek-v4-flash`, justified by real result-file evidence (D6's tightened bar), not a source grep.
18. `src/instrument/CONTEXT.md`'s module count reads 38 (not 33); its table includes all 16 previously-missing modules, each with its own row (this is the one place full descriptions of `supervisor.py`/`workflow_runner.py`/`test_runner.py` live, per D5).
19. **Guard, unchanged from scope:** the ledger's UNMEASURED fields (`confidence`, `perturbation_strength`, `test_executed_success`, the `answer`/`explanation` token split) are still marked unmeasured everywhere — this doc-refresh does not touch that status, and verify should confirm the build phase didn't accidentally "fix" it by conflating "compiler is written" with "instrumentation gap is closed."
20. `enqueue.ts` exposes `--model`/`--missing-only`; `pipeline.ts`'s plan description/`.describe()` mention `cross_models`; `batch.ts`'s description no longer says "all 13" (§3.2, 4 items).
21. The 9 new tools in §3.1 exist under `.opencode/tools/*.ts`, each matching its spec's args/flags; `compile_experiment.ts` and `control_room.ts` are clearly documented as convention-breaking (inline `python3 -c` and HTTP `fetch` respectively) rather than silently shipped as if they matched the other 23 tools' `Bun.$`-wraps-a-script shape; `supervisor.ts` and `control_room.ts` expose **no** steering/interrupt/control endpoint (§3.1's security-relevant constraint, checked explicitly, not just assumed from the tool description).
22. §3.3's 12-tool flag-parity audit backlog is either completed (with any found drift added to this checklist) or explicitly still open in the verify-phase report — not silently dropped (D7).

**Port design (§4) — this phase's actual deliverable; nothing here is "implemented," only specified:**

23. The mapping table (§4) preserves the plural `.opencode/agents/`, `.opencode/commands/`, `.opencode/skills/` naming on the opencode side — confirmed plural this phase (`ls .opencode/` → `agents/`, `commands/`, `skills/`, `instructions/`, `tools/`), matching scope §1.4/§3's correction to the task's own singular-form hint.
24. No `.claude/*` files or `CLAUDE.md` are generated as part of landing this spec — confirmed pre-condition this phase (`find .claude` / `ls CLAUDE.md` both empty) and D8's gating conditions (drift-fix landed + explicit go-ahead) are restated at the top of §4, not silently dropped.
25. Every mapping-table row that doesn't port cleanly is flagged inline with *why*, not just listed as a bare mapping: `.opencode/tools/*.ts` → MCP (D1, recommended against), `permission` (shape mismatch), `lsp`/`formatter` (no equivalent), `subagent_depth` (no equivalent), `instructions` field (mechanism mismatch, not missing field).
26. The two rows the task specifically asked to be checked (`references` → `permissions.additionalDirectories`, `compaction` → `/autocompact`) are marked **verified-against-docs**, backed by a live doc fetch performed this phase (`code.claude.com/docs/en/settings`, `/cli-reference`), not carried over unverified from the scope doc (which didn't cover either field, since this repo doesn't use `references` and scope's own §3 table predates this phase's fetch).

---

TESTS: 0 passed, 0 failed — this phase's deliverable is a design document (`docs/opencode_docs_spec.md`); no code was written and no test suite applies. The build phase that implements §2/§3 against real files is a separate, later phase (this repo's own multi-phase convention: scope → challenge → spec → build → verify), and that phase is where `pytest tests/` becomes the relevant gate.
