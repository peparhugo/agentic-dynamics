---
status: accepted
---

# Control Room research - design critique (campaign r6b)

**Date:** 2026-09-11
**Pass:** adversarial pass 2 of 3; design critique
**Subject:** `docs/research/control_room_direction.md` (r5)
**Inputs:** the measured portal audit (`docs/research/control_room_audit.md`), the operator-needs
contract (`docs/research/control_room_questions.md`), the r5 direction, the r6a entailment review,
and direct checks of the cited exemplars listed in the appendix.

## Verdict

**REWORK REQUIRED before the facelift brief.**

The r5 direction is disciplined about existing data, accessibility, and no-regression constraints.
It is not yet a distinctive product direction. Its central composition - rail, attention strip,
domain boards, cards, charts, docked detail, and a truth footer - is a familiar observability
dashboard pattern. It would produce a cleaner dashboard, but it would not yet make the operator feel
that this is the control surface for multiple CLI coding agents.

The design should be re-centered on the thing this room uniquely operates: a live run that may need
triage, evidence, and a controlled human decision. The visual system should make that object and its
causal evidence feel immediate. Dark surfaces, an iris accent, sparklines, gauges, topology SVG, and
the phrase "premium flight deck" are not a product identity by themselves. They are styling around a
generic dashboard grammar and risk reading as a dated monitoring-console costume.

The strongest replacement direction is:

> **An evidence-first run triage console:** a calm, terminal-native surface where unresolved work is
> triaged first, every run opens into a causal evidence ladder, and every control previews its target,
> scope, revision, reversibility, and recording before it acts.

This is a design policy, not a claim that the web corpus proves one canonical layout. The local audit
proves the problem; the external exemplars supply bounded interaction patterns; the proposed synthesis
must be labelled `[P]`.

## Evidence discipline

This review separates three kinds of statement:

- `[M]` measured in the repository, primarily from r0 and the current portal contract.
- `[X]` observed in an external exemplar or normative reference checked on 2026-09-11.
- `[P]` a proposed design policy for this product.

The r6a review already found that several r5 support counts were inflated by broad taxonomy labels.
That affects the confidence of the r5 chart and board claims, not only their footnotes. In particular,
r6a E1-E7 means that `board-per-domain`, gauges, status grids, virtualized tables, money grouping,
degraded banners, uncertainty encoding, and several superlative claims must not be presented as
external convergence until the crosswalk is repaired. This review therefore treats the r5 layout as
a proposal driven by local needs, not as a researched default.

## Findings

Findings are ordered by the cost of carrying the mistake into the facelift brief.

### D1 - The direction is a dashboard template, not a product identity

**Severity: HIGH**

The r5 concrete layout is a conventional operations-dashboard stack:

```text
rail -> attention strip -> board of panels -> docked detail -> freshness footer
```

Grafana documents the same broad vocabulary: dashboard panels and rows, filters, time range,
refresh, dashboard navigation, and a command palette. Datadog documents grid/timeboard/screenboard
layouts composed of graphs, logs, lists, and tables. Those are good precedent for familiar controls,
but they also prove the problem: a rail plus a panel field is the category default, not a distinctive
answer for a multi-agent CLI room.

**Why this misses the mandate.** A screenshot of r5 could be mistaken for Grafana, Datadog, or an
internal admin dashboard after the logo and color tokens were removed. Nothing in the first screen
says that the primary object is an agent run with attempts, tools, tests, ledger facts, and a human
control boundary.

**Required disposition:** Replace "Instrument Panel" as the product thesis with the evidence-first
run-triage thesis above. Keep the rail, if useful, as navigation chrome only. Make the run/cell,
triage state, causal evidence, and safe action semantics the identity-bearing elements.

### D2 - Four peer boards will fragment one operational decision

**Severity: HIGH**

r5 promotes Work, Money, Health, and Decisions to peer destinations. The audit does establish that
money, projection health, approvals, and registry facts are currently misplaced or absent `[M]`.
It does not establish that four peer boards are the right answer. r6a E2 specifically rejects the
claim that the corpus demonstrates a dominant board-per-domain pattern.

The split also creates a predictable operator tax:

- a failed run appears on Work;
- its projection lag appears on Health;
- its reserved budget appears on Money;
- its promotable candidate appears on Decisions;
- its explanation appears in Detail.

The operator has to reconstruct one decision across five places. That is the opposite of evidence at
hand. The money and health facts matter because they change the decision about a particular run; they
should not be made into mandatory context switches before that run can be understood.

