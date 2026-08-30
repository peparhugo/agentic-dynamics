---
status: accepted
---

# Stage 6 — gates (acceptance tests + compile gate + invariant audit)

**Phase `gates` of `consolidation_stage_6_verification_release`.** Runs every stage-specific
acceptance test in one pass, the compile-gate validate over every committed spec, and the invariant
audit (Redis isolation, dual Firebase, CAP frozen-not-deleted, no `_results_summary.json`
resurrection).

**Provenance:** [M] measured this phase (pytest output, `grep`/config ground truth); [P] policy
invariants (`docs/release/consolidation/stage_map.md` §7).

---

## 1. Stage-specific acceptance tests (one pass)

```
tests/test_doc_lifecycle.py                       5 passed
tests/test_dependency_direction.py                9 passed
tests/test_experiment_workflow_classification.py  3 passed
tests/test_script_classification.py               2 passed
tests/test_generated_surfaces_match.py            2 passed
tests/test_data_flow.py                           3 passed
                                                  ———
                                                  24 passed
```

**Result: PASS — 24/24 guard tests green.**

## 2. Compile gate — every committed spec

`validate_spec` + `validate_rules` (the `requires`/`produces` gate) over all 77 specs under
`experiments/definitions/` + `workflows/**`:

```
77 specs validated; 0 refusals.
```

**Result: PASS — the load-bearing rule is intact end-to-end.**

## 3. Invariant audit

### Redis isolation (6380 queue DB1 / KB DB2; 6379 sandbox)

- Framework queue: `FINOPS_REDIS_PORT` default **6380**, `FINOPS_REDIS_DB` default **1**
  (`scripts/worker.py`, `scripts/monitor.py`, `scripts/enqueue.py`,
  `agentic_dynamics/control/live.py`). [M]
- KB stream: `agentic_dynamics/knowledge/knowledge_stream.py` — port **6380**, `FINOPS_KB_DB`
  default **2**, and the docstring states "Never port 6379 — the story-agent Redis on 6379 is a
  test sandbox". [M]

**Result: PASS.**

### Dual Firebase

`firebase/.firebaserc` → `{"projects": {"default": "ai-finops-rulebook",
"agentic-dynamics": "agentic-dynamics"}}` — both projects present. [M]

**Result: PASS.**

### CAP frozen-not-deleted

`workflows/repository/context_abstraction_implement.yaml` exists, `status: draft`, PAUSED note
present (2 matches) — not deleted, not superseded. [M]

**Result: PASS.**

### No `_results_summary.json` resurrection

- `scripts/build_data.py` (the website build — the live publication path) **does not read**
  `_results_summary.json` (grep = zero). [M]
- `scripts/analyze_worktrees.py` is the writer (regenerates the summary from the clean re-runs,
  per `docs/verification/data_integrity_findings.md`). [M]
- The data-integrity regression guards (`tests/test_data_integrity.py`) are green in the full
  suite. [M]

**Result: PASS.**

## 4. Full suite

`pytest tests/ -m "not external"` → **1189 passed, 106 deselected**. [M]

**Result: PASS.**

---

## Final result

| # | Gate | Result |
|---|---|---|
| 1 | Stage-specific acceptance tests (24 guard tests, one pass) | PASS |
| 2 | Compile gate (77 specs, 0 refusals) | PASS |
| 3 | Redis isolation (6380 queue DB1 / KB DB2; 6379 sandbox) | PASS |
| 4 | Dual Firebase (.firebaserc both projects) | PASS |
| 5 | CAP frozen-not-deleted | PASS |
| 6 | No `_results_summary.json` resurrection (build_data.py clean) | PASS |
| 7 | Full suite green | PASS |

**Overall: PASS — 7/7 gates green.**
