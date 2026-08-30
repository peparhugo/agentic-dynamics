---
status: accepted
---

# Fleet-ladder slice 2 — the orchestrator tier + the per-step scope model

**Status: PASS · Date: 2026-08-30 · Role: slice 2 (`fleet_ladder_implementation` p3 — the
execution phase).** Builds the orchestrator image + the sibling-spawn wrapper + the scope model,
per proposal §7 slice 2, §2 D-14, §4, §5 D-16. Every finding is a test result, a live build, or
a compose config.

## 0. Verdict

**PASS.** The spawn-wrapper's five-check validation passes its unit tests (a scope outside the
vocabulary fails at step 1, an unauthorized scope fails at step 2, a bad mount fails at step 3 —
all BEFORE the socket call), the `scope:` field parses and validates, and the orchestrator image
builds (docker CLI + the wrapper baked). No validation bypass.

## 1. The per-step scope model (D-16, §5) — `src/agentic_dynamics/experiment/experiment_spec.py`

- **`SCOPE_VOCABULARY`** — the closed five-scope set (`research_readonly` / `implementation` /
  `review_readonly` / `proposal_write` / `adversarial_readonly`). No others exist.
- **`SCOPE_CONFIGS`** — the declared config per scope (`results_mode` ro/rw, `network`,
  `write_flag`, `capabilities`), made machine-readable from the §5 table.
- **`PHASE_SCOPE_AUTHORIZATION`** — the phase→scope table: the proposal's own `fleet_ladder_plan`
  phases (p1/p2 → research_readonly, p3 → review_readonly, p4 → proposal_write,
  p5 → adversarial_readonly) + the implementation workflow's phases (p0/p7 → proposal_write,
  p1-p5 → implementation, p6 → adversarial_readonly) as the running example.
- **`phase_scope(phase)`** — resolves a phase's authorized scope: its declared `scope:` wins,
  else the table; `None` when neither exists (the wrapper then refuses the spawn at step 2).
- **The `scope:` field + validation** — `validate_spec` now rejects a phase whose `scope:` is
  not a vocabulary member (caught at spec-load time, not at spawn time).

## 2. The sibling-spawn wrapper (D-14/D-16) — `scripts/fleet/spawn_wrapper.py`

- **`validate_spawn(request)`** — the five ordered checks, in order, each failing BEFORE any
  docker call: (1) scope ∈ the vocabulary → (2) phase-authorized for the scope → (3) every
  mount target ∈ the four-mount contract + the D-2 auth set, and its mode matches the
  scope/contract (results ro vs rw) → (4) network = the scope's network → (5) no undeclared
  write flag (`FINOPS_KB_WRITE` only where the scope authorizes; `FINOPS_ACTUATION_ARMED`
  never — G2).
- **`validate_fleet_command(command)`** — the D-14 fleet:commands gate: action ∈
  {scale,drain,restart}, service ∈ the compose allowlist, scale count bounded [0, 32].
- **`spawn_sibling(request)`** — `validate_spawn` FIRST, then (only if valid) build/run the
  `docker run` sibling command; a validation error raises `SpawnValidationError` and never
  reaches the socket.