**Required disposition:** Make **Triage / Work** the primary surface. Treat money, health, registry,
and approvals as lenses and context attached to a selected run, with aggregate views available when
the operator is comparing the fleet. Do not delete the underlying capabilities; change their
hierarchy and join them to the run object.

### D3 - The attention strip is an alert dump unless it has a state machine

**Severity: HIGH**

r5 places failed runs, projection lag, unhealthy workers, approvals, and docs warnings in one live
strip and proposes an `aria-live` announcement path. This is visually plausible and operationally
underspecified. It mixes distinct objects, severities, owners, freshness states, and actionability
into one horizontal sentence.

The accessibility references do not justify announcing every strip rewrite. WCAG 2.2 requires status
messages to be programmatically determinable without moving focus; MDN describes `role="status"` as a
polite live region with implicit atomic updates. A frequently rewritten aggregate can therefore
repeat the entire strip to a screen-reader user. The visual equivalent is also noisy: a 1-second tick
can make the room feel permanently urgent even when no decision changed.

Linear's Triage is a more useful exemplar than a generic alert bar: it is an inbox with explicit
accept, duplicate, decline, and snooze outcomes, responsibility, and ordered automation. The lesson
is not to copy Linear's issue workflow. The lesson is to model attention as stateful work to resolve,
not as decoration at the top of a dashboard.

**Required disposition:** Define an attention state machine before specifying the strip:

| State | Meaning | Visible treatment | Announcement |
|---|---|---|---|
| `new` | A consequential item has appeared | one deduplicated inbox row | polite, once |
| `active` | The operator is inspecting it | selected row and object context | none on ordinary refresh |
| `snoozed` | The operator deferred it | hidden from default queue, history retained | none |
| `resolved` | Evidence or action closed the item | history/audit entry | action result only |
| `stale` | The item or its source can no longer support a fresh decision | explicit stale marker | announce only on transition |

Each item needs a stable key, severity, first-seen time, last-change time, owner, source, reason,
and safe next action. A live region may announce transitions in that state machine; it must not read
the entire aggregate on every poll. The supervisor remains flag-only: an attention item proposes; it
does not steer.

### D4 - The truth bar is too passive to carry trust

**Severity: HIGH**

r5's footer reads like a global status legend: age, retained window, provenance class, and timezone.
Those facts are useful, but a footer cannot explain which source, scope, revision, or partiality
belongs to each consequential number. A stale registry count and a fresh live event should not share
one undifferentiated "age 4s" label.

Grafana makes time range, timezone, refresh, and cancellation explicit in the object being viewed.
Langfuse describes traces as structured records of prompt, response, tokens, latency, tools, and
retrieval steps. Phoenix separates trace inspection, evaluation, prompt iteration, and experiments.
These exemplars point toward local context and inspectable lineage, not a single global trust ribbon.

**Required disposition:** Keep a compact room-level freshness summary, but attach provenance to the
metric or object that can cause a decision. At minimum, the inspector must expose:

- source and projection, for example ledger, Redis, registry, or browser state;
- observed time and age;
- scope, retained window, and truncation/partiality;
- revision or control epoch where applicable;
- measured, estimated, unknown, or unmeasured semantics;
- the exact record or event from which the displayed value was derived.

The design must not use a green room badge to imply that a stale or unmeasured subsystem is healthy.

### D5 - The visual language risks a dated retro-ops costume

**Severity: HIGH**

The r5 direction and its predecessor refresh design accumulate a recognizable 2010s monitoring
recipe: near-black canvas, graphite cards, mono telemetry, uppercase micro-labels, neon semantic
hues, glowing selection, a signature accent, sparklines, gauges, and a technical topology diagram.
Each ingredient can be defensible. Together they read as "industrial control panel" before they read
as a coherent product for reasoning agents.

The phrase "premium flight deck" is especially risky. It asks the implementation to perform a mood
rather than to solve a user problem. A dark theme, token layer, contrast bar, forced-colors path,
reduced motion, and non-color status encoding are quality constraints `[P]`, not evidence that the
result will be sleek or sexy. r6a also records that the corpus' aesthetic field is text-limited, so
the visual claim cannot be upgraded to external fact.

**Required disposition:** Keep the accessibility and token requirements. Remove "flight deck",
"expensive-feeling", and similar mood language from acceptance criteria. Reduce visual signature to
three product behaviors:

1. **Quiet until a decision changes.** No decorative pulse, dashboard theater, or update animation.
2. **Sharp at the selected object.** Selection reveals causal evidence and safe next action, not a
   brighter card border alone.
