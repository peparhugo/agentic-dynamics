---
status: accepted
---

# CAP Evidence Integrity — Adversarial Review (a1_review_evidence_integrity)

**Reviewer:** deepseek-v4-pro (operator override — sonnet-5 unavailable via Claude OAuth), `feature/cap-evidence-adversary` phase `a1_review_evidence_integrity`.
**Target:** `feature/cap-evidence-integrity` — the seven phase commits `4eb563816` (p0) +
`0891e115c` (e1) + `332acab8a` (e2) + `80222e549` (e3) + `1146b8143` (e4) + `95bf8b081` (e5)
+ `96301d90c` (e6), on base `a504ff505`.
**Method:** checked the branch out at `96301d90c` into a worktree, re-derived each phase's
claims against the actual source rather than the evidence `.md` files, ran the hermetic test
surface live (`test_evidence_prereq_gate.py`, `test_sonar.py`, `test_code_delta.py`,
`test_quality_ingestion.py`, `test_code_change_facts.py`, `test_change_analyzer.py` — 57 tests,
all green), ran the gate script itself, and constructed a targeted counter-example for the one
denominator I suspected was degenerate.

## Verdict: **PASS with 3 mandatory fixes**

Six of the seven phase claims survived direct attack — most notably the two hardest ones: the
`code_change_risk` v1 formula matches the spec **exactly** (weights, normalization, renormalization,
None-when-nothing-measurable), and the traversal ACL is genuinely enforced inside the Cypher (a
public-scope seed cannot reach a private-repo node — proven by `test_scoped_seed_cannot_reach_private_repo_node`,
not by a post-filter). Three findings below do not falsify the stream's load-bearing claims but
do require fixes: one is a measured fact that cannot express the quantity it names, one is a
reproducibility gap in the p0 gate's *evidence*, and one is an over-stated wiring claim.

## Findings

### F1 (e5, MANDATORY) — `ast_parse_coverage` is structurally always 1.0

`code_change_facts.py:219-225` computes `ast_parse_coverage = parsed_changed_files / changed_files`
where `changed_files = delta.changed_files | delta.added_files`. But `CodeDelta.changed_files` /
`added_files` are derived **only from the parsed-files dicts** (`before.files` / `after.files`,
which `build_code_snapshot` populates exclusively for files that parsed without error — see
`language.py:630-635`, where a parse failure or `has_error` goes to `unparsed_files`, never to
`files`). Therefore every file in the denominator is already in `after.files`, so
`parsed == changed_files` always and coverage is **always 1.0**.

Re-derived counter-example (live, in the branch worktree):

```
before = {'m.py': b'def f():\n    pass\n'}        # parsed
after  = {'m.py': b'def f(:\n    syntax error\n'} # UNPARSEABLE
delta.changed_files = [], added_files = [], removed_files = ['m.py']
=> ast_parse_coverage OMITTED, changed_symbol_count = '1'
```

A file that becomes unparseable is *invisible* to the coverage denominator: the fact is omitted
rather than reporting a degraded coverage, and whenever the fact *is* emitted it is exactly 1.0.
The correct quantity already exists — `CodeSnapshot.parse_coverage()` (`parsed / (parsed + unparsed)`,
`language.py:404-412`) — but the reducer never uses it. The e5 evidence's own test
(`test_full_fixture_produces_all_measurable_facts`) only exercises the happy path (`== 1.0`) and
`test_zero_change_omits_parse_coverage_denominator` the zero case; **no test covers a changed-but-unparseable
file**, which is precisely where the fact should diverge from 1.0.

**Fix:** compute `ast_parse_coverage` from the snapshots' `parse_coverage()` (or track unparsed
files in the delta's file lists) and add a regression test with a changed-but-unparseable file.

### F2 (p0, MANDATORY) — the gate's *evidence* is not reproducible at the branch tip

The gate script (`scripts/evidence_prereq_gate.py`) is genuinely exit-code based and
fails-closed — its *logic* is deterministic and cannot be satisfied by prose (F1-adjacent attack
**not falsified**: it reads run ledgers + review docs and resolves ancestry with
`git merge-base --is-ancestor`, not text). But its INPUT is not part of the tree: the run ledgers
it reads live under `experiments/results/workflows/<spec>/*.json`, which `.gitignore` explicitly
excludes ("machine-local, not provenance"). Running it at the branch tip (fresh checkout,
`/tmp/wt_evidence_integrity_review`) does **not** exit 0:

