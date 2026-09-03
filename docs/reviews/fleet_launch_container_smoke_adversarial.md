---
status: accepted
kind: adversarial
spec: fleet_launch_container_smoke
phase: cs4_adversarial
run: run-6bd836f71f01
generated_at: 2026-09-03T14:44:00Z
---

# Adversarial review — `fleet_launch_container_smoke` cs4_adversarial (the independent pro pass)

A DIFFERENT model and session (pro vs the flash author) re-verifies the container-smoke wave
against the actual code + the durable smoke evidence, never asserting. Attack order: (1) cs1 —
does the container tier carry the env, and does a container orchestrator now derive the
broker-expected view? (2) cs3 — is the smoke evidence from the CONTAINER-TIER orchestrator, is
it durable/re-derivable, and can I find ANY path it did not traverse? (3) cross — reproduce the
f1 failure shape both directions (with the fixed env CAN spawn; without it the discriminator
refuses). Every finding is reproduced against the code at `8ba3b056c` with the command/artifact
that produced it; a claim I could not reproduce is a FAILED finding, not a PASS.

**Verdict up front: NOT merge-ready to main — one decisive residual, two recorded scope gaps.**
The three findings of the `fleet_launch_smoke` adversarial review (f1 container env, f2
container-view never smoke-proven, f3 mount proof a `--rm` observation) are **CLOSED**, each
re-verified below, and the container-tier path WORKS end to end — the compose `workflow-runner`
container (with the cs1 env) builds a request the broker accepts, spawns the verifier cell with
the run clone mounted read-only, the trivial suite runs, and the verdict returns, all durably
persisted before removal. But the smoke's success depended on ONE host-side input the wave did
not actually reconcile: the host launch broker was driven **manually with
`FINOPS_RUNS_ROOT=/tmp/agentic-dynamics-runs` exported** (the ws4 override), while the deployed
broker unit (`infrastructure/agentic-dynamics-launch-broker.service` + `gen_launch_broker_service.py`)
carries **no** `FINOPS_RUNS_ROOT`. The cs3 fix set the runs root in the CONTAINER tier only, so
in the real deployment the broker tier still defaults to `/var/lib/agentic-dynamics/runs` and
**refuses the container's clone** — the same hard-rule-3 violation (a tier deriving its clone
root differently) the wave exists to close, one tier over. That is F1. Two further gaps — the
broken `campaign-wrapper` service and the untraversed agent-cell/submit front-end — are recorded.

---

## The findings (table)

