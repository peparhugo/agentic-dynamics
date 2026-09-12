---
status: accepted
---

# Control Room rules — the frozen mandate (d0 extract)

**Status:** frozen extract. This document transcribes the published **ten rules** and the shared
**engine chain** verbatim from the records pinned by `d0_pin_sources` (see
`docs/research/control_room_rules_sources.md`). It is the evidence base every later design phase
(`d1`–`d5`) must trace to. A design element that does not trace to a rule or an operator job, a
record the backend does not emit, and a missing measured/computed input are all **gaps to name**,
never assumptions to fill.

Citation keys (short handle → frozen record `sha256`):

| key | record | uri |
|-----|--------|-----|
| `[F]` | `experiments/control_room_rules/sources/30370e379a32ffcd.json` | `https://ai-finops-rulebook.web.app/framework.html` |
| `[E]` | `experiments/control_room_rules/sources/aa676d570db807c4.json` | `https://ai-finops-rulebook.web.app/evidence.html` |
| `[METH]` | `experiments/control_room_rules/sources/3bc3039b19ea19bc.json` | `https://ai-finops-rulebook.web.app/methodology.html` |
| `[IDX]` | `experiments/control_room_rules/sources/805d756a5f891ff0.json` | `https://ai-finops-rulebook.web.app/index.html` |

Full pinned-record hashes are listed in the sources doc; every `sha256` below is a prefix-unique
tag resolution of the pin table entry named by the key.

## The engine chain (verbatim)

The mandate's engine is the load-bearing rule of this repo — instrument → derive → write policy
→ grid → campaign. The published form: [`[F]`]

> **01 / DECLARE Cell** — Workflow, factor assignment, instrumentation, budget, and deadline.
> **02 / ORDER Compile** — Validate dependencies and produce the executable DAG.
> **03 / CONTROL Jobs** — Materialize work with a policy arm and operating limits.
> **04 / EXECUTE Attempts** — Model calls, tools, retries, timing, tokens, and outcomes.
> **05 / RECORD Ledger** — Append-only events shared by operations and experiments.
> **OBSERVE / MEASUREMENT** — Measurement rules turn ledger fields into named information:
> first-pass quality, cost, grit, uncertainty, and value.
> **CONTROL / POLICY** — Control rules consume available information to route, retry, escalate,
> budget, or halt work inside the running workflow.
> **LEARN / CAMPAIGN** — When G > 1, compare policy arms, change one factor, and emit the next
> grid. The winning arm is already executable.

The chain, in the task's canonical spelling — each arrow is one published stage [`[F]`]:

```
cell -> compile -> jobs -> attempts -> ledger -> measurement -> policy -> compare -> adapt
```

The published four-step form of the same loop [`[F]`]:

1. **SELECT OR VARY** — Fixed factors produce one cell. Varied factors produce G cells without
   changing the workflow executor.
2. **EXECUTE AND RECORD** — Every cell becomes jobs and attempts that emit append-only events to
   the same ledger.
3. **MEASURE AND CONTROL** — Measurement rules produce information. Admissible control rules
   consume it inside the running workflow.
4. **COMPARE AND ADAPT** — Grids compare arms. Campaigns alter one factor and run the next
   evidence-acquisition pass.

Operating modes over the same engine [`[F]`]: a **fixed assignment** produces one cell
(`OPERATE`); a **factor cross-product** produces G cells (`EXPERIMENT`), and only the grid
branches to compare and adapt. Breadth is `G × N × M` — grid breadth × workflow depth ×
measurement breadth.

Hard ordering (the repo's load-bearing rule, and the published gate on the `derive → write-policy`
arrow) [`[F]`]: **a control rule whose requirements are not measured cannot be written.** The
mandate's own receipt separates the evidence classes [`[F]`]:

> **What is measured [M]** Observed cost, outcome, narration, and cache fields from the corpus
> (1,067 story sessions, 7 models). **What is computed [C]** First-pass quality, Grit, cost per
> accepted outcome, WOC ratio — derived from the measured fields. **What is modeled [P]/[X]** β
> context inflation, EPM energy horizon, batch/cascade/SLA extensions — calibrated inputs and
> assumptions, not measured outcomes. **Limitation** A rule's premise being measured does not
> make the rule measured; rules not run as policy arms remain proposals.

## Rule status legend

