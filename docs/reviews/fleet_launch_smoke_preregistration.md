---
status: accepted
kind: preregistration
spec: fleet_launch_smoke
phase: ws0_pin_spec
run: run-82800f7b4649
generated_at: 2026-09-03T04:15:00Z
---

# Preregistration — `fleet_launch_smoke` (ws0_pin_spec)

**The house pin convention.** This document is written BEFORE any implementation phase of the
smoke wave executes (`ws1_clone_wired`, `ws2_broker_pathview`, `ws3_stragglers`, `ws4_smoke`,
`ws5_adversarial`, `ws6_test_gate`). Its purpose is twofold, and both halves are load-bearing:

1. **Anchor the run to exact bytes.** A workflow spec is a mutable file. Recording the spec's
   SHA256 makes the mandate immutable *by reference*: any divergence is detectable by re-running
   one command.
2. **Verify the three wiring gaps + the smoke precondition, do not assert them.** The gaps this
   wave exists to close are stated as current-state claims in the spec's question/current_state
   (authored 2026-09-02) and inherit the `fleet_launch_boundary` + `fleet_launch_boundary_followups`
   adversarial reviews' findings (F1 clone-not-wired, F2 broker-seam config split, F3 straggler
   residuals): (1) `create_run_clone` has no callers — the executors read `FINOPS_RUN_CLONE` but
   nothing exports it; (2) the broker validates container-built mounts against the HOST path
   config — the D-16 repo-alias split (/app in-container vs host path) makes it refuse every
   containerized spawn; (3) `backfill_sonar.py:110` calls docker run — a third untyped caller
   outside the broker. The smoke precondition is that docker works on THIS host and the
   `fleet/base:latest` image exists. Each edge is re-derived below against the ACTUAL code at the
   pin + this host, and the command that produced the evidence is recorded so a reader can
   reproduce every finding without trusting this document. An edge that does not hold is a FAILED
   finding — recorded as a deviation below, never smoothed over.

The four edges are verified below against the state at launch.

---

## 1. The pin

