# Plan — Close the live-KB test-emission leak

*Execute phase follows this file. Deviations go in `notes/deviations.md`; the posterior diffs
against `notes/world_model.md` and this plan.*

## Decision (from the world model)

The leak is a **test-seam** defect, not a production bug. `_finding_emit_enabled`
(`workflow_runner.py:1819-1839`) intentionally lets the spec's explicit `rag.emit_self: true`
outrank the suite disarm `FINOPS_EMIT_SELF=0` (`tests/conftest.py:15`). The fixture spec in
`tests/test_world_model_gates.py:42-44` therefore causes four tests to write real findings and
reports into the durable tree on every run (measured: 10 `kb/*.json` + 6 report files).

Fix scope: **`tests/test_world_model_gates.py` only.** Do not change production precedence; do
not touch `workflows/repository/world_model_loop.yaml`; do not "repair" the dead
`_disarm_finding_emit` helper. The guard belongs to this module, not the suite.

The prior loop's fix (reported commit `78866649e`) is **not present in this checkout** — verify
with `grep -n _stub_emit_write_path tests/test_world_model_gates.py` before editing; if it is
somehow present, reconcile rather than duplicate.

## Files

- `tests/test_world_model_gates.py` — the only file changed.
  - Add `import os` and `import pytest` to the import block.
  - Add a **module-local autouse fixture** `_stub_emit_write_path`.
  - Add one **regression test** `test_no_emission_escapes_the_module_under_the_suite_disarm`.

No other file. `git diff --stat` must show a single path.

### Fixture design

```python
@pytest.fixture(autouse=True)
def _stub_emit_write_path(tmp_path_factory, monkeypatch):
    """No test in this module may reach the real GB/emit write path.

    The module's fixture spec opts in with rag.emit_self/emit_report: true, which
    _finding_emit_enabled returns BEFORE the suite-wide FINFOPS_EMIT_SELF=0 disarm. Two layers:
    (1) stub knowledge_ingestion.emit_phase_finding — the one durable write+publish entry both
    emit paths import at call time; (2) point FINFOPS_RESULTS_DIR at a tmp tree so
    _emit_research_report's DIRECT report-file write_text also lands there. The recording list
    lets the regression prove the gate actually opened (non-vacuous) and was intercepted.
    """
    from agentic_dynamics.knowledge import knowledge_ingestion as ki
    emitted = []
    monkeypatch.setattr(
        ki, "emit_phase_finding", lambda pr, **kw: emitted.append((pr.phase, kw))
    )
    monkeypatch.setenv("FINOPS_RESULTS_DIR", str(tmp_path_factory.mktemp("results")))
    return emitted
```

Constraints this fixture must respect:

- Patch the **`ki` module attribute**, not a `wr` name — both emit paths do
  `from agentic_dynamics.knowledge.knowledge_ingestion import emit_phase_finding` inside their
  function bodies, so the call-time attribute lookup is intercepted.
- `_emit_research_report` writes its report file directly (`workflow_runner.py:1946`) before the
  `emit_phase_finding` call, so the results-dir redirect is mandatory; the stub alone is not
  enough.
- The three emit-aware existing tests set their own env/stub **after** this autouse fixture, so
  they still exercise the real `_emit_research_report` path:
  `test_report_path_honors_the_results_dir_contract` (:200) and
  `test_report_stamp_is_unique_within_a_second` (:451) override `ki.emit_phase_finding` and set
  `FINOPS_RESULTS_DIR`; `test_emit_report_opts_in_for_committed_phases` (:116) patches the `wr`
  functions. Run all three explicitly to confirm.

### Regression design

`test_no_emission_escapes_the_module_under_the_suite_disarm(tmp_path, monkeypatch, _stub_emit_write_path)`:

