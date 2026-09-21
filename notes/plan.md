# Plan — close the live-KB test-emission leak (test-seam fix)

*Execute phase follows this file. Deviations go in `notes/deviations.md`; the posterior diffs
against `notes/world_model.md` and this plan.*

## 0. Decision (from the world model)

The leak is a **test-seam** defect, not a production defect. `tests/test_world_model_gates.py`'s
shared spec opts in `rag.emit_self: true` / `rag.emit_report: true`
(`tests/test_world_model_gates.py:42-44`), and `_finding_emit_enabled` deliberately lets an
explicit opt-in outrank the suite-wide `FINFOPS_EMIT_SELF=0` disarm
(`src/agentic_dynamics/runtime/workflow_runner.py:1836-1839`; pinned by
`tests/test_workflow_runner.py:1136-1153`). Four tests in the module therefore reach the real
`emit_phase_finding` write on every run.

**The fix is test-only:** add a module-local autouse guard that intercepts the emit write path,
plus one regression proving the closure. Do **not** change `_finding_emit_enabled`, the opt-in
precedence, or any production file. Do **not** change the shared `SPEC`'s `emit_self`/`emit_report`
values: `test_emit_report_opts_in_for_committed_phases` depends on the opt-in being true to reach
its own stubbed assertions (`tests/test_world_model_gates.py:116-136`).

## Files

