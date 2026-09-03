---
status: accepted
kind: preregistration
spec: fleet_launch_boundary_followups
phase: fb0_pin_spec
run: run-f114d4c43ff2
generated_at: 2026-09-03T02:08:38Z
---

# Preregistration — `fleet_launch_boundary_followups` (fb0_pin_spec)

**The house pin convention.** This document is written BEFORE any implementation phase of the
follow-up wave executes (`fb1_clone_mounted`, `fb2_broker_hostside`, `fb3_stragglers`,
`fb4_adversarial`, `fb5_test_gate`). Its purpose is twofold, and both halves are load-bearing:

1. **Anchor the run to exact bytes.** A workflow spec is a mutable file. Recording the spec's
   SHA256 makes the mandate immutable *by reference*: any divergence is detectable by re-running
   one command.
2. **Verify the four follow-up edges, do not assert them.** The gaps this wave exists to close are
   stated as current-state claims in the spec's question/current_state (authored 2026-09-02) and
   inherit the `fleet_launch_boundary` adversarial review's findings (F2 clone-not-mounted, F3
   broker-not-host-side, F4 system_snapshot docker ps, F6 stale prose): (1) the per-run clone is
   created but never mounted — cells still mount `/tmp` rw + shared `.git` rw; (2) the compose
   has no socket mount and nothing host-side invokes the broker; (3) `system_snapshot.py:175`
   calls docker directly; (4) stale socket-holder prose remains in the Containerfile + the agent
   surfaces. Each edge is re-derived below against the ACTUAL code at the pin, and the command
   that produced the evidence is recorded so a reader can reproduce every finding without trusting
   this document. An edge that does not hold is a FAILED finding — recorded as a deviation below,
   never smoothed over.

The four edges are verified below against the state at launch.

---

## 1. The pin

| Field | Value |
|---|---|
| Spec path | `workflows/repository/fleet_launch_boundary_followups.yaml` |
| Spec **SHA256** | `8f953b36340fa5143d5a90052971be2f825eaa6e048326b3f16eb244014c22cb` |
| Spec size | 15,916 bytes |
| Worktree HEAD (git sha) | `86b148027f427624570ede1107ef57662c4d08bc` |
| HEAD subject | `[workflow] b4_adversarial — Land the two fleet-level security gaps (` (the fleet_launch_boundary Wave-2 tip, incl. the b3 broker module + the b4 adversarial review) |
| Worktree | `/tmp/wt_wave2` — detached `HEAD` at the Wave-2 tip (gitdir `/home/drseuss/ai-finops-framework/.git/worktrees/wt_wave2`) |
| Main checkout | `/home/drseuss/ai-finops-framework` — branch `main`, `6eee5cea131447f7e6dfa78b1865ccef136fcc3a` (pre-Wave-2: the Wave-2/follow-up work lives on the worktree branch, awaiting the permanence gate) |
| Working tree | clean except modified `run2.log` (a runner artifact, not a source file) |
| Control run | `run-f114d4c43ff2` — `fleet_launch_boundary_followups`, `state: running`, `model: deepseek/deepseek-v4-flash`, started `2026-09-03T02:03:33.335684Z` (this run) |
| Control db | `/home/drseuss/ai-finops-framework/experiments/results/control/control.db` (machine-local state at the MAIN checkout, per the DB-location rule), `runs.spec_name = 'fleet_launch_boundary_followups'`, `workflow_revision_id = d19a76af…` |
| Pinned at | 2026-09-03T02:08:38Z |

The spec file is committed at the pinned HEAD and byte-identical in both trees:

```bash
sha256sum workflows/repository/fleet_launch_boundary_followups.yaml   # run at the MAIN checkout
# 8f953b36340fa5143d5a90052971be2f825eaa6e048326b3f16eb244014c22cb
git rev-parse HEAD          # (in the worktree /tmp/wt_wave2)
# 86b148027f427624570ede1107ef57662c4d08bc
```

If either value differs when `fb4_adversarial` (or `fb5_test_gate`) runs, the spec was edited
mid-run and the mandate this document pins is no longer the mandate being executed — a reportable
finding in itself.

