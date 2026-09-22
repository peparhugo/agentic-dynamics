# Posterior — the confidence-cascade study, Phase A (retrospective + pre-registration)

Author: `confidence_cascade_study` phase `posterior` (spec version `0.1`).
This document diffs **what the retrospective could establish** against **what the plan/world
model assumed**. It is written *after* the two Phase-A artifacts
(`docs/reviews/confidence_cascade_retrospective.md`,
`docs/designs/proposed/confidence_cascade_study.md`) and *after* an independent re-walk of the
live stores. Every number below names whether it is quoted from the machine artifact or
recomputed here.

**Feasibility verdict (restated, [M]).** **NULL FEASIBILITY — the grid is PAUSED.** The
measured `confidence` signal carries no ordinal information above `0.0` (AUC excluding the
`0.0` cell = **0.488**; Spearman ρ = **−0.009**), the one separating cell is partly
definitional (14/14 `confidence == 0.0` attempts are `failed`), the independent outcome
(`test_executed_success`) exists on **4 of 394** ledger attempts, and there is **zero**
escalation history (0/0/0/0 across 388 ledgers). All six plan falsifiers (F1–F6) fired. The
pre-registration is fully specified but gated on the instrumentation set I1–I4.

**Snapshot at posterior time** [M]. `sha256sum`/`wc -l`/`ls | wc -l`/`find | wc -l`:

| field | value |
|---|---|
| registry path | `/app/experiments/results/registry_index.jsonl` |
| **registry sha256** | `6761c52cb23963baeca8ff784ccce3dd92d55dd65ec06e2fe864a85be0311d37` |
| registry lines | **55,081** |
| kb artifacts | **24,267** |
| run ledgers | **388** |

> The *retrospective's* artifact pinned `7eaf2252…` / 55,079 / 24,263; the *prior* phase pinned
> `cf64fc97…` / 55,077 / 24,261. `7eaf2252…` **no longer exists on disk**. See V5.

---

## Violations

An assumption the plan or world model made that the executed retrospective (or this phase's
independent recompute) **refuted or corrected**.

### V1 — The prior inventory's point-mass figure was wrong (65.5% → 64.5%) [M]

`notes/world_model.md` §4 states "**881 / 1,345 attempts (65.5%)** are exactly `1.0`", and its
calibration table is binned differently from the retrospective's. The execute artifact and this
phase's independent recompute both give **868 / 1,345 = 64.5%** (14 exactly `0.0`, 226 distinct
values). The drift of +4 registry rows does **not** touch the attempt layer — the recompute at
the *current* sha (`6761c52c…`) reproduces 2,505 distinct attempts / 1,345 paired / 868 exact-1.0
exactly. The prior figure is a binning/arithmetic error, **not** drift. Disposition: the design
and retrospective correctly use `868` / `64.5%`; the world-model number is superseded.

```bash
# independent recompute (current registry) — reproduces the execute artifact, not the prior inventory
cd /app && python3 - <<'PY'
import json, collections, os
by=collections.defaultdict(dict)
for line in open('experiments/results/registry_index.jsonl'):
    if not line.strip(): continue
    r=json.loads(line)
    if r.get('source_type')!='fact' or r.get('lifecycle_state')!='current': continue
    uri=str(r.get('source_uri') or '')
    if not uri.startswith('fact://attempt/'): continue
    k,p=uri[len('fact://attempt/'):].rsplit('/',1); by[k][p]=r['knowledge_id']
vals=[]
for k,v in by.items():
    if 'attempt_confidence' not in v: continue
    a=json.load(open(f"experiments/results/kb/{v['attempt_confidence']}.json"))
    vals.append(float(json.loads(a['text'])['value']))
c=collections.Counter(vals)
print(len(by), len(vals), c.get(1.0), c.get(0.0), len(c))   # 2505 1345 868 14 226
PY
```

### V2 — "`model_cascade` has no implementation and no call site" is false [M]

`notes/world_model.md` §5 asserts no implementation. The retrospective corrected this: an
opt-in, **failure-triggered** ladder exists (`runtime/escalation.py`,
`EscalationPlan.from_params`, step 9 / G-27) and is wired at
`runtime/workflow_runner.py:164`; it is **default OFF**, **0** specs declare a ladder, and
**0 of 388** ledgers mention one — which is exactly why the corpus records zero escalations.
This violation is *constructive*: the design's narrowed arm (`cascade_error_gate`, §10) is the
existing ladder gated on a confidence score rather than on failure, so it is a real treatment,
not a replay.

