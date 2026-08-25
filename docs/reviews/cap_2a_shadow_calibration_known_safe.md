---
status: accepted
---
# cap_2a — Shadow calibration: known-safe (attempted attacks that did not falsify)

Date: 2026-08-25 · Campaign: `cap_2a_shadow_calibration` · Phase: `p6_adversarial`

This is the second of the two p6 outputs: every attack that was attempted and did NOT falsify the
campaign, with what was tried, the artifact/tree evidence, and why it is safe. It is not a generic
checklist; each entry is tied to a specific attempt.

## Known-safe

### S1 — Wrong baseline (verifier and baseline on different inputs/worktrees)

- **Tried:** compared the baseline/analyzed revision chain across artifacts and against the git
  object store.
- **Evidence:** `git -C /tmp/wt_cap2a_p2_registry rev-parse <c>^` yields the exact parent chain
  `e61c709eb → bccb17514 → fb1ca291e → c2ed5270e`, matching `p2_phase_ledger.json` phases[].baseline_revision
  → analyzed_revision and `p2_cell_manifest.json` source_baseline_revision.
- **Why safe:** the verifier's input revisions are a real, contiguous commit chain on one worktree;
  no cross-worktree or cross-input mismatch.

### S2 — Cherry-picked cells

- **Tried:** checked that every candidate was either run, refused with a reason, or excluded with a
  reason.
- **Evidence:** `p2_candidate_manifest.json` lists all five candidates with `excluded_reason`;
  registry_canonicalize was run (p2); `p3_execution_manifest.json` lists labbook_refresh +
  queue_steer as `not-run` with the blocking reason; finding_economics_closure + canonical_publication_closure
  carry `excluded_reason` in the p2 manifest.
- **Why safe:** no listed candidate was silently dropped.

### S3 — Hit-rate denominator games

- **Tried:** checked whether unknown/not-run/invalid cells were silently excluded from any denominator.
- **Evidence:** `cap_2a_score_20260825T222430Z.json` `aggregates` prints `n_scored=0`, `n_hits=0`,
  `n_unknown_outcome=0`, `n_invalid_join=0`, `n_not_run=2`, `n_proposal_missing=1` separately; no
  denominator is used that is not printed.
- **Why safe:** denominators are explicit; there are no unknown-outcome cells to hide.

### S4 — Candidate cost presented as a measurement when it was only historical

- **Tried:** searched for any place a historical-index cost is passed off as a measurement.
- **Evidence:** `p2_cell_manifest.json` marks `historical_cost_usd: 0.1872` with
  `historical_cost_label: "historical-index, NOT measured"`; `p3_execution_manifest.json` labels the
  p2-derived budget `forecast_label: "FORECAST … NOT a measured cost"`; `p2_phase_ledger.json`
  reports the measured `total_measured_cost_usd` separately.
- **Why safe:** forecast and measured are reported independently and labeled.

### S5 — p4 JSON hashes do not match the verdict citations

- **Tried:** re-hashed every input artifact the p5 verdict cites.
- **Evidence:** `docs/designs/current/cap_2a_shadow_calibration.md` cites candidate-manifest
  `6b8bbab6…` and p4 JSON `3862c784…adc197`; `sha256sum` on `p2_candidate_manifest.json` and
  `cap_2a_score_20260825T222430Z.json` reproduce both exactly.
- **Why safe:** the verdict's provenance hashes match the tree.

### S6 — p1 wiring changes no-graph behavior (byte-identical claim)

- **Tried:** confirmed the no-`--change-analysis` path is inert even when graph env vars are set.
- **Evidence:** `tests/test_run_workflow_graph_cli.py::test_change_analyzer_absent_when_only_graph_requested`
  and `::test_main_no_analyzer_no_client_without_flag`, plus
  `tests/test_change_analyzer.py::test_default_analyzer_is_a_strict_noop` — 53-test p1 subset green.
- **Why safe:** without `--change-analysis`, no analyzer is injected and no Neo4jClient is
  constructed, even with `FINOPS_NEO4J_URI` set.

### S7 — Graph construction failure mislabeled `not_requested`

- **Tried:** confirmed a requested-but-unconstructable graph is `unavailable`, not `not_requested`.
- **Evidence:** `tests/test_change_analyzer.py::test_requested_but_unavailable_graph_is_not_mislabeled`
  and `tests/test_run_workflow_graph_cli.py::test_construction_failure_is_recorded_as_unavailable`.
- **Why safe:** the `graph_requested` bit keeps `unavailable` distinct from `not_requested`.

### S8 — Deleted symbols absent because only the after revision was populated

