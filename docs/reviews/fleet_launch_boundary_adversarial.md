---
status: accepted
kind: adversarial
spec: fleet_launch_boundary
phase: b4_adversarial
generated_at: 2026-09-02T23:47:27Z
---

# Adversarial review — `fleet_launch_boundary` (b4_adversarial)

**ROLE.** Independent adversarial reviewer (pro model, separate session from the flash author).
The job here is to *falsify* the Wave-2 launch-boundary, not certify it. Every claim below was
re-derived against the actual code at `20ef11f94` (the b3 tip), never asserted from the author's
prose. Findings are either **FIXED on the branch** or **RECORDED** as an accepted limitation
with reasoning.

**Verdict up front: NOT merge-ready.** Two of the wave's four hard rules are unmet at the tip:
hard rule 3 (private clone per run / no shared git metadata) is not implemented — the clone
lifecycle exists but is never bound to execution; and the "host-side" half of hard rule 1 (the
broker is the *only* Docker API caller, running host-side) is not wired — the wrapper calls the
broker in-process inside the now-socketless orchestrator container. The socket *did* leave the
container, and the typed-request discipline *is* real, but the wave lands scaffolding, not the
two security properties it exists to establish.

---

## 1. Attack order and findings

| # | Target | Finding | Severity | Disposition |
|---|---|---|---|---|
| F1 | b1 | host-specific literals remained in `infrastructure/docker-compose.ladder.yml` (env defaults, `HOME`/bin env, mount targets) — the one surface the b1 mandate names | HIGH | **FIXED** (env-derived, fail-closed) |
| F2 | b2 | the per-run clone is created/discarded but **never mounted**; cells still execute in shared worktrees (`/tmp` rw) with the shared `.git` rw — two concurrent cells still share git metadata | HIGH | **RECORDED** (hard rule 3 unmet) |
| F3 | b3 | the broker is **not deployed host-side** — the wrapper imports it and calls it in-process; no IPC seam; with the socket removed the in-container `docker` call fails | HIGH | **RECORDED** (launch path broken) |
| F4 | b3 | `scripts/system_snapshot.py:175` runs `docker ps` — a second Docker API caller outside the broker | LOW | **RECORDED** (benign read-only) |
| F5 | b5 gate | the gate's `tests:` list names `tests/test_docker_executor.py`, which does not exist | MEDIUM | **RECORDED** (gate will fail) |
| F6 | cross | stale prose still describes the pre-b3 socket-holder state (Containerfile + agent surfaces) | LOW | **NOTED** (docs drift) |

Six findings — a bare PASS would have been a failed review. Details follow, in attack order.

---

## 2. b1 — does ANY host-specific path literal remain? **F1: yes → FIXED**

The b1 mandate is explicit: "the hard-coded `/home/drseuss/ai-finops-framework` contract dies
from **spawn_wrapper/compose/tests**". The preregistration's own D-1 deviation flagged the
compose `:-` defaults as "part of the same contract and must die with it".

