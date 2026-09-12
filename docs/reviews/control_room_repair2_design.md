---
status: accepted
---

# Control Room repair2 -- distinctive design / thesis verdict

**Reviewer:** `openai/gpt-5.6-luna`
**Date:** 2026-09-11
**Scope:** `docs/research/control_room_direction.md`, `docs/research/control_room_ia.md`, and the
repaired quoted-evidence artifacts under `experiments/research/control_room/`.

## Verdict: PASS at design level

The direction now names **eight** distinctive moves. Each move has all three required parts:

1. a named exemplar pattern with current repaired support or a direct checked exemplar;
2. a specific behavior that changes when the object is an AI-agent run; and
3. a visible screenshot carrier that a stranger can point to.

The thesis no longer depends on mood, color, or the assertion that a roster is “agent-native.” The
resting composition is explicitly a **run ledger with annotation gutters**: session identity, terminal
target, current command, attempt, evidence authority, lease constraint, eligibility, and recording
coverage are visible before selection. `R1` and `R3` are prohibited from becoming peer card boards.

This is a design-level PASS, not an implementation claim. The facelift and screenshot gate remain
future work. The implementation fails the design if it restores the generic shell described below.

## Explicit Pass Conditions

| Condition | Result | Evidence |
|---|---|---|
| Direction names at least six exemplar-grounded distinctive moves. | PASS | §4.1 names eight moves; each has an exemplar, the changed agent-run behavior, and a screenshot carrier. |
| No qualifying move reads as generic dashboard grammar. | PASS | The moves are session identity, attempt/evidence authority, governed decision doors, typed addresses, lease-attached cost, one selected evidence feed, and durable run attention. The direction explicitly rejects KPI cards, peer boards, chart walls, lifecycle-only rows, and transcript sidebars. |
| The recognizability test is concrete and would hold for a stranger seeing a screenshot. | PASS | §4.2 now specifies resting screenshots with no selection, fixed fixtures, two viewports, a ten-second limit, five statements, pixel carriers, prohibited help/hover/selection, and a generic comparator. The IA adds B-9..B-11 and G-13 for the same carriers. |
| If the screen still reads as a monitoring console, the failure elements are named. | PASS | §4.5 has a hard failure rule and lists lifecycle-first rows, money/health/fleet KPI cards, generic alert tiles, transcript sidebars, and selection-only evidence/action cues to kill. |

## Findings

| ID | Severity | Finding | Result / disposition |
|---|---|---|---|
| D1 | BLOCKER | The previous structure was still “truth bar → attention inbox → run roster → constraint rail → selection dock,” which could be mistaken for observability tooling with runs substituted for services. | **CLOSED at direction/IA level.** The primary object is now the R2 run ledger. R1/R3 are annotation gutters, not peer panels; rows carry agent identity, attempt, evidence authority, eligibility, and receipt coverage. |
| D2 | BLOCKER | The previous recognizability test depended on selected-run inspector content even though R4 is hidden at rest. | **CLOSED.** The five statements now use resting-screen carriers. Claim/proof, hard-budget cost, waiting authority, and recorded action are required on the visible R2 row/R1/R3 context. |
| D3 | HIGH | Several q1 counts and citations were stale after quoted-evidence repair. | **CLOSED.** §4 uses current supports: session grouping 7, trace tree 17, waterfall 3, alerting 6, keyboard-first 6, direct command palette 1, eval loop 21, cost attribution 4, live-follow 10. Unsupported log-stream composition remains `[P]`. |
| D4 | HIGH | “Exemplar-grounded” could be misread as external proof of the full Control Room composition. | **CLOSED.** §4.0 keeps pattern `[X]`, repository contract `[M]`, and composition `[P]` separate; the new distinctiveness gate requires the changed agent-run action and visible carrier, not just a catalog citation. |
| D5 | HIGH | The design needed a non-generic visual grammar rather than a new token palette. | **CLOSED.** The required grammar is session identity band, attempt boundary, ADVISORY/MEASURED/SOURCE marks, lease-attached cost, typed eligibility, and receipt coverage. Tokens remain hygiene. |
| D6 | MEDIUM | A live stream could reintroduce log-viewer or chart-wall grammar. | **CLOSED as a bounded policy.** Only one selected evidence feed may follow/pause; `tech-viz-log-stream` is not used as external support, and ambient charts/per-card sparklines are prohibited. |

