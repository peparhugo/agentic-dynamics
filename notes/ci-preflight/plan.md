# Plan — local CI preflight (`scripts/ci_preflight.py`, `agentic-dynamics validate preflight`)

This is the EXECUTE phase's contract. It follows the world model (`notes/world_model.md`);
deviations from it must be recorded in `notes/deviations.md`.

## Deliverable in one line

`scripts/ci_preflight.py` — a zero-model, stdlib-only runner that executes the five CI-parity
gates in cheap→expensive order, prints one PASS/FAIL line per gate, and exits non-zero if any
gate fails. Reachable as `agentic-dynamics validate preflight`.

## Gate registry (exact argv — parity is the whole point)

Ordered cheap→expensive; each entry is `(id, human name, argv, cwd)`.

| id | name | argv (cwd = repo root) | CI anchor |
|---|---|---|---|
| `lint` | Lint (ruff, whole active surface) | `ruff check .` | `pytest.yml:38-44` |
| `surfaces` | Generated instruction surfaces | `python3 scripts/_gen_instructions.py --check` | `pytest.yml:66-69` |
| `docs-drift` | Docs drift (spec lifecycle) | `python3 scripts/scan_docs_drift.py --check spec_lifecycle --fail-on-drift` | `pytest.yml:71-81` |
| `fast-path` | Fast path | `bash scripts/test_fast.sh` | `pytest.yml:106-118` |
| `full-suite` | Deterministic suite (external excluded) | `python3 -m pytest tests/ -m "not external" [-n auto --dist loadfile] --timeout=600` | `pytest.yml:173-181` |

Rationale for each choice:
- **lint** uses the bare `ruff` on `PATH` (not `python -m ruff`): that is what CI runs; report
  `ruff --version` in the preamble so a version mismatch is visible. Missing `ruff` is a **gate
  FAIL** with the install hint `pip install ruff==0.16.2`, never a crash — parity requires the gate.
