---
status: accepted
kind: preregistration
spec: fleet_launch_boundary
phase: b0_pin_spec
run: run-a8cd0180841c
generated_at: 2026-09-02T22:33:17Z
---

# Preregistration — `fleet_launch_boundary` (b0_pin_spec)

**The house pin convention.** This document is written BEFORE any implementation phase of the
wave executes (`b1_path_config`, `b2_ephemeral_clone`, `b3_launch_broker`). Its purpose is
twofold, and both halves are load-bearing:

1. **Anchor the run to exact bytes.** A workflow spec is a mutable file. Recording the spec's
   SHA256 makes the mandate immutable *by reference*: any divergence is detectable by re-running
   one command.
2. **Verify the three launch-boundary edges, do not assert them.** The gaps this wave exists to
   close are stated as current-state claims in the spec's question/current_state (authored
   2026-09-02): (1) the orchestrator container mounts the Docker socket and the spawn wrapper
   invokes docker itself; (2) `/home/drseuss/ai-finops-framework` literals live in
   `spawn_wrapper.py` and the tests; (3) cells execute in shared host worktrees with the repo's
   `.git` mounted rw via the overlay. Each edge is re-derived below against the ACTUAL code at
   the pin (read by absolute path at the MAIN checkout, `/home/drseuss/ai-finops-framework`), and
   the command that produced the evidence is recorded so a reader can reproduce every finding
   without trusting this document. An edge that does not hold is a FAILED finding — recorded as a
   deviation below, never smoothed over.

The three edges are verified below against the state at launch.

---

## 1. The pin

| Field | Value |
|---|---|
| Spec path | `workflows/repository/fleet_launch_boundary.yaml` |
| Spec **SHA256** | `c83a03ab8c140d24ee11b5a988ff0559091df0ff545491085dd2a472b98d0439` |
| Spec size | 17,470 bytes |
| Worktree HEAD (git sha) | `6eee5cea131447f7e6dfa78b1865ccef136fcc3a` |
| HEAD subject | `rebuild data.js (workflow_specs 172) after the fleet_launch_boundary spec-add` |
| Worktree | `/tmp/wt_wave2` — detached `HEAD` at the spec-add tip (gitdir `/home/drseuss/ai-finops-framework/.git/worktrees/wt_wave2`) |
| Main checkout | `/home/drseuss/ai-finops-framework` — branch `main`, SAME tree (`6eee5cea1`) |
| Working tree | clean except modified `run.log` (a runner artifact, not a source file) |
| Control run | `run-a8cd0180841c` — `fleet_launch_boundary`, `state: running`, `model: deepseek/deepseek-v4-flash`, started `2026-09-02T22:29:56.898614Z` (this run) |
| Control db | `/home/drseuss/ai-finops-framework/experiments/results/control/control.db` (machine-local, gitignored), `schema_version: 4`, `control_epoch: 57` |
| Pinned at | 2026-09-02T22:33:17Z |

The spec file is byte-identical in both trees (the pin was taken from the MAIN checkout, per the
DB-location rule; the worktree copy matches):

```bash
sha256sum workflows/repository/fleet_launch_boundary.yaml   # run at the MAIN checkout
# c83a03ab8c140d24ee11b5a988ff0559091df0ff545491085dd2a472b98d0439
git rev-parse HEAD          # (in the worktree)
# 6eee5cea131447f7e6dfa78b1865ccef136fcc3a
```

If either value differs when `b4_adversarial` (or `b5_test_gate`) runs, the spec was edited
mid-run and the mandate this document pins is no longer the mandate being executed — a
reportable finding in itself.

**Spec shape at the pin** — six phases (five `kind: agent` + one `kind: test`):

