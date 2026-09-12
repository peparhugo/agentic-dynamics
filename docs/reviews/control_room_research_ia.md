---
status: accepted
---

# Control Room research - information architecture critique (campaign r6c)

**Date:** 2026-09-11
**Pass:** adversarial pass 3 of 3; information architecture
**Reviewer:** `openai/gpt-5.6-sol`
**Subject:** `docs/research/control_room_direction.md` (r5)
**Inputs:** the r0 measured portal audit, the r1 operator-needs contract, the r5 direction, the r6a
entailment review, the r6b design critique, and direct checks of the external exemplars in the
appendix.

## Verdict

**FAIL - the r5 direction does not satisfy its own no-interaction glance contract.**

r5 names every operator need, but naming a need is not the same as placing its answer where the
operator encounters it. The resting screen can show only one active domain board, while the glance
contract assigns required information to Work, Money, Health, Decisions, the rail, an attention
strip, and a footer. A run's lifecycle, spend, dependency health, approval state, and evidence are
therefore split across five places. The operator must navigate before deciding whether the thing in
front of them is safe, urgent, or even trustworthy.

The central IA defect is this:

```text
r1 promise:  one resting screen answers ON-G1..G7 with no interaction
r5 reality:  one active board answers one domain; the operator reconstructs the rest
```

r5 also treats alerting as the third depth after glance and drill-down. That model is wrong. Glance
and drill-down are disclosure depths. Alerting is an orthogonal lifecycle that detects a transition,
creates or updates a durable attention object, optionally delivers a notification, and brings the
operator back to a scoped detail view. A transient strip cannot serve as status, issue, notification,
and decision queue simultaneously.

The brief must adopt a new information sequence:

> **Scope and truth stay visible; unresolved attention comes first; fleet state comes second; one
> selected run joins its evidence, constraints, and safe action; aggregate analysis comes last.**

This sequence is a product policy `[P]` derived from r0/r1, not an externally measured universal.
The checked exemplars `[X]` support bounded patterns such as triage queues, issue detail, alert
lifecycles, context preservation, and trace structure. They do not prove r5's four-board taxonomy.

## Review method

The pass asks three mechanical questions of every r5 proposal:

1. **Glance:** Can the operator answer the need from the default resting screen without opening a
   peer board, and can they trust the answer's scope and age?
2. **Drill-down:** Does one selection preserve context and reveal the evidence required for the next
   decision, or does the operator have to search another destination?
3. **Alert:** Is the signal a durable, ranked, deduplicated object with a lifecycle, or only a visual
   change that disappears or repeats?

Evidence labels in this review are:

- `[M]` measured repository fact from r0 or an existing runtime contract.
- `[X]` direct external observation checked on 2026-09-11.
- `[P]` required design policy for the facelift brief.

## What the operator must know first

r1 orders the glance needs as connection, work, risk, money, decisions, truth, and fleet shape. r5
repeats that order in a table but does not produce it in the interface. The correct reading order
must distinguish a **prerequisite** from a **work queue**:

| Rank | Persistent question | Why it belongs here |
|---:|---|---|
| 0 | What scope am I operating, and is its data trustworthy? | Scope, connection, control epoch, and freshness qualify every later answer. They stay visible but should not dominate the page. |
| 1 | What changed, what is unsafe, and what needs my decision now? | Failures, stalls, pending approvals, quota risk, unhealthy dependencies, and advisory flags change the operator's next action. |
| 2 | What is running, queued, failed, and live across the fleet? | Once exceptions are visible, the operator needs fleet progress and capacity context. |
| 3 | What constraint changes the current decision? | Spend, headroom, provider windows, leases, worker health, and projection health belong beside affected work. |
| 4 | What does the selected run's evidence support, and what action is safe? | Investigation and actuation need one joined context, not board hopping. |
| 5 | What patterns exist across model, condition, provider, cost, and quality? | Fleet comparison and historical analysis are important but rarely the first response to a live exception. |

This does not discard ON-G1..G7. It changes how they are composed. ON-G1 and ON-G6 become a thin,
persistent qualification layer. ON-G3 and ON-G5 become the primary work queue. ON-G2 stays the
default operational body. ON-G4 appears both as exception context and as a secondary fleet lens.
ON-G7 remains a comparison lens rather than pushing live triage below charts.

