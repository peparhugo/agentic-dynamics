---
status: accepted
kind: adversarial
spec: fleet_launch_smoke
phase: ws5_adversarial
run: run-82800f7b4649
generated_at: 2026-09-03T07:39:00Z
---

# Adversarial review — `fleet_launch_smoke` ws5_adversarial (the independent pro pass)

A DIFFERENT model and session (pro vs the flash author) re-verifies the smoke wave against the
actual code + the smoke evidence, never asserting. Attack order: (1) ws1 clone-wiring, (2) ws2
broker path-view, (3) ws4 smoke evidence, (4) cross — parity suite + gate. Every finding is
reproduced against the code at `d4c8d60ef` (the ws4_smoke commit) with the command/artifact that
produced it; a claim I could not reproduce is a FAILED finding, not a PASS.

**Verdict up front: NOT merge-ready.** The containerized path WORKS end to end for the
host-view / in-process orchestrator — that is a real, re-verified result (the smoke's clone,
the container, the suite, the verdict are all real). But the wave's central claim is that the
*containerized* path works, and the containerized orchestrator — the compose reference path —
would refuse its own spawn. ws2's path-view fix is keyed to a path the compose topology never
produces, and the clone-world shared-surface check collides for a container-derived config. The
smoke could not see either because it drove the orchestrator in-process on the host.

---

## The three findings (table)

| # | Finding | Disposition |
|---|---|---|
| F1 | ws1+ws2 — **the containerized orchestrator's spawn path is still broken.** The container env (`x-ladder-env`) never carries `FINOPS_REPO_DIR`/`FINOPS_GIT_DIR`, so a container-tier orchestrator derives `repo_root = PROJECT_ROOT = /repo` (the mounted live repo). (a) `config_view` keys "container" on `repo_root == "/app"` (the baked image copy), so the real container config (`/repo`) is classified `host` — the ws2 view machinery never activates. (b) `_mounts_shared_surface` treats `repo_root` as a shared surface, so with `repo_root == /repo == REPO_TARGET` a clone-world cell's own `/repo` clone mount is mis-flagged as "shared worktree/.git" and the request is refused at `validate_spawn` step 3 — by the orchestrator's OWN client-side validation. **Reproduced** below. | RECORDED — the clean fix is env-based (set `FINOPS_REPO_DIR`/`FINOPS_GIT_DIR` in the container env, the prior review's remediation #1), not a view-key tweak. |
| F2 | ws4 — **the container-view path was never smoke-proven.** The smoke drove the HOST-view path (in-process orchestrator) and admits it ("the container-view acceptance is unit-proven in ws2's suite"). The container-view path — the actual D-16 split ws2 exists to fix — is dry-run/stub tested but never reached a real docker container. | RECORDED — honest in the smoke doc + preregistration; F1 shows the path is also *mis-keyed*. |
| F3 | ws4 — **the mount-proof evidence is a recorded observation, not durably re-verifiable.** The container `ea0017059406` was `--rm`'d, so the "RW=false" docker-inspect record cannot be re-derived now. Surviving: the real clone, the smoke cell test+spec, the `step_attempt` ok row, and the container-side ro-write refusal assertion. | RECORDED — evidence is consistent with a real run, but the docker-level claim is recorded, not re-checkable. |

---

## F1 — the containerized orchestrator's spawn path is still broken (decisive)

The reference execution path for a spec workflow is the **containerized** orchestrator
(`campaign-wrapper`: `python3 scripts/run_workflow.py --orchestrator`, compose
`working_dir: /repo`, image `fleet/orchestrator`). The smoke drove the orchestrator in-process on
the host instead (the preregistration §3 records the broker unit is not installed, and the smoke
doc records "this smoke drove it there"). That host-side run inherits the operator's env, so
`FINOPS_REPO_DIR` is set and `repo_root` resolves to the host checkout path — which never
collides with the fixed `/repo` mount target.

