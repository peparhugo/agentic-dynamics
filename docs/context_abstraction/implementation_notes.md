---
status: accepted
---
# Context Abstraction Plane — Implementation Notes

**Append-only.** This file records the design deviations and verify-phase findings that the
implement spec (`workflows/repository/context_abstraction_implement.yaml`) must carry into
I0–I7. Never rewrite or delete an existing line — append new entries below the last one.

## 1. Addendum A reference (out of scope)

`docs/designs/current/context_abstraction_design.md` Addendum A (I8 profiles, I9 patterns,
I10 checkpoint) is OUT OF SCOPE for this spec; I8–I10 are implemented under a follow-up design
spec, not here.

## 2. F1 resolution (material)

An invariant with `on_missing: classify` silently disables a safety constraint — invariants
require halt semantics; the validator refuses a contract whose invariant lacks halt semantics
(new check documented under C8); the design's `max_spend_usd` example is amended: either
demote it from `invariants` to `requires_facts` or set `on_missing: halt`.

## 3. F2 resolution

Check C5 rejects an empty `facts_used`.

## 4. F3 resolution

`expected_effect` scores are recorded on the decision record, never applied.

## 5. F4 resolution

`conflicted` is computed in the reducer (`fact_state()`), read by the compiler.

## 6. F5 resolution

OQ3/OQ7 table-form answers accepted as-is.

## 7. F6 resolution

`source_type=fact` nominal authority column is documentation only — no change.

## 8. CAP I0-I3 repair (r1-r4, material — carried forward into I4)

Before I4 (`context_compiler.py`) could resume, an audit found the I0-I3 reducers/fact-ingestion
implementation had four load-bearing gaps against the design's own stated invariants. All four are
fixed (`src/agentic_dynamics/control/reducers/{attempt_facts,job_facts,workflow_facts,_common}.py`,
`src/agentic_dynamics/control/fact_ingestion.py`, `scripts/kb_produce_facts.py`); the decisions
below are genuine deviations from what the design text left implicit, and I4 (or any future reader
of the fact plane) must know them:

1. **Run identity is a new, explicit concept — content-addressed, not caller-supplied.**
   `_common.run_artifact_id(run)` = sha256 of a run's own canonical (sorted-key) JSON. Introduced
   because `EvidenceItem.evidence_id` for a workflow run used to be `f"workflow:{spec_name}"` —
   spec-name-only — so every run of the same spec collided on identity regardless of model, phase
   values, or when it ran (two distinct persisted run artifacts silently merged into one fact).
2. **Attempt facts (L1) are PER-RUN; job facts (L2) are CURRENT-PER-CELL.** This is an explicit,
   asymmetric identity choice the original design left unstated (§ its own open question 2: "does
   a fact supersede by entity_id, or accumulate like observations?"). Attempt facts fold
   `run_artifact_id` into `scope_id` (`<cell>:<phase>:<run_id>`) so they NEVER supersede across
   runs (an attempt is a historical execution record — "phase X of run Y cost $Z" — not a mutable
   summary); job facts keep the pre-existing cell-only scope so they DO supersede via the existing
   registry chain (a job fact answers "what is the current state of this cell, right now"). Two
   opposite identity strategies for two adjacent abstraction levels, by design, not oversight.
3. **Content identity is NOT run identity — `fact_fingerprint` must ignore provenance.**
   Once `evidence_ids` carried a real run-specific citation (deviation 1), two runs of the same
   job cell that happened to measure the SAME value got DIFFERENT `evidence_ids` (each cites its
   own run) and therefore, if the fingerprint hashed them, DIFFERENT fingerprints — every
   re-run, even a pure re-confirmation, would have spuriously superseded the previous value and
   defeated the "unchanged → no-op" convergence guard the design explicitly requires. Fixed:
   `fact_ingestion.fact_fingerprint` hashes the DECLARATIVE payload only (predicate/value/scope/
   subject/abstraction_level/expires_at/reducer_version), excluding `evidence_ids`/
   `inputs_digest`. The persisted artifact (`knowledge_id`/`content_hash`) is untouched and still
   differs per run — only the supersession-worthiness decision changed.
4. **`derive_fact_records` guarantees oldest-first chaining itself — it does not merely benefit
   from a well-behaved caller.** Originally the "which value ends up current" outcome depended on
   the ORDER facts were handed in (a caller-side contract: `kb_produce_facts.load_run_jsons`
   sorts oldest-first). An adversarial review (r4) found this meant out-of-order evidence (a
   caller — or a future producer bug — handing facts newest-first) would let an OLDER observation
   win the "current" slot. Fixed: `derive_fact_records` now stably sorts its input by
   `observed_at` internally, so the guarantee holds regardless of caller behavior.

Two further r4 defense-in-depth additions, not identity deviations but worth recording alongside:
duplicate evidence (two on-disk run artifacts with byte-identical content) is deduped at
`kb_produce_facts._run_evidence` by `run_artifact_id`, and `workflow_facts_v1` independently
dedupes its finalized input facts by `fact_id` before aggregating, so a duplicated artifact
upstream can never double-count a phase in `workflow_phases_completed`/`workflow_status`.

Also material: `workflow_status`/`workflow_health` now treat `job_status` (derived from
`WorkflowRunResult.ok`, which sees EVERY phase) as authoritative over a phase-only scan for the
literal string `"failed"` — a phase status of `"skipped"`/`"error"`/`"timeout"` would otherwise
read as "not failed". And `projected_budget_overrun` is emitted only when BOTH a budget ceiling
AND a measured cost are known — an unmeasured cost previously fabricated a `0.0` overrun.