| # | Phase | kind | scope | notes |
|---|---|---|---|---|
| 0 | `b0_pin_spec` | agent | `implementation` | **this phase** — the preregistration |
| 1 | `b1_path_config` | agent | `implementation` | ONE typed PathConfig object; the host literals die |
| 2 | `b2_ephemeral_clone` | agent | `implementation` | private clone per run at runs_root/<run-id>/repo |
| 3 | `b3_launch_broker` | agent | `implementation` | the socket leaves the container; typed LaunchRequest only |
| 4 | `b4_adversarial` | agent | `adversarial_readonly` | independent pro reviewer (requires_deliverable) |
| 5 | `b5_test_gate` | test | `implementation` | the harness gate suite |

---

## 2. Verified current-state edges (the three launch-boundary gaps)

Each edge is stated as the spec's mandate states it, then **independently derived** against the
code at `6eee5cea1…` (read at the MAIN checkout, `/home/drseuss/ai-finops-framework`). No
finding was accepted on the spec's authority.

**Verdict legend.** **PASS** — the claimed edge holds at the pin, with code/command evidence.
**FAILED (deviation)** — the claimed edge does not hold as stated; the deviation is recorded and
the true state proven. In a pin phase, a FAILED sub-edge is not a wave failure — it is the
correction that makes the implementation phases target the real state.

### Edge 1 — the socket is mounted into a container AND `spawn_wrapper` invokes docker directly. **PASS**

**1a. The compose line.** The orchestrator tier mounts the Docker socket. Read the anchor, then
the socket line:

```bash
sed -n '121,146p' infrastructure/docker-compose.ladder.yml
# 121  # The orchestrator tier (slice 2, D-3/D-14/D-16): the cell mount set PLUS the docker socket
# 126  x-orchestrator-mounts: &orchestrator-mounts
# 144    - /var/run/docker.sock:/var/run/docker.sock:ro
grep -n "x-orchestrator-base\|campaign-wrapper:\|workflow-runner:\|socket-holder" infrastructure/docker-compose.ladder.yml
# 146  x-orchestrator-base: &orchestrator-base      (volumes: *orchestrator-mounts)
# 291  # socket-holder tier (D-3): /var/run/docker.sock ro, gated by the spawn-wrapper.
# 293  campaign-wrapper:      <<: *orchestrator-base
# 299  workflow-runner:       <<: *orchestrator-base
```

`x-orchestrator-mounts` (`:126-144`) is consumed by `x-orchestrator-base` (`:146-155`), which the
two socket-holding services extend: `campaign-wrapper` (`:293`) and `workflow-runner` (`:299`).
The socket mount is `infrastructure/docker-compose.ladder.yml:144` —
`/var/run/docker.sock:/var/run/docker.sock:ro`. The `:ro` filesystem flag does not constrain
Docker API authority — the mount makes the whole Docker Engine control surface reachable from
inside those containers.

**1b. The subprocess call.** `spawn_wrapper.py` invokes docker directly — `subprocess.run` over
an argv it builds, in the sibling-spawn and submit paths:

```bash
grep -n "subprocess.run\|argv = \[docker\|argv = \[compose" scripts/fleet/spawn_wrapper.py
# 699   argv = [docker, "run", "--rm", "-i"]            # build_spawn_argv
# 744   proc = subprocess.run(argv, capture_output=True, text=True)   # spawn_sibling
# 1012  argv = [compose, "-f", compose_file, "run", "--rm"]           # build_submit_argv
# 1056  proc = subprocess.run(argv, capture_output=True, text=True)   # dispatch_submit
# 1212  argv = [compose, "-f", compose_file, "up", "-d", "--scale",   # consume_fleet_commands
# 1224  proc = subprocess.run(argv, check=False)
```

`build_spawn_argv` (`spawn_wrapper.py:693-711`) assembles `docker run --rm -i` with the
request's `-v`/`--network`/`-e` flags; `spawn_sibling` (`:715`) runs it via
`subprocess.run` at `:744`. `build_submit_argv` (`:986`) assembles
`docker compose -f docker-compose.ladder.yml run --rm workflow-runner …` and `dispatch_submit`
(`:1030`) runs it via `subprocess.run` at `:1056`. The live BRPOP consumer
(`consume_fleet_commands`, `:1128`) additionally drives `docker compose up/stop/restart`
(`:1212-1217`) via `subprocess.run` at `:1224`. The module docstring states the design
(`:26-30`, `:30`): "spawn_sibling — validate_spawn THEN build/run the ``docker run`` sibling
command … resize/drain/restart/submit commands to ``docker compose``" — i.e. one trusted module
both validates and invokes arbitrary docker CLI commands. `docker-compose.ladder.yml:144` +
`spawn_wrapper.py:699/744` confirm both halves of the edge.

