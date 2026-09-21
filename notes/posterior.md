# Posterior — close the live-KB test-emission leak

*Final phase of the world-model loop. Read-only with respect to production code. Every claim is
grounded in a file, a commit, or a command output. The diff is against `notes/world_model.md`
(the prior) and `notes/plan.md`; the deviations record is `notes/deviations.md`. This file
replaces the previous loop run's posterior (Item 4), as the world model's §Gaps 5 / the plan's
§Risks anticipated.*

## Verdict

The plan's central prediction held and the execute phase delivered it: **the leak is a test-seam
defect; the fix is test-only; the module now intercepts the emit write path and no live record
escapes under the suite disarm.** Verified independently in this posterior: `12 passed`,
`ruff check`/`ruff format --check` clean, and — with `FINFOPS_RESULTS_DIR` unset — a full module
run creates neither `experiments/results/kb/` nor `experiments/results/workflows/t_wml/`
(`ls` → "No such file or directory"; `find` → nothing). `git show --stat 78866649e` touches only
`tests/test_world_model_gates.py` (+ `notes/deviations.md`). No production file changed.

Three things the model did not carry are now visible: (1) its own line-precise citations were
invalidated by the very fixture insertion the plan authorized; (2) the suite-disarm helper it
cited is misnamed and, in fact, dead code; and (3) the **loop's own** declared emission — the
property the workflow exists to produce — is still unobserved and was not checked, a carry-over
the prior posterior had already flagged.

---

## 1. VIOLATIONS — where reality differed from the world model

### V1. The world model's line-precise citations were invalidated by the planned edit (+37 / +78)

`notes/world_model.md` navigates the test module by line number: the opt-in at `:42-44`, the four
leaking tests at `:80, :99, :161, :181`, the self-stubbing tests at `:127-132, :208`, `PLAN_GATE_SPEC`
at `:251`, the clone tests at `:338-375`. The execute phase inserted 3 imports and a 30-line
autouse fixture **above** `SPEC` (`tests/test_world_model_gates.py:13-54`), which is exactly the
edit the plan authorized (`notes/plan.md:26`). Every prior reference is therefore stale:

| prior reference (`notes/world_model.md`) | prior line | reality now (`tests/test_world_model_gates.py`) |
|---|---|---|
| `emit_self` / `emit_report` / `emit_scope` | 42 / 43 / 44 | 79 / 80 / 81 |
| `test_artifact_gate_refuses_without_the_declared_plan` | 80 | 117 |
| `test_artifact_gate_passes_when_the_prior_wrote_the_plan` | 99 | 136 |
| `test_shape_gate_refuses_an_unsectioned_plan` | 161 | 198 |
| `test_shape_gate_passes_when_the_plan_carries_its_sections` | 181 | 218 |
| `test_emit_report_opts_in_for_committed_phases` stubs | 127-132 | 164-169 |
| `test_report_path_honors_the_results_dir_contract` stub | 208 | 245 |
| `PLAN_GATE_SPEC` | 251 | 308-329 |
| clone tests | 338-375 | 416-453 |

The shift is +37 lines above the regression and +78 below it (the regression itself is inserted
at `:265-303`). Measured against the exact blobs:

```
$ sha256(prior blob e41eedc0b:tests/test_world_model_gates.py)  = 2ea5484dd5fd…   (13478 bytes)
$ sha256(execute blob 78866649e:tests/test_world_model_gates.py)= 339347f5bcfc…   (17662 bytes)
```

