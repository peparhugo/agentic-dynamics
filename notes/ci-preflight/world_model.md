# World model — local CI preflight (`validate preflight`)

**Loop:** PRIOR phase of `workflows/repository/world_model_loop.yaml` (prior → execute → posterior).
**Task:** ONE local command that runs the same gates GitHub Actions runs on every push, so a push
fails locally instead of after minutes of CI. Gates: (1) `ruff check .`, (2) generated-instruction
surfaces check, (3) docs-drift spec-lifecycle check, (4) fast-path suite, (5) full deterministic
suite (external excluded). Print a per-gate PASS/FAIL summary; exit non-zero if any gate fails.
**Branch:** `feature/ci-preflight` @ `3bc05dd2f` (main @ `11bae5110`).
**Evidence discipline:** every claim below cites a file, a KB record, or a command output.
**Date:** 2026-09-21.

---

## 1. The task, restated as an observable contract

The deliverable is a *runner*, not a new test: invoked once, it executes five pre-existing
commands in a fixed order, streams/records each exit code, prints one PASS/FAIL line per gate,
and returns a non-zero process exit if any gate is non-zero. It must not re-implement a gate
(call the same scripts CI calls), and it must not duplicate the Redis-driven `pipeline ci` plan.

## 2. What exists today (grounded)

### 2.1 The CI surface — `.github/workflows/pytest.yml`

The workflow is the parity target. The five named concerns live in four jobs:

| Gate | Exact CI command | Anchor |
|---|---|---|
| Lint | `ruff check .` (CI pins `ruff==0.16.2`) | `.github/workflows/pytest.yml:38-44` |
| Generated surfaces | `python3 scripts/_gen_instructions.py --check` | `.github/workflows/pytest.yml:66-69` |
| Docs drift (spec lifecycle) | `python3 scripts/scan_docs_drift.py --check spec_lifecycle --fail-on-drift` | `.github/workflows/pytest.yml:71-81` |
| Fast path | `bash scripts/test_fast.sh` | `.github/workflows/pytest.yml:106-118` |
| Full deterministic suite | `pytest tests/ -m "not external" -n auto --dist loadfile -v --timeout=600 --splits 2 --group <n>` | `.github/workflows/pytest.yml:173-181` |

- `scripts/test_fast.sh` is a 3-line wrapper: `python3 -m pytest tests/ -m fast -q -p no:cacheprovider`
  with a `cd "$(dirname "$0")/.."`. Its budget (180s) is pinned by
  `tests/test_fast_path_gate.py:26` (`FAST_BUDGET_SECONDS`).
- Per-test hang timeout `600` is also the repo default (`pyproject.toml:99`).
- The full-suite job additionally runs `Configure git identity` and `Restore the corpus fixture`
  (`cp -r tests/fixtures/corpus/* experiments/results/`) — CI-shape steps, not gates.
- **The CI surface is larger than the five gates** and the extra jobs are explicitly NOT part of
  this preflight: `verify` (build_data import/dry-run, parquet parity, import gate),
  `workflow-parity` (`tests/test_workflow_executor_parity.py`), `repro` (docker build + container
  smoke), `packaging` (wheel honesty). Naming this boundary matters: "CI parity" here means the
  five named gates, not the whole workflow.

### 2.2 The command surface — CLI dispatcher and its guards

- `src/agentic_dynamics/cli.py` is a thin dispatcher: `_COMMANDS: dict[tuple[str,...], str]`
  maps argv prefixes → `scripts/*.py` (`cli.py:19`), resolved longest-prefix-first
  (`cli.py:272`) and documented in `_HELP` (`cli.py:227-...`). The `validate` group currently
  reads `session|tests|prereq|preexisting|render` (`cli.py:232` region, help text).
- `tests/test_cli_resolution.py` hand-authors `DOCUMENTED_RESOLUTIONS` from `_HELP` +
  `mental-model.md` (`test_cli_resolution.py:28`, `:155`, `:259`) and fails in **both directions**
  if the table and the help text disagree. **Adding a CLI command requires updating this table.**
- `tests/test_agent_config_semantic.py::test_cli_commands_exist` extracts valid prefixes from
  `cli._COMMANDS` (`:143-149`) and regex-scans every `agent_config/**.md` for
  `agentic-dynamics <verb> <noun>` (`_CLI = r"agentic-dynamics\s+([a-z][a-z-]*)\s+([a-z][a-z-]*)"`,
  `:111`). **Note the `\s+` crosses newlines** — a latent fragility, see §4.