Sweep at the tip (before this review's fix):

```bash
grep -rn "home/drseuss" scripts/fleet/ infrastructure/docker-compose.ladder.yml tests/
# scripts/fleet/              -> (none — spawn_wrapper clean, b1 adopted)
# infrastructure/docker-compose.ladder.yml -> 45/46/47 (HOME/OPENCODE_BIN/CLAUDE_BIN),
#   70/73/74/94/97/98/135/138/139 (${FINOPS_REPO_DIR:-/home/drseuss/ai-finops-framework}),
#   81-89/100-103/145-150 (${AUTH_HOME:-/home/drseuss}/… + target paths /home/drseuss/.claude etc.)
# tests/                      -> test_subscription_usage_api.py:87 (unrelated subsystem, see §6)
```

`spawn_wrapper.py` and the fleet tests were correctly swept (the `CONTRACT_TARGETS` host-literal
contract is gone, replaced by `PathConfig`-derived `contract_targets(path_config)` at
`spawn_wrapper.py:208`). But the **compose file — the surface the mandate names — still carried
the host literal as an env-interpolation DEFAULT and as fixed container env/mount-target
values.** That ties the ladder to one host identity, exactly the contract b1 exists to kill.

**FIX (this review).** Every host literal in the compose is now env-derived, with fail-closed
`:?` forms on the sources (no host-specific fallback):

- `HOME: /home/drseuss` → `HOME: ${AUTH_HOME}`; `OPENCODE_BIN` / `CLAUDE_BIN` derived from `${AUTH_HOME}`.
- `${FINOPS_REPO_DIR:-/home/drseuss/ai-finops-framework}` → `${FINOPS_REPO_DIR:?…}` (9 sites).
- `${AUTH_HOME:-/home/drseuss}` → `${AUTH_HOME:?…}` (all sites).
- D-16 alias targets `/home/drseuss/ai-finops-framework` → `${FINOPS_REPO_DIR}`; auth targets → `${AUTH_HOME}/…`.

**Re-verification (both directions):**

```bash
grep -rn "home/drseuss" infrastructure/docker-compose.ladder.yml   # (empty)
FINOPS_REPO_DIR=/home/drseuss/ai-finops-framework AUTH_HOME=/home/drseuss \
  docker-compose -f infrastructure/docker-compose.ladder.yml config   # exit 0
# rendered config reproduces the pre-fix mounts byte-for-byte — behavior-preserving when env is set.
```

The one remaining `:-` default, `${FINOPS_REPO_DIR:-..}/experiments/results`, is a *relative*
(`..`) fallback, not a host literal — left as-is.

---

## 3. b2 — can two concurrent runs share git metadata? **F2: yes, still — RECORDED**

Hard rule 3: "a cell executes in its own ephemeral clone … never in a shared worktree with a
writable shared .git. Two concurrent cells never share git metadata."

`run_clone.py` delivers the lifecycle (create with `--no-hardlinks`, refuse reuse, verify head,
discard idempotently, sweep stale) and the request *reference* is threaded through
`build_phase_request`/`build_verifier_request` → `run_clone`. **But the clone is never bound to
execution.** The broker's own profile expansion says so, in code:

- `launch_broker.py:240-241` — `run_clone` "is deliberately **NOT yet mounted**: binding the
  per-run clone as the cell's execution surface is a clone-execution change … which b3's scope
  fence defers".
- `launch_broker.py:159` — the `run_clone` field "does not mount it yet".

And the shared-git surface the clone was meant to replace is still emitted by
`mounts_for_profile` for every agent cell (`launch_broker.py:270-281`):

```
270  {"source": worktrees_root, "target": "/tmp",           "mode": "rw"}   # shared worktree namespace
273  {"source": git_dir,        "target": "/repo/.git",      "mode": "rw"}   # shared gitdir overlay
281  {"source": git_dir,        "target": <git_dir host path>, "mode": "rw"} # D-16 host-path .git
```

So a cell still commits into `/tmp/<shared-worktree>` with the repo's `.git` (and the D-16
host-path `.git`) mounted **rw** — the precise shared-writable-git pattern the wave exists to
eliminate. Two concurrent cells still read/write the same git metadata. The b2 scope fence
delegated the mount to b3, and b3's fence said "no clone changes beyond what b2 already did" —
**no phase owns the mount.** Hard rule 3 is unmet.

**RECORDED** (not fixed): binding the clone as the cell surface is a real change (clone mount
profile, cell workdir/commit path into the clone, the promoter consuming the clone's candidate
sha) and is the subject of a follow-on wave, not a drive-by reviewer fix. The clone lifecycle +
reference are correct scaffolding; the execution isolation they were built to provide is not yet
landed.

---

## 4. b3 — can the broker be bypassed / does an arbitrary docker command reach the engine?

### 4a. Is the socket really absent from every container? **PASS**

```bash
grep -rn "docker.sock" infrastructure/   # (empty — all compose files)
```