## Findings

### IA1 - The glance contract is physically impossible

**Severity: CRITICAL**

r1 defines ON-G1..G7 as resting-screen needs with no interaction and explicitly says ON-G1..G6
must be answered in order. r5 assigns those answers to four peer boards:

- ON-G2 and ON-G7 live on Work;
- ON-G4 lives on Money;
- most of ON-G1, ON-G3, and ON-G6 live on Health or the attention/truth chrome;
- ON-G5 lives on Decisions.

The r5 layout then declares one `BOARD (active domain)`. When Work is active, Money, Health, and
Decisions are hidden. When the operator opens one of them, the live fleet is hidden. No amount of
token polish can satisfy a no-interaction requirement with mutually exclusive destinations.

**Required disposition:** Declare **Fleet Triage** as the default resting surface and place compact,
always-visible summaries for connection/truth, unresolved attention, money risk, and pending decisions
around the fleet list. Keep Money, Health, Decisions, and Registry as secondary comparison or evidence
lenses. Do not require a board switch to determine whether a visible run is actionable.

### IA2 - The four-board taxonomy fragments one decision

**Severity: CRITICAL**

For a single failed run, r5 places:

- lifecycle and phase on Work;
- spend, quota, wallet, and lease reservations on Money;
- worker and projection health on Health;
- approval, candidate SHA, and canonical state on Decisions;
- transcript, lineage, per-step cost, and controls in Detail.

This contradicts r5's own rule that evidence be one step from the decision. It also creates an epoch
problem: the operator can inspect each board at a different poll age while the run changes. A fresh
failure, stale quota value, and old approval can look like one coherent decision when they are not.

**Required disposition:** A selection must establish one persistent run context joining:

```text
run -> phase -> attempt -> session -> worker -> lease
    -> approval/candidate SHA -> independent verification -> decision -> registry record
```

Decision-changing money, health, approval, and evidence facts belong in that inspector. Aggregate
boards may still exist, but they must open the same selected object and preserve its context.

### IA3 - The `control-status/v1` packet is not established as the overview authority

**Severity: CRITICAL**

r0 M3 identifies the canonical control packet as the missing authority for active, failed, awaiting,
and promotable runs, unhealthy workers, projection lag, degraded state, and database-derived
`safe_actions` `[M]`. r5 says to render the packet "on Health/Decisions", then distributes fragments
of it across the rail, attention strip, Health board, Decisions board, and detail. The layout omits
the packet's control epoch and does not show that safe actions come from the enforced transition
graph.

**Required disposition:** Use one current control-packet projection as the source of the persistent
room overview and attention queue. Show its epoch and update age. Derive run and decision objects from
that packet without inventing another status vocabulary. Analytical views may enrich it, but they may
not redefine current control state or synthesize actions independently.

### IA4 - The attention strip has no information model

**Severity: CRITICAL**

r5 combines failed runs, projection lag, unhealthy workers, approvals, spend thresholds, supervisor
flags, docs warnings, and room staleness in one horizontal strip. Those are not interchangeable:

- a failure is a lifecycle transition;
- projection lag is standing dependency state;
- an approval is a pending decision;
- a quota crossing is a threshold event with a reset window;
- a supervisor flag is advisory attention;
- docs drift is a process finding;
- room disconnection is loss of observation.

The layout gives none of them stable identity, first-seen time, last-change time, affected object,
owner, evidence authority, acknowledgement, snooze, resolution, or overflow behavior. r0 A1 asked
for an alert aggregate and log, not merely a sentence at the top of the page.

Linear separates triage work from inbox notifications `[X]`. Datadog's Triage Inbox consolidates
related events into work items that can be sorted, assigned, investigated, escalated, split, merged,
and resolved `[X]`. Grafana models an alert instance lifecycle with pending, alerting, recovering,
resolved, no-data, and error states `[X]`. The useful lesson is stateful attention, not visual
imitation.

