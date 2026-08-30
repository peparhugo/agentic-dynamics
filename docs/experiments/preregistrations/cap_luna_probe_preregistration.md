---
status: accepted
---

# cap_luna_probe — pre-registration: is Luna a good choice for the machine's story-cell volume?

**Status: accepted · PRE-REGISTERED — committed BEFORE any cell runs.**
**Spec SHA256 (pinned):** `e7220621d318a86d8be681a55fab3220a3a5e0f14c7f442c7b9ab1a1b9af1f54`
— `workflows/repository/cap_luna_probe.yaml`, pinned on its commit
`1395a4e4e7abfd697a8c9b0488a865d79651db7d`. This is the ONLY post-hoc edit to this document.
**Campaign:** `cap_luna_probe` (the spec `workflows/repository/cap_luna_probe.yaml`). **Motivation
(operator-directed, 2026-08-28):** the ChatGPT subscription is OAuth-wired into opencode, and
Luna is the pricing-page-designated high-volume workhorse ("routing, classification, support,
background automation, focused coding tasks" — the machine's story-cell shape) with a
subscription window 10–25× Sol's. The machine's own corpus measured Luna at 100% (34 cells,
$0.094/story) — but the corpus is ceiling-heavy and **has zero late_degrade runs anywhere**, so
Luna's behavior under the full stress envelope is unmeasured, and the subscription counts
MESSAGES (per-cell consumption unknown). The "re-measure before policy consumes it" discipline
(the cross-models caveat's lesson) applies. This probe measures both unknowns and reports
whether Luna-first routing is justified and whether the subscription window can carry grid
volume.

## 1. The two unknowns being measured

1. **The stress envelope:** Luna's success under `late_degrade` — the condition NO corpus run
   has ever measured — with the fixed runner (the Claude-side artifacts are excluded by the
   caveat; the openai family's earlier runs stand, but late_degrade is open for every model).
2. **The window math:** per-cell MESSAGE consumption (session turns — the subscription's
   scarce unit, readable from the cell transcripts) × the grid volume vs the plan tiers'
   Luna windows (Plus 250–2,000 / Pro 5x 1,250–10,000 / Pro 20x 5,000–40,000 per 5h).

## 2. The grid — 8 cells (6 Luna + 2 Sol)

| cell_id | model | story | condition | purpose |
|---|---|---|---|---|
| `luna_probe_luna_task_manager_api_clean_r1` | gpt-5.6-luna | task_manager_api | clean | the baseline re-check under the fixed runner |
| `luna_probe_luna_static_site_gen_clean_r1` | gpt-5.6-luna | static_site_gen | clean | same |
| `luna_probe_luna_notification_service_clean_r1` | gpt-5.6-luna | notification_service | clean | same |
| `luna_probe_luna_task_manager_api_late_degrade_r1` | gpt-5.6-luna | task_manager_api | **late_degrade** | the unmeasured condition — THE probe |
| `luna_probe_luna_static_site_gen_late_degrade_r1` | gpt-5.6-luna | static_site_gen | late_degrade | the unmeasured condition, story 2 |
| `luna_probe_luna_notification_service_late_degrade_r1` | gpt-5.6-luna | notification_service | late_degrade | the unmeasured condition, story 3 |
| `luna_probe_sol_task_manager_api_late_degrade_r1` | gpt-5.6-sol | task_manager_api | late_degrade | the matched Sol comparison on the stress axis |
| `luna_probe_sol_static_site_gen_late_degrade_r1` | gpt-5.6-sol | static_site_gen | late_degrade | the matched Sol comparison, story 2 |

Backend: opencode (the OAuth subscription path — the cells bill to the ChatGPT window, not the
API key). 4-wide concurrency (the window is the shared envelope — the 5-hour rolling window is
a per-plan limit, and the probe is small enough to fit any tier). **E1** =
`luna_probe_luna_task_manager_api_late_degrade_r1`. No randomization needed (8 fully-specified
cells — the assignment table above IS the canonical record).

## 3. The measurements + decision rule (pre-registered)

**Per cell (recorded in the cell record by the run phase, BEFORE scoring):**
- `test_executed_success` (independent runtime.test_runner on the final commit)
- `all_successful` (the 5-session outcome)
- **`messages` — the per-cell session-turn count from the transcripts** (the session.jsonl
  step events — the subscription's scarce unit; the run phase counts and records it; a cell
  without the count is flagged, never imputed)
- cost/tokens/duration (the ledger, as always)

**The decision rule (SUPPORT ⟺ all of):**
1. **Stress parity:** Luna's late_degrade success ≥ Sol's late_degrade success on the matched
   cells (task_manager_api + static_site_gen), OR both at ceiling (2/2 vs 2/2). A Luna
   late-degrade failure that Sol does not share → the stress envelope refutes Luna-first.
2. **Window fit:** `per-cell messages (median) × 30` (a full grid's volume) fits the
   operator's plan tier's Luna window lower bound (250 / 1,250 / 5,000). The fit is reported
   for all three tiers with the measured number; SUPPORT requires fit on the operator's tier.
3. **Baseline intact:** the clean cells' success matches the corpus expectation (100% — the
   fixed-runner re-check; a clean-cell failure is a runner regression, flagged).

**What is NOT claimed:** the probe is 8 cells — it measures the unmeasured axis + the window
math, not a full reliability curve. A SUPPORT verdict authorizes Luna-first routing for the
story-cell volume + a routing-recommendation update; nothing activates without it.

## 4. Analysis + authorization

p0 (pin spec) → p1 (run the 8 cells, 4-wide, RECORDING the per-cell message counts from the
transcripts) → p2 (score: per-cell table, the stress-parity leg, the window-fit leg, the
baseline leg + the grid-fit math for all three tiers) → p3 (verdict doc
`docs/experiments/results/cap_luna_probe.md`) → p4 (adversarial: the message counts re-derived
from the transcripts, the success determinations independent, the matched-cell pairing
checked). Budget: 8 cells on the subscription window (small enough for any tier) — the $30
stop pattern holds as the ceiling. The openai envelope is this probe's until its verdict; the
anthropic re-measurement drain and the deepseek 2f campaign continue in parallel (the
parallel-vehicles rule).

## Guard

The per-cell message count is a MEASURED field (transcript-derived), never estimated from
tokens. The grid-fit math cites the pricing-page window table (Plus 250–2,000 / Pro 5x
1,250–10,000 / Pro 20x 5,000–40,000 Luna per 5h) and the measured median. The assignment
table is fixed here; the spec SHA256 is appended on the spec commit; no cell runs before this
document is on main.

**LOG:** the operator's question operationalized as two measured unknowns (the late_degrade
stress axis — zero corpus coverage — and the per-cell message window math — the subscription's
scarce unit); the 8-cell grid (6 Luna incl. 3 late_degrade + 2 matched Sol late_degrade) with
the message-count recording requirement; the three-leg decision rule (stress parity / window
fit × 30 cells / baseline intact) with the tier table cited; the analysis plan p0–p4; the
authorization boundary (routing recommendation update only on SUPPORT). **PASS — committing
before any cell runs.**
