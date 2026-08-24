---
status: accepted
---
# CAP Test-Runner Wiring — Phase-Test-Verified for Agent Phases (t1: map the path)

**Spec:** `workflows/repository/cap_test_runner_wiring.yaml` (phase `t1_map_the_path`)
**Branch:** `feature/cap-test_runner_wiring`
**Date:** 2026-08-25 · **Model:** deepseek/deepseek-v4-flash (single-model, `--backend opencode`)
**Question:** Wire the independent test runner into attempt facts so `phase_test_verified` becomes
PRODUCED for workflow agent phases — the census gap is 7/455 (only the 7 explicit test-kind phases
carry a bool; agent phases stamp `None`). `test_runner` is the sole source; additive only.

**Planned sections:** §1 path + seam mapping (t1) · §2 wiring implementation (t2) · §3 coverage note
+ what it unblocks (t3).

---

## 1. Path mapping — where the test_runner's outcome lives and where the fact is built

This section is the t1 deliverable: a line-by-line trace of the signal path from the execution
runtime to the fact plane, and the **named** seam the wiring crosses. No code changed in this
phase (design-only).

### 1.1 The signal path, end to end

Three legs. The first two are the `runtime` plane; the third is the `control` plane. The seam sits
between leg 1 and legs 2–3.

**Leg 1 — Producer (runtime): the outcome exists at the phase gate, and only there.**

`run_workflow()` iterates `spec.workflow.params.phases` and branches per phase on `kind`
(`src/agentic_dynamics/runtime/workflow_runner.py:495-514`):

- The **only** call site of the independent runner is the `kind == "test"` branch:
  `run_suite(wd, language, timeout=phase_timeout)` (`workflow_runner.py:508`), succeeded by
  `pr.test_executed_success = suite_succeeded(suite)` (`workflow_runner.py:511`) — the boolean is
  derived from the runner's normalized result (`test_runner.py:138`, `suite_succeeded`), never from
  the model's self-reported `tests_passed`/`tests_total`.
- The `agent` branch (`workflow_runner.py:515-629`) never touches `test_executed_success`; it stays
  at its `PhaseResult` default.

**Leg 2 — Carrier + persistence (runtime → on-disk artifact): the field survives verbatim.**

- `PhaseResult.test_executed_success: bool | None = None` (`workflow_runner.py:113`) is the typed
  carrier; serialized unchanged by `PhaseResult.to_dict()` (`workflow_runner.py:147`).
- `scripts/run_workflow.py:199-203` writes `WorkflowRunResult.to_dict()` to
  `experiments/results/workflows/<spec>/<timestamp>.json` — so each phase dict carries a
  `test_executed_success` key that is a real `bool` for test-kind phases and `null` for agent phases.

**Leg 3 — Reducer (control): the fact is built from that field, kind-agnostically.**

- `scripts/kb_produce_facts.py:load_run_jsons()` (`:111`) loads every
  `experiments/results/workflows/**/*.json`; `_run_evidence()` (`:218`) wraps each distinct run in an
  `EvidenceItem` whose `evidence_id` is the content-addressed `run_artifact_id`.
- `attempt_facts_v1()` (`src/agentic_dynamics/control/reducers/attempt_facts.py:237`) → per-phase
  `_facts_for_phase()` (`:177`) mints `phase_test_verified` at `:226-230`:

  ```python
  if isinstance(phase.get("test_executed_success"), bool):
      facts.append(fact("phase_test_verified", encode_value(phase.get("test_executed_success"), "bool")))
  ```

  This check is **not gated on `phase.get("kind")`** — the reducer already emits
  `phase_test_verified` for an *agent* phase too, whenever its `test_executed_success` field is a
  real bool. Epistemic status is `verified` → MEASURED/[M] (`attempt_facts.py:30-31,96`;
  `facts.py:86-87`); the predicate is registered in `FACT_PREDICATES` (`facts.py:399-409`).

### 1.2 The seam — named, not assumed

> **The seam is `PhaseResult.test_executed_success` population at the phase gate**
> (`workflow_runner.py:507-514`, field default at `:113`).

It is the single typed field that carries the independent test_runner outcome from the `runtime`
plane into the attempt artifact the `control` plane's reducer reads. Concretely:

- **Downstream half — already wired.** From the field onward (`to_dict()` → run artifact →
  `load_run_jsons`/`_run_evidence` → `_facts_for_phase` → `phase_test_verified`) the path is
  complete and kind-agnostic. The reducer needs **zero** changes for agent phases.
- **Upstream half — the gap.** The field is populated only in the `kind == "test"` branch
  (`workflow_runner.py:511`). For the ~448 non-test phases in the census, `run_suite` is never
  invoked, so the field serializes to `null` and the reducer's `isinstance(..., bool)` guard keeps
  `phase_test_verified` absent — the measured-or-absent semantics (`attempt_facts.py:226`) working
  exactly as designed, which is *why* the census reads 7/455.

The wiring therefore crosses this seam at **population time**: to make `phase_test_verified`
producible for agent phases, the test_runner's outcome must be captured into
`PhaseResult.test_executed_success` for them too — nothing downstream of the field changes.

### 1.3 Constraints the wiring must honour (from the spec's hard rules)

- **`test_runner` is the only source** — the boolean must come from `run_suite` /
  `suite_succeeded` (as `workflow_runner.py:508-511` does for test phases), never from the model's
  self-report or from `PhaseResult`'s agent branch.
- **Null-not-zero** — when the runner did not execute for a phase, `test_executed_success` stays
  `None` and `phase_test_verified` is absent; no default, no fabrication.
- **Additive only** — `attempt_facts/v1` semantics unchanged; the existing 7 test-kind facts are
  untouched.

### 1.4 LOG

- **Seam named:** `PhaseResult.test_executed_success` population at the phase gate
  (`workflow_runner.py:507-514`, `:113`); the reducer half (`attempt_facts.py:226-230`) is already
  kind-agnostic and needs no change.
- **PASS** — the path is fully traced with file:line evidence (legs 1–3 above); the seam is named,
  not assumed; both endpoints verified in source. No code changed (design-only guard honoured).
