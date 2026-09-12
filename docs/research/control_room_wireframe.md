---
status: accepted
---

# Control Room — annotated wireframe (campaign phase d4)

**Date:** 2026-09-11
**Workflow:** `workflows/repository/control_room_rules_design.yaml`, phase `d4_room_design`.
**Inputs:** `experiments/control_room_rules/surface_map.json` (d4),
`docs/research/control_room_state_screens.md` (d4),
`docs/designs/current/control_room_backend_requirements.md` (d3).
**Geometry authority:** `docs/research/control_room_ia.md` §3.2 (pixel budget) and §3.4 (R4
budgets); this document re-states them so the wireframe is self-contained and gate-checkable.

Every element is labeled with the **rule(s) `[R1]..[R10]`** and/or **job(s) `J1..J11`** it serves.
Rule labels are the acceptance hook: the future render gate asserts each rule appears
(§8 legend). All dimensions are CSS border-box pixels; `R4` is `0` at rest.

## 1. Viewports and grid rules

- Reference viewports: **1440×900** (desktop), **1024×768** (narrow), **390×844** (mobile).
- Outer padding: 16px desktop / 12px narrow+mobile. Inter-region gaps: 12px desktop / 8px narrow;
  mobile stacks with 8px gaps.
- Desktop places `R1 | R2 | R3` side by side; mobile stacks `R0 R1 R2 R3a R3b R3c`.
- Every region is fixed-height and **non-scrolling**; overflow is a drill-down (`R4`) or a lens,
  never an internal scrollbar.

## 2. Resting screen — 1440×900 (desktop)

```text
 16px pad                                                                         16px pad
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ R0  SYSTEM + TRUST  (H=72)                                              [J1][R1,R7][R10]  │
│  ┌ scope: repo/worktree/campaign ┐  ON-G1 browser up · control up · workers up · proj ○   │
│  └───────────────────────────────┘  ON-G6 epoch 8421 · worst 3s · stale 0 · partial 0 ·  │
│                                       unknown 0                                            │
├───────────────────────┬───────────────────────────────────────────┬──────────────────────┤
│ R1 ATTENTION (H=800)  │ R2 RUN LEDGER (H=800)                     │ R3 CONSTRAINTS (340) │
│  [J1,J2,J3]           │  [J1,J2,J3,J5,J7]                         │  [J1,J5,J7][R7,R10]  │
│  [R1,R5,R7,R8,R9]     │  [R1,R5,R7,R8,R9,R10]                     │                      │
│ ┌───────────────────┐ │ ┌ ON-G2  run 3 · queued 7 · fail 1 · live 4 ────────────────┐ │
│ │ R1a DECISION      │ │ │ (counts line H=40)                                        │ │
│ │  (ON-G5)          │ │ ├───────────────────────────────────────────────────────────┤ │
│ │ pending: promote  │ │ │ row  identity·target·model·attempt  (line 1)               │ │
│ │ run r-8821 gate g5│ │ │      phase 3/5 · running · live      (line 2)             │ │
│ │ epoch 8421 auth C │ │ │      ADVISORY│MEASURED · commit · cost-src · eligibility · │ │
│ │ elig: approve     │ │ │      receipt                                              │ │
│ └───────────────────┘ │ │ (H=88 per row, 8 rows)                                     │ │
│ ┌───────────────────┐ │ │  ...                                                       │ │
│ │ R1b RISK  (ON-G3) │ │ └───────────────────────────────────────────────────────────┘ │
│ │ failed r-8804     │ │                                                            │
│ │ action: triage    │ ├─ R3a COST  (ON-G4, H=220) ─────────────────────────────────┤
│ └───────────────────┘ │ │ spend $41.20 · burn $0.34/m · quota 18% · wallet $9.80 ·  │
│ ┌───────────────────┐ │ │ leases $1.05 · ⚠ money-risk none        [R3,R7,R10]        │
│ │ R1c NEXT          │ ├─ R3b HEALTH DETAIL (H=180) ────────────────────────────────┤
│ │ stalled worker w3 │ │ workers 0 unhealthy · projections worst lag 3  [R9]         │
│ └───────────────────┘ ├─ R3c COMPOSITION (ON-G7, H=140) ───────────────────────────┤
│                       │ │ model DS│other│unk  cond clean│…  prov …  lifecycle …     │
│                       │ │ (4 one-line marginals, ≤3 buckets)            [R10]       │
└───────────────────────┴───────────────────────────────────────────┴──────────────────────┘
R4 SELECTION DOCK — hidden (H=0 at rest)
```