### Edge 2 — `/home/drseuss/ai-finops-framework` literals exist in `spawn_wrapper.py` + the tests. **PASS**

```bash
grep -rn --include="*.py" "home/drseuss/ai-finops-framework" \
  scripts/fleet/spawn_wrapper.py tests/
# scripts/fleet/spawn_wrapper.py:138   #: /home/drseuss/ai-finops-framework/.git/...). Without this mount the pointer does not
# scripts/fleet/spawn_wrapper.py:142   "/home/drseuss/ai-finops-framework": ("repo-alias", "ro"),
# scripts/fleet/spawn_wrapper.py:143   "/home/drseuss/ai-finops-framework/.git": ("repo-alias-git", "rw"),
# tests/test_spawn_wrapper.py:50       _CANONICAL_REPO_DIR = "/home/drseuss/ai-finops-framework"
# tests/test_workflow_executor_parity.py:996  # construction). Run it from the MAIN checkout (``/home/drseuss/ai-finops-framework`` — the
```

The `CONTRACT_TARGETS` mount map (`spawn_wrapper.py:124-151`) hard-codes the repo's host path as
the **contract keys** for the D-16 repo-alias mounts (`:142-143`, modes `ro`/`rw`). The host-home
auth set `AUTH_DIRS` (`:98-101`) hard-codes `/home/drseuss/.claude`, `/home/drseuss/.local/bin`,
`/home/drseuss/.local/share/claude`, `/home/drseuss/.opencode/bin`, and `build_phase_request`
defaults `auth_home` to `/home/drseuss` (`:822`). The tests encode the same host path: the
spawn-contract suite pins `FINOPS_REPO_DIR` to the canonical literal
(`tests/test_spawn_wrapper.py:50`, documented `:45-54`) and asserts the host-home auth targets
(`:83-86`, `:153-154`); `tests/test_fleet_guards.py:122-124`/`:462` carry the same host-home
paths; `tests/test_workflow_executor_parity.py:996` references the checkout path in a docstring.
First-hand confirmation — import the module and dump the contract (run at the MAIN checkout):

```python
from scripts.fleet import spawn_wrapper as sw
for k, (cat, mode) in sw.CONTRACT_TARGETS.items():
    print(k, cat, mode)
# '/home/drseuss/ai-finops-framework'      ('repo-alias',     'ro')
# '/home/drseuss/ai-finops-framework/.git' ('repo-alias-git', 'rw')
```

The hard-coded host-path contract is present in `spawn_wrapper.py` (`:142-143`) and referenced by
the tests (`test_spawn_wrapper.py:50`). The full literal also remains as the compose env DEFAULT
(`${FINOPS_REPO_DIR:-/home/drseuss/ai-finops-framework}` at `docker-compose.ladder.yml:67/70/71/
91/94/95/128/131/132`) — an additional surface for `b1_path_config` to consume (see D-1).

### Edge 3 — cells execute in shared host worktrees with `.git` rw (the mount). **PASS**

**3a. The contract map.** The fixed-mount map grants the shared worktree namespace rw and the
`.git` overlays rw:

```bash
sed -n '124,151p' scripts/fleet/spawn_wrapper.py     # CONTRACT_TARGETS
# 128  "/tmp":            ("worktree",   "rw")    -- the shared /tmp worktree namespace
# 130  "/repo":           ("repo",       "ro")
# 135  "/repo/.git":      ("repo-git",   "rw")    -- gitdir overlay, phase commits write here
# 142  "/home/drseuss/ai-finops-framework":      ("repo-alias",     "ro")
# 143  "/home/drseuss/ai-finops-framework/.git": ("repo-alias-git", "rw")
```