A container-tier orchestrator does NOT inherit `FINOPS_REPO_DIR` — `x-ladder-env`
(`infrastructure/docker-compose.ladder.yml:31-63`) sets `HOME`/`OPENCODE_BIN`/`CLAUDE_BIN`/Redis/
proxy vars but NOT the repo dirs (they appear only as `${FINOPS_REPO_DIR:?...}` **mount sources**,
interpolated by the host's docker-compose, never exported into the container). The scripts'
own sys.path bootstrap (`scripts/_bootstrap.py:16`, `spawn_wrapper.py:82-85`) inserts
`<cwd>/src`, and `cwd` is `/repo` (compose `working_dir: /repo`, `entrypoint.sh:44` `exec "$@"`),
so `PathConfig.from_env()` → `repo_root = PROJECT_ROOT = /repo` (`paths.py:192`). The image's
baked `/app` copy is never what runs — the compose comments name it "the image's stale /app copy".

Two consequences, both reproduced:

**(a) `config_view` mis-keys the view.** `CONTAINER_REPO_ROOT = "/app"`
(`broker_contract.py:185`) and `config_view` returns `container` iff `repo_root == "/app"`
(`:224`). A container config rooted at `/repo` is classified `host`, so the ws2 view machinery
never activates for the real topology:

```bash
python3 - <<'PY'
import sys; sys.path[:0] = ['scripts/fleet','src']
from broker_contract import config_view, CONTAINER_REPO_ROOT, VIEW_CONTAINER
from agentic_dynamics.core.paths import PathConfig
import os
for k in ('FINOPS_REPO_DIR','FINOPS_GIT_DIR','FINOPS_RESULTS_DIR'):
    os.environ.pop(k, None)
os.environ['HOME']='/home/drseuss'; os.environ['FINOPS_WORKTREE_ROOT']='/tmp'
cfg = PathConfig.from_env(require_existing=False)
print(cfg.repo_root, '->', config_view(cfg), ' (constant=', CONTAINER_REPO_ROOT, ')')
PY
# <this-host PROJECT_ROOT> -> host  (constant= /app)   # in-container PROJECT_ROOT is /repo -> host
```

**(b) the clone-world shared-surface check collides.** `_mounts_shared_surface`
(`spawn_wrapper.py:448`) treats `str(path_config.repo_root)` as a shared surface. For a container
config `repo_root == /repo == REPO_TARGET`, the clone-world cell's own clone mount
(`target=/repo`) is mis-flagged and the request is refused — by the orchestrator's OWN
client-side `validate_spawn`, before the broker is ever reached:

```bash
python3 - <<'PY'
import sys; sys.path[:0] = ['scripts/fleet','src']
from pathlib import Path
from agentic_dynamics.core.paths import PathConfig
import spawn_wrapper
cfg = PathConfig(repo_root=Path('/repo'), git_dir=Path('/repo/.git'),
    worktrees_root=Path('/tmp'), runs_root=Path('/var/lib/agentic-dynamics/runs'),
    results_dir=Path('/repo/experiments/results'), state_root=Path('/tmp/opencode_state'),
    auth_home=Path('/home/drseuss'))
req = spawn_wrapper.build_phase_request({'name':'p1_slice1_base_supervisor','scope':'implementation'},
    goal='g', workdir='/tmp/wt', model='deepseek/deepseek-v4-pro', spec_name='spec_x',
    path_config=cfg, run_clone='/var/lib/agentic-dynamics/runs/run-xyz/repo')
print('view stamped:', req['view'])
for e in spawn_wrapper.validate_spawn(req, phase_scopes={'p1_slice1_base_supervisor':'implementation'}, path_config=cfg):
    print(' -', e)
PY
# view stamped: host
#  - step 3: mount target '/repo' (source '.../run-xyz/repo') is the SHARED worktree/.git surface
#    — a clone-world cell mounts its own run clone ... never the shared worktree or the shared .git
```

I first attempted the natural fix — re-key `CONTAINER_REPO_ROOT` from `/app` to `/repo` — and it
did NOT close the gap: it produced exactly the (b) collision in the ws2 tests
(`tests/test_launch_broker.py::test_container_view_clone_world_request_validates_and_mounts_the_host_clone`
fails with the shared-surface refusal). That the fix of the constant re-opens a second defect
proves the view-keyed approach itself is unsound: the container cannot know the host path the
D-16 alias mounts at, because `FINOPS_REPO_DIR` is absent from its env. The remediation the prior
review already named (set `FINOPS_REPO_DIR`/`FINOPS_GIT_DIR` in the container env, env-derived and
fail-closed) makes both sides derive the same config, and is the correct fix — it resolves the
split AND the (b) collision together.

Note: I did NOT land that env change here. It is a compose-level change that only takes effect
when the containerized orchestrator actually runs, and this wave never ran it — landing it
unverified would itself be an unverified change. It is recorded as the required remediation for
the ws6 gate / a follow-up, and is why the wave is not merge-ready for the reference path.

---

## F2 — the container-view path was never smoke-proven

The smoke (`docs/reviews/fleet_launch_smoke_ws4_smoke.md:45-47`) states the request "is HOST-view
here, built by a host-side caller, so it validates against the host config; the container-view
acceptance is unit-proven in ws2's suite." So the smoke's one real end-to-end launch traversed the
host-view + clone-world path only. The container-view path — a request built by a container-tier
caller whose D-16 alias targets `/repo` — is covered by `tests/test_launch_broker.py` (dry-run)
and `tests/test_broker_hostside.py` (stub docker), never a real `docker run`. F1 shows it would not
have passed a real launch anyway.

---

## F3 — the mount-proof evidence is a recorded observation, not durably re-verifiable

Re-verified what survives, and what does not:

| Claim | Surviving artifact | Re-verifiable? |
|---|---|---|
| clone created at `runs_root/run-82800f7b4649/repo`, HEAD `abcb6cc7b`, clean | the clone on disk (own `.git`, `HEAD abcb6cc7b`, two untracked smoke files) | YES — re-verified |
| container `ea0017059406` mounted the clone at `/repo` `RW=false` | none — `--rm` deleted it (`docker inspect ea0017059406` → "no such object") | NO — recorded observation only |
| trivial suite ran in the ro clone | `tests/test_ws4_smoke_cell.py` (in the clone) — asserts `/repo` read-only via an `OSError` on write | partially — the file exists; the *run* is recorded |
| verdict returned (`StepResult ok=True`, `1/1`) | `step_attempts` row `att-92659617cfe6` (`ws4_smoke`, `state ok`) in the control db | the agent phase ok is real; the *cell* StepResult is recorded, not persisted |

The container-side ro-write assertion is the strongest surviving proof — if `/repo` had been
writable the suite would have failed — but the docker-level "RW=false" claim and the cell verdict
are recorded assertions the reviewer cannot re-derive. Consistent with a genuine run; not
independently re-checkable.

---

## ws1 re-verification (PASS) — the clone is really created and bound

`create_run_clone` IS invoked, not just documented. In `scripts/run_workflow.py`:

- `_build_orchestrator_executors` calls `create_run_clone(run_id, base_sha=..., path_config=...)`
  at `:375`, BEFORE either executor is constructed.
- `run_clone` is passed explicitly to both `DockerAgentExecutor` and `DockerVerifierExecutor`
  at `:388-391`.
- `os.environ[RUN_CLONE_ENV] = run_clone` is exported only AFTER construction (`:397`), so the
  executors' `run_clone` provably came from the constructor arg, not the env fallback.
- The composition is reached from `_run_workflow_cli` at `:674-676`, gated on `--orchestrator`
  AND a minted control-run id (a containerized run without its run row refuses loudly at `:670-673`).

The ws1 tests (`tests/test_run_workflow_clone_wiring.py`) drive the REAL `main()` composition
root (monkeypatched argv), create a REAL git clone, and assert (a) `create_run_clone` runs before
`run_workflow`, (b) the clone lands at `runs_root/<run-id>/repo` with its own `.git`, and (c) the
executors carry the explicit clone path even when a "decoy" `FINOPS_RUN_CLONE` env is set. The
clone exists on disk and matches (`HEAD abcb6cc7b`). **PASS.**

## ws2 re-verification (PARTIAL) — the mechanism is real, the keying is wrong

The view machinery is real and coherent at the mechanism level: `request_view` /
`validation_config_for_request` (`launch_broker.py:186-203`) select a container-view or host-view
`PathConfig` for BOTH shared validations, an unknown view refuses at the typed gate, and the
broker's own launch argv always expands from the host config. The broker-side tests
(`test_launch_broker.py:348-451`) prove the acceptance/refusal shape against a synthetic
container config. But the container config the tests synthesize (`container_view_config`, keyed on
`/app`) is not the config the compose topology actually produces (`/repo`) — see F1. The mechanism
works; the discriminator is keyed to a path that never occurs.

## ws3 re-verification (PASS) — the loose docker callers are closed

`scripts/archive/backfill_sonar.py` now documents its `docker run` as the second benign
read-only exception with the reason (`:127-130`, `-v ...:/usr/src:ro`). The launch-broker unit
committed at `infrastructure/agentic-dynamics-launch-broker.service` carries NO host literal —
`WorkingDirectory=@REPO_ROOT@` (`:76`) is a template placeholder rendered by
`infrastructure/gen_launch_broker_service.py` at install time. **PASS.**

---

## Cross — parity suite + gate

```bash
python3 -m pytest tests/test_run_workflow_clone_wiring.py tests/test_broker_hostside.py \
  tests/test_launch_broker.py tests/test_ws3_stragglers.py tests/test_workflow_executor_parity.py \
  tests/test_spawn_wrapper.py tests/test_fleet_guards.py tests/test_system_snapshot.py \
  -q -p no:cacheprovider
# 239 passed, 1 skipped in 15.65s
python3 -m ruff check scripts/fleet/broker_contract.py scripts/fleet/launch_broker.py \
  scripts/fleet/spawn_wrapper.py scripts/fleet/docker_executor.py \
  scripts/fleet/docker_verifier_executor.py scripts/run_workflow.py \
  tests/test_launch_broker.py tests/test_spawn_wrapper.py \
  tests/test_run_workflow_clone_wiring.py tests/test_ws3_stragglers.py tests/test_broker_hostside.py
# All checks passed!
```

Green, and the tests are substantive (the ws1 suite drives the real composition root; the
broker-hostside suite round-trips the real `serve()` over a real unix socket against a stub docker
binary). Note: a bare green suite is exactly what the smoke exists to falsify — the suite stays
green precisely because it never runs a containerized orchestrator, so F1 is invisible to it.

---

## LOG

| Claim | Result |
|---|---|
| ws1 — `create_run_clone` invoked at the composition root, clone real, `run_clone` explicit | **PASS** — `run_workflow.py:375/:388/:397/:674`; clone on disk `HEAD abcb6cc7b`; ws1 tests drive the real `main()` |
| ws2 — container-view request validates against the container-view config and reaches docker | **PARTIAL** — mechanism real + unit-proven, but keyed on `/app` (never occurs); the real container derives `/repo`, which `config_view` classifies `host` (F1a) |
| ws3 — backfill_sonar documented + broker unit host-literal removed | **PASS** — `:127-130` record; `@REPO_ROOT@` template + `gen_launch_broker_service.py` |
| ws4 — smoke evidence REAL (clone + container + mount + suite + verdict) | **PARTIAL** — clone + smoke files + agent-phase ok are real; container `--rm`'d (mount record not re-derivable), and only the host-view path was launched (F2/F3) |
| ws4 — the containerized orchestrator path works end to end | **FAIL** — a container-tier orchestrator refuses its own spawn (`validate_spawn` step 3 shared-surface collision), reproduced above (F1b) |
| cross — parity suite + gate green | **PASS** — 239 passed / 1 skipped; ruff clean |

## Release verdict

**NOT merge-ready to main.** The host-view / in-process containerized path works end to end — that
is a genuine, re-verified result, and ws1 + ws3 are correct. But the wave's object was the
*containerized* path, and the containerized orchestrator (the compose reference path) would refuse
its own spawn: the container env never carries `FINOPS_REPO_DIR`/`FINOPS_GIT_DIR`, so a
container-tier orchestrator derives `repo_root=/repo`, which (a) mis-keys ws2's view discriminator
and (b) collides with `REPO_TARGET` in the clone-world shared-surface check. The smoke could not
see either because it drove the orchestrator in-process on the host. Required before merge: set
`FINOPS_REPO_DIR`/`FINOPS_GIT_DIR` in the container env (env-derived, fail-closed — the prior
review's remediation #1), then re-smoke the `campaign-wrapper` service so the container-view +
clone-world path is actually exercised.