### V3 — "`first_pass` / `accepted` are not retrospectively measurable" is half false [M]

`notes/world_model.md` gap 7 (and `plan.md` acceptance 6) says the preferred metrics are not
retrospectively measurable. True of the **fact layer**, false of the **run-ledger layer**.
Independent walk of the 388 ledgers:

| field | rows with a value (of 394 attempts) |
|---|---:|
| `first_pass` | **394** |
| `accepted` | **394** |
| `status` | **394** |
| `cost_usd` | **394** |
| `confidence` | 327 |
| `test_executed_success` | **4** |
| `perturbation_strength` | **0** |

So the grid's primary quality metrics **are** available — from the typed `AttemptRecord`s, not
from the `fact` layer. The design sources them correctly (§2, §4); the plan's "redefine onto the
measurable signal" worry is resolved by the ledger path.

```bash
cd /app && python3 - <<'PY'
import json, glob
n=att=conf=fp=acc=tes=ps=0
for f in glob.glob('experiments/results/workflows/**/*.json', recursive=True):
    try: d=json.load(open(f))
    except Exception: continue
    n+=1
    for a in d.get('attempts') or []:
        att+=1
        conf+=a.get('confidence') is not None
        fp  +=a.get('first_pass') is not None
        acc +=a.get('accepted') is not None
        tes +=a.get('test_executed_success') is not None
        ps  +=a.get('perturbation_strength') is not None
print(n, att, conf, fp, acc, tes, ps)   # 388 394 327 394 394 4 0
PY
```

### V4 — Phase A could NOT supply a treatment effect size (the central "could not establish") [M]

