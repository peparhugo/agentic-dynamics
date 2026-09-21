# World model — Close the live-KB test-emission leak

*Prior phase of the world-model loop. Read-only: no production or test code touched. Every claim
below is grounded in a file, a KB record, or a command output — never in memory.*

## Problem

`tests/test_world_model_gates.py` writes real knowledge-base records to the durable results tree
on every run, even though the suite is disarmed.

- Its fixture spec opts into emission: `rag.emit_self: true` and `rag.emit_report: true`
  (`tests/test_world_model_gates.py:42-44`).
- `_finding_emit_enabled` returns the **explicit** per-run value *before* it consults the
  process disarm (`src/agentic_dynamics/runtime/workflow_runner.py:1819-1839`; the decisive
  lines are `explicit = rag_params.get("emit_self")` → `return bool(explicit)`).
- The suite's disarm is only the env default `FINOPS_EMIT_SELF=0`
  (`tests/conftest.py:15`), so it is bypassed for every test that runs a workflow against the
  fixture spec without stubbing the emit seam.
- Four tests do exactly that (the two artifact-gate and the two shape-gate tests); the other
  nine are either already stubbed, use a spec with `emit_self: false`, or do not commit.

Measured first-hand (`python3 -m pytest tests/test_world_model_gates.py -q`, 13 passed):

- with no results redirect: **10 artifacts under `experiments/results/kb/` + 6 report files
  under `experiments/results/workflows/t_wml/reports/`** were created in the checkout;
- with `FINFOPS_RESULTS_DIR` redirected to a tmp tree: the same 10 + 6 landed in the redirect
  and the checkout stayed clean (0 new files).

The root cause is a **precedence rule, not a stray write**: the explicit opt-in is intentional
and documented ("the flag still works when set (outranks the env disarm)"), so the defect is the
**test seam** — this module's tests do not stub the write path their own spec authorizes.

Task: stub the emit write path in this module's tests and add a regression proving no emission
escapes this module while the suite disarm is active.

## What Exists

The emit chain, exactly as written today:

- `_finding_emit_enabled(rag_params, phase_def)` — `workflow_runner.py:1819-1839`. Marker
  `no_emit` first, then explicit `rag_params["emit_self"]`, then env. The explicit value wins.
- The emit block — `workflow_runner.py:5448-5463`. A committed phase calls
  `_emit_self_finding`; a run with `rag.emit_report: true` additionally calls
  `_emit_research_report`; a report-only phase (no commit) calls `_emit_research_report`.
- `_emit_self_finding` — `workflow_runner.py:1842-1855`. Imports `emit_phase_finding`
  **in-function** and swallows every exception.
- `_emit_research_report` — `workflow_runner.py:1914-1957`. Writes the report file **directly**
  (`path.write_text`, `:1946`) to `<results>/workflows/<spec>/reports/<stamp>_<phase>.md`,
  *then* calls `emit_phase_finding`. A stub of only `emit_phase_finding` therefore does NOT stop
  the report-file write.
- `emit_phase_finding` — `src/agentic_dynamics/knowledge/knowledge_ingestion.py:625-668`.
  Derives the record, writes `<results>/kb/<knowledge_id>.json` (`:661-663`), then publishes.
- `_artifact_path` — `knowledge_ingestion.py:421-433`. Honors `FINOPS_RESULTS_DIR` when set,
  else `PROJECT_ROOT/ARTIFACT_DIR`.

Existing test coverage of the seam (so the new guard must not break it):

- `test_emit_report_opts_in_for_committed_phases` (`tests/test_world_model_gates.py:116`)
  monkeypatches both `wr._emit_self_finding` and `wr._emit_research_report`.
- `test_report_path_honors_the_results_dir_contract` (`:200`) stubs `ki.emit_phase_finding`,
  sets `FINOPS_RESULTS_DIR` to a tmp path, and calls the **real** `_emit_research_report`.
- `test_report_stamp_is_unique_within_a_second` (`:451`) stubs `ki.emit_phase_finding` and sets
  its own results dir.
- `_disarm_finding_emit` (`tests/conftest.py:251`) exists but is **dead code** — it is never
  referenced; the active disarm is the module-level assignment at `conftest.py:15`.

Prior art — a previous world-model loop ran this exact task (2026-09-21 18:14–18:29) and
implemented a test-only fix in its run worktree (reported as commit `78866649e`). **It is not in
this checkout:** `git log --all` contains no such commit, no ref contains it, and the fixture
name `_stub_emit_write_path` is absent from `tests/`. The prior POSTERIOR and the adversarial
review still hold as evidence of approach and pitfalls: the harness intermittently strips
`FINFOPS_RESULTS_DIR` from shell prefixes (set it with `monkeypatch.setenv` instead), the report
write needs its own redirect, and a regression must prove the gate **opened** (positive control)
or it is vacuous.

