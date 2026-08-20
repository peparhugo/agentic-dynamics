# Verification — consolidation release, end to end

**Phase `verify` of `consolidation_release`.** Verifies the staged consolidation plan produced by
`stage_map` → `design` → `stage_specs`: coverage, the compile gate on all 7 stage specs, sequence
soundness, and the operational invariants. One finding was detected (a WS-01 script-retirement
duplication between Stage 1 and Stage 3) and fixed in this phase — see §5.

**Provenance:** [M] measured this phase (compile-gate output, grep/`ls` ground truth); [C] computed
from the stage artifacts; [P] policy invariants; [X] the critique.

---

## 1. Coverage proof — all 9 recommendations → ≥1 stage

| Rec | Recommendation | Stage(s) | Result |
|---|---|---|---|
| 1 | Freeze architectural expansion (pause CAP I0–I7) | S0 | PASS |
| 2 | Modular monorepo `src/agentic_dynamics/` | S1 | PASS |
| 3 | Separate experiments from workflows | S2 | PASS |
| 4 | One root `ARCHITECTURE.md` + doc lifecycle | S0 | PASS |
| 5 | One CLI + script classification | S3 (CLI) + S5 (identity) | PASS |
| 6 | One instruction source (`agent_config/`) | S4 | PASS |
| 7 | Delete deprecated code (`legacy/`, zero imports) | S1 | PASS |
| 8 | Dependency-direction rules, auto-enforced | S1 | PASS |
| 9 | Website + control room as `apps/` | S5 | PASS |

Every recommendation maps to ≥1 stage; none is orphaned. Stage 6 is the cross-cutting gate that
asserts all nine.

## 2. Coverage proof — WS-01..10 disposition (zero orphans, zero duplicates)

| WS | Disposition | Lands in | Verified |
|---|---|---|---|
| WS-01 retire dead code | FOLDED | S1 (`retire_shim`) | PASS |
| WS-02 KB branch integration | DEFERRED | post-consolidation `knowledge/` | PASS |
| WS-03 KB write-path | DEFERRED | post-consolidation `knowledge/` | PASS |
| WS-04 lab book registry repoint | DEFERRED | post-consolidation `reporting/` (guard-test pattern promoted to S2/S6) | PASS |
| WS-05 compiler matrix wire | DEFERRED | post-consolidation | PASS |
| WS-06 compiler compare/evaluate | DEFERRED | post-consolidation | PASS |
| WS-07 compiler adapt/campaign | DEFERRED | post-consolidation | PASS |
| WS-08 admin step_sample | DEFERRED | post-consolidation `apps/control-room` | PASS |
| WS-09 review_worker retire | FOLDED (retire) / DEFERRED (rewire) | S3 (retire) / post-consolidation (rewire) | PASS |
| WS-10 sys.path + archive + docs | FOLDED (sys.path S1, archive S3) / RETIRED (doc-drift) | S1, S3, S0/S4 | PASS |

Tally: folded 3 (WS-01, WS-09, WS-10), deferred 7 (WS-02..08), retired 1 sub-part (WS-10 doc-drift).
All 10 workstreams dispositioned exactly once.

### Module/script orphan check

- **64/64 modules** dispositioned in `design.md` §1.1 (core 4 · experiment 3 · measurement 15 ·
  runtime 4 · adapters 3 · knowledge 16 · control 9 · reporting 4 · legacy 5 · barrel 1 = 64).
  [M] `ls src/instrument/*.py | wc -l` = 64 — matches. Zero orphans.
- **85/85 scripts** classified in `design.md` §5 (56 maintained → subcommands, 15 one-time, 13
  deprecated, 1 module `_constants`). [M] `ls scripts/*.py | wc -l` = 85 — matches. Zero orphans.

## 3. Compile-gate validate — every `consolidation_stage_*.yaml`

Ran `validate_spec` (which wraps `validate_rules`, the `requires`/`produces` gate) + `compile_spec`
on all 7 specs. [M] Output:

```
consolidation_stage_0_architecture_spine.yaml:      validate_spec NONE (valid) · validate_rules NONE (valid) · warnings NONE
consolidation_stage_1_package_move.yaml:            validate_spec NONE (valid) · validate_rules NONE (valid) · warnings NONE
consolidation_stage_2_experiments_workflows_split.yaml: validate_spec NONE (valid) · validate_rules NONE (valid) · warnings NONE
consolidation_stage_3_cli_classification.yaml:      validate_spec NONE (valid) · validate_rules NONE (valid) · warnings NONE
consolidation_stage_4_instruction_surfaces.yaml:    validate_spec NONE (valid) · validate_rules NONE (valid) · warnings NONE
consolidation_stage_5_apps_realignment.yaml:        validate_spec NONE (valid) · validate_rules NONE (valid) · warnings NONE
consolidation_stage_6_verification_release.yaml:    validate_spec NONE (valid) · validate_rules NONE (valid) · warnings NONE
```

Each spec compiles to the standard DAG `validate → cells → execute → measure → compare → writeup →
adapt` (feedback `adapt → cells`). Each stage's measurement rule carries `requires: []` and produces
its acceptance criteria (`imports_resolve`/`dependency_lint_green`/… for S1, `generated_surfaces_match`
for S4, etc.) — no control rule consumes unmeasured information, so the load-bearing gate is satisfied
in every spec. **Result: 7/7 PASS.**

## 4. Sequence audit — topological soundness

Dependency order (from `stage_map.md` §3): `S0 → S1 → {S2 → S3 → S4, S5} → S6`.

