---
status: accepted
---

# Stage 1 verification — modular monorepo package move

**Phase `retire_shim` of `consolidation_stage_1_package_move.yaml`** — verifies the whole
Stage 1 (skeleton → move → rewrite_consumers → dependency_lint → retire_shim) against the four
acceptance metrics the spec declares (`imports_resolve`, `dependency_lint_green`,
`deprecated_retired`, `bootstrap_centralized`) and the standing gates.

**Provenance:** [M] measured this phase (pytest output, `grep`/`ls` ground truth); [C] computed
from the tree; [P] policy invariants; [X] the critique (`docs/review/semantic_monolith_review.md`).

---

## 1. `imports_resolve` — the shim is gone and every import resolves natively

- `grep -rE "from instrument|import instrument" scripts/ admin/ tests/ src/` → **0 matches**
  (the shim is deleted, so there is no "outside the shim" exception any longer). [M]
- `grep -rE "agentic_dynamics.legacy" scripts/ admin/ tests/ src/` → 0 matches. [M]
- `pytest tests/ -m "not external"` → **1183 passed, 106 deselected**. [M]

**Result: PASS.**

## 2. `dependency_lint_green` — the rec-8 graph lint + data-flow guards

- `tests/test_dependency_direction.py` — 8 forbidden-edge assertions + the 2 pinned
  execution→control edges (`workflow_runner→step_routing/live`; `opencode`/`claude_adapter`→`live`)
  as the *complete* tier-1→tier-2 set. Demonstrably red on an injected forbidden edge. [M]
- `tests/test_data_flow.py` — `retrieval.py` references `publish_event` zero times and
  hard-excludes `Authority.POLICY`; knowledge modules never import/call
  `derive_actuation_record`. [M]

**Result: PASS (12/12).**

## 3. `deprecated_retired` — rec 7 (delete, don't merely label)

Deleted (git history preserved): [M]

- `src/instrument/` — the entire compat shim (barrel + 63 stubs + `CONTEXT.md`).
- `src/agentic_dynamics/legacy/` — all 5 dead modules (`experiment`, `adapter`, `lab_book`,
  `recovery`, `trajectory`) + `__init__.py`.
- `scripts/plan.py`, `scripts/analyze_with_ollama.py`, `scripts/analyze_with_opencode.py`,
  `scripts/build_graph.py`, and the 8 `scripts/lab_*_DEPRECATED_bge_m3.py`.
- `tests/test_adapter.py`, `tests/test_recovery.py`, `tests/test_trajectory_embedding.py`.

Final active package: **59 modules across 8 planes** (core 5 · experiment 3 · measurement 15 ·
runtime 4 · adapters 3 · knowledge 16 · control 9 · reporting 4). `legacy/` and the shim are gone.

**Result: PASS.**

## 4. `bootstrap_centralized` — one `scripts/_bootstrap.py`

- 50 per-file `sys.path.insert(.../src)` bootstraps replaced by `import _bootstrap` (a robust
  try/except so it works both direct-run and as `scripts.<name>`). [M]
- `scripts/_constants.py` moved → `agentic_dynamics/core/constants.py`, importers updated. [M]
- `python scripts/run.py --help`, `python scripts/spec_status.py --dry-run`,
  `python scripts/generate_manifest.py`, and `from scripts import registry` all smoke-clean. [M]

**Result: PASS.**

## 5. Standing gates

- **Compile-gate validate** on all 77 `experiments/specs/*.yaml` — `validate_spec` +
  `validate_rules` (the `requires`/`produces` gate) → **0 errors**. [M]
- **Full non-external suite** green at the phase boundary. [M]

**Result: PASS.**

---

## Final result

| # | Metric | Result |
|---|---|---|
| 1 | `imports_resolve` | PASS |
| 2 | `dependency_lint_green` | PASS |
| 3 | `deprecated_retired` | PASS |
| 4 | `bootstrap_centralized` | PASS |

**Overall: PASS — 4/4.** Stage 1 (the crux package move) is complete and gate-green; S2 may
proceed.