The live spec `workflows/repository/world_model_loop.yaml:28-31` also opts in
(`emit_self: true`, `emit_report: true`, `emit_scope: agentic-dynamics`) — intentional for real
runs; the fix must not change production precedence.

## Gaps

- **No module-local guard.** Nothing in `tests/test_world_model_gates.py` prevents a test from
  reaching the real emit write path; the suite disarm is only a default the spec outranks.
- **No regression.** No test asserts the module leaves the live results tree untouched.
- **Stub seam subtlety.** Stubbing only `emit_phase_finding` misses `_emit_research_report`'s
  direct report-file `write_text`; both the stub AND a results-dir redirect are required.
- **Blind KB in this checkout.** `scripts/kb_read.py` fails here — `registry_index.jsonl` is
  absent from `/repo/experiments/results/` and `agentic_dynamics.knowledge.neo4j_vectors` is
  missing. Prior knowledge was recovered from the durable container tree
  (`/app/experiments/results/kb/*.json`) and its report files instead.
- **Harness quirk.** `FINFOPS_RESULTS_DIR=… python3 …` on the command line was honored once and
  silently ignored on later invocations (identical command shape) — so acceptance verification
  must not rely on the shell prefix; the test must set the env in-process.
- **Dead disarm helper.** `_disarm_finding_emit` (`conftest.py:251`) is unused; a future editor
  could "fix" it and believe the suite is guarded.
- **No production change is warranted.** Explicit opt-in winning is intentional and pinned by
  the function docstring; the leak is a test-seam defect, and production specs
  (`world_model_loop.yaml`) legitimately emit.

## Sources

KB records (canonical tree `/app/experiments/results/kb/<id>.json`), the prior loop on this task:

- `kb:598c8a8fb9397063f06d74a07c47d46fd424bab115cf686098439fc64f7aa361` (prior, `agentic-dynamics`)
- `kb:34e86fa2d2402e6b8d2628d61cb00b60043f46292cced4298a991354bb629136` (execute, `agentic-dynamics`)
- `kb:2bacadba099bfe2aa175b788e3704363ea478892157ffd327d994c7ed4ebad49` (posterior, `agentic-dynamics`)
- `kb:016b5d9431f0be944e9231e9abdfaf2be07bce6a6fcddf396546caaae7144135` (p2_mint, `agentic-dynamics`)
- `kb:dddefbfe7f5b9d322ff72c743c9812751101778e300a42ff74c9917ebe2ad1bf` (g_adversarial, `agentic-dynamics`)

Files (+sha256):

- `tests/test_world_model_gates.py` (fb2eee5f9a7e0b61c89955d85ddc97a54c5942897f3e466f0ad2bb72f2489377)
- `src/agentic_dynamics/runtime/workflow_runner.py` (19563a67d0e546a5ad9730df9d25159a6efb89635381378eb48c0f7fa2ec922d)
- `src/agentic_dynamics/knowledge/knowledge_ingestion.py` (d7f776d481d2bf50731520f625044c430cb9431769155f676d0cf75f0c1f1668)
- `tests/conftest.py` (0282bbe2b1c3ce3f5dea7604ea8fdbce83e0f49523625a90319ad08cb690e41e)
- `workflows/repository/world_model_loop.yaml` (c49a4dd5119ea47cec665715d94a7aa15b99832c8e480c76715e7d3cce0b3f4a)
- `/app/experiments/results/workflows/world_model_loop/reports/20260921181437_prior.md` (300604d15614c149838f475614ab991cc97654f93136a418cabae71cbd6f8da9)
- `/app/experiments/results/workflows/world_model_loop/reports/20260921181703_execute.md` (b56ac2bd0b48bbcd22590d31aa75c05b164f4b55d1a531e1efdc6bb261b3c385)
- `/app/experiments/results/workflows/world_model_loop/reports/20260921182021_posterior.md` (3c33572582db51a03ff094dd36ba56d6b82ef0c22554f22e75638d49bdfd9e89)
- `/app/experiments/results/workflows/world_model_loop/reports/20260921182307_p2_mint.md` (d056e5c61c9f10b8ba918ba01849ad3e22ef4b18031e0ab8e5f2532e3e8f7b16)
- `/app/experiments/results/workflows/world_model_loop/reports/20260921182924_g_adversarial.md` (c1a8ea4eec600851f26eda1c5ec8fe458425991769a086c69818b45127980162)

No external URL was fetched (no fact required it).