**Required disposition:** Replace the strip as the primary model with a durable **Attention Inbox**.
The strip may survive only as a compact index into it. Every attention item must carry:

| Field | Requirement |
|---|---|
| identity | Stable item key and typed source object |
| priority | Severity plus whether a human decision is possible now |
| timing | First seen, last changed, source age, and any threshold/reset window |
| scope | Affected run, worker, projection, provider, campaign, or room |
| state | `new`, `active`, `snoozed`, `resolved`, or `stale` |
| authority | Measured, computed, heuristic, policy, or unknown |
| action | Evidence link and database-derived safe next action, if one exists |

### IA5 - Alerting is not a third disclosure depth

**Severity: HIGH**

r5 labels sections `glance`, `drill-down`, and `alert` as if they were three points on one depth
axis. They are not. A run failure can be visible at glance, open in detail, represented by a durable
attention item, and delivered as a notification at the same time.

The checked products separate these concepts. Sentry groups events into issues and then places
evidence and actions on issue detail `[X]`. Grafana evaluates rules into alert-instance states and
routes notifications only on specified transitions `[X]`. Linear keeps Triage work distinct from
Inbox notifications `[X]`.

**Required disposition:** Replace the three-depth story with two orthogonal models:

```text
Disclosure:    overview -> selected object -> evidence detail
Attention:     observation -> state transition -> attention item -> notification -> resolution
```

The facelift brief must specify where each alert type persists, what transition generates an
announcement, and what detail view owns its investigation.

### IA6 - `must interrupt` contradicts pull-first, in-room-only delivery

**Severity: HIGH**

r5 says alert conditions "must interrupt or be impossible to miss", rejects browser, sound, email,
and webhook channels, and keeps the room pull-first. An in-room surface cannot interrupt when the
browser is hidden or closed. This is an information-delivery contradiction, not a visual detail.

External products commonly separate notification channels from the underlying durable state; their
channel choices do not require this project to adopt those trust boundaries `[X]`. The local policy
may still reject them, but its promise must be honest.

**Required disposition:** For this scope, rename the contract to **in-room attention: impossible to
miss while the Control Room is foregrounded**. Record browser or external notifications as a deferred
delivery decision, not as functionality implied by the word "interrupt". A durable inbox must retain
what happened while the room was not foregrounded.

### IA7 - Global truth cannot qualify local data

**Severity: CRITICAL**

r5 promises data age and retained-window state per panel in its A10 disposition, but the concrete
layout supplies one global truth footer. A fresh SSE status, a five-second matrix snapshot, a cached
provider quota, a stale projection, a truncated transcript, and an estimated cost cannot share one
meaningful age or provenance label.

Sentry distinguishes lifetime issue totals from counts filtered by search, environment, and time
period, and preserves that scope while navigating events `[X]`. Grafana keeps time range, timezone,
and refresh explicit for the current dashboard or panel `[X]`. Those patterns reinforce the local
rule: truth belongs to the object whose interpretation it qualifies.

**Required disposition:** Keep only scope, browser connection, control epoch, and a compact degraded
summary globally. Attach source, observation time, age, window, truncation, revision, and
measured/estimated/unknown/unmeasured semantics to every consequential value. A selected object must
link to the event or record from which the value was derived.

### IA8 - Active-board-only polling can stale global attention

**Severity: HIGH**

r5 responds to r0 M8 by polling only the active board and pausing hidden surfaces. The attention
strip simultaneously depends on hidden Money, Health, and Decisions state. If Work remains active,
quota exhaustion, projection failure, worker loss, or a new approval can go stale precisely where r5
claims a global alert.

**Required disposition:** Split refresh responsibility by information role:

| Feed role | Cadence policy |
|---|---|
| current control and attention | Lightweight, always on while the room is active |
| selected object | One live stream plus bounded reconciliation `[M]` |
| active analytical lens | Poll while visible; abort or pause when hidden |
| historical or expensive data | Fetch on demand; mark its age |

Pause hidden heavy views, not the current-state facts required to keep global attention truthful.

### IA9 - Pending decisions are presented as counts, not decision objects

**Severity: CRITICAL**

