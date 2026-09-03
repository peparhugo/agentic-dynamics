---
status: accepted
kind: smoke
spec: fleet_launch_container_smoke
phase: cs3_container_smoke
run: run-6bd836f71f01
generated_at: 2026-09-03T14:26:00Z
---

# THE SMOKE OF THE REAL SHAPE — `fleet_launch_container_smoke` cs3_container_smoke

The wave's central claim, held to the letter of hard rule 1: the wave is complete only when
the CONTAINER-TIER orchestrator — the compose `workflow-runner` service (image
`fleet/orchestrator`), whose container env carries `FINOPS_REPO_DIR`/`FINOPS_GIT_DIR` (cs1)
and, after this phase's fix, `FINOPS_RUNS_ROOT` — spawns a cell end to end through the host
broker. A host-view-only smoke (the previous wave's shape) is a failed wave. This document
records the ONE real container-tier drive and its DURABLE evidence (per cs2's
`smoke_harness`, persisted to `experiments/results/smoke/<spec>/<ts>.json` BEFORE the
container is removed).

## The smoke precondition

- docker works on this host (`docker info` exit 0; server 29.1.3).
- `fleet/base:latest` + `fleet/orchestrator:latest` rebuilt from the current wave tree
  (`bash scripts/fleet/build.sh base orchestrator`) so the images' baked `/app` copy matches
  the code under smoke — the ws4 requirement restated for cs3.
- The host-side launch broker is driven in `serve` mode over the real unix-socket seam
  (`FINOPS_LAUNCH_BROKER_SOCKET=/tmp/agentic-dynamics-launch-broker.sock`, the exact surface
  the systemd unit runs) — the compose workflow-runner container reaches it at the fixed
  `/run/launch-broker.sock` mount.
- A **deploy checkout** of the wave tree at the smoke commit (`git clone --no-hardlinks` of
  `/tmp/wt_wave2` to `/tmp/cs3_deploy_repo`) serves as the compose `/repo` mount source: the
  smoke cell spec + suite are COMMITTED at the wave HEAD (they must be inside the run clone
  the orchestrator mints, because the verifier cell runs its suite from inside the clone).

## The smoke path (what the container tier does, end to end)

1. The smoke driver (`experiments/results/smoke/fleet_launch_container_smoke/cs3_driver.py`)
   invokes the reference containerized execution path:

   ```
   docker-compose -f infrastructure/docker-compose.ladder.yml run --rm workflow-runner \
     python3 scripts/run_workflow.py --orchestrator \
       --spec experiments/results/smoke/fleet_launch_container_smoke/cs3_smoke_cell.yaml \
       --goal "<cs3 container-tier smoke>" \
       --model deepseek/deepseek-v4-flash \
       --workdir /repo
   ```

   The compose service env (cs1 + the cs3 `FINOPS_RUNS_ROOT` addition) carries
   `FINOPS_REPO_DIR=/repo`, `FINOPS_GIT_DIR=/repo/.git`,
   `FINOPS_RUNS_ROOT=/tmp/agentic-dynamics-runs`, and
   `FINOPS_LAUNCH_BROKER_SOCKET=/run/launch-broker.sock`.

2. The orchestrator (a container) derives `repo_root=/repo`, `git_dir=/repo/.git`,
   `runs_root=/tmp/agentic-dynamics-runs` — the broker-expected view — and `config_view=host`
   (the cs1 discriminator keys correctly; f1 fixed). It mints a control run, creates the run
   clone at `runs_root/<run-id>/repo` from the mounted `/repo`, and dispatches the smoke
   cell's ONE `kind: test` phase (`p5_test_gate`) to the DockerVerifierExecutor.

3. The verifier executor builds the clone-world request and `spawn_sibling` emits it over the
   seam socket. The host broker ACCEPTS it (no REFUSED) and performs the docker call — the
   ONLY docker call. Docker runs `fleet/base` mounting ONLY the run clone at `/repo`
   READ-ONLY.

4. The verifier cell runs `run_workflow.py --only-phase p5_test_gate --no-commit` inside the
   read-only clone; the trivial suite runs there; the verdict returns through the child's
   envelope to the orchestrator, which records the phase `ok` and exits 0.

## Evidence (durable, per cs2 — persisted before the `--rm` cell was removed)

`experiments/results/smoke/fleet_launch_container_smoke/20260903T142541Z.json` (schema
`fleet-smoke-evidence/v1`):

```
captured:      true
container_id:  8001a5ae7d032e20a464d614e7ed8de000342f1c24fe314934d1b5c10027d166
image:         fleet/base
mount_proof:   [{"source": "/tmp/agentic-dynamics-runs/run-c43b5ae19ceb/repo",
                 "target": "/repo", "rw": false}]
exit_code:     0
verdict:       {"ok": true, "state": "succeeded",
                "test_executed_success": true, "tests_passed": 1, "tests_total": 1}
events:        captured → snapshot_persisted → launch_completed → final_persisted
               → cleanup_start → cleanup_complete
```

The harness wrote the SNAPSHOT (container id + mount proof) while the launch was still in
flight — structurally before the broker's `docker run --rm` removed the cell (the event
order `snapshot_persisted` < `launch_completed` proves it) — then replaced it with the final
record (exit code + verdict), then ran cleanup. The evidence is re-derivable from the
artifact, not a `--rm` memory (cs2's guarantee).

The underlying run clone is a real independent git repo at the smoke base sha:

```
$ git -C /tmp/agentic-dynamics-runs/run-c43b5ae19ceb/repo rev-parse HEAD
88abcfbe4...   # the smoke commit (cs3's wave HEAD carrying the committed cell spec + suite)
```

## The wiring gap the smoke EXPOSED and this phase FIXED

The container-tier smoke did not pass on the first drive. It exposed one real wiring gap —
the exact class of gap the smoke exists to catch:

1. **The container env did not carry `FINOPS_RUNS_ROOT`.** cs1 set the container tier's repo
   view (`FINOPS_REPO_DIR`/`FINOPS_GIT_DIR`) but a container orchestrator ALSO derives its
   per-run clone root from this env. Without it the orchestrator's `create_run_clone` fell to
   the container-LOCAL default `/var/lib/agentic-dynamics/runs` — unwritable by the cell uid
   AND, worse, a DIFFERENT namespace from the host runs root the broker validates and binds
   (the host broker was driven with `FINOPS_RUNS_ROOT=/tmp/agentic-dynamics-runs`, the ws4
   smoke override). The first drive failed:
   `PermissionError: [Errno 13] Permission denied: '/var/lib/agentic-dynamics'`. Fix (this
   phase): `infrastructure/docker-compose.ladder.yml`'s `x-ladder-env` + `x-orchestrator-base`
   now carry `FINOPS_RUNS_ROOT` interpolated with the shared `/tmp` fallback
   (`${FINOPS_RUNS_ROOT:-/tmp/agentic-dynamics-runs}`), so a container orchestrator mints its
   clone at the SAME host-visible path the broker validates and bind-mounts (hard rule 3 —
   no tier derives its clone root differently). Proven both ways in
   `tests/test_fleet_container_env.py` (the compose env carries the runs root for every tier;
   a container-view derivation with it roots `runs_root` at the shared path).

A second drive-level detail was aligned, not a wiring fix: the smoke cell's test phase is
named `p5_test_gate` — a name in the spawn-wrapper's static `PHASE_SCOPE_AUTHORIZATION`
table (implementation) — because the executor→`spawn_sibling` path authorizes a phase by that
table when the engine does not inject declared scopes (the ws4 smoke cell used the same
authorized name for the same reason).

## LOG

| Claim | Result |
|---|---|
| (1) the compose workflow-runner service (container env carrying `FINOPS_REPO_DIR`/`FINOPS_GIT_DIR`/`FINOPS_RUNS_ROOT`) runs the orchestrator | PASS — control run minted inside the container; `config_view=host`, `repo_root=/repo`, `runs_root=/tmp/agentic-dynamics-runs` |
| (2) the broker ACCEPTS the container-built request (discriminator keys correctly — f1 fixed) | PASS — `spawn_sibling` over the seam returned OK, not REFUSED |
| (3) the verifier container spawns with the run clone mounted read-only | PASS — live cell `8001a5ae7d03…` (image `fleet/base`); mount proof `run-c43b5ae19ceb/repo -> /repo  (RW=false)` |
| (4) a trivial suite runs in the read-only clone | PASS — `tests_passed/tests_total = 1/1`, `test_executed_success=true` |
| (5) the verdict returns through the envelope | PASS — orchestrator phase `status: ok`, run `state: succeeded`, exit 0 |
| (6) the evidence is DURABLE (persisted before removal, re-derivable) | PASS — `20260903T142541Z.json` written (snapshot while the launch was in flight), schema + round-trip valid |
| smoke-exposed gap: container env lacked `FINOPS_RUNS_ROOT` (clone root fell to container-local `/var/lib/...`) | FIXED — `FINOPS_RUNS_ROOT` added to `x-ladder-env` + `x-orchestrator-base`; container-view derivation test added |
| gate | PASS — `test_fleet_container_env`, `test_smoke_harness`, `test_launch_broker`, `test_spawn_wrapper`, `test_path_config` all green (181 passed); ruff clean |

**Verdict: PASS — the CONTAINER-TIER orchestrator works end to end.** One real cell, driven
by the compose `workflow-runner` service (a container whose env carries the fixed repo view +
the runs root): request built in the container → broker accepted (discriminator keys
correctly) → verifier container spawned with the run clone read-only → trivial suite ran →
verdict returned through the envelope — with the mount proof + every artifact DURABLY
persisted before the cell was removed. Committed as `[workflow] cs3_container_smoke`.
