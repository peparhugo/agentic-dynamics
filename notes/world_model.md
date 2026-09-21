# World model — close the live-KB test-emission leak

*Prior phase of the world-model loop. Read-only: no production code or test code touched. Every
claim below is grounded in a file, a command output, or an explicit "not available in this
worktree" note. (This file replaces the previous loop run's Item-4 model, which is preserved in
git history / `notes/ci-preflight/`.)*

## Problem

`tests/test_world_model_gates.py` writes real knowledge-base records and run reports into the
live durable tree on every run. The cause is a precedence rule, not a stray write:

- The module's shared fixture spec opts in explicitly: `rag.emit_self: true`
  (`tests/test_world_model_gates.py:42`) and `rag.emit_report: true` (`:43`), scoped
  `emit_scope: agentic-dynamics` (`:44`).
- `_finding_emit_enabled` returns the **explicit** value *before* consulting the process
  disarm, so `True` wins over the suite's `FINFOPS_EMIT_SELF=0`
  (`src/agentic_dynamics/runtime/workflow_runner.py:1836-1839`).
- The suite-level disarm is real but powerless against an explicit opt-in: `tests/conftest.py:15`
  sets `FINFOPS_EMIT_SELF=0` at import; the helper `_disarm_finding_emits`
  (`tests/conftest.py:251-264`) exists but is **not** an autouse fixture.
- When the gate fires (`workflow_runner.py:5441-5456`), a committed phase runs
  `_emit_self_finding` (`:1842-1855`) → `emit_phase_finding`
  (`src/agentic_dynamics/knowledge/knowledge_ingestion.py:625-668`), which writes a durable
  per-record artifact under `experiments/results/kb/<knowledge_id>.json` (`:660-663`) and
  publishes a pointer onto the DB-2 stream. A phase with a report emits
  `_emit_research_report` (`workflow_runner.py:1914-1953`) too, which additionally writes
  `experiments/results/workflows/<spec>/reports/<stamp>_<phase>.md` (`:1937-1942`).

Which tests leak: the **four** tests that run a committing `agent` phase with `SPEC` / `SHAPE_SPEC`
and never stub the emit seam — `test_artifact_gate_refuses_without_the_declared_plan` (`:80`),
`test_artifact_gate_passes_when_the_prior_wrote_the_plan` (`:99`),
`test_shape_gate_refuses_an_unsectioned_plan` (`:161`),
`test_shape_gate_passes_when_the_plan_carries_its_sections` (`:181`). `SHAPE_SPEC` derives from
`SPEC` (`:153-158`), so it inherits the opt-in. The other tests are already safe:
`test_emit_report_opts_in_for_committed_phases` stubs both `workflow_runner` emit functions
(`:127-132`), `test_report_path_honors_the_results_dir_contract` stubs `ki.emit_phase_finding`
(`:208`), `PLAN_GATE_SPEC` sets `emit_self/emit_report: false` (`:251`), and the two clone tests
run `commit=False` with an executor that produces no phase commit (`:338-375`).

Measured, not assumed (this is the falsifiable core of the model):

```
FINOPS_RESULTS_DIR=/tmp/opencode/wml_probe4 python3 -m pytest \
  tests/test_world_model_gates.py::test_artifact_gate_refuses_without_the_declared_plan \
  tests/test_world_model_gates.py::test_artifact_gate_passes_when_the_prior_wrote_the_plan \
  tests/test_world_model_gates.py::test_shape_gate_refuses_an_unsectioned_plan \
  tests/test_world_model_gates.py::test_shape_gate_passes_when_the_plan_carries_its_sections -q
# => 4 passed; 8 files under /tmp/opencode/wml_probe4/kb/*.json
#    and 4 files under /tmp/opencode/wml_probe4/workflows/t_wml/reports/
```

With the durable `FINOPS_RESULTS_DIR` redirected, the same bytes land under the *real*
`experiments/results/kb/`. The task's observed "4 `self-test_artifact_gate_*` records"
(2026-09-21) is that write, with `cell_scope` = `self-<tmpdir>` because `FINFOPS_CELL_ID` was
unset in the observing environment.

## What Exists

The machinery that causes and can contain the leak already exists; no new mechanism is needed.