Each rule carries a **published status** and an **evidence class**. The two answer different
questions — the premise may be measured while the rule itself is unrun [`[F]`]:

| published status | meaning |
|------------------|---------|
| **[M] instrumented** | its inputs and premise are measured |
| **[C] proposed** | modeled or designed, but not run as an arm |
| **decided** | a verdict binds it (reserved; see the `cap_2b` decision on `[E]`) |

The mandate states the distinction explicitly: *"A rule's premise being measured does not make
the rule measured — a policy becomes decided only when it is run as an arm and compared."* [`[F]`]
The `cap_2b` verdict on the Evidence page is the only decided artifact, and it is scoped:
*"the verdict authorizes design review only — it does not arm a control policy."* [`[E]`]

## The ten rules (verbatim cards)

Ordered by rule number (the published page groups 1/2/5 as instrumented and 3/4/6/7/8/9/10 as
proposed; the number order below keeps the canonical 1→10 sequence). Each card's `Inputs`,
`Evidence class`, `Limitation`, and `Next test` are quoted from the *Policy / Rule Status*
section; the description is quoted from the *Policy / Proposed Control Rules* section. [`[F]`]

---

### Rule 1 — Grit (Ground-Truth Integrity)
- **Status:** `[M] instrumented` · **Evidence class:** `[M]/[C]`
- **Inputs:** test-executed success under 10 perturbation operators ([M]).
- **Limitation:** single-session + story corpus; not a universal trait.
- **Next test:** strength-grid live run.
- **Lever:** C₀

> **Default to models that keep correctness under degraded input.** Default to models that
> maintain correctness when given degraded, contradictory, or incomplete instructions. If a model
> flails under perturbation — producing zero code despite high token output — it has low Grit.
> Don't use it for unsupervised work. The 10 perturbation operators measure Grit across three
> perturbation classes: specification corruption, objective mutation, and process perturbation.

*Source:* [`[F]`]. *Corroboration:* the Evidence page defines the measured quantity
`G(s) = P(test_executed_success | perturbation_strength = s)` — *"the verdict is the independent
test runner's, never the agent's self-report, and a cell missing either field is excluded rather
than imputed."* [`[E]`]

---

### Rule 2 — Explanation Tax (ε)
- **Status:** `[M] instrumented` · **Evidence class:** `[M]/[C]`
- **Inputs:** measured flail + narration overhead per model ([M]).
- **Limitation:** descriptive; not matched-task causal evidence.
- **Next test:** re-weight by accepted outcome.
- **Lever:** ε

> **Measure what resilience costs — flail rate and narration penalty.** Rule 1 selects models that
> CAN code under degraded input. Rule 2 measures what their resilience COSTS — the flail rate
> (sessions producing zero code) and narration penalty (overhead on successful sessions).
> Measured: Claude 11% flail, 8% penalty. DeepSeek 8% flail, 0.0% penalty. For auditable work,
> the tax is insurance. For routine tasks, it's waste.

*Source:* [`[F]`].

---

### Rule 3 — Snowball Rule (N²)
- **Status:** `[C] proposed` · **Evidence class:** `[C]/[P]`
- **Inputs:** β (calibrated, [P]), v ([C]).
- **Limitation:** N² is a modeled extension beyond the measured arc.
- **Next test:** canonical lab output for the arc.
- **Lever:** β, v · **Formula:** `C(N,v) = C₀ × EPM(N) × [N + β·v·N(N−1)/2]`

> **Codebase growth compounds quadratically; β is calibrated, not measured.** Your codebase grows
> with every session. Each new line of generated code increases the context window for every
> future session. This isn't additive – it's quadratic. The more you build, the more each
> subsequent build costs. Measured: story cost roughly doubles across the five-session arc
> ($0.16 → $0.34, a 2.13× Snowball). The β term compounds per-session — model the curve before
> you commit to an architecture. This is a one-way door.

*Source:* [`[F]`].

---

### Rule 4 — EPM Horizon
- **Status:** `[C] proposed` · **Evidence class:** `[X]/[P]`
- **Inputs:** IEA projections ([X]), rate r ([P]).
- **Limitation:** external scenario, not a corpus outcome.
- **Next test:** energy-measured campaign.
- **Lever:** EPM(t) · **Formula:** `EPM(t) = 1.00 + r(t−2024)`

