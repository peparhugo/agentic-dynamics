---
status: accepted
---

# ledger_instrumentation — known-safe attacks

**Role:** adversarial verifier (p4). **Source revision:** `workflows/repository/ledger_instrumentation.yaml`
SHA256 `8adafd6faa74877413bf62c42005aed30af6b00d01df338739364a2b0d8b96b3`.

This companion file records the non-falsifying attacks attempted — what was tried, the evidence, and
why each did not falsify the instrumentation.

## Attempted attacks and why they did not falsify

### A1. "The attempt emission invents or renames a schema field" — not supported
- **Tried:** diffing `AttemptRecord.to_dict()` keys against `experiment_spec.LEDGER_FIELDS`.
- **Evidence:** the spec-named fields (`retry_reason`, `first_pass`, `accepted`,
  `escalation_from`, `escalation_to`, `attempt_number`) are byte-exact LEDGER_FIELDS names; the
  extra keys (`phase`, `cost_usd`, `tokens`) mirror `PhaseResult`'s own measured-data convention
  and are not fabricated schema fields.
- **Why safe:** the named fields' names and semantics are pinned; nothing is invented.

### A2. "`attempt_count` double-counts the retry metric" — a documented distinction, not a bug
- **Tried:** reading `attempt_count=2` (run level) against the retry-rate metric's
  "attempt_count > 1" (per-job).
- **Evidence:** the run-level `attempt_count` is the total attempt-record count (= agent phases);
  the aggregator derives the retry metric per-job (each phase = one single-attempt job), so the
  honest `r` is `0/2`, not `2/2`. Documented in `AttemptRecord`'s docstring and the aggregator's
  extraction docstring.
- **Why safe:** two different quantities share the metric-definition name; both are recorded
  honestly and the retry metric never conflates them.

### A3. "An old ledger crashes the aggregator or gets imputed as zero" — not supported
- **Tried:** a pre-instrumentation ledger (no `attempts`/`attempt_count`/`state`/`checkpoints`, no
  breach keys) through `classify` + `extract_ledger` + all eight metric computers.
- **Evidence:** it classifies `workflow_run`, extracts phases unchanged, and every metric reports
  `measurable=False` naming the missing field — never a fabricated `0.0` or a clean SLA record.
- **Why safe:** the new keys are additive; the measured-not-estimated rule holds for the old corpus.

### A4. "The fresh-run ledger was hand-authored, not produced by the runner" — not supported
- **Tried:** re-deriving the field presence from the committed ledger and recomputing the metrics
  with the aggregator against the live corpus.
- **Evidence:** the ledger carries the exact emitted shape (`attempt_count=2`, per-attempt
  `attempt_number=1`/`retry_reason=""`/`first_pass`/`accepted`/`escalation=null`, four breach keys,
  one `checkpoint_reached` record with `reached_at==decided_at`); the aggregator recomputes the
  four now-measurable metrics over it.
- **Why safe:** the records are machine-emitted, committed, and re-derivable from disk.

### A5. "The runner changes leaked onto main" — not supported
- **Tried:** `git show main:src/agentic_dynamics/runtime/workflow_runner.py` and `git log main..branch`.
- **Evidence:** main's runner has zero `AttemptRecord` occurrences; the four phase commits are
  branch-only; main advanced only via the in-flight workflow-metrics merge + README bumps.
- **Why safe:** the branch discipline holds — the runner changes live on `feature/ledger-instrumentation`.

### A6. "The findings rewrote the historical rows" — not supported
- **Tried:** `git diff` of `docs/reviews/workflow_metrics_findings.md` against the pre-update
  revision.
- **Evidence:** zero `-` lines — sections 1–5 are byte-preserved; section 6 is purely additive and
  every citation resolves.
- **Why safe:** the historical "not measurable" state stands honestly; the post-instrumentation
  update cites the fresh run rather than re-measuring the old corpus.

### A7. "The pinned metric definitions were silently changed" — not supported
- **Tried:** diffing `PINNED_METRIC_DEFINITIONS` between the pre-instrumentation aggregator and the
  branch.
- **Evidence:** byte-identical; only the *extraction* (attempt rows) and two *computers*
  (`first_pass`/`escalation`, which now read the written fields) changed.
- **Why safe:** hard rule (8) holds — the data became measurable, the definitions did not.

**LOG: PASS** — none of the attacks falsified a claim; the known-safe list records seven attempted
and non-falsifying attacks.