| Stage | needs (declared in `question`) | blocks (declared) | Verify gate defined? |
|---|---|---|---|
| S0 | — | S1–S6 | YES — `verify` phase runs `tests/test_doc_lifecycle.py` |
| S1 | S0 | S2–S6 | YES — `retire_shim` writes `stage_1_verification.md` + `verify` (kind:test) full suite |
| S2 | S1 | S3, S5, S6 | YES — `repoint` (index regenerates, guard test) + `verify` (kind:test) |
| S3 | S2 | S4, S5, S6 | YES — `retire_and_archive` (smoke-run) + `verify` (kind:test) |
| S4 | S3 | S6 | YES — `generate` (guard test) + `verify` (kind:test) |
| S5 | S1, S2, S3 | S6 | YES — `verify` (agent) + `test` (kind:test) |
| S6 | S0–S5 | — | YES — `gates` + `test` (kind:test) |

Checks:

- **No stage leaves the pipeline broken.** S1–S5 carry `enforce_pytest: true` on code-touching
  phases and a `kind: test` full-suite phase; S0 is doc-only (its `verify` runs the doc-lifecycle
  test, no production code touched). Each stage's `needs` matches the actual data dependency it
  consumes: S1 reads S0's `ARCHITECTURE.md` plane definitions; S2 reads S1's moved `experiment_spec`
  paths; S3 reads S2's split paths; S4 reads S3's CLI surface; S5 reads S1 imports + S2 data paths +
  S3 subcommands; S6 consumes S0–S5 outputs.
- **Verify gate feeds the next stage's needs.** S1's green full-suite + dependency lint is the
  precondition S2–S5 run on the moved package; S2's regenerated spec index is what S3's subcommands
  and S5's `site build` reference; S3's CLI is what S4 documents; S6 re-runs every prior stage test
  in one pass (the `gates` phase).
- **No cycle.** The order is a DAG; the only feedback edge in the system is the compiler's
  `adapt → cells` campaign loop, which is a per-spec runtime edge, not a stage-ordering edge.

**Result: PASS.**

## 5. Finding fixed this phase — WS-01 duplication (Stage 3)

Stage 3's `retire_and_archive` phase listed WS-01 script retirement (`plan.py`,
`analyze_with_ollama.py`, `analyze_with_opencode.py`, `build_graph.py`) as a "fold WS-01 remainder"
— but Stage 1's `retire_shim` phase already owns those deletions (WS-01 folds into S1). That was a
**duplicate execution** risk, violating the "no duplicate execution" rule.

Fix: Stage 3 now explicitly does **not** retire the WS-01 scripts; its `retire_and_archive` phase
retires **only** `review_worker.py` (WS-09) and archives the 15 one-time migrations (WS-10), with an
explicit "these are Stage 1's sole responsibility" note. Re-validated: S3 still passes the gate.
**Result: FIXED → PASS.** No other workstream is executed in two stages.

## 6. Invariant audit

| Invariant | Evidence [M] | Result |
|---|---|---|
| Redis isolation: 6380 queue DB1 + KB DB2; 6379 sandbox; never conflated | `knowledge_stream.py:41` `REDIS_PORT=6380`, `:45` `REDIS_DB=2`; `live.py:22` `6380`, `:23` `DB=1`; `pipeline_status.py:6`/`posthoc.py:4` `6380 db 1`; `knowledge_stream.py:14` "Never port 6379". Stage 1 hard_rules re-assert this. | PASS |
| Dual Firebase hosting | `firebase/.firebaserc` lists `{"default": "ai-finops-rulebook", "agentic-dynamics": "agentic-dynamics"}`; `firebase.json` `hosting.public = "public"`. S5/S6 require both-host deploy. | PASS (config present; deploy is a S5/S6 action) |
| Load-bearing rule survives every stage | All 7 specs measurement-only (`requires: []`, no control rule) → gate passes trivially; S0 restates the rule in `ARCHITECTURE.md`; S1/S6 re-run `compile_spec` on every committed spec. | PASS |
| CAP frozen, not deleted | `context_abstraction_implement.yaml` present (no `status:`/`superseded_by:`) [M]. Freeze is a S0 action: mark PAUSED + reserved homes, never delete/supersede (S0 `hard_rules` + `stage_map.md` §6). I0–I7 → reserved `control/*` + `core/contracts.py`. | PASS (freeze specified; applied at S0 execution) |
| Deprecated modules retired only inside the package move | `experiment.py, adapter.py, lab_book.py, recovery.py, trajectory.py` all still present [M] (`ls` confirms 5 files). Only S1 (`retire_shim`) retires them — no other stage. | PASS |

## 7. Final result

| # | Check | Result |
|---|---|---|
| 1 | All 9 recommendations → ≥1 stage | PASS |
| 2 | WS-01..10 dispositioned, zero orphans, zero duplicates | PASS (after §5 fix) |
| 3 | All 7 `consolidation_stage_*.yaml` pass the compile gate | PASS (7/7, no errors, no warnings) |
| 4 | Sequence audit: topological, no broken intermediate state | PASS |
| 5 | Invariant audit: Redis / dual Firebase / load-bearing / CAP freeze / retire-only-in-package-move | PASS |

**Overall: PASS** — 5/5 checks pass; one defect (WS-01 duplicate in Stage 3) was found and fixed in
this phase. The staged consolidation plan is verified end to end and ready for the execution
workflows, which run the stages in order `S0 → S1 → S2 → S3 → S4/S5 → S6`.