ON-G5 and ON-A4 require the operator to know what needs a decision. r5 provides a Decisions board
and attention event but does not define the decision object. A count of approvals or a promotable tile
cannot tell the operator whether an action is still valid, what candidate it binds, or what evidence
supports it.

**Required disposition:** Every pending decision must expose, before actuation:

- exact target and run ID;
- current run state and control epoch/revision;
- gate ID and candidate SHA where applicable;
- proposer, rationale, and evidence authority;
- scope and expected blast radius;
- lease or budget consequence;
- reversibility and confirmation requirement;
- database-derived safe action;
- resulting decision and recording receipt.

Typed confirmation is necessary for destructive action but does not replace current-state validation.

### IA10 - Drill-down is specified as geometry, not navigation

**Severity: HIGH**

r5 says detail is docked on desktop and becomes a sheet on narrow screens. That defines placement,
not an investigation contract. It does not define selected-object identity, deep linking, browser
history, preservation of filters and time range, what happens when a live row disappears, or how
focus returns.

Sentry preserves search, environment, date range, and event-navigation context on issue detail `[X]`.
The checked Langfuse model structures observations inside traces and traces inside sessions `[X]`.
These examples support stable object identity and scoped investigation.

**Required disposition:** Specify the detail navigation contract:

- each selectable object has a type and stable key;
- selection survives live reconciliation and compatible lens changes;
- active scope, filters, sort, time range, scroll, transcript query, and follow/pause state persist;
- incompatible scope changes explicitly clear or confirm stale selection;
- loading, stale, disappeared, and permission-denied states retain object identity;
- closing detail restores focus to the originating object;
- exactly one selected event stream remains the measured invariant `[M]`.

### IA11 - Transcript, execution trace, and canonical lineage are conflated

**Severity: HIGH**

r5 describes a transcript, a lineage tree, and Registry lineage as related drill-down answers, and
calls Registry lineage a span/session tree. Those are different information structures:

- transcript is chronological output;
- execution trace is nested runtime causality;
- test/evaluator evidence is independent verification;
- registry lineage is supersession or cross-record causality;
- decision history records what the controller authorized.

Langfuse's data model distinguishes session, trace, and nested observation `[X]`. That does not prove
or replace this repository's canonical-record lineage.

**Required disposition:** Use a causal evidence ladder with explicit evidence classes:

```text
run -> phase -> attempt -> reasoning/tool event -> change/commit
    -> independent test/evaluator -> cost/lease provenance
    -> controller decision -> canonical record/supersession
```

Agent narration must never visually collapse into independently verified success. Registry lineage
must remain distinct from the execution trace while still being reachable from the affected run.

### IA12 - Design, Claude sessions, Flags, and Routing lose entry paths

**Severity: HIGH**

r5 says Design and Claude detail remain unchanged and Routing is folded into Work/detail. Its rail
contains only Work, Money, Health, and Decisions. The layout does not show the design-session roster,
Claude-agent roster, persistent supervisor Flags destination, or routing surface. An unchanged detail
panel is unreachable if its source list disappears.

This violates the r0 carry-forward requirement that every existing panel receive an explicit
disposition. It also risks regressing ON-D3, ON-D5, ON-D7, and the currently satisfied ON-A5.

**Required disposition:** Make design and background-agent sessions typed objects in the Work/Session
index, or retain a Sessions destination. Preserve a persistent visual supervisor-attention view even
if flags also enter the Attention Inbox. Place routing inputs and recommendation evidence in selected
run context, with an aggregate comparison lens. Add all four object classes to global search.

### IA13 - Cross-session search remains ambiguous and therefore absent

**Severity: HIGH**

r0 A8 asks for cross-session and log search. r5 says to build bounded search "on the log-stream
surface", which can still mean filtering only the selected transcript. It does not define searchable
objects, retained scope, time range, truncation, or how a result opens.

**Required disposition:** Separate two search modes:

1. **Object search:** run, phase, attempt, session, worktree, model, provider, lease, flag, approval,
   registry record, commit, and candidate SHA.
2. **Event search:** text and event fields across explicitly bounded retained sessions, with source,
   time range, and truncation visible.

Results must open the selected run's evidence ladder and preserve the query when the operator returns.