The module's own comment (`:131-141`) states the shared-worktree design outright: *"a sibling
cell must COMMIT its phase work into the shared worktree, which writes the worktree registration
+ objects + refs under /repo/.git … worktrees in the shared /tmp namespace carry a ``gitdir:``
pointer to the repo's HOST path (e.g. /home/drseuss/ai-finops-framework/.git/…)"* — i.e. the
cell worktree's git metadata IS the main repo's `.git`, shared across every cell.

**3b. The compose mount.** Cells and the orchestrator mount the shared host worktree root rw and
the repo's `.git` rw:

```bash
grep -n "FINOPS_WORKTREE_ROOT\|/home/drseuss/ai-finops-framework/.git" infrastructure/docker-compose.ladder.yml
# 39   FINOPS_WORKTREE_ROOT: /tmp
# 66   - ${FINOPS_WORKTREE_ROOT:-/tmp}:/tmp:rw                 # x-ladder-mounts (the cell set)
# 71   - ${FINOPS_REPO_DIR:-…}/.git:/home/drseuss/ai-finops-framework/.git:rw
# 127  - ${FINOPS_WORKTREE_ROOT:-/tmp}:/tmp:rw                 # x-orchestrator-mounts
# 132  - ${FINOPS_REPO_DIR:-…}/.git:/home/drseuss/ai-finops-framework/.git:rw
```

**3c. The mount a REAL cell request carries** — first-hand dump of
`build_phase_request` for an `implementation` phase (no docker, no model — a pure function
call; the request is what `spawn_sibling` mounts into the cell):

```
=== REAL build_phase_request (implementation, phase b1_path_config) ===
  target=/tmp                               mode=rw    # the shared /tmp worktree namespace
  target=/app/experiments/results           mode=rw
  target=/repo                              mode=ro
  target=/repo/.git                         mode=rw    # shared git metadata, WRITABLE
  target=/home/drseuss/ai-finops-framework  mode=ro    # host-path repo alias (D-16)
  target=/home/drseuss/ai-finops-framework/.git  mode=rw  # shared host .git, WRITABLE
  target=/home/drseuss/.local/bin           mode=ro    # D-2 auth set
  target=/home/drseuss/.opencode/bin        mode=ro
  target=/home/drseuss/.local/share/claude  mode=ro
  target=/home/drseuss/.claude              mode=ro
  target=/state                             mode=rw    # per-attempt state namespace (P0-3)
  target=/auth/opencode_auth.json           mode=ro
```

