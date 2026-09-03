---
status: accepted
kind: preregistration
spec: fleet_launch_container_smoke
phase: cs0_pin_spec
run: run-6bd836f71f01
generated_at: 2026-09-03T12:18:00Z
---

# Preregistration — `fleet_launch_container_smoke` (cs0_pin_spec)

**The house pin convention.** This document is written BEFORE any implementation phase of the
container-smoke wave executes (`cs1_container_env`, `cs2_durable_evidence`, `cs3_container_smoke`,
`cs4_adversarial`, `cs5_test_gate`). Its purpose is twofold, and both halves are load-bearing:

1. **Anchor the run to exact bytes.** A workflow spec is a mutable file. Recording the spec's
   SHA256 makes the mandate immutable *by reference*: any divergence is detectable by re-running
   one command.
2. **Verify the three findings of the `fleet_launch_smoke` adversarial review + the smoke
   precondition, do not assert them.** The gaps this wave exists to close are stated as current-state
   claims in the spec's question/current_state (authored 2026-09-02) and inherit the
   `fleet_launch_smoke` adversarial review's findings (F1 the container env — `x-ladder-env` —
   never carries `FINOPS_REPO_DIR`/`FINOPS_GIT_DIR`, so a container-tier orchestrator derives the
   wrong repo view and the broker refuses its own spawns; F2 the container-view path was never
   smoke-proven — only unit-proven; F3 the mount-proof evidence was a recorded `--rm` observation,
   not durably re-verifiable): (1) `x-ladder-env` lacks `FINOPS_REPO_DIR`/`FINOPS_GIT_DIR`; (2) the
   container-tier orchestrator shape is not smoke-proven (only unit tests); (3) the mount proof was
   a `--rm` observation. The smoke precondition is that docker works on THIS host and the fleet
   images (`fleet/base`, `fleet/orchestrator`) exist. Each edge is re-derived below against the
   ACTUAL code at the pin + this host, and the command that produced the evidence is recorded so a
   reader can reproduce every finding without trusting this document. An edge that does not hold is
   a FAILED finding — recorded as a deviation below, never smoothed over. If a claim cannot be
   reproduced after THREE attempts, the deviation is recorded and the claim FAILs — never loop.

The four edges are verified below against the state at launch.

---

## 1. The pin