### IA14 - Fleet composition and fleet performance are conflated

**Severity: MEDIUM-HIGH**

ON-G7 asks for fleet shape by model, condition, and provider. r5 omits provider and proposes a status
grid plus small multiples. r0 A6 separately asks for cost/quality comparison. Composition/status and
performance comparison are different questions with different denominators and freshness needs.

**Required disposition:** Separate:

- **composition/status:** grouped counts and rates by model, condition, provider, and lifecycle;
- **performance:** cost, independently verified quality, latency, and sample coverage over a named
  time range.

Start with a sortable table or grouped counts. Add a chart only when its baseline, denominator,
completeness, and drill-through are explicit. Do not let comparison graphics outrank live triage.

### IA15 - Docs health and recording coverage have contradictory homes

**Severity: MEDIUM**

r5 assigns docs health to Decisions, Health, and the attention strip. It assigns recording coverage
to Decisions "or System", while the layout places recording in System. These unresolved placements
create duplicate attention and make the claimed complete disposition table non-deterministic.

**Required disposition:** Give each concept one owner and one escalation path:

- docs drift is a process-health item; a warranted proposal becomes a decision item;
- recording coverage is process health; a missing required record becomes an attention item;
- the durable evidence remains in its owning detail view, not copied into multiple boards.

Mirrors may summarize counts but must navigate to the same canonical object.

### IA16 - Mobile is only a reflow of desktop IA

**Severity: MEDIUM-HIGH**

r5 converts the dock to a sheet and reflows tables. That preserves geometry but not priority. A phone
cannot reproduce four peer boards, a fleet field, several charts, and a detail inspector without
turning the first screen into navigation.

**Required disposition:** Define mobile as a **triage and inspection mode**. Its first view contains
unresolved attention and recently changed runs. It preserves one selected object, its truth/evidence,
and safe-action preview. Fleet comparisons and historical charts are explicit secondary views. Sheet
acceptance must include focus containment, focus return, preserved query/time scope, and usable live
logs.

## Glance audit

| Need | r5 answer | IA verdict | Required placement |
|---|---|---|---|
| `ON-G1` whole system up / room connected | rail summary plus Health | **PARTIAL.** Browser connection, control-plane health, workers, and projections are conflated. | Persistent scope/truth chrome with separate named states. |
| `ON-G2` running / queued / failed / live | Work grid and live filter | **PARTIAL.** Work is not explicitly the default; making live a filter can hide it. | Default Fleet Triage list with live/change state always visible. |
| `ON-G3` failing / stalled / risk | attention strip | **FAIL AT SCALE.** No durable identity, ranking, lifecycle, or investigation. | Attention Inbox above or beside Fleet Triage. |
| `ON-G4` money | Money board | **FAIL.** First-class is not the same as first-visible. | Exception summary at rest; affected-run context; aggregate Money lens. |
| `ON-G5` needs my decision | Decisions board plus event | **FAIL.** Hidden on Work and lacks decision semantics. | Actionable decision objects in Attention Inbox and run context. |
| `ON-G6` fresh and trustworthy | footer plus Health | **FAIL.** Global truth cannot qualify local data. | Local source/age/scope on values; compact global degraded summary. |
| `ON-G7` fleet shape | status grid / small multiples | **FAIL.** Provider omitted; composition conflated with performance. | Secondary composition lens with complete dimensions and denominators. |

## Drill-down audit

| Need | r5 answer | IA verdict | Required disposition |
|---|---|---|---|
| `ON-D1` one cell step by step | docked transcript | **PARTIAL.** Live detail survives, but chronology is not causal evidence. | Transcript inside the typed evidence ladder. |
| `ON-D2` why flagged / safe action | provenance plus typed door | **PARTIAL.** Target, epoch, scope, budget effect, and receipt are absent. | Decision preview backed by current `safe_actions`. |
| `ON-D3` design draft/validation | unchanged detail | **FAIL DISCOVERABILITY.** Sessions entry path disappears. | Typed design-session object and roster/search entry. |
| `ON-D4` canonical explanation | Registry under Decisions | **PARTIAL.** Evidence is separated from the affected run; trace and record lineage are conflated. | Registry record link in run evidence; separate canonical-lineage view. |
| `ON-D5` route and cost/quality | folded into Work/detail | **FAIL SPECIFICATION.** It appears in neither concrete layout block. | Recommendation inputs, evidence, and provenance in selected-run context. |
| `ON-D6` cost by step/model/cell | step detail plus Money rollup | **PARTIAL.** Attribution is split across views. | Local per-step provenance plus linked aggregate lens. |
| `ON-D7` manage background Claude session | unchanged detail | **FAIL DISCOVERABILITY.** No roster or destination is shown. | Typed background-session object with ownership and actions. |