3. **Terminal-native without cosplay.** Use keyboard addressability, compact textual state, stable
   focus, and bounded live output. Do not use monospace, glyphs, or neon as a substitute for those
   behaviors.

The visual brief should specify hierarchy, rhythm, and state transitions; it should not prescribe a
brand accent as the source of distinctiveness.

### D6 - The chart proposition is cargo-culted

**Severity: HIGH**

r5 section 7 maps questions to status grids, gauges, tables, log streams, timelines, and small multiples,
then calls several of them defaults. The mapping sounds rigorous, but r6a E1 and E5 show that the
underlying mark-specific support was inflated or thin. A chart catalog can still be useful; it must
not become a gallery of expected dashboard furniture.

The operator does not need a gauge because gauges look operational. The operator needs to know, for a
bounded question, whether to wait, inspect, retry, approve, or stop. A number, ordered list, or short
evidence sentence may answer that faster and more accessibly than a mark.

**Required disposition:** Remove unconditional chart defaults from the direction. Every chart in the
brief must state:

- the operator question and decision it changes;
- the comparison baseline and time scope;
- the data completeness and sampling rule;
- the textual/table equivalent;
- the fallback when there are too few or too many observations;
- a performance and focus-preservation budget.

Prefer a compact triage list, counts, rates, and a causal timeline in the first implementation. Add a
chart only when a screenshot or usability check shows that it improves a specific decision.

### D7 - A topology SVG can become documentation theater

**Severity: MEDIUM**

The audit correctly finds that the existing architecture SVG is orphaned and describes the research
loop rather than the operator topology `[M]`. r5's proposed replacement, `queues -> broker -> workers
-> cells -> sessions -> projections`, is directionally more relevant but is still a static diagram
unless it reflects current health and selection.

Embedding a fixed architecture picture in a live room would consume scarce attention without
answering what is failing now. It would also duplicate documentation that belongs outside the active
triage loop.

**Required disposition:** Choose one of two explicit policies:

- make topology a scoped, data-linked inspector that highlights the selected run's dependencies,
  current lag, and affected records; or
- keep it out of the resting room and link to the architecture documentation from System/help.

Do not ship a decorative diagram merely because an SVG asset exists.

### D8 - The command palette is an accelerator, not yet a CLI control model

**Severity: MEDIUM**

r5 keeps a command palette beside a visual board. That is the correct rejection of palette-only
navigation, but the proposal stops at `Cmd/Ctrl+K`. It does not define what the operator can address,
how context is shown, or how a mutation is previewed.

Warp's command palette searches typed object classes such as sessions, files, workflows, and actions.
k9s makes resource, namespace, context, filtering, readonly mode, and escape behavior explicit.
Railway's CLI exposes target service/environment options, JSON output, and a plan/apply distinction.
These are more relevant to a CLI-agent room than a generic palette affordance.

**Required disposition:** Define a terminal grammar for the room:

- addressable objects: run, phase, attempt, worktree, model, lease, flag, approval, record;
- visible context: repository, worktree, model, provider, cell, revision, and permission boundary;
- query verbs: filter, inspect, attach, compare, and show evidence;
- control verbs: preview, authorize, execute, settle, and record;
- escape behavior: one-key cancel/close, preserved selection, and no accidental destructive action;
- readonly mode: visible and enforceable, not just a disabled-looking button.

The visual layer can remain build-less. This disposition concerns the interaction contract, not a
framework choice.

### D9 - The agent-specific surface is still generic transcript detail

**Severity: MEDIUM-HIGH**

r5's docked detail includes transcript, provenance, lineage, and per-step cost. That is a good start,
but it still reads like a generic log viewer with an observability sidebar. Langfuse describes the
trace as a structured causal record of model calls, retrieval, tools, tokens, latency, and outputs.
Phoenix similarly separates a run's trace from evaluations, prompt iteration, and same-input
experiments. These exemplars support the causal structure, not the r5 claim that every major agent-ops
product has the same exact waterfall.

The Control Room also has a repository-specific distinction that the direction does not make visually
primary: the agent's narrative is not independent verification. A model can say it passed while the
test runner, ledger, or registry says otherwise.

**Required disposition:** Replace generic "transcript plus lineage" language with a causal evidence
ladder:

```text
run -> phase -> attempt -> tool/reasoning event -> change/commit -> independent test/evaluator
    -> ledger cost/provenance -> registry/canonical record
