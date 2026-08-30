---
status: accepted
---
# CAP Fact Backfill — Stage 0 Prerequisite Acceptance

**Spec:** `workflows/repository/cap_fact_backfill.yaml` (phase `p0_prereq_acceptance`)
**Branch:** `feature/cap-fact-backfill`
**Date:** 2026-08-24 (re-audit 2026-08-24) · **Model:** deepseek/deepseek-v4-flash (single-model, `--backend opencode`)
**Question:** Stage 0 is CHECKED, not assumed — verify with evidence (commands run, output shown)
that the five prerequisites for the retroactive fact backfill are merged and live before any
Stage 1 phase begins. Any FAIL => commit this doc and STOP.

## Check table

| # | Check | Command | Output summary | Result |
|---|---|---|---|---|
| 0.1 | Disposition merged | `git merge-base --is-ancestor feature/cap-shadow_campaign main`; same for `feature/cap-fact_auto_emit`; `grep applied` in `control/rules.py` + tests; `ls docs/experiments/results/cap_shadow_fact_disposition.md` | Both branches **REACHABLE from main**; `applied: False` shadow marker stamped in `rules.py:400-406`; 3 asserting tests pass (84-test suite green); disposition doc exists with fact-flow evidence (27 facts, idempotency re-derived to 0) | **PASS** |
| 0.2 | FINOPS_KB_WRITE | `echo $FINOPS_KB_WRITE` | `FINOPS_KB_WRITE=[1]` (set to `1`, plus `FINOPS_CELL_ID=wf_cap_fact_backfill_deepseek_deepseek_v4_flash`) | **PASS** |
| 0.3 | Gate migration merged | `grep -rn "requires_facts:" workflows/ experiments/definitions/`; `validate_fact_contracts` spot-check 3 | Matches in `workflows/repository/cap_routing_evidence_specs.yaml` + 6 spec files under `experiments/definitions/`; real gate (`validate_spec_fact_contracts`) clean — 0 errors on `cap_shadow_comparison`, `cap_confidence_cascade`, `cap_coverage_routing_impact` | **PASS** |
| 0.4 | Routing evidence specs | `ls experiments/definitions/{cap_shadow_comparison,cap_confidence_cascade,cap_coverage_routing_impact,cap_grit_strength_grid}.yaml`; `load_spec` + `validate_spec` + `validate_spec_fact_contracts` + `compile_spec` | All four exist; each loads, baseline-validates clean, passes the real fact-contract gate (0 errors), and compiles a full 7-phase DAG (validate → cells → execute → measure → compare → writeup → adapt) | **PASS** |
| 0.5 | Addendum merged | `test -f src/agentic_dynamics/control/profiles.py`; `grep pattern FACT_PREDICATES`; `test -f experiments/contexts/session_routing.yaml` | `profiles.py` **exists**; `FACT_PREDICATES["pattern"]` declared (`facts.py:663-674`, produced by `pattern/v1`, inheritable, workload-scoped); `session_routing.yaml` **exists**; addendum suites green (`test_context_plane_profiles/contracts/seam` + `test_actuation_ingestion`: 84 passed) | **PASS** |

**VERDICT: 5/5 PASS** — no guard trip. Stage 0 accepted; proceed to Stage 1
(`p1_corpus_inventory`). In-flight branches untouched (no diff involving the four in-flight
worktrees/branches; working tree was clean at check start).

---

## Evidence per check

### 0.1 — Disposition merged — PASS

```
$ git merge-base --is-ancestor feature/cap-shadow_campaign main
cap-shadow_campaign: REACHABLE from main
$ git merge-base --is-ancestor feature/cap-fact_auto_emit main
cap-fact_auto_emit: REACHABLE from main
$ test -f docs/experiments/results/cap_shadow_fact_disposition.md && echo EXISTS
EXISTS
```

`main`'s history reaches both workstream branches. The disposition doc
(`docs/experiments/results/cap_shadow_fact_disposition.md`) records the fact-flow evidence: the
`applied`-marker problem, 27 KB artifacts + 27 registry rows, and idempotency re-derived to
0 records.

**Marker in code:** `src/agentic_dynamics/control/rules.py` records shadow decisions with an
explicit `applied: False` stamp so the record body is self-describing
(`rules.py:400-406`): a shadow decision is *recorded + surfaced, never applied*.

**Tests asserting it (all pass):**
```
$ python3 -m pytest tests/test_context_plane_seam.py::test_shadow_bookkeeping_records_the_applied_flag \
    tests/test_context_plane_seam.py::test_shadow_decision_carries_applied_false_marker \
    tests/test_actuation_ingestion.py::test_real_actuation_record_does_not_carry_applied_marker -q
...  [100%]
3 passed
```

### 0.2 — FINOPS_KB_WRITE — PASS