**Spec shape at the pin** — six phases (five `kind: agent` + one `kind: test`):

| # | Phase | kind | scope | notes |
|---|---|---|---|---|
| 0 | `fb0_pin_spec` | agent | `implementation` | **this phase** — the preregistration |
| 1 | `fb1_clone_mounted` | agent | `implementation` | the clone is the cell's world — the mount contract + its validation |
| 2 | `fb2_broker_hostside` | agent | `implementation` | the broker as a genuinely host-side systemd unit + a real IPC seam |
| 3 | `fb3_stragglers` | agent | `implementation` | f4 route/document + f6 prose fix through the generators |
| 4 | `fb4_adversarial` | agent | `adversarial_readonly` | independent pro reviewer (requires_deliverable) |
| 5 | `fb5_test_gate` | test | `implementation` | the harness gate suite |

---

## 2. Verified current-state edges (the four follow-up gaps)

Each edge is stated as the spec's mandate states it, then **independently derived** against the
code at `86b148027…` (the follow-up wave's starting tree). No finding was accepted on the spec's
authority.

**Verdict legend.** **PASS** — the claimed edge holds at the pin, with code/command evidence.
**FAILED (deviation)** — the claimed edge does not hold as stated; the deviation is recorded and
the true state proven. In a pin phase, a FAILED sub-edge is not a wave failure — it is the
correction that makes the implementation phases target the real state.

### Edge 1 — f2: the per-run clone is created but never mounted; cells still mount `/tmp` rw + shared `.git` rw. **PASS**

**1a. The clone LIFECYCLE exists — creation + discard + sweep — but has ZERO production callers.**
The b2 module `src/agentic_dynamics/runtime/run_clone.py` implements the full lifecycle:
`create_run_clone` (`:130`, a fresh `git clone --no-hardlinks` at
`PathConfig.runs_root/<run-id>/repo` with its OWN `.git`), `discard_run_clone` (`:222`),
`sweep_stale_clones` (`:256`). Nothing in the run path invokes it:

```bash
grep -rn "create_run_clone\|discard_run_clone\|sweep_stale_clones\|FINOPS_RUN_CLONE" \
  --include="*.py" scripts/ src/ tests/   # minus the module itself + the two executor constructors
# tests/test_run_clone.py:34-37,86,106-107,141-143   (unit tests ONLY)
# tests/test_workflow_executor_parity.py:671-674      (the executors' env-fallback test)
# scripts/run_workflow.py: (no matches)
```

`scripts/run_workflow.py` (the composition root) has no clone reference at all. The executors
`docker_executor.py:73` and `docker_verifier_executor.py:84` READ `FINOPS_RUN_CLONE` from the env
as a fallback, but nothing in the tree EXPORTS that variable. In a real run today no clone is
even created — cells execute in exactly the pre-b2 shared-worktree shape (see D-fb-1).

**1b. The clone is a validated REFERENCE, never a mount.** The request builders stamp the clone
path as a top-level field (`spawn_wrapper.py:1017-1024` — `request["run_clone"]`), and the broker
accepts it as one of the closed `LAUNCH_REQUEST_FIELDS` (`launch_broker.py:159` — "b2 reference
field — the broker validates the path, does not mount it yet") and validates it resolves under
`PathConfig.runs_root` (`launch_broker.py:440-460`). The ONE shared profile→mounts expansion,
`mounts_for_profile` (`launch_broker.py:219-294`), takes `run_clone` as a parameter (`:224`) but
NEVER adds it to the returned mount list; its own docstring says so (`:240-245`):
*"``run_clone`` (b2) is accepted and validated as a typed reference …, but is deliberately NOT
yet mounted."* The single docker subprocess (`launch_broker.py:578`) mounts only that profile
expansion.

**1c. What a cell DOES mount — the shared worktree rw + the shared git metadata rw, in both
halves of the mount assembly.** The broker's expansion for an agent cell (`mounts_for_profile`
`:269-294`): the shared worktree namespace `/tmp` rw (`:270`), the repo `/repo` ro (`:272`), the
gitdir overlay `/repo/.git` rw (`:273`), the repo at its host path ro (`:280`) and its host `.git`
rw (`:281`) — plus auth ro, per-attempt state rw, the credential file ro. The compose mirrors it:
`x-ladder-mounts` (`docker-compose.ladder.yml:68`, `/tmp:rw` `:69`, `.git:rw` `:74`) and
`x-orchestrator-mounts` (`:133`, `/tmp:rw` `:134`, `.git:rw` `:139`). `spawn_wrapper.py`'s
`FIXED_CONTRACT_TARGETS` (`:183-195`) states the design outright: `/repo/.git` rw *"so the cell's
phase commit can write … the shared .git"*, and `contract_targets` (`:219-220`) adds the
host-path `.git` rw alias. Two concurrent cells therefore still share git metadata through both
the `/repo/.git` and the host-path `.git` rw overlays.

**1d. First-hand dump of a real agent-cell mount set** (`mounts_for_profile('implementation_rw')`,
run at the pinned tree):

```
=== REAL implementation_rw profile expansion (the broker's ONE mount vocabulary) ===
  source=/tmp                      target=/tmp                     mode=rw   # the SHARED /tmp worktree namespace
  source=…/experiments/results     target=/app/experiments/results mode=rw
  source=<repo_root>               target=/repo                    mode=ro
  source=<repo_root>/.git          target=/repo/.git               mode=rw   # shared git metadata, WRITABLE
  source=<repo_root>               target=<repo_root>              mode=ro   # host-path repo alias (D-16)
  source=<repo_root>/.git          target=<repo_root>/.git         mode=rw   # shared host .git, WRITABLE
  … auth dirs ro · state rw · credential file ro
  # NO mount references runs_root/<run-id>/repo — the clone is absent from the mount set.
```

Edge 1 confirmed exactly as the spec's `current_state` states it, with the mount-assembly grep +
the shared profile expansion + a live dump as evidence. The follow-up's hard rule 1 — "the clone
is the cell's world" — targets a real, present state.

### Edge 2 — f3: the compose has no socket mount and nothing host-side invokes the broker. **PASS**

**2a. No socket mount remains in the compose.** `docker-compose.ladder.yml` has no
`/var/run/docker.sock` mount — every "socket" match is a comment asserting its absence:

```bash
grep -n "docker.sock\|/var/run/docker\|socket" infrastructure/docker-compose.ladder.yml
#  12  # The socket (D-3/D-14) lives on the HOST ONLY — the launch broker (b3_launch_broker) …
#  13  # host-side (non-container) component that holds the Docker socket …
#  14  # API caller. No service in this file mounts the socket; …
#  92  # NAMED volume. NO worktree mount …, NO socket.
# 124  # The Docker socket is NOT here (b3_launch_broker …) — no ladder service mounts the socket anymore.
# 128  # socket and is the ONLY Docker API caller: …
# 163  # fleet/cell — …; no socket.
# 297  # socket (b3_launch_broker): the socket lives ONLY where the broker runs (host);
# 315  # fleet/supervisor — … NO socket
```

The pre-b3 mount (`/var/run/docker.sock:/var/run/docker.sock:ro`) is gone; `b3_launch_broker`
removed it from the orchestrator tier.

**2b. No broker service/unit exists in the yml, and nothing host-side invokes the broker.**
The compose service list (`docker-compose.ladder.yml:161-…`) contains NO launch-broker service —
the two orchestrator services are `campaign-wrapper` (`:300`, `run_workflow.py --orchestrator`)
and `workflow-runner` (`:306`, `spawn_wrapper.py consume`), which run the wrapper IN a container.
`infrastructure/` holds only three systemd units — `docs-drift-scan.{service,timer}` and
`fleet-bootstrap.service` (brings up the `fleet-manager` container and nothing else) — no
broker unit; a repo-wide grep for broker-launch surfaces finds no `.service`/`.sh`/daemon:

```bash
grep -rln "launch_broker\|launch-broker" --include="*.service" --include="*.timer" --include="*.sh" . 
# (no systemd unit or launcher script — the broker is never run as a host service)
```

`scripts/fleet/launch_broker.py` is a module with a CLI `main()` (`:749-797`), but nothing wires
it to run as a host-side daemon or unit. There is NO host-side broker process.

**2c. The broker is invoked IN-PROCESS, from inside the socketless containers.** The wrapper
imports the broker (`spawn_wrapper.py:83`) and calls it directly:
`launch_broker.launch` (`:837`), `launch_broker.submit_run` (`:1171`),
`launch_broker.run_fleet_command` (`:1335`, `:1368`). Those wrapper entrypoints execute inside the
orchestrator containers (`campaign-wrapper` / `workflow-runner`), which mount NO socket (`2a`).
The broker's docker subprocess (`launch_broker.py:578` `docker run`; `:668` `docker compose run`;
`run_fleet_command` at `:696+`) therefore has no daemon to talk to when invoked in-container — the
Wave-2 change removed the socket AND added no host-side deployment of the broker, so the ladder's
reference containerized execution path is currently non-functional. The compose's own comments
(`:127-129`) assert the orchestrator services "run where the broker is reachable (host-side)" —
but nothing deploys such a broker; the in-process in-container call is the ONLY call path. The
follow-up's hard rule 2 — deploy the broker genuinely host-side with an IPC seam — targets a real,
present breakage.