Cells execute in shared host worktrees under `/tmp` (`FINOPS_WORKTREE_ROOT` default `/tmp`,
`spawn_wrapper.py:551`; the run's own worktree `/tmp/wt_wave2` is one of them), and every cell
mounts the SAME `.git` (both `/repo/.git` and the host-path `/home/drseuss/ai-finops-framework/
.git`) **rw** so phase commits write the shared git metadata — a bad cell can pollute the
metadata another concurrent cell reads. All three mounts are in the request a cell actually
receives. Edge 3 confirmed exactly as the spec's `current_state` states it.

---

## 3. Verdict summary

| # | Mandate edge (as stated) | Status at the pin |
|---|---|---|
| 1 | the socket is mounted into a container, and spawn_wrapper invokes docker directly | **PASS** — compose mounts `/var/run/docker.sock:/var/run/docker.sock:ro` into the orchestrator tier (`docker-compose.ladder.yml:144`, services `campaign-wrapper` `:293` + `workflow-runner` `:299`); `spawn_wrapper.py` builds `docker run`/`docker compose` argv and executes via `subprocess.run` at `:744` / `:1056` / `:1224` |
| 2 | `/home/drseuss/ai-finops-framework` literals exist in `spawn_wrapper.py` + tests | **PASS** — `spawn_wrapper.py:142-143` (CONTRACT_TARGETS repo-alias/repo-alias-git keys, rw `.git`), `:98-101` + `:822` host-home defaults; `tests/test_spawn_wrapper.py:50` (+ `:83-86/:153-154`), `tests/test_fleet_guards.py:122-124/:462`, `tests/test_workflow_executor_parity.py:996` |
| 3 | cells execute in shared host worktrees with `.git` rw | **PASS** — `CONTRACT_TARGETS` `:128` (`/tmp` worktree rw) + `:135` (`/repo/.git` rw) + `:142-143` (host-path `.git` rw); compose `:66/:71/:127/:132`; real `build_phase_request` dump carries `/tmp` rw + both `.git` dirs rw — the shared git metadata every cell mounts writable |

**Pin verdict: all three launch-boundary edges are CONFIRMED against the actual code — each with
code + command + (for edge 3) a live-request dump as evidence, none asserted.** The socket-in-
container + direct-docker-invocation shape is the `b3_launch_broker` mandate's ground truth; the
host-path literals in the wrapper and the tests are the `b1_path_config` mandate's; the shared
`/tmp` worktrees with rw `.git` overlays are the `b2_ephemeral_clone` mandate's. The three
findings above are the baseline the implementation phases and the adversarial review
(`b4_adversarial`) will be measured against.

---

## 4. Deviations recorded against the pinned bytes / mandate

Recorded per the D-series convention. Each deviation is a correction to the spec's stated
baseline that the implementation phases should consume; none changes the wave's work items.

**D-1 — the host-path literal also survives as the env DEFAULT in the compose file, not only in
`spawn_wrapper.py`/tests.** The spec's `current_state` and `b1` scope name
`spawn_wrapper.py` + tests as the literal surfaces; in addition, every compose mount that needs
the repo path carries `${FINOPS_REPO_DIR:-/home/drseuss/ai-finops-framework}`
(`docker-compose.ladder.yml:67/70/71/91/94/95/128/131/132`) — an env-indirection with a
host-specific literal default. The env indirection already exists (`FINOPS_REPO_DIR` /
`FINOPS_WORKTREE_ROOT` / `AUTH_HOME`), so `b1_path_config`'s PathConfig "derived from env with
defaults relative to the package root" is the direct replacement for these defaults — but the
compose `:-` defaults and the `AUTH_DIRS`/`auth_home` host-home set (`spawn_wrapper.py:98-101`,
`:822`) are part of the same contract and must die with it, and the tests that assert the
host-home auth targets (`test_spawn_wrapper.py:83-86`, `test_fleet_guards.py:122-124`) will need
the same PathConfig treatment as the `:50` canonical-repo pin. The three preregistered edges all
hold as stated; this deviation widens the *surface* `b1` must sweep, not the edge claims.

---

## 5. LOG — PASS/FAIL per claim

| Claim | Attempts | Result |
|---|---|---|
| Edge 1a — the socket is mounted into a container (compose line found) | 1 | **PASS** — `docker-compose.ladder.yml:144` |
| Edge 1b — `spawn_wrapper` invokes docker directly (subprocess call found) | 1 | **PASS** — `spawn_wrapper.py:699/744` (+ `:1012/1056`, `:1212-1224`) |
| Edge 2 — `/home/drseuss/ai-finops-framework` literals in `spawn_wrapper.py` + tests | 1 | **PASS** — `spawn_wrapper.py:142-143`; `test_spawn_wrapper.py:50`; `test_workflow_executor_parity.py:996` |
| Edge 3 — cells execute in shared host worktrees with `.git` rw (mount found) | 1 | **PASS** — `CONTRACT_TARGETS` `:128/:135/:142-143`; compose `:66/:127/:132`; real-request dump (all three `.git`/`/tmp` surfaces rw) |
| Pin integrity — spec SHA256 + worktree sha recorded | 1 | **PASS** — `c83a03ab…` / `6eee5cea1…`, identical in both trees |

No edge required more than one reproduction attempt; no failed finding. Preregistration
committed as `[workflow] b0_pin_spec — Land the two fleet-level security gaps (Wave 2)`.
