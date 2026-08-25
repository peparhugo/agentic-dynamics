# e5 — code_change_facts/v1 + verify_code_change/v1 (cap_evidence_integrity)

Date: 2026-08-25 · Branch: feature/cap-evidence-integrity

## The implementation (design §5.6)

1. **`code_change_facts/v1` reducer** (`control/reducers/code_change_facts.py`, registered in
   `REDUCERS`): the TEN job-scoped predicates, minted from the typed CodeDelta (e2) + analyzer
   statuses:
   `analysis_revision_matches`, `ast_parse_coverage`, `lsp_analysis_status`,
   `sonar_analysis_status`, `changed_symbol_count`, `impacted_symbol_count`,
   `new_lsp_error_count`, `new_sonar_critical_count`, `changed_symbols_with_tests_ratio`,
   `code_change_risk`. Pure (design §4.1); evidence contract in the reducer docstring.
2. **Ten new `FACT_PREDICATES` rows** (`control/facts.py`), `produced_by=("code_change_facts/v1",)`.
3. **DEFINED semantics** (hard rule 6, not delegated):
   - status facts carry the measured enum (`available`/`unavailable`/`stale-refused`);
   - `analysis_revision_matches` omitted when the analysis did not run;
   - `ast_parse_coverage = parsed_changed_files / changed_files` (changed = changed+added
     files); omitted when changed_files == 0 (no denominator);
   - dependent count facts (`new_lsp_error_count`, `new_sonar_critical_count`,
     `impacted_symbol_count`) OMITTED when the analyzer/graph did not run — never fabricated
     zeroes (null-not-zero);
   - `changed_symbols_with_tests_ratio = tested_changed_symbols / changed_symbols` (TESTED_BY
     rule, §5.4); OMITTED when changed_symbols == 0 OR the rule links no changed symbol
     (DEFERRED, never 0);
   - `code_change_risk` v1 = `0.35·min(1,new_sonar_critical/10) + 0.25·min(1,new_lsp_error/10) +
     0.20·(1−tests_ratio) + 0.20·min(1,impacted/10)`; non-measurable terms omitted, remaining
     weights RENORMALIZED to 1; risk is None (fact omitted) when NO term is measurable; the
     weights are `[P]` operator policy with provenance recorded in the reducer docstring
     (`RISK_WEIGHTS`).
   - minting-order guard: `changed_symbol_count` etc. are minted ONLY from the typed CodeDelta.
4. **`verify_code_change/v1` contract** (`experiments/contexts/verify_code_change.yaml`):
   shadow-only proposal actions (`verify`/`rework`/`continue`), `AUTOMATABLE_ACTIONS` untouched;
   hard-rule-6 framing in the header; count facts soft (`on_missing: classify` = analyzer did
   not run, never zero), the three identity facts halt.

## The tests

- `tests/test_code_change_facts.py` (new, 9): full fixture → all measurable facts with exact
  values (risk = 0.245); all predicates registered + produced by the reducer; unavailable LSP
  omits counts + renormalizes risk (0.2267 over w=0.75); stale-refused sonar → status +
  revision-mismatch, counts omitted; no measurable term → no risk fact (never 0); TESTED_BY
  ratio deferred with no test link; zero-change omits the parse-coverage denominator (real 0
  for changed_symbol_count, not fabricated); contract loads + passes the R1-R11 gate with real
  registries; contract compiles ADMISSIBLE through the real `compile_context`.
- `tests/test_context_plane_facts.py` + `tests/test_context_plane_checkpoint.py`: the pinned
  predicate-set / loaded-contracts assertions updated for the 10 new rows + `verify_code_change`.

Full suite: **1941 passed** (excluding pre-existing environmental hangs — Chroma/Ollama — and
the pre-existing lab-output failures on the parent checkout).

## Verdict

**PASS** — fixture delta + analyzer statuses → the ten facts with defined semantics; unavailable
analyzers omit counts (never zero); the contract compiles and passes the gate; shadow-only (no
new automatable actions).