The `- /var/run/docker.sock:/var/run/docker.sock:ro` orchestrator mount is removed. The broker's
own process runs host-side (no container mounts a socket into it). **This half of hard rule 1 holds.**

### 4b. Is the broker the only docker caller, reachable only host-side? **F3: no — RECORDED**

The broker module is the *only* docker **launcher** (`launch_broker.py` is the sole `docker run`/
`docker compose` site in the runtime). But it is **not actually a host-side process**. The
wrapper reaches it **in-process** — a plain import + function call, not IPC:

```bash
grep -n "launch_broker.launch\|launch_broker.submit_run\|launch_broker.run_fleet_command" scripts/fleet/spawn_wrapper.py
# 837  return launch_broker.launch(...)              (spawn_sibling)
# 1171 return launch_broker.submit_run(...)          (dispatch_submit)
# 1335 outcome = launch_broker.run_fleet_command(...) (consume_fleet_commands)
```

`launch_broker.main()` provides a host-side CLI, but **nothing invokes it**: no systemd unit, no
compose service, no subprocess seam from the wrapper. The `campaign-wrapper` / `workflow-runner`
services are still defined as containers (`docker-compose.ladder.yml:300-312`), now *without*
the socket — so when the wrapper calls `launch_broker.launch` in-process there, the broker's
`subprocess.run(["docker", …])` runs **inside a socketless container** and fails. The socket left
the container, but nothing was put in its place: the reference execution path cannot actually
spawn a sibling cell. Hard rule 1's "host-side broker is the ONLY Docker API caller" is half-true
(the broker is the only caller; it is not host-side).

**RECORDED** (not fixed): making the broker a true host-side process requires an IPC seam
(a Redis/HTTP/unix-socket channel the wrapper speaks, the broker serves) plus re-homing the
orchestrator tier — a deployment change, not a reviewer patch.

### 4c. A second docker caller (read-only) — **F4: RECORDED**

`scripts/system_snapshot.py:175` runs `docker ps --filter name=chromadb` directly, outside the
broker. It is read-only (status query, best-effort `_sh` that swallows a missing socket) and
predates the wave, so it is not a launch-path escape — but it is a second Docker API caller, and
`docker ps` in a socketless container simply returns empty. Recorded as a benign, out-of-scope
seam to be folded into the broker (or dropped) when the broker deployment lands.

---

## 5. cross — do the executors still produce the same verdicts? **PASS**

Parity suite green (the b5-gate-relevant families, run at the tip):

```bash
python3 -m pytest tests/test_path_config.py tests/test_run_clone.py tests/test_launch_broker.py -q   # 50 passed
python3 -m pytest tests/test_spawn_wrapper.py tests/test_fleet_guards.py tests/test_workflow_executor_parity.py -q   # 155 passed, 1 skipped
python3 -m pytest tests/test_script_classification.py tests/test_doc_lifecycle.py tests/test_agent_config_render.py tests/test_cli_resolution.py -q   # 118 passed
```

`test_workflow_executor_parity.py` (the executor → envelope → classify round-trip) stays green:
the `DockerAgentExecutor`/`DockerVerifierExecutor` verdicts are unchanged by the typed-request
refactor, satisfying the cross check.

**F5 — the harness gate is broken, though (RECORDED).** The spec's b5 `tests:` list names
`tests/test_docker_executor.py`, which does not exist (never on `main`, never in the tree):

```bash
git ls-files | grep -i docker_exec   # scripts/fleet/docker_executor.py  (no tests/test_docker_executor.py)
```

The executor's real coverage lives in `tests/test_workflow_executor_parity.py` (already in the
list). A `pytest tests/test_docker_executor.py` invocation exits 4 (file-not-found), so the
b5_test_gate phase will **fail** — not on a verdict, but on a phantom file. Recorded, not fixed:
the spec was SHA-pinned in b0, and editing it would break the pin (a reportable deviation). The
gate should drop the phantom file; the coverage is already present.

---

