---
status: accepted
---
# Consolidation execution log

Per-stage acceptance-criterion results for the consolidation release (S0–S6). Each entry records
PASS/FAIL against the stage's acceptance criteria (`docs/consolidation/stage_map.md` §4) and the
per-phase deliverables (`experiments/specs/consolidation_stage_*.yaml`).

---

## S0 — architecture spine (phase `spine`)

Spec: `experiments/specs/consolidation_stage_0_architecture_spine.yaml` · phase `spine`.
Deliverable: root `ARCHITECTURE.md`.

| # | Acceptance criterion | Result |
|---|---|---|
| 1 | `ARCHITECTURE.md` exists at the repo root (exactly one) | PASS |
| 2 | Six sections present: §1 Planes, §2 Package boundaries, §3 Dependency direction, §4 Implemented vs proposed, §5 Canonical execution loop, §6 Supersession map | PASS |
| 3 | §1 lists the eight bounded packages + one-line ownership, mapped to the critique's six systems | PASS |
| 4 | §2 states import may/may-not boundaries and points at `tests/test_dependency_direction.py` (to be added in Stage 1) | PASS |
| 5 | §3 draws the spine `core ← experiment/measurement/runtime/knowledge ← control ← applications` with the two pinned execution→control observation edges (`workflow_runner→step_routing/live`; `opencode/claude_adapter→live`) as observe-only arrows | PASS |
| 6 | §4 names the shipped planes, the reserved-but-empty CAP homes (I0–I7 → `control/*` + `core/contracts.py`), the deferred workstreams (WS-02..08), and names `docs/consolidation/stage_map.md` as the release plan | PASS |
| 7 | §5 states the canonical execution loop (spec → compile → DAG → cells → jobs → attempts → ledger → information → policy → grid → campaign) | PASS |
| 8 | §6 maps supersession: replaces BLUEPRINT×3 + dated handoffs + superseded reviews; leaves mental-model, `src/instrument/CONTEXT.md`, `scripts/CONTEXT.md`, `data_integrity_findings.md`, `docs/review/` authoritative | PASS |
| 9 | The load-bearing rule is stated verbatim as the architectural invariant, not redefined | PASS |

**S0-spine result: 9/9 PASS.**

---

## S0 — doc lifecycle (phase `lifecycle`)

Spec: `experiments/specs/consolidation_stage_0_architecture_spine.yaml` · phase `lifecycle`.
Deliverables: migrated doc tree (`docs/archive/`, `docs/designs/{current,implemented}/`),
status front-matter on every remaining doc, `tests/test_doc_lifecycle.py`.

| # | Acceptance criterion | Result |
|---|---|---|
| 1 | `BLUEPRINT.md`, `BLUEPRINT_v2.md`, `BLUEPRINT_v3.md` moved → `docs/archive/` with `status: superseded` + `superseded_by: ARCHITECTURE.md` | PASS |
| 2 | Dated handoffs (`docs/HANDOFF_2026-08-17.md`, `docs/HANDOFF_2026-08-19.md`) moved → `docs/archive/` (superseded) | PASS |
| 3 | Dated `code_reviews/*` predating the registry repoint moved → `docs/archive/` (superseded, kept not deleted) | PASS |
| 4 | Current-but-frozen designs → `docs/designs/current/` with `status: accepted` (context-abstraction design+verify, `supervisor_design.md`, spec/compiler roadmap `2026-08-14_*`) | PASS |
| 5 | Shipped designs → `docs/designs/implemented/` with `status: implemented` + `implemented_by:` (canonical-state rounds, RAG seam split, website repoints) | PASS |
| 6 | Status front-matter added to every remaining root + docs markdown file (vocabulary `proposed|accepted|implementing|implemented|superseded|abandoned`) | PASS |
| 7 | `tests/test_doc_lifecycle.py` written — walks `docs/**` + root `*.md`, asserts status field + `docs/archive/` superseded | PASS |
| 8 | `pytest tests/test_doc_lifecycle.py` green | PASS (5 passed) |
| 9 | No `BLUEPRINT*.md` remains at the repo root | PASS |

**S0-lifecycle result: 9/9 PASS.**

---

## S0 — CAP freeze (phase `freeze`)

Spec: `experiments/specs/consolidation_stage_0_architecture_spine.yaml` · phase `freeze`.
Deliverables: PAUSED marker on `context_abstraction_implement`, reserved CAP homes declaration,
refreshed spec index.

| # | Acceptance criterion | Result |
|---|---|---|
| 1 | `context_abstraction_implement.yaml` marked PAUSED (freeze_reason `consolidation_release/stage_map`, resume_after `consolidation S6`) — not deleted, not superseded (`superseded_by` absent) | PASS |
| 2 | Status uses the schema vocabulary only (`status: draft` — the "not runnable now" state); no value outside `{draft,active,superseded,tombstoned}` invented | PASS |
| 3 | `ARCHITECTURE.md` §4 declares the reserved CAP homes (`control/facts.py`, `control/reducers/`, `control/context_compiler.py`, `control/rules.py`, `control/validator.py`, `control/decisions.py`, `core/contracts.py`) as empty-but-reserved placeholders | PASS |
| 4 | Spec index reflects the freeze — `index.json` + `STATUS.md` show `context_abstraction_implement` as `draft`, never `active` | PASS |
| 5 | `docs/consolidation/cap_freeze_note.md` written (durable freeze note: what/why/where/how) | PASS |
| 6 | `validate_spec` passes on the modified spec (status valid, no self-supersession) | PASS |

**S0-freeze result: 6/6 PASS.**

Note: the index was updated with a *targeted* status edit (active → draft in `index.json` +
`STATUS.md`) rather than a full `spec_status.py` regeneration — the run ledgers under
`experiments/results/workflows/` are untracked and absent from this worktree, so a full regen
would have wiped the measured run columns (`last_run`/`ok`/`model`/`cost`/`n_runs`) for all 77
specs. `spec_status.py --dry-run` confirms the derived status is `draft`, so the targeted edit is
consistent with the generator.