- **`build_phase_request(phase_def, …)`** — the campaign-wrapper mechanism: resolves the phase's
  scope and assembles the four-mount contract (scope's results mode) + network + canonical cell
  env (the write flag only when the scope authorizes it).
- **`consume_fleet_commands()`** — BRPOP `fleet:commands` (db1/6380), validate, dispatch only
  validated resize/drain/restart to `docker-compose`.

## 3. The orchestrator image (§4) — `Containerfile.fleet`

`fleet/orchestrator` = `fleet/base` + the **docker CLI** + the spawn-wrapper (baked via
`COPY scripts/`). **Fix on the way:** the stage first installed `docker.io` (Debian's *daemon*
package — no `/usr/bin/docker` client), which the smoke probe caught; corrected to `docker-cli`
(the client only — the orchestrator talks to the host daemon over the socket, it must NOT run
its own daemon). Build: `fleet/orchestrator:latest` (`5c358f452048`), `docker --version`
26.1.5, `spawn_wrapper.py validate` rejects a bad scope (exit 2) and accepts a valid one (exit 0).

## 4. The compose orchestrator tier — `infrastructure/docker-compose.ladder.yml`

`x-orchestrator-base` (image `fleet/orchestrator`, the cell env MINUS `FINOPS_KB_WRITE` — D-15)
+ `x-orchestrator-mounts` (the four + the D-2 auth set + `/var/run/docker.sock:ro` — D-3) +
the `campaign-wrapper` / `workflow-runner` services (both `run_workflow.py --orchestrator`).
The socket appears in exactly ONE tier — the orchestrator. `docker-compose config` validates.

## 5. The campaign wrapper as an orchestrator container (§7 slice 2)

`scripts/run_workflow.py` gains two OPT-IN flags (default path unchanged — the in-process run is
byte-identical):
- `--only-phase NAME` — filter the spec's phases to one phase (the sibling-cell entrypoint).
- `--orchestrator` — `_run_orchestrator`: each agent phase spawns as a sibling cell (via
  `build_phase_request` → `spawn_sibling`) running `run_workflow.py --only-phase <name>` with
  the phase's scope config; a phase whose scope fails validation is REFUSED before the socket
  call. The 4-wide grid shape is unchanged (the grid harness spawns cells; run_workflow's
  sequential phase model spawns one sibling per phase).

## 6. Test evidence

`python3 -m pytest tests/test_spawn_wrapper.py tests/test_experiment_spec.py
tests/test_compile_experiment.py tests/test_script_classification.py
tests/test_dependency_direction.py -q` → **100 passed**.

- Step 1 (scope ∉ vocab) — `test_scope_not_in_vocabulary_fails_step_1` + `test_spawn_sibling_refuses_before_socket_call`.
- Step 2 (unauthorized scope) — `test_unauthorized_scope_fails_step_2`; declared scope overrides — `test_declared_scope_overrides_the_table`.
- Step 3 (bad mount) — `test_bad_mount_target_fails_step_3`, `test_results_mount_mode_must_match_scope`, `test_worktree_mount_must_be_rw`.
- Steps 4/5 (network/env) — `test_network_mismatch_fails_step_4`, `test_undeclared_write_flag_fails_step_5`, `test_actuation_armed_never_allowed`.
- Scope field parses — `test_scope_field_bogus_fails_validation`, `test_scope_field_valid_member_validates_clean`, `test_scope_field_round_trips_through_yaml`.
- Orchestrator image builds — `docker build --target orchestrator` → `fleet/orchestrator:latest`.

## 7. Housekeeping fix (not a guard weakening)

The slice-1 fleet scripts were never entered into the script-classification manifest, so
`test_script_classification.py` reported them as orphans (a pre-existing failure that my
`spawn_wrapper.py` joined). Fixed honestly: a new **`fleet`** bucket (runtime modules under
`scripts/fleet/`, not CLI commands) in `scripts/CONTEXT.md` + the test's `BUCKETS` — the guard
is green without folding the fleet modules into a bucket they don't belong to.

## LOG

**PASS.** Scope model written (closed five-scope vocabulary + configs + the phase→scope
authorization table + the `scope:` field + validation); the sibling-spawn wrapper written (the
five ordered checks before the socket, the fleet:commands BRPOP consumer, `spawn_sibling` +
`build_phase_request`); the orchestrator image built (docker CLI + wrapper; the `docker.io`→
`docker-cli` daemon/client fix); the compose orchestrator tier added (socket in exactly one
tier); the campaign wrapper's `--orchestrator`/`--only-phase` opt-in path wired. 100 tests pass.
Committed.
