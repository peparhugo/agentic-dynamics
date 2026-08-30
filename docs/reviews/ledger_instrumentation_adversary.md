---
status: accepted
---

# ledger_instrumentation — adversarial verification

**Role:** adversarial verifier (p4). **Source revision:** `workflows/repository/ledger_instrumentation.yaml`
SHA256 `8adafd6faa74877413bf62c42005aed30af6b00d01df338739364a2b0d8b96b3`. **Findings:**
`docs/reviews/workflow_metrics_findings.md` (section 6 is the post-instrumentation update). **Fresh
run:** `experiments/results/workflows/ledger_instrumentation_probe/20260830T190548Z.json`
(+ `docs/reviews/ledger_instrumentation_fresh_run.md`). **Aggregator:**
`scripts/aggregate_workflow_metrics.py` (+ `tests/test_aggregate_workflow_metrics.py`).

## Findings table

| # | Attack (order) | Result | Disposition |
|---|---|---|---|
| F1 | (1) field wiring — the attempt + breach fields are the EXACT schema fields | **PASS** | no finding; the named fields are byte-exact LEDGER_FIELDS names; two noted nuances (see §1) are documented design choices, not deviations |
| F2 | (2) backward compatibility — a ledger WITHOUT the new fields still parses | **PASS** | no finding; an old-shaped ledger classifies + extracts and every metric reports `not_measurable`, never a fabricated zero |
| F3 | (3) fresh-run verification — the complete records land + the metrics recompute | **PASS** | no finding; re-derived `attempt_count=2`, 2 attempt records, breach fields on both phases, 1 committed checkpoint; `r=0.0`/`WOC=1.0`/escalation `0.0`/checkpoint `0.0s` recompute |
| F4 | (4) branch discipline — main untouched, runner changes on the branch only | **PASS** | no finding; `main:workflow_runner.py` carries no `AttemptRecord`; the 4 phase commits are branch-only |
| F5 | (5) findings honesty — historical rows stand, post-instrumentation cites the fresh run | **PASS** | no finding; sections 1–5 are byte-unchanged; every §6 citation resolves |

No attack falsified a claim. The instrumentation's one load-bearing consequence — the attempt/breach/
checkpoint fields now emit and commit, making the operating metrics measurable — survives every
attack.

---

## Attack-by-attack

### (1) Field wiring — the exact schema fields, no deviating/invented field — **PASS**

Diffed `AttemptRecord.to_dict()`'s keys against `experiment_spec.LEDGER_FIELDS` (the single source
of truth). Every field the spec named is byte-exact and carries its declared semantics:

| field | LEDGER_FIELDS | emitted value (fresh run) | semantics |
|---|---|---|---|
| `attempt_count` | (metric-definition name; the literal schema field is `attempt_number`) | `2` (run level) | total attempt records = total agent phases |
| `retry_reason` | yes | `""` | not a retry (the runner never retries) |
| `first_pass` | yes | `true`/`true` | `status != "failed"` |
| `accepted` | yes | `true`/`false` (`gate` is `awaiting`) | `status == "ok"` |
| `escalation_from`/`escalation_to` | yes | `null`/`null` | no model escalation |
| `attempt_number` | yes | `1` | the sole attempt of the phase |

The breach fields (`stall_evidence`/`deploy_gate`/`commit_gate`/`relabel_gate`) are serialized with
their declared `PhaseResult` shapes (`dict | None`), all `null` on a clean run.

**Two noted nuances (non-falsifying).** (a) `attempt_count` is the spec's *metric-definition* term,
not a `LEDGER_FIELDS` entry; the schema's literal field is `attempt_number`. The run-level
`attempt_count = len(attempts)` = "how many attempts (model invocations) this run made" (2 agent
phases), which is a *different* quantity from the retry-rate metric's "attempt_count > 1" — the
aggregator derives that per-job (each phase = one single-attempt job) and honestly reads `0/2
retried`. The distinction is documented in `AttemptRecord` and in the aggregator's extraction. (b)
`AttemptRecord` also carries measured data outside `LEDGER_FIELDS` (`phase`, `cost_usd`, `tokens`)
— these mirror `PhaseResult`'s own fields (the phase-identity + cost + token conventions), not
invented schema fields. Neither nuance is a deviating or fabricated field.

### (2) Backward compatibility — a ledger WITHOUT the new fields still parses — **PASS**

Constructed a pre-instrumentation ledger (`spec_name` + `phases` with no breach keys, and **no**
`attempts`, `attempt_count`, `state`, or `checkpoints`) and ran it through the aggregator. It
classifies as `workflow_run` and extracts phases unchanged; every metric reports
`measurable=False` with the missing field named (`attempt_count, attempts`; `first_pass`;
`escalation_from, escalation_to`; `checkpoints`; `stall_evidence, deploy_gate, commit_gate,
relabel_gate`) — the old corpus is never imputed as zero. Locked additionally by
`tests/test_ledger_instrumentation.py::test_old_ledger_without_new_fields_still_parses` and
`test_new_ledger_is_a_superset_of_the_old_shape`.

### (3) Fresh-run verification — re-derive the records, recompute the metrics — **PASS**

Re-read the committed fresh-run ledger directly: `attempt_count=2`, two attempt records (each
`attempt_number=1`, `retry_reason=""`, `first_pass` `true`/`true`, `accepted` `true`/`false`,
`escalation_from`/`escalation_to` `null`), the four breach keys present on both phase ledgers, and
one `checkpoint_reached` record (`decision=awaiting`, `reached_at == decided_at`). Re-running the
aggregator recomputes `retry_rate=0.0`, `first_call_resolution=1.0`, `escalation_rate=0.0`,
`checkpoint_latency` (1 record, both timestamps, mean 0.0 s), and `sla_behavior` (2 phases with
breach fields, 0 breaches) — all `measurable=True`. The pinned definitions are byte-identical to the
pre-instrumentation aggregator (diffed `PINNED_METRIC_DEFINITIONS` against main: equal).

### (4) Branch discipline — main untouched, the changes are branch-only — **PASS**

`main` is at `d08698200` (advanced only by the in-flight workflow-metrics merge + README spec-count
bumps, not by this phase). The four phase commits (`p0_pin_mandate` … `p3_update_findings`) exist
only on `feature/ledger-instrumentation`. `git show main:src/agentic_dynamics/runtime/workflow_runner.py`
contains **zero** occurrences of `AttemptRecord` — the runner changes are branch-only. (Merge note,
not a violation: main's workflow-metrics merge brought its *own* `scripts/aggregate_workflow_metrics.py`
and `docs/reviews/workflow_metrics_findings.md`, so those two files will need a reconcile at merge
time; the runner + `.gitignore` + probe files have no such overlap.)

### (5) Findings honesty — historical rows stand, post-instrumentation cites the fresh run — **PASS**

`git diff` of `docs/reviews/workflow_metrics_findings.md` against the pre-update revision shows
**no `-` lines**: sections 1–5 (the historical "not measurable" rows, the "website claim
unsupported" flag, the "data is not there" conclusion) are byte-preserved; section 6 is purely
additive. Every §6 citation resolves to a real file (`workflow_runner.py`,
`ledger_instrumentation_probe.yaml`, the fresh-run ledger, `ledger_instrumentation_fresh_run.md`,
`aggregate.json`) and the `framework.html` line refs (`:726, :747, :904`) still point at the cited
text.

**LOG: PASS.**