## Alert audit

| Need | r5 answer | IA verdict | Required disposition |
|---|---|---|---|
| `ON-A1` run failed/timed out | attention event | **FAIL AT SCALE.** An event is not a persistent work item. | Keyed attention item linked to run and evidence. |
| `ON-A2` worker/projection unhealthy | strip from control packet | **PARTIAL.** Affected runs and local source age are absent. | Dependency item with impact list and drill-through. |
| `ON-A3` spend/quota threshold crossed | threshold band plus event | **PARTIAL.** Threshold source, crossing time, reset, attribution, and resolution are undefined. | Money-risk item with window/headroom context. |
| `ON-A4` controller decision pending | tile plus event | **PARTIAL.** No complete target/evidence/action contract. | Decision object with safe action and receipt. |
| `ON-A5` supervisor flag raised/changed | live announcement | **REGRESSION RISK.** Persistent visual Flags surface disappears. | Advisory inbox row plus deduplicated transition announcement. |
| `ON-A6` room data stale/disconnected | footer plus degraded banner | **PARTIAL/FAIL.** Staleness is not localized; the banner is absent from the layout. | Named dependency degradation and local stale markers. |

## r0 disposition audit

### Present but misplaced: M1-M14

| ID | r5 disposition result | Required correction |
|---|---|---|
| M1 money buried | Partial | Money leaves System but remains hidden from default run context. |
| M2 projections unrendered | Partial and duplicated | Define global summary, dependency detail, and affected-run roles instead of copying state into three surfaces. |
| M3 control packet absent | Incomplete | Make it the current overview authority; preserve epoch and safe-action derivation. |
| M4 Registry overflow | Partial | Promote the authority, but link evidence directly from the selected run/decision. |
| M5 docs health below fold | Contradictory | Assign process health one owner; promote only warranted decisions. |
| M6 incomparable sparklines | Partial | Removal is correct; weakly justified replacement charts must not inherit the same noise. |
| M7 duplicate Live list | Partial | Merge the list, but keep live/change state visible without requiring a filter. |
| M8 hidden polling | Unsafe as written | Pause heavy analytical views, not current control/attention facts. |
| M9 inaudible rail mirrors | Wrong mechanism | Make ordinary values labelled/readable; do not make every changing metric a live announcement. |
| M10 pseudo-button rows | Pass | Real controls inside semantic table rows are the right disposition. |
| M11 reinterleave affordance | Partial | Add order/target preview, idempotency state, and recording receipt. |
| M12 recording absent | Fail | Resolve "Decisions or System" and distinguish health from a warranted action. |
| M13 reparented strip | Partial | Avoid both movement and duplicated current-state writers; use one canonical summary projection. |
| M14 native confirms | Partial | Shared typed doors help but do not replace safe-action validation and preview. |

### Absent surfaces: A1-A12

| ID | r5 disposition result | Required correction |
|---|---|---|
| A1 health/alert aggregate | Fail | Build a stateful attention model, not only a strip plus Health board. |
| A2 projection/latency health | Partial | Add impact and local provenance. |
| A3 approval/permanence queue | Partial | Define complete decision objects and current safe actions. |
| A4 worker health | Partial | Link worker state to affected runs and sessions. |
| A5 historical trends | Partial | Place as secondary analysis tied to a decision and named time scope. |
| A6 cost/quality rollup | Fail | Separate composition/status from performance and sample coverage. |
| A7 operator topology | Mis-ranked | Keep out of rest view unless live, scoped, and actionable. |
| A8 cross-session search | Fail | Define object search and bounded fleet event search separately. |
| A9 notifications | Explicit rejection with contradiction | Narrow promise to foreground in-room attention; retain durable unseen history. |
| A10 data age/timezone | Fail | Per-object truth is promised but a global footer is drawn. |
| A11 auth/multi-operator | Accepted scope policy | Preserve actor identity and recording on consequential actions. |
| A12 mobile data surfaces | Fail | Reflow is not a triage/inspection mode. |

