---
status: accepted
---
# CAP Test-Runner Wiring — Phase-Test-Verified for Agent Phases (t1–t3)

**Spec:** `workflows/repository/cap_test_runner_wiring.yaml` (phases `t1_map_the_path` →
`t2_wire_it` → `t3_document`)
**Branch:** `feature/cap-test_runner_wiring`
**Date:** 2026-08-25 · **Model:** deepseek/deepseek-v4-flash (single-model, `--backend opencode`)
**Question:** Wire the independent test runner into attempt facts so `phase_test_verified` becomes
PRODUCED for workflow agent phases — the census gap is 7/455 (only the 7 explicit test-kind phases
carry a bool; agent phases stamp `None`). `runtime.test_runner` is the sole source of truth for
`test_executed_success`; this stream routes that signal into `attempt_facts/v1`'s
`phase_test_verified` predicate so shadow admissibility (one of the 5 formerly-unknown predicates)
is unblocked. `test_runner` is the sole source; additive only.

**Sections:** §1 path + seam mapping (t1) · §2 wiring implementation (t2) · §3 coverage note +
what it unblocks (t3).

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
(`src/agentic_dynamics/runtime/workflow_runner.py:517-519`):

- The test-kind branch calls `run_suite(wd, language, timeout=phase_timeout)`
  (`workflow_runner.py:529-533`), succeeded by `pr.test_executed_success = suite_succeeded(suite)`
  (`workflow_runner.py:533`) — the boolean is derived from the runner's normalized result
  (`test_runner.py:138`, `suite_succeeded`; `total > 0 and failed == 0 and errors == 0`), never
  from the model's self-reported `tests_passed`/`tests_total`.
- The `agent` branch (default, `workflow_runner.py:537-649`) never invokes the runner itself; the
  `enforce_pytest` flag (`workflow_runner.py:604-606`) only edits the agent's *prompt*, never the
  harness. `test_executed_success` stays at its `PhaseResult` default `None`
  (`workflow_runner.py:116`) — unless the phase declares `test_gate` (see §2).

At phase completion the phase is committed and appended (`result.phases.append(pr)`,
`workflow_runner.py:678`); the run is then serialized via `WorkflowRunResult.to_dict()` →
`PhaseResult.to_dict()` (`workflow_runner.py:181`, `:121`).

**Leg 2 — Carrier + persistence (runtime → on-disk artifact): the field survives verbatim.**

- `PhaseResult.test_executed_success: bool | None = None` (`workflow_runner.py:116`) is the typed
  carrier; serialized unchanged by `PhaseResult.to_dict()` (`workflow_runner.py:150`) under the
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
> (`workflow_runner.py:529-533`, field default at `:116`).

It is the single typed field that carries the independent test_runner outcome from the `runtime`
plane into the attempt artifact the `control` plane's reducer reads — the field's **name is the
contract** (writer at `workflow_runner.py:150`, reader at `attempt_facts.py:227`, verbatim, no
mapping or transcription). Concretely:

- **Downstream half — already wired.** From the field onward (`to_dict()` → run artifact →
  `load_run_jsons`/`_run_evidence`/`derive_run_facts` → `_facts_for_phase` →
  `phase_test_verified`) the path is complete and kind-agnostic. The reducer needs **zero** changes
  for agent phases.
- **Upstream half — the gap.** The field is populated only in the `kind == "test"` branch
  (`workflow_runner.py:533`). For the ~448 non-test phases in the census, `run_suite` is never
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
2. **Placement:** the gate is **per-phase opt-in** (`test_gate: true` on the phase def — the name
   finalised at implementation, §2.1), not run-after-every-agent-phase — hard rule 3 says "phases
   without a test run keep `phase_test_verified` None and the coverage note records why," so an
   opting-in phase gets a bool and a non-opting phase stays `None`. Additive: no existing spec's
   phase changes semantics.
3. **Contract key:** `test_executed_success` in the serialized phase dict — unchanged name and
   shape (`workflow_runner.py:150`); the reducer already reads it verbatim.
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
  (`workflow_runner.py:529-533`, field default `:116`); the downstream leg
  (`attempt_facts.py:226-230`) is already kind-agnostic and needs no change.
- **PASS** — the path is fully traced with file:line evidence (legs 1–3 above); the census is
  reproduced from the registry (7/7 on test-kind phases, 0 on agent phases); the seam is named, not
  assumed; both endpoints verified in source. No code changed (design-only guard honoured).

---

## 2. The wiring (t2_wire_it)

This section is the t2 deliverable: the implementation that crosses the §1 seam at **population
time**, per the §1.4 crossing contract. **Guard honoured: additive only — zero reducer changes,
zero semantic change to existing phases, the boolean comes only from `test_runner`, and a phase
whose runner did not execute keeps the field `None` (never a default).**

