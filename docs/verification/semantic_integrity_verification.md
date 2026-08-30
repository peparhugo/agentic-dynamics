---
status: accepted
---

# Semantic-Integrity Release — Verification Report

**Provenance [C]:** computed from the release's own execution log
(`docs/release/consolidation/execution_log.md` §"Semantic-integrity release") and re-executed gates
against the tree at the release commit. The citable input is
`docs/reviews/semantic_integrity_review.md` (external critique of `35ef34310`); this file maps
every finding in that review to a release phase, re-runs the gates, and records the verdict.

## 1. Coverage — every finding maps to a phase with a PASS

| Finding (severity) | Phase(s) | Result |
|---|---|---|
| P0 — lab pipeline bypasses the canonical boundary (10 summary-reading labs; split publication path) | `s1_lab_quarantine` | **8/8 PASS** |
| P0 — publication labs lack provenance (contract fields; `build_data` accepts stale lab JSON) | `s2_lab_contract` | **9/9 PASS** |
| P0 — derived outputs rebuilt from canonical records only | `s3_rebuild_outputs` | **10/10 PASS** |
| P0 — Grit has two meanings (`high_grit` quadrant vs `G(s)`) | `s4_grit_resolution` | **9/9 PASS** |
| P1 — specialist agent context still describes the old tree | `s5_agent_context_rewrite` | **10/10 PASS** |
| P1 — stale-path guard does not scan `agent_config/**`; prose not checked semantically | `s6_semantic_context_guards` | **7/7 PASS** |
| P1 — reproduction container built but the full pipeline not exercised | `s7_repro_split` | **7/7 PASS** |
| P1/P2 — agent config not semantically neutral (see §2) | — | **DEFERRED** |
| P2 — `derive_status` treats historical failure as `running` | `s8_lifecycle_backfill` | **6/6 PASS** |
| P2 — Control Room composition root used as a service locator | `s9_control_room_di` | **5/5 PASS** |
| P3 — hygiene (CAP placeholders, README drift, `.scannerwork`, CI pinning) | `s10_hygiene_cap` | **5/5 PASS** |

Every P0/P1/P2/P3 finding is either resolved by a passing phase or explicitly deferred in §2.

## 2. The one deferral — the neutral-intent schema (P1/P2)

The review's P1/P2 finding ("the agent configuration is target-specific but not yet semantically
neutral") is **explicitly deferred, with a pointer**. The required correction is a neutral intent
schema (`role`, `capabilities`: read_repository/execute_tests/edit_code:confirm/spawn_subagents,
`model_class`) with each renderer mapping intent to its platform and refusing generation when an
important capability cannot be represented. It is sequenced **after** the lab contract and the
context guards because it re-touches the renderers — and those are now complete (s2/s5/s6).

- **Pointer:** `scripts/_gen_instructions.py` module docstring ("Deferred — the neutral-intent
  schema (semantic-integrity review P1/P2)") and
  `docs/reviews/semantic_integrity_review.md` § "P1/P2 — The agent configuration is
  target-specific but not yet semantically neutral".
- **Why it does not block this release:** it is a *generation-time* capability guarantee for the
  agent surfaces, not a data-integrity or architecture defect. The context is now canonical (s5/s6),
  the renderers are schema-validated (s6), and the deferral records exactly what remains.

## 3. Re-executed gates

| Gate | Command | Result |
|---|---|---|
| Full test suite | `pytest tests/ -q` | **1505 passed, 1 skipped** |
| Guard suites (all 13) | stale-path, agent_config semantic, render, lab contract, lab manifest, lab-outputs-canonical, data-integrity, dependency-direction, doc-lifecycle, script-classification, experiment-workflow-classification, kb-produce-registry, data-flow | **174 passed** |
| Compile-gate all specs | `load_spec` + `compile_spec` over `experiments/definitions/*.yaml` + `workflows/**/*.yaml` | **79/79 compile, 0 fail** |
| CLI — help | `agentic-dynamics --help` | **exit 0** |
| reproduce core — dry-run | `scripts/reproduce.sh core --dry-run` | **exit 0** (8 canonical labs, `--no-tests --no-sonar`) |
| Docker build | `docker build -t agentic-dynamics .` | **success** |
| Container core run (fixture) | `docker run --rm -v …apps/website agentic-dynamics` | **exit 0**, `data.js` = 108,783 bytes |
| Agent surfaces | `python scripts/_gen_instructions.py` | **36 files; opencode + claude schemas OK** |

## 4. Invariant audit

| Invariant | Check | Result |
|---|---|---|
| Redis isolation | framework queue lives on `FINOPS_REDIS_PORT` (default **6380**); never 6379 (story agents' `finops-redis`) | **PASS** — `enqueue.py`/`worker.py`/`monitor.py`/`queue_reinterleave.py`/`pipeline_status.py` all default 6380 |
| Firebase dual-host | `apps/website/.firebaserc` names both `ai-finops-rulebook` (default) + `agentic-dynamics`; `firebase.json` `public: "."` | **PASS** |
| CAP frozen-not-implemented | the seven reserved homes exist and contain *no code* (docstring + `# reserved for CAP I<n>` only) | **PASS** — `facts.py` (I0), `reducers/` (I1–I3), `context_compiler.py` (I4), `contracts.py` (I5), `rules.py`/`validator.py`/`decisions.py` (I6) |
| No retired summary in publication input | no canonical (publication-eligible) lab reads `_results_summary.json` | **PASS** — the only match is a "does not read" docstring note in `lab_story_arc.py`; the classification guard (`test_lab_manifest.py`) enforces it |
| Canonical lab lineage | `build_data.py` rejects stale-manifest lab JSON | **PASS** — `test_lab_outputs_canonical.py` + `test_lab_contract.py` green |

## 5. Final verdict

**PASS.** All P0/P1/P2/P3 findings of `docs/reviews/semantic_integrity_review.md` are resolved by
passing release phases; the single remaining item (the neutral-intent schema, P1/P2) is explicitly
deferred with a pointer. Full suite green (1505 passed, 1 skipped), every guard suite green,
79/79 specs compile, the reproduction container runs the core pipeline to a published `data.js`,
and every invariant audit check passes. The release is complete.