- **Tried:** confirmed the analyzer populates the parent snapshot before expansion.
- **Evidence:** `tests/test_change_analyzer.py::test_evidence_loop_smoke_hermetic` asserts the store
  sees both revisions (`["rev-1", REV]`); `tests/test_workflow_runner.py::test_run_workflow_change_analysis_seam`
  asserts `removed_symbols == {"f0"}` resolves from the parent.
- **Why safe:** removed-symbol seeds resolve from the parent revision.

### S9 — SUPERSEDES counted as impact

- **Tried:** confirmed the impact traversal excludes version-history edges.
- **Evidence:** `tests/test_change_analyzer.py::test_impact_expansion_allowlist_excludes_supersedes`
  asserts `IMPACT_EXPANSION_RELS == ALLOWED_EXPANSION_RELS - {"SUPERSEDES"}`.
- **Why safe:** version history is never an impact edge.

### S10 — Short-SHA or reused-cell identity collision

- **Tried:** checked whether identity keys use a short SHA or collide across cells.
- **Evidence:** `_git_full_sha` (workflow_runner.py:247) resolves full 40-char SHAs; the p4 JSON's
  `analyzed_revisions` are full 40-char; cell IDs are unique (`cap2a_p2_registry_canonicalize`,
  `cap2a_p3_labbook_refresh`, `cap2a_p3_queue_steer`) and carry no SHA.
- **Why safe:** no short-SHA identity, no reused cell identity.

### S11 — Malformed or stale proposal accepted

- **Tried:** attempted to build/validate proposals with a wrong action, a wrong schema version, an
  empty revision, a negative depth, and `applied=true`.
- **Evidence:** `tests/test_code_change_facts.py::test_proposal_schema_validation_contract_and_version`
  and `::test_proposal_schema_validation_with_applied_false` — all refused with a named reason.
- **Why safe:** the seam refuses rather than accepts a malformed/stale/applied proposal.

### S12 — `applied` true or any actuation call

- **Tried:** AST-scanned the proposal seam for actuation/steering call sites.
- **Evidence:** `tests/test_code_change_facts.py::test_proposal_seam_never_actuates_or_steers` asserts
  no `publish_event`/`derive_actuation_record`/control_route/rework call or import;
  `validate_verify_proposal` hard-refuses `applied=True`.
- **Why safe:** shadow-only, never applied, never armed.

### S13 — Unclosed Neo4j driver

- **Tried:** confirmed the client is closed even when the run raises.
- **Evidence:** `tests/test_run_workflow_graph_cli.py::test_main_closes_graph_client_on_success` and
  `::test_main_closes_graph_client_when_run_raises` — closed in a `finally`.
- **Why safe:** no leaked driver.

### S14 — Leaked credentials

- **Tried:** grep'd every committed p2/p3/p4 artifact + the 28 KB records for credential patterns.
- **Evidence:** no `NEO4J_PASSWORD`/API-key/private-key material found; the only "token" matches are
  `token_count` / `attempt_tokens_in/out` (token-count measurements, not auth tokens).
- **Why safe:** no secrets in committed artifacts.

### S15 — Graph-down cell silently dropped or mislabeled as full-fact

- **Tried:** checked whether the registry_canonicalize cell was dropped or relabeled as graph-complete.
- **Evidence:** `p2_phase_ledger.json` `graph_reachability` records `populate_completed: false` and
  `neo4j_reachable: true`; the p4 scoring keeps the cell in `cells[]` with `graph_status:
  "unavailable"` and `graph_flagged: true`.
- **Why safe:** the cell remains in the dataset, flagged, never mislabeled as full-fact.

### S16 — Proposal/outcome circular labeling

- **Tried:** searched for any proposal and outcome that reference each other as both signal and label.
- **Evidence:** no proposal and no outcome were produced anywhere in p2–p4 (the seam refused), so no
  circular labeling is possible; the p4 scoring has `n_scored=0`.
- **Why safe:** vacuous — and the campaign correctly recorded it as such rather than fabricating a label.

### S17 — Stale facts consumed (`analysis_revision_matches=false` ignored)

- **Tried:** checked whether a stale-fact path could be silently consumed.
- **Evidence:** `analysis_revision_matches` is only emitted when sonar runs (`code_change_facts.py`
  semantics: "OMITTED when the sonar analysis did not run"); sonar never runs in this wiring, so the
  fact is never `false`, and the proposal seam refuses before any fact is consumed.
- **Why safe:** no stale-fact consumption path exists in this campaign's wiring.

## Log

**PASS/FAIL: PASS** — seventeen attacks attempted; none falsified the campaign's verdict. The
findings that DID surface (F1–F4) are recorded separately in
`docs/reviews/cap_2a_shadow_calibration_adversary.md` as accepted limitations with residual risk.
