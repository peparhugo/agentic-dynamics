---
status: accepted
kind: smoke
spec: fleet_launch_smoke
phase: ws4_smoke
run: run-82800f7b4649
generated_at: 2026-09-03T07:50:00Z
---

# THE SMOKE — `fleet_launch_smoke` ws4_smoke (the wave's verdict)

The wave's central claim: after ws1-ws3 (clone wiring, broker path-view, stragglers) the
containerized path WORKS end to end on a real host. A green pytest without a real docker launch
would be the exact lie the wave exists to end. This document records the ONE real end-to-end
launch — the smoke — with its evidence (clone created → executor bound → broker accepts →
container spawns with the clone mounted read-only → trivial suite runs in the ro clone → verdict
returns through the envelope).

## The smoke precondition

- docker works on this host (`docker info` exit 0; client=server=29.1.3).
- `fleet/base:latest` exists. Rebuilt for the smoke from the wave tree
  (`bash scripts/fleet/build.sh base`) because the reference container round-trip requires a
  CURRENT image (its baked `/app` copy of `scripts/` + `src/` must match the repo — the parity
  suite's docker round-trip documents the same requirement). The rebuild is what makes the
  child `run_workflow.py` inside the cell run this wave's code, not a 2-day-old snapshot.
- The host-side launch broker is NOT installed as a systemd unit on this host, so the smoke
  drives the broker in its `serve` mode over the real unix-socket seam
  (`FINOPS_LAUNCH_BROKER_SOCKET=/tmp/agentic-dynamics-launch-broker.sock`) — the exact surface
  the systemd unit runs (`launch_broker.py serve`). The executor→`spawn_sibling`→`BrokerClient`
 → broker-serve→docker path is exercised for real.

## The smoke path (what ws1-ws3 wired)

1. `create_run_clone("run-82800f7b4649")` → the per-run clone at
   `PathConfig.runs_root/run-82800f7b4649/repo` (ws1's composition-root call, driven for the
   smoke with `FINOPS_RUNS_ROOT=/tmp/agentic-dynamics-runs` since the host default runs root is
   not writable by this user). The clone is a real independent git clone at the run's base sha.
2. A `DockerVerifierExecutor` is constructed with `run_clone` passed EXPLICITLY (ws1's binding
   shape — the executor carries the clone, never the env fallback).
3. The executor builds the typed launch request for a trivial `kind: test` phase
   (`verifier_readonly` profile + the clone reference), and `execute()` → `spawn_sibling`
   validates + emits it over the seam to the broker.
4. The broker re-validates the request (shared typed contract + the ws2 path-view validation —
   the request is HOST-view here, built by a host-side caller, so it validates against the host
   config; the container-view acceptance is unit-proven in ws2's suite) and performs the docker
   call — the ONLY docker call, per ws3.
5. Docker runs `fleet/base` mounting ONLY the run clone at `/repo` READ-ONLY.
6. The cell runs `run_workflow.py --only-phase <gate> --no-commit` inside the read-only clone;
   the trivial suite runs there; the verdict returns through the child's result envelope.

## Evidence

### 1. The clone exists at runs_root/<run-id>/repo (ws1)

```bash
$ git -C /tmp/agentic-dynamics-runs/run-82800f7b4649/repo rev-parse HEAD
abcb6cc7b8050119bfc2cd100826b988c7289fae   # == the wave's base sha
$ git -C /tmp/agentic-dynamics-runs/run-82800f7b4649/repo status --short   # clean
```

The clone was created by `create_run_clone` (the ws1 lifecycle function) — a fresh
`git clone --no-hardlinks` of the repo at the run base, with its OWN `.git` (independent object
store, detached HEAD at the base sha).

### 2. The executor is bound to the clone (ws1)

The `DockerVerifierExecutor` was constructed with `run_clone=<clone path>` (the explicit
constructor argument, not the `FINOPS_RUN_CLONE` env fallback). The request it built carries the
clone:

```
run_clone: /tmp/agentic-dynamics-runs/run-82800f7b4649/repo
mounts:    [('/repo', 'ro', '/tmp/agentic-dynamics-runs/run-82800f7b4649/repo')]
```

### 3. The broker accepts the request (ws2 path-view holds)

`spawn_sibling` (executor→broker over the real seam) returned `OK` — no `REFUSED`, no
`DOCKER_UNAVAILABLE`. The request is a real verifier request (mount_profile
`verifier_readonly`, verifier marker set, view `host`), validated by BOTH the wrapper and the
broker.

### 4. The container spawns with the clone mounted read-only (ws1+ws3 mount proof)

While the cell ran, `docker ps` + `docker inspect` observed the live container:

```
container id: ea0017059406a847cab174ce7ba888061d849272dfe402907811c3c04e98b779
image:        fleet/base
mount:        /tmp/agentic-dynamics-runs/run-82800f7b4649/repo -> /repo   (RW = false)
```

The docker inspect mount record shows `RW=false` — the clone is mounted READ-ONLY at `/repo`,
the ONLY mount in the verifier profile (no shared worktree, no shared `.git`, no credentials,
no writable state).

### 5. The trivial suite runs in the read-only clone

The suite file (`tests/test_ws4_smoke_cell.py`, written into the clone host-side before launch)
asserts the mount contract from INSIDE the container: `/repo/.git` is present, the smoke spec +
suite are readable at `/repo/...`, and writing `/repo/.ws4_ro_probe` raises `OSError` (read-only
proof, container-side). The cell ran it and reported:

```
tests_passed / tests_total = 1 / 1
test_executed_success = True
```

### 6. The verdict returns through the envelope

The executor's `execute()` classified the child's envelope and produced the StepResult:

```
StepResult.ok = True            state = ok
test_executed_success = True    tests_passed = 1 / tests_total = 1
```

That is the broker outcome → child envelope → classify → verdict chain, end to end.

## Wiring gaps the smoke EXPOSED and this phase FIXED

The smoke did not pass on the first try. It exposed two real wiring defects — both fixed in this
phase (they are the reason the smoke exists):

1. **The verifier cell died at boot: the D-18 probe ran in a credential-less cell.**
   `fleet/base`'s entrypoint runs the D-18 binary-resolution probe at container start (it
   asserts the model CLIs — `opencode`/`claude` — resolve). An AGENT cell mounts those CLI dirs
   (the D-2 auth set) so the probe legitimately passes. A VERIFIER cell carries NO credentials
   and NO CLI mounts BY CONSTRUCTION (it makes no model call — it runs a suite), so the probe
   always FAILED and the container exited 2 before the suite ever ran. Fix: the verifier request
   env now sets `FLEET_SKIP_PROBE=1` (the same env the compose gives supervisor services that
   invoke no CLI). `scripts/fleet/spawn_wrapper.py::build_verifier_request` + a unit test
   proving the verifier skips the probe while the agent request does not.
   *Without this fix the containerized verifier path could never have worked — every kind:test
   sibling would have died at the probe. This is exactly the class of defect the smoke exists to
   catch.*

2. **The sibling command baked the HOST interpreter into the container argv.**
   Both Docker executors built the cell command with the executor process's own `sys.executable`
   — when the executor runs on the host (this smoke drove it there; the wave's controller runs
   in-process), `sys.executable` is the host's `/usr/bin/python3`, a DIFFERENT interpreter than
   the fleet image's `/usr/local/bin/python3` (where the deps are installed). The cell therefore
   crashed at `import` (no `tree_sitter_languages`, etc.) before running the suite. Fix: the
   sibling command now uses `python3` — the interpreter the CONTAINER resolves on PATH — exactly
   as `spawn_wrapper`'s own default cell command and the compose `workflow-runner` command
   already do. `docker_executor.py` + `docker_verifier_executor.py`.
   *Without this fix the executor→broker→docker path only worked when the executor happened to
   run inside the fleet image (interpreter paths coinciding); a host-side composition root (the
   in-process wave, the smoke) always produced a broken cell argv.*

## LOG

| Claim | Result |
|---|---|
| (1) run clone created at `runs_root/<run-id>/repo` | PASS — `/tmp/agentic-dynamics-runs/run-82800f7b4649/repo`, HEAD `abcb6cc7b…`, clean |
| (2) executor bound to the clone (run_clone explicit) | PASS — request carries `run_clone` + the clone as the sole `/repo` source |
| (3) broker ACCEPTS the request (path-view fix holds) | PASS — `spawn_sibling` over the real seam returned OK, not REFUSED |
| (4) container spawns with the clone mounted read-only | PASS — `docker inspect` on live container `ea001705…`: clone → `/repo`, RW=false |
| (5) trivial suite runs in the read-only clone | PASS — container-side assertions on `/repo` contents + ro write refusal; `1/1` |
| (6) verdict returns through the envelope | PASS — `StepResult.ok=True`, `test_executed_success=True` |
| smoke-exposed gap A: verifier D-18 probe in a credential-less cell | FIXED — `FLEET_SKIP_PROBE=1` on verifier requests + unit test |
| smoke-exposed gap B: host `sys.executable` baked into cell argv | FIXED — sibling commands use container-PATH `python3` |
| gate | PASS — 196 passed / 1 skipped across test_spawn_wrapper, test_workflow_executor_parity, test_run_workflow_clone_wiring, test_launch_broker, test_broker_hostside; ruff clean on all touched files |

**Verdict: PASS — the containerized path works end to end.** One real cell: clone created →
executor bound → broker accepted → container spawned with the clone read-only → trivial suite
ran in the ro clone → verdict returned through the envelope. Committed as `[workflow] ws4_smoke`.