## Internal contradictions in r5

| # | Contradiction | Required resolution |
|---:|---|---|
| 1 | Glance requires no interaction, but only one of four boards is active. | Put required summaries on the default Fleet Triage surface. |
| 2 | Evidence must be one step from action, but one run spans five surfaces. | Join run context in one inspector. |
| 3 | A single health score is rejected, but the rail has an undefined overall status. | Separate connection, control, dependency, and freshness states. |
| 4 | The attention prose includes eight signal classes; the diagram shows only failures, approval, projection lag, and docs. | Specify complete typed attention inventory. |
| 5 | An alert log is promised but absent from the layout. | Add the durable Attention Inbox. |
| 6 | Alerts must interrupt, but all out-of-room delivery channels are rejected. | Narrow the promise or separately authorize a channel. |
| 7 | Hidden boards stop polling, but global attention depends on their state. | Split lightweight current state from heavy board data. |
| 8 | Calm operation forbids announcement floods, but ordinary rail metrics become a live region. | Keep one transition-only live region; ordinary metrics are readable, not live. |
| 9 | Docs health belongs to Decisions, Health, and Attention. | Assign one owner and one escalation rule. |
| 10 | Recording belongs to Decisions or System, while the diagram chooses System. | Resolve the disposition before the brief. |
| 11 | A10 says freshness per panel, while the layout shows one footer. | Put truth on each object/value. |
| 12 | ON-G7 requires provider, while r5 names model and condition only. | Add provider or explicitly revise the need. |
| 13 | Design and Claude detail remain unchanged, but Sessions disappears from navigation. | Preserve or replace the source rosters explicitly. |
| 14 | Routing is folded into Work/detail but appears in neither concrete block. | Place it and define the selected-object relationship. |
| 15 | Supervisor announcements remain, but the persistent Flags destination disappears. | Preserve durable visual access to advisory flags. |
| 16 | Registry is both a destination and a lineage tree without defining execution vs canonical lineage. | Separate the structures and connect them by stable IDs. |
| 17 | Small multiples are prescribed for fleet shape, then described as thin and dropped as a default. | Remove default status until evidence and operator question justify it. |
| 18 | Every r0 panel supposedly has a disposition, yet several existing entry paths are absent. | Add a panel-by-panel migration map to the brief. |

## Required IA for the facelift brief

```text
PERSISTENT SCOPE / TRUTH
repository | worktree/campaign scope | browser connection | control epoch | degraded summary

ATTENTION INBOX
pending decisions | run failures/stalls | money risk | worker/projection impact
advisory flags | process gaps

FLEET TRIAGE (default resting body)
keyed runs/cells | current phase | changed-at | attention state
constraint exception | affected dependency | pending decision

SELECTED RUN / SESSION
identity + current truth
phase -> attempt -> events/tools -> change/commit -> independent verification
cost/lease provenance -> decision -> registry record

SAFE ACTION
target + epoch/revision + scope + budget effect + reversibility
preview -> typed confirmation when required -> execute -> receipt

SECONDARY LENSES
Money | Health | Decisions | Registry | composition/performance | history
```

The ordering is deliberate:

1. Persistent scope and truth qualify everything but consume little attention.
2. Attention is the operator's unresolved work, not a decorative banner.
3. Fleet Triage remains visible while one object is investigated.
4. Evidence and constraints join around the selected object.
5. Action follows evidence and current-state validation.
6. Comparisons, charts, and topology support deliberate analysis after live exceptions are handled.

## Required dispositions for r7

These dispositions are blockers for emitting the facelift brief:

1. **Replace the no-interaction fiction.** Show ON-G1..G6 simultaneously in compact form on the
   default Fleet Triage surface, or explicitly narrow and re-approve the glance contract.
