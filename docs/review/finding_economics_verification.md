---
status: accepted
---

# Finding-Economics Closure — Verification Report

**Provenance [C]:** computed from the closure's own execution log (phases f1–f5 on branch
`feature/finding-economics`) and re-executed gates. This is the release gate for the
finding-economics closure: it proves every finding in
`docs/review/finding_economics_review.md` is addressed (zero orphans) and re-runs the full
test/guard/compile/reproduce/invariant surfaces, then signs off on finding-corpus economics,
exact contributor attestation, and public semantic consistency.

## 1. Coverage proof — every review finding → a phase → PASS

| Finding | Severity | Phase | Status |
|---|---|---|---|
| Public finding corpus treats uncaptured cost/energy as real zeroes — `_finding_entry_from_run` coerces `cost_usd`/`energy_j`/`escape_score`/… to `0.0`, `narration_failure=False`, `correctness_per_dollar = correctness / max(cost, 1e-9)` (published `857,142,857` for claude-haiku), ten `"?"` strategy classifications, and `compute_routing` defaults missing cost/correctness to zero | P0 | f1 | **PASS** — finding adapter routes all 8 economic/optional fields through `MeasurementCoverage`/`cost_coverage` (`_optional_economic`/`_opt_float`); `correctness_per_dollar`/`avg_quality_per_joule` null unless the denominator is captured AND positive; `narration_failure` is `None`; strategy distribution labels the ten unknowns `"unknown"`; routing treats cost-/outcome-unavailable as `UNAVAILABLE`. Guard `tests/test_finding_economics.py` |
| Contribution contracts do not bind the exact contributor set — `attach_contribution` discards `used_record_ids`; `record_id()` returns only the entity id so a story and its analysis collide | P1 | f2 | **PASS** — table-qualified refs `story|review|finding:<entity_id>:<knowledge_id>` / `analysis:<story_entity_id>:<content_digest>`; `record_id()` table-qualified; `ContributionReport.of` rejects empty/duplicate refs, negative counts, unknown reasons; `used_record_refs_sha256`/`excluded_record_refs_sha256`/`used_unique_records`/`used_contributions` hashed into the v6 contract. Guard `tests/test_contribution_report.py` |
| `sync_data --check` does not verify actual Parquet contents — reads only row counts, so a modified value with an unchanged count passes | P1 | f3 | **PASS** — `_actual_rows_hash` reads the Parquet back through its typed schema and hashes the rows with the same canonical encoding; `check()` enforces three-way parity `expected == sidecar == actual`. Guard `tests/test_sync_data.py::test_check_detects_a_modified_parquet_value` |
| Four metric definitions changed without version bumps — `condition_effects/v1`, `quality_frontier/v1`, `story_review/v1`, `verification_frontier/v1` still at v1 | P2 | f4 | **PASS** — all four bumped to v2 in `lab_manifest.json` (rationales updated), artifacts regenerated, `data.js` rebuilt |
| Generator source-tree identity not fully transitive — relative imports unresolved; `path.name` + bytes makes two `__init__.py` indistinct | P2 | f4 | **PASS** — `_source_closure` resolves `from .x`/`from ..x` against the importing package; `_source_tree_identity` hashes repo-relative path + length + bytes. Guard `tests/test_build_data.py::test_source_closure_resolves_relative_imports` + `test_source_tree_identity_changes_when_init_py_package_renamed` |

**Zero orphans:** all 5 findings map to a phase and PASS. The f5 adversarial hunt additionally
found and fixed one defect outside the review's own list (see §2.5): the same
ratio-denominator floor class in `measurement/strategy.py` (`exploration_premium` /
`thermal_efficiency`), guarded by `tests/test_strategy.py`.

## 2. Re-run results

### 2.1 Full suite

`pytest tests/ --ignore={test_embeddings,test_graph,test_knowledge_stream,test_ollama_analyzer,test_opencode_analyzer}.py`
→ **1517 passed, 0 failed**. The five excluded files are external-service suites (Ollama,
Neo4j, ChromaDB, live opencode) whose services are not running in this environment; they are
unrelated to the finding-economics closure and gated by the `external` marker by design.

### 2.2 Guard suites (all green)

`tests/test_finding_economics.py` (9), `tests/test_contribution_report.py` (15),
`tests/test_sync_data.py` (8), `tests/test_strategy.py` (4), `tests/test_routing.py` (8),
`tests/test_lab_contract.py`, `tests/test_lab_outputs_canonical.py`,
`tests/test_lab_manifest.py`, `tests/test_build_data.py` (32),
`tests/test_publication_singular_door.py`, `tests/test_experiment_workflow_classification.py`,
`tests/test_doc_lifecycle.py` → **230 passed, 0 failed**.

### 2.3 Compile-gate — all specs

`load_spec → validate_spec → validate_rules → compile_spec` over
`experiments/definitions/*.yaml` + `workflows/**/*.yaml` → **83 specs scanned, 0 load /
validate / requires-produces / compile errors**.

### 2.4 Reproduce core dry-run + container core

`scripts/reproduce.sh --dry-run` → prints the deterministic core (8 canonical labs, no external
services), PASS. The container core (inventory → sync → labs → `build_data` → `generate_manifest`)
has been re-run across f1–f5: the 8 lab artifacts, `data.js`, the Parquet tables, and
`data_manifest.json` are all regenerated and consistent (registry identity stable at 701 rows;
`data.js` hash current).

### 2.5 Adversarial hunt (f5) residue

The expression-variant sweep found one same-class residue outside the review's list —
`measurement/strategy.py`'s `exploration_premium = novelty * correctness / max(cost, 0.0001)`
and `thermal_efficiency = correctness / max(energy, 0.01)`. Fixed to compute only when the
denominator is captured (`> 0`); guard `test_economic_ratios_null_when_denominator_uncaptured`.
All other `or 0`/`or 0.0` hits are sums (0.0 is the additive identity) or count defaults in
retired/operational paths; no published `"?"` identity remains.

### 2.6 Invariant audit

| Invariant | Status |
|---|---|
| Redis isolation — framework queue on `FINOPS_REDIS_PORT` 6380, never the 6379 story sandbox | **PASS** |
| Firebase dual-host — `.firebaserc` carries `ai-finops-rulebook` (canonical) + `agentic-dynamics` (mirror) | **PASS** |
| CAP frozen — no commit on the branch touches `experiment_spec.py` / `compile_experiment.py` | **PASS** |

## 3. Verdict

**Finding-corpus economics: YES** — the single-task finding corpus now publishes the same
null-with-coverage honesty the story and lab paths enforce; economic ratios are nullable; routing
never models an unmeasured economics as free execution.

**Exact contributor attestation: YES** — every canonical lab contract carries the
table-qualified ref digests (`used_record_refs_sha256` / `excluded_record_refs_sha256`) and the
unique/contribution counts, recomputed and verified against a fresh resolver pass.

**Public semantic consistency: YES** — `data.js` reconciles with the README `By the Numbers`
block and the canonical registry; the four bumped metric versions are consistent in manifest and
artifacts; the transitive generator source-tree identity is current.

**CAP fact-authority readiness:** follows — the f2 table-qualified ref + content-digest contract
is the CAP fact-lineage primitive, and the compiler (CAP) is unchanged (frozen) throughout.

**Overall: PASS.**
