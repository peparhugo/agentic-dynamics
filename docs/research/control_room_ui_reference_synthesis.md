---
status: proposed
---

# Control Room — UI reference synthesis and facelift proposal

**Date:** 2026-09-13
**Status:** proposed (research only; no implementation).
**Relationship to the accepted direction:** this document does **not** supersede
`docs/research/control_room_direction.md` (status: accepted, 2026-09-11, "the live run as the unit of
work"). It presupposes that direction's run-first object, evidence classes, removed-generic-elements
list, and restraint budget, and adds what it did not have: (a) UI mechanisms extracted from Herdr's
client and Omarchy's shell code, and (b) a synthesis of six community reference apps. §6 reconciles the
two documents item by item; where an idea is already covered, it says so.
**Claim discipline:** `[X]` external observation at the pinned commit/URL; `[M]` measured in this
repository with a `file:line` anchor; `[P]` local recommendation, not a decision.

---

## 1. Current room inventory (measured) `[M]`

One resting screen, no navigation, no build step. Served by `apps/control_room/server.py:132`; the page
is `apps/control_room/static/index.html` (321 lines) with client JS:

- **R0** machine rail (`index.html:100-150`), **R1** attention (`159-162`), **R2** run roster
  (`170-176`), **R3a/b/c** cost / health / composition (`183-194`), **R4** selection dock (`206-243`),
  trends lens (`250-260`), workbench with 13 lenses (`270-297`).
- Render entry `static/app.js:772-803`; per-region renderers at `app.js:189,210,229,259,498,602,648,661`;
  shared keyed reconciler `static/keyed-list.js:88-136`; one `EventSource("/api/events")`
  (`app.js:999`), 30 s stale rule (`app.js:948-988`); theme tokens `static/style.css:24-130`; trend
  charts `static/charts.js:39-76`; workbench registry `static/parity.js:2223-2237`; composed confirm
  bar with typed phrases `parity.js:121-170`.
- Verified absences: **no ack/seen/snooze/dismiss** anywhere; **no toast/notification system** (only an
  sr-only announcer `index.html:301` + inline receipts); **no terminal streaming**; **no command palette
  or global shortcuts**; **no filtering on the resting screen**; `safe_actions` render as read-only
  tables (`parity.js:1789-1821`). Attention lifecycle `new|active|snoozed|resolved|stale` exists only in
  docs and a dead client vocabulary (`app.js:463`).
- Guardrails to preserve: textContent-only rendering (`app.js:55-67`), one EventSource, the render/
  verification gate (`apps/control_room/verification/gate_report.md`), forced-colors + reduced-motion
  (`style.css:104-130,1280-1293`), and the authority split (GETs + one bounded SSE; mutations behind
  the confirm bar; `.opencode/tools/control_room.ts` GET-only).

## 2. UI mechanisms worth borrowing from Herdr and Omarchy `[X]`

### 2.1 Herdr client (TUI, mechanisms transfer)

1. **Status vocabulary and attention ordering.** Glyph+color: `●` working, blocked red, `✓` done teal,
   `○` idle green, `·` unknown (`src/client/shell.rs:198-217,245-257`); priority
   `Blocked 4 > Done 3 > Working 2 > Idle 1` (`:223-232`), max-aggregated per workspace
   (`src/workspace/aggregate.rs:50-75`); sort key `(priority, last state change)` (`agent_sidebar.rs:37-45`).
2. **Done vs Idle via `seen`, with presentation-coherent acknowledgement.** `Done = Idle + not seen`
   (`src/pane/state.rs:8-10`; `src/app/api_helpers.rs:96-107`); the seen watermark advances only when the
   client's *coherently presented surface* covered the change while focused
   (`src/client/shell/endpoint_agent_state.rs:36-89`; `input.rs:237-243`).
3. **Bounded toast policy.** Max 8 queued (drop oldest), one visible, per-kind durations
   (needs-attention 8 s, finished 5 s, update 3 s), same-pane replacement, active view is silent,
   finished is advisory/rechecked, click focuses target (`notification_policy.rs:3-22,40-63,105-142,194-224`;
   `mouse.rs:978-989`); endpoint notices have dedupe keys (`actions.rs:305-345`).
4. **Navigator + context help.** Universal tree overlay with `/` search and `a/b/w/i/d` filters
   (`overlays.rs:694-931`; `overlay_input.rs:633-788`); one-line context mode bar (`render.rs:31-211`)
   and a searchable keymap overlay (`overlays.rs:997-1129`).
5. **Stale dimming and slow-client backpressure.** Offline/stale surfaces dim
   (`endpoint_sidebar.rs:455-462`); render queue capacity 1 per client; surfaces rejected monotonically
   (`client_transport.rs:122-127`; `state.rs:1603-1617`).
6. **Live theme preview with revert.** Settings previews the palette live; Esc/outside click reverts;
   contrast is test-pinned (`settings.rs:108-198`; `src/app/state.rs:1393-1476`).

### 2.2 Omarchy shell (Quickshell; product-level patterns)

7. **Self-hiding widgets.** A slot's size is zero when its widget is invisible
   (`shell/plugins/bar/Bar.qml:1814-1815`); the agents panel ships in the default bar but draws nothing
   until data exists (`shell/plugins/agents/Panel.qml:300`, `Main.qml:184-224`).
8. **Cost/usage panel design.** Hero → subscription chips → auth/status → balance drain meter alarming
   at ≤10% → normalized session/weekly/monthly limits → tokens-by-day with today bold → top-4 models
   bar scaled to the heaviest with in/out/cache tooltip (`Panel.qml:397-697,528-588,620-651,875-941`);
   keyboard `h/l` provider, `j/k` scroll, `r` refresh (`:363-379`); open-panel does a cheap
   limits-only probe while full scans run on a 900 s timer (≥30 s clamp) (`Main.qml:117-177`).
9. **Notifications with typed actions, persistence, and DND.** Actions are discrete argv, never a
   shell string (`bin/omarchy-notification-send:117-137`); live toasts are mirrored to files so they
   survive a shell restart and remain clickable (`Service.qml:23-39,355-397`); hover pauses the
   countdown; critical persists; DND has a two-category bypass allowlist
   (`Service.qml:121-154,929-978,1013-1039`).
10. **Menu/command surfaces as data.** JSONC entries with per-key overlay merge, `checked`/`disabled`/
    `when` guards, search scoring, provider rows (`default/omarchy/omarchy-menu.jsonc:1-27`,
    `MenuModel.js:66-96,274-363,395-491`).
11. **One theme unit propagated across surfaces.** Theme set regenerates tokens for bar/notifications/
    menu/lock and retints agent TUIs (Claude theme json hot-reload; opencode SIGUSR2; Hermes skin)
    (`bin/omarchy-theme-set:277-380`; `bin/omarchy-theme-set-claude:9-12`; `bin/omarchy-restart-opencode`).
12. **Agent glyph font.** Monochrome PUA marks so the active theme colors apply
    (`default/fonts/omarchy/README.md:3-22`).

**Do not import:** screen-scraping as primary state source; the terminal server as the work unit; the
no-sandbox plugin trust model; a sidebar multi-page IA (the room is deliberately one screen); heavy
canvas/3D dependencies.

## 3. Reference synthesis — what each app contributes `[X]`

| Reference | Contribution | Anchors |
|---|---|---|
| **Call-center dashboards** (`github.com/topics/call-center-analytics`, `.../callcenter`; Amazon LCA is the strongest) | Wallboard KPI strip; **alert counter that sorts/filters the list**; queue depth/wait as first-class numbers; per-operator states; supervisor assist patterns; category alerts in red | `aws-samples/amazon-transcribe-live-call-analytics` README (Categories and Alerts; live call list) |
| **Clawboard** (`Wadera/clawboard` @ `9b3d6905…`) | Sidebar usage-limit bars + execution-system health cards (`Sidebar.tsx:294-324,326-430`); cards **glow when live, dim/grayscale after ~10 min idle** (`TaskCard.css:85-99`, `TasksPage.tsx:306-312`); **segmented multi-state progress bar** (`TaskCard.tsx:300-334`); sessions split-pane with transcript + tool calls (`SessionsPage.css:3-11`, `SessionsPage.tsx:473-543`); deep-link-first navigation (`TasksPage.tsx:55-69,426-495`); **server-authored state classification, never client-guessed** (`sessionPresentation.ts:29-53`); dark palette tokens (`styles/variables.css:10-15,26-83`) |
| **The Colony** (`BovineDawn/TheColony` @ `ea8d407a…`) | **ID-card tiles** (dept stripe, ID, status dot, barcode, badges) (`ColonyMap.tsx:277-442`); **status as animation rhythm** — distinct sine per state — plus an independent mood ring for strikes/quality (`:183-202,263-272`); **Founder Inbox "Items Requiring Attention"** with expand-in-place reports (`FounderInbox.tsx:107-181`); **one computed health score** (`MorningBriefing.tsx:121-130`); surfaces ramp + amber/cyan accents + HUD mono microtype (`styles/globals.css:5-42`); demo mode for offline presentation (`MissionControl.tsx:857-888`) |
| **The Brain** (`Hastur-HP/The-Brain` @ `f336e7c9…`) | **Pipeline-as-grid** stage instrumentation with % (`main.js:24-29,153-183`); content-block composition bars (`:253-267`); live log with kind colors + filter (`:530-562`); graph legend with per-type counts, hide/isolation, neighborhood drill-down, node limits (`:1290-1326,1373-1401`); hub sampling server-side (`neo4j_utils.py:80-82`); glass cards + JetBrains Mono (`style.css:1-21,465-473`) |
| **OpenVizAI** (`OpenVizAI/OpenVizAI` @ `faf667f0…`) | Prompt→chart with **"LLM picks the spec, deterministic JS renders the full data"** (`README.md:60-68`); recommended chart carries a plain-language rationale (`ChartPlayground.tsx:399-402`); sessions as replayable artifacts (`Home.tsx:36-68`); chart-type registry (`packages/react/src/charts/registry.ts:15-31`); nulls render as gaps, never zeros (`chartSpec/chartData.ts:8-15`) |

## 4. The facelift proposal `[P]`

### 4.1 Direction — "wallboard liveness on a measurement bench"

Keep the accepted run-first skeleton and the calm glance. Add the two things the references do better:
**operations-room immediacy** (call-center wallboards; Clawboard's live sidebar; Colony's status rhythm)
and **per-run identity** (Colony tiles, Clawboard cards). The room reads like a mission-control wall at
rest and behaves like a workbench on selection. Every number keeps its evidence class; nothing is
inferred client-side.

### 4.2 Resting screen (evolution, not replacement)

```text
R0 WALLBOARD   agents · queue · running · spend vs cap · projection lag · stream state   [lenses][theme]
R1 ATTENTION   [DECISION n] [RISK n] [NEAR CAP n]   counters ARE filters; expand-in-place reports
R2 FLEET       run tiles: state chip+rhythm, spec, model, phases n/m segmented bar, budget bar,
               age, last event; dim when stale
R3 MONEY       call-center KPI tiles │ HEALTH one score + providers │ COMPOSITION token split
R4 DETAIL      split-pane: transcript │ tools │ diff │ events   (live tail, pinned scroll)
```

- **R0 becomes a wallboard**: six numbers with sparklines (Clawboard's usage-bar shape), each linking to
  its lens. `[X] Clawboard Sidebar.tsx:727-751`; `[M]` packet already carries every field.
- **R1 becomes the Founder Inbox**: today decision/risk items are inert (`app.js:421-430` has
  `role="button"` with no handler). Expand in place, Colony-style; mutations stay behind the confirm
  bar. `[X] Colony FounderInbox.tsx:107-181`.
- **R2 becomes identity tiles**: state as color **and** rhythm (idle slow / working medium / blocked
  sharp; disabled under reduced motion), segmented phase bar, liveness dim after inactivity.
  `[X] Colony ColonyMap.tsx:183-202`; `[X] Clawboard TaskCard.tsx:300-334, TaskCard.css:85-99`.
- **R3 gets the call-center KPI treatment** plus one computed health score with its formula on hover
  (`[X] Colony MorningBriefing.tsx:121-130`) and the token-split composition bars
  (`[X] Brain main.js:253-267`).
- **R4 becomes a real session surface**: list+detail split, transcript with role-colored rows,
  expandable tool calls, commit diff. `[X] Clawboard SessionsPage.tsx:1546-1591,473-543`.

### 4.3 State language (one vocabulary everywhere)

`◐ working` (cyan, medium pulse) · `× blocked` (red, sharp pulse, always first) · `✓ done-unseen`
(green, static) · `○ idle` (neutral, static) · `? unknown` (dashed) — glyph + color + rhythm + label
(§2.1–2.2). Add: **seen/ack** (done collapses when acknowledged; an ack may write a decision record —
recording is part of the act), **stale dimming** with "last event Nm", **one health score** with an
exposed formula, and **alert counters that filter** (`[X]` LCA). Never inferred client-side: render
only server-authored state (`[X]` Clawboard sessionPresentation.ts:29-53; `[M]` packet is the source).

### 4.4 Visual system `[P]`

- **Surfaces**: Colony's four-step neutral ramp, warm-white text (`[X] globals.css:5-42`) — calmer than
  the current mixed backgrounds under long watch.
- **Accents**: one operator accent (amber `hsl(42 65% 52%)`) for human-attention items; one machine
  accent (cyan `#00D4FF`) for live activity; green/red reserved for success/failure. Idle loses the
  violet accent it currently borrows.
- **Type**: UI sans for prose; system mono (or self-hosted JetBrains Mono) for all data — 10–11 px
  uppercase, 0.08–0.15 em tracking for region headers, tabular numerals. No font CDN on this host.
- **Chrome**: corner brackets on active/selected cards only; glass for overlays and R4 only
  (`[X] Brain style.css:465-473`); grain/scanlines optional, ≤3 %.
- **Motion**: state rhythm only on live/blocked cards, number ticks, attention slide-ins; everything
  behind `prefers-reduced-motion` (`[M] style.css:1280-1293`).

### 4.5 Adds

1. **Live-log lens** (`[X]` Brain): per-cell event kinds with color + filter.
2. **Pipeline lens** (`[X]` Brain): per-run phase grid from `step_attempts`; packet already carries
   `phases_completed/phases_total`.
3. **"Ask the data" lens** (`[X]` OpenVizAI): natural-language question → recommended chart + one-line
   rationale, rendered client-side from real data; model picks the spec, code computes the values.
4. **Alert counters as filters** (`[X]` LCA) and `safe_actions` rendered as a menu with disabled
   reasons (`[X]` Omarchy menu guards) instead of read-only tables.
5. **Toast rail** (`[X]` Herdr §2.1.3): bounded, per-kind durations, active view silent, click to
   deep-link only — never mutate from a toast.

### 4.6 Non-negotiables `[M]`

No build step (vanilla JS + CSS tokens, textContent-only, one EventSource, keyed reconcilers); render
gate/verification fixtures updated with any layout change; authority unchanged (GETs + bounded SSE;
mutations behind the confirm bar; agent tool GET-only); no new runtime dependency (no React/Tailwind/
Pixi/force-graph in the portal); accessibility bar kept (contrast, forced colors, reduced motion).

### 4.7 Do not import

Colony's missing ARIA/toasts/responsive behavior; Clawboard's emoji-as-status language and hardcoded hex
drift; Brain's 3D graph as a primary surface; OpenVizAI's single blocking POST with no progress; any
login/auth stack — the boundary stays peer trust + Tailscale (`services/mutations.py:30-68`).

## 5. Suggested next steps

1. Controller decision: adopt / scope / park this synthesis. If adopted, the natural home is a spec in
   the `docs/website/control_room_ui/` series (research/design/audit/verify already exist) with per-region
   acceptance checks against the render gate.
2. If a wave is commissioned, sequence: R0 wallboard + R1 inbox expansion (small, high value) → R2 tiles
   → R4 session surface → new lenses.
3. The stale-flag/seen mechanism depends on whether supervisor flags gain an ack bit (see
   `docs/research/agent_runtime_landscape.md` §5.1 item 1) — decide those together.

## 6. Reconciliation with `docs/research/control_room_direction.md` (accepted)

| This proposal | Status vs accepted direction |
|---|---|
| Run-first object, evidence classes, calm resting screen | **Presupposed** (direction §1–§2); not re-litigated here |
| Removed generic elements, restraint budget | **Presupposed** (direction §4.3–4.5); §4.4 accents/type are within that budget |
| R2 identity tiles + liveness dim | Extends direction §3.1/§4.1 with external reference evidence (Colony/Clawboard); new |
| R1 expand-in-place attention inbox | Extends direction §3.3 with the Colony inbox pattern; new |
| Seen/ack + done-vs-idle | **New** (direction has attention states, not a seen watermark) |
| Alert counters as filters | **New** (LCA convention) |
| Toast rail | **New** (Herdr policy; direction has no toast contract) |
| KPI strip + one health score | Within direction §7 chart set, but the score framing is new |
| Cost/usage panel design | **New** component-level detail for direction §2.3 |
| Pipeline/live-log lenses | **New** lenses for direction §3.2/§3.6 |
| Split-pane session surface (transcript/tools/diff) | Extends direction §3.2 evidence ladder; new detail |
| Visual tokens (surface ramp, amber/cyan) | A concrete `[P]` proposal under direction §12/§18's quality bar |

## 7. Sources and pins

- Herdr @ `981fe83ca2e23474255f4cacc4da2814f9de0744`; Omarchy @ `8247eb36b7ce7727ccdb5680ca64e207eae9bb0c`;
  Clawboard @ `9b3d6905070cbabf18a1df84687dd57b924f56b9`; The Colony @ `ea8d407ab81ec03992976c2e4831a4d5589e7c2b`;
  The Brain @ `f336e7c9489a867f926a9bf1cfa216deb816a024`; OpenVizAI @ `faf667f0192f29d97c5e6607536175a40ef269d3`.
- Call-center topic pages: `github.com/topics/call-center-analytics`, `github.com/topics/callcenter`;
  Amazon LCA sample: `github.com/aws-samples/amazon-transcribe-live-call-analytics` (README, "Categories
  and Alerts" + live call list). Screenshots reviewed in-repo for Clawboard, Colony, Brain, OpenVizAI.
- Companion doc: `docs/research/agent_runtime_landscape.md` (tool comparison + open-code adoption ideas).