**Vertical:** `R0 72 + gap 12 + max(R1 800, R2 800, R3 540) = 884 ≤ 900`.
**Horizontal:** `16 + R1 300 + 12 + R2 744 + 12 + R3 340 + 16 = 1440`.

## 3. Resting screen — 390×844 (mobile, stacked)

```text
 12px pad            366 content            12px pad
┌──────────────────────────────────────────────────┐  y=0
│ R0 SYSTEM+TRUST (H=72)                     [J1]  │
│  ON-G1 (2 rows × 2 cells)                         │
│  ON-G6 (1 row ×3, 1 row ×4)                       │
├──────────────────────────────────────────────────┤  y=72
│ R1 ATTENTION (H=144) visible rows: 3       [J2,J3]│
│  R1a decision (38px) [R5,R7,R10]                  │
│  R1b risk     (38px) [R1,R5,R8,R9]                │
│  R1c next     (38px)                              │
├──────────────────────────────────────────────────┤  y=224
│ R2 RUN LEDGER (H=284)                      [J1,J2]│
│  counts (32px): run 3 · queued 7 · fail 1 · live 4│
│  3 rows × 80px: identity/target/model/attempt     │
│                 command/phase/state/live          │
│                 claim/proof/src/cost/elig/receipt │
├──────────────────────────────────────────────────┤  y=516
│ R3a COST (ON-G4, H=92) 3+2 grid            [R7]   │
├──────────────────────────────────────────────────┤  y=608
│ R3b HEALTH DETAIL (H=68)                   [R9]   │
├──────────────────────────────────────────────────┤  y=676
│ R3c COMPOSITION (ON-G7, H=60) 4 lines      [R10]  │
└──────────────────────────────────────────────────┘  y=760  (headroom 84)
```

**Vertical:** `72 + 144 + 284 + 92 + 68 + 60 + 5×8 = 760 ≤ 844`. No mobile omission: the same seven
answers appear stacked.

## 4. Element list — resting screen

Dimensions are the maxima from `ia.md` §3.2. `[R…]`/`[J…]` are the rule/job labels.

| # | element (selector) | dims @1440 | dims @390 | content | serves |
|---|--------------------|-----------:|----------:|---------|--------|
| E1 | `[data-region="R0"]` | 1440×72 | 366×72 | scope + `ON-G1` + `ON-G6` | J1; [R1,R7] trust/budget freshness |
| E2 | `[data-answer="ON-G1"]` | 2×24 rows | 2 rows | browser/control/workers/projections state+age | J1 |
| E3 | `[data-answer="ON-G6"]` | 1×24 | 2 rows | epoch, worst age, stale/partial/unknown | J1 |
| E4 | `[data-region="R1"]` | 300×800 | 366×144 | attention inbox, 3 reserved rows | J1,J2,J3 |
| E5 | `R1a [data-attention-class="decision"]` | 300×56 | 366×38 | `ON-G5`: target/kind/epoch/authority/eligibility | J3; [R5,R7,R10] |
| E6 | `R1b [data-attention-class="risk"]` | 300×56 | 366×38 | `ON-G3`: failure/stall/money-risk item | J2; [R1,R5,R8,R9] |
| E7 | `R1c [data-attention-class="next"]` | 300×56 | 366×38 | next decision/risk/advisory/process gap | J7; [R10] |
| E8 | `[data-region="R2"]` | 744×800 | 366×284 | `ON-G2` counts + run sample | J1,J2 |
| E9 | counts line | 744×40 | 366×32 | running/queued/failed/live (exact) | J1 |
| E10 | `.run-row[data-run-id]` | 744×88 | 366×80 | identity, target, model×attempt, phase n/t, state, live, claim/proof, commit, cost-provenance, eligibility, receipt | J2,J5; [R1,R5,R7,R8,R9,R10] |
| E11 | `[data-region="R3a"]` | 340×220 | 366×92 | `ON-G4` five values + exception | J5; [R3,R7,R10] |
| E12 | `[data-region="R3b"]` | 340×180 | 366×68 | worker + projection health detail | J2; [R9] |
| E13 | `[data-region="R3c"]` | 340×140 | 366×60 | `ON-G7` model/condition/provider/lifecycle marginals | J1; [R10] |
| E14 | `[data-region="R4"]` | 0 (hidden) | 0 | selection dock | J2–J11 |

