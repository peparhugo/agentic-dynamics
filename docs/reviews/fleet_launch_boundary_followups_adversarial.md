---
status: accepted
kind: adversarial
spec: fleet_launch_boundary_followups
phase: fb4_adversarial
generated_at: 2026-09-03T03:00:00Z
---

# Adversarial review — `fleet_launch_boundary_followups` (fb4_adversarial)

**ROLE.** Independent adversarial reviewer (deepseek/deepseek-v4-pro, a separate session from
the flash author). The job is to *falsify* the follow-up wave, not certify it. Every claim
below was re-derived against the actual code at the fb3 tip (`360bd5901`), never asserted from
the author's prose. Findings are either **FIXED on the branch** or **RECORDED** as an accepted
limitation with reasoning.

**Verdict up front: NOT merge-ready.** Both of the wave's load-bearing security properties are
still unmet in the *reference execution path*, even though the contract layer for each is now
correct and green:

- **fb1 — the clone is still not wired into execution.** The clone-mount contract and its
  validation are real and tested, but `create_run_clone` has **zero production callers** and
  nothing exports `FINOPS_RUN_CLONE`; `run_workflow.py --orchestrator` constructs both
  executors *without* `run_clone`, so every cell in the actual ladder still mounts the shared
  `/tmp` rw + `/repo/.git` rw + host-path `.git` rw. Two concurrent cells still share git
  metadata. Hard rule 1 is not met. (Finding F1.)
- **fb2 — the containerized path is broken in a *new* way.** The seam is genuinely host-side
  and the socket is genuinely absent from every container, but the broker re-validates the
  wrapper's *container-built* mount list against its *host* `PathConfig`, and the two disagree
  on the D-16 repo-alias target (container defaults `repo_root` to `/app` because
  `FINOPS_REPO_DIR` is not set in the container env). The broker therefore **refuses every
  containerized agent/verifier spawn** at step 3 — "mount target '/app' is outside the
  four-mount contract". The containerized path does *not* "work again"; the round-trip smoke
  cannot see this because it runs serve() and the client in one process against one config.
  (Finding F2.)

fb3 (f4 docker-ps documentation + f6 prose) is closed cleanly; the surfaces regenerate
(`--check` green) and the full fb5 gate is green (397 passed / 1 skipped). The stragglers are
the part of this wave that is done.

---

## 1. Attack order and findings

| # | Target | Finding | Severity | Disposition |
|---|---|---|---|---|
| F1 | fb1 | the clone is never bound to execution — `create_run_clone` has no caller, `FINOPS_RUN_CLONE` is never exported, `run_workflow.py --orchestrator` builds both executors with no `run_clone`; cells still mount shared `/tmp` rw + `/repo/.git` rw + host-path `.git` rw, so two concurrent cells still share git metadata | HIGH | **RECORDED** (hard rule 1 unmet) |
| F2 | fb2 | the broker re-validates container-built mounts against the host `PathConfig`; the D-16 repo-alias target splits (`/app` in-container vs host path), so the broker **refuses every containerized spawn** at step 3 — the containerized path is still non-functional | HIGH | **RECORDED** (seam is real, config contract across it is broken) |
| F3 | fb3 | `scripts/archive/backfill_sonar.py:110` runs `docker run` — a third untyped docker caller outside the broker, not covered by the f4 exception; the new `agentic-dynamics-launch-broker.service` embeds the host literal `/home/drseuss/ai-finops-framework` | LOW | **NOTED** (out-of-scope / precedent) |

Three findings, each re-verified with code + a reproducible command. Details in attack order.

---

## 2. fb1 — can two concurrent cells still share git metadata? **F1: yes — RECORDED**

The review question is precise: *"can two concurrent cells share git metadata through ANY
remaining path (grep every mount the request builder can emit)? is the shared worktree/.git
truly absent from the cell contract?"* The answer is **no, the shared .git is not absent** —
it is absent only from the *clone-world* contract, which the reference path never enters.