- `scripts/CONTEXT.md` is the machine-parsed classification manifest
  (`tests/test_script_classification.py:36`): every `scripts/*.py` is in exactly one bucket, and
  every `maintained` script must be CLI-reachable (`:66-76`). New maintained scripts are appended
  on their own `maintained: <name>` line (pattern at `scripts/CONTEXT.md:25-32`).

### 2.3 The existing `pipeline ci` plan — why this is not a duplicate

`experiments/definitions/configs/plans.yaml:2-23` defines `ci` as a **Redis-driven phase DAG**:
`lint` (kind: lint) → `typecheck` (`mypy src/`) → `test` (kind: test) → `build`
(`python3 scripts/build_data.py`). It is a different mechanism (queue phases, `pipeline.py`
executor), a different gate set (adds mypy + build_data; omits surfaces/docs-drift/fast-path),
and no per-gate PASS/FAIL process summary. The preflight is a **local, synchronous,
subprocess-only parity runner** and must stay disjoint from it.

### 2.4 The design of record names this exact deliverable

`docs/designs/proposed/world_model_loop.md` §"What already exists" lists
`local CI parity | pipeline plans (ci), the workflow's gates | partial — no one-command
preflight`, and §"Smallest next steps" specifies: *"Local CI preflight: one command running the
workflow's gates locally (ruff → generator check → docs drift → fast path → full suite) so a push
fails locally, not after minutes of waiting. (`act` is not installed; the parity set is the
cheap version.)"* The task's five gates match this list one-for-one. Prior KB finding:
`e6222c1ca0de8ead | finding | design:world-model-loop` (retrieved with
`python3 scripts/kb_read.py --query "CI preflight local gates parity workflow" --scope agentic-dynamics`).

### 2.5 Existing test-runner conventions to mirror

- Scripts that expose logic for a hermetic test do so by being importable:
  `tests/test_docs_proposal_gate.py:30-33` does `sys.path.insert(0, ROOT/"scripts")` then
  `import docs_proposal_gate as gate`; `tests/test_command_journal_scripts.py` imports a helper.
- `tests/test_fast_path_gate.py` forbids `subprocess`, `redis`, `worktree`, `time.sleep`, etc. in
  any `fast`-marked module (`FORBIDDEN_IN_FAST`). **A test that imports `subprocess` therefore
  must not be `fast`-marked** (or must carry a `# fast-safe` declaration).

## 3. What is believed about the problem (hypotheses)

- **H1.** The five gates are sufficient to reproduce the *blocking* part of CI on a developer
  box; the remaining jobs require docker/wheel/network and are deliberately excluded.
- **H2.** A sequential runner with injectable process execution is testable hermetically, so the
  preflight's own test can run in the full suite without spawning real gates.
- **H3.** The value is demonstrated immediately: running the full suite now exposes drift that a
  push would hit in CI (measured in §5).

## 4. Gaps and unknowns (with what would reduce each)

| # | Gap / unknown | Evidence | What reduces it |
|---|---|---|---|
| G1 | **The full suite is currently RED on this branch (4 failures).** | Measured §5.2. | Run the gate; classify each failure as branch-introduced vs harness-environment. |
| G2 | **`FINOPS_CELL_ID` (set by THIS loop harness) breaks 2 tests.** `cell_scope()` lets the env var override the workdir scope, so `tests/test_control_room_build_contract.py` asserts `self-wd` but sees `self-wf_world_model_loop_deepseek_deepseek_v4_flash`. CI never sets it. | `env` shows `FINOPS_CELL_ID=wf_world_model_loop_deepseek_deepseek_v4_flash`; the two tests pass 23/23 when it is unset (§5.2). | Decide whether the preflight scrubs harness-only env vars for the pytest gates to match a clean CI shell (plan §Risks R1). |
| G3 | **`knowledge read` is CLI-reachable but absent from `DOCUMENTED_RESOLUTIONS`**, so `test_cli_resolution::test_every_documented_leaf_is_covered_by_the_table` fails. | `cli.py:100` adds `("knowledge","read")`; `cli.py:232` adds `read` to `_HELP`; `git show main:...cli.py` has neither; the table lacks the row. Introduced by `d6cdc0270`. | Add the table row (plan §Files) — the same file the new command must touch anyway. |
| G4 | **`_CLI` regex spans newlines**, so the skill line ending `--scope agentic-dynamics` followed by an `agentic-dynamics knowledge read …` line synthesises a fake command. | `test_agent_config_semantic` failure names `agent_config/skills/knowledge-reader.md`; Python probe reproduces the match across the newline. | Rewrite the separator to `[^\S\n]+` (or split-scope the examples). Plan §Files. |
| G5 | **Local tool versions may differ from CI** (ruff pinned 0.16.2; `pytest-xdist`/`pytest-timeout` presence). | `.github/workflows/pytest.yml:40`; local `ruff --version` = `0.16.2`; `pytest`, `xdist` import probe OK. | Preflight prints `ruff --version`; detect xdist/timeout and degrade argv; never crash. |
| G6 | **Local data root ≠ CI fixture restore.** CI copies `tests/fixtures/corpus/*` into `experiments/results/`; a local checkout has the real (untracked) runtime data. | `.github/workflows/pytest.yml:162-172`. | Document; do not copy fixtures locally (would mutate the data root). Coverage differences are expected, not a preflight failure. |
| G7 | **Full suite wall time.** Measured 110.76s with `-n auto`; fast path 45.27s. | §5. | Accept ~3 min total; the preflight is a pre-push ritual, not a fast path. |
| G8 | **CLI addition ripples into generated surfaces.** `agent_config/mental-model.md:601` is the CLI tree and is rendered to `.opencode/instructions/mental-model.md`. | `_gen_instructions.py --check` reports "40 generated files match"; `tests/test_cli_resolution.py` docstring names `mental-model.md` as a source. | Edit `agent_config/mental-model.md` then `python3 scripts/_gen_instructions.py`; the surfaces gate then stays green. |
| G9 | **Naming/home of the command** (`validate preflight` vs a new `ci preflight` group) is a judgment call with no precedent. | `validate` group already holds `tests`/`preexisting`/`render` runners (`cli.py` validate region). | Pick one in the plan; record the alternative. |