1. `_init_repo(tmp_path)`; `spec = load_spec(_write_spec(tmp_path))`.
2. Positive control: assert `os.environ.get("FINOPS_EMIT_SELF") == "0"` (suite disarm active),
   and `wr._finding_emit_enabled(wr._resolve_rag_params(spec, None, wd=tmp_path,
   rag_augment=False), {}) is True` (the spec's explicit opt-in opens the gate).
3. Snapshot the live tree: the path SET (not a count) under
   `<repo>/experiments/results/kb/` and `<repo>/experiments/results/workflows/t_wml/`.
4. Run `wr.run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=fake)` where
   `fake` writes `notes/plan.md` + a work file and returns an ok result (the shape that
   commits and therefore emits).
5. Assert the guard recorded at least one emit — proves the runner actually reached the seam
   and the guard intercepted it (fails if the stub is removed).
6. Assert the live snapshots are unchanged — proves no file escaped (fails if the redirect is
   removed).

Falsifiers (sabotage, performed on throwaway copies and then reverted):
removing the stub fails step 5; removing the redirect leaks a report file and fails step 6.

## Tests

- Run the module: `python3 -m pytest tests/test_world_model_gates.py -q` → **14 passed**
  (13 existing + the regression).
- Run the three emit-aware tests explicitly to prove no fixture conflict:
  `python3 -m pytest tests/test_world_model_gates.py -q -k "emit_report_opts_in or
  report_path_honors or report_stamp_is_unique"`.
- Guard against cross-module regressions from the new autouse fixture (it is module-local, so
  the knowledge-ingestion suite must be unaffected):
  `python3 -m pytest tests/test_knowledge_ingestion.py -q`.
- Lint: `ruff check tests/test_world_model_gates.py`.

## Acceptance

- `pytest tests/test_world_model_gates.py -q` all pass (13 + 1).
- Running the module with `FINFOPS_RESULTS_DIR` **unset** creates no new files under the
  checkout's `experiments/results/kb/` and no `experiments/results/workflows/t_wml/` — verified
  by a before/after path-set listing. Because the harness intermittently strips the shell env
  prefix, the in-test `monkeypatch.setenv` guard is the guarantee; the acceptance command should
  demonstrate the live tree is untouched without depending on the shell redirect.
- The regression asserts both interception and live-tree invariance (not a count).
- `ruff check tests/test_world_model_gates.py` clean.
- `git diff --stat` touches only `tests/test_world_model_gates.py`.
- Production precedence unchanged: no edit to `workflow_runner.py` or
  `knowledge_ingestion.py`; a re-read confirms `_finding_emit_enabled` still returns the explicit
  opt-in before the env disarm (the behavior stays pinned, now by a module-local guard).

## Risks

- **Shell env stripping.** `FINFOPS_RESULTS_DIR=… python3 …` was honored once and silently
  ignored on later identical invocations. Any verification that redirects via the shell can
  silently test the wrong tree; set env in-process (`monkeypatch.setenv`) and assert on the
  guard, not on the shell.
- **Wrong seam.** Patching `wr.emit_phase_finding` (does not exist) or only `_emit_self_finding`
  leaves `_emit_research_report`'s direct file write live. Patch `ki.emit_phase_finding` and
  redirect the results dir.
- **Fixture override order.** The autouse fixture runs before the test body; the three
  emit-aware tests override after it. If any of them unexpectedly stops exercising the real
  `_emit_research_report`, the assertion in that test (path honors the results dir) will fail —
  run them explicitly.
- **Nondeterministic report filenames.** Same-second collisions make report counts unstable
  (prior observed 8/4, 6/2 alternating). Snapshot path SETS, never counts.
- **Do not delete `FINOPS_EMIT_SELF`.** A test that calls `monkeypatch.delenv("FINOPS_EMIT_SELF")`
  would re-open the gate; no test in this module should.
- **Scope creep.** Production specs legitimately emit (including `world_model_loop.yaml`);
  changing precedence would break the loop. The fix is the module's test seam only.
- **Prior fix absent.** `78866649e` is not in this checkout; confirm by grep before editing so
  the work is not duplicated or mis-assumed present.