### 2.1 What was implemented

A **per-phase opt-in flag `test_gate: true`** on an agent phase, enforced at the phase gate:

```python
# workflow_runner.py:664-665 — after the agent branch, before duration/commit
if kind != "test" and phase_def.get("test_gate") and pr.status == "ok":
    _run_test_gate(pr, wd, language, phase_timeout)
```

`_run_test_gate` (`workflow_runner.py:277-296`) runs the independent suite and stamps the attempt,
mirroring the `kind == "test"` branch verbatim (`workflow_runner.py:529-533`):

```python
suite = run_suite(wd, language, timeout=timeout)
pr.tests_passed = suite["passed"]
pr.tests_total = suite["total"]
pr.test_executed_success = suite_succeeded(suite)
if suite.get("failed", 0) > 0 or suite.get("errors", 0) > 0:
    pr.status = "failed"
    pr.error = suite.get("tail", "")[-400:]
```

Three design decisions (each documented in-code, `workflow_runner.py:8-13` + `:656-663`):

1. **Opt-in, not run-after-every-agent-phase.** The flag is per-phase, so a spec opts its agent
   phases into independent verification explicitly. Existing phases are byte-for-byte unchanged —
   the additive guarantee (hard rule 3).
2. **The gate runs only when the agent phase already succeeded** (`pr.status == "ok"`). A failed
   agent phase is failed regardless; running the suite would only record noise, and the honest
   "runner did not execute" → `None` is the null-not-zero outcome. `test_runner` remains the **only**
   source: the boolean is `suite_succeeded(run_suite(...))`, never a model self-report, and
   `enforce_pytest` (a prompt-only knob, `workflow_runner.py:604-606`) is untouched.
3. **A failing gate fails the phase.** Same semantics as the test-kind branch: no commit
   (`workflow_runner.py:668-669` — the `if commit and pr.status == "ok":` gate skips
   `_git_commit`), `stop_on_error` stops, and the recorded
   `False` survives into the attempt as a **genuine measurement** — `_sanitize_run`'s F1 guard
   (`kb_produce_facts.py:190-215`) only nulls `cost_usd`, never `test_executed_success`.

### 2.2 Behaviour matrix (traceable to `tests/test_test_runner_wiring.py`)

| `test_gate` | agent ok | runner outcome | `test_executed_success` | phase status | `phase_test_verified` |
|---|---|---|---|---|---|
| absent | ok | — (runner not run) | `None` | `ok` | **absent** (`test_:86`) |
| absent | failed | — | `None` | `failed` | absent |
| `true` | ok | suite passes | `True` | `ok` | **`true`** (`test_:100`) |
| `true` | ok | suite fails | `False` | `failed` (no commit, stop) | **`false`** (`test_:116`, `:152`) |
| `true` | failed | — (gate gated on ok) | `None` | `failed` | absent (`test_:133`) |

### 2.3 What did NOT change (the additive guarantee)

- **`attempt_facts/v1` is untouched** (`attempt_facts.py` byte-identical) — its `isinstance(bool)`
  gate at `:227` was already kind-agnostic, so an agent phase carrying a bool mints the fact with
  no reducer diff.
- **`test_runner` is untouched** — `run_suite` / `suite_succeeded` are reused as-is
  (`test_runner.py:113`, `:138`); the story-path caller (`runtime/story/orchestration.py:197-203`)
  is unaffected.
- **No new evidence family or transport** — the fact flows through the existing
  `workflow_run` → `attempt_facts/v1` pipe (batch `load_run_jsons` and per-run auto-emit
  `derive_run_facts`, `kb_produce_facts.py:111`, `:450`), so `run_artifact_id` identity, the
  out-of-order guard, and the idempotence gate are all inherited unchanged.

### 2.4 Tests (t2 VERIFY)

`tests/test_test_runner_wiring.py` — 6 tests, all hermetic (fixture `run_suite` monkeypatched)
except the final integration test:

- `:86` no gate → agent field `None`, no fact; test-kind fact unchanged (`true`).
- `:100` gate + passing fixture → `True`, serialized as bool, reducer mints `"true"`.
- `:116` gate + failing fixture → `False`, phase failed, stopped, reducer mints `"false"`.
- `:133` gate on a phase whose agent failed → runner never called, field `None`.
- `:152` gate failure in a real git worktree → `[workflow] implement` commit skipped.
- `:180` **real re-derivation**: real `run_suite` against a real pytest suite in a real git
  worktree (only the LLM stubbed), then the real `attempt_facts/v1` mints
  `phase_test_verified = "true"` (`epistemic_status=verified`, MEASURED/[M]) for an agent phase.

### 2.5 Verification results