## 6. Other surfaces (noted, not load-bearing)

- **Docs drift (F6).** `Containerfile.fleet:154-155` still reads "the orchestrator is the ONE
  socket-holder (D-3): it mounts `/var/run/docker.sock ro`"; `agent_config/rules.md` +
  `agent_config/skills/run-workflow.md` (+ their rendered `AGENTS.md` / skill surfaces) still
  state "the socket lives in exactly one tier" and "the container mounts the docker socket
  (ro)". All are now false. Regenerate from `agent_config/` when the source is corrected.
- **`tests/test_subscription_usage_api.py:87`** carries `/home/drseuss/.local/share/opencode/opencode.db`
  as a sample path — a host literal in a test, but for the subscription-usage subsystem, not the
  fleet path contract. Out of scope; noted.
- **`infrastructure/fleet-bootstrap.service`** and the docs-drift systemd units still embed the
  host repo path (`REPO=/home/drseuss/ai-finops-framework`). These are host-side bootstrap/admin
  units (the operator's own host footprint), outside the b1 "spawn_wrapper/compose/tests"
  surface; flagged for the same env-derivation treatment.

---

## 7. Verdict

**NOT merge-ready to main.**

What is real and correct: PathConfig (`b1`), the clone lifecycle + sweep (`b2` scaffolding), the
typed `LaunchRequest` + shared wrapper/broker validation + the socket's removal from every
container (`b3` scaffolding), and the parity suite staying green.

What is not: hard rule 3 — cells still execute in shared worktrees with a writable shared
`.git`; the clone is never mounted (F2). Hard rule 1's host-side broker — the socket left the
container but the broker is called in-process inside the socketless container, so no sibling can
actually be spawned (F3). The compose host-literal (F1) is now fixed on this branch, but F2/F3
are the wave's load-bearing security properties and they are not yet delivered.

Recommended disposition: land the F1 fix now (it closes a hard-rule-2 gap on an explicitly
named surface), then either (a) accept F2/F3 as recorded, deferred work and *do not* merge as a
completed security wave, or (b) return the wave to authoring for the clone mount + broker
deployment before this branch is considered merge-ready.

---

## 8. LOG — PASS/FAIL per claim

| Claim | Attempts | Result |
|---|---|---|
| b1 — host literal swept from spawn_wrapper | 1 | **PASS** — `scripts/fleet/` clean |
| b1 — host literal swept from compose | 2 | **FAIL→FIXED** — `docker-compose.ladder.yml` carried 20+ `/home/drseuss` sites; now env-derived (`docker-compose config` exit 0, renders identically) |
| b1 — host literal swept from tests | 1 | **PASS (fleet)** — `test_spawn_wrapper.py`/`test_fleet_guards.py` clean; unrelated `test_subscription_usage_api.py:87` noted |
| b2 — clone truly per-run and discarded | 1 | **PASS (lifecycle)** — `run_clone.py` create/discard/sweep + tests |
| b2 — cells execute in the clone, no shared git | 1 | **FAIL** — `mounts_for_profile` still mounts `/tmp` rw + `/repo/.git` rw + host-path `.git` rw; clone "deliberately NOT yet mounted" (`launch_broker.py:240`) |
| b3 — socket absent from every container | 1 | **PASS** — no `docker.sock` in `infrastructure/` |
| b3 — broker is the only docker caller | 1 | **PASS (launch)** — only `launch_broker.py` runs `docker run`/`docker compose` |
| b3 — broker is host-side / no bypass | 1 | **FAIL** — wrapper calls broker in-process (`spawn_wrapper.py:837/1171/1335`); no IPC seam; in-container docker call fails |
| b3 — no other docker caller | 1 | **FAIL (minor)** — `system_snapshot.py:175` `docker ps` (read-only) |
| cross — parity suite green | 1 | **PASS** — 50 + 155(1 skip) + 118 passed |
| b5 gate — test list resolvable | 1 | **FAIL** — `tests/test_docker_executor.py` missing |
