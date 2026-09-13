---
status: proposed
---

# Control Room — UI reference synthesis v2 (extends v1)

**Date:** 2026-09-13
**Status:** proposed (research only; no implementation in this phase).
**Phase:** `a0_deep_research` of `workflows/repository/control_room_facelift_review.yaml`.
**Relationship to v1:** this document **extends** `docs/research/control_room_ui_reference_synthesis.md`
(hereafter **v1**) and never deletes it. V1 is the facelift proposal; v2 is the reference sweep that
tests it against a wider, pinned, 2025-2026 source base. §6 is the required reconciliation.
**Relationship to the accepted direction:** this document presupposes
`docs/research/control_room_direction.md` (status: accepted, "the live run as the unit of work") and the
v1 facelift brief (v1 §4). It does not re-litigate the run object, the evidence classes, the
removed-generic-elements list, or the restraint budget; it grounds them in new evidence and — where the
new evidence disagrees with v1 — it says so in §5 (conflicts) and §7 (adversarial findings).
**Claim discipline** (same as v1, §4.0): `[X]` external observation at the pinned URL/commit; `[M]`
measured in this repository with a `file:line` anchor; `[P]` local recommendation, never an adopted
decision. Every external claim carries a pin (§2). No unpinned external claim appears below.

---

## 0. Method, budget, and what changed

The protocol is the one the agent-runtime-ui-research session used, named in the phase prompt:
**sweep → pin → extract → dispose → reconcile**. Concretely:

1. **Sweep** the open web and GitHub topic indexes for 2025-2026 operator-console, agent-fleet,
   observability-wall, and incident-console material (§1).
2. **Pin** the strongest sources at full commit SHAs (or URL + access date for non-git pages) (§2).
3. **Extract** mechanisms, not screenshots — naming, state vocabularies, layout grammars,
   interaction patterns, animation policy, accessibility handling, data-density decisions — each with
   a `file:line` anchor in the pinned source (§3).
4. **Dispose** every mechanism `ADOPT` / `ADAPT` / `DO-NOT-COPY`, one line of reason tied to the
   accepted direction and the v1 facelift brief (§4).
5. **Reconcile** every new idea against v1 and the direction: *presupposed / extends / conflicts* (§6).

**Budget.** Twelve repositories were cloned shallow into `/tmp/opencode/research` (ephemeral);
**nine** were read deeply (the 5-8 depth budget, stretched by one for the on-thesis `DashClaw` find);
the rest are recorded as sweep-only with a disposition in §1.3. Clones are disposable; the pins in §2
are the durable artifact.

**Delta versus v1.** V1 extracted mechanisms from Herdr, Omarchy, Clawboard, The Colony, The Brain,
OpenVizAI, and call-center dashboards. V2 adds sources v1 did not have — the run/workflow engines
(**Temporal UI**, **Hatchet**, **Dagu**), the agent-observability surfaces (**Langfuse**,
**OpenHands**), a status-page/monitoring grammar (**Uptime Kuma**), and — most consequentially — an
open-source **governance/approval console** (`DashClaw`) that is structurally the same product as this
Control Room's decision boundary. V2 also adds the live-agent fleet dashboards the phase prompt named
via the GitHub topics (**herdr-portal**, **lazyagent**, **herdr-f1**). The largest thing v2 changes is
not an addition but a correction: several of v1's proposals **conflict** with the accepted direction,
and §5/§7 name them (the R0 wallboard, status-rhythm animation, the LLM chart lens, the computed health
score, and the R3 KPI treatment).

---

## 1. SWEEP — the 2025-2026 landscape

### 1.1 How the sweep was bounded

