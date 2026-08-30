---
status: accepted
---

# Canonical-Publication Closure — Verification Report

**Provenance [C]:** computed from the release's own execution log
(`docs/release/consolidation/execution_log.md` §"Canonical publication closure") and re-executed gates
against the tree at the release commit. The citable input is
`docs/reviews/canonical_publication_review.md` (external critique of `ec66947d5`); this file maps
every finding in that review to a closure phase, re-runs the gates, and records the verdict.

## 1. Coverage — every finding maps to a phase with a PASS

| Finding (severity) | Phase(s) | Result |
|---|---|---|
| P0 — the labs use the resolver but the primary story/review/analysis path still globs raw dirs (bad_seed 41 / early_degrade 91 contradiction in `data.js`) | `c1_canonical_tables` | **8/8 PASS** |
| P1 — resolver completeness is not measured or enforced (10 payload-less rows silently skipped) | `c2_resolution_fail_closed` | **9/9 PASS** |
| P1 — the lab contract validates freshness, not semantic identity (grit/v0 accepted against manifest grit/v1) | `c3_contract_semantic` | **9/9 PASS** |
| P2 — the registry hash does not attest to exact payload content | `c3_contract_semantic` | **9/9 PASS** |
| P2 — `n_input_records` does not mean records used (279 resolved vs 144 used) | `c4_record_scopes` | **8/8 PASS** |
| smaller — test-count fields conflate scopes (`tests_total` vs `tests_passed`/`tests_run`) | `c5_test_scope_names` | **5/5 PASS** |
| smaller — README figures unreconciled (1,097 / 36 / $288.69 vs 1,067 / 35 / $309.17) | `c6_readme_site_reconcile` | **7/7 PASS** |
| smaller — Docker persistence overstates (manifest outside the mounts; CI verifies data.js only) | `c6_readme_site_reconcile` | **7/7 PASS** |

Every P0/P1/P2/smaller finding is resolved by a passing phase — **zero orphans**. No finding is
deferred (unlike the semantic-integrity release, which explicitly deferred the neutral-intent
schema; this review has no such item).

## 2. The singular publication boundary — condition split assertion

The release's load-bearing claim, asserted directly (and guarded permanently in
`tests/test_publication_singular_door.py::test_data_js_story_conditions_match_the_canonical_split`):

- `data.js` `stories.conditions` carries **exactly two arms, each exactly once**: `clean 135` and
  `early_degrade 80`.
- **No `bad_seed 41` arm**, **no `early_degrade 91` arm** — the legacy semantics the review found
  are gone.

| Check | Result |
|---|---|
| `stories.conditions` == `[clean 135, early_degrade 80]`, each exactly once | **PASS** |
| `bad_seed 41` absent | **PASS** |
| `early_degrade 91` absent | **PASS** |

## 3. Re-executed gates

| Gate | Command | Result |
|---|---|---|
| Full test suite | `pytest tests/ -q` | **1538 passed, 1 skipped** |
| Guard suites (15 files) | stale-path, agent_config semantic, render, lab contract, lab manifest, lab-outputs-canonical, data-integrity, dependency-direction, doc-lifecycle, script-classification, experiment-workflow-classification, kb-produce-registry, data-flow, publication-singular-door, build-data | **220 passed** |
| Compile-gate all specs | `load_spec` + `compile_spec` over `experiments/definitions/*.yaml` + `workflows/**/*.yaml` | **80/80 compile, 0 fail** |
| reproduce core — dry-run | `scripts/reproduce.sh core --dry-run` | **exit 0** (8 canonical labs, `--no-tests --no-sonar`) |
| Docker build | `docker build -t agentic-dynamics .` | **success** |
| Container core run (fixture) | `docker run --rm -v …apps/website -v …data_manifest.json agentic-dynamics` | **exit 0** — `data.js` 116,193 bytes; manifest regenerated (`generated_at` advanced, `files.data.js.sha256` matches the rebuilt `data.js`) |

The container core run surfaced one defect that was fixed in this phase: the Docker image did not
carry `experiments/waivers/unresolved_payloads.json`, so the fail-closed gate aborted inside the
container. `Dockerfile` now `COPY`s `experiments/waivers/`; the CI gate (`.github/workflows/
pytest.yml`) mounts the manifest and asserts it regenerates.

## 4. Invariant audit

| Invariant | Check | Result |
|---|---|---|
| Redis isolation | framework queue lives on `FINOPS_REDIS_PORT` (default **6380**); never 6379 (story agents' `finops-redis`) | **PASS** — `enqueue.py`/`worker.py`/`monitor.py`/`live.py`/`queue_reinterleave.py` all default 6380 |
| Firebase dual-host | `apps/website/.firebaserc` names both `ai-finops-rulebook` (default) + `agentic-dynamics`; `firebase.json` `public: "."` | **PASS** |
| CAP frozen-not-implemented | the reserved homes (`facts.py`, `reducers/`, `context_compiler.py`, `contracts.py`, `rules.py`/`validator.py`/`decisions.py`) exist and contain *no code* (`# reserved for CAP I<n>` only) | **PASS** |
| No retired summary in publication input | no canonical (publication-eligible) lab reads `_results_summary.json` | **PASS** — the only mentions are "does not read" docstrings; `test_lab_manifest.py` enforces it |
| Canonical lab lineage | `build_data.py` rejects a lab whose contract's semantic fields, registry hash, or content hash drift | **PASS** — `test_lab_contract.py` + `test_lab_outputs_canonical.py` + `test_build_data.py` green |
| Publication fail-closed | an unresolved current row without a waiver aborts `build_data.py` | **PASS** — `test_build_data.py::test_fail_closed_on_unwaivered_missing_row` + the container run above |

## 5. Final verdict

**PASS — semantic-integrity signoff: YES.** Every P0/P1/P2/smaller finding of
`docs/reviews/canonical_publication_review.md` is resolved by a passing closure phase (c1–c6), with
zero orphans and zero deferrals. `data.js` carries the canonical condition split (clean 135 /
early_degrade 80) exactly once with no legacy `bad_seed`/`early_degrade-91` arm. Full suite green
(1538 passed, 1 skipped), every guard suite green (220 passed), 80/80 specs compile, the
reproduction container runs the core pipeline to a published `data.js` *and* a regenerated
manifest, and every invariant audit check passes. The publication boundary is singular: one
canonical door (`load_canonical_tables`), one lineage to `data.js`.
