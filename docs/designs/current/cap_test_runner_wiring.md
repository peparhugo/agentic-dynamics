---
status: accepted
---
# CAP Test-Runner Wiring — Phase-Test-Verified for Agent Phases (t1: map the path)

**Spec:** `workflows/repository/cap_test_runner_wiring.yaml` (phase `t1_map_the_path`)
**Branch:** `feature/cap-test_runner_wiring`
**Date:** 2026-08-25 · **Model:** deepseek/deepseek-v4-flash (single-model, `--backend opencode`)
**Question:** Wire the independent test runner into attempt facts so `phase_test_verified` becomes
PRODUCED for workflow agent phases — the census gap is 7/455 (only the 7 explicit test-kind phases
carry a bool; agent phases stamp `None`). `runtime.test_runner` is the sole source of truth for
`test_executed_success`; this stream routes that signal into `attempt_facts/v1`'s
`phase_test_verified` predicate so shadow admissibility (one of the 5 formerly-unknown predicates)
is unblocked. `test_runner` is the sole source; additive only.

**Planned sections:** §1 path + seam mapping (t1) · §2 wiring implementation (t2) · §3 coverage note
+ what it unblocks (t3).

---

## 1. Path mapping — where the test_runner's outcome lives and where the fact is built

This section is the t1 deliverable: a line-by-line trace of the signal path from the execution
runtime to the fact plane, and the **named** seam the wiring crosses. **Guard honoured: no code
changed in this phase (design-only).**

### 1.1 The signal path, end to end

Three legs. The first two are the `runtime` plane; the third is the `control` plane. The seam sits
at the phase gate between leg 1 and legs 2–3.

**Leg 1 — Producer (runtime): the outcome exists at the phase gate, and only there.**

`run_workflow()` iterates `spec.workflow.params.phases` and branches per phase on `kind`
(`src/agentic_dynamics/runtime/workflow_runner.py:495-514`):

- The **only** call site of the independent runner is the `kind == "test"` branch:
  `run_suite(wd, language, timeout=phase_timeout)` (`workflow_runner.py:508`), succeeded by
  `pr.test_executed_success = suite_succeeded(suite)` (`workflow_runner.py:511`) — the boolean is
  derived from the runner's normalized result (`test_runner.py:138`, `suite_succeeded`;
  `total > 0 and failed == 0 and errors == 0`), never from the model's self-reported
  `tests_passed`/`tests_total`.
- The `agent` branch (default, `workflow_runner.py:515-629`) never invokes the runner; the
  `enforce_pytest` flag (`workflow_runner.py:582-584`) only edits the agent's *prompt*, never the
  harness. `test_executed_success` stays at its `PhaseResult` default `None`
  (`workflow_runner.py:113`).

At phase completion the phase is committed and appended (`result.phases.append(pr)`,
`workflow_runner.py:634-645`); the run is then serialized via `WorkflowRunResult.to_dict()` →
`PhaseResult.to_dict()` (`workflow_runner.py:177-190`).

**Leg 2 — Carrier + persistence (runtime → on-disk artifact): the field survives verbatim.**

- `PhaseResult.test_executed_success: bool | None = None` (`workflow_runner.py:113`) is the typed
  carrier; serialized unchanged by `PhaseResult.to_dict()` (`workflow_runner.py:147`) under the
  exact key name `test_executed_success`.
- `scripts/run_workflow.py:199-203` writes `WorkflowRunResult.to_dict()` to
  `experiments/results/workflows/<spec>/<timestamp>.json` — so each phase dict carries a
  `test_executed_success` key that is a real `bool` for test-kind phases and `null` for agent phases.

**Leg 3 — Reducer (control): the fact is built from that field, kind-agnostically.**

- **Batch evidence:** `scripts/kb_produce_facts.py:load_run_jsons()` (`:111`) loads every
  `experiments/results/workflows/**/*.json`; `_run_evidence()` (`:218`) wraps each distinct run in
  an `EvidenceItem(source_type="workflow_run")` whose `evidence_id` is the content-addressed
  `run_artifact_id` (payload sanitized by `_sanitize_run`, `:190`).
- **Auto-emit evidence (per run, default-ON):** `derive_run_facts()` (`kb_produce_facts.py:450`)
  builds the same evidence from `run = result.to_dict()` (`:502`) for the just-finished run, wired
  at `scripts/run_workflow.py:210` (`_emit_workflow_facts`, `:229`). Both routes funnel into the
  same `attempt_facts_v1`.
- `attempt_facts_v1()` (`src/agentic_dynamics/control/reducers/attempt_facts.py:237`) → per-phase
  `_facts_for_phase()` (`:177`) mints `phase_test_verified` at `:226-230`:

  ```python
  if isinstance(phase.get("test_executed_success"), bool):
      facts.append(fact("phase_test_verified", encode_value(phase.get("test_executed_success"), "bool")))
  ```

  This check is **not gated on `phase.get("kind")`** — the reducer already emits
  `phase_test_verified` for an *agent* phase too, whenever its `test_executed_success` field is a
  real bool. Epistemic status is `verified` → MEASURED/[M] (`attempt_facts.py:87-97`;
  `_EPISTEMIC_BY_PREDICATE`); the predicate is registered in `FACT_PREDICATES`
  (`facts.py:399-409`, `value_type="bool"`, `scope_type="attempt"`,
  `produced_by=("attempt_facts/v1",)`).