**2a. The clone lifecycle is still unwired.** Re-grep at the tip for every production caller of
the lifecycle:

```bash
grep -rn "create_run_clone\|discard_run_clone\|sweep_stale_clones\|FINOPS_RUN_CLONE" \
  --include="*.py" scripts/ src/ | grep -v "def \|test_\|run_clone.py:" | grep -v "docker_executor\|docker_verifier"
# (only the module's own defs + the executor env-FALLBACK reads + the run_clone.py docstring)
```

`create_run_clone` / `discard_run_clone` / `sweep_stale_clones` are referenced **only** by
their own definitions and by unit tests. The two executor constructors *read*
`os.environ.get("FINOPS_RUN_CLONE")` (`docker_executor.py:74`,
`docker_verifier_executor.py:84`), but **nothing in the tree ever exports that variable**, and
nothing calls the create function. The preregistration's own deviation **D-fb-1** stated the
wiring "is part of the deliverable, not a precondition" — it was not done.

**2b. The reference path passes no clone.** `run_workflow.py:442-470` (the `--orchestrator`
composition root) constructs `DockerAgentExecutor(...)` and `DockerVerifierExecutor(...)` with
`spec_path/spec_name/goal/model/workdir/backend/timeout/cell_image` — **no `run_clone`
argument**. So `self._run_clone = run_clone or os.environ.get("FINOPS_RUN_CLONE")` resolves to
`None` in the real ladder.

**2c. With `run_clone = None`, `mounts_for_profile` still emits the shared-git surface.**
`build_phase_request` calls `mounts_for_profile(profile, run_clone=None)`, which takes the
pre-b2 non-clone branch (`broker_contract.py:298-323`) and emits exactly the surface the wave
exists to eliminate — re-dumped live at the tip:

```
  source=<worktrees_root=/tmp>   target=/tmp           mode=rw   # shared worktree namespace
  source=<results_dir>           target=/app/experiments/results mode=rw
  source=<repo_root>             target=/repo          mode=ro
  source=<git_dir>               target=/repo/.git     mode=rw   # SHARED git metadata, writable
  source=<repo_root>             target=<repo_root>     mode=ro   # D-16 host-path alias
  source=<git_dir>               target=<git_dir>       mode=rw   # SHARED host .git, writable
  … auth ro · state rw · credential ro
```

Two concurrent cells (two `docker run`s the broker launches) therefore mount the **same**
`git_dir` at `/repo/.git` **rw** and at its host path **rw** — the precise shared-writable-git
pattern the clone was meant to kill. `FIXED_CONTRACT_TARGETS` still declares `/tmp` rw and
`/repo/.git` rw (`spawn_wrapper.py:200-212`), and `contract_targets` still adds the host-path
`.git` rw alias — those are the *default* contract, and the default is what runs.

**2d. The clone-world contract itself is correct — it is just never engaged.** All five fb1
VERIFY (a)–(e) checks pass *when `run_clone` is supplied*: the repo mounts source from
`runs_root/<run-id>/repo`; the shared worktree/`.git` surface is absent; validation refuses a
clone-world request that would mount the shared `.git` (step 3 +
`_mounts_shared_surface`); two run ids produce distinct clone paths; the verifier is read-only
against its clone. `tests/test_spawn_wrapper.py:493-687` covers this thoroughly and green. The
defect is not in the contract — it is that no caller ever passes a `run_clone`, so the contract
is a dormant branch.