- New suite: **6 passed**. `tests/test_workflow_runner.py`: **29 passed**. CAP + guards
  (`test_context_plane_reducers`, `test_kb_produce_facts_*`, `test_cap_i0_i3_adversarial`,
  `test_fact_auto_emit*`, `test_context_plane_*`, `test_dependency_direction`, `test_data_flow`,
  `test_script_classification`, `test_doc_lifecycle`, spec/compiler + ledger families): **755
  passed**.
- Two pre-existing failures, unrelated to this diff (same root cause — published lab artifacts are
  stale against a registry that grew 701 → 736 rows): `test_lab_contract.py::…_valid_contract` and
  `test_lab_outputs_canonical.py::…_match_the_current_registry`. Neither touches the reducer, the
  runner, or the fact plane.

---

## 3. Coverage note and what it unblocks (t3_document)

### 3.1 The coverage note — PARTIAL → PRODUCED, precisely scoped

The census's verdict for `phase_test_verified` is **PARTIAL** (`cap_fact_backfill_coverage.md`
§3a, `:47`): workflow **7/455** (only the 7 test-kind phases carry a bool), story 92/227 cells
(cell-level only). The coverage note is: **agent phases no longer stamp `None` by construction.**
Before this wiring, "the 448 agent phases carry no runner outcome *because nothing records it*" was
true in the code. After it, the same 448-shaped phases stamp `None` **only when their spec did not
declare `test_gate`** — and any phase that opts in is emit-ready for the predicate. In the
coverage-doc's verdict terms (`:25-33`), `phase_test_verified` moves from "**PARTIAL**, gap:
agent phases stamp None" toward **PRODUCED** for every cell whose workflow gates its agent phases —
the measured-or-absent semantics keeps an un-gated phase `None` (never a fabricated default), so
coverage rises per cell exactly as fast as specs opt in.

**Scope honesty (the guard):** the wiring makes the predicate *producible*; it does **not**
retroactively populate the historical corpus. Existing run artifacts keep `null` and re-deriving
them cannot fabricate a bool (the reducer's `isinstance(bool)` guard and the idempotent
content-addressed `run_artifact_id` both forbid it). The historical 7/455 figure stands for the
pre-wiring corpus; the path is forward-looking.

### 3.2 What it unblocks — shadow admissibility

`phase_test_verified` is one of the **5 formerly-unknown predicates** that shadow snapshots miss
5/5 times (`cap_shadow_measurement.md:138-141`: `allowed_models`, `job_accumulated_cost_usd`,
`max_spend_usd`, `phase_test_verified`, `workflow_phases_remaining`) — the direct cause of the
shadow campaign's 0% agreement rate. Its coverage pre-check (`cap_routing_evidence_specs.md:51`)
found `phase_test_verified` **0/420** agent phases — the r4 fix made the pre-check *see* the gap,
but nothing produced the fact. This wiring closes that producer gap: a gated agent phase now
carries the MEASURED/[M] `verified`-epistemic bool, so the shadow admissibility gate (`route_next_job`
contract requiring `phase_test_verified`, `experiments/contexts/route_next_job.yaml:71`) no longer
resolves the predicate to "unknown" for those cells. It does **not** by itself flip the apply
decision — that still needs the `shadow_decision_report.py` agreement / `decision_arm_comparison.py`
loss evidence and a usable n (`cap_shadow_measurement.md:146-158`) — it removes one of the two
structural blockers (facts now populate where the plane could decide).

### 3.3 What it does NOT unblock (honest boundary)

- **Job-scoped aggregation of the predicate is still missing.** `cap_gate_migration.md:115-121`:
  a control rule requiring `phase_test_verified` at `scope: job` (not `attempt`) remains unwritable
  until an `aggregates_from: phase_test_verified` job-level reducer exists. This wiring is the
  per-attempt prerequisite, not that aggregate.
- **Story-cell coverage is unchanged.** Story cells already carry `test_executed_success`
  cell-level (`ledger_ingestion.py:180`); wiring them into a *per-session* attempt fact remains the
  story-bridge gap (`cap_story_bridge.yaml`).

### 3.4 LOG

- **Seam:** `PhaseResult.test_executed_success` population at the phase gate — crossed by the
  `test_gate: true` opt-in gate (`workflow_runner.py:664-665`), stamped by `_run_test_gate`
  (`:277`), read verbatim by `attempt_facts/v1` (`attempt_facts.py:227`).
- **PASS** — §1 mapping, §2 wiring, and §3 coverage/unblocks are complete; every claim traces to
  code (`workflow_runner.py:8-13,116,150,277-296,529-533,604-606,656-665`), the reducer
  (`attempt_facts.py:226-230`), the tests (`tests/test_test_runner_wiring.py`), and the cited
  designs/ledgers (`cap_fact_backfill_coverage.md:47`, `cap_shadow_measurement.md:138-141`,
  `cap_routing_evidence_specs.md:51`, `cap_gate_migration.md:115-121`).