## Eight Distinctive Moves

| Move | Current exemplar grounding | Agent-run difference | Screenshot carrier |
|---|---|---|---|
| 1. Session is the addressable object | `tech-ops-session-grouping`, support 7, agentops-only | session/agent leads; worktree, terminal, command, provider/model, and attempt follow | R2 identity band |
| 2. Attempt ledger, not monitoring record | `tech-ops-trace-tree`, 17; `tech-viz-waterfall-timeline`, 3 | session → phase → attempt with typed evidence instead of service latency | attempt boundary and evidence sequence |
| 3. Governed decision door, not button | `tech-trust-alerting`, 6, plus repository safe-action graph | eligibility, authority, epoch, blast radius, reversibility, and receipt govern the act | eligibility token + R1 decision item |
| 4. Claim versus proof | `tech-ops-eval-loop`, 21 | ADVISORY claim cannot earn a pass; MEASURED test-runner proof is authoritative | paired ADVISORY/MEASURED marks on R2 |
| 5. Typed addresses replace dashboard navigation | `tech-int-keyboard-first`, 6; direct command-palette record, 1 | run/phase/attempt/session/worktree/lease/flag/approval/record grammar | visible typed address and keyboard path |
| 6. Cost attached to attempt and lease | `tech-money-cost-attribution`, 4 | reserved/settled, cost source, cap headroom, settlement, and unknown-not-zero | lease/cost band attached to R2 row; R3a constraint ledger |
| 7. One selected evidence feed | `tech-int-live-follow`, 10; log-stream node deliberately `[P]` | one bounded, aged feed with follow/pause and evidence classes | selected-feed affordance, never chart wall |
| 8. Durable run attention | `tech-trust-alerting`, 6, plus direct Linear Triage lifecycle check | severity × actionability ranking across runs, workers, projections, and money risk | durable R1 item with lifecycle and eligibility |

## Recognizability Protocol

The reviewer receives two screenshots: 1440×900 and 390×844, both at rest, with no run selected and
this document hidden. The fixture includes one waiting-for-approval session, one failed session, one
running session, and one near-cap lease. The reviewer has ten seconds per image, may not hover, open R4,
read explanatory prose, or infer state from color alone, and must point to the relevant pixels.

| Statement | Required visible carrier |
|---|---|
| “These are AI agent sessions, not services.” | session/agent, terminal target, current command, provider/model, attempt |
| “That run is waiting on a person.” | `approve` token, controller authority, waiting state, and R1 decision item |
| “This is spend against a hard budget.” | attached reserved/settled lease band, cost source, headroom, and R3a exception |
| “The agent claimed it passed, but that is not the verified result.” | paired ADVISORY claim and MEASURED test-runner result |
| “I can act from here, and it will be recorded.” | eligibility token adjacent to `recorded`/`missing` receipt coverage |

Pass requires 5/5 statements in both screenshots. A generic observability comparator must fail at least
statements 1, 4, and 5. Any answer requiring selection, hover, color-only interpretation, or hidden
inspector content is a failure.

## Kill List If the Thesis Regresses

If a screenshot still reads as a monitoring console, kill these elements before accepting the facelift:

- lifecycle-first rows with no session, terminal, command, provider/model, or attempt identity;
- money, health, or fleet KPI cards rendered as peer dashboard panels;
- generic red alert tiles without run identity, lifecycle, actionability, and authority;
- transcript-plus-metadata sidebars that hide the claim/proof distinction;
- evidence or action cues that appear only after selection;
- per-card sparklines, chart walls, unconditional gauges, or ambient topology diagrams;
- command palette as primary navigation rather than an accelerator for typed addresses;
- decorative glow, pulse, repeated neon marks, or uppercase telemetry texture.

These are thesis failures, not copy or styling issues.

## Remaining Gate

The direction and IA now pass the thesis review. The implementation must still run the q2 geometry,
blind-comprehension, accessibility, and event/state gates. The implementation must not be called a pass
until the two resting screenshots satisfy the protocol above and the IA `G-13`/`B-9..B-11` checks pass.