> **Energy prices inflate compute; EPM(t) is externally calibrated.** Energy costs are the
> inflation rate of AI compute. Local energy markets – not global averages – determine your
> long-term prices. A team in Texas (ERCOT grid) faces different EPM growth than one in Frankfurt
> (ENTSO-E) or Singapore. Find the year your geographic energy costs flip your model selection.
> Hedge before that point.

*Source:* [`[F]`]. IEA baseline 1.6%/yr, aggressive 2.5% scenario [`[F]`].

---

### Rule 5 — First-Pass Rule
- **Status:** `[M] instrumented` · **Evidence class:** `[C]`
- **Inputs:** attempt number, acceptance, independent evaluator ([M]).
- **Limitation:** needs per-task/per-model coverage.
- **Next test:** coverage-corrected routing.
- **Lever:** P, retry rate

> **Price the accepted outcome, not the prompt; derive first-pass from the attempt ledger.** A
> cheaper model can lose its price advantage through failed verification, retries, and escalation.
> Derive first-pass quality from attempt number, acceptance, and an independent evaluator; then
> track it by task type, model, policy, and time window. Do not substitute a narrated report
> failure rate for an attempt-ledger measurement.

*Source:* [`[F]`]. The published identity: `WOC = 1/(1+r)` [`[F]`].

---

### Rule 6 — Batch Discount
- **Status:** `[C] proposed` · **Evidence class:** `[X]/[P]`
- **Inputs:** provider batch pricing ([X]), queue model ([P]).
- **Limitation:** modeled; batch experiments not yet executed.
- **Next test:** batch-vs-on-demand arm.
- **Lever:** b, Q

> **Deferred batch work is cheaper (50%) with a 72-hour horizon.** Batch processing is 50% cheaper
> but has a 72-hour horizon. If your task doesn't need a response in <4 hours, run in batch.
> Monitor queue depth.

*Source:* [`[F]`]. Discount factor `D(b) = 1 − b×0.5` [`[F]`].

---

### Rule 7 — Budget Ceiling
- **Status:** `[C] proposed` · **Evidence class:** `[C]/[P]`
- **Inputs:** measured retry rate r=0.115 ([M]), WFM theory ([P]).
- **Limitation:** capacity formula, not a verified SLA.
- **Next test:** budget-policy arm.
- **Lever:** W (jobs/day) · **Formula:** `T max = Budget / C job`; `Max jobs/day = Budget / (Cost per job × (1 + retry_rate))`

> **Throughput = Budget / (cost per job × (1 + retry)).** Your maximum throughput is set by your
> budget, not your infrastructure. Max jobs/day = Budget / (Cost per job × (1 + retry_rate)).
> Double your budget, double your capacity – zero hiring required.

*Source:* [`[F]`].

---

### Rule 8 — Cascade Rule
- **Status:** `[C] proposed` · **Evidence class:** `[X]/[P]`
- **Inputs:** price ratios ([X]), escalation design ([P]).
- **Limitation:** cascade experiments not yet executed.
- **Next test:** escalation arm.
- **Lever:** Eₔ (28.2× price ratio: DS → GPT-5.6)

> **Failures auto-escalate through model tiers; design for <1% human escalation.** In autonomous
> workloads, failures auto-escalate through model tiers: Flash → Sonnet → Opus → Human. A 1%
> escalation to human review can double your total cost. Design for <1% escalation.

*Source:* [`[F]`]. Measured fix multipliers on the Evidence page: "`[M]` costs ($0.008949
baseline; $0.102619 Sol; $0.111982 Sonnet) and `[C]` ratios (E_x = 11.4671; 12.513…)" [`[E]`].

---

### Rule 9 — SLA Buffer
- **Status:** `[C] proposed` · **Evidence class:** `[P]`
- **Inputs:** queue theory ([P]), retry buffer ([P]).
- **Limitation:** modeled from WFM, not measured.
- **Next test:** live queue-depth validation.
- **Lever:** Slack Buffer · **Formula:** `Actual batch completion time = (Queue_length × Avg_job_time) + (Retry_buffer × retry_rate)`

> **Completion time = queue × job time + retry buffer; never batch under 2× queue depth.** Actual
> batch completion time = (Queue_length × Avg_job_time) + (Retry_buffer × retry_rate). Never batch
> jobs with an SLA less than 2× your observed queue depth. Always have an on-demand fallback.

*Source:* [`[F]`].

---