| Field | Value |
|---|---|
| Spec path | `workflows/repository/fleet_launch_container_smoke.yaml` |
| Spec **SHA256** | `301ff0191f2eccf661b5e693c7dacc566c83d2459e1fb4369dd5279c2553a358` |
| Spec size | 13,596 bytes |
| Worktree HEAD (git sha) | `57774dfcbd3290159db8ddd6277e4f6882422cd5` |
| HEAD subject | `[workflow] ws5_adversarial — Wire the containerized path by SMOKING i…` (the predecessor smoke wave's terminal commit — the tree this container-smoke wave starts from; it is the commit that introduced this spec file) |
| Worktree | `/tmp/wt_wave2` — detached `HEAD` at `57774dfcb` (gitdir `/home/drseuss/ai-finops-framework/.git/worktrees/wt_wave2`) |
| Main checkout | `/home/drseuss/ai-finops-framework` — branch `main`, `6eee5cea131447f7e6dfa78b1865ccef136fcc3a` (the container-smoke work lives on the worktree branch, awaiting the permanence gate) |
| Working tree | clean except untracked `run4.log` (a runner artifact, not a source file) |
| Control run | `run-6bd836f71f01` — `fleet_launch_container_smoke`, `state: running`, `model: deepseek/deepseek-v4-flash`, started `2026-09-03T12:11:14.003712Z` (this run) |
| Control db | `/home/drseuss/ai-finops-framework/experiments/results/control/control.db` (machine-local state at the MAIN checkout, per the DB-location rule), `runs.spec_name = 'fleet_launch_container_smoke'`, `workflow_revision_id = c1f8286a46f83221b250d8180bf1008719217df8396d36ddeb37d66b02936a82` |
| Revision digest | `c1f8286a46f83221b250d8180bf1008719217df8396d36ddeb37d66b02936a82` — verified to EQUAL a fresh `compute_workflow_revision_id(load_spec(...))` at the pin (the run's recorded digest matches the spec's canonicalized definition digest) |
| Pinned at | 2026-09-03T12:18:00Z |

The spec file is committed at the pinned HEAD (tracked in `git ls-files`; `git diff HEAD` is empty
for it), so the mandate is immutable by reference:

```bash
sha256sum workflows/repository/fleet_launch_container_smoke.yaml
# 301ff0191f2eccf661b5e693c7dacc566c83d2459e1fb4369dd5279c2553a358
git rev-parse HEAD          # (in the worktree /tmp/wt_wave2)
# 57774dfcbd3290159db8ddd6277e4f6882422cd5
```

If either value differs when `cs3_container_smoke` (or `cs5_test_gate`) runs, the spec was edited
mid-run and the mandate this document pins is no longer the mandate being executed — a reportable
finding in itself.

**Spec shape at the pin** — six phases (five `kind: agent` + one `kind: test`):

| # | Phase | kind | scope | notes |
|---|---|---|---|---|
| 0 | `cs0_pin_spec` | agent | `implementation` | **this phase** — the preregistration |
| 1 | `cs1_container_env` | agent | `implementation` | `FINOPS_REPO_DIR`/`FINOPS_GIT_DIR` set in `x-ladder-env` + the orchestrator tier env; both directions unit-proven |
| 2 | `cs2_durable_evidence` | agent | `implementation` | the smoke harness persists every artifact (container id, mount inspect RW=false, exit code, verdict) BEFORE removal |
| 3 | `cs3_container_smoke` | agent | `implementation` | THE SMOKE OF THE REAL SHAPE — the compose orchestrator service (with the cs1 env) drives ONE cell end to end; a host-view-only smoke is a failed wave (hard rule 1) |
| 4 | `cs4_adversarial` | agent | `adversarial_readonly` | independent pro reviewer (requires_deliverable; `run_model: deepseek/deepseek-v4-pro`) |
| 5 | `cs5_test_gate` | test | `implementation` | the harness gate suite |

---

## 2. Verified current-state edges (the three adversarial findings + the smoke precondition)

Each edge is stated as the adversarial review / spec's mandate states it, then **independently
derived** against the code at `57774dfcb` (the container-smoke wave's starting tree) + this host.
No finding was accepted on the review's authority.

**Verdict legend.** **PASS** — the claimed edge holds at the pin, with code/command evidence.
**FAILED (deviation)** — the claimed edge does not hold as stated; the deviation is recorded and
the true state proven. In a pin phase, a FAILED sub-edge is not a wave failure — it is the
correction that makes the implementation phases target the real state.

### Edge 1 — f1: `x-ladder-env` lacks `FINOPS_REPO_DIR`/`FINOPS_GIT_DIR`. **PASS**

`x-ladder-env` (`infrastructure/docker-compose.ladder.yml:31-63`) — the canonical container env
anchor, merged into `x-cell-base` (`:115-116`), `x-supervisor-base` (`:123-124`) and
`x-orchestrator-base` (`:174-175`) — sets the Redis reachability vars, `FINOPS_WORKTREE_ROOT`,
`HOME`, `OPENCODE_BIN`/`CLAUDE_BIN`, the RAG store endpoints, and the egress `HTTP(S)_PROXY`
block. It carries **no** repo-view var:

```bash
sed -n '31,63p' infrastructure/docker-compose.ladder.yml | grep -nE '^  [A-Z]'
#  4: FINOPS_REDIS_HOST: finops-queue
#  9: FINOPS_REDIS_PORT: "6379"
# 10: FINOPS_REDIS_DB: "1"
# 11: FINOPS_KB_DB: "2"
# 16: FINOPS_WORKTREE_ROOT: /tmp
# 19: HOME: ${AUTH_HOME}
# 20: OPENCODE_BIN: ${AUTH_HOME}/.opencode/bin/opencode
# 21: CLAUDE_BIN: ${AUTH_HOME}/.local/bin/claude
# 25: CHROMA_HOST: chromadb
# 26: FINOPS_NEO4J_URI: bolt://neo4j:7687
# 31: HTTP_PROXY: http://egress:8888
# 32: HTTPS_PROXY: http://egress:8888
# 33: NO_PROXY: finops-queue,neo4j,chromadb,localhost,127.0.0.1
```

Every occurrence of `FINOPS_REPO_DIR` in the file is a **mount-source interpolation** — a
host-side `- ${FINOPS_REPO_DIR:?...}:…` volume source that the host's docker-compose substitutes
and never exports into a container environment — and `FINOPS_GIT_DIR` appears **zero** times:

```bash
grep -c "FINOPS_GIT_DIR" infrastructure/docker-compose.ladder.yml        # 0
python3 - <<'PY'   # classify each FINOPS_REPO_DIR occurrence: env mapping vs mount source
import re
for i, line in enumerate(open('infrastructure/docker-compose.ladder.yml'), 1):
    if 'FINOPS_REPO_DIR' in line:
        print(i, 'ENV' if re.match(r'\s+FINOPS_REPO_DIR:', line) else 'mount-source',
              line.strip()[:60])
PY
# 74/77/78/79  mount-source   (cell-base:   ${FINOPS_REPO_DIR}:…)
# 98/101/102/103 mount-source (supervisor:  ${FINOPS_REPO_DIR}:…)
# 144/147/148/149 mount-source (orchestrator: ${FINOPS_REPO_DIR}:…)
```

The orchestrator tier's own env (`x-orchestrator-base`, `:174-179`) merges `<<: *ladder-env` and
adds only `FINOPS_LAUNCH_BROKER_SOCKET` — the seam socket's container path. So a container-tier
orchestrator (`campaign-wrapper` `:323-327`, `workflow-runner` `:329-335`) boots with **no**
`FINOPS_REPO_DIR`/`FINOPS_GIT_DIR`; its `PathConfig.from_env()` falls to the compose
`working_dir: /repo` (both orchestrator services run at `/repo`), i.e. `repo_root = /repo` — the
mis-keyed view the adversary reproduced. **Confirmed** — cs1's mandate ("set FINOPS_REPO_DIR and
FINOPS_GIT_DIR to the container-visible repo path in x-ladder-env and the orchestrator tier env")
targets a real, present absence.

### Edge 2 — f2: the container-tier orchestrator shape is not smoke-proven (only unit tests). **PASS**

The previous smoke's OWN evidence states the orchestrator was driven **in-process on the host**,
never as the compose container tier. Three statements in `docs/reviews/fleet_launch_smoke_ws4_smoke.md`:

```bash
grep -n "HOST-view\|host-view\|in-process\|host-side caller\|unit-proven" \
  docs/reviews/fleet_launch_smoke_ws4_smoke.md
# :45  "the request is HOST-view here, built by a host-side caller, so it validates against the
#       host config; the container-view acceptance is unit-proven in ws2's suite"
# :142 "when the executor runs on the host (this smoke drove it there; the wave's controller runs
#       in-process)"
# :150 "in-process wave, the smoke) always produced a broken cell argv.*"
# :28  the broker was driven in its `serve` mode over a HOST-side unix-socket seam (the systemd
#       unit is not installed on this host — preregistration §3 of the prior wave)
```

A grep of the smoke evidence for any launch of the compose orchestrator service finds none — no
`docker compose up`, no `docker-compose run`, no `campaign-wrapper`/`workflow-runner` launch:

```bash
grep -rn "docker compose up\|docker-compose up\|compose run\|docker-compose run" \
  docs/reviews/fleet_launch_smoke_ws4_smoke.md docs/reviews/fleet_launch_smoke_adversarial.md
# (no matches)
grep -rn "campaign-wrapper" docs/reviews/fleet_launch_smoke_ws4_smoke.md
# (no matches — the smoke never touched the compose orchestrator service)
```

The container-view path is covered ONLY by unit tests — synthetic configs against a dry-run
validation and a stub docker binary, never a real container:

```bash
grep -n "def test_container_view\|container_view_config" tests/test_launch_broker.py
# :348 test_container_view_request_is_accepted_and_the_w2_refusal_shape_dies
# :353 container_cfg = launch_broker.container_view_config(host_cfg)   # synthetic /app config
# :415 test_broker_argv_still_uses_the_host_docker_path_for_a_container_view_request
# :434 test_container_view_clone_world_request_validates_and_mounts_the_host_clone
# :439 container_cfg = launch_broker.container_view_config(host_cfg)
grep -n "docker" tests/test_broker_hostside.py | head -3   # the broker-hostside suite uses a STUB docker binary
```

**Confirmed.** No smoke evidence — previous-wave doc or otherwise — shows the container-tier
orchestrator (the compose service) ever launching a cell. cs3's mandate ("launch the container-tier
orchestrator with the cs1 env and drive ONE cell end to end; a host-view-only smoke is a failed
wave") targets a genuinely unproven shape.

### Edge 3 — f3: the mount proof was a `--rm` observation. **PASS**

The previous smoke's mount proof was a **live observation transcribed into the doc**, made while
the container ran — not a durable artifact captured before removal. Two independent confirmations:

```bash
# (a) the docker call the smoke's broker made runs --rm — the container is gone at exit:
grep -n 'argv = \[docker, "run"' scripts/fleet/launch_broker.py
# :225  argv = [docker, "run", "--rm", "-i"]
# (the ws4 doc's own evidence: the RW=false inspect was taken "while the cell ran")
sed -n '84,96p' docs/reviews/fleet_launch_smoke_ws4_smoke.md
# "While the cell ran, `docker ps` + `docker inspect` observed the live container:"
# "container id: ea0017059406a847cab174ce7ba888061d849272dfe402907811c3c04e98b779"
# "mount: /tmp/.../run-82800f7b4649/repo -> /repo   (RW = false)"
```

Attempted re-derivation now — the container no longer exists and no durable smoke artifact dir was
ever written:

```bash
docker inspect ea0017059406a847cab174ce7ba888061d849272dfe402907811c3c04e98b779
# []  error: no such object: ea0017059406...   (attempt 1 of 3)
ls experiments/results/smoke   # (no such directory — no persisted smoke-artifact file)
```

The `RW=false` docker-level claim survives only as the doc's transcription. **Confirmed** — f3's
mandate ("every artifact — container id, docker inspect mount proof, exit code, verdict — written
to a DURABLE file BEFORE the container is removed; a recorded observation that cannot be re-derived
is not evidence") targets a real evidence gap.

### Edge 4 — the smoke precondition: docker works here AND the fleet images exist. **PASS**

Both halves of the smoke precondition hold on this host:

```bash
docker info | grep "Server Version"        # Server Version: 29.1.3  (exit 0 — the engine is up)
docker images --format '{{.Repository}}:{{.Tag}} {{.ID}}' | grep '^fleet/'
# fleet/base:latest       8160b6cb7112
# fleet/orchestrator:latest 569dd89c25c5
# fleet/supervisor:latest 4cddad0b2031
# fleet/job-example:latest ab6475914428
# fleet/egress-proxy:latest 0998120a4039
```

The images required for the cs3 compose drive are all present — in particular `fleet/base:latest`
(the cell image, rebuilt from the wave tree during the prior smoke, hence its id differs from the
`ab6475914428` the ws0 preregistration recorded) and `fleet/orchestrator:latest` (the container the
compose orchestrator services run). `docker info` exits 0. **Confirmed** — a real cs3 launch
(compose orchestrator service → broker → cell container, clone mounted read-only, trivial suite,
returned verdict) is executable on this host.

---

## 3. Supplementary observations (not preregistration edges, recorded for the cs phases)

- **The launch-broker systemd unit is STILL not installed on this host.** `systemctl --user status
  agentic-dynamics-launch-broker` → "could not be found"; no user unit under
  `~/.config/systemd/user/`; no `/run/launch-broker.sock`. The previous smoke's serve-mode seam
  socket `/tmp/agentic-dynamics-launch-broker.sock` still exists from the ws4 run.
  `cs3_container_smoke` must therefore drive the broker in its `serve` mode over a host seam socket
  (as ws4 did) or install/start the unit first — the container-tier orchestrator reaches the host
  broker through the seam (`FINOPS_LAUNCH_BROKER_SOCKET` at the fixed container target
  `/run/launch-broker.sock`, `docker-compose.ladder.yml:167/:179`).
- **The host runs_root default is not present/writable for this user** (`/var/lib/agentic-dynamics/runs`
  does not exist). The prior smoke phases overrode `FINOPS_RUNS_ROOT=/tmp/agentic-dynamics-runs`
  (the ws4 clone `run-82800f7b4649` still lives there). cs1/cs3 must keep that override in play —
  the clone-world mount source and the compose `x-orchestrator-mounts` `/tmp` bind must agree.
- **cs1's env value is a container-path decision, recorded here.** The spec names the fix: set
  `FINOPS_REPO_DIR`/`FINOPS_GIT_DIR` to the container-visible repo path — `/repo` and `/repo/.git`
  (the compose `working_dir` + `:ro` repo mount the orchestrator actually runs against; note the
  D-16 double-mount also exposes the repo at its HOST path inside the container, `.git` writable
  there at `:148`). cs1 must verify with a container-view path derivation that the discriminator
  keys correctly for whatever path it exports.
- **The `fleet/base:latest` id changed since the ws0 pin** (`ab6475914428` → `8160b6cb7112`): the
  ws4 smoke rebuilt it from the wave tree so the cell's baked `/app` copy matches the repo. cs3 must
  rebuild `fleet/base` (and, if the orchestrator service's code path changed under cs1, the
  orchestrator image) from the current wave tree before its launch, exactly as the ws4 doc requires.

---

## 4. LOG — PASS/FAIL per claim

| Claim | Attempts | Result |
|---|---|---|
| Edge 1 — `x-ladder-env` lacks `FINOPS_REPO_DIR`/`FINOPS_GIT_DIR` (grep the yml) | 1 | **PASS** — env block `:31-63` carries no repo-view var; every `FINOPS_REPO_DIR` occurrence is a mount-source interpolation (`:74/:77/:78/:79/:98/:101/:102/:103/:144/:147/:148/:149`); `FINOPS_GIT_DIR` appears 0 times; the orchestrator tier env (`:174-179`) adds only `FINOPS_LAUNCH_BROKER_SOCKET` |
| Edge 2 — the container-tier orchestrator shape is not smoke-proven (grep the smoke evidence) | 1 | **PASS** — ws4 smoke doc states the request was HOST-view, built host-side, controller in-process (`:45-46/:142/:150`); no `docker compose up`/`compose run`/`campaign-wrapper` launch anywhere in the smoke evidence; container-view coverage is unit-only (`test_launch_broker.py:348/:415/:434` synthetic config, `test_broker_hostside.py` stub docker) |
| Edge 3 — the mount proof was a `--rm` observation (read the smoke phase's evidence) | 1 | **PASS** — `launch_broker.py:225` runs `docker run --rm`; the ws4 RW=false inspect was taken "while the cell ran" (transcribed, not persisted); `docker inspect ea0017059406…` → "no such object"; no `experiments/results/smoke` artifact dir |
| Edge 4 — docker works here AND the fleet images exist | 1 | **PASS** — `docker info` exit 0 (server 29.1.3); `fleet/base:latest` `8160b6cb7112`, `fleet/orchestrator:latest` `569dd89c25c5` (+ supervisor/job-example/egress-proxy) |
| Pin integrity — spec SHA256 + worktree git sha recorded | 1 | **PASS** — `301ff0191f…` / `57774dfcbd3…`, spec committed at the pinned HEAD; run `workflow_revision_id` `c1f8286a46f…` equals a fresh `compute_workflow_revision_id` at the pin |

No edge required more than one reproduction attempt; no failed finding; no deviation recorded.
Preregistration committed as `[workflow] cs0_pin_spec — Smoke the container-tier orchestrator, the
REAL fleet shape`.