## 5. Measured current state (command outputs, 2026-09-21)

**5.1 The four cheap gates are green on the branch.**

```
$ ruff check .
All checks passed!
$ python3 scripts/_gen_instructions.py --check
surfaces OK — 40 generated files match agent_config/
$ python3 scripts/scan_docs_drift.py --check spec_lifecycle --fail-on-drift
DRIFT SCORE: 0            # spec_lifecycle: 1 checked, 1 current
$ bash scripts/test_fast.sh
599 passed, 3 skipped, 4125 deselected in 45.27s
$ python3 -m pytest tests/ --collect-only -q          # full suite shape
4726 tests collected
$ python3 -m pytest tests/ -m "not external" --collect-only -q
4600/4726 tests collected (126 deselected)
```

**5.2 The full deterministic suite is RED — and the failures split into two causes.**

```
$ python3 -m pytest tests/ -m "not external" -n auto --dist loadfile -q --timeout=600
FAILED tests/test_cli_resolution.py::test_every_documented_leaf_is_covered_by_the_table
FAILED tests/test_control_room_build_contract.py::test_domain_context_crosses_the_executor_boundary
FAILED tests/test_control_room_build_contract.py::test_retrieval_scope_is_cell_scoped_by_default_and_explicit_override_is_preserved
FAILED tests/test_agent_config_semantic.py::test_cli_commands_exist
4 failed, 4565 passed, 32 skipped in 110.76s
```

- **Branch-introduced (real, 2)** — both from `d6cdc0270` (the reader verb):
  - `test_cli_resolution`: set difference `Extra items in the left set: ('knowledge', 'read')`.
    Verified `main`'s `cli.py` has neither the `_COMMANDS` row nor `read` in `_HELP`.
  - `test_agent_config_semantic`: `agent_config/skills/knowledge-reader.md: unknown CLI command:
    agentic-dynamics agentic-dynamics knowledge`. `git show main:.../knowledge-reader.md` →
    file absent on `main`. Root cause is G4 (regex crossing the newline).
- **Harness-environment (not real, 2)** — `FINOPS_CELL_ID` overrides the cell scope:
  - `AssertionError: 'self-wf_world_model_loop_deepseek_deepseek_v4_flash' == 'self-wd'`.
  - `env -u FINOPS_CELL_ID python3 -m pytest tests/test_control_room_build_contract.py` → **23 passed**.

**Interpretation.** H3 holds: the preflight's full-suite gate would have caught G3/G4 before a
push. G2 is exactly the kind of unknown the loop is meant to surface: *the measuring environment
itself leaks into the measurement*.

## 6. Explicit non-goals

- Not a replacement for CI; not a docker/wheel/network reproduction (no `repro`/`packaging`/
  `workflow-parity`/`verify`).
- Not the `pipeline ci` plan, and not a phase of it.
- Not a fix for the two branch-introduced failures — those are the preflight's *first findings*
  (though the plan §Files proposes a minimal, in-context repair because the same file is touched).
- Not a merge/publish/session-close action (no P0 verbs).
