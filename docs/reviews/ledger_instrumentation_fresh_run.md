---
status: accepted
---

# ledger_instrumentation — fresh-run verification (p2)

**Role:** verify by a FRESH run (p2). **Spec:** `workflows/repository/ledger_instrumentation.yaml`
SHA256 `8adafd6faa74877413bf62c42005aed30af6b00d01df338739364a2b0d8b96b3`.

**The claim under test:** the instrumented runner (ledger_instrumentation p1) produces the
COMPLETE ledger — the attempt fields, the breach fields, and the committed checkpoints array —
and the aggregator (`scripts/aggregate_workflow_metrics.py`) re-runs with the metrics now
measurable, the pinned definitions unchanged.

## The fresh run

- **Spec:** `workflows/repository/ledger_instrumentation_probe.yaml` (a committed, repeatable
  probe: `scope` agent phase + `gate` agent phase with `checkpoint: true`).
- **Runner:** `run_workflow` (the modified runner) driven end-to-end in a scratch git worktree,
  `commit=True`, with the test suite's injected fake agent (the emission under verification is
  the runner's deterministic serialization, not the LLM).
- **Ledger:** `experiments/results/workflows/ledger_instrumentation_probe/20260830T190548Z.json`
  (committed — the `.gitignore` fix makes run-ledger JSONs trackable).

## Fields-present table

| field family | present in the fresh-run ledger? | observed |
|---|---|---|
| attempt fields (`attempt_count`, `retry_reason`, `first_pass`, `accepted`, `escalation_from/to`) | **YES** | `attempt_count=2`; 2 attempt records: `attempt_number=1`, `retry_reason=""`, `first_pass` `true`/`true`, `accepted` `true`/`false` (the `gate` phase is `awaiting`), `escalation_from/to=None` |
| breach fields (`stall_evidence`, `deploy_gate`, `commit_gate`, `relabel_gate`) | **YES** | present on both phase ledgers, all `None` (no breach recorded) |
| checkpoints array | **YES** | 1 committed `checkpoint_reached` record: `decision=awaiting`, `reached_at==decided_at` (a mechanical stop), `phase=gate`, `phase_index=2` |

## Aggregator re-run (pinned definitions unchanged)

`PINNED_METRIC_DEFINITIONS` is byte-identical; only the *extraction* gained the attempt rows and
the `first_pass`/`escalation` computers now read the (newly written) fields. Output:
`experiments/results/workflow_metrics/aggregate.json` (46 ledgers, 10 campaigns).

| metric | before (workflow-metrics findings) | after (fresh run, `ledger_instrumentation_probe`) |
|---|---|---|
| `r` (retry rate) | 0.125 (grit story grid only) | **measurable, 0.0** — 0/2 jobs with >1 attempt |
| `WOC` (first-call resolution) | not measurable (`first_pass` declared-not-written) | **measurable, 1.0** — 2/2 attempts first-pass |
| escalation rate | not measurable | **measurable, 0.0** — 0/2 attempts escalated |
| checkpoint latency | not measurable (0 records committed) | **measurable, 0.0 s** — 1 record, both timestamps present |
| `b` (batch fraction) | not measurable | not measurable (no batch-mode field — out of scope for this phase) |

`run_ledger_coverage` is unchanged at `{"referenced": 118, "present": 0, "absent": 118}` — the
index's 118 historical `results_pointer`s are still absent; the probe ledger is a NEW ledger
(not yet in the derived index), so the historical gap stands honestly while the forward path is
now committed.

## Verification

**PASS** — the complete records land (attempt fields, breach fields, committed checkpoints) and
the aggregator re-runs with `r`, `WOC`, escalation rate, and checkpoint latency measurable,
definitions pinned. The `throughput` figure (`80111.3 phases/hr`) is a degenerate artifact of the
instant fake agent (`span_hours≈0`), not an instrumentation defect.

**LOG: PASS.**