| need | primitive | state |
|---|---|---|
| the emit gate + opt-out ladder | `_finding_emit_enabled` (`workflow_runner.py:1819-1839`), `FINDING_EMIT_ENV = "FINFOPS_EMIT_SELF"` (`:3689`), `NO_EMIT_MARKER` (`:3682`) | exists; explicit opt-in outranks env, by design and by test |
| the suite disarm | `tests/conftest.py:15` (`FINFOPS_EMIT_SELF=0`) + the unwired helper `_disarm_finding_emits` (`:251`) | exists; not autouse |
| the write seam | `knowledge_ingestion.emit_phase_finding` (`knowledge_ingestion.py:625`) — the single durable-write + publish entry | exists |
| the durable path contract | `_artifact_path` honors `FINOPS_RESULTS_DIR` (`knowledge_ingestion.py:421-433`); `_emit_research_report` honors it (`workflow_runner.py:1933-1937`); pinned by tests at `test_world_model_gates.py:145-150, 200-225` | exists |
| the established test seam for exactly this leak | stub `workflow_runner._emit_self_finding` / `_emit_research_report` (`tests/test_workflow_runner.py:1095, 1122, 1144, 1164, 1203, 3213`); or point the durable seam at tmp and capture `emit_phase_finding` (`:1217-1254`, patches `ki.PROJECT_ROOT`, stubs `ks.connect`/`ks.publish_event`) | exists |
| the spec that opts in | `workflows/repository/world_model_loop.yaml:28-31`; the execute gate requires `notes/sources.jsonl` (`:69-71`) | exists |
| the design rationale | durable emission v1.1 honors `FINOPS_RESULTS_DIR` so ephemeral-worktree runs do not strand records (`docs/designs/proposed/world_model_loop.md:83-89`) | documented |

## Gaps

1. **No module-level guard.** The disarm is suite-wide and opt-in-proof, but this module's own
   spec opts in, so nothing in the module stops the write. *Reduce:* a module-local autouse
   fixture that (a) stubs the write seam `knowledge_ingestion.emit_phase_finding` and (b)
   redirects `FINOPS_RESULTS_DIR` to a per-test tmp dir (containing the report file write).
2. **No regression pins the closure.** No test asserts that this module's specs produce zero
   live-tree writes. *Reduce:* a dynamic regression that drives `SPEC` through `run_workflow`
   with the **real** `_emit_self_finding`/`_emit_research_report` routing while the module
   fixture intercepts the write seam; assert (i) the emission actually fired (intercepted, not
   silently skipped), and (ii) the real `experiments/results/kb/` and
   `experiments/results/workflows/t_wml/` are unchanged.
3. **Scope is environment-dependent.** `cell_scope` returns `FINFOPS_CELL_ID` when set
   (`workflow_runner.py` cell-scope override), so inside a loop run (this phase has
   `FINFOPS_CELL_ID=world_model_loop:prior`) the leaked records are scoped to the run's cell, not
   `self-<tmpdir>`. The fix must therefore be scope-independent: intercept at the write seam, not
   by chasing a scope name.
4. **The production rule must not change.** "Explicit `emit_self=True` outranks the env disarm"
   is intentional and pinned (`tests/test_workflow_runner.py:1136-1153`). The leak is a *test
   seam* defect; the fix is test-only. Changing `_finding_emit_enabled` would be a scope
   violation.
5. **Stale prior-run notes.** `notes/deviations.md`, `notes/posterior.md`, `notes/minted.md` are
   the previous loop's artifacts in this merged worktree; the current run's execute/posterior/mint
   phases overwrite them before any later phase reads them. Not a code gap; recorded so the
   posterior does not mis-attribute stale prose to this run.
6. **No external gap and no KB record available.** `experiments/results/registry_index.jsonl` is
   absent in this worktree and `python3 scripts/kb_read.py --query ... --scope agentic-dynamics`
   fails (`ranked retrieval unavailable: no module agentic_dynamics.knowledge.neo4j_vectors`) and
   then `FileNotFoundError` in `_contains`. No external fact is needed, so no URL is fetched; the
   sources file therefore carries file-provenance only. This degradation is expected in a run
   worktree (recorded in the previous loop's plan §5), not evidence of an empty corpus.

## Sources

KB record ids actually used: **none** — the registry index is absent in this worktree and
`kb_read.py` cannot run (ranked retrieval unavailable; `--contains` raises `FileNotFoundError`).
No external fact was needed, so **no URL was fetched**.

Files actually used (sha256 of the exact revision read; `notes/sources.jsonl` mirrors this list):

- `tests/test_world_model_gates.py`
  `2ea5484dd5fd3d841f507eedbb6ecd9b75291e522dbcc86862f08aec45d8a720`
- `src/agentic_dynamics/runtime/workflow_runner.py`
  `1bae62682aa2cadedfb9f07d2084abaaad8612ed8fb1f98f9a88ee1ed9dd849c`
- `src/agentic_dynamics/knowledge/knowledge_ingestion.py`
  `d7f776d481d2bf50731520f625044c430cb9431769155f676d0cf75f0c1f1668`
- `tests/conftest.py`
  `0282bbe2b1c3ce3f5dea7604ea8fdbce83e0f49523625a90319ad08cb690e41e`
- `tests/test_workflow_runner.py`
  `96ec8e0bcf76721a42f92cb9501a1ab9575c7198e700a2c952887c01b015db59`
- `workflows/repository/world_model_loop.yaml`
  `8cf6f518bd350e62284963af6ac1032ca1206d301b7c930ae6ac34213c61b4f9`
- `docs/designs/proposed/world_model_loop.md`
  `f4f13dd8fd64e041e9085886c1de74087363c795e7f35d3a9276589b3d84b3a6`
- `src/agentic_dynamics/core/paths.py`
  `6d4b7cc042d9774fbe85cb0968e25d5b96cdc1bf4af8a417cd91ff5448a70e95`
