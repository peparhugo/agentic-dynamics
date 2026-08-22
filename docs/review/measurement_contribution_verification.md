---
status: accepted
---

# Measurement-Contribution Closure — Verification Report

**Provenance [C]:** computed from the closure's own execution log (phases m1–m6 on branch
`feature/measurement-closure`) and re-executed gates. This is the release gate for the
measurement-contribution closure: it proves every finding in
`docs/review/measurement_contribution_review.md` is addressed (zero orphans) and re-runs the
full test/guard/reproduce/compile/container surfaces, then signs off on canonical metric
correctness and public semantic consistency.

## 1. Coverage proof — every review finding → a phase → PASS

| Finding | Severity | Phase | Status |
|---|---|---|---|
| `lab_verification_value` publishes a contaminated correlation (`stories.get(sid, ("?", 0))`) | P0 | m1 | **PASS** — join fails explicitly; `review_without_current_story` + `story_without_review`; `verification_value/v2`; guard `test_verification_value_join_publishes_no_placeholder_identity` |
| Cost denominator policy inconsistent across outputs | P1 | m2 | **PASS** — shared `MeasurementCoverage` primitive + `cost_captured` + `cost_coverage`; guard `test_canonical_producers_have_no_zero_coercion` |
| Record-scope contracts explicit but not proven against computation | P1 | m3 | **PASS** — typed `ContributionReport`; `result, contribution = compute(...)`; guard `test_contract_reconciles_with_recomputed_contribution` |
| Static registry fallback text stale ("225/215/10/77", "Every token … is measured") | P1 | m4 | **PASS** — `contaminated_tombstones 77 / no_measurement_tombstones 10 / tombstones_total 87`; static-fallback guard; coverage-honest prose |
| Null-versus-zero fixed for LSP but not generalized | P2 | m2 | **PASS** — `build_data` solution/basin + `lab_quality_frontier` + `lab_story_review` correctness all captured-only/null |
| Tombstone history contains a contradictory "current" predecessor | P2 | m4 | **PASS** — terminal-tombstone semantics in compaction; guard `test_compact_registry_index_terminal_tombstone_supersedes_earlier_open_version` |
| Publication source identity incomplete | P2 | m4 | **PASS** — `metric_source_sha256` on every contract; `generator_source_tree_identity` derived from the import graph; guard `test_data_js_generator_source_tree_identity_is_current` |
| `sync_data --check` is not full parity | P2 | m4 | **PASS** — `sessions_rows_sha256` / `stories_rows_sha256` / `sync_transform_sha256` / `schema_sha256`; recomputed in `--check`; guard in `test_sync_data.py` |
| Branch protection covers only the `test` job | P3 | m6 | **PASS** — `main` now requires `test`, `repro`, and `packaging` (applied via `gh api`) |

**Zero orphans:** all 9 findings map to a phase and PASS. The m5 adversarial hunt additionally
found and fixed two defects outside the review's own list (see §2.2): `sync_data.py`'s residual
zero-coercion class, and a stale `generator_source_tree_identity` in `data.js`.

## 2. Re-run results

### 2.1 Full suite

`pytest tests/` → **1592 passed, 1 skipped, 0 failed** (the 1 skip is an optional Neo4j-dependent
fixture; external-service tests are gated by the `external` marker and excluded in CI by design).

### 2.2 Guard suites (all green)

| Suite | Result |
|---|---|
| `test_measurement_coverage.py` — zero-coercion class + primitive | PASS (incl. `sync_data.py` in the producer surface) |
| `test_contribution_report.py` — contract == recomputed contribution | PASS |
| `test_static_fallback_guard.py` — data-stat/meta/OG == generated stats | PASS |
| `test_static_narrative_guard.py` — retired figures absent | PASS |
| `test_lab_contract.py` — semantic identity + `metric_source_sha256` | PASS |
| `test_lab_outputs_canonical.py` — canonical derivation path | PASS |
| `test_generate_manifest.py` — tombstone/compaction semantics | PASS |
| `test_sync_data.py` — sidecar content hashes | PASS |

### 2.3 Compile-gate all specs

`test_committed_specs_all_load_without_unknown_key_warnings` → **PASS** (all 82 committed specs
load clean). The closure's own spec was re-homed from `experiments/specs/` to
`workflows/repository/measurement_contribution_closure.yaml` with `artifact_kind: workflow`, and
compiles (`valid: true`, 7-phase DAG). `test_experiments_specs_flat_dir_is_drained` now passes.

### 2.4 Reproduce core dry-run + container core run

- `bash scripts/reproduce.sh --dry-run` → **PASS** (8-lab core set + all 7 steps dispatched).
- `docker build -t agentic-dynamics:release-gate .` → **PASS**.
- Container CORE run (`ENTRYPOINT reproduce.sh core`, mounted website + manifest) → **PASS**:
  produced `data.js` (133,181 bytes) and regenerated `data_manifest.json` (701-entity registry
  preserved; `generated_at` advanced) — reproducing the `repro` CI gate.

### 2.5 Invariant audit

| Invariant | Result |
|---|---|
| Redis isolation (framework queue on 6380, story-agent sandbox on 6379) | **PASS** — all producers read `FINOPS_REDIS_PORT` (default 6380); `kb_produce_sources.py` explicitly "never touches 6379 nor DB 1" |
| Firebase dual-host (canonical `ai-finops-rulebook` + mirror `agentic-dynamics`) | **PASS** — `.firebaserc` carries both projects; never drifted |
| CAP frozen (no consensus/fact-authority implementation) | **PASS** — `core/contracts.py`, `control/{validator,context_compiler,facts,rules}.py`, `control/reducers/` all reserved/empty per `ARCHITECTURE.md` §4 |

## 3. Branch protection

`gh` authenticated; applied `PATCH …/branches/main/protection/required_status_checks` →
`contexts: ["test", "repro", "packaging"]`. Verified via
`GET …/branches/main/protection` (checks: `test`, `repro`, `packaging`).

## 4. Final verdict

**Canonical metric correctness: PASS.** Every canonical lab's contract is now derived from a
typed `ContributionReport` the computation itself returns; every lab's join reconciles against its
artifact (guard: `test_contract_reconciles_with_recomputed_contribution`); the "?" placeholder
class, the missing-as-zero class, and the missing-as-`"?"` class are all guarded as unrepresentable;
tombstones are terminal.

**Public semantic consistency: PASS.** Static `data-stat` fallbacks and meta/OG text equal the
generated `public_statistics`/`summary` exactly (guard: `test_static_fallback_guard.py`); the
tombstone population is split into contaminated (77) vs no-measurement retractions (10) and
described honestly; the "Every token … is measured" overclaim is replaced with coverage-honest
prose; `data.js`'s publication contract (registry identity, resolved-input identity, waiver digest,
normalization version, and derived generator-source-tree identity) verifies against the current
manifest.

**Signoff: canonical metric correctness YES · public semantic consistency YES.** CAP
fact-authority readiness follows (its implementation remains frozen, per the review).
