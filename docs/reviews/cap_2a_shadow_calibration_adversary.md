---
status: accepted
---
# cap_2a — Shadow calibration: adversarial falsification review

Date: 2026-08-25 · Campaign: `cap_2a_shadow_calibration` · Phase: `p6_adversarial`

Role: adversarial verifier. Each attack below was re-verified against the tree (not imagined). A
finding is either **fixed** or recorded as an **accepted limitation** with reasoning and residual
risk; a non-finding is listed in `docs/reviews/cap_2a_shadow_calibration_known_safe.md`, never a
bare PASS.

## Findings

### F1 — Duplicate qualified names collapse in the CALLS edge (accepted limitation)

- **Attack:** duplicate qualified names (two functions with the same `qualified_name` in different
  files) collapse into one symbol.
- **Evidence:** `src/agentic_dynamics/knowledge/graph.py:852` builds `qname_to_vid[sym.qualified_name] = sym_vid`
  — keyed by bare name only, so a later symbol with the same name overwrites the earlier one — and
  `graph.py:905` resolves `callee in qname_to_vid` to pick the CALLS target.
- **Result:** the symbol *version nodes* are NOT collapsed — `symbol_entity_id(repository_id,
  file_path, qualified_name, kind)` (`graph.py:739`, used at `:847`) keys identity by file+name+kind,
  and `sym_vids[(path, qname, kind)]` (`:851`) is correct. Only the CALLS *edge* resolution is
  name-based and can point to a same-named symbol in a different file.
- **Fix / limitation:** accepted limitation. CALLS is documented "name-based best-effort from
  sym.calls" (`graph.py:899`) — `sym.calls` is a bare-name list from tree-sitter call expressions,
  so without import resolution this ambiguity is inherent.
- **Residual risk:** impact-expansion via `CALLS` could be imprecise for duplicate names. **Not
  exercised**: the campaign never produced an `impacted_symbol_count` (graph leg unavailable), so no
  scored number used this edge.
- **Re-test:** `tests/test_versioned_graph.py::test_call_and_tested_by_edges` green (53-test p1
  subset re-run 2026-08-25).

### F2 — Missing independent test evidence (`test_executed_success = null`) (accepted limitation)

- **Attack:** the campaign claims an "independent test/result signal" but the selected cell has no
  independent `test_runner` verdict.
- **Evidence:** `experiments/results/cap_2a/p2_phase_ledger.json` → `phases[].test_result` =
  "test_executed_success = null (no test_gate / kind:test phase)"; `workflows/operations/registry_canonicalize.yaml`
  has no `test_gate: true` and no `kind: test` phase (grep of all five candidates returns none).
- **Result:** the "independent" signal was the agent's self-reported pytest (`kind: agent` test
  phase), not the independent `runtime.test_runner`. Had outcome adjudication been reached, the
  realized outcome would lack independent test evidence.
- **Fix / limitation:** accepted limitation — it is explicitly recorded in `p2_phase_ledger.json`,
  and it never entered a scored number because no proposal was emitted (the campaign reached zero
  outcomes).
- **Residual risk:** a future p3 resume must select a cell with `test_gate: true` / `kind: test` to
  obtain `test_executed_success`.
- **Re-test:** grep confirms no candidate declares `test_gate`/`kind: test`; p4 scoring correctly
  reports 0 outcomes.

### F3 — Implement phase's canonical KB facts absent (accepted limitation)

- **Attack:** canonical fact emission silently absent for one committed phase.
- **Evidence:** the implement phase ran in the first `run_workflow.py` invocation, which died during
  graph population (empty run log — SIGKILL, no traceback). The 27 emitted facts
  (`experiments/results/registry_index.jsonl`, `attempt:test` / `attempt:verify` /
  `workflow:wf_registry_canonicalize_deepseek_deepseek_v4_pro`) cover only the resume run's test +
  verify phases. The implement phase's facts (`changed_symbol_count=0`, `ast_parse_coverage=1.0`)
  exist only in `p2_phase_ledger.json`.
- **Result:** the implement phase's canonical KB facts are absent — but NOT silent; they are
  reconstructed in the committed ledger.
- **Fix / limitation:** accepted limitation — the phase committed in the graph-hung invocation that
  died before the fact-emit step; its facts are in the committed ledger, which is what p4 read.
- **Residual risk:** the KB lacks the implement-phase canonical facts; no scoring or verdict read
  them, so this did not change any reported number.
- **Re-test:** `registry_index.jsonl` traced for `wf_registry_canonicalize_*` facts; implement facts
  traced to `p2_phase_ledger.json` phases[0].

### F4 — p3 manifest does not restate the not-small exclusion (accepted limitation)

- **Attack:** cherry-picked cells — a listed candidate skipped without a reason.
- **Evidence:** `experiments/results/cap_2a/p3_execution_manifest.json` lists 2 cells
  (`labbook_refresh`, `queue_steer`) but does not re-state why `finding_economics_closure` ($1.2820,
  6 phases) and `canonical_publication_closure` ($1.4475, `repeatable: false`, `completed`) were
  excluded. The reasons DO exist in `experiments/results/cap_2a/p2_candidate_manifest.json` →
  `candidates[].excluded_reason`.
- **Result:** not a cherry-pick (the reasons are traceable), but the p3 manifest is not self-contained.
- **Fix / limitation:** accepted limitation — the p3 prompt asked for "2-3 remaining *small* cells",
  and the two largest/one non-repeatable candidates are excluded with reasons in the p2 manifest.
- **Residual risk:** a reader of p3 alone would not see the exclusion reasons; they are recoverable
  from the p2 manifest.
- **Re-test:** `p2_candidate_manifest.json` carries `excluded_reason` for all four non-selected
  candidates.

## Re-stated verdict

**The 2b calibration threshold (proposal hit-rate ≥ 0.6) is NOT met — hit-rate is undefined at
n = 0.** This verdict is **correct and unfalsified**: no cell produced a complete
`verify_code_change` proposal. The blocker is real and re-verified: `build_verify_proposal` raises
`ValueError` ("required fact 'ast_parse_coverage' not measured") on the delta-only facts the cells
produce, because `code_change_risk` / `ast_parse_coverage` are never minted (sonar/lsp not wired
into `run_workflow.py::_run_change_analysis`, remaining cells change no Python symbols, graph leg
unavailable). The zero-score is a dataset-integrity fact, not a small-n authorization, and no
finding above changes any reported number.

## Log

**PASS/FAIL: PASS** — four accepted limitations recorded with evidence, residual risk, and re-test;
the campaign's verdict is re-stated as unfalsified. No p4 JSON or the p5 verdict was rewritten.