**Disposition: RECORDED.** Hard rule 1 ("every cell executes in its per-run clone … two
concurrent cells cannot share git metadata through any path") is not delivered in the
reference path. Closing it is a composition-root change (create the clone per run in
`run_workflow.py --orchestrator` / the submit path, thread it to both executors, discard after),
which the fb1 scope fence explicitly parked outside "the clone-mount contract + its validation".
The contract + validation are correct scaffolding; the execution isolation they were built to
provide is still not landed.

---

## 3. fb2 — does the containerized path ACTUALLY work again? **F2: no — RECORDED**

Three of the four sub-questions hold; the fourth does not.

**3a. Is the socket absent from every container? PASS.** `docker.sock` appears nowhere in
`infrastructure/` except absence-comments; `tests/test_fleet_guards.py:287` asserts "no service
mounts the docker socket" and `tests/test_broker_hostside.py:265` asserts the same — both green.
The only `.sock` mounted anywhere is the **seam** socket at
`/run/launch-broker.sock:ro` (`docker-compose.ladder.yml:164`), which is the typed IPC seam, not
the docker socket — and a `:ro` socket bind-mount still permits `connect()` (the entire
`/var/run/docker.sock:ro` industry pattern depends on it), so that is not a defect.

**3b. Can ANY in-container code reach docker? PASS (by construction, not by absence).** The
orchestrator image carries **no docker client** (`Containerfile.fleet:155-177` — the
socket-holder-era `docker-cli` install was removed in fb3). The only docker *subprocess* sites
in the runtime are `launch_broker.py` (host-side) and `system_snapshot.py:107` (documented
exception). The spawn path imports `broker_client`/`broker_contract`, never `launch_broker`;
`tests/test_broker_hostside.py:105` AST-verifies the in-process import is gone. `broker_client`
is stdlib-only and speaks the typed verb set. No in-container code path reaches a docker
daemon.

**3c. Is the IPC seam genuinely host-side? PASS.** The seam is real: `launch_broker.py:serve`
(`:552`) binds a unix socket, `serve_request` (`:430`) dispatches the closed verb set
(`launch|submit|fleet-command|ping`), every reply is a NAMED `state` (a refusal,
`DOCKER_UNAVAILABLE`, or `SERVER_ERROR` is a complete object, never a dropped connection).
`infrastructure/agentic-dynamics-launch-broker.service` runs `launch_broker.py serve` as a
systemd **user** unit (`WantedBy=default.target`, `NoNewPrivileges`, non-root). The broker
client round-trips the *real* `serve()` loop in the tests (`test_broker_hostside.py:134-194`).
This is not a pretend seam.

**3d. Does the containerized path actually spawn a cell? F2: NO — the broker refuses every
real spawn because the config splits across the seam.** This is the falsifying finding. Trace
the two configs:

- **Container side** (`workflow-runner` / `campaign-wrapper`): `FINOPS_REPO_DIR` is **not** in
  the container env (`x-ladder-env` / `x-orchestrator-base` carry `HOME`, `OPENCODE_BIN`, the
  Redis/proxy vars — no `FINOPS_REPO_DIR`). So the wrapper's `PathConfig.from_env()` defaults
  `repo_root` to `PROJECT_ROOT` — the package root **inside the image, `/app`**
  (`paths.py:192`). `build_phase_request` therefore builds the request's `mounts` with the D-16
  repo-alias targets `/app` and `/app/.git`.
- **Host side** (the broker): `default_path_config()` reads the operator's host env
  (`FINOPS_REPO_DIR=/home/drseuss/ai-finops-framework`), so `contract_targets(host_cfg)` keys the
  D-16 alias at the **host path**, not `/app`.

`launch()` then runs `spawn_wrapper.validate_spawn(request, path_config=host_cfg)`
(`launch_broker.py:216-224`), and `validate_spawn` step 3 checks every mount in the
request's `mounts` against the **host** contract (`spawn_wrapper.py:500-501, 546-615`). The
`/app` and `/app/.git` alias targets are not in the host contract, so step 3 fails.

Reproduced against the actual code (not asserted):

```
container config: repo_root=/app, git_dir=/app/.git   (the image's PROJECT_ROOT)
host config:      repo_root=/home/drseuss/ai-finops-framework, git_dir=…/.git

client-side validate_spawn(container cfg) -> NONE (valid)
broker-side validate_spawn(host cfg)     ->
  "step 3: mount target '/app' is outside the four-mount contract + the D-2 auth set"
  "step 3: mount target '/app/.git' is outside the four-mount contract + the D-2 auth set"
```

The verifier request fails the same way (its non-clone candidate surface also carries the
`/app` repo-alias). So the broker — correctly validating what it will execute — **refuses every
containerized agent and verifier spawn**. The containerized path is still non-functional, just
broken at the seam's validation instead of at a missing socket. The smoke cannot see it because
`test_broker_hostside.py` runs `serve()` and the client in one process against **one** scratch
config — there is no host/container split to expose.

**Disposition: RECORDED.** The seam and the host-side broker are genuinely landed, but the
config contract *across* the seam is broken: the container never learns the host's
`FINOPS_REPO_DIR`/`FINOPS_GIT_DIR`, so the D-16 alias it emits (`/app`) is refused by the host
broker. The remediation is to set `FINOPS_REPO_DIR`/`FINOPS_GIT_DIR` in the orchestrator
container env (env-derived, fail-closed — a path, not a literal) so both sides of the seam
derive the same repo-alias target, or to have the broker re-derive the mounts without
re-validating the client's host-path-dependent D-16 alias. Until one of those lands, "the
containerized path WORKS again" is false.

---

## 4. fb3 — is system_snapshot's docker usage closed, and is the prose clean?

**4a. f4 (system_snapshot docker ps) — CLOSED.** The `docker ps` call is now a named,
documented function `_chromadb_docker_ps()` (`system_snapshot.py:93-109`) with a docstring
recording the ONE benign read-only exception and the reason it is *not* broker-routed (the seam
serves launch/submit/fleet verbs, not status queries; the supervisor tier mounts no seam
socket). The module docstring (`:18-31`) carries the same record. This satisfies the spec's
"route it OR document it as a benign read-only exception with the reason" branch.

**4b. f6 (stale prose) — CLEAN.** The pre-b3 "socket-holder" phrasing is gone from every live
surface. The remaining `docker.sock` matches are all *correct* broker-era prose ("no service
mounts the docker socket — it lives only in the host-side launch broker"). The
socket-holder-era `docker-cli` install was removed from the Containerfile. The rendered
surfaces regenerate cleanly:

```bash
python3 scripts/_gen_instructions.py --check   # "surfaces OK — 36 generated files match agent_config/"
```

`tests/test_system_snapshot.py:56-208` guards the F6 phrases (asserting they are *absent* from
the Containerfile, agent_config sources, and rendered surfaces) — green.

**4c. F3 (stragglers beyond f4/f6) — NOTED, LOW.** Two residuals:

1. `scripts/archive/backfill_sonar.py:110` runs `docker run --rm sonarsource/sonar-scanner-cli`
   — a *third* untyped docker caller outside the broker, and outside the f4 documentation
   (which names only `system_snapshot.py`'s `docker ps`). It is an archived one-time migration,
   host-side, never a fleet container — so it does not violate "no in-container code calls
   docker" — but the ONLY-caller rule's prose ("the fleet's ONLY Docker API caller … its one
   documented exception") is now strictly incomplete. Out of scope for this wave (not part of
   the fleet launch boundary); noted for the next broker-documentation sweep.
2. `infrastructure/agentic-dynamics-launch-broker.service` embeds the host literal
   `/home/drseuss/ai-finops-framework` in `Documentation=`, `WorkingDirectory=`, and
   `Environment=REPO=` (`:43,55-56`). This is a **new** host-specific literal introduced by
   fb2 — the same pattern the original review's §6 already flagged on
   `fleet-bootstrap.service` / `docs-drift-scan` units. A systemd user unit is inherently a
   host-local artifact (the install block says "Update REPO if the framework lives elsewhere"),
   so this is LOW and precedent-consistent, not a b1 violation (b1's surface was
   spawn_wrapper/compose/tests).

---

## 5. Re-verification evidence (the full gate)

```bash
python3 -m pytest \
  tests/test_launch_broker.py tests/test_path_config.py tests/test_spawn_wrapper.py \
  tests/test_workflow_executor_parity.py tests/test_workflow_runner.py \
  tests/test_system_snapshot.py tests/test_script_classification.py \
  tests/test_doc_lifecycle.py tests/test_agent_config_render.py \
  tests/test_cli_resolution.py -q -p no:cacheprovider
# 397 passed, 1 skipped
```

The fb5 gate is green; the pin holds (`8f953b36…`); the surfaces regenerate cleanly. The
failure is not in the tests — it is that the tests prove a *dormant* clone contract (F1) and a
seam whose cross-boundary config contract is never exercised by a real two-process split (F2).

---

## 6. Verdict

**NOT merge-ready to main.**

What is real and correct: the clone-mount contract + its validation (fb1), the genuinely
host-side broker unit + a real unix-socket seam + the in-process import's removal + the
socket's absence from every container (fb2 scaffolding), the f4 documentation and the f6 prose
sweep with clean regeneration (fb3), and the parity + gate suites staying green.

What is not: hard rule 1 — cells still execute in shared worktrees with a writable shared
`.git`, because the clone is never created or threaded (F1). Hard rule 2's "the containerized
path WORKS again" — the host broker refuses every containerized spawn because the wrapper and
the broker derive their repo-alias contract from different configs across the seam (F2). The
follow-up wave closed the *contract* layer of both half-deliveries but not the *execution*
layer; the two properties the wave exists to establish are still not present in the reference
path.

Recommended disposition: do not merge as a completed security wave. Either (a) accept F1/F2 as
recorded, deferred work — the clone wiring and the cross-seam config contract are the next
wave's first two items — or (b) return the branch to authoring for those two closures before it
is considered merge-ready.

---

## 7. LOG — PASS/FAIL per claim

| Claim | Attempts | Result |
|---|---|---|
| fb1 — clone-mount contract + validation correct (repo sources from clone; shared .git refused; two ids distinct; verifier ro) | 1 | **PASS** — `broker_contract.mounts_for_profile:256-296`, `spawn_wrapper.validate_spawn:546-624`; `test_spawn_wrapper.py:493-687` green |
| fb1 — clone wired into execution (create + thread + discard) | 1 | **FAIL** — `create_run_clone` has no production caller; `FINOPS_RUN_CLONE` never exported; `run_workflow.py:450-469` passes no `run_clone` |
| fb1 — shared .git absent from the *default* cell contract | 1 | **FAIL** — non-clone branch still mounts `/tmp` rw + `/repo/.git` rw + host-path `.git` rw (`broker_contract.py:298-311`; `FIXED_CONTRACT_TARGETS:200-212`) |
| fb2 — socket absent from every container | 1 | **PASS** — no `docker.sock` in `infrastructure/`; seam socket only, orchestrator tier only (`compose:164`; `test_fleet_guards.py:287/317`) |
| fb2 — no in-container code reaches docker | 1 | **PASS** — no docker client in the image; only `launch_broker` (host) + documented `system_snapshot` call docker |
| fb2 — seam genuinely host-side | 1 | **PASS** — systemd user unit runs `launch_broker.py serve`; real `serve()`/client round-trip in tests |
| fb2 — containerized path actually works (real spawn through the broker) | 1 | **FAIL** — broker re-validates container-built `/app` alias mounts against host config and refuses every spawn (reproduced) |
| fb3 — system_snapshot docker usage closed | 1 | **PASS** — `_chromadb_docker_ps` documented as the ONE benign read-only exception |
| fb3 — prose clean + surfaces regenerate | 1 | **PASS** — `_gen_instructions.py --check` green; `test_system_snapshot.py` F6 guard green |
| gate — full fb5 suite | 1 | **PASS** — 397 passed, 1 skipped |
| pin integrity — spec SHA | 1 | **PASS** — `8f953b36…` unchanged |