```
$ python3 scripts/evidence_prereq_gate.py
EVIDENCE PREREQ GATE: NOT MET
  - cap_e2_cascade_run: no run ledger found
  - cap_pattern_minting: no run ledger found
  - cap_story_bridge: no run ledger found
  - cap_test_runner_wiring: no run ledger found
  - cap_story_bridge: last run ledger is not ok
EXIT=1
```

This contradicts the review's own criterion ("run it yourself: exit 0"). The committed p0
evidence is `experiments/results/evidence_prereq_gate_report.txt` — a one-line prose record of a
run whose inputs no longer exist in the tree. The gate ran correctly once, in the machine that
held the four prerequisite ledgers; the *reproducibility of its evidence* does not survive
checkout. This is not a determinism-of-logic defect (the code path is sound and the script's own
tests prove exit 1 on unmet prereqs), but the "checks hold at the branch tip" claim is false as
stated.

**Fix (either):** (a) commit the four prerequisite run ledgers (or a pinned `git_sha` for each)
so the gate re-runs, or (b) restate the claim to "the gate is a one-time preflight whose
machine-local inputs are not provenance" and stop asserting re-runnability.

### F3 (e6, MANDATORY) — "injected at the composition root" is unsubstantiated

`runtime/change_analyzer.py` and `runtime/__init__.py` both state the concrete analyzer is
"injected at the composition root (`scripts/run_workflow.py`)". It is not. Grep for
`run_change_analysis` / `ChangeAnalyzer` / `EvidenceChangeAnalyzer` across `scripts/` and
`runtime/` finds **zero call sites** outside the two new modules and their tests; `scripts/run_workflow.py`
and `runtime/workflow_runner.py` were not modified by any phase commit. The `run_change_analysis`
entry point has no production caller; the end-to-end loop is proven only by direct
`EvidenceChangeAnalyzer().analyze(...)` invocation in `tests/test_change_analyzer.py`
(hermetic store-double + live-Neo4j), never through an actually-wired runtime seam.

The runtime side of the claim **holds** (`runtime/change_analyzer.py` imports only stdlib —
"runtime never imports control" is true; `NoopChangeAnalyzer` is a strict no-op so existing
behavior is byte-identical — trivially, since the seam is never invoked). But the composition-root
injection the docstrings assert does not exist, so the claim overstates what shipped.

**Fix (either):** wire `run_change_analysis` into `scripts/run_workflow.py` as an opt-in (default
`None`), or correct the docstrings/evidence to say "protocol + concrete implementation delivered;
composition-root wiring is a follow-up."

## Known-safe list (attacked, did not falsify)