The plan's power section (Q6) assumed the retrospective would extract "the observed effect sizes
the pre-registration needs". It cannot, and the reason is structural: **the treatment has never
executed**. Independent re-walk confirms 0 `escalation_from` / 0 `escalation_to` /
0 `parent_attempt_id` / 0 retries with `attempt_number > 1`. On the would-escalate subset the
strong model was never run, so its cost and outcome are genuinely unknown. Phase A licenses only:
(a) the **baseline** rate, (b) the **trigger fraction** per θ, (c) the **per-attempt cost
distribution**. The grid must measure its own effect. The design says this plainly (§6, "the hard
limit"), so the refutation is absorbed rather than hidden — but it **kills any claim that Phase A
"powered" the grid in the usual sense**.

### V5 — The reproducibility contract is weaker than the plan assumed [M]

`plan.md` risk 2 says "pin and record the sha256; treat every count as of that sha." In practice
the live store moved **three times in two phases**: `cf64fc97…`/55,077 (prior) →
`7eaf2252…`/55,079 (execute) → `6761c52c…`/55,081 (posterior; kb 24,261 → 24,263 → 24,267). The
execute artifact's own pinned sha **is gone**, so the artifact is **not byte-reproducible from
its recorded command**. The saving grace: the attempt-layer aggregates are stable across all
three snapshots (recompute reproduces 1,345 / 868 / 14), so the **null verdict is robust even
though the fixture is not**. Update: Phase B must pin a **versioned snapshot copy**, not a
live-file hash (see UPDATES).

### V6 — The grid's cost-arbitrage premise is contradicted by Phase A's own costs [M]

The design pins `fast = deepseek/deepseek-v4-flash`, `strong = deepseek/deepseek-v4-pro` and
implicitly assumes the strong model costs more. The retrospective's `per_attempt` rows say
otherwise: **flash mean $0.1037 (n=423) > pro mean $0.0927 (n=477)** — the "strong" model is
*cheaper* per attempt. The design already flagged this as a caution and pre-registered **G-F4**
(no cost gap ⇒ close the cascade question), but the posterior elevates it to a **hard
pre-condition**: a probe must establish a real per-attempt cost gap for the pinned pair, or the
pair changes before submission. Otherwise the grid spends ~$5.7k to learn what the retrospective
already shows at n≈900.

```bash
cd /app && python3 - <<'PY'
import json, collections, statistics
d=json.load(open('experiments/results/confidence_cascade/retrospective.json'))
by=collections.defaultdict(list)
for r in d['per_attempt']:
    if r.get('cost_usd') is not None: by[r['model']].append(r['cost_usd'])
for m in ('deepseek/deepseek-v4-flash','deepseek/deepseek-v4-pro'):
    v=by[m]; print(m, len(v), round(statistics.mean(v),4), round(statistics.median(v),4))
# flash 423 0.1037 0.0377 ; pro 477 0.0927 0.0564
PY
```

---

## Unknowns

What the retrospective **could not** settle, and which gates a responsible Phase B.

| # | unknown | why it matters | smallest resolver |
|---|---|---|---|
| **U1** | Is the `1.0` point mass (64.5%) a property of the signal or of the **recorder**? `opencode.py:113` falls back to the tool-call success fraction, so a run with no failed tool calls reads `1.0`. | If it is the recorder, "uninformative above 0.0" may be an artifact, not a fact — and the study's headline is provisional. | I4: emit a variance-bearing score; re-check monotonicity. |
| **U2** | Root cause of the differential missingness (confidence present **60.2%** of `ok` vs **26.1%** of `failed`; RR **2.31**). | A trigger set drawn from the confidence-bearing subset is success-biased. | Producer-side trace of the emission path (I3). |
| **U3** | Why `test_executed_success` reaches **4/394** ledger rows and **165/24,263** kb artifacts when `runtime.test_runner` is the declared sole source of truth. | It is the grid's **primary endpoint**; if it cannot be populated, the grid measures completion — which Phase A showed cannot separate arms. | Producer bug-hunt vs conditional-emission decision (I1). |
| **U4** | Per-story cost and variance for the pinned pair on **story** attempts. | Sets the repetition count `R` and the Phase B budget; the fact-layer means are task-mixed. | A handful of full story-runs per arm (the probe the design §6 owes). |
| **U5** | Whether `pro` is genuinely **stronger** on these three stories (G-F1). | If not, cascading cannot help regardless of calibration. | The probe's `test_executed_success` split across the pair. |
| **U6** | Whether `perturbation_strength` can be recorded on the attempt row at all. Despite the domain context, it is **0/394** ledgers and **144/24,263** kb artifacts. | A strength-graded cascade is not instrumentable until it lands. | Producer-side field check. |
| **U7** | The drift cadence of the unversioned store. | Counts held across three snapshots in ~1 hour — an observation, not a guarantee. | Pin snapshots per phase (UPDATES). |

---

## UPDATES

Concrete changes to the plan, the pre-registration, and the next phase, forced by the
violations and unknowns above.

### 1. Feasibility verdict (unchanged from execute, confirmed here)

**NULL FEASIBILITY [M].** `confidence` is a fault flag at `0.0`, not a probability. The grid is
**PAUSED**. Per the spec's honesty rule this is a first-class finding, and it is the *right*
outcome: Phase A cost ~$0 and averted a ~$5.7k grid built on a non-signal.

### 2. The numbers that anchor the grid's power (the pre-registered inputs)

These are the **only** Phase-A numbers Phase B's power and stopping rules may use. The two key
recomputes (MDE table, per-model cost) were re-run here and match the design.

| anchor | value | source |
|---|---:|---|
| baseline `first_pass`, all 394 ledger attempts | **0.848** (334/394) | artifact Q2b [M] |
| baseline `accepted`, all 394 | **0.845** (333/394) | artifact Q2b [M] |
| completion baseline `phase_status == "ok"`, pooled | **0.958** (1,288/1,345) | artifact Q2 [M] |
| per-attempt cost, mean / median / p90 | **$0.886 / $0.076 / $1.885** | artifact Q6 [M] |
| trigger fraction θ = 0.3 / 0.5 / 0.7 (registry) | **1.34% / 2.01% / 8.40%** | artifact Q6 [C] |
| `P(ok)` spread over positive bins | **0.083**, non-monotone | artifact Q6 [C] |
| AUC / ρ excluding the `0.0` cell | **0.488 / −0.009** | artifact Q2 [C] |
| confidence present `ok` vs `failed` | **60.2% vs 26.1%** (RR **2.31**) | artifact Q2 [M] |
| MDE **+5 pt**, pairwise α=0.05 | **694 attempts / arm** | recomputed, matches design §6 |
| MDE **+5 pt**, family-wise α=0.05 across 5 comparisons | **1,033 attempts / arm** | recomputed, matches design §6 |
| `R` reaching ≥1,033/arm | **R ≈ 18** → **~1,296 story-runs / ~6,480 attempts** | design §6 |
| inference floor at the measured mean | **≈ $5,741** (before premium/rework/orchestration) | design §6 [C] |

```bash
python3 - <<'PY'   # reproduces the MDE table exactly
from scipy.stats import norm
import math
z_b=norm.ppf(0.80); p1=0.8477157360406091
for label,za in (("pairwise",norm.ppf(0.975)),("family-wise",norm.ppf(1-0.05/(2*5)))):
    for d in (0.02,0.03,0.05,0.075,0.10):
        p2=p1+d
        print(label, f"+{d*100:g}pt",
              math.ceil((za+z_b)**2*(p1*(1-p1)+p2*(1-p2))/d**2))
PY
```

### 3. Hard pre-conditions before Phase B may be submitted

1. **Cost gap (V6/G-F4).** The probe must show `always_strong` costs materially more than
   `always_fast` for the pinned pair (the design's margin: ≤1.25× ⇒ no arbitrage). If it does
   not, either swap the pair or close the cascade question.
2. **Value gap (G-F1).** The probe must show the strong model buys `test_executed_success`.
3. **Instrumentation gate.** I1–I4 must hold on **≥ 300 attempts spanning ≥ 2 models and
   ≥ 2 conditions**, and I2 or I4 must restore monotone separation (G-F5 must not fire).
4. **Probe-derived budget.** `R` and `stop.budget_usd` are set from the probe's measured
   variance — never scaled from another model's per-story cost (the E4 3.1× overrun).

### 4. The instrumentation gap that must be closed first (unchanged, confirmed)

The study needs four fields emitted **on the same attempt row**; it needs no new subsystem:

| # | gap today (measured) | smallest fix | unblocks |
|---|---|---|---|
| **I1** | `test_executed_success` on **4/394** | propagate `runtime/test_runner`'s verdict onto every attempt record | the independent outcome (primary metric) |
| **I2** | `confidence == 0.0` **is** the error flag (14/14 `failed`) | emit `confidence = None` on error and log `error: true` separately | removes the definitional coupling |
| **I3** | present **60.2%** `ok` vs **26.1%** `failed` | emit confidence unconditionally, with a reason code when unavailable | removes the selection bias |
| **I4** | **64.5%** of values are exactly `1.0` | record a variance-bearing (calibrated/binned) score | gives any threshold room to act |

**First gate: I1 + I3.** They are the two that make the calibration question answerable at all;
I2/I4 then decide whether the *signal* or only the *recorder* was at fault (U1).

### 5. Reproducibility contract (strengthened)

Phase B and every successor phase must **copy** `registry_index.jsonl` (and the kb artifacts it
resolves) into a versioned, committed snapshot before computing, and cite that snapshot's sha —
because the live sha does not survive between phases (V5). The posterior's snapshot
(`6761c52c…` / 55,081) is recorded above for continuity. Record both the live sha **and** the
snapshot sha when they differ.

### 6. Disposition of the narrowed fallback

The design §10 (`cascade_error_gate` — escalate only on `confidence == 0.0`) remains the **only**
arm Phase A licenses if the operator elects to run something before the instrumentation lands.
It is fault handling, not a confidence cascade, and it cannot answer the original question.

### 7. Cost ledger for Phase A

Phase A was analysis-only (`proposal_write`, no `src/`/`scripts/`/`tests/` change) and spent
**~$0** against its `stop.budget_usd: 4.0`.

---

## Provenance

**Machine artifact:** `experiments/results/confidence_cascade/retrospective.json`
(schema `confidence_cascade_retrospective/v1`), pinned at registry sha256
`7eaf2252…` / 55,079 / 24,263 kb / 388 ledgers, `generated_at 2026-09-22T13:10:03Z`.

**Posterior snapshot (recompute basis):** registry sha256
`6761c52cb23963baeca8ff784ccce3dd92d55dd65ec06e2fe864a85be0311d37`, 55,081 lines, 24,267 kb
artifacts, 388 ledgers. All independent recomputes above were run against this snapshot; the
counts matched the artifact, the sha did not.

**Inputs:** `notes/world_model.md`, `notes/plan.md`, `notes/sources.jsonl`
(`docs/reviews/confidence_cascade_retrospective.md`,
`docs/designs/proposed/confidence_cascade_study.md`).