| Field | Value |
|---|---|
| Spec path | `workflows/repository/fleet_launch_smoke.yaml` |
| Spec **SHA256** | `64bbeba7b259c5df3dcb58b83cd4e48fb8fead25606de2b6ec8824c530743490` |
| Spec size | 16,368 bytes |
| Worktree HEAD (git sha) | `97c4f5e0bd8ffea84e883dcb183e103991d7efc4` |
| HEAD subject | `[workflow] fb4_adversarial — Complete the two half-deliveries the fle…` (the follow-up wave's terminal commit — the tree this smoke wave starts from) |
| Worktree | `/tmp/wt_wave2` — detached `HEAD` at `97c4f5e0b` (gitdir `/home/drseuss/ai-finops-framework/.git/worktrees/wt_wave2`) |
| Main checkout | `/home/drseuss/ai-finops-framework` — branch `main`, `6eee5cea131447f7e6dfa78b1865ccef136fcc3a` (the smoke work lives on the worktree branch, awaiting the permanence gate; 15 commits ahead of main) |
| Working tree | clean except untracked `run3.log` (a runner artifact, not a source file) |
| Control run | `run-82800f7b4649` — `fleet_launch_smoke`, `state: running`, `model: deepseek/deepseek-v4-flash`, started `2026-09-03T04:10:37.125844Z` (this run) |
| Control db | `/home/drseuss/ai-finops-framework/experiments/results/control/control.db` (machine-local state at the MAIN checkout, per the DB-location rule), `runs.spec_name = 'fleet_launch_smoke'`, `workflow_revision_id = 45fc0710ef78440456450fbd7e9bc9c8ce96095d9d0df638e0cd5034bdbe6fb3` |
| Revision digest | `45fc0710ef78440456450fbd7e9bc9c8ce96095d9d0df638e0cd5034bdbe6fb3` — verified to EQUAL a fresh `compute_workflow_revision_id(load_spec(...))` at the pin (the run's recorded digest matches the spec's canonicalized definition digest) |
| Pinned at | 2026-09-03T04:15:00Z |

The spec file is committed at the pinned HEAD (tracked in `git ls-files`), so the mandate is
immutable by reference:

```bash
sha256sum workflows/repository/fleet_launch_smoke.yaml
# 64bbeba7b259c5df3dcb58b83cd4e48fb8fead25606de2b6ec8824c530743490
git rev-parse HEAD          # (in the worktree /tmp/wt_wave2)
# 97c4f5e0bd8ffea84e883dcb183e103991d7efc4
```

If either value differs when `ws4_smoke` (or `ws6_test_gate`) runs, the spec was edited mid-run
and the mandate this document pins is no longer the mandate being executed — a reportable finding
in itself.

**Spec shape at the pin** — seven phases (six `kind: agent` + one `kind: test`):

| # | Phase | kind | scope | notes |
|---|---|---|---|---|
| 0 | `ws0_pin_spec` | agent | `implementation` | **this phase** — the preregistration |
| 1 | `ws1_clone_wired` | agent | `implementation` | create_run_clone invoked in the `--orchestrator` composition root, `FINOPS_RUN_CLONE` exported, run_clone passed explicitly to both executors |
| 2 | `ws2_broker_pathview` | agent | `implementation` | the broker validates the view it executes (container-view vs host-view PathConfig) |
| 3 | `ws3_stragglers` | agent | `implementation` | backfill_sonar routed/documented; the broker service host-literal removed |
| 4 | `ws4_smoke` | agent | `implementation` | THE SMOKE — one real end-to-end launch on this host (the wave's verdict) |
| 5 | `ws5_adversarial` | agent | `adversarial_readonly` | independent pro reviewer (requires_deliverable) |
| 6 | `ws6_test_gate` | test | `implementation` | the harness gate suite |

---

## 2. Verified current-state edges (the three wiring gaps + the smoke precondition)

Each edge is stated as the spec's mandate states it, then **independently derived** against the
code at `97c4f5e0b` (the smoke wave's starting tree) + this host. No finding was accepted on the
spec's authority.

**Verdict legend.** **PASS** — the claimed edge holds at the pin, with code/command evidence.
**FAILED (deviation)** — the claimed edge does not hold as stated; the deviation is recorded and
the true state proven. In a pin phase, a FAILED sub-edge is not a wave failure — it is the
correction that makes the implementation phases target the real state.

### Edge 1 — w1: `create_run_clone` has no callers. **PASS**

The full clone lifecycle (`create_run_clone` / `discard_run_clone` / `sweep_stale_clones`) lives
in `src/agentic_dynamics/runtime/run_clone.py` (`create_run_clone` def at `:153`, `discard_run_clone`
at `:245`, `sweep_stale_clones` at `:279`; `RUN_CLONE_ENV = "FINOPS_RUN_CLONE"` at `:66`). A
grep of the production tree (`src/` + `scripts/`, excluding the defining module) finds ZERO call
sites:

```bash
grep -rn "create_run_clone" src/ scripts/ --include=*.py
# src/agentic_dynamics/runtime/run_clone.py:153   (the def — the ONLY production reference)
# + docstring/error-string mentions at :10, :114, :187, :194, :201, :213 (self-references)
grep -rn "discard_run_clone\|sweep_stale_clones" src/ scripts/ --include=*.py
# run_clone.py:17, :21, :114, :140, :235, :245, :266, :270, :279, :287 (self-references ONLY)
```

`scripts/run_workflow.py` (the composition root) has zero clone references — the `--orchestrator`
branch constructs both executors at `:450-469` with NO `run_clone` argument:

```bash
grep -n "DockerAgentExecutor\|DockerVerifierExecutor\|run_clone\|create_run_clone\|FINOPS_RUN_CLONE" scripts/run_workflow.py
# :444-445  the imports
# :450-459  DockerAgentExecutor(spec_path=…, spec_name=…, goal=…, model=…, workdir=…,
#           backend=…, timeout=…, cell_image=…)   ← NO run_clone
# :460-469  DockerVerifierExecutor(same shape)     ← NO run_clone
```

The executors READ `FINOPS_RUN_CLONE` from the environment as a fallback — `docker_executor.py:74`
(`self._run_clone = run_clone or os.environ.get("FINOPS_RUN_CLONE")`) and
`docker_verifier_executor.py:84` (identical) — but a repo-wide scan (`.py`/`.sh`/`.service`/
`.yaml`/`.yml`) finds nothing that EXPORTS it:

```bash
grep -rn "FINOPS_RUN_CLONE" . --include=*.py --include=*.sh --include=*.service --include=*.yaml
# run_clone.py (RUN_CLONE_ENV def) · docker_executor.py:74 + docker_verifier_executor.py:84
#   (os.environ.get READS) · tests/test_workflow_executor_parity.py:701 (monkeypatch.setenv — a
#   TEST) · the executors' docstrings + this spec. NO production export anywhere.
```

**Confirmed.** In a real `--orchestrator` run today, no clone is created and the executors'
`run_clone` argument is always empty (falls to an unset env → `None`). w1's mandate ("create the
per-run clone at `PathConfig.runs_root/<run-id>/repo` BEFORE the executors are built, export
`FINOPS_RUN_CLONE`, pass `run_clone` explicitly") targets a real, present gap.

### Edge 2 — w2: the broker validates against the host path config. **PASS**

The broker's launch path validates twice, and BOTH validations default to the HOST-view
`PathConfig` — never a container-view config, and never a per-request view discriminator:

```bash
# scripts/fleet/launch_broker.py — launch() (the broker's ONE launch path)
# :212  errors = validate_launch_request(request, path_config=path_config)
#       → path_config is None unless injected (serve/main pass nothing → broker_contract.py:479
#         falls back to PathConfig.from_env(require_existing=False) — the HOST env config)
# :221  cfg = path_config or spawn_wrapper.default_path_config()
#       → spawn_wrapper.default_path_config() = PathConfig.from_env() (spawn_wrapper.py:154-163)
#         — the HOST env config (FINOPS_REPO_DIR / FINOPS_WORKTREE_ROOT / …), validated once
# :222  scope_errors = spawn_wrapper.validate_spawn(request, path_config=cfg)
#       → step 3 derives the mount contract from that cfg: contract_targets(cfg) (spawn_wrapper
#         :501) keys the repo-alias/.git contract on cfg.repo_root / cfg.git_dir — the HOST paths
```

The `serve` daemon mode — the mode the systemd unit runs (`serve` binds the seam socket and calls
`serve_request`, which calls `launch(payload, path_config=None)`, `launch_broker.py:467`) — never
passes a `path_config`, so every validated mount contract is the host env config. The request
schema carries NO view field: `LAUNCH_REQUEST_FIELDS` (broker_contract.py, the closed typed
contract) has no `view`/`container_view`/`host_view` member — only the typed fields including
`run_clone` (`broker_contract.py:139`, "fb1 clone-mount reference"). A grep for a view
discriminator across `scripts/fleet/*.py` finds nothing.

Consequence (the w2 refusal shape): a request whose mounts were built against a container-view
`PathConfig` (the repo aliased at its /app-in-container path, per the compose mounts
`docker-compose.ladder.yml:72/:75/:76` — `${FINOPS_REPO_DIR}:/repo:ro` AND
`${FINOPS_REPO_DIR}:${FINOPS_REPO_DIR}:ro`, the same value for both the /repo target and the
host-path alias) is validated against the broker's OWN host config. When the two views resolve to
different paths, a mount the caller legitimately built is outside the contract the broker derives
— refused for a path split the caller cannot see. On THIS host the broker-side config resolves to
the host paths (verified: `PathConfig.from_env()` → repo_root `/tmp/wt_wave2`, git_dir
`/tmp/wt_wave2/.git`, worktrees_root `/tmp`, runs_root `/var/lib/agentic-dynamics/runs`), while a
container-tier caller sees `/repo` + the in-container repo path — the split the spec names.

**Confirmed.** The broker validates against the host path config (no view-aware validation
exists). w2's mandate ("a container-view request validates against the container-view PathConfig,
a host-view request against the host config — never refusing a request for a path split the
caller cannot see") targets a real, present gap.

### Edge 3 — w3: `backfill_sonar.py:110` calls docker run. **PASS**

`scripts/archive/backfill_sonar.py` — a one-time bucket script per `scripts/CONTEXT.md`'s manifest
(the classification line lists `backfill_sonar.py` under `one-time:`) — invokes docker directly
via `subprocess.run`, outside the broker:

```bash
sed -n '109,125p' scripts/archive/backfill_sonar.py
# 109:    cmd = [
# 110:        "docker", "run", "--rm",
# 111:        "--network", SONAR_NETWORK,
# 112:        "-v", f"{code_dir}:/usr/src",
# …        sonarsource/sonar-scanner-cli:latest …
# 125:        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
```

`grep -n '"docker", "run"' scripts/archive/backfill_sonar.py` → `:110` exactly. The docker call is
`run_sonar_docker`'s `subprocess.run` at `:125` over the argv whose head is `:110` — a loose,
untyped docker caller outside the broker's closed typed seam. **Confirmed.** w3's mandate (route
through the broker OR document as the second benign read-only exception with the reason, recorded)
targets a real, present caller.

### Edge 4 — the smoke precondition: docker works here AND `fleet/base:latest` exists. **PASS**

Both halves of the smoke precondition hold on this host:

```bash
docker info                       # exit 0 — the engine is up (client=29.1.3 server=29.1.3)
docker images --format '{{.Repository}}:{{.Tag}} {{.ID}}' | grep fleet/base
# fleet/base:latest ab6475914428
```

The image is present (1.77GB; `fleet/job-example:latest` shares the same image id `ab6475914428`,
and `fleet/orchestrator:latest` / `fleet/supervisor:latest` also exist). `docker info` exits 0.
**Confirmed** — a real `ws4_smoke` launch (docker run of `fleet/base` with the run clone mounted
read-only, a trivial suite, a returned verdict) is executable on this host.

---

## 3. Supplementary observations (not preregistration edges, recorded for the smoke phases)

- **The launch-broker systemd unit is NOT installed on this host.** `systemctl --user status
  agentic-dynamics-launch-broker` → "could not be found"; no user unit under
  `~/.config/systemd/user/`; no broker socket at the default seam locations; no `launch_broker`
  daemon process. The unit file is committed (`infrastructure/agentic-dynamics-launch-broker.service`)
  but the daemon is not running. `ws4_smoke` must therefore either drive the broker in-process
  (`launch_broker.serve_request` / `launch`, which `launch_broker.py:445` itself names as the
  broker-hosted smoke surface) or install/start the unit first — and `ws3`'s host-literal
  remediation still applies to the committed unit.
- **`PathConfig.from_env()` on this host** resolves repo_root `/tmp/wt_wave2`, git_dir
  `/tmp/wt_wave2/.git`, worktrees_root `/tmp`, runs_root `/var/lib/agentic-dynamics/runs` — the
  host view Edge 2 names. `runs_root` (`/var/lib/agentic-dynamics/runs`) is where ws1 must create
  `runs_root/<run-id>/repo`, and where ws4 must observe the mount source.

---

## 4. LOG — PASS/FAIL per claim

| Claim | Attempts | Result |
|---|---|---|
| Edge 1 — `create_run_clone` has no callers (grep of `src/` + `scripts/`) | 1 | **PASS** — `run_clone.py:153/:245/:279` self-references only; `run_workflow.py` has zero clone references; both executor constructors (`:450-469`) pass no `run_clone`; `FINOPS_RUN_CLONE` is read (`docker_executor.py:74`, `docker_verifier_executor.py:84`) but never exported in production |
| Edge 2 — the broker validates against the host path config | 1 | **PASS** — `launch_broker.py:212/:221-222` — `validate_spawn(request, path_config=cfg)` with `cfg = path_config or spawn_wrapper.default_path_config()` (= `PathConfig.from_env()`, the HOST config); `serve` passes no path_config; `LAUNCH_REQUEST_FIELDS` carries no view discriminator |
| Edge 3 — `backfill_sonar.py:110` calls docker run | 1 | **PASS** — `"docker", "run", "--rm"` at `:110`, executed by `subprocess.run` at `:125`; one-time bucket script |
| Edge 4 — docker works here AND `fleet/base:latest` exists | 1 | **PASS** — `docker info` exit 0 (client/server 29.1.3); `fleet/base:latest` = `ab6475914428` |
| Pin integrity — spec SHA256 + worktree git sha recorded | 1 | **PASS** — `64bbeba7…` / `97c4f5e0b…`, spec committed at the pinned HEAD; run `workflow_revision_id` `45fc0710…` equals a fresh `compute_workflow_revision_id` at the pin |

No edge required more than one reproduction attempt; no failed finding; no deviation recorded.
Preregistration committed as `[workflow] ws0_pin_spec — Wire the containerized path by SMOKING
it`.