| file | change |
|---|---|
| `tests/test_world_model_gates.py` | ADD a module-local `autouse` fixture (e.g. `_stub_emit_write_path`) that (1) monkeypatches `agentic_dynamics.knowledge.knowledge_ingestion.emit_phase_finding` to a recorder no-op, and (2) redirects `FINOPS_RESULTS_DIR` to a `tmp_path_factory` dir (containing `_emit_research_report`'s direct `path.write_text`). ADD one regression test proving no live-tree write escapes the module under the disarm. |
| `notes/deviations.md` | CREATE only if reality differs from this plan (the execute prompt requires it). |
| `notes/sources.jsonl` | Written by the prior phase (gate requirement); execute leaves it. |

Explicitly NOT touched: `src/agentic_dynamics/runtime/workflow_runner.py`,
`src/agentic_dynamics/knowledge/knowledge_ingestion.py`, `tests/conftest.py` (the suite-wide
disarm stays as-is), any other test module, and the shared `SPEC`/`PLAN_GATE_SPEC` constants.

### Fixture shape (why this seam)

The established seams both work; choose the *write seam* because it contains both leak channels
in one place and is transparent to the routing under test:

```python
@pytest.fixture(autouse=True)
def _stub_emit_write_path(monkeypatch, tmp_path_factory):
    """No test in this module may reach the live KB/report tree (2026-09-21 leak).

    SPEC/SHAPE_SPEC opt in with rag.emit_self/emit_report: true, which outranks the suite
    FINFOPS_EMIT_SELF=0 disarm (workflow_runner._finding_emit_enabled). Intercept the single
    durable write+publish entry (knowledge_ingestion.emit_phase_finding) and point the durable
    results tree at tmp, so neither the kb/*.json artifact/publish nor the
    workflows/<spec>/reports/*.md file can land in the checkout. Tests that exercise the real
    write path stub these themselves and override this fixture.
    """
    import agentic_dynamics.knowledge.knowledge_ingestion as ki
    results = tmp_path_factory.mktemp("live_kb_guard")
    monkeypatch.setenv("FINOPS_RESULTS_DIR", str(results))
    emitted = []
    monkeypatch.setattr(ki, "emit_phase_finding",
                        lambda pr, **kw: emitted.append((pr.phase, kw)))
    yield emitted
```

Notes:
- `_emit_self_finding` and `_emit_research_report` both import `emit_phase_finding` *inside* the
  function (`workflow_runner.py:1851, 1925`), so patching the module attribute is honored.
- `monkeypatch` sharing: `test_emit_report_opts_in_for_committed_phases` (`:127-132`) and
  `test_report_path_honors_the_results_dir_contract` (`:208`) already `setattr`/`setenv` on the
  same monkeypatch instance in the test body, so their values win at call time and teardown
  restores cleanly (LIFO undo).
- The fixture yields the recorder so the regression can request it by name.

## Tests

| test | file | proves |
|---|---|---|
| `test_no_emission_escapes_the_module_under_the_suite_disarm` (ADD) | `tests/test_world_model_gates.py` | With `FINFOPS_EMIT_SELF == "0"` asserted active and `SPEC` (opt-in) driven through the **real** `wr._emit_self_finding` / `wr._emit_research_report` routing, the module fixture intercepts the emission and **no file lands under the real** `PROJECT_ROOT/experiments/results/kb/` or `experiments/results/workflows/t_wml/`. |
| existing 11 tests | `tests/test_world_model_gates.py` | all still pass; the fixture is transparent to the gate/path contracts. |

### Regression shape (ADD)

```python
def test_no_emission_escapes_the_module_under_the_suite_disarm(
    tmp_path, monkeypatch, _stub_emit_write_path
):
    _init_repo(tmp_path)
    # The disarm is ACTIVE and the spec nevertheless opts in — the exact leak precondition.
    assert os.environ.get("FINOPS_EMIT_SELF") == "0"
    assert wr._finding_emit_enabled({"emit_self": True}, {}) is True

    kb_dir = PROJECT_ROOT / "experiments" / "results" / "kb"
    reports_dir = PROJECT_ROOT / "experiments" / "results" / "workflows" / "t_wml"
    before_kb = set(kb_dir.glob("*")) if kb_dir.is_dir() else set()
    before_reports = set(reports_dir.rglob("*")) if reports_dir.is_dir() else set()

    spec = load_spec(_write_spec(tmp_path))
    def fake(prompt, **kwargs):
        (tmp_path / "notes").mkdir(exist_ok=True)
        (tmp_path / "notes" / "plan.md").write_text("## Files\nx\n## Tests\ny\n## Acceptance\nz")
        return _R()
    wr.run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=fake)

    # (i) the emission fired and was intercepted (NOT silently skipped) ...
    assert any(phase == "prior" for phase, _kw in _stub_emit_write_path)
    # (ii) ... and nothing escaped to the live tree.
    assert (set(kb_dir.glob("*")) if kb_dir.is_dir() else set()) == before_kb
    assert (set(reports_dir.rglob("*")) if reports_dir.is_dir() else set()) == before_reports
```

Adjust the interception assertion to the actual fixture return shape chosen in execution; the
two contract points are: *the route fired and was seen by the stub*, and *the live dirs are
byte-identical before/after*.

## Acceptance

1. `python3 -m pytest tests/test_world_model_gates.py -q -p no:cacheprovider` → 12 passed
   (11 existing + 1 regression), 0 failed, in the loop worktree with the suite disarm active
   (`tests/conftest.py:15`).
2. With `FINOPS_RESULTS_DIR` **unset** and `experiments/results/kb/` absent, a full module run
   creates **no** `experiments/results/kb/` directory and no
   `experiments/results/workflows/t_wml/` directory. Verify by snapshotting before/after:
   `find experiments/results/kb experiments/results/workflows/t_wml -type f 2>/dev/null` is empty
   and unchanged (the fix's stated acceptance).
3. The regression fails if the guard is removed: temporarily deleting the fixture's
   `ki.emit_phase_finding` stub leaves the recorder empty → assertion (i) fails; deleting the
   `FINOPS_RESULTS_DIR` redirect lets a report file land under the live
   `workflows/t_wml/reports/` → assertion (ii) fails. (Run this check once during execution;
   do not leave the sabotage in the commit.)
4. `ruff check tests/test_world_model_gates.py` is clean.
5. No production file is modified. `git diff --stat` touches only
   `tests/test_world_model_gates.py` (+ `notes/deviations.md` only if a deviation occurred).

## Risks

- **Fixture/over-stub interference.** `test_report_path_honors_the_results_dir_contract` calls
  the real `wr._emit_research_report`. The write-seam fixture must NOT stub
  `wr._emit_research_report` (that would break this test); stub at
  `knowledge_ingestion.emit_phase_finding` instead. Verify the 11 existing tests individually.
- **Ordering of `monkeypatch` setters.** The fixture and the two tests that self-stub share one
  function-scoped `monkeypatch`. If an existing test starts failing after the guard is added,
  the guard is over-reaching: narrow it (e.g. stub `wr` functions only for the four leaking
  tests) rather than editing the tests.
- **Redirection could hide a real write from the acceptance check.** The regression must assert
  both the interception and the untouched live dirs; an unchanged live-dir assertion alone
  passes even without the stub (because the redirect contains the write). Keep both assertions.
- **Do not "fix" the production precedence.** `_finding_emit_enabled`'s explicit-opt-in-wins
  behaviour is intended and pinned by `tests/test_workflow_runner.py:1136-1153`. Changing it is
  out of scope and would break `test_finding_emit_explicit_true_outranks_env_disarm`.
- **Scope is not the fix.** `FINFOPS_CELL_ID` is set inside a loop run (this phase carries
  `FINFOPS_CELL_ID=world_model_loop:prior`), so leaked records would be scoped to the run cell,
  not `self-<tmpdir>`. Do not attempt to key the guard on a scope name; intercept the write.
- **Stale notes from the previous loop.** `notes/deviations.md` / `notes/posterior.md` /
  `notes/minted.md` in this worktree belong to the prior Item-4 run and are overwritten by the
  current phases. Do not treat their presence as this run's work.
- **KB read degradation.** `kb_read.py` fails in this worktree (no registry index, no
  `neo4j_vectors` module). This is expected; do not mistake it for an empty corpus, and do not
  add a KB fetch to satisfy a gap that does not need one.

## Out of scope (explicitly)

- Any production change to `_finding_emit_enabled`, the emit gate, `emit_phase_finding`, or the
  `FINOPS_EMIT_SELF`/`FINOPS_RESULTS_DIR` contracts.
- A repo-wide autouse guard in `tests/conftest.py`: it would break
  `tests/test_workflow_runner.py::test_finding_emit_default_run_writes_enriched_records`
  (`:1217-1254`), which intentionally exercises the real write path against a tmp tree. The guard
  is module-local by design.
- The previous loop run's Item-4 / stale-next-action work; unrelated and already landed.
