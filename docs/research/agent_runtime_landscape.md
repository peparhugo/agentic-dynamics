---
status: proposed
---

# Agent-runtime landscape — external tools vs this system, and adoptable mechanisms from their open code

**Date:** 2026-09-13
**Status:** proposed (research complete; recommendations only — nothing adopted, nothing built)
**Origin:** a research session requested by the controller ("part of the team uses Herdr + Moshi; I use
Conductor; Omarchy is getting attention"). Two follow-up passes: open-source code analysis of Herdr and
Omarchy, then a UI/UX facelift brief from four community reference apps (stored separately in
`docs/research/control_room_ui_reference_synthesis.md`).
**Claim discipline:** `[X]` external observation from the named repo/URL at the pinned commit; `[M]`
measured in this repository with a `file:line` anchor; `[P]` local policy/recommendation, never an
adopted decision.

---

## 1. Why this evaluation exists

Four agent-era products are circulating in the team: **Herdr** (agent runtime / persistent terminal
server), **Moshi** (phone client for agents over SSH/Mosh), **Conductor** (Mac app for parallel
isolated-agent workspaces), and **Omarchy** (agent-first Linux distribution). Herdr and Omarchy are
open source; Moshi and Conductor ship no source. This document compares all four against this
repository and extracts the mechanisms from the open code that are worth considering here. It is an
input to the controller's adoption decision, not an adoption.

The system this compares against: a queue-driven, headless, multi-model measurement platform — Redis
queue on 6380 + worker fleet, ephemeral worktrees (`feature/*` / `wt_*`) with a controller-only
permanence gate (`scripts/promote.py`), the Control Room portal, the flag-only supervisor rail, and the
admission/lease spend gate. See `AGENTS.md` and `agent_config/mental-model.md`.

## 2. Method and pins

- Live product pages fetched 2026-09-13 (`herdr.dev`, `getmoshi.app`, `conductor.build`, `omarchy.org`).
- Open code cloned shallow into `/tmp/opencode/research/` (scratch; commit shas recorded in §9). Line
  references below are against those shas.
- Deep passes by explore subagents over: Herdr's detection/persistence/API/plugins/client UI trees;
  Omarchy's crash flow, usage meters, dispatcher, skills provisioning, shell UI; the four reference
  apps' UIs; and this repository's existing surfaces. Every claim below is anchored.
- Moshi and Conductor: behavior only (closed source). Conductor's docs are the only evidence base.

## 3. What each tool is `[X]`

| Tool | Layer | Core claim |
|---|---|---|
| **Herdr** | Terminal/agent runtime (server) | Server-owned persistent terminals; agents survive detach/close/reboot; per-pane `working/blocked/idle/done` state; blocked-first triage; one CLI+socket API humans and agents both drive; 22 agent CLIs incl. opencode; multi-machine over SSH; plugins/hooks; Apache-2.0, Mac/Linux/Windows |
| **Moshi** | Remote client (iOS/Android/desktop) | Phone terminal over SSH/Mosh/ET straight to your machine (no session relay); `moshi-hook` adds agent awareness: chat view, agents/usages kanban, approvals on Watch/Live Activity, diff viewer, file browser, dev-server preview |
| **Conductor** | Desktop GUI (Mac) | Parallel Claude Code/Codex/Cursor/OpenCode, each task in an isolated workspace + branch + diff + review path; then PR/merge/archive; docs list checks and a Conductor API |
| **Omarchy** | OS/host | Opinionated Arch+Hyprland distro, agent-first (default agent at first boot, crash→agent diagnosis, skills to build plugins/themes); ships opencode/Neovim/terminals; plugin+theme ecosystem |

## 4. Mapping to this repository

| Their capability | Closest thing here `[M]` | Gap |
|---|---|---|
| Per-task isolated workspace + branch (Conductor) | Worktrees: pipeline/run_workflow ride `git worktree` on `feature/*`; story cells are stronger isolation — copytree + `git init` per cell (`src/agentic_dynamics/runtime/story/orchestration.py:212`) | Workspace lifecycle is script-driven, not visual; ephemeral until `scripts/promote.py` |
| Parallel agents, queue, workers (Conductor/Herdr) | Redis `story_jobs` on 6380, N independent `worker.py` BRPOP processes, dead-letter lane, heartbeats, recommended width ~6 from measured beta (`scripts/worker.py:170-187`) | Batch queue model, not interactive attach; no terminal session server |
| Review/merge path (Conductor) | `review_all.py` → trigger/enqueue/finalize workers; controller-only merges via `scripts/promote.py:102` | No diff viewer GUI; review is model-driven + CLI |
| blocked/idle triage (Herdr) | Supervisor: `healthy/stalled/off_track`, flags to `flags.jsonl`, flag-only (`scripts/supervise.py:1-10`); lease watchdog → flags + quarantine | States are advisory flags, not live pane semantics; no ack |
| Remote/phone access (Moshi) | Control Room portal (SSE, matrix/flags/analytics, mobile CSS), loopback by default; Tailscale noted for operator remote (`docs/postmortems/claude_oauth_clearing.md:40`) | No terminal streaming, no auth middleware, no approvals-from-watch; agent tool GET-only |
| Session persistence/resume (Herdr) | opencode SQLite store + `.instrument/session.jsonl`; `--session --fork` continuation, workflow `--resume` from ledger | No pane-history replay, no restart-restore of a live TTY |
| Agentic OS (Omarchy) | Host is Linux + docker + systemd user units + containerized workflow-runner | Different layer — workstation ergonomics; keep measurement runs containerized so distro drift cannot touch them |

**Already in-repo:** `workflows/repository/herdr_inspired_ux.yaml` — a pinned-source workflow
(`experiments/specs/STATUS.md:149`: runnable, 0 runs) that would produce blocked-state semantics, a
session-state contract, a one-API + wait-until-blocked primitive, and an adversarial adoption review.
The code-level findings below sharpen its h3–h5 specs.

## 5. Adoptable mechanisms from the open code `[X]` → here `[M]`/`[P]`

Dispositions are recommendations; none is adopted.

### 5.1 High value, small

1. **`seen` bit — "done" is not a detected state.** Herdr derives `Done = Idle + not seen`
   (`src/pane/state.rs:8-10`, `src/app/api_helpers.rs:96-107`) and orders attention
   `Blocked > Done > Working > Idle` (`api_helpers.rs:1-9`, max over panes in
   `src/workspace/aggregate.rs:50-75`). Notifications are re-validated against projected state so a
   stale "needs attention" cannot linger (`src/client/shell/notification_policy.rs:267-318`).
   *Here:* our supervisor flags have no ack semantics; adding a seen/ack bit gives blocked-first
   triage and kills stale-flag confusion. **Disposition: adopt-candidate (small).**

2. **Anti-flap hysteresis for state publishing.** Working→Idle requires 3 confirmations (100 ms
   rechecks, 700 ms cap); publish only on state/flag change plus a stable-blocker refresh every
   800 ms; a startup grace window suppresses false transitions
   (`src/pane/agent_detection.rs:5-13,23-78,140-168`).
   *Here:* supervisor flags and lease-watchdog emissions fire on a single observation; a
   confirmation window directly reduces noise. **Adopt-candidate (small).**

3. **Contract freeze for the control packet.** A generated JSON-Schema artifact is byte-compared in a
   freshness test (`src/api/schema/tests.rs:182-208`); per-method shape digests are frozen with the
   rule "add load-bearing behavior as a new advertised method" (`src/server/client_commands.rs:233-295`);
   a protocol-mismatch client sends only `ping` and exits (`tests/cli/protocol_guard.rs:68-84`).
   *Here:* `control-status/v1` has `validate_packet`; the shape-digest + add-never-mutate discipline
   is a direct fit. **Adopt-candidate (small).**

4. **Failure → agent triage rail (Omarchy crash flow).** A systemd user unit tails coredump journal
   `MESSAGE_ID`s (`bin/omarchy-crash-watch:12,49`), gates on: default agent exists, not its own
   machinery, per-program mute, 60 s dedupe (`:69-103`), then a notification whose `--exec` hands the
   agent metadata only plus a pointer to a **skill** — the agent runs `coredumpctl` itself
   (`bin/omarchy-agent-crash:33-52`, `default/agents/skills/diagnose-crash/SKILL.md:78-103`).
   *Here:* failed cells / dead-letter / timeouts deserve a structured "diagnose this run" handoff
   (metadata + skill pointer; agent fetches the rest) with mute/dedupe/exclude-self guards.
   **Adopt-candidate (medium).**

5. **Per-provider usage record contract (Omarchy meters).** One collector per provider writes validated
   JSON to a state dir with atomic `mv`; consumers pick up any record that appears, so adding a
   provider = adding a collector (`bin/omarchy-agent-usage-update:12,45-61`,
   `shell/plugins/agents/README.md:41-51`); collectors read transcripts, the opencode SQLite DB
   read-only (`bin/omarchy-agent-usage-claude:444-541`), and provider usage endpoints with a 15 s probe
   floor (`:800-846`); absent data hides rather than fabricates.
   *Here:* our usage/settlement stack is the same domain; this is a cleaner collector-registry shape
   and another expression of "unknown is never zero" (`core/cost_provenance.py`).
   **Adopt-candidate (medium).**

### 5.2 High value, medium

6. **Wait-until-blocked primitive.** `agent.wait --until <status>` defaults to `[idle, done, blocked]`
   (`src/api/wait.rs:523-535`); implementation is a hybrid: scan a 512-event ring for relevant
   changes, re-probe only then, 100 ms sleep otherwise, with an `after_state_change_seq` gate so a
   stale match cannot return instantly (`wait.rs:364-514,552-559`; `event_hub.rs:12-26`); distinct
   errors for timeout vs agent-gone. *Here:* exactly the h5 target in `herdr_inspired_ux.yaml`, now
   with a proven design to copy instead of inventing. **Adopt-candidate (medium).**

7. **Evidence-precedence arbitration.** State is a merge of sources with explicit authority: live
   full-lifecycle hooks override screen detection; session-identity-only integrations are refused state
   authority; a visible blocker may override a non-authoritative hook for the same agent but never the
   authority (`src/terminal/state.rs:120-151,645-647,1807-1812,1853-1864,2151-2192`).
   *Here:* the fact plane / measurement rules could adopt explicit source precedence instead of
   last-write-wins — the single-writer discipline applied to derived state. **Adopt-later.**

8. **Data-driven detection manifests with out-of-band updates.** Detection rules are TOML data
   (priority, region vocabulary, `contains|regex|line_regex`, nested all/any/not), bundled,
   remote-updatable from a catalog, with local overrides taking precedence
   (`src/detect/manifest.rs:138-198,239-262,600-697,1130-1136`; `manifest_update.rs:16`). Unknown
   screen shape falls back to Idle rather than guessing.
   *Here:* if state classifiers are ever formalized, ship them as versioned data with an override
   layer, not prompt text. **Adopt-later.**

9. **Plugin event hooks with deliberate negative space.** Only 22 low-volume event kinds are hookable;
   high-volume ones are policy-excluded and tested (`src/api/schema/events.rs:286-309,350-358`);
   hooks spawn fire-and-forget with context in env vars, capped at 32 in-flight / 64 KiB per stream
   (`src/app/api/plugins/runtime.rs:11-13,82-102`); hooks run before the hub push and metadata updates
   bypass them to prevent recursion (`src/app/api.rs:748-771`). Trust model is explicit: review, no
   sandbox (`docs/.../plugins.mdx:49-52`).
   *Here:* for campaign operators/hooks, copy the exclusions, caps, and recursion rules — not the
   no-sandbox trust model (our outbox writers must stay governed). **Adopt-later.**

### 5.3 Worth knowing, lower priority

10. **Persistence mechanics.** Atomic tmp+rename writes; snapshot version + migration; warn-and-ignore
    when the on-disk version is from the future (`src/persist/io.rs:44-61,128-137`); debounced save +
    save-on-shutdown (`src/app/mod.rs:43`, `src/server/headless.rs:722-725`); native resume suppresses
    pane-history replay so context is not duplicated (`src/persist/restore.rs:744-778`); resume
    commands as a per-agent data table, deferring the resume keystroke until terminal geometry is known
    (`src/agent_resume.rs:136-256`).
    *Here:* resume-table-as-data and no-double-context rules apply to adapters'
    `--session`/`--resume` paths. **Study.**

11. **Two-lane API with an allowlist + remote posture.** Scripts/agents get newline-JSON on one
    socket, the UI a separate binary lane restricted by `CLIENT_SHELL_METHODS`
    (`src/server/client_commands.rs:15-58`); remote is `ssh -T` carrying the framed protocol over
    stdio — no TCP forwarding — with opaque profile ids so storage keys do not leak targets and a
    restart-policy enum `KeepRunning | LiveHandoff | StopRequired(reason)`
    (`src/remote/attach.rs:574-587`, `src/client/endpoint/catalog.rs:62-89`,
    `src/remote/restart_policy.rs:16-62`).
    *Here:* relevant only if the fleet spans machines; the agent-facing GET-only tool already
    implements the allowlist idea by construction. **Study (multi-machine).**

12. **Omarchy's dispatch/metadata trick and skills provisioning.** The CLI scans `bin/omarchy-*` and
    parses `# omarchy:` headers, so the command surface is self-describing and
    `omarchy commands --json` is machine-readable (`bin/omarchy:6,205,315-322,672-689`); skills are
    symlinked from one source into every agent's skills dir (`bin/omarchy-provision-user:84-104`).
    *Here:* a machine-readable command manifest for `agentic-dynamics` would help agents; host-level
    skill provisioning would let any agent on this box see our ops skills. **Study.**

### 5.4 What not to copy `[P]`

- **Screen-scraping as primary detection.** Herdr's per-agent fallback heuristics are a maintenance
  tax they mitigate with hooks/manifests; we have structured signals (session.jsonl, SSE, ledger).
- **The terminal-server architecture itself.** It solves interactive supervision; our unit of work is a
  batch cell and the queue + ledger is the better measurement substrate.
- **Plugin trust model (no sandbox)** and **live PTY handoff via fd passing** — out of proportion to
  our authority/lease rails today.
- **Moshi/Conductor cannot be adopted as orchestration layers:** Conductor is Mac-only and
  single-developer-GUI shaped; Moshi is a client, not a control plane. Their concepts (workspaces,
  review path, remote triage) already exist here in governed form.

## 6. Questions for the controller

1. Run `workflows/repository/herdr_inspired_ux.yaml` (runnable, 0 runs) to turn §5.1–5.2 into pinned
   specs with adversarial review? It is the already-authored vehicle for exactly this.
2. Which §5 items are worth a wave — the small ones (1–3) are cheap; 4–6 are medium.
3. Is the multi-machine question (§5.11) live enough to matter now?

## 7. Cross-reference

- UI-focused findings from Herdr's client and Omarchy's shell, plus the four community reference apps
  and the Control Room facelift direction, live in
  `docs/research/control_room_ui_reference_synthesis.md` (same branch).

## 8. Sources and pins

External pages (fetched 2026-09-13): `https://herdr.dev/` and `/docs/`; `https://getmoshi.app/`;
`https://www.conductor.build/` + `/docs`; `https://omarchy.org/`.

Cloned at (fresh shallow clones; scratch paths are ephemeral):

| Repo | Commit | Used for |
|---|---|---|
| `github.com/herdrdev/herdr` | `981fe83ca2e23474255f4cacc4da2814f9de0744` | detection, persistence, API, plugins, client UI |
| `github.com/omacom/omarchy` | `8247eb36b7ce7727ccdb5680ca64e207eae9bb0c` | crash flow, usage meters, dispatcher, shell UI |
| `github.com/Hastur-HP/The-Brain` | `f336e7c9489a867f926a9bf1cfa216deb816a024` | UI reference (see synthesis doc) |
| `github.com/Wadera/clawboard` | `9b3d6905070cbabf18a1df84687dd57b924f56b9` | UI reference |
| `github.com/BovineDawn/TheColony` | `ea8d407ab81ec03992976c2e4831a4d5589e7c2b` | UI reference |
| `github.com/OpenVizAI/OpenVizAI` | `faf667f0192f29d97c5e6607536175a40ef269d3` | UI reference |

In-repo anchors: `experiments/specs/STATUS.md:149` (herdr spec state), `scripts/worker.py:170-187`,
`src/agentic_dynamics/runtime/story/orchestration.py:212`, `scripts/promote.py:102`,
`scripts/supervise.py:1-10`, `docs/postmortems/claude_oauth_clearing.md:40`.