## 5. Drill-down `R4` — desktop bottom dock (≈320px)

Opens on a run/attention-item selection; `R0/R1/R2/R3` stay in their columns above (reduced-height
summaries). Internal budgets never charge the resting sum.

```text
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ R0 summary (compressed) · R1 summary · R2 summary · R3 summaries                          │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│ R4 SELECTION DOCK  (H≈320)                                                                │
│ ┌ R4a ADDRESS & IDENTITY (H=48) ───────────────────────────────────────[J2,J3,J9]─────┐   │
│ │ run r-8821 · session s-77 · wt ctrl-room · cmd pytest · ds/DS-Pro · attempt 2/3 ·   │   │
│ │ state awaiting_approval · epoch 8421 · routing inputs [R1,R5,R7]                     │   │
│ └──────────────────────────────────────────────────────────────────────────────────────┘  │
│ ┌ R4b WORKER EVENT + ACTION (H=160) ─[J4,J6]──┐ ┌ R4c EVIDENCE LADDER (H=160)[J4,J7]─┐   │
│ │ ▶ replay_complete  · follow ▮ pause ▯       │ │ identity → lifecycle → narration →  │   │
│ │ [step_start] 12:04:03  pytest              │ │ MEASURED facts → independent test → │   │
│ │ [reasoning]  ...                            │ │ change/commit → cost provenance →   │   │
│ │ [tool_use]   ...                            │ │ decision → registry record          │   │
│ │ ACTIONS: [attach][detach][copy][steer]      │ │ [data-attempt-boundary] × n         │   │
│ │          [interrupt][escalate]  [R5,R8,R9]  │ │        [R1,R5,R8,R10]               │   │
│ └─────────────────────────────────────────────┘ └─────────────────────────────────────┘   │
│ ┌ R4d STEP TIMINGS (H=96) ─────────────────────────────────────────────[J4][R2,R9]────┐   │
│ │ queue_wait unknown · service_time unknown · first_token 0.8s · duration 42s ·       │   │
│ │ retries 1 · tokens.answer 340 · tokens.explanation 1.2k · cost $0.021 · exit 0 ·     │   │
│ │ verification measured              (each: [data-state=measured|unknown] + source+age) │   │
│ └──────────────────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

Dock budgets (`ia.md` §3.4): `R4a 48 + max(R4b 160, R4c 160) + R4d 96 ≈ 304 ≤ 320`. On mobile `R4`
is a full-height inspector (R4a 64 / R4b 360 / R4c 280 / R4d 140) with an explicit Back; `R0` and
`R1` stay at top.

## 6. Drill-down `R4` — 390×844 (mobile inspector)

```text
┌──────────────────────────────────────┐
│ R0 (72) · R1 (144, top)              │  ← remain visible
├──────────────────────────────────────┤
│ ← Back   run r-8821                  │
│ R4a ADDRESS (H=64)              [J3] │
├──────────────────────────────────────┤
│ R4b WORKER EVENT + ACTION (H=360)    │
│  event feed (bounded, follow/pause)  │
│  action chips wrap                    │
│                              [J4,J6] │
├──────────────────────────────────────┤
│ R4c EVIDENCE LADDER (H=280)          │
│                              [J4,J7] │
├──────────────────────────────────────┤
│ R4d STEP TIMINGS (H=140)             │
│                              [J4][R2,R9]
└──────────────────────────────────────┘
```

## 7. Lenses (deliberate drill-downs; never required at rest)

Each lens is a full-area panel opened from a named entry; it hydrates from the d3 projection in
parentheses. Rule tags are on the lens's answer elements.

| lens | entry (from) | purpose | rule tags | projection |
|------|--------------|---------|-----------|------------|
| `L-FLEET` | `R2` "full roster" | all runs, filters/search/density | [R5,R7,R8,R9] | P1 workflow_records |
| `L-ATTENTION` | `R1` overflow | all advisories/flags | [R1,R8] | supervisor flags |
| `L-MONEY` | `R3a` | spend history, leases, settlement, EPM scenario, story arc, batch scenario, human cost, T_max | [R3,R4,R6,R7,R10] | P7, P4 |
| `L-COMPOSITION` | `R3c` | model×condition×provider performance, arm comparison, BVI | [R1,R5,R10] | P6, P5, P3 |
| `L-HEALTH` | `R3b` | per-projector watermark detail | [R7] | projection_watermarks |
| `L-WORKFORCE` | `R4d` / `R2` | p50/p95 queue wait, service time, first-token, retry rate, tokens by model, Grit, narration penalty, escalation rate | [R1,R2,R5,R8,R9] | P3, P8, P9 |
| `L-REGISTRY` | `R4c` registry link | canonical lineage (supersedes/causes) | [R10] | registry |
| `L-SESSIONS` | `R2` object type | design + Claude sessions + search | [R8] | L-SESSIONS |
| `QUEUE` | `R2` action / `J8` | enqueue/clear/reinterleave, queue depth, batch | [R6,R9] | P10, P1 |
| `DOCS` | `R1c` process gap | docs-health decision/remediation | — | docs-health |
| `AUDIT` | `J7`/`J11` | recording coverage, decision ledger | [R3,R7,R10] | P11 |
| `SEARCH` | `⌘K` | typed global search/command | all | — |
| `SYSTEM` | help/topology | architecture/help link | all | — |
| `A11Y` | — | one polite live region | — | — |

Representative lens shell (all lenses share it):

```text
┌──────────────────────────────────────────────────────────────┐
│ ‹ Back   L-MONEY   [time range ▾] [model ▾] [export]         │
│  headline: spend $41.20 · burn $0.34/m · leases $1.05 [R7]   │
│ ┌ session arc (story) ──────────────────────┐ [R3]          │
│ │ S1 $0.16 ─ S2 $0.21 ─ S3 $0.26 ─ S4 $0.29 ─ S5 $0.34      │
│ │ snowball ×2.13  β 0.001 [P]  velocity 500 ln/s [C]        │
│ └───────────────────────────────────────────────────────────┘│
│ ┌ EPM scenario ─────────────────────────────┐ [R4]          │
│ │ baseline 1.6%/yr [X]  · aggressive 2.5%   T_max  667K [C] │
│ └───────────────────────────────────────────────────────────┘│
│ ┌ settlement / leases ──────────────────────┐ [R7]          │
│ │ reserved $1.05 · spent $0.42 · headroom … │                │
│ └───────────────────────────────────────────────────────────┘│
│ batch [R6]: measurable=false — no batch_mode marker [P]      │
└──────────────────────────────────────────────────────────────┘
```

## 8. Rule label legend (acceptance hook)

Every rule 1–10 appears as an element label above. The render gate asserts each rule string
appears in the committed wireframe labels (and, later, on the rendered element carrying it).

| rule | elements carrying its label |
|------|-----------------------------|
| `[R1]` Grit | E1 freshness, E6 risk, E10 row proof, R4c independent-verification rung, `L-COMPOSITION`/`L-WORKFORCE` |
| `[R2]` Explanation Tax | R4d `tokens.answer`/`tokens.explanation`, `L-WORKFORCE` narration penalty |
| `[R3]` Snowball | E11 `R3a`, `L-MONEY` session arc |
| `[R4]` EPM Horizon | `L-MONEY` EPM scenario |
| `[R5]` First-Pass | E5 decision, E6 risk, E10 row, R4a/R4b/R4c, `L-COMPOSITION` WOC |
| `[R6]` Batch Discount | `L-MONEY` batch panel, `QUEUE` |
| `[R7]` Budget Ceiling | E3 trust, E5 decision, E11 `R3a`, `L-MONEY`/`L-HEALTH` |
| `[R8]` Cascade | E6 risk, E10 row escalation, R4b `escalate`, R4c attempt boundary, `L-WORKFORCE` |
| `[R9]` SLA Buffer | E6 risk, E10 row, E12 health, R4b actions, R4d timings, `QUEUE`/`L-WORKFORCE` |
| `[R10]` Outcome Multiplier | E5 decision, E7 next, E10 row, E11 `R3a`, E13 `R3c`, `L-COMPOSITION`, `AUDIT` |

## 9. Acceptance

- Both resting viewports fit without scroll (`884 ≤ 900`, `760 ≤ 844`) and the horizontal sums are
  exact (`1440`, `390`).
- Every rule `[R1]..[R10]` appears as an element label (§8); every job `J1..J11` appears in a
  region/lens label.
- Every `R4` sub-region has a budget and is `0` at rest; a missing timing renders `[data-state=
  "unknown"]`, never `0`.
- Element identifiers match `ia.md` §10.2's selector map so the existing render gate can assert
  this wireframe without a second vocabulary.
