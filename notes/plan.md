# Plan — the confidence-cascade study, Phase A (retrospective + pre-registration)

Author: `confidence_cascade_study` phase `prior` (spec version `0.1`).
This is the *analysis plan*: the files Phase A will write, the exact queries that produce
every number, the acceptance conditions, and the risks. It is deliberately **analysis-only**
(matching `docs/reviews/loose_ends_register.md` L21: "analysis-only — the `g_test_gate`
skips explicitly"), so the plan names **no production code and no pytest targets**.

See `notes/world_model.md` for the observed coverage this plan is built on.

---

## Files

### Deliverables (Phase A owes these two documents)

| file | content |
|---|---|
| `docs/reviews/confidence_cascade_retrospective.md` | (1) the calibration of `confidence` vs outcome at the available sample sizes; (2) the escalation economics (which is a **zero-history** finding) and the counterfactual caveat; (3) a **feasibility verdict**; (4) the exact command that produced each number |
| `docs/designs/proposed/confidence_cascade_study.md` | the **pre-registered grid**: arms (always-fast / always-strong / cascade-at-θ), metrics (first-pass, accepted, test-executed success, cost inference + rework = quality-per-dollar), comparison (`arm_factor = policy`; `loss = {quality, cost}`), power derived from Phase A's effect sizes, and the falsifiers |

### Machine artifact (durable, cited by the retrospective)

| file | content |
|---|---|
| `experiments/results/confidence_cascade/retrospective.json` | the computed output — coverage counts, the calibration table, the counterfactual ROI table, the pinned registry sha256. Written by the recorded query block and cited by the doc (same pattern as the prior `experiments/results/cap_cascade_retrospective.json`). This path is under the gitignored `experiments/results/`, so it is a **process artifact**, not a tracked deliverable. |

### Working notes (this phase; travel via the phase report, per L11)

`notes/world_model.md`, `notes/plan.md`, `notes/sources.jsonl` (this phase) and, in later
phases, `notes/posterior.md`, `notes/adversarial_review.md`.

### Explicitly NOT in this phase

No `src/` module, no `scripts/*` entry point, no `tests/` file. Phase A is `proposal_write`
scope and analysis-only. Phase B (the grid) is a **later submission** and is the only thing
that would add machinery.

---

## Queries — the exact commands (run from `/app`; the live data root)

> The live registry is unversioned. **Pin it first** and record the sha in the retrospective:
> `sha256sum /app/experiments/results/registry_index.jsonl`
> (observed this phase: `cf64fc97d8352ea4ea61e260160b9aa91342d3f4a0442032944571a45da7cf5c`).

**Q1 — coverage pre-check (confidence + outcome, and every predicate's reach).**
Build `attempt_key -> {predicate: knowledge_id}` from current `fact` rows whose
`source_uri` starts `fact://attempt/`, then count reachable predicates and co-occurrence:

```python
import json, collections
by_att = collections.defaultdict(dict)
for line in open('experiments/results/registry_index.jsonl'):
    if not line.strip(): continue
    r = json.loads(line)
    if r.get('source_type') != 'fact' or r.get('lifecycle_state') != 'current': continue
    uri = str(r.get('source_uri') or '')
    if not uri.startswith('fact://attempt/'): continue
    key, pred = uri[len('fact://attempt/'):].rsplit('/', 1)
    by_att[key][pred] = r['knowledge_id']
cov = lambda *ps: sum(1 for v in by_att.values() if set(ps) <= v)
print('attempts', len(by_att),
      'confidence', cov('attempt_confidence'),
      'confidence+status', cov('attempt_confidence', 'phase_status'),
      'verified', cov('phase_test_verified'),
      'verified+confidence', cov('phase_test_verified', 'attempt_confidence'))
```

**Q2 — calibration values (the kb-artifact join).** Resolve each predicate's value via
`json.loads(open(f'experiments/results/kb/{kid}.json')['text'])['value']`, then bin
confidence and compute `P(phase_status == "ok" | bin)`, per stratum (model / story / vintage)
as well as pooled. **Null-not-zero:** an attempt whose artifact is missing or unparseable is
*a*bsent (reported as a coverage count), never a `0.0` confidence and never a `failed`
outcome.

**Q3 — escalation history (the ROI feasibility check).** Over
`experiments/results/workflows/**/*.json`, count attempt rows with a non-empty
`escalation_from`/`escalation_to` or `parent_attempt_id`, and count retries
(`attempt_number > 1`). Observed this phase: **0 / 0 / 0**.

**Q4 — reproduce the prior baseline.** Re-read `cap_cascade_retrospective.json` and confirm
baseline cpvo `$1.8109` (`785.9273 / 434`) and the trigger rates; **cite it, do not
recompute a competing number** — Phase A's new content is calibration, not a second
baseline.

**Q5 — parquet exposure (negative control).**
`python3 scripts/sync_data.py --check` (the **flag**, never the positional `check`) and a
`duckdb` `describe` of `sessions.parquet` / `stories.parquet`, demonstrating that the
calibration fields are absent from the parquet (so the doc does not imply the parquet can
answer the question).

**Q6 — the design's power inputs.** From Q2, extract the observed effect sizes the
pre-registration needs: the spread of `P(ok | bin)` across bins, the trigger fraction at
each candidate θ, and the per-attempt cost distribution (`attempt_cost_usd`). These are the
only numbers Phase B's power may be derived from.

---

## Tests

**This is an analysis-only plan: there are no pytest targets, and the `g_test_gate` phase
is expected to SKIP explicitly** (recorded on the run ledger as a skip, matching
`workflow_runner`'s analysis-only contract and `loose_ends_register.md` L21).

The substitute for a test suite is the **reproducibility contract**: every number in both
documents must be reproducible from a command recorded in the document, and the
machine artifact (`experiments/results/confidence_cascade/retrospective.json`) is the
single source the prose quotes. The adversarial phase (`g_adversarial`) recomputes one
number from its recorded query as the independent check.

If, at execute time, the operator decides the analysis warrants a committed, tested script,
that is a **scope change** (a `proposal_write` → `implementation` move, a new `scripts/*`
entry point requiring the AGENTS one-line justification) and must be recorded as a
deviation, not smuggled into this phase.

---

## Acceptance

Phase A is **acceptance-complete** when all of the following hold:

1. **Coverage is stated before any metric.** The retrospective opens with the Q1 counts —
   how many attempts carry `confidence` (1,345), how many carry a resolvable outcome
   (2,353), how many are paired (1,345) — and the `phase_test_verified` reach (132; 4 with
   confidence). No downstream number is presented before its coverage.
2. **The calibration is reported with its degeneracy, not hidden.** The bin table is shown;
   the doc states that the signal is informative essentially only at `0.0`, that `P(ok)`
   is flat (~0.96–0.98) above `0.2`, and that the `0.0` cell is **partly definitional**
   (`opencode.py:113` computes `confidence` from the same run the outcome records).
3. **The verified-outcome infeasibility is explicit.** The doc says a calibration against
   *independent correctness* is not measurable (n=4) and does not substitute the completion
   signal without naming the substitution.
4. **Escalation economics is stated as zero-history.** The doc reports 0 escalations /
   0 retries-of-lineage, labels the ROI **counterfactual only**, and separates the n=1 `E_x`
   multiplier (11.47 / 12.51, a *defect-fix* cost) from a cascade ROI.
5. **The feasibility verdict is explicit and first-class.** Either "calibratable, grid
   proceeds" or "null feasibility — grid pauses / is reduced", with the reason.
6. **The pre-registration is complete or expressly paused.** If calibration is infeasible,
   `docs/designs/proposed/confidence_cascade_study.md` says so and either pauses or narrows
   the grid; arms, metrics, comparison (`arm_factor = policy`; `loss = {quality, cost}`),
   power, and falsifiers are otherwise fully specified.
7. **Every number traces.** Each quantitative claim cites the query (Q1–Q6) and the
   registry sha256 `cf64fc97…`; the machine artifact matches the prose.

---

## Falsifiers (what would REFUTE the plan's hypotheses)

These are the analytic tests the recorded queries will run — if any fires, the
corresponding claim dies and the grid must change:

| # | hypothesis under test | falsifier (fires ⇒ claim refuted) |
|---|---|---|
| F1 | `confidence` is calibrated against the outcome | `P(ok \| confidence bin)` is flat or non-monotone across the bins that carry mass (every bin with n ≥ 5 except the `0.0` cell). Observed shape already suggests **this fires**: only `0.0` separates. |
| F2 | A threshold policy has room to act | fewer than some minimum fraction of attempts fall below any θ in `(0.2, 1.0)` — i.e. the trigger rate is ~0 for every useful θ (65.5% sit at exactly `1.0`). |
| F3 | The signal predicts the outcome *independently* | the `P(ok\|bin)` structure is explained by the `0.0` cell alone and `confidence` adds no ordinal information above `0.0` (test: is `P(ok)` non-decreasing where n ≥ 5?). |
| F4 | Escalation economics is measurable from history | **this already fires**: 0 observed escalations ⇒ no retrospective ROI; any "ROI" presented as measured is refuted by construction. |
| F5 | The corpus is large enough to fit a threshold with power | the paired sample (1,345) is dominated by one point mass and one model/task mixture; a per-stratum calibration leaves bins with n < 5, which cannot support a threshold. |
| F6 | The parquet can carry the study | the parquet lacks `confidence` (Q5) ⇒ any design that assumes the parquet supplies the signal is refuted. |

**Falsifier disposition rule (from the spec):** if F1/F3/F5 fire, the retrospective records
a **null feasibility** result and the grid design **pauses** (or is narrowed to the only
defensible arm — e.g. a `0.0`-vs-rest error gate — with the narrowing stated as a
pre-registered consequence). The plan does not require the grid to proceed; it requires the
retrospective to be honest about which falsifiers fired.

---

## Risks

1. **Definitional coupling (the biggest risk).** `confidence` is computed from the same run
   that produces `phase_status` (`opencode.py:113`). A "calibration" can therefore look real
   while being partly arithmetic identity. *Mitigation:* report the `phase_status` result
   **and** flag it as completion-only; do not claim it predicts independent correctness.
2. **Unversioned data.** `/app` is outside the worktree and not in git. A re-run on another
   day yields different counts. *Mitigation:* pin and record the registry sha256; state the
   snapshot date; treat every count as of that sha.
3. **The named query is empty.** A careless execute phase could read
   `source_type == 'ledger_attempt'`, get 0, and wrongly conclude "no data". *Mitigation:*
   the plan and world model name the correct layer (`fact` + kb artifacts); the retrospective
   must show the 0-for-`ledger_attempt` as a *finding*, not a result.
4. **Confounds.** Pooled calibration averages over models, stories, and run vintages.
   *Mitigation:* stratify by model and by task where n permits; report the strata that fall
   below n≥5 rather than pooling them silently.
5. **`sync_data.py` hand-run hazard.** `main()` (`scripts/sync_data.py:461`) only branches on
   the `--check` / `--query` **flags**; every other argv — including the positional
   `python3 scripts/sync_data.py check` — falls through to `sync()`. That positional did run
   sync during this inventory and overwrote the tracked parquet with empty tables
   (restored via `git restore`). *Mitigation:* use **`--check`** only; never the positional
   form; never run bare sync in this checkout (its canonical payloads are absent, so it
   writes empty and the tracked parquet goes stale).
6. **Competing with prior art.** `cap_cascade_retrospective.json` already exists. Phase A
   must *extend* it (calibration), not restate it, or the phase produces no new information.
   *Mitigation:* cite its baseline ($1.8109) and add only the calibration + feasibility.
7. **Budget honesty for Phase B.** The E4 grid overran its ceiling 3.1×; any Phase B power
   statement must re-baseline per-story cost from probes, not scale from another model.
   Phase A itself is analysis-only and spends ~$0.
8. **Notes are gitignored (L11).** `notes/` is deliberately untracked; the phase's durable
   record travels via the phase report and the KB. *Mitigation:* write the notes on disk (the
   later phases' `requires_files` read them there) and additionally force-add them into this
   phase's commit so the phase record is self-contained; this does not touch `main`.
