---
status: accepted
---

# Consolidation verification — the release report

**Phase `release` of `consolidation_stage_6_verification_release`.** The capstone: PASS/FAIL across
coverage, gates, invariants, and the synced dual-Firebase deploy. This is the release record for the
consolidation outcome (`docs/release/consolidation/stage_map.md` §1).

**Provenance:** [M] measured this phase (pytest, `grep`, `firebase deploy` output); [P] policy
invariants; [X] the critique (`docs/reviews/semantic_monolith_review.md`).

---

## 1. The release outcome

Per the critique's blunt summary, the consolidation release has one outcome — a structural rehome:

> one architectural spine · clear bounded packages · experiments separated from work orders ·
> one CLI · one instruction source · one current architecture document · old generations
> archived or deleted.

| Outcome | Where | Status |
|---|---|---|
| One architectural spine | `ARCHITECTURE.md` (root) — planes, boundaries, direction, supersession map | ✅ |
| Clear bounded packages | `src/agentic_dynamics/{core,experiment,measurement,runtime,adapters,knowledge,control,reporting}` (60 modules), enforced by `test_dependency_direction.py` | ✅ |
| Experiments separated from work orders | `experiments/definitions/` + `workflows/**`, enforced by `test_experiment_workflow_classification.py` | ✅ |
| One CLI | `agentic-dynamics` (`agentic_dynamics/cli.py`) + script classification (`test_script_classification.py`) | ✅ |
| One instruction source | `agent_config/` → generated `.opencode/` + `.claude/` (`test_generated_surfaces_match.py`) | ✅ |
| One current architecture document | `ARCHITECTURE.md` supersedes BLUEPRINT×3 + dated handoffs (`test_doc_lifecycle.py`) | ✅ |
| Old generations archived or deleted | `docs/archive/`, `docs/designs/{current,implemented}`, retired shim + `legacy/` + dead scripts | ✅ |

## 2. Coverage — 9 recommendations, WS-01..10, six systems

- **9/9 recommendations** → ≥1 stage (`docs/release/consolidation/stage_6_coverage.md` §1). [C]
- **WS-01..10** dispositioned exactly once — folded 3, deferred 7, retired 1 sub-part
  (`stage_6_coverage.md` §2). [P]
- **Six systems** each have a package home (`stage_6_coverage.md` §3). [M]

**Result: PASS.**

## 3. Gates — every stage-specific test, one pass

- **24/24** guard tests green in one pass (`test_doc_lifecycle` 5 · `test_dependency_direction` 9 ·
  `test_experiment_workflow_classification` 3 · `test_script_classification` 2 ·
  `test_generated_surfaces_match` 2 · `test_data_flow` 3). [M]
- **Compile gate** — `validate_spec` + `validate_rules` on all 77 specs → 0 refusals (the
  load-bearing rule intact end-to-end). [M]
- **Full suite** — `pytest tests/ -m "not external"` → 1189 passed, 106 deselected. [M]

**Result: PASS.**

## 4. Invariants

| Invariant | Evidence | Result |
|---|---|---|
| Redis isolation | 6380 queue (DB1) + KB stream (DB2); 6379 story-agent sandbox ("never 6379") | PASS |
| Dual Firebase | `.firebaserc` lists `ai-finops-rulebook` (default) + `agentic-dynamics` (mirror) | PASS |
| CAP frozen-not-deleted | `context_abstraction_implement` `status: draft` + PAUSED, reserved homes in `ARCHITECTURE.md` §4 | PASS |
| No `_results_summary.json` resurrection | `build_data.py` (the website build) does not read it; `analyze_worktrees.py` is the writer | PASS |

**Result: PASS.**

## 5. Dual-Firebase deploy — in sync

From `apps/website/` (the Firebase project directory, `firebase.json` `"public": "."`):

```
=== Deploying to 'ai-finops-rulebook'...  ✔  Deploy complete!  (canonical)
=== Deploying to 'agentic-dynamics'...    ✔  Deploy complete!  (mirror)
```

Both hosts deployed from the same `apps/website/` source in one release — no drift by construction.
The `deploy`/`full_matrix`/`cross_models` pipeline plans now carry `cwd: apps/website` so the
maintained deploy command targets the new location.

**Result: PASS.**

## 6. Self-describing release

- `experiments/specs/index.json` + `STATUS.md` regenerated (77 specs). [M]
- `data_manifest.json` regenerated (registry: 701 entities). [M]

**Result: PASS.**

---

## Final result

| # | Check | Result |
|---|---|---|
| 1 | Release outcome (7 items) | PASS |
| 2 | Coverage (9 recs · WS-01..10 · six systems) | PASS |
| 3 | Gates (24 guard tests · compile gate · full suite) | PASS |
| 4 | Invariants (Redis · Firebase · CAP · data integrity) | PASS |
| 5 | Dual-Firebase deploy in sync | PASS |
| 6 | Self-describing release (index + manifest) | PASS |

**Overall: PASS — the consolidation release is complete and gate-green.** The deferred workstreams
(WS-02..08) and the post-consolidation CAP implementation (I0–I7) now unblock inside the new
structure.
