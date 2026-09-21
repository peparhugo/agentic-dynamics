# Deviations — local CI preflight (`notes/deviations.md`)

**Loop:** EXECUTE phase of `workflows/repository/world_model_loop.yaml` (prior → execute → posterior).
**Plan:** `notes/plan.md`. **World model:** `notes/world_model.md`.
**Branch:** `feature/ci-preflight` @ `f2f6bcaa1`.

Every entry states *what the plan said*, *what was true*, *what was done instead*. An entry that
records "plan followed" is included only where the world model's measured state changed during
execution (so the posterior phase does not diff against a stale model).

---

## D1 — `run_preflight` gained optional injectable metadata (signature superset)

- **Plan:** `run_preflight(gates=GATES, *, runner=..., which=shutil.which, env=...) -> int`.
- **Reality:** `run_preflight`'s summary prints the repo HEAD and the ruff version; the plan's
  signature has no seam to inject either, so a unit test calling it would shell out to real
  `git` and `ruff` — contradicting acceptance #4 ("green **without** spawning a real gate ...
  or creating a worktree").
- **Done instead:** kept the plan's signature and return type (it still returns `int`), and added
  optional keyword-only `repo_head_sha`, `ruff_version`, `quiet`, `clean_env`, `stream`
  parameters (all defaulted; production `main()` passes the real probes). The structured seam the
  tests use is the new pure function `evaluate_preflight(...) -> PreflightReport`, which the plan
  did not name but which is exactly its "pure functions with injected process execution" intent.
  `run_preflight` = `evaluate_preflight` + `render_summary` + return code.

## D2 — the `Gate` record is a superset of the plan's `(id, name, argv, cwd)`

- **Plan:** gate registry entries are `(id, human name, argv, cwd)`, all `cwd = repo root`.
- **Reality:** three behaviours the plan requires have no home in that 4-tuple: the missing-ruff
  FAIL + install hint (a `requires` binary probe), the `FINOPS_CELL_ID` scrub ("the two **pytest**
  gates" — a per-gate flag), and auditable parity (a CI anchor).
- **Done instead:** `cwd` is implicit (module constant `ROOT`), and the frozen `Gate` dataclass
  adds `ci_anchor`, `requires`, and `pytest_gate`. The registry is built by `build_gates(*, probe)`
  so the full-suite argv's plugin probes are injectable (plan test #10). `GATES` is the module
  default.

## D3 — `--json -` can interleave with streamed gate output

- **Plan:** "Gate output is inherited (streamed) by default ... `--quiet` still streams";
  separately, `--json <path|->` writes the report.
- **Reality:** `--json -` writes to stdout while the gates also stream to the inherited stdout, so
  the JSON document is not the only thing on that stream.
- **Done instead:** unchanged default behaviour (streaming is the plan's explicit requirement);
  the JSON payload is emitted last, and the caveat is documented in the module docstring. No test
  depends on `--json -`; `build_report` is the pure, tested path. `--json <path>` (the useful
  form) is unaffected.

## D4 — the global `agentic-dynamics` console script resolves to a different checkout

- **Plan:** the deliverable is "reachable as `agentic-dynamics validate preflight`" and acceptance
  #1 names that invocation.
- **Reality:** on this host `/home/drseuss/.local/bin/agentic-dynamics` imports
  `agentic_dynamics` from `/home/drseuss/ai-finops-framework/src/agentic_dynamics/` — a different
  checkout, which does not carry this branch's `_COMMANDS` row. Invoking the global binary
  therefore prints `unknown command validate preflight`.
- **Done instead:** verified reachability from THIS checkout's source:
  `cli._resolve(["validate", "preflight"]) == ("ci_preflight.py", [])` and
  `PYTHONPATH=src ... cli.main(["validate", "preflight", "--list"])` prints the registry.
  `tests/test_cli_resolution.py` pins the resolution. The stale installed console script is an
  environment fact for the posterior phase, not a defect in this branch.

---

## World-model state that changed during execution (not deviations)

- **G3 (branch-introduced `knowledge read` table row) — REPAIRED.** Added
  `(("knowledge", "read"), "kb_read.py", ())` to `tests/test_cli_resolution.py`. Chosen path from
  the plan's scope note ("Recommended: make both repairs in the same unit").
- **G4 (branch-introduced `_CLI` regex newline span) — REPAIRED.** `test_agent_config_semantic.py`'s
  `_CLI` separator changed `\s+` → `[^\S\n]+` (horizontal whitespace only).
- **G2 (`FINOPS_CELL_ID` leaks into the suite) — NEUTRALISED in the runner.** The two pytest gates
  are scrubbed by default (tested by `test_cell_id_is_scrubbed_for_pytest_gates_and_restorable`).
- **G1 (full suite red, 4 failures) — GREEN after G3/G4/G2.** End-to-end
  `python3 scripts/ci_preflight.py` reported **`5 passed, 0 failed`** (exit 0); the deterministic
  suite alone was **4581 passed, 32 skipped in 109.3s**. The world model's measured `4 failed`
  (§5.2) is superseded.

## Not done (explicitly out of scope, per the plan)

`.github/workflows/pytest.yml` unchanged; no `verify`/`workflow-parity`/`repro`/`packaging` gates;
no fleet/admission wiring; no publish/merge/session-close (P0 verbs). The `pipeline ci` plan is
untouched — the preflight is subprocess-only and deliberately disjoint.