```

Show agent-reported facts, measured runtime facts, and controller decisions as separate evidence
classes. The selected run should answer "what happened, what was independently verified, what remains
unknown, and what can I safely do next?" without switching boards.

### D10 - No-build is a constraint, not a design virtue

**Severity: MEDIUM**

The no-build shell is a real local guardrail `[M]` and should be preserved for this facelift. It is
not a web-researched aesthetic or proof that React is unnecessary. r6a E7 explicitly identifies
that absence-to-necessity inference.

**Required disposition:** State no-build under implementation constraints and preserve the current
classic-script, safe-DOM, keyed-reconciliation contracts. Do not use "vanilla" as part of the product
identity. If the framework constraint changes, compare delivery models separately rather than making
the visual direction carry that decision.

### D11 - Mobile is described as reflow, not as an operator mode

**Severity: MEDIUM**

r5 correctly says that the dock becomes a sheet on narrow screens, but a sheet is a geometry decision,
not a mobile strategy. A phone cannot reproduce a wide fleet wall by stacking four boards and every
chart. The operator on a narrow viewport needs to identify what changed, inspect one run, and either
defer or take a safe action.

**Required disposition:** Define mobile as **triage and inspection mode**:

- default to unresolved attention items and recently changed runs;
- preserve one selected object and its evidence ladder;
- expose target context and safe actions before secondary charts;
- make fleet comparison an explicit filtered view, not a compressed desktop mosaic;
- keep the same truth/provenance semantics and focus return rules.

The desktop layout may retain a dense fleet lens. The mobile layout must not pretend to be the same
operations wall at a smaller width.

### D12 - Control semantics are less distinctive than the existing safety boundary

**Severity: HIGH**

r5 retains typed confirmation doors and idempotent mutation guards, but treats them mostly as visual
polish. In this product, the control boundary is part of the experience: supervisor flags propose,
the operator decides, leases bound spend, and recording closes the act. A sleek room should make that
boundary feel fast and trustworthy, not hide it behind a pretty button.

**Required disposition:** Every mutation in the brief must show, before execution:

- the exact target object and current selection;
- repository/worktree/model/provider context;
- requested scope and expected blast radius;
- current revision/control epoch and concurrency conflict behavior;
- reversibility or typed confirmation requirement;
- admission/budget effect where applicable;
- the resulting decision/recording receipt.

The visual treatment may be quiet. The preview cannot be optional. No visual redesign may turn a
flag into an automatic steer, interrupt, route, retry, or budget action.

## Operator-needs check

The r5 table covers the named needs, but coverage is not the same as good prioritization. The
following is the design critique of its answer:

| Need | r5 treatment | Critique | Disposition |
|---|---|---|---|
| `ON-G1` connected/up | rail badge plus Health | A badge is still too close to a single health number; connection and subsystem health differ. | Separate browser connection, control-plane health, and projection freshness. |
| `ON-G2` work now | Work board and fleet grid | Covered, but it is not yet the primary triage object. | Make runs/cells the main addressable list. |
| `ON-G3` failing/stalled/risk | attention strip | Covered as aggregation, not as resolvable work. | Use the stateful attention inbox. |
| `ON-G4` money | Money board | Local need is real; a peer board can fragment a run decision. | Show money in run context plus a fleet money lens. |
| `ON-G5` human decision | Decisions board | "Pending" is not enough; the operator needs target, rationale, and safe action. | Use approval/flag objects with preview and recording. |
| `ON-G6` trustworthy/fresh | truth bar | Footer-only provenance is too weak. | Put source, age, scope, and uncertainty on consequential objects. |
| `ON-G7` fleet shape | rollup and small multiples | Small multiples are thinly supported and can become chart furniture. | Add only for a demonstrated comparison question. |
| `ON-D1` step-by-step | transcript | A transcript is not a causal explanation. | Use the evidence ladder. |
| `ON-D2` why flagged/action | detail and typed doors | Good contract, but target/revision/scope are not first-class in r5. | Add a pre-action preview. |
| `ON-D5` routing cost/quality | routing in Work/detail | The proposed placement is plausible but needs object context and evidence quality. | Show decision inputs and provenance beside the recommendation. |
| `ON-D6` cost by step | detail plus Money | Covered only if cost provenance stays local to the step. | Keep measured/estimated/unknown on each cost value. |
| `ON-A1..A6` alerts | strip and live region | The intended coverage risks alarm fatigue and repeated announcements. | Implement the attention state machine and deduplication first. |

## Required dispositions for the next phase

These are blocking dispositions, not optional polish.

1. **Block brief emission on the r6a provenance issue.** Repair the r3 crosswalk and regenerate the
   affected support values, or explicitly downgrade each claim to `[P]`/`[X]` with its caveat. Do not
   carry inflated counts into r7/r8.
2. **Replace the r5 thesis.** Use evidence-first run triage as the product direction; keep
   "Instrument Panel" only as a rejected metaphor or implementation note.
3. **Recompose the IA.** Make one triage/work surface primary. Treat money, health, decisions, and
   registry as contextual lenses and destinations for deliberate comparison, not mandatory board
   hops for a single incident.
4. **Specify the attention state machine.** Stable keys, dedupe, first/last seen, owner, snooze,
   resolution, stale state, and announcement policy are required before an attention strip is accepted.
5. **Move truth to the object.** A global footer may summarize freshness, but every consequential
   number must carry source, scope, age, revision, partiality, and evidence path.
6. **Delete chart cargo cult.** Require a question, decision, baseline, completeness rule, and text
   equivalent before accepting any chart or topology mark.
7. **Add the terminal control grammar.** Define object addressing, context, readonly behavior,
   preview/apply semantics, escape paths, and JSON/recording-equivalent output where the portal can
   support it.
8. **Make agent evidence causal and typed.** Separate model narration, runtime measurements,
   independent tests/evaluators, costs, registry records, and controller decisions in the inspector.
9. **Treat mobile as triage/inspection mode.** Do not accept a stacked desktop dashboard as the
   responsive brief.
10. **Preserve the hard guardrails.** No new automatic actuation, no mutation trust-boundary bypass,
    no HTML-string rendering, no focus loss under live reconciliation, no false freshness, and no
    build-pipeline rewrite in this design pass.

## What to keep from r5

The critique is not a request to discard the useful work. Retain these parts after relabelling and
re-ranking them:

- the explicit r0 M1-M14 and A1-A12 disposition coverage;
- the two-layer poll/SSE reconciliation and keyed write-on-change discipline `[M]`;
- the selected-detail stream and bounded transcript behavior `[M]`;
- typed confirmation doors, idempotency, and the flag-only supervisor boundary `[M]`;
- accessible status language, forced-colors support, reduced motion, and non-color status cues `[P]`;
- dark/light token parity and a restrained density ladder, as implementation policies `[P]`;
- the prohibition on inventing model, condition, confidence, heartbeat, or quality encodings not in
  the current API `[M]`.

## Sources checked

These direct web checks are used as bounded observations, not as claims of universal convergence.
The repository corpus remains the canonical source for r5's `[src:*]` tags; this appendix records the
fresh direct checks that informed this adversarial pass.

| Source | What it actually supports in this review |
|---|---|
| [Linear Triage](https://linear.app/docs/triage) | A stateful inbox with accept, duplicate, decline, snooze, ownership, ordered rules, and conflict visibility. |
| [Grafana Use dashboards](https://grafana.com/docs/grafana/latest/dashboards/use-dashboards/) | Panels/rows, filters, time ranges, refresh, dashboard navigation, and a command palette: evidence that the r5 shell is familiar dashboard grammar. |
| [Datadog Dashboards](https://docs.datadoghq.com/dashboards/) | Grid/timeboard/screenboard compositions and graph/log/list/table widgets; useful precedent, not proof of four domain boards. |
| [Railway CLI](https://docs.railway.com/guides/cli) | Explicit service/environment targets, JSON output, plan/apply, usage, logs, and agent commands. |
| [Warp Command Palette](https://docs.warp.dev/terminal/command-palette/) | Typed search for workflows, prompts, notebooks, files, actions, sessions, and launch configurations. |
| [k9s Commands](https://k9scli.io/topics/commands/) | Resource/context/filter grammar, readonly mode, escape behavior, and asymmetric confirmation conventions. |
| [Langfuse tracing overview](https://langfuse.com/docs/observability/overview) | Structured traces containing prompts, responses, tokens, latency, tools, retrieval, cost, scores, and experiments. |
| [Arize Phoenix overview](https://arize.com/docs/phoenix) | Separate trace inspection, evaluations, prompt iteration, replay, datasets, and same-input experiments. |
| [WCAG 2.2 status messages](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html) | Status updates must be programmatically determinable without taking focus; live-region behavior must avoid unnecessary interruption. |
| [MDN `status` role](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/status_role) | `status` is polite and atomic by default; repeated aggregate updates can be noisy if not deduplicated. |

**Result:** r6b does not approve the r5 direction unchanged. The next brief should be visually
restrained, but its distinctiveness must come from triage, causal evidence, terminal context, and
safe control - not from a darker dashboard skin.