- **surfaces**/**docs-drift** are stdlib-only (verified: both run with no install), so they are
  cheap and belong above the pytest gates.
- **fast-path** calls `bash scripts/test_fast.sh` (the CI command) rather than re-spelling
  `pytest -m fast`, so the budget-audited wrapper stays the single source of truth.
- **full-suite** derives from CI's shard command with exactly two deliberate omissions:
  `--splits/--group` (local runs are not sharded) and `-v` (summary readability). `-n auto
  --dist loadfile` is kept **only if** `pytest-xdist` imports; `--timeout` only if
  `pytest-timeout` imports. Both are present locally (probed), but the runner degrades instead of
  failing on a thinner box.

## Script interface

```
scripts/ci_preflight.py [--list] [--only <id> ...] [--skip <id> ...]
                        [--json <path|->] [--quiet] [--no-clean-env]
```

- `--list` prints the gate registry and exits 0.
- `--only`/`--skip` select a subset (repeatable); an id that matches nothing exits **2**.
- `--json -` writes a `ci-preflight/v1` report (keys: `schema`, `generated_at`, `repo_head_sha`,
  `ruff_version`, `gates[{id,name,argv,exit_code,status,elapsed_s}]`, `passed`, `failed`, `status`).
- Default prints a short header (repo HEAD, ruff version) plus one `PASS`/`FAIL` line per gate
  (with elapsed seconds) and a final `N passed, M failed` line. `--quiet` prints only the summary.
- Gate output is inherited (streamed) by default so a long suite is observable; `--quiet` still
  streams (it only suppresses the preflight's own chatter).
- Exit codes: **0** all gates PASS; **1** one or more gates FAIL; **2** usage error.

**Testability seam (required):** pure functions with injected process execution —
`run_gate(gate, *, runner=subprocess.run, env=...) -> GateResult` and
`run_preflight(gates=GATES, *, runner=..., which=shutil.which, env=...) -> int`. Production
`main()` passes the real callables; the test passes fakes. This keeps the unit test hermetic
(no real subprocesses, no Redis, no git).

**Environment hygiene (G2):** the two pytest gates run with `FINOPS_CELL_ID` removed from the
child env by default, because CI runs in a shell that never sets it and the variable rewrites the
cell scope inside 2 tests (measured). `--no-clean-env` restores the inherited env for reproducing
harness-specific behavior. This default is documented in the script docstring and asserted by a
test. (Only `FINOPS_CELL_ID` is scrubbed; other `FINOPS_*` config is left intact.)

## Files to touch

| File | Change | Why |
|---|---|---|
| `scripts/ci_preflight.py` | **new** — the runner (docstrings + inline reasoning per the verbose-mode constraint) | deliverable |
| `src/agentic_dynamics/cli.py` | add `("validate","preflight"): "ci_preflight.py"`; add `preflight` to the `_HELP` validate line | CLI mapping (G8) |
| `tests/test_cli_resolution.py` | add the `("validate","preflight")` row **and** the missing `("knowledge","read")` row | required by the guard; fixes G3 (see "scope" note) |
| `tests/test_agent_config_semantic.py` | change `_CLI` separator `\s+` → `[^\S\n]+` so the regex cannot span lines | fixes G4 (regex fragility, 1-char semantic) |
| `agent_config/mental-model.md` | add `validate …|preflight` to the CLI tree (line ~601) | source of the generated CLI surface |
| `.opencode/instructions/mental-model.md`, `.claude/rules/mental-model.md`, `CLAUDE.md`, `AGENTS.md` | regenerated by `python3 scripts/_gen_instructions.py` — never hand-edited | surfaces gate stays green |
| `scripts/CONTEXT.md` | append `maintained: ci_preflight.py` on its own line after `:32` | classification manifest (`test_script_classification`) |
| `tests/test_ci_preflight.py` | **new** — hermetic unit tests (below) | "a test for the runner" |

**Scope note (G1/G3/G4 — the decision the execute phase must make explicit).**
The task's deliverable is the preflight. But the preflight's `full-suite` gate can only reach
green if the two branch-introduced failures are repaired. Because the CLI change already forces
an edit to `tests/test_cli_resolution.py`, adding the missing `knowledge read` row there is a
near-free in-context fix; the `_CLI` regex fix in `test_agent_config_semantic.py` is a one-token
change. **Recommended:** make both repairs in the same unit and record them in
`notes/deviations.md` as small in-context fixes (not scope creep). If the execute phase judges
them out of scope, it must instead record them as the preflight's first findings and leave the
full-suite gate red — but then "exit non-zero if any gate fails" is demonstrably true and the
acceptance below must be read as "the runner is correct", not "the branch is green".

## Tests to create — `tests/test_ci_preflight.py` (hermetic; NOT `fast`-marked)

Not `fast`-marked because it imports `subprocess` (`test_fast_path_gate.FORBIDDEN_IN_FAST`); it is
still ~ms because every gate run is faked.

1. `test_registry_is_exactly_the_five_parity_gates` — ids `== {lint, surfaces, docs-drift,
   fast-path, full-suite}` and ordered cheap→expensive.
2. `test_gate_argv_matches_the_workflow` — assert the exact token lists, including the
   `--check spec_lifecycle --fail-on-drift` flags and `test_fast.sh`. (Pins parity to `pytest.yml`.)
3. `test_all_pass_exits_zero` — fake runner returns 0 for every gate → exit 0, every row `PASS`.
4. `test_any_failure_exits_nonzero` — one gate returns 1 → exit 1; the summary names it.
5. `test_summary_prints_one_pass_fail_line_per_gate`.
6. `test_missing_ruff_is_a_gate_failure_with_an_install_hint` — fake `which` returns `None`.
7. `test_cell_id_is_scrubbed_for_pytest_gates_and_restorable` — child env lacks `FINOPS_CELL_ID`;
   `--no-clean-env` keeps it; the stdlib gates keep it either way.
8. `test_json_report_is_ci_preflight_v1` — schema/keys/shape.
9. `test_only_skip_select_a_subset_and_unknown_id_exits_2`.
10. `test_full_suite_argv_omits_xdist_when_unavailable` — inject an import probe that fails.

## Local verification commands (execute phase)

```bash
ruff check .                                                   # gate 1 manually
python3 scripts/ci_preflight.py --list
python3 scripts/ci_preflight.py --only lint --only surfaces --only docs-drift   # fast smoke
python3 -m pytest tests/test_ci_preflight.py -v                # the new unit suite
python3 scripts/_gen_instructions.py --check                   # after editing agent_config
python3 scripts/_gen_instructions.py                           # regenerate surfaces
python3 -m pytest tests/test_cli_resolution.py tests/test_agent_config_semantic.py -q
python3 scripts/ci_preflight.py                                # end-to-end, expect all 5 PASS
```

## Acceptance criteria

1. `agentic-dynamics validate preflight` (and `python3 scripts/ci_preflight.py`) runs the five
   gates and prints exactly one PASS/FAIL line per gate.
2. Exit 0 iff all gates pass; exit 1 if any fails; exit 2 on a usage error.
3. The gate argv equals the CI commands (asserted by test #2).
4. `python3 -m pytest tests/test_ci_preflight.py -v` is green **without** spawning a real gate,
   touching Redis, or creating a worktree.
5. `tests/test_cli_resolution.py` and `tests/test_script_classification.py` are green (CLI row +
   manifest entry present).
6. `python3 scripts/_gen_instructions.py --check` is green after regeneration.
7. `ruff check .` is green.
8. An end-to-end `python3 scripts/ci_preflight.py` reports `5 passed` — which requires the G3/G4
   repairs (see scope note); otherwise record the residual failures explicitly.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| **R1 — env pollution (G2):** preflight inside a fleet cell reports false failures CI would not. | Scrub `FINOPS_CELL_ID` by default for the pytest gates; `--no-clean-env` to reproduce. Documented + tested. |
| **R2 — pre-existing red suite (G1/G3/G4):** the full-suite gate stays red and makes the preflight look broken. | Recommended minimal in-context repairs (same files already touched); otherwise record as first findings. |
| **R3 — ruff version drift (G5):** local ruff ≠ 0.16.2. | Print `ruff --version`; warn on mismatch in the header; never hard-fail solely on version. |
| **R4 — missing pytest plugins:** `-n auto`/`--timeout` unsupported. | Probe `importlib.util.find_spec`; drop unsupported flags; degrade, don't crash (test #10). |
| **R5 — data-root divergence (G6):** local has real runtime data, CI restores fixtures. | Do not touch the data root; document that corpus-dependent coverage may differ. |
| **R6 — generated-surface drift (G8):** forgetting to regenerate after the mental-model edit. | The `surfaces` gate itself catches it; run `_gen_instructions.py` then `--check` before commit. |
| **R7 — preflight total time (~3 min).** | Expected; cheap gates first so failures surface in seconds; `--only` for iteration. |
| **R8 — accidental duplication of `pipeline ci`.** | Keep the runner subprocess-only and CLI-only; no queue phases, no mypy/build_data gates. |

## Out of scope

CI jobs beyond the five gates (`verify`, `workflow-parity`, `repro`, `packaging`); any change to
`.github/workflows/pytest.yml`; fleet/admission wiring; publishing; the posterior phase.