### 1.2 The census — reproduced, not assumed

| Evidence | Count | Source |
|---|---|---|
| `phase_test_verified` current registry facts, by phase name | **7/7 on `test`/`validate`/`verify`; 0 on agent phases** | `experiments/results/registry_index.jsonl` (source_type=fact, logical_locator `attempt:<phase>#phase_test_verified`, lifecycle_state current) |
| Workflow phases carrying a non-null `test_executed_success` | **7/455** | `docs/designs/current/cap_fact_backfill_coverage.md` §3a |
| Workflow run denominator | 455 phases / 125 runs | same coverage doc, §1 census command |

All 7 are `kind: test` phases. The 448 agent phases carry no runner outcome by construction, so
`attempt_facts/v1` can never mint `phase_test_verified` for them — the observed 0/455 agent-phase
coverage.

### 1.3 The seam — named, not assumed

> **The seam is `PhaseResult.test_executed_success` population at the phase gate**
> (`workflow_runner.py:507-514`, field default at `:113`).

It is the single typed field that carries the independent test_runner outcome from the `runtime`
plane into the attempt artifact the `control` plane's reducer reads — the field's **name is the
contract** (writer at `workflow_runner.py:147`, reader at `attempt_facts.py:227`, verbatim, no
mapping or transcription). Concretely:

- **Downstream half — already wired.** From the field onward (`to_dict()` → run artifact →
  `load_run_jsons`/`_run_evidence`/`derive_run_facts` → `_facts_for_phase` →
  `phase_test_verified`) the path is complete and kind-agnostic. The reducer needs **zero** changes
  for agent phases.
- **Upstream half — the gap.** The field is populated only in the `kind == "test"` branch
  (`workflow_runner.py:511`). For the ~448 non-test phases in the census, `run_suite` is never
  invoked, so the field serializes to `null` and the reducer's `isinstance(..., bool)` guard keeps
  `phase_test_verified` absent — the measured-or-absent semantics (`attempt_facts.py:226`) working
  exactly as designed, which is *why* the census reads 7/455.

The wiring therefore crosses this seam at **population time**: to make `phase_test_verified`
producible for agent phases, the test_runner's outcome must be captured into
`PhaseResult.test_executed_success` for them too — nothing downstream of the field changes.

### 1.4 What the wiring must do — the crossing contract

1. **Producer (runtime):** for an agent phase, run the independent `run_suite` +
   `suite_succeeded` at phase completion and stamp `PhaseResult.test_executed_success` **before**
   `to_dict()` can serialize it. `test_runner` stays the ONLY source — never a model self-report.
2. **Placement:** the gate is **per-phase opt-in** (e.g. a `gate: test` flag on the phase def), not
   run-after-every-agent-phase — hard rule 3 says "phases without a test run keep
   `phase_test_verified` None and the coverage note records why," so an opting-in phase gets a bool
   and a non-opting phase stays `None`. Additive: no existing spec's phase changes semantics.
3. **Contract key:** `test_executed_success` in the serialized phase dict — unchanged name and
   shape (`workflow_runner.py:147`); the reducer already reads it verbatim.
4. **Consumer (control):** unchanged. `_facts_for_phase`'s `isinstance(bool)` gate
   (`attempt_facts.py:227`) turns a present bool into `phase_test_verified` MEASURED/[M], and a
   `None` into absence. No reducer diff.
5. **Null-not-zero / F1 interplay:** a phase that did not run the runner keeps `None`, never a
   default. `_sanitize_run`'s F1 guard (`kb_produce_facts.py:167-215`) only nulls `cost_usd`, so a
   failed agent phase that still ran the gate records its real `False` — preserved as a genuine
   measurement.

### 1.5 Verification anchors (t1 map → t2 tests)

- **Hermetic reducer test:** fixture phase dicts with `test_executed_success` = `True` / `False` /
  absent → `attempt_facts_v1` emits `phase_test_verified` `true` / `false` / nothing (pattern:
  `tests/test_context_plane_reducers.py` attempt-facts block, `:614-680`).
- **Hermetic runner-gate test:** fixture agent phase where the gate ran (`run_suite` result → bool)
  vs did not (no runner) → `PhaseResult.test_executed_success` bool vs `None`.
- **Re-derivation:** run `attempt_facts/v1` over one real workflow run whose agent phases now carry
  the bool and show the predicate goes from absent to `true`/`false` (the t2 verify step).

### 1.6 LOG

- **Seam named:** `PhaseResult.test_executed_success` population at the phase gate
  (`workflow_runner.py:507-514`, field default `:113`); the downstream leg
  (`attempt_facts.py:226-230`) is already kind-agnostic and needs no change.
- **PASS** — the path is fully traced with file:line evidence (legs 1–3 above); the census is
  reproduced from the registry (7/7 on test-kind phases, 0 on agent phases); the seam is named, not
  assumed; both endpoints verified in source. No code changed (design-only guard honoured).

---

## 2. The wiring (t2_wire_it) — PLACEHOLDER (filled in t2)

## 3. Coverage note and what it unblocks (t3_document) — PLACEHOLDER (filled in t3)