| # | Attack attempted | Result |
|---|---|---|
| 1 | **p0 — the gate can be satisfied by prose** | **Not falsified.** `evidence_prereq_gate.py` never inspects prose: it derives branch-merged-ness from `git merge-base --is-ancestor` over the ledger `git_sha` and review-verdict approval from a `## Verdict:` line lacking "FAIL". Its own tests (`test_gate_fails_when_verdict_is_fail`, `test_gate_fails_when_story_bridge_not_ok`) force exit 1 on unmet prereqs. (The gate's *inputs* are the F2 issue, not its logic.) |
| 2 | **e1 — some path stamps a stale analysis with a newer revision** | **Not falsified.** Traced `run_sonar_analysis` → `_revision_confirmed` (`sonar.py:447-460`): fail-closed — an unscoped key with missing/different captured revision is NOT confirmed → `status="stale-refused"`. `_sonar_text` (`quality_ingestion.py:146-158`) carries the true `analyzed_sha` (or `""`), never the current commit. The stale-refused branch (`quality_ingestion.py:466-486`) emits the status fact with counts omitted. |
| 3 | **e1 — unknown `extra_fields` crept into `record_factory`** | **Not falsified.** `record_factory.py` diff vs base is empty. The only `extra_fields` passed are `extractor_version`, `language`, `symbols` — all valid `KnowledgeRecord` fields; `build_record` raises `ValueError` on any unknown key (`record_factory.py:157-159`). |
| 4 | **e2 — the two-ID helpers are non-deterministic** | **Not falsified.** `module_entity_id`/`module_version_id`/`symbol_entity_id`/`symbol_version_id` (`language.py:713-732`) are pure sha256 over fixed delimited strings; `test_revision_pair_produces_versions_and_supersedes` asserts `v1 != v2` and `entity_id` stability. |
| 5 | **e2 — CommitAnalysis callers broken** | **Not falsified.** `compute_ast_diff`'s public signature is unchanged; `CommitAnalysis` gains only additive fields (`parse_coverage`, `code_delta`); the regex diff-stat heuristic is fully removed and `test_data_integrity::test_go_rust_patterns_in_ast_diff` asserts its absence. `test_commit_analysis.py` (131/151/168) still passes. |
| 6 | **e3 — Sonar issues still collapse to one sentence** | **Not falsified.** `fetch_sonar_issues` (`sonar.py:505-557`) returns one `SonarIssue` per line/rule; `derive_quality_records` emits one `build_issue_record` per issue with a per-issue signal fragment (`sonar-issue/<rel>:<line>:<rule>`). |
| 7 | **e3 — pyright silent pass** | **Not falsified.** `pyproject.toml` has `[project.optional-dependencies] lsp = ["pyright==1.1.390"]` (exact pin). e3 satisfies BOTH branches: the durable `lsp_analysis_status: unavailable` probe with zero dependent counts (`_lsp_unavailable_text` + `derive_quality_records:529-545`) AND the pinned-version fixture proof (probe C in the evidence md). |
| 8 | **e4 — a public-scope seed reaches a private-repo node** | **Not falsified.** `_acl_clause` (`graph.py:119-137`) is interpolated into the seed resolution (`_resolve_node:1026-1029`) and every hop (`_neighbors:1063-1066`); scoped mode constrains `repository_id = $… AND acl_scope = $…`. `test_scoped_seed_cannot_reach_private_repo_node` proves the private repo id is absent from the reachable set. |
| 9 | **e4 — a legacy caller that omits ACL args reaches versioned nodes** | **Not falsified.** The omitted-scope clause is `NOT (n:ModuleVersion OR n:SymbolVersion)` — versioned nodes fail closed always; `test_legacy_omitted_scope_fails_closed_for_versioned` asserts `[]`, while `test_legacy_omitted_scope_still_reaches_unversioned` confirms unversioned back-compat. |
| 10 | **e4 — every `expand_candidates` caller passes both ACL args** | **Not falsified.** Only two production callers exist: `retrieval.py:1011-1018` and `evidence_analyzer.py:111-119`; both pass `repository_id` + `acl_scope` explicitly. The remaining call sites are test code (legacy-path tests). |
| 11 | **e5 — risk formula deviates from spec / invented weights** | **Not falsified.** `RISK_WEIGHTS` = `(new_sonar_critical, 0.35), (new_lsp_error, 0.25), (tests_ratio, 0.20), (impacted, 0.20)` — byte-for-byte the spec; terms are `min(1, x/10)` / `(1 − tests_ratio)`; renormalization is `sum(w·t)/sum(w)`; risk omitted when no term is measurable. Independently recomputed the three asserted values (0.245, 0.2267, 0.115) and they match. |
| 12 | **e5 — null-not-zero violated (None-as-zero)** | **Not falsified.** Dependent counts emit only under `isinstance(…, int)`; the ratio emits only when `tested_changed > 0`; `test_unavailable_lsp_omits_counts_and_renormalizes_risk` and `test_no_measurable_risk_terms_yields_no_risk_fact` assert the omissions. |
| 13 | **e6 — runtime imports control** | **Not falsified.** `runtime/change_analyzer.py` imports only `dataclasses` + `typing`; the concrete impl lives in `control/evidence_analyzer.py` (control→runtime, a legal downward edge). `test_dependency_direction` is green for the changed surfaces. |
| 14 | **e6 — the smoke is fake (not an actual data flow)** | **Not falsified.** `test_evidence_loop_smoke_hermetic` runs the real `EvidenceChangeAnalyzer.analyze` over a real `CodeSnapshot`/`CodeDelta` with a duck-typed graph client, asserting graph update + `changed_symbol_count=2` + `impacted=1` + `risk≈0.115` + neighborhood `("Calc",)`. `test_composition_root_data_flow_live_neo4j` (skipif no Neo4j) proves the real graph populates 3 `SymbolVersion`s for the after-revision and emits the facts. |

## Notes for the record

- **Test-surface confirmation.** Ran the six hermetic test files live at the branch tip: 57 tests,
  all green (`test_evidence_prereq_gate` 3, `test_sonar` + `test_quality_ingestion` 22+16,
  `test_code_delta` + `test_change_analyzer` 29, `test_code_change_facts` 9 — the live-Neo4j
  cases in `test_versioned_graph.py` / `test_change_analyzer.py` skip when Neo4j is absent).
  The phase evidence `.md` files' "full suite NNNN passed" numbers were not re-run end-to-end
  (they include the whole corpus and the pre-existing lab-output/environmental failures); the
  load-bearing hermetic surface was.
- **F1 vs the `ast_parse_coverage` contract posture.** The `verify_code_change.yaml` contract
  requires `ast_parse_coverage` with `on_missing: halt`, so the F1 degenerate case (changed file
  becomes unparseable → fact omitted) actually *halts* rather than mis-verifying — a lucky
  fail-safe, not a justification for the always-1.0 fact.
- **Operator override.** This review was executed by deepseek-v4-pro (Claude OAuth unavailable),
  per the workflow's run-shape override. The adversarial convention's two-output requirement
  (findings + known-safe list) and no-bare-PASS rule are both met above.

## Resolutions (committed on this branch after the review — `cap_evidence_integrity_fixes`)

All three mandatory findings were FIXED (each with a regression test), not waived:

- **F1 (e5)** — `compute_code_delta` now tracks unparseable files in the delta's file lists
  (they compare by content hash — `_file_content_unchanged` in `core/language.py`), so a
  changed-but-unparseable file stays in `changed_files` and `ast_parse_coverage` degrades
  below 1.0 instead of being structurally 1.0. Regression tests: `test_changed_file_becoming_unparseable_stays_in_changed_files`
  (+ added/unchanged unparseable variants in `test_code_delta.py`), `test_changed_but_unparseable_file_degrades_parse_coverage`
  and `test_parse_coverage_mixed_parsed_and_unparseable` in `test_code_change_facts.py`.
- **F2 (p0)** — the gate is now re-runnable at the branch tip: `experiments/results/evidence_prereq_inputs.json`
  pins the four prerequisite runs' `git_sha` + `ok` (the run ledgers stay gitignored
  "machine-local, not provenance"), and `scripts/evidence_prereq_gate.py` falls back to the
  pinned record when a machine-local ledger is absent. Verified live: `exit 0` with the four
  ledger directories removed. Regression tests: `test_gate_passes_via_pinned_inputs_when_ledgers_absent`,
  `test_gate_fails_when_pinned_inputs_also_absent`.
- **F3 (e6)** — the composition-root claim now holds: `scripts/run_workflow.py --change-analysis`
  injects the concrete `EvidenceChangeAnalyzer` at the root, and `runtime/workflow_runner.py`
  hands every committed phase's typed delta (materialized from git) to the injected
  `ChangeAnalyzer`, recording `code_change_facts/v1` + the executor neighborhood on
  `PhaseResult.change_analysis` — best-effort, never a gate on the phase. No graph client in
  v1 (the versioned-graph step stays a documented follow-up). Regression tests:
  `test_run_workflow_change_analysis_seam`, `test_run_workflow_change_analysis_inert_without_injection`,
  `test_run_workflow_change_analysis_root_commit_never_fails`.

Resolution verification: the six hermetic test files + `test_workflow_runner.py` +
`test_commit_analysis.py` + `test_data_integrity.py` + `test_dependency_direction.py` all green
(157 tests); full suite green except the pre-existing environmental `test_embeddings.py::test_connectivity`
(Chroma, fails on base too).