| # | Finding | Disposition |
|---|---|---|
| F1 | cs3 — the **container↔broker runs-root is not reconciled.** cs3 added `FINOPS_RUNS_ROOT` to `x-ladder-env`/`x-orchestrator-base` (the CONTAINER tier) only; the host launch broker (unit template + `gen_launch_broker_service.py`) sets **no** `FINOPS_RUNS_ROOT`, so it defaults to `/var/lib/agentic-dynamics/runs` and `validate_launch_request` step 5b + `validate_spawn` step 3 **refuse** the container's `/tmp/agentic-dynamics-runs/run-<id>/repo` clone. The smoke passed only because it started the broker by hand with the ws4 override. **Reproduced.** | **RECORD (blocker).** Fix: carry `FINOPS_RUNS_ROOT` (interpolated, shared-`/tmp` fallback) in the broker unit + generator, mirroring the cs3 container fix; or record an operator prerequisite and the broker's refusal stays. |
| F2 | the **`campaign-wrapper` service is broken.** Its command is `run_workflow.py --orchestrator` with no `--spec/--goal/--model/--workdir` (all `required=True`), so it exits 2 at argparse and, with `restart: on-failure`, crash-loops under `docker compose up -d`. The smoke drove `workflow-runner` with an overridden command, never `campaign-wrapper`. **Reproduced.** | **RECORD** (pre-existing; the smoke's literal mandate was `workflow-runner`, but it is a broken orchestrator service in the "real deployment shape"). |
| F3 | the smoke traversed only the **verifier (`kind: test`) clone-world cell** and the **direct `run_workflow.py --orchestrator` entry**; it never drove an **agent (`implementation_rw`) clone-world cell** (the results/auth/state/credential mount surface) nor the **submit→consume front-end** (`spawn_wrapper.py consume` → `validate_submit_request` → broker `docker compose run`), `workflow-runner`'s canonical command. | **RECORD** (scope note — the verifier is the leanest mount; the full agent surface + the submit path are unit-proven, not smoke-proven). |

---

## F1 — the container↔broker runs-root is not reconciled (decisive)

cs3's fix is the correct *idea* — a container orchestrator derives its per-run clone root from
`FINOPS_RUNS_ROOT`, and without it the clone falls to the container-local `/var/lib` namespace
(unwritable, and a different namespace from the host broker's bind). But the fix landed the env
in **one** of the two tiers that must agree. The broker is the tier that *validates* `run_clone`
(step 5b of `broker_contract.validate_launch_request`, `broker_contract.py:581-592`) and
*bind-mounts* it; its own `PathConfig` comes from the broker process's environment, which is the
systemd unit's. The unit (`infrastructure/agentic-dynamics-launch-broker.service:75-80`) sets
`REPO`, `FINOPS_DOCKER_BIN`, `FINOPS_DOCKER_COMPOSE_BIN` — and nothing else. `gen_launch_broker_service.py`
renders only `@REPO_ROOT@` (three tokens, `EXPECTED_TOKEN_COUNT = 3`). So the broker derives
`runs_root = /var/lib/agentic-dynamics/runs` (the `paths.py:78` default) while the container
derives `/tmp/agentic-dynamics-runs` (cs3). Reproduced against the real unit env:

```bash
python3 - <<'PY'
import sys; sys.path[:0] = ['scripts/fleet','src']
from agentic_dynamics.core.paths import PathConfig
import launch_broker, spawn_wrapper
unit_env = {"REPO": "/home/drseuss/ai-finops-framework",
            "FINOPS_DOCKER_BIN": "docker", "FINOPS_DOCKER_COMPOSE_BIN": "docker-compose",
            "HOME": "/home/drseuss"}
broker_cfg = PathConfig.from_env(unit_env, require_existing=False)
print("BROKER runs_root =", broker_cfg.runs_root)   # -> /var/lib/agentic-dynamics/runs
cont_env = {"FINOPS_REPO_DIR":"/repo","FINOPS_GIT_DIR":"/repo/.git","FINOPS_WORKTREE_ROOT":"/tmp",
            "FINOPS_RUNS_ROOT":"/tmp/agentic-dynamics-runs","HOME":"/home/drseuss"}
cont_cfg = PathConfig.from_env(cont_env, require_existing=False)
clone = "/tmp/agentic-dynamics-runs/run-c43b5ae19ceb/repo"
req = spawn_wrapper.build_verifier_request(
    {'name':'p5_test_gate','scope':'implementation','kind':'test'},
    goal='g', workdir='/repo', model='deepseek/deepseek-v4-flash', spec_name='cs3_smoke_cell',
    path_config=cont_cfg, run_clone=clone)
for e in launch_broker.validate_launch_request(req, path_config=broker_cfg): print(" -", e)
for e in spawn_wrapper.validate_spawn(req, phase_scopes={'p5_test_gate':'implementation'},
                                       path_config=broker_cfg): print(" -", e)
PY
#  - run_clone '/tmp/agentic-dynamics-runs/run-c43b5ae19ceb/repo' is not a runs_root/<run-id>/repo
#    clone path (must be two segments under the runs root /var/lib/agentic-dynamics/runs, ...)
#  - step 3: run_clone '/tmp/agentic-dynamics-runs/run-c43b5ae19ceb/repo' is not a runs_root/<run-id>/repo
#    clone path — a clone-world request must name the run's private clone
```

The smoke did not see this because the smoke itself records the override:
`fleet_launch_container_smoke_cs3_smoke.md:110-112` ("the host broker was driven with
`FINOPS_RUNS_ROOT=/tmp/agentic-dynamics-runs`, the ws4 smoke override"), and the preregistration's
supplementary note §3 flagged that the host default is unwritable and the override "must keep
that override in play". cs3 put it in the container; it did not put it in the broker's deployed
config. The test suite is blind to it for the same reason the smoke was: `test_fleet_container_env.py`
asserts `FINOPS_RUNS_ROOT` only on the **compose** anchors (`test_x_ladder_env_carries_the_shared_runs_root`
and friends), and no test models the broker under its unit env. The remediation is one env line
in the unit + one token in the generator (mirroring cs3), plus a test that asserts the broker
tier carries the same runs root — without it, "no tier derives its clone root differently"
(hard rule 3) is satisfied only while a human remembers to export the override.

## F2 — the `campaign-wrapper` service is broken

`docker-compose.ladder.yml:366-370` defines `campaign-wrapper` with
`command: ["python3", "scripts/run_workflow.py", "--orchestrator"]` and no arguments, but
`run_workflow.py` marks `--spec/--goal/--model/--workdir` `required=True` (`:403-406`):

```bash
python3 scripts/run_workflow.py --orchestrator; echo "exit $?"
# run_workflow.py: error: the following arguments are required: --spec, --goal, --model, --workdir
# exit 2
```

With `restart: on-failure` this is a crash loop under `docker compose up -d`. The smoke drove
`workflow-runner` with an overridden command (`docker-compose run --rm workflow-runner python3
scripts/run_workflow.py --orchestrator --spec … --goal … --model … --workdir /repo`), which is the
AGENTS.md reference path — but that is `workflow-runner`, not `campaign-wrapper`, and neither is
`workflow-runner`'s own canonical command (`spawn_wrapper.py consume`). The
`fleet_launch_smoke` adversarial review already named `campaign-wrapper` as the reference shape
and asked it be re-smoked (`fleet_launch_smoke_adversarial.md:238`); this wave smoked
`workflow-runner` instead. Recorded, not fixed here (read-only review; the fix is to give
`campaign-wrapper` the same `consume` command or a submit-fed entry, or remove it).

## F3 — the verifier-only, direct-entry smoke left the agent cell + submit path unproven

The smoke's ONE cell was `p5_test_gate`, a `kind: test` phase dispatched to
`DockerVerifierExecutor`. Its clone-world mount is the LEANEST surface — exactly
`[{source: <clone>, target: /repo, mode: ro}]` (`build_verifier_request` →
`mounts_for_profile("verifier_readonly", run_clone=…)`, `broker_contract.py:351-359`) — no
results, no D-2 auth, no per-attempt state, no credential file. An agent cell
(`implementation_rw`, clone-world) carries the full surface — results rw at `/app/experiments/results`,
the D-2 auth dirs, `/state`, the credential FILE — which exercises the cross-tier derivation of
every other host path, not just the clone. That path, and the submit→consume front-end
(`spawn_wrapper.py consume` → `validate_submit_request` → broker `docker compose run`), are
unit-proven (`test_launch_broker.py`, `test_spawn_wrapper.py`, `test_workflow_executor_parity.py`)
but were not smoke-proven in the container tier. Recorded as a scope note, not a blocker: the
mandate was "drive ONE cell", and a verifier is a cell — but it is the cheapest cell, and the
wave's central claim is "the real fleet deployment shape".

---

## cs1 re-verification (PASS) — the container tier carries the env and the discriminator keys correctly

The env is present, grep-confirmed, in BOTH the anchor and the orchestrator tier, as literal
container paths (never a mount-source interpolation):

```bash
grep -n "FINOPS_REPO_DIR\|FINOPS_GIT_DIR\|FINOPS_RUNS_ROOT" infrastructure/docker-compose.ladder.yml | head
# x-ladder-env: FINOPS_REPO_DIR: /repo, FINOPS_GIT_DIR: /repo/.git, FINOPS_RUNS_ROOT: ${FINOPS_RUNS_ROOT:-/tmp/agentic-dynamics-runs}
# x-orchestrator-base: the same three, declared again explicitly
```

A container config derived from that env roots at `/repo` and the ws2 discriminator keys it into
the **host** view family (the family the broker validates its spawn requests against) — not the
legacy `/app` container view:

```bash
python3 - <<'PY'
import sys; sys.path[:0] = ['scripts/fleet','src']
from agentic_dynamics.core.paths import PathConfig
import spawn_wrapper, launch_broker
cfg = PathConfig.from_env({"FINOPS_REPO_DIR":"/repo","FINOPS_GIT_DIR":"/repo/.git",
    "FINOPS_WORKTREE_ROOT":"/tmp","FINOPS_RUNS_ROOT":"/tmp/agentic-dynamics-runs",
    "HOME":"/home/drseuss"}, require_existing=False)
print(cfg.repo_root, "->", spawn_wrapper.config_view(cfg))   # /repo -> host
legacy = launch_broker.container_view_config(cfg)
print(legacy.repo_root, "->", spawn_wrapper.config_view(legacy))  # /app -> container
PY
```

The f1(b) `_mounts_shared_surface` collision is fixed: the `repo_root` shared-surface check now
excludes the case `repo_root == REPO_TARGET` (`spawn_wrapper.py:463-468`), so a `/repo`-rooted
config's OWN `/repo` clone mount is no longer mis-flagged (verified in the cross section). **PASS.**

## cs2 re-verification (PASS) — the evidence is durable and re-derivable, never a `--rm` memory

The durable artifact loads through the harness's own round-trip validator and the container is
gone (the `--rm` happened, after persistence):

```bash
python3 - <<'PY'
import sys; sys.path[:0] = ['scripts/fleet','src']
from smoke_harness import load_evidence
ev = load_evidence('experiments/results/smoke/fleet_launch_container_smoke/20260903T142541Z.json')
print(ev['captured'], ev['container_id'], ev['image'], ev['exit_code'], ev['mount_proof'][0], ev['verdict'])
PY
# True 8001a5ae7d03… fleet/base 0 {'source': '/tmp/agentic-dynamics-runs/run-c43b5ae19ceb/repo',
#   'target': '/repo', 'rw': False} {'ok': True, 'state': 'succeeded', 'test_executed_success': True,
#   'tests_passed': 1, 'tests_total': 1, 'error': None}
docker inspect 8001a5ae7d032e20a464d614e7ed8de000342f1c24fe314934d1b5c10027d166
# [] error: no such object: 8001a5ae7d03…   (the cell was --rm'd; the evidence survived)
git -C /tmp/agentic-dynamics-runs/run-c43b5ae19ceb/repo rev-parse HEAD
# 88abcfbe4f9ae50f256327b787d5b7a21fdc4203   (the run clone is a real git repo)
```

The `RW=false` mount proof, the exit code, and the verdict are all in the file, written
structurally before the broker's `docker run --rm` removed the cell (`smoke_harness.py`'s
snapshot-before-launch-completes ordering, unit-proven in `test_smoke_harness.py`). **PASS.**

## cs3 re-verification (PASS, with F1 caveat) — the container-tier orchestrator drove a real cell

The evidence's `launch_context.shape` is "container-tier orchestrator (compose workflow-runner
service, cs1 env)", the image is `fleet/base`, and the mount proof names the shared runs root —
this is NOT a host-view replay. The underlying path re-derives: the container orchestrator
derives `repo_root=/repo` + `runs_root=/tmp/agentic-dynamics-runs`, the verifier request is
accepted by BOTH the client-side and broker-side validators when the broker is given the SAME
shared runs root (see the cross section), and the broker's argv mounts the clone read-only at
`/repo`. **PASS** — contingent on the broker carrying the same runs root, which the deployed
unit does not (F1).

---

## Cross — the f1 failure shape, both directions

**With the fixed env, a container CAN spawn through the broker.** The cs1+cs3 container config
builds a clone-world verifier request; both validations accept it and the broker dry-run launches
the read-only clone mount:

```bash
python3 - <<'PY'
import sys; sys.path[:0] = ['scripts/fleet','src']
from agentic_dynamics.core.paths import PathConfig
import spawn_wrapper, launch_broker
cont = PathConfig.from_env({"FINOPS_REPO_DIR":"/repo","FINOPS_GIT_DIR":"/repo/.git",
    "FINOPS_WORKTREE_ROOT":"/tmp","FINOPS_RUNS_ROOT":"/tmp/agentic-dynamics-runs",
    "HOME":"/home/drseuss"}, require_existing=False)
host = PathConfig.from_env({"FINOPS_REPO_DIR":"/tmp/wt_wave2","FINOPS_GIT_DIR":"/tmp/wt_wave2/.git",
    "FINOPS_WORKTREE_ROOT":"/tmp","FINOPS_RUNS_ROOT":"/tmp/agentic-dynamics-runs",
    "HOME":"/home/drseuss"}, require_existing=False)
clone = "/tmp/agentic-dynamics-runs/run-c43b5ae19ceb/repo"
req = spawn_wrapper.build_verifier_request({'name':'p5_test_gate','scope':'implementation','kind':'test'},
    goal='g', workdir='/repo', model='deepseek/deepseek-v4-flash', spec_name='cs3_smoke_cell',
    path_config=cont, run_clone=clone)
print("view:", req['view'], "mounts:", req['mounts'])              # host; clone ro at /repo
print("client:", spawn_wrapper.validate_spawn(req, phase_scopes={'p5_test_gate':'implementation'},
                                               path_config=cont))   # []  ACCEPTED
print("broker:", launch_broker.validate_launch_request(req, path_config=host))  # []  ACCEPTED
print(launch_broker.launch(req, dry_run=True, path_config=host)['argv'][:4])
# ['docker', 'run', '--rm', '-i'] … -v /tmp/agentic-dynamics-runs/run-c43b5ae19ceb/repo:/repo:ro …
PY
```

**Without the fix (the base tree `57774dfcb`), the discriminator refuses.** The SAME `/repo`-rooted
config under the pre-cs1 `_mounts_shared_surface` mis-flags the cell's own clone mount as the
shared surface, exactly as the `fleet_launch_smoke` review reproduced:

```bash
# (at the base commit 57774dfcb, a throwaway worktree)
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
for e in spawn_wrapper.validate_spawn(req, phase_scopes={'p1_slice1_base_supervisor':'implementation'},
                                       path_config=cfg): print(" -", e)
PY
#  - step 3: mount target '/repo' (source '.../run-xyz/repo') is the SHARED worktree/.git surface …
# => REFUSED
```

The same reproduction against `8ba3b056c` (HEAD) is `[]  ACCEPTED`. Both directions proven.

---

## Cross — parity suite + gate

```bash
python3 -m pytest tests/test_fleet_container_env.py tests/test_smoke_harness.py \
  tests/test_launch_broker.py tests/test_spawn_wrapper.py tests/test_path_config.py \
  tests/test_workflow_executor_parity.py tests/test_broker_hostside.py \
  tests/test_run_workflow_clone_wiring.py -q -p no:cacheprovider
# 235 passed, 1 skipped in 12.22s
python3 -m ruff check scripts/fleet/smoke_harness.py scripts/fleet/spawn_wrapper.py \
  scripts/fleet/broker_contract.py infrastructure/gen_launch_broker_service.py \
  tests/test_fleet_container_env.py tests/test_smoke_harness.py
# All checks passed!
```

Green, and the tests are substantive. Note the same caveat as the prior review: a bare green
suite is what the smoke exists to falsify. The suite stays green on F1 precisely because
`test_fleet_container_env.py` asserts `FINOPS_RUNS_ROOT` on the **compose** anchors only and no
test models the broker under its unit env.

---

## LOG

| Claim | Result |
|---|---|
| cs1 — the container tier (`x-ladder-env` + `x-orchestrator-base`) carries `FINOPS_REPO_DIR`/`FINOPS_GIT_DIR`/`FINOPS_RUNS_ROOT` | **PASS** — grep of `docker-compose.ladder.yml:59-60/:73/:213-214/:222`; literal container paths, no mount-source leak |
| cs1 — a container config derives `/repo` and the discriminator keys it to the broker-validated view | **PASS** — `config_view(/repo)=host`, `config_view(/app)=container`; the f1(b) `_mounts_shared_surface` collision is fixed (`spawn_wrapper.py:463-468`) |
| cs2 — the mount proof / exit code / verdict are DURABLE and re-derivable (never a `--rm` memory) | **PASS** — `load_evidence` round-trips; `docker inspect` → "no such object"; run clone `HEAD 88abcfbe4` on disk |
| cs3 — the evidence is CONTAINER-TIER (not a host replay) | **PASS** — `launch_context.shape` + `image fleet/base` + the shared-runs-root mount proof |
| cs3 — the container orchestrator spawns a cell end to end **in the real deployment shape** | **FAIL (partial)** — works with the broker on the shared runs root, but the deployed broker unit carries no `FINOPS_RUNS_ROOT` (defaults `/var/lib`) and refuses the container's clone (F1) |
| cross — with the fixed env the container CAN spawn; without it the discriminator refuses | **PASS** — HEAD `[] ACCEPTED` vs base `step 3 … SHARED surface` REFUSED, both reproduced |
| `campaign-wrapper` service boots | **FAIL** — `run_workflow.py --orchestrator` exits 2 (required args absent); crash-loops (F2) |
| cross — parity suite + gate green | **PASS** — 235 passed / 1 skipped; ruff clean |

## Release verdict

**NOT merge-ready to main.** The three `fleet_launch_smoke` findings are genuinely closed, and
the container-tier path WORKS end to end — that is a real, re-verified result: the env is
carried (cs1), the evidence is durable (cs2), and one real cell was driven by the compose
orchestrator container through the broker with the clone mounted read-only and the verdict
returned (cs3). But the wave's central claim is the *real deployment shape*, and in that shape
the host broker tier still derives `runs_root=/var/lib/agentic-dynamics/runs` (its unit carries
no `FINOPS_RUNS_ROOT`) while the container tier derives `/tmp/agentic-dynamics-runs` — so the
broker refuses the container's spawn exactly as the prior wave's orchestrator refused its own.
The smoke hid this by starting the broker with the ws4 override by hand. Required before merge:
carry `FINOPS_RUNS_ROOT` in the broker unit + generator (mirroring cs3's container fix) so no
tier derives its clone root differently, then re-verify the broker accepts a container-built
clone under its real unit env. F2 (`campaign-wrapper`) and F3 (agent-cell / submit path) are
recorded limitations, not blockers.