The sweep used GitHub topic indexes (the phase prompt's named entry points) plus the repository graph
they exposed (a cloned repo's `frontend/`, `ui/`, `web/` trees), then followed the strongest
on-thesis match. Topic-page counts are `[X]` observations at access date **2026-09-13**:

| Topic | Repos | Read of the field |
|---|---|---|
| `github.com/topics/agent-dashboard` | 46 | Small, fast-moving, mostly single-binary monitors for Claude Code / Codex / OpenCode. Newest and closest to this room's fleet. |
| `github.com/topics/ai-ops` | 214 | Broad AI-for-ops and ops-for-AI. Surfaced the governance/approval console (`DashClaw`) and an "autonomy is earned" governance repo (`OpenMAO`). |
| `github.com/topics/observability-ui` | **0** | The topic is unused; "observability UI" is not a meaningful index — the material lives under `dashboards`, `monitoring`, and the named products. Recorded as a negative sweep finding: there is no community "observability wall" canon to borrow from, only products. |

### 1.2 Source roster (deep reads)

| # | Source | Layer | Why it earned a deep read |
|---|---|---|---|
| 1 | **Temporal UI** | workflow engine console | The most complete public treatment of "a run is an addressable object with an event-sourced life", plus status counts that are filters and a debounced live-region announcer. |
| 2 | **Hatchet** | workflow engine console | Run detail with a step-run tab set, a mini-map DAG, and a live trace timeline; a contrasting (throwing) unknown-status policy. |
| 3 | **Dagu** | local workflow runner | Compact status vocabulary, per-node status chip and table, runtime-condition summary — the cleanest small grammar. |
| 4 | **Langfuse** | agent/LLM observability | Dense trace timeline with a playback playhead, a size-gated JSON viewer, and a resizable split layout with explicit comfort minima. |
| 5 | **OpenHands** | agent run console | Run status badge with degrade-on-unknown and reduced-motion policy; phase + age presentation; log-scale activity sparkline with an honest "unknown" bar. |
| 6 | **Uptime Kuma** | status page / monitoring | A keyboard- and screen-reader-accessible canvas heartbeat bar; status pill and uptime sanity rules; incident history. |
| 7 | **DashClaw** | **governed approval/decision console** | Structurally the same product as the Control Room's decision boundary: approvals inbox, policy evaluation, causal decision timeline, evidence tabs, receipts, flood/pause control, live-liveness honesty. The single most on-thesis source. |
| 8 | **herdr-portal** | live agent-fleet dashboard | Dynamic zero-footprint attention column, click-to-land, reply-to-agent, fingerprint-skipped redraws, reconnect-keep-last-data, multi-theme. |
| 9 | **lazyagent** | live agent-fleet dashboard | `compact`/`rich`/`live` density switch, per-card resume actions, per-session sparkline, provider window/pace limits. |
| 10 | **Netdata** | observability wall (docs) | Per-second charts, synced hover, anomaly advisor, alert state (warning/critical). Used as the negative comparator for "chart wall". |

### 1.3 Sweep-only longlist (cloned or observed, not deeply read)

| Candidate | Pin | Disposition |
|---|---|---|
| `OpenMAO/OpenMAO` | `6333832b8b57b8c4de0f3e3d275505206e1b487c` | **Sweep-only.** "Autonomy is earned, not assumed" and an organization-of-record over agents. It presupposes the direction's authority model rather than showing a UI mechanism; no extract. |
| `Temaki-AI/clawd-control` | `0ed74f55cc6ce3d39eb3c52d0c7a03c9f2d9ed77` | **Sweep-only.** Real-time Clawdbot monitor, single-file HTML; strictly less structured than DashClaw, which covers the same ground better. |
| `hmu332233/herdr-f1` | `9af4d2af82da1fe71b3ef8a8d31ba0edf3c326b0` | **DO-NOT-COPY** (§4.3): gamifies agents into race cars with explicitly fictional laps/points. Named here as the anti-pattern that the direction's "no invented telemetry" already forbids. |
| `netdata/netdata` (dashboard source) | `0a4ce7db5fa329c8a9c1a4b82e78ee2af9750072` | **DO-NOT-COPY** as a model (§4.3); the docs are cited only to name the "chart wall" comparator. |
| `henrygd/beszel`, `langgenius/dify`, `PrefectHQ/prefect` | — | **Not cloned.** Beszel's UI is not in the server repo; Dify/Prefect are broader than the run-console question and would duplicate the workflow-engine finds. Recorded, not read. |

### 1.4 What the 2025-2026 field converges on (one paragraph)

Three cross-source patterns are now common enough to be conventions rather than opinions: (a) **status
is a countable, filterable dimension** — every workflow/run console renders per-state counts and makes
them the filter (Temporal, Hatchet, Dagu, OpenHands); (b) **the run detail is a tabbed/regioned object
with a timeline, not a log** — Output/Input/Logs/Traces/Activity (Hatchet), timeline/graph/evidence/
policies/assumptions (DashClaw); and (c) **independent verification is a distinct, separately-styled
artifact** (a receipt, a probe, an eval) rather than an assertion inside the agent's narration
(DashClaw, Langfuse, Hatchet). All three are already in the accepted direction; the field is evidence
that the direction is not idiosyncratic.

---

## 2. PINS — durable provenance

All repository reads were at the commit below (shallow clone, `git rev-parse HEAD`, 2026-09-13).
Non-git pages carry an access date. Line references in §3 are against these SHAs.

| Tag | URL | Pin |
|---|---|---|
| `[src:temporal-ui]` | https://github.com/temporalio/ui | commit `542fa634e7ae7b1441e82b2a1beb4717811430d8` |
| `[src:hatchet]` | https://github.com/hatchet-dev/hatchet | commit `315d43a72fd771b049b304b865a81dbab98c466c` |
| `[src:dagu]` | https://github.com/dagu-org/dagu | commit `2635b927b345a2ecadc89462276c6a82f062eabe` |
| `[src:langfuse]` | https://github.com/langfuse/langfuse | commit `6d298ec5d618ab236d8aacb6e59fa9daf59bb3a0` |
| `[src:openhands]` | https://github.com/All-Hands-AI/OpenHands | commit `28464621d879e3e9b3ceeae9d70a71d96da6212d` |
| `[src:uptime-kuma]` | https://github.com/louislam/uptime-kuma | commit `3afdc9ca86752587cc5a88147403194b5f83196d` |
| `[src:dashclaw]` | https://github.com/ucsandman/DashClaw | commit `275c6f3338129967d32ed36d447bdd3493c810fc` |
| `[src:herdr-portal]` | https://github.com/loofare/herdr-portal | commit `cae8ea07a51f54d6e73b6e5a40d0930c8d4f074f` |
| `[src:lazyagent]` | https://github.com/illegalstudio/lazyagent | commit `2be879c1660ad9f7592f1869e67a8f60243dc773` |
| `[src:herdr-f1]` | https://github.com/hmu332233/herdr-f1 | commit `9af4d2af82da1fe71b3ef8a8d31ba0edf3c326b0` |
| `[src:netdata-docs]` | https://github.com/netdata/netdata/tree/0a4ce7d/docs/dashboards-and-charts | commit `0a4ce7db5fa329c8a9c1a4b82e78ee2af9750072` |
| `[src:openmao]` | https://github.com/OpenMAO/OpenMAO | commit `6333832b8b57b8c4de0f3e3d275505206e1b487c` |
| `[src:clawd-control]` | https://github.com/Temaki-AI/clawd-control | commit `0ed74f55cc6ce3d39eb3c52d0c7a03c9f2d9ed77` |
| `[src:gh-topic-agent-dashboard]` | https://github.com/topics/agent-dashboard | accessed 2026-09-13 |
| `[src:gh-topic-ai-ops]` | https://github.com/topics/ai-ops | accessed 2026-09-13 |
| `[src:gh-topic-observability-ui]` | https://github.com/topics/observability-ui | accessed 2026-09-13 |

Local (repository) references are `[M]` with `file:line` against `main` at the phase commit; the live
room inventory is carried from v1 §1 `[M]` (re-verified: `apps/control_room/static/app.js` is 1306
lines, `index.html` 321, `parity.js` 2350; `app.js:463` still holds the dead
`STATE_RANK {active,new,stale,snoozed,resolved}` vocabulary; the room still has one
`EventSource("/api/events")` at `app.js:999`; `safe_actions` still render read-only at
`parity.js:1802`; `.opencode/tools/control_room.ts:7` still declares GET-only).

---

## 3. EXTRACT — mechanisms with anchors

Every row is a mechanism (not a screenshot): what it is, what it does, and the anchor. Dispositions are
in §4; reconciliations are in §6.

### 3.1 Run/work item as an addressable object

| ID | Mechanism | What it does | Anchor |
|---|---|---|---|
| T1 | **Run history as an event-sourced list of typed events** | Each event is a card keyed by its id (deep-linkable), with a display name, timestamp, typed attribute rows, payload code blocks capped at `maxHeight: 384`, an optional call stack, and links to related executions. The list *is* the causal record, not a log tail. | `[src:temporal-ui]` `src/lib/components/event/event-card.svelte:126-177, 258-316` |
| T2 | **Status vocabulary as a first-class filter set** | The statuses are an exported const tuple; filters are `'All' + statuses`. A status label map has an explicit `unknown` fallback. | `[src:temporal-ui]` `src/lib/models/workflow-status.ts:5-25`; `src/lib/utilities/get-workflow-status-label.ts:24-27` |
| T3 | **Counts-as-filters with a trend delta** | One count badge per status; the badge carries the count and the *difference since last refresh* as an extension. | `[src:temporal-ui]` `src/lib/components/status-counts.svelte:62-84` |
| T4 | **Query-grammar filter chip** | A status filter is a chip that composes into a query string with `OR` and parentheses; an accessible checkbox menu; the chip's `title` shows `attribute = values`. | `[src:temporal-ui]` `src/lib/components/search-attribute-filter/status-filter-chip.svelte:65-108, 141-165` |
| T5 | **Pending vs retry vs completed-with-retries are distinct marks** | The event-history legend renders `Pending` and `Retry` as their own keys; "Completed with retries" is a gradient between success and failure. The legend carries dots, category icons, and titles. | `[src:temporal-ui]` `src/lib/components/lines-and-dots/event-history-legend.svelte:24-50, 99, 124` |
| HT1 | **Run detail as a tab set** | Output / Child-workflow-runs / Input / Logs / Traces / Additional-metadata / Activity — the run is one object with orthogonal regions. | `[src:hatchet]` `frontend/app/src/pages/main/v1/workflow-runs-v1/$run/v2components/step-run-detail/step-run-detail.tsx:35-42` |
| HT2 | **Mini-map DAG with a computed column layout** | Step nodes are laid out into columns by parent depth, then rendered as a navigable mini-map that opens the clicked step with a default tab. | `[src:hatchet]` `frontend/app/src/pages/main/v1/workflow-runs-v1/$run/v2components/mini-map.tsx:63-116` |
| HT3 | **Live trace timeline** | Span rows on a shared time axis; in-progress spans extend to a `useLiveClock` "now"; rows have a fixed `ROW_HEIGHT`; a visible range controls windowing. | `[src:hatchet]` `…/observability/timeline/trace-timeline.tsx:52-85, 157` |
| D1 | **Compact status vocabulary** | Nine states with lowercase display labels (`not started`, `running`, `failed`, `aborted`, `success`, `queued`, `partial`, `waiting`, `rejected`). | `[src:dagu]` `ui/src/features/dags/components/common/statusLabels.ts:8-18` |
| D2 | **Per-node status chip + status dot** | A chip pairs status class, size, and — for active states — a braille spinner marked `aria-hidden`; running labels use a subtle matrix-text animation. The dot pairs color with a `title`. | `[src:dagu]` `ui/src/features/dags/components/common/NodeStatusChip.tsx:12-24, 53-72`; `…/common/StatusDot.tsx` |
| D3 | **Status overview + runtime conditions** | A unified node-status config and an execution-status config (icon + message per state); a `Runnable` summary condition plus a filter that surfaces only *failed* detail conditions. | `[src:dagu]` `ui/src/features/dags/components/dag-details/DAGStatusOverview.tsx:48-90, 112, 125-133` |
| D4 | **Per-node status table with gated row actions** | One row per node; a log-view action per row; actions column shown only when the actor has the `runDags` permission. | `[src:dagu]` `ui/src/features/dags/components/dag-details/NodeStatusTable.tsx:29-56` |
| C1 | **The decision record as a multi-tab object** | A decision page with Timeline / (chronological + causal) / Graph / Evidence / Policies / Assumptions / Signals tabs, plus a replay sidebar; a containment-lifecycle chip is a *separate* column from the action's status. | `[src:dashclaw]` `app/decisions/[actionId]/page.tsx:31-42, 296-297, 471-533` |
| L1 | **Trace tree + dense timeline + playback playhead** | A trace is a tree and a time axis; a vanilla-Zustand playhead engine drives a ~60fps position via imperative DOM writes while discrete flags go through React; the store syncs geometry hard on trace change and soft on same-trace churn. | `[src:langfuse]` `web/src/features/traces/contexts/PlayheadContext.tsx:1-14, 38-67, 91-100` |

### 3.2 State vocabularies and status marks

| ID | Mechanism | What it does | Anchor |
|---|---|---|---|
| O1 | **Degrade on unknown status** | A badge looks up the config by status and falls back to `PENDING` when the backend adds a status the client does not know, instead of throwing. | `[src:openhands]` `src/components/features/automations/detail/run-status-badge.tsx:140-143` |
| O2 | **Status is icon + label + color, never color alone** | Status icons are distinct per state (check / x / spinner / alert / help / clock); the badge carries a label by default; an `iconOnly` variant adds a tooltip and `aria-label`. | `[src:openhands]` `…/run-status-badge.tsx:66-127, 146-175` |
| O3 | **Reduced-motion is honored in the status mark** | The running spinner is `animate-spin motion-reduce:animate-none`. | `[src:openhands]` `…/run-status-badge.tsx:103` |
| O4 | **Phase text + phase age** | A run's current phase is shown only for in-flight or failed runs; its *age* only for in-flight runs (a failed run's phase is where it stopped, not a duration); unknown codes fall through to the author label, then to the raw code — never invented English. | `[src:openhands]` `src/components/features/automations/detail/run-phase.tsx:17-43, 65-114, 196` |
| O5 | **Coarse health derived from a fine status** | A single `deriveRunHealth` maps run status → `success`/`failed`/`warning`/`in_progress`/`none`/`unknown`, with a label key per health. | `[src:openhands]` `src/components/features/home/featured-automations/automation-run-health.ts:11-52` |
| HTx | **Throw on unknown status (contrast)** | A V1 run indicator throws `Unknown status` on an unhandled enum via an exhaustiveness check. Recorded as the *opposite* policy to O1; the room follows O1. | `[src:hatchet]` `frontend/app/src/pages/main/v1/workflow-runs-v1/components/run-statuses.tsx:21-22` |
| K1 | **Status pill with a text word always** | A status badge is class + a human word (`Down`/`Up`/`Pending`/`Maintenance`/`Unknown`); the pill has a `min-width` so labels align. | `[src:uptime-kuma]` `src/components/Status.vue:17-53` |
| C2 | **Containment lifecycle is independent of action status** | An action can be `completed` and still be `contained` / `awaiting_promotion` / `promoted` / `discarded`; `awaiting_promotion` is the only state that gets the brand-orange operator cue; every state pairs an icon with the label. | `[src:dashclaw]` `app/decisions/[actionId]/page.tsx:26-35` |

### 3.3 Attention and approval queues

| ID | Mechanism | What it does | Anchor |
|---|---|---|---|
| C3 | **A single approvals inbox as the primary human surface** | Pending and expired queues, plan review, containment, and grants all resolve on one page; two decisions per item; bulk actions fan out per item and a partial failure is surfaced (never rendered as a clean sweep). | `[src:dashclaw]` `app/approvals/page.tsx:96-150, 256-260` |
| C4 | **Approval-flood detection behind a labeled confirm** | When one policy floods the interrupt budget (`N interrupts in 15m`), a banner offers pause / bulk-allow / bulk-deny — each behind an explicit `Confirm`, with `autoFocus` returning keyboard focus to the flow and a "pending approvals stay pending" clarification on pause. Renders nothing when there is no flood. | `[src:dashclaw]` `app/components/ApprovalFloodBanner.tsx:12-18, 38-101` |
| C5 | **Approval-pause is a first-class, loud state** | A pause means the inbox is *not* the whole picture; the banner exists so a pause cannot read as "nothing needed you". | `[src:dashclaw]` `app/components/ApprovalPauseBanner.tsx:15-26` |
| C6 | **"Things you told me to stop asking about" strip** | Live grants are a strip above the pending queue with a revoke button inline; above 3 grants it collapses to a one-line count and opens a bounded list on demand; the countdown ticks in state (render stays pure). | `[src:dashclaw]` `app/approvals/_components/ActiveGrantsStrip.tsx:8-23, 81-108` |
| C7 | **Queue-unavailable is honest** | A failed refresh keeps the last list, sets `queue unavailable`, and shows "the last successful result from HH:MM:SS; retry before assuming the queue is clear". | `[src:dashclaw]` `app/approvals/page.tsx:103, 140, 456-457` |
| H1 | **Zero-footprint attention column that appears first** | The "waiting" column renders nothing until an agent stops for a human (approval or question), then it appears first and animates in. | `[src:herdr-portal]` `board/web/app.js:160-170`; `README.md` ("Dynamic waiting column") |
| H2 | **Click-to-land and reply-to-agent** | A card click switches the terminal to that workspace/pane and raises the host window; a reply box sends text to the agent's terminal (prompt when idle, simulated keystrokes while running). | `[src:herdr-portal]` `README.md` (web board / reply) |
| H3 | **Fingerprint plus reconnect keeps the room steady** | The server sends a data fingerprint; the client skips the redraw when nothing changed; on disconnect it keeps the last data and preserves scroll. | `[src:herdr-portal]` `board/web/app.js:283-290`; `README.md` ("Sturdy") |
| L2 | **Status-message presentation is a typed tone map** | ERROR→danger, WARNING→warning, DEBUG→muted, DEFAULT→neutral, with `assertUnreachable` for the closed set; structured status JSON is parsed only under a 5 000-char budget, else stays text. | `[src:langfuse]` `web/src/features/traces/components/IOPreview/components/statusMessagePresentation.ts:6-49` |

### 3.4 Evidence, receipts, and proof

| ID | Mechanism | What it does | Anchor |
|---|---|---|---|
| C8 | **A five-stage causal spine for one decision** | Goal Declared → Policy Evaluation (decision badge + reason + matched policies) → Assumption Check (validated/invalidated/unknown per assumption) → Risk Signals → Final Outcome, drawn as a connected vertical timeline with the full goal text wrapped in place. | `[src:dashclaw]` `app/decisions/[actionId]/_components/CausalTimeline.tsx:27, 40-49, 78-86, 101-106, 123` |
| C9 | **Evidence tab: side effects, artifacts, systems touched, raw payload** | Three typed evidence listings plus a `<details>` disclosure of the full decision JSON with a copy button. "No side effects recorded" is an explicit empty state, not a blank. | `[src:dashclaw]` `app/decisions/[actionId]/_components/EvidenceTab.tsx:20, 36, 51, 70-83` |
| C10 | **Receipt/bundle verification is stateless and paste-driven** | Paste a receipt or signed bundle; the endpoint verifies against the published keys and never reads the original record; the panel labels itself "stateless". | `[src:dashclaw]` `app/components/VerifyReceiptPanel.tsx:8-11, 41, 63-68` |
| C11 | **Enforcement-liveness honesty** | A synthetic liveness probe tests the installed seam and reports "stale or unavailable evidence" rather than a green mark; the thesis states a receipt does not prove external execution and a probe does not prove tamper-proof enforcement. | `[src:dashclaw]` `THESIS.md:47-48, 83` |
| C12 | **The human-experience contract** | Six clauses for every ship, including the *zero-terminal test* ("walk the entire human role; the count must be zero") and *rendered proof, not asserted proof* ("only a rendered page proves a human can see and use it"). | `[src:dashclaw]` `HUMAN-EXPERIENCE.md:31-82` |
| HT4 | **A step's vertical reads as an evidence ladder too** | Step detail keeps a separate `observability/span-detail` and a trace timeline beside Output/Logs/Input. | `[src:hatchet]` `…/observability/observability.tsx`; `…/timeline/trace-timeline.tsx` |
| T6 | **Payload rendering is bounded and lazy** | Payload code blocks take a `maxHeight` and a `lazy` flag; the stack trace is a labelled code block, not inline prose. | `[src:temporal-ui]` `src/lib/components/event/event-card.svelte:258-316` |

### 3.5 Layout grammars and data density

| ID | Mechanism | What it does | Anchor |
|---|---|---|---|
| L3 | **Split panes sized by a comfort target, not a fixed 60/40** | The tree gets a comfortable band (min 340, max 460 px) and the detail gets the rest, expressed as a percentage so the default is width-independent and stable across opens; when both panels' minima cannot fit, the group pins to the sum of minima inside an `overflow-x-auto` wrapper instead of force-collapsing one. | `[src:langfuse]` `web/src/features/traces/components/TraceLayoutDesktop.tsx:42-87, 115-116` |
| L4 | **Size-gated JSON rendering** | A single serialization probe decides whether a field is too large for the unvirtualized viewer; above 2 M chars (or 3 333 rows) it shows a bounded preview + download and skips the parse and full render. The comments state the measured crash point (~20 MB) and the safe parse bounds. | `[src:langfuse]` `web/src/features/traces/components/IOPreview/fns/jsonViewSizeGate.ts:1-40, 38, 59, 78` |
| L5 | **Object-type iconography with a color per type** | A single `iconMap` + `cva` variant maps every observation type (TRACE/GENERATION/EVENT/SPAN/AGENT/TOOL/CHAIN/RETRIEVER/EMBEDDING/GUARDRAIL/SESSION/…) to an icon and a color, so type is never textual only. | `[src:langfuse]` `web/src/components/ItemBadge.tsx:43-82, 101-121` |
| Y1 | **Density switch as a user preference** | A card grid with `compact`/`rich`/`live` densities; per-card normal and YOLO resume, an Editor action in a context menu, per-session sparkline, and an activity badge. | `[src:lazyagent]` `README.md` ("Desktop App"); `frontend/src/lib/SessionCard.svelte:10, 61, 113-118` |
| Y2 | **Provider window/pace limits** | A rate-limit summary for 5h/7d (and monthly) windows with a detailed pace view. | `[src:lazyagent]` `README.md` ("lazyagent limits"); `frontend/src/lib/LimitsPage.svelte` |
| Y3 | **Tiny inline sparkline as SVG** | A 120×24 SVG polyline + area path, max-normalized, per session. | `[src:lazyagent]` `frontend/src/lib/Sparkline.svelte:1-40` |
| O6 | **Log-scale duration bar with a status-driven color and an unknown height** | Activity bars on an 18 px track: duration maps log-scale to bar height (1s…30min), color stays status-driven, running pulses (`motion-reduce:animate-none`), pending is a hatch, and an unmeasurable duration uses a distinct `UNKNOWN` height rather than zero. | `[src:openhands]` `src/components/features/home/featured-automations/automation-run-activity-metrics.ts:9-17, 44-63, 74-96` |

### 3.6 Animation, accessibility, and streaming

| ID | Mechanism | What it does | Anchor |
|---|---|---|---|
| T7 | **Debounced, increases-only live-region announcer** | Tracks count increases, coalesces a batch over a 250 ms window, never announces the initial value or decreases, clears the region before re-announcing so an identical consecutive message still fires, and is framework-agnostic by design. | `[src:temporal-ui]` `src/lib/utilities/count-announcer.ts:7-52`; adapter `src/lib/components/live-count-announcer.svelte:24-25` |
| K2 | **Canvas mark that is still accessible** | The heartbeat bar is a `<canvas>` with `role="img"`, a computed `aria-label`, `tabindex="0"`, and keyboard/focus handlers — a graphical mark that remains reachable without a pointer. | `[src:uptime-kuma]` `src/components/HeartbeatBar.vue:4-16, 76-77` |
| K3 | **Status-page uptime sanity rule** | Uptime is rounded to two decimals and clamped to `100%` only on the public status page (with a comment linking the upstream issue) — an explicit guard against a computed value reading wrong in public. | `[src:uptime-kuma]` `src/components/Uptime.vue:35-39` |
| C13 | **Motion collapses under reduced-motion system-wide** | The hero decision record stages rows with a fade-slide keyframe, and the global `prefers-reduced-motion` block collapses the choreography to an instant render. | `[src:dashclaw]` `app/components/HeroDecisionRecord.tsx:1-13, 20-24` |
| N1 | **Synced hover + anomaly context** | Hovering a chart gives a cross-chart overlay; an anomaly-rate ribbon sorts dimensions by anomaly and a histogram shows the rates; an anomaly index ranks charts. | `[src:netdata-docs]` `docs/dashboards-and-charts/netdata-charts.md:326-364`; `docs/dashboards-and-charts/anomaly-advisor-tab.md:11-30` |
| N2 | **Alert state vocabulary** | The raised-alerts tab lists only `warning`/`critical`, with status as a filterable column. | `[src:netdata-docs]` `docs/dashboards-and-charts/alerts-tab.md:7-32` |

---

## 4. DISPOSE — one disposition per mechanism

Dispositions are tied to `docs/research/control_room_direction.md` (sections cited as `dir §n`) and the
v1 facelift brief (`v1 §4.x`). **ADOPT** = the mechanism is compatible and adds value as-is.
**ADAPT** = compatible in spirit but must be constrained to the direction's authority, evidence, or
restraint rules. **DO-NOT-COPY** = copying would violate the direction.

### 4.1 ADOPT

| Mechanism | Reason |
|---|---|
| T1 event-sourced event cards | Directly realizes the direction's typed evidence ladder (dir §2.4, v1 §4.2 R4); the deep-linkable event id is the typed address of dir Move 5. |
| T2 status const tuple + `unknown` fallback | The direction's two-axis status language (dir §12.2.5) needs one closed vocabulary; the fallback matches the run-state contract's "never re-derived" rule. |
| T4 query-grammar filter chip | Counters as filters (v1 §4.5.4) need an addressable grammar; the chip keeps filter state visible and testable. |
| T5 pending/retry/completed-with-retries marks | The direction forbids fabricated values (dir §8); distinct marks for partial and pending states are the honest rendering. |
| HT1 run detail as orthogonal regions | Exactly the evidence-ladder composition (dir §2.4); v1 §4.2 R4 proposes the same. |
| HT2 mini-map DAG | The pipeline lens (v1 §4.5.2) is a per-run phase grid; the computed column layout is the reusable part. |
| D1 lowercase status labels | The direction's restraint budget (dir §4.5) prefers labels over telemetry texture; lowercase labels are calm and pair with a word. |
| D4 per-node table with gated actions | Realizes dir Move 3 (rows show eligibility, not a button) at the step level; permission-gated actions are the repository's own authority model. |
| C1 decision record as a multi-tab object | The single strongest external validation of v1 §4.2 R4/R1: one decision, many typed faces, no board hopping (dir §3.2). |
| C2 containment lifecycle separate from action status | Mirrors the repository's promote/quarantine lifecycle (dir §2.2); a run can be "done" and still need a human — the direction's core claim. |
| C3 single approvals inbox | The direction's attention inbox (dir §3.3) and v1 §4.2 R1; it is a work queue, not a card wall. |
| C4 flood detection behind a labeled confirm | Attention must be a durable work queue, not a ping storm (dir §3.3, Move 8); the confirm keeps the human the actor. |
| C5 loud approval-pause state | "An unknown/blocked state must never read as all-clear" is the direction's truth rule (dir §8, §9). |
| C6 grants strip with inline revoke | A P1 standing grant is a lease; showing and revoking it on the surface that created it keeps the authority model legible. |
| C7 queue-unavailable honesty | "Green never lies" (dir §8); this is the exact wording the room should use when its control packet fetch fails. |
| C8 five-stage causal spine | The evidence ladder's causal shape (dir §2.4, Move 2) rendered for one object. |
| C9 evidence tab + raw-payload disclosure | The per-value provenance rule (dir §8) plus a bounded raw fallback; the empty state is explicit. |
| C11 enforcement-liveness honesty | Directly supports "fresh/trustworthy" (`ON-G6`) and the direction's degraded-summary rule; a probe that cannot confirm must say so. |
| C12 zero-terminal test + rendered proof | Already the repository's gate philosophy (render gate, verification fixtures); it is an acceptance axiom, not a visual choice. |
| T7 debounced increases-only announcer | The direction's announcement policy is one transition-only polite live region (dir §3.3, §12.1); this is a correct implementation of it. |
| L2 typed status-message tone map | A closed severity→tone map is exactly the direction's per-value `measured`/`unknown`/severity grammar (dir §8); it keeps severity out of free-text prose. |
| K2 accessible canvas mark | The accessibility bar (dir §12.1) requires the mark be reachable; if a canvas mark is used, this is the minimum. |
| C13 reduced-motion collapse | dir §11 requires it; the hero's global collapse is the pattern. |

### 4.2 ADAPT

| Mechanism | Adaptation required (and why) |
|---|---|
| T3 counts-as-filters with a **delta** | Keep counts-as-filters; the *delta since last refresh* must carry the refresh age or be dropped — a delta from a stale poll is a fabricated trend (dir §8). |
| T6/C9 payload blocks `maxHeight` | Adopt the cap and the disclosure; wire the lazy flag only if a measured mark count requires it (dir §7; v1 §4.6 no new runtime dependency). |
| O1/O2/O3 status badge | Adopt degrade-on-unknown, icon+label, and `motion-reduce`; drop the pill's rounded badge chrome where dir §4.5's restraint budget applies, keeping the icon+word. |
| O4 phase + age | Adopt phase text + age; map the phase enum exhaustively to the database `RunState`/`StepAttemptRecord` vocabulary (dir §2.2) and render an explicit `unknown` for unmapped phases — never a raw code as a label. |
| O5 coarse health | Adopt only as a **derived display of measured statuses** with its mapping exposed; it must not become a composite "health score" (§5 conflict 5). |
| O6 log-scale activity bar | Adopt the `UNKNOWN` height and `motion-reduce`; the per-card sparkline is forbidden by dir §4.3/§4.5, so the bar fires only inside the `L-WORKFORCE` lens (dir §3.6), never on the resting roster. |
| D2 braille/matrix animation | The animation is decorative; keep the status class and the `aria-hidden` spinner only for genuinely in-flight work, and disable it under reduced motion (dir §11, §4.5). |
| D3 runtime conditions | Adopt the "summary condition + failed-detail conditions" split as the degraded/`safe_actions` summary (dir §8–§9); do not import Dagu's node-status color set as a second palette. |
| C10 stateless receipt verify | Adopt the *idea* (verify a receipt against published keys without reading the record) but route it as a bounded read-only affordance; a new POST/verify endpoint is a controller decision, not a facelift default (dir §12.2 "no new mutating route class"). |
| L1 trace playback playhead | Adopt only for the selected attempt's bounded replay (dir §3.6 R4b; v1 §4.2 R4); playback must never drive live actuation, and the RAF loop must pause on unmount and under reduced motion. |
| L3 comfort-target split | Adopt the comfort-band math as guidance; the direction fixes **one arrangement per breakpoint** (dir §3.2/§12), so the persisted/user-resizable layout is dropped — pane sizes are layout constants. |
| L4 size gate | Adopt the gate; the threshold constants belong to the portal's measured budget, not Langfuse's numbers, and `partial`/truncation must be marked (dir §8). |
| L5 type iconography | Adopt a small closed type set for the room's own evidence classes (ADVISORY/MEASURED/SOURCE/DERIVED/POLICY); do not import Langfuse's full observation taxonomy. |
| H1 dynamic waiting column | Adopt zero-footprint-until-attention and appear-first; the "blinks in the header counters" part is a decorative pulse and is dropped (dir §11). |
| H3 fingerprint + reconnect | Adopt the fingerprint skip (`[M]` the room already has keyed reconcilers, `app.js` / `keyed-list.js`) and keep-last-data on disconnect; this is the direction's two-layer reconciliation (dir §12.2.1). |
| H2 click-to-land / reply | Adopt click-to-select; the *reply/steer* path becomes the governed `R4b` action band (dir §3.6) — a P1 act within a lease, previewed and recorded, never an unguarded terminal write. |
| Y2 provider window/pace | Adopt as the `ON-G4` provider-window value (dir §2.3) and the Money lens; the source is the existing usage/settlement ledger, not a new poll. |
| Y3 inline SVG sparkline | Adopt the SVG+`viewBox` technique only inside a lens and only on **one shared scale** (dir §7); per-card micro-sparklines stay removed (dir §4.3). |
| K3 uptime clamp / sanity rule | Adopt the guard: every computed percentage is clamped and paired with its retained window; a public/status value that would read above its maximum is corrected and marked, never shown wrong (dir §8). |
| C4 pause/bulk-confirm | Adopt, but the direction's observe-only rails never steer (dir §2.5): pause is a **controller act behind the confirm**, never an automatic reaction to a threshold. |
| K1 status pill | Adopt the always-a-word rule; keep the min-width alignment, drop the pill chrome outside the attention region. |
| N2 alert vocabulary | Adopt `warning`/`critical` as external naming evidence for severity, but map to the repository's own flag severities (dir §12.2). |
| HT3 live trace timeline | Adopt for the `R4d` step-timing region and the pipeline lens; windowing is required once the measured mark count demands it. |
| HT4 separate span-evidence region | Adopt as the `R4d`/`R4b` split. |

### 4.3 DO-NOT-COPY

| Mechanism | Why not |
|---|---|
| HTx **throw on unknown status** | The control database may gain states; a live console must degrade, not crash (follow O1). |
| Y1 **`compact`/`rich`/`live` density switch** | dir §3.2/§12 requires one arrangement per breakpoint and v1 §4.6 forbids a second layout contract; a per-user density switch multiplies the render gate and defeats the glance contract. (If ever adopted, it belongs to a *lens*, not the resting screen.) |
| N1 **synced-hover anomaly charts / anomaly advisor** | The direction is a run-triage console, not a chart wall (dir §6, §7; v1 §4.7 "Brain's 3D graph as a primary surface"); anomaly-rate ML is a model call and a fabricated telemetry source (dir §12.2 "no invented telemetry"). |
| H1's **blinking counters** | Decorative pulse is removed by dir §4.3/§11 and the dir §4.5 restraint budget. |
| F1 **gamification (laps / standings / points)** | `[src:herdr-f1]` README states the values are explicitly fictional and "do not measure productivity or agent performance"; the direction is built to forbid precisely this (dir §8, §12.2). |
| C10's **new POST verify route as a default** | dir §12.2 forbids a new mutating route class; adopt the idea only as a controller-approved read-only affordance. |
| L3's **persisted resizable layout** | dir §12.2 forbids a new persistence plane; the room keeps fixed, tested arrangements. |
| **Multi-theme switcher as a product feature** (herdr-portal) | The direction treats tokens as hygiene, not identity (dir §4.4); a user theme picker is scope. Keep the existing light/dark/forced-colors contract only. |

---

## 5. Conflicts surfaced by the new evidence (headline)

V2's most useful output is not an addition; it is that **several v1 proposals contradict the accepted
direction** and one v1 claim is quietly unsupported. The a1/a3 phases must resolve these, not repeat
them.

1. **V1 §4.2 "R0 becomes a wallboard" conflicts with dir §4.3 (top-row KPI stat tiles removed) and
   the dir §4.5 restraint budget.** V1 proposes "six numbers with sparklines" at rest; the direction removes
   exactly that idiom and instead makes R0 the persistent **scope/truth strip** (`ON-G1`/`ON-G6`, dir
   §3, §16). *Correction:* R0 is a scope/truth strip whose every value carries provenance and links to
   its lens; counts are addressable filters, not decorations; no sparklines (single shared-scale
   series live in a lens, dir §7). The new evidence (Temporal T3/T4, DashClaw C7) supports
   counts-as-filters and stale-honesty, not a KPI row.
2. **V1 §4.3 "state as color and rhythm" conflicts with dir §11 ("no decorative pulse; liveness is a
   labelled state") and dir §4.3 (decorative glow/pulse removed).** The Colony-derived rhythm is the
   single most attractive-looking v1 idea and the single clearest restraint-budget violation.
   *Correction:* state is glyph + word + color + a settled timestamp (the room's existing two-axis
   language, dir §12.2.5); animation is permitted only for genuinely in-flight work, only as state
   transition (100–240 ms), and only under a reduced-motion collapse (v1 §4.4 already says this — the
   conflict is internal to v1 and must be resolved in favor of the direction).
3. **V1 §4.5 "Ask the data" LLM lens conflicts with dir §7 (no unconditional chart defaults), dir §6
   (no generic dashboard idiom), and v1 §4.6 (no new runtime dependency).** A runtime LLM that picks a
   chart spec adds a model call to a portal that is deliberately zero-model-call and can produce a
   chart default. *Correction:* **DO-NOT-COPY** as a runtime model. If the value is wanted, replace it
   with a static "recommended lens for this question" mapping derived from `spec.rules` (zero model
   calls), or omit.
4. **V1 §4.2 R3 "one computed health score" is an unsupported `[P]` claim.** The direction requires every
   consequential value to carry source, age, and authority (dir §8); a single composite score has no
   measured source in the packet. *Correction:* ADAPT to a **derived display of measured statuses**
   with its mapping exposed (`R3b` worst lag/age; `ON-G6` degraded summary), not a new vanity KPI. If a
   score ships, it is `[C]` with its formula and inputs visible and a link to the constituent signals.
5. **V1 §4.2 "R3 gets the call-center KPI treatment" conflicts with dir §4.1 Move 6 (R3a is a bounded
   constraint ledger, not money cards) and dir §3.1 (R1/R3 are annotation gutters).** *Correction:*
   render the five `ON-G4` values as a labelled constraint ledger with provenance and a money-risk
   exception marker (dir §3.1, v1 §4.2 already says "constraint ledger" elsewhere — reconcile the two
   sentences).

---

## 6. RECONCILE — every new idea against v1 and the direction

`Presupposed` = already in v1/direction, re-confirmed by new evidence. `Extends` = new mechanism or
new detail the v1/direction did not have. `Conflicts` = disagreement that must be resolved.

| New idea / mechanism | v1 | Direction | Status | What changed |
|---|---|---|---|---|
| Run/decision as an event-sourced, tabbed object (T1, HT1, C1) | v1 §4.2 R4 evidence ladder | dir §2.4, §3.2 | **Presupposed** | External support: Temporal, Hatchet, DashClaw independently converge on the same object. |
| Typed evidence classes with an authority boundary (C8/C9) | v1 §4.3 "never inferred client-side" | dir Move 4, §2.4 | **Presupposed** | DashClaw's causal spine + evidence tab is the closest external implementation of the same boundary. |
| Counts-as-filters (T3, T4) | v1 §4.5.4 (LCA) | dir §3.3, §9 | **Extends** | Adds the query-grammar chip, the accessible menu, and the stale-delta caveat. |
| Transition-only announcer (T7) | v1 §4.3 (seen/ack) | dir §3.3, §12.1 | **Extends** | A concrete, correct implementation (increases-only, debounced, never initial). |
| Approval flood + pause + grants (C4/C5/C6) | v1 §4.2 R1 inbox | dir §3.3, Move 8 | **Extends** | New: interruption-budget flood control, pause as a loud state, inline grant revoke. |
| Phase text + age (O4) | v1 §4.2 R2 | dir §2.2, §3.6 R4d | **Extends** | New: age separates progress from stall; unknown phases render honestly. |
| Log-scale activity sparkline with unknown height (O6) | v1 §4.2 R0 (sparklines) | dir §4.3 removes per-card sparkline | **Conflicts (partial)** | The *bar grammar* is good; the *per-card placement* violates dir §4.3. Move it to the `L-WORKFORCE` lens. |
| R0 wallboard with six numbers + sparklines | v1 §4.2 | dir §4.3 removes top-row KPI tiles + dir §4.5 | **Conflicts** | Resolution in §5.1: R0 is a scope/truth strip, not a KPI row. |
| State rhythm / pulse (Colony-derived) | v1 §4.3 | dir §11 forbids decorative pulse | **Conflicts** | Resolution in §5.2: glyph + word + color; motion only for live transitions. |
| LLM "Ask the data" chart lens | v1 §4.5.3 | dir §6/§7; v1 §4.6 | **Conflicts** | Resolution in §5.3: static recommended-lens mapping or omit. |
| One computed health score | v1 §4.2 R3 | dir §8 provenance | **Conflicts** | Resolution in §5.4: derived display with mapping, never a vanity composite. |
| Call-center KPI treatment for R3 | v1 §4.2 | dir §4.1 Move 6 | **Conflicts** | Resolution in §5.5: bounded constraint ledger, not money cards. |
| Live-region / forced-colors / reduced-motion discipline (T7, C13, K2) | v1 §4.6 | dir §11–§12 | **Presupposed** | Re-confirmed; new accessible-canvas and global-collapse patterns. |
| Split-pane session surface (L3) | v1 §4.2 R4 | dir §3.2 | **Extends** | New: comfort-band sizing and the both-minima overflow fallback; persisted layout dropped. |
| Size-gated heavy payloads (L4, T6) | v1 §4.6 no-build | dir §8 partial/truncation | **Extends** | New: a serialization-probe gate with an explicit measured crash bound. |
| Stale/queue-unavailable honesty (C7, C11) | v1 §4.6 (r0 freshness) | dir §8 "green never lies" | **Extends** | New: exact copy pattern and a liveness-probe honesty model. |
| Click-to-land / reply (H2) | v1 §4.6 (no terminal streaming) | dir §3.6 R4b | **Extends (governed)** | Reply becomes a lease-scoped `R4b` action, not an unguarded write. |
| Fingerprint skip + reconnect keep-last-data (H3) | v1 §4.6 keyed reconcilers | dir §12.2.1 | **Presupposed** | v1 already had keyed write-on-change; adds the fingerprint and reconnect detail. |
| Dynamic attention column (H1) | v1 §4.2 R1 inbox | dir §3.3 | **Extends** | New: zero-footprint-until-attention, appears first; blink dropped. |
| Density switch (Y1) | — | dir §3.2/§12 one arrangement | **Conflicts** | DO-NOT-COPY at rest (see §4.3). |
| Provider window / pace view (Y2) | v1 §2.2 item 8 (cost panel), R3 | dir §2.3 `ON-G4` | **Extends** | New: 5h/7d window + pace as a stated value; source stays the existing ledger. |
| Receipt verification (C10) | — | dir §8, registry lineage | **Extends (gated)** | New affordance; needs a controller decision on the route. |
| Four design anti-references (C-DESIGN) | v1 §4.7 | dir §4.4/§4.5 | **Presupposed** | DashClaw names the same neighbors (generic SaaS, consumer-AI, heavy-enterprise, crypto); useful as the blind-comparator set. |
| Gamified agent race (F1) | — | dir §8, §4.5 | **DO-NOT-COPY** | Reinforces "no invented telemetry"; recorded as the explicit anti-pattern. |
| Synced anomaly charts (N1) | — | dir §6/§7 | **DO-NOT-COPY** | The chart wall the direction defines itself against. |
| Throwing on unknown status (HTx) | — | dir §8 degrade | **DO-NOT-COPY** | Follow O1 instead. |

**Net change to v1.** V2 does not add a new resting-screen region; it **subtracts** two v1
proposals (the R0 KPI wallboard and the rhythm animation), **relocates** one (the activity bar to the
lens), and **gates** one (the LLM lens). It **adds** mechanism-level detail to existing v1 regions:
the announcer, the evidence tab's typed listings, the causal spine, the flood/pause/grants attention
controls, the phase+age pair, and the payload size gate.

---

## 7. Adversarial findings (external lens; feeds phase a3)

Phrased as corrections to claims/questions, with the acceptance that proves the correction.

| # | Severity | The flawed claim | Required correction | Acceptance that proves it |
|---|---|---|---|---|
| A-1 | high | v1 §4.3 "state as color and rhythm" is a legitimate identity move. | Rhythm is not identity (dir §11). State = glyph + word + color + settled timestamp; motion only for in-flight transitions, collapsed under reduced motion. | A forced-colors + reduced-motion screenshot shows every state identifiable with no animation running; render gate passes. |
| A-2 | high | v1 §4.2 "R0 becomes a wallboard" extends the direction. | R0 is the scope/truth strip (`ON-G1`/`ON-G6`); no KPI tiles, no per-card sparklines. Counts are filters. | The one-resting-screen glance check (`ON-G1..G7` at three viewports, dir §18.2) still passes without a KPI row. |
| A-3 | high | The LLM "ask the data" lens is a v1 §4.5 add. | It adds a model call and a chart default to a zero-model-call portal. Static lens mapping or omit. | Portal remains zero model calls and no chart renders without a stated question/baseline/fallback (dir §7). |
| A-4 | high | DashClaw's automatic approval-flood pause is an adoptable pattern. | The repository's rails are observe-only; a pause triggered by a threshold would be an automatic steer (dir §2.5). Pause is a confirmed controller act. | No code path pauses a policy without a recorded human confirmation and a decision receipt. |
| A-5 | medium | A per-user density switch improves the room. | It creates a second layout contract and a second glance contract. DO-NOT-COPY at rest; a lens may own density. | The render gate tests one arrangement per breakpoint, not a density matrix. |
| A-6 | medium | Temporal's "difference since last refresh" is a safe count delta. | A delta from a stale poll is a fabricated trend (dir §8). Drop it or pair the count with the refresh age. | A stale fixture shows the age/last-updated, not an unqualified delta. |
| A-7 | medium | A canvas heartbeat/sparkline is fine because the reference has one. | Canvas is opaque to assistive tech unless `role="img"` + `aria-label` + focus + keyboard are added (K2). | Forced-colors and keyboard-only passes; the mark has an accessible name and a textual equivalent. |
| A-8 | medium | Langfuse's persisted resizable split can be copied. | It is a new persistence plane and a second arrangement contract (dir §12.2). Use fixed, tested arrangements. | No `localStorage` layout key; one arrangement per breakpoint in the render gate. |
| A-9 | medium | Any of these consoles proves the direction is a consensus. | No source claims consensus; each mechanism is bounded to its cited file. The compliance/approval console is one product, not a field. | Every external claim in v2 carries a pin; composition claims stay `[P]`. |
| A-10 | medium | A "health score" is a harmless convenience. | It is an unmeasured composite unless its formula and constituent signals are visible (dir §8). | If shipped, the score is `[C]`, its inputs are linked, and no fabricated value appears. |
| A-11 | low | The evidence ladder needs a transcript. | A log viewer is not a causal explanation (dir §6, Move 2). Keep the typed rungs; payloads are bounded disclosures, not the spine. | R4 renders typed rungs; raw JSON is behind a disclosure with a size gate. |
| A-12 | low | "Reply to agent" from the room is a free convenience. | Steering is a P1 act within a lease, previewed and recorded (dir §3.6, §2.5). | Every steer shows target/scope/reversibility and writes a receipt. |

---

## 8. Small-task seeds (handoff to phase a1 — a1 owns the canonical plan)

These are **seeds**, not the plan; `a1_decompose` writes
`docs/website/control_room_ui/facelift_task_plan.md`. Each seed is small (one session) and gated.

| Seed | Question | Artifact | Acceptance (named gate) | Layer | Class |
|---|---|---|---|---|---|
| S1 | Can R0 be a scope/truth strip that answers `ON-G1`/`ON-G6` with per-value provenance and no KPI tile? | R0 markup + tokens | render gate `ON-G1`/`ON-G6` anchors, no tile row | structure | [M] |
| S2 | Does one transition-only, increases-only live region replace the current sr-only announcer without double-announcing a batch? | announcer module + tests | unit test (initial/decreases not announced; identical re-announces) | behavior | [M]/[X] T7 |
| S3 | Does R1 render counts as filters (with refresh age, no bare delta) and expand in place? | R1 region | render-gate fixture F-1 + click-through test | behavior | [M]/[X] T3/T4 |
| S4 | Does R2 replace rhythm with glyph+word+color+timestamp and stay legible in forced-colors? | R2 row schema | forced-colors screenshot + recognizability §4.2 | presentation | [M] |
| S5 | Does the evidence region use the five-stage causal spine with the repository's own rungs? | R4 causal region | fixture with one waiting/one failed/one money-risk run | structure | [X] C8 |
| S6 | Does the payload/JSON surface gate on a serialization probe and mark truncation? | size-gate helper | unit test at/below/above threshold + `partial` marker | behavior | [X] L4 |
| S7 | Is `safe_actions` rendered as a menu with disabled reasons instead of a read-only table? | action menu | render-gate + authority test (no auto-steer) | behavior | [M]/[X] D4 |
| S8 | Does the attention surface have a flood/pause state that is a *confirmed* controller act? | flood/pause region | no unconfirmed pause path; receipt written | behavior | [X] C4/A-4 |
| S9 | Does the room keep last-known data and label it stale when the packet fetch fails? | freshness banner | failure fixture shows last-successful age, never all-clear | verification | [M]/[X] C7 |
| S10 | Does the `L-WORKFORCE`/pipeline lens host the activity bar and step timings, off the resting screen? | lens | lens fixture at desktop/mobile; resting gate unchanged | structure | [M]/[X] O6/HT3 |
| S11 | Is the `ON-G4` cost set a bounded constraint ledger with provenance? | R3a region | render gate `ON-G4` (all five values) | presentation | [M] |
| S12 | Does R4 offer a governed steer/reply with target, scope, reversibility, receipt? | R4b action band | authority test + receipt fixture | behavior | [M]/[X] H2/A-12 |

Minimal first wave (visible improvement, smallest set): **S1, S2, S3, S4** (the resting screen's truth,
announcement, attention, and identity) + **S9** (honesty on failure). The others build on them.
Stopped-by gates: the render gate at 1440×900 / 1024×768 / 390×844; the one-resting-screen glance
check; and the §4.2 recognizability test (dir §18).

## 9. Dynamic-workflow note (handoff to phase a2 — a2 owns the design)

`a2_dynamic_workflow` writes `docs/website/control_room_ui/dynamic_workflow_design.md`. This phase's
contribution to it is the mechanism inventory in §3 and the conflict ledger in §5–§7: a question tree
over the facelift should make each v1 proposal a node whose **kill-criterion** is one of the five
conflicts above, and each `requires`/`produces` edge should cite the mechanism IDs (T1…C13) as the
external evidence that an acceptance is achievable. No new machinery is implied by this phase; the
compiler's `requires`/`produces` gate and the `AdaptSpec` selection strategies
(`highest_uncertainty | highest_regret | largest_effect`) already express the drive the a2 prompt
describes.

---

## 10. Controller decisions needed (from a0 only)

1. **The five v1 conflicts (§5).** Confirm the resolutions: R0 scope/truth strip (not wallboard), no
   state rhythm beyond live transitions, no runtime LLM chart lens, no vanity health score, and R3 as a
   constraint ledger (not money cards). These change what v1 proposed.
2. **Receipt-verification route (§4.2 C10).** A stateless verify affordance needs either an existing
   read-only route or a controller-approved new one; the direction forbids a new mutating route class
   by default.
3. **Density switch (§4.3 Y1).** Confirm it is out of scope for the resting screen.

Everything else in §4 is dispositioned and can proceed to a1 as-is.

## 11. Pins (repeated for a standalone citation)

`[src:temporal-ui]` temporalio/ui @ `542fa634e7ae7b1441e82b2a1beb4717811430d8`;
`[src:hatchet]` hatchet-dev/hatchet @ `315d43a72fd771b049b304b865a81dbab98c466c`;
`[src:dagu]` dagu-org/dagu @ `2635b927b345a2ecadc89462276c6a82f062eabe`;
`[src:langfuse]` langfuse/langfuse @ `6d298ec5d618ab236d8aacb6e59fa9daf59bb3a0`;
`[src:openhands]` All-Hands-AI/OpenHands @ `28464621d879e3e9b3ceeae9d70a71d96da6212d`;
`[src:uptime-kuma]` louislam/uptime-kuma @ `3afdc9ca86752587cc5a88147403194b5f83196d`;
`[src:dashclaw]` ucsandman/DashClaw @ `275c6f3338129967d32ed36d447bdd3493c810fc`;
`[src:herdr-portal]` loofare/herdr-portal @ `cae8ea07a51f54d6e73b6e5a40d0930c8d4f074f`;
`[src:lazyagent]` illegalstudio/lazyagent @ `2be879c1660ad9f7592f1869e67a8f60243dc773`;
`[src:herdr-f1]` hmu332233/herdr-f1 @ `9af4d2af82da1fe71b3ef8a8d31ba0edf3c326b0`;
`[src:netdata-docs]` netdata/netdata @ `0a4ce7db5fa329c8a9c1a4b82e78ee2af9750072`;
`[src:openmao]` OpenMAO/OpenMAO @ `6333832b8b57b8c4de0f3e3d275505206e1b487c`;
`[src:clawd-control]` Temaki-AI/clawd-control @ `0ed74f55cc6ce3d39eb3c52d0c7a03c9f2d9ed77`.
GitHub topic pages accessed 2026-09-13. Local references are `[M]` against this repository's `main`
at the phase commit; companion documents: `docs/research/control_room_direction.md` (accepted),
`docs/research/control_room_ui_reference_synthesis.md` (v1, extended here, never deleted),
`docs/research/agent_runtime_landscape.md` (tool comparison).