```
$ echo "FINOPS_KB_WRITE=[${FINOPS_KB_WRITE}]"; env | grep FINOPS | sort
FINOPS_KB_WRITE=[1]
FINOPS_CELL_ID=wf_cap_fact_backfill_deepseek_deepseek_v4_flash
FINOPS_KB_WRITE=1
```

The env var is **set** by the operator (not by this workflow). Note: `p4_run_backfill` sets it
only for the emit step as its own hard rule; derivation stays pure.

### 0.3 — Gate migration merged — PASS

```
$ grep -rn "requires_facts:" workflows/ experiments/definitions/
workflows/repository/cap_routing_evidence_specs.yaml:101,118   requires_facts: attempt_confidence, ...
experiments/definitions/routing_regret_under_degradation.yaml:44  requires_facts: [{fact: max_spend_usd, ...}]
experiments/definitions/cap_confidence_cascade.yaml:183-310       requires_facts: (10 entries)
experiments/definitions/cap_shadow_comparison.yaml:172-268        requires_facts: (7 entries)
experiments/definitions/cap_grit_strength_grid.yaml:186-263       requires_facts: (8 entries)
```

The `requires_facts` migration is live in both `workflows/` and `experiments/definitions/`.
`validate_fact_contracts` (R1-R11, `src/agentic_dynamics/core/contracts.py:236`) composes into
the real spec gate via `control.context_compiler.validate_spec_fact_contracts` (real
`FACT_PREDICATES`/`REDUCERS`/committed contracts).

**Spot-check 3 migrated specs through the real gate — 0 errors each:**
```
$ python3 -c "... validate_spec_fact_contracts(load_spec(p)) ..."
cap_confidence_cascade.yaml     -> PASS (0 errors)
cap_shadow_comparison.yaml      -> PASS (0 errors)
cap_coverage_routing_impact.yaml -> PASS (0 errors)
```

### 0.4 — Routing evidence specs — PASS

The four E1-E4 routing evidence YAMLs exist in `experiments/definitions/` and compile:

```
$ for f in cap_shadow_comparison cap_confidence_cascade cap_coverage_routing_impact cap_grit_strength_grid; do
    test -f experiments/definitions/$f.yaml && echo "EXISTS: $f"; done
EXISTS: cap_shadow_comparison      # E1 — shadow-record comparison
EXISTS: cap_confidence_cascade     # E2 — retrospective confidence-gated cascade
EXISTS: cap_coverage_routing_impact  # E3 — coverage-corrected vs legacy routing impact
EXISTS: cap_grit_strength_grid     # E4 — live story grid (perturbation_strength × condition × arm)

cap_shadow_comparison:      load=OK baseline_errs=[] gate_errs=[] 7-phase DAG
cap_confidence_cascade:     load=OK baseline_errs=[] gate_errs=[] 7-phase DAG
cap_coverage_routing_impact: load=OK baseline_errs=[] gate_errs=[] 7-phase DAG
cap_grit_strength_grid:     load=OK baseline_errs=[] gate_errs=[] 7-phase DAG
```

Each loads, baseline-validates clean, passes the real fact-contract gate with **0 refusals**,
and `compile_spec` produces the full DAG: validate → cells → execute → measure → compare →
writeup → adapt.

### 0.5 — Addendum merged — PASS

```
$ test -f src/agentic_dynamics/control/profiles.py && echo "profiles.py: EXISTS"
profiles.py: EXISTS
$ test -f experiments/contexts/session_routing.yaml && echo "session_routing.yaml: EXISTS"
session_routing.yaml: EXISTS
$ grep -n '"pattern"' src/agentic_dynamics/control/facts.py
src/agentic_dynamics/control/facts.py:663:    "pattern": PredicateSpec(
```

`FACT_PREDICATES["pattern"]` (`facts.py:663-674`) is the addendum's I9 entry: typed
`PatternPayload` body, `produced_by=("pattern/v1",)`, workload-scoped, inheritable, derived
authority — a real reducer-backed predicate, never an LLM fabrication. The I8 profile machinery
(`control/profiles.py`) declares predicate/policy/pattern references for session routing, and
the I10 `session_routing` contract lives at `experiments/contexts/session_routing.yaml`.

**Addendum + gate suites green:**
```
$ python3 -m pytest tests/test_context_plane_profiles.py tests/test_context_plane_contracts.py \
    tests/test_context_plane_seam.py tests/test_actuation_ingestion.py -q
84 passed
```

---

## Stage 0 verdict

**5/5 PASS.** All five prerequisites are merged and live with command-shown evidence. No guard
trip; the workflow proceeds to Stage 1 (`p1_corpus_inventory`). In-flight worktrees and
branches were not touched (working tree clean at check start; no diffs involving the four
in-flight workstreams).