`2ea5484d…` is the hash the prior itself recorded (`notes/sources.jsonl:1`), confirming the drift
is caused by the execute edit, not a prior mis-read. This is the **second consecutive loop run**
bitten by the same class (the Item-4 posterior's V3 recorded an identical line-refresh failure);
it is structural, not incidental (see U4).

### V2. The cited suite-disarm helper is misnamed — and never called

`notes/world_model.md:20-21` names `_disarm_finding_emits` (`tests/conftest.py:251-264`) and says
it "exists but is **not** an autouse fixture." Reality is stronger and slightly different:

- the function is `_disarm_finding_emit`, **singular** (`tests/conftest.py:251`);
- it is **dead code**: the only occurrence of the name anywhere under `tests/` is its own `def`
  (searched with a Python `rglob` scan; the `grep` channel on this file was unreliable — see U5),
  so it is neither autouse nor called;
- the real, active disarm is the module-level `os.environ["FINFOPS_EMIT_SELF"] = "0"` at
  `tests/conftest.py:15`.

The mechanism the model attributes to the helper is real, but it is installed by line 15, not by
the helper. A next model acting on "wire the helper" would be editing a redundant function.

### V3. The loop's own declared emission is unobserved, and the model's "no deviation" verdict never scoped it

The execute deviations assert "**no plan deviation**" and verify the *test module* thoroughly. But
the world-model loop spec itself opts in (`workflows/repository/world_model_loop.yaml:28-31`:
`emit_self: true`, `emit_report: true`, `emit_scope: agentic-dynamics`), and this run's prior and
execute phases committed (`e41eedc0b`, `78866649e`). If emission were working, artifacts would
exist for `world_model_loop`. They do not:

```
$ ls experiments/results/kb                       -> No such file or directory
$ find experiments/results/workflows -maxdepth 1  -> contemplation_synthesis_rerun  (only)
```

The prior posterior for the previous run (`notes/posterior.md`, V5/C3 at its lines 109-127,
198-200) already named this — *"a silent emit is unverified emit"* — and instructed the phase to
verify its own artifact. The world model here neither carried that unknown forward nor checked it;
`notes/world_model.md` §Sources records **no** KB record read. Both emit paths swallow every
exception by construction (`workflow_runner.py:1854-1855` and `:1952-1953`), so a successful and a
failed emission are byte-for-byte indistinguishable from the outside. The deviations' "no
deviation" is true of the test-seam task and false as a statement about the loop's purpose.

### V4. The fixture's "tests override this fixture" path is asserted but never exercised

The fixture docstring and the plan's §Risks rely on "tests that exercise the real write path stub
these themselves and override this fixture" (`tests/test_world_model_gates.py:44-46`). In
reality, no test in the module exercises the *default* durable tree at all: the two contract tests
set their own `FINFOPS_RESULTS_DIR` (`:186`, `:243`), and every gate test only needs the guard to
hold. The claimed override interaction is untested — harmless today, but it is a coverage claim
the model treats as established.

---

## 2. UNKNOWNS DISCOVERED — what the next model must carry

1. **The loop cannot read its own history in a worktree.** `python3 scripts/kb_read.py --query …
   --scope agentic-dynamics` fails in ranked mode (`ModuleNotFoundError: No module named
   'agentic_dynamics.knowledge.neo4j_vectors'`) and `--contains` raises `FileNotFoundError` on the
   absent `experiments/results/registry_index.jsonl` (both reproduced). The prior recorded this as
   §Gaps 6 "not a code gap"; it is actually the **loop's sensory failure**: the loop's stated first
   step ("READ what is known") is blind in exactly the environment it runs in, which is why
   recurring lessons (line drift, emit observability) never propagate. The previous posterior's
   V4 showed ranked retrieval *worked* in its environment; the capability is environment-dependent
   and cannot be assumed.

2. **The loop's own emission remains unverified (carry V5/C3).** Second consecutive run with no
   `experiments/results/kb/` or `experiments/results/workflows/world_model_loop/` artifacts while
   the spec opts in. The next model must either (a) look for the artifact after its own phase and
   report its presence/absence, or (b) treat the loop's emit as broken until proven otherwise.
   `_emit_self_finding`/`_emit_research_report`'s `except Exception: pass`
   (`workflow_runner.py:1854-1855, 1952-1953`) makes silence ambiguous by design.

3. **The guard is coupled to a lazy-import detail.** The fixture patches
   `knowledge_ingestion.emit_phase_finding` (`tests/test_world_model_gates.py:48-53`) and it works
   only because both emitters import the name *inside* the function (`workflow_runner.py:1851`,
   `:1925`). A future refactor that hoists either import to module scope would silently stop the
   interception. The new regression would then fail on assertion (i) — this module is
   self-protecting — but no repo-wide test guards the lazy-import contract itself.

4. **Line drift is structural.** A plan whose file table says "ADD a fixture above `SPEC`"
   necessarily invalidates the prior's line-precise references; the remedy is a citation
   convention (symbol **and** line), not more careful reading. The prior should predict the shift
   and the posterior should record it (this posterior does), because the next model reads
   `notes/world_model.md` and will navigate by the stale numbers.

5. **Probe-channel caveat (environment).** On `tests/conftest.py`, the local `grep`/Python
   byte-matching channel returned *self-contradictory* results: in a single Python process,
   `lines[14]` printed `b'os.environ["FINFOPS_EMIT_SELF"] = "0"'` while
   `b'FINFOPS_EMIT_SELF' in lines[14]` was `False` and `b.count(...)` was `0`; the file's sha256
   matches both `HEAD` and the prior's recorded `0282bbe2…`. The Read tool shows the string at
   `:15` and `:264`. Every conftest claim above was therefore verified through the Read tool, not
   through the query channel. Do not treat one negative byte-match as proof a string is absent —
   corroborate with a second channel.

---

## 3. UPDATES — the concrete update set

### A. KB findings to emit (scope `agentic-dynamics`, existing producer path)

**A1 — the verification outcome (authority MEASURED [M]).** *"Live-KB test-emission leak CLOSED
test-only. `tests/test_world_model_gates.py`'s shared `SPEC` opts into
`rag.emit_self/emit_report: true` (`:79-81`), which `_finding_emit_enabled`
(`src/agentic_dynamics/runtime/workflow_runner.py:1836-1839`) returns **before** consulting the
process disarm, so four committing tests wrote real findings to the canonical KB every run. Fixed
by one module-local autouse fixture (`tests/test_world_model_gates.py:25-54`) stubbing
`knowledge_ingestion.emit_phase_finding` and redirecting `FINFOPS_RESULTS_DIR`, plus one regression
(`:265-303`) driving the REAL emit routing and asserting (i) interception and (ii) the live
`experiments/results/kb/` + `workflows/t_wml/` trees unchanged. 12 passed; no production file
changed (commit 78866649e)."* Cite commit `78866649e`.

**A2 — the rule the fix encodes (authority ADVISORY [H]).** *"An explicit `emit_self=True` in a
TEST spec defeats the suite-wide `FINFOPS_EMIT_SELF=0` disarm (`tests/conftest.py:15`) by design.
A test module whose shared spec opts in MUST install a module-local autouse guard at the write
seam; the guard cannot live in `tests/conftest.py` because it would also intercept
`tests/test_workflow_runner.py::test_finding_emit_default_run_writes_enriched_records`, which
intentionally exercises the real path against a tmp tree."* This is the reusable transfer.

**A3 — the loop's emission gap (authority ADVISORY [H]).** *"`world_model_loop.yaml` opts into
emission, but no `world_model_loop` kb/report artifacts exist after two runs, and both emit paths
swallow all exceptions (`workflow_runner.py:1854-1855, 1952-1953`). The loop's own output is
git-only; its emit is unverified."* Second run to carry this — do not let it recur silently.

### B. Conventions to record

- **C1 (citation discipline).** Cite symbols **and** line numbers. When a plan inserts code above
  referenced code, the prior predicts the shift and the posterior records it. (Recurring: prior
  loop V3, this run V1.)
- **C2 (test-seam guard).** Any test whose shared spec sets `rag.emit_self/emit_report: true` owns
  a module-local autouse guard that stubs `knowledge_ingestion.emit_phase_finding` and redirects
  `FINFOPS_RESULTS_DIR`. The suite-wide disarm cannot cover an explicit opt-in.
- **C3 (emit observability — reaffirm).** A silent emit is unverified emit. A phase (or loop) that
  opts in must assert its artifact exists; the posterior must verify it.
- **C4 (channel corroboration).** Verify environment-var/suite-disarm claims through at least two
  independent channels; a single negative byte-match is not evidence of absence (U5).

### C. Skills / knowledge to create or amend

- **`run-workflow` skill:** add the test-seam guard pattern (C2) and the lazy-import detail
  (`_emit_self_finding`/`_emit_research_report` import `emit_phase_finding` inside the function);
  note the scope split (`_emit_self_finding` → `cell_scope`, `_emit_research_report` → `emit_scope`)
  already flagged by the previous posterior's C.
- **`docs/designs/proposed/world_model_loop.md`:** require symbol+line citations (C1); require the
  prior to verify the loop's own artifact (C3/A3); record that KB read is degraded in run
  worktrees and that the loop must not treat that as a footnote.

### D. What should change in the next loop's prior phase

1. **Cite symbols, and predict line drift.** When the plan adds code above existing code, state the
   expected shift (here +37/+78) or use symbol anchors so the execute edit does not blind the next
   model.
2. **Check the loop's own artifact first.** Before writing, confirm whether `experiments/results/kb/`
   and `experiments/results/workflows/world_model_loop/reports/` contain this run's records; if
   absent, carry it as an open unknown (do not repeat the previous posterior's V5 without action).
3. **Treat KB-read failure as loop-blocking, not a footnote.** `kb_read.py` cannot run in this
   worktree; a prior that cannot read prior findings must say so as a first-class limitation.
4. **Do not rely on a single probe channel** for suite/env claims (U5); corroborate with the Read
   tool.

---

## 4. Probe log (what was read, and why)

| probe | why | result |
|---|---|---|
| `notes/world_model.md`, `plan.md`, `deviations.md` | the model, plan, and record under test | mechanism accurate; citations drift (V1); helper misnamed (V2); loop emit unchecked (V3) |
| `git show --stat 78866649e`, `e41eedc0b`; `git log --format=%P` | what execute actually did | test file + notes only; parent chain e41eedc0b→8e6a046d0 |
| `git diff e41eedc0b 78866649e -- tests/test_world_model_gates.py` | the exact change | +78 lines, no deletions |
| sha256 prior vs execute blob | confirm the drift is the edit's | `2ea5484d…` → `339347f5…` |
| `pytest tests/test_world_model_gates.py -q` (with and without `FINFOPS_RESULTS_DIR`) | acceptance 1/2 | 12 passed both; no live dirs created |
| `ruff check` / `ruff format --check` | acceptance 4 | clean / already formatted |
| `ls experiments/results/kb`; `find experiments/results/workflows` | did the loop emit? | absent; only `contemplation_synthesis_rerun` (V3) |
| `scripts/kb_read.py` (ranked and `--contains`) | the loop's read step | both fail (U1) |
| Python `rglob` scan for `_disarm_finding_emit` | is the cited helper used? | only its own `def` (V2) |
| Read tool on `tests/conftest.py:1-20, 245-274` and `tests/test_world_model_gates.py` | ground the fixture/line claims | `FINFOPS_EMIT_SELF` at `:15` and `:264`; citation table confirmed |
| `workflow_runner.py:1836-1839, 1851, 1854-1855, 1925, 1952-1953` | precedence + swallow-by-design | explicit opt-in wins; both emits swallow |