### Rule 10 — Outcome Multiplier
- **Status:** `[C] proposed` · **Evidence class:** `[C]/[P]`
- **Inputs:** accepted outcomes and total cost ([M]), BVI definition ([P]).
- **Limitation:** business-value framing, not a verified outcome metric.
- **Next test:** value-weighted arm comparison.
- **Lever:** BVI · **Formula:** `BVI = WOC/(C job + H/W)`; `C total = C augmented + C autonomous + H`

> **Maximize outcomes per dollar (BVI = outcomes / total cost).** The goal isn't to minimize cost
> – it's to maximize outcomes per dollar. Business Value Index = Total Successful Outcomes / Total
> AI + Human Cost. A 2× BVI means twice the work for the same cost. A 10× BVI unlocks new business
> models.

*Source:* [`[F]`].

---

## Rule status summary

Extracted from the *Policy / Rule Status* cards [`[F]`]:

| # | rule | published status | evidence class | inputs measured? | limitation (one line) | next test |
|---|------|------------------|----------------|------------------|-----------------------|-----------|
| 1 | Grit (Ground-Truth Integrity) | `[M]` instrumented | `[M]/[C]` | yes ([M]) | single-session + story corpus; not a universal trait | strength-grid live run |
| 2 | Explanation Tax (ε) | `[M]` instrumented | `[M]/[C]` | yes ([M]) | descriptive; not matched-task causal evidence | re-weight by accepted outcome |
| 3 | Snowball Rule (N²) | `[C]` proposed | `[C]/[P]` | premise modeled | N² is a modeled extension beyond the measured arc | canonical lab output for the arc |
| 4 | EPM Horizon | `[C]` proposed | `[X]/[P]` | modeled | external scenario, not a corpus outcome | energy-measured campaign |
| 5 | First-Pass Rule | `[M]` instrumented | `[C]` | yes ([M]) | needs per-task/per-model coverage | coverage-corrected routing |
| 6 | Batch Discount | `[C]` proposed | `[X]/[P]` | modeled | modeled; batch experiments not yet executed | batch-vs-on-demand arm |
| 7 | Budget Ceiling | `[C]` proposed | `[C]/[P]` | rule modeled | capacity formula, not a verified SLA | budget-policy arm |
| 8 | Cascade Rule | `[C]` proposed | `[X]/[P]` | modeled | cascade experiments not yet executed | escalation arm |
| 9 | SLA Buffer | `[C]` proposed | `[P]` | modeled | modeled from WFM, not measured | live queue-depth validation |
| 10 | Outcome Multiplier | `[C]` proposed | `[C]/[P]` | outcomes [M], framing [P] | business-value framing, not a verified outcome metric | value-weighted arm comparison |

**Counts:** 3 instrumented `[M]` (rules 1, 2, 5); 7 proposed `[C]` (rules 3, 4, 6, 7, 8, 9, 10);
0 decided in the published rule cards. The only decided artifact in the pinned corpus is the
`cap_2b` randomized non-inferiority verdict, scoped to design review only [`[E]`].

## Provenance of the measured fields (why classes differ)

- **Corpus:** `1,067` story sessions, `7` models, `215` multi-session stories, total measured
  cost `$309.17` [`[IDX]`]; the older perturbation instrument is `249` historical sessions /
  `227` historical worktrees across `8` models [`[METH]`]. The two corpora are *"never merged"*
  [`[METH]`].
- **Provenance tagging:** *"Every measurement is provenance-tagged; a signal that was not
  captured is published as null with its coverage, never a fabricated zero."* [`[IDX]`]. Method
  outputs are tagged `[M]/[C]/[H]/[X]` in the game reports [`[METH]`].
- **What is still open:** *"Still open: when to route, retry, escalate, or stop"* [`[E]`] — i.e.
  the control rules (the `policy` stage of the engine chain) remain proposals.

## Notes for downstream phases

- The chain above (`cell -> compile -> jobs -> attempts -> ledger -> measurement -> policy ->
  compare -> adapt`) is the shared engine both workforces run on; every Control Room surface must
  serve an operator decision somewhere on this chain (hard rule 1).
- Evidence classes are load-bearing: a room element backed only by `[C]`/`[P]`/`[X]` fields must
  say so, and a field the corpus does not measure is a **gap** (hard rules 2 and 3).
- These records are frozen — `d1`–`d5` cite this file and the pinned `sources/*.json`, never the
  live web.