### Edge 3 — f4: `system_snapshot.py:175` calls docker directly. **PASS**

```bash
grep -n "docker" scripts/system_snapshot.py
# 175  chroma_rows = _sh(["docker", "ps", "--filter", "name=chromadb", "--format", "{{.Names}} up {{.Status}}"])
# 177      add(f"- chromadb (docker): {chroma_rows}")
```

`scripts/system_snapshot.py:175` runs `docker ps` via the module's `_sh` subprocess helper
(`:32`) — exactly one docker call in the file, outside the broker. This is a second Docker API
caller (benign read-only — the chroma container's name/status for the game board), which the
broker's ONLY-caller rule forbids as an untyped caller. The spec's `current_state` line number
holds exactly. (The containerized `game-board` service — `docker-compose.ladder.yml:340` — runs
`system_snapshot.py` from an image built off the orchestrator's docker-CLI stage with NO socket,
so this call cannot even succeed in the containerized deployment.)

### Edge 4 — f6: stale socket-holder prose remains (Containerfile + agent surfaces). **PASS**

**4a. The Containerfile still describes the orchestrator as the socket-holder.** The b3 change
removed the socket from the compose, but `Containerfile.fleet` still describes the pre-b3 state:

```bash
grep -n "socket" Containerfile.fleet
#  36  # the orchestrator/workflow-runner container itself (the one socket-holder) is unaffected.
#  48  # the socket in exactly one tier, every tier on fleet-net only).
# 155  # The orchestrator is the ONE socket-holder (D-3): it mounts /var/run/docker.sock ro and its
# 157  # every spawn against the mount contract + scope vocabulary before the socket call. It needs
# 158  # only the docker CLIENT (`docker-cli` — talks to the host daemon over the socket); …
# 179  # socket at runtime (D-3/D-14) — its restart authority is the compose policies it owns plus
```

`Containerfile.fleet:155-158` ("The orchestrator is the ONE socket-holder (D-3): it mounts
`/var/run/docker.sock` ro …") is the exact pre-b3 reality the compose's own comments (`2a`) now
contradict. Lines `:36`, `:48`, and `:179` carry the same socket-in-container framing.

**4b. The agent surfaces (generated from `agent_config/`) carry the same stale prose.** The
source files and their renders both describe the container mounting the socket:

```bash
grep -n "docker.sock\|docker socket call\|socket lives in exactly one tier" agent_config/*.md \
  agent_config/skills/*.md
# agent_config/rules.md:114          "… write flags — validated before the docker socket call). … (one orchestrator at a time — the socket lives in exactly one tier)"
# agent_config/skills/run-workflow.md:124  "OPT-IN. The container mounts the docker socket (ro); a phase"
# agent_config/skills/run-workflow.md:125  "whose scope fails validation refuses BEFORE the socket call."
# agent_config/skills/run-workflow.md:174  "checked BEFORE the docker socket call). The fleet runs one orchestrator at a time (the"
# agent_config/skills/run-workflow.md:175  "socket lives in exactly one tier), so don't start a second orchestrator…"
```

Those render into the generated surfaces — `.opencode/skills/run-workflow/SKILL.md:124,174` and
`.claude/skills/run-workflow/SKILL.md:124,174`, and `rules.md` into `AGENTS.md`/`CLAUDE.md`/the
`.opencode`/`.claude` rule surfaces. All describe the socket-in-container state that
`b3_launch_broker` removed — the exact prose the follow-up's hard rule 4 ("no committed prose
describes the pre-b3 socket-holder state") and fb3's surface-changes-through-the-generators
mandate target.

---

## 3. Verdict summary

| # | Mandate edge (as stated) | Status at the pin |
|---|---|---|
| 1 | f2 — the per-run clone is created but never mounted; cells still mount `/tmp` rw + shared `.git` rw | **PASS** — lifecycle exists (`run_clone.py:130/222/256`) with ZERO production callers; the clone is a broker-validated reference only (`spawn_wrapper.py:1023-1024`, `launch_broker.py:159/440-460`, never added to the mounts in `mounts_for_profile:269-294`); cells mount shared `/tmp` rw + both shared `.git` dirs rw (`mounts_for_profile:270-281`, compose `:69/:74/:134/:139`, `FIXED_CONTRACT_TARGETS:184-191`) — confirmed by a live `implementation_rw` dump with no clone path |
| 2 | f3 — the compose has no socket mount and nothing host-side invokes the broker | **PASS** — zero `/var/run/docker.sock` mounts (compose socket matches are all absence-comments `:12-17/:92/:124-130/:163/:297/:315`); no broker service in the yml (`campaign-wrapper:300`, `workflow-runner:306` only) and no host-side unit/daemon (infra units = docs-drift-scan + fleet-bootstrap only); the broker is called in-process by the in-container wrapper (`spawn_wrapper.py:83/837/1171/1335/1368`), so the socketless containerized path cannot reach docker |
| 3 | f4 — `system_snapshot.py:175` calls docker directly | **PASS** — `system_snapshot.py:175` (`_sh(["docker", "ps", …])`) is the file's only docker call, outside the broker |
| 4 | f6 — stale socket-holder prose remains in the Containerfile + agent surfaces | **PASS** — `Containerfile.fleet:36/48/155/157-158/179` (orchestrator "the ONE socket-holder" mounting `/var/run/docker.sock` ro); `agent_config/rules.md:114` + `agent_config/skills/run-workflow.md:124-125/174-175` and their renders (`.opencode`/`.claude` skills + the root surfaces) |

**Pin verdict: all four follow-up edges are CONFIRMED against the actual code — each with code +
command + (for edge 1) a live-request dump as evidence, none asserted.** The created-but-unmounted
clone + the still-shared `/tmp`/`.git` cell mounts are the `fb1_clone_mounted` mandate's ground
truth; the socketless compose with no host-side broker is `fb2_broker_hostside`'s; the
`system_snapshot.py:175` direct docker call is fb3-f4's; the Containerfile + agent-surface
socket-holder prose is fb3-f6's. The four findings above are the baseline the implementation
phases and the independent adversarial review (`fb4_adversarial`) will be measured against.

---

## 4. Deviations recorded against the pinned bytes / mandate

Recorded per the D-series convention. Each deviation is a correction to the spec's stated
baseline that the implementation phases should consume; none changes the wave's work items.

**D-fb-1 — the clone lifecycle is not merely "never mounted"; it is not WIRED into any run path.**
The spec's `current_state` says the per-run clone "is created/discarded but never mounted". At the
pin the lifecycle module exists but has NO production caller (grep in Edge 1a: only unit tests
reference `create_run_clone`/`discard_run_clone`; `run_workflow.py` has zero clone references;
nothing exports `FINOPS_RUN_CLONE`), so in a real run today NO clone is created either — cells
execute in the pre-b2 shared-worktree shape unconditionally. `fb1_clone_mounted` must therefore
WIRE the lifecycle into the spawn/executor path (create per run, thread the path, mount it,
discard/sweep) as well as adding the mount contract + its validation — the wiring is part of the
deliverable, not a precondition that already holds.

**D-fb-2 — the prose is mixed, not uniformly stale: the compose comments already describe the
broker reality while the Containerfile + the agent surfaces still describe the socket-holder
reality.** `docker-compose.ladder.yml`'s comments (`:12-17`, `:124-130`) are b3-correct; the
stale text is confined to `Containerfile.fleet` (`:36/:48/:155-158/:179`), `agent_config/rules.md`
(`:114`) and `agent_config/skills/run-workflow.md` (`:124-125/:174-175`) + their renders. fb3-f6's
prose fix should sweep the stale surfaces through the generators and leave the already-correct
compose comments untouched.

**D-fb-3 — the containerized `game-board` service runs `system_snapshot.py` from an image that
inherits the docker CLI but no socket** (`docker-compose.ladder.yml:340`; `Containerfile.fleet`
builds `supervisor FROM orchestrator`, which installs `docker-cli` at `:161-163`). The
`system_snapshot.py:175` docker ps therefore cannot succeed inside the containerized deployment
(no socket → the `_sh` call fails to the degraded branch), which is an additional, concrete
instance of the f3 breakage the fb-wave is closing — and a data point fb3-f4's
route-through-the-broker-or-document decision should account for.

---

## 5. LOG — PASS/FAIL per claim

| Claim | Attempts | Result |
|---|---|---|
| Edge 1a — the clone lifecycle exists but is not wired (no production caller) | 1 | **PASS** — `run_clone.py:130/222/256`; zero callers outside the module + its tests; `run_workflow.py` clean |
| Edge 1b — the clone is a reference, never a mount | 1 | **PASS** — `launch_broker.py:159/:440-460`; `mounts_for_profile` takes `run_clone` (`:224`) but never mounts it |
| Edge 1c — cells still mount `/tmp` rw + shared `.git` rw | 1 | **PASS** — `mounts_for_profile:270-281`; compose `:69/:74/:134/:139`; `spawn_wrapper.py:184-191/:219-220` |
| Edge 1d — real-request dump carries no clone path | 1 | **PASS** — live `implementation_rw` expansion: shared `/tmp` rw + both `.git` overlays rw, no `runs_root/<run-id>/repo` mount |
| Edge 2a — no socket mount in the compose | 1 | **PASS** — socket matches are all absence-comments (`:12-17/:92/:124-130/:163/:297/:315`) |
| Edge 2b — no broker service/unit in the yml, nothing host-side invokes the broker | 1 | **PASS** — no broker service; infra units = docs-drift-scan + fleet-bootstrap only; no `.service`/`.sh` launcher |
| Edge 2c — the broker is invoked in-process by the in-container wrapper | 1 | **PASS** — `spawn_wrapper.py:83/837/1171/1335/1368`; orchestrator services `campaign-wrapper:300` / `workflow-runner:306` run in-container socketless |
| Edge 3 — `system_snapshot.py:175` calls docker directly | 1 | **PASS** — `_sh(["docker", "ps", …])` at `:175`, the file's only docker call |
| Edge 4a — stale socket-holder prose in the Containerfile | 1 | **PASS** — `Containerfile.fleet:36/48/155/157-158/179` |
| Edge 4b — stale socket-holder prose in the agent surfaces | 1 | **PASS** — `agent_config/rules.md:114`, `agent_config/skills/run-workflow.md:124-125/174-175` + renders (`.opencode`/`.claude` SKILL.md + root surfaces) |
| Pin integrity — spec SHA256 + worktree sha recorded | 1 | **PASS** — `8f953b36…` / `86b148027…`, spec byte-identical in both trees |

No edge required more than one reproduction attempt; no failed finding. Preregistration committed
as `[workflow] fb0_pin_spec — Complete the two half-deliveries the fleet_launch_boundary
adversarial review found NOT merge-ready (fb1 clone-mount + fb2 host-side broker + fb3
stragglers)`.