2. **Make the control packet authoritative.** Current runs, pending decisions, worker/projection
   health, degraded state, control epoch, and safe actions come from one current-state projection.
3. **Replace the attention strip with an information model.** Define item identity, priority,
   timing, scope, state, authority, evidence, and resolution before styling it.
4. **Separate disclosure from alert lifecycle.** Overview/detail is one axis; event/status/attention/
   notification/resolution is another.
5. **Join decision context around the selected run.** Work, money, health, approval, evidence, and
   action cannot require five board hops.
6. **Put truth on objects.** Keep a global degraded summary, but source/age/scope/window/revision and
   uncertainty travel with consequential values.
7. **Define the detail navigation contract.** Preserve identity, filters, time range, scroll, focus,
   search, and follow state across live updates and compatible lens changes.
8. **Separate evidence structures.** Transcript, runtime trace, independent verification, decision
   history, and canonical lineage remain distinct but linked.
9. **Restore all entry paths.** Design sessions, Claude sessions, Flags, Routing, Registry, recording,
   and queue controls need explicit migration destinations and global search classes.
10. **Make cross-session search real.** Specify object search and bounded event search with scope,
    time range, truncation, and return-path behavior.
11. **Use honest alert language.** In-room-only means foreground attention plus durable unseen history,
    not guaranteed interruption.
12. **Define mobile as triage/inspection.** Do not accept a stacked desktop dashboard as responsive IA.
13. **Keep aggregate analysis secondary.** Fleet composition, cost/quality trends, charts, and topology
    must not precede live attention and evidence.
14. **Preserve measured guardrails.** Keep two-layer reconciliation, one selected stream, keyed
    write-on-change rendering, safe DOM construction, mutation/idempotency gates, accessible focus,
    and the no-build delivery constraint `[M]`.

## Sources checked

Direct checks are bounded observations. They support the stated interaction patterns, not universal
claims or the r5 taxonomy.

| Source | IA observation used |
|---|---|
| [Linear Triage](https://linear.app/docs/triage) | Triage is a durable queue with accept, duplicate, decline, snooze, responsibility, and ordered rules. |
| [Linear Inbox](https://linear.app/docs/inbox) | Notifications have priority/read/snooze/search behavior and open an owning issue; Inbox is distinct from Triage. |
| [Sentry Issue Details](https://docs.sentry.io/product/issues/issue-details/) | Issue scope, filtered event counts, evidence, actions, activity, first/last seen, and event navigation coexist in one investigation context. |
| [Grafana alert evaluation](https://grafana.com/docs/grafana/latest/alerting/fundamentals/alert-rule-evaluation/) | Alert instances have explicit pending, alerting, recovering, resolved, no-data, and error semantics; notifications route on transitions. |
| [Datadog Triage Inbox](https://docs.datadoghq.com/events/triage_inbox/) | Related events become sortable, assignable work items with split-view investigation, escalation, merge/split, and resolution. |
| [Grafana dashboard use](https://grafana.com/docs/grafana/latest/dashboards/use-dashboards/) | Time range, timezone, refresh, filters, and cancellation are explicit scope controls rather than one generic freshness footer. |
| [Langfuse data model](https://langfuse.com/docs/observability/data-model) | Sessions group traces; traces group nested observations such as LLM, tool, and retrieval steps. |
| [Railway CLI](https://docs.railway.com/guides/cli) | Target context, status, logs, usage, plan/apply, and machine-readable output are explicit command concepts. |
| [k9s commands](https://k9scli.io/topics/commands/) | Context, namespace, resource, filters, readonly mode, escape, and confirmation behavior are visible operator grammar. |
| [WCAG 2.2 status messages](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html) | Dynamic status must be programmatically exposed without unnecessary focus changes or excessive interruption. |

**Result:** r6c does not approve the r5 information architecture. The facelift brief must put
triage first, evidence second, safe action third, and aggregate analysis fourth. It must preserve the
fleet while the operator investigates, and it must never make a board switch the price of knowing
whether a visible run is current, affordable, verified, or awaiting a decision.
