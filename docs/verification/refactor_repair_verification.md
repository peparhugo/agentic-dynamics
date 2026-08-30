---
status: accepted
---
# Refactor-Repair Release — Verification

Release gate for the refactor-repair release (17 phases, driven by
`docs/reviews/refactor_repair_review.md` — an external, operator-provided review of main at
`1e360335f`, every load-bearing claim re-verified against the tree). Each phase is a green
commit; this document is the final coverage proof: every review finding → a phase → a PASS entry
in `docs/release/consolidation/execution_log.md`, plus the full-suite / guard-suite / CI-gate / compile-gate
/ invariant results.

## 1. Coverage proof — finding → phase → PASS

| Review finding | Phase(s) | Execution-log subsection | Result |
|---|---|---|---|
| **P0-1** — agent config semantically wrong (byte-copy → schema drift) | `b1_dual_renderers` | `P0-1 — semantic agent-config source + two platform renderers` | PASS (7/7) |
| **P0-2** — authoritative instructions stale | `b2_instruction_rewrite` | `P0-2 — instruction docs rewritten against the current tree` | PASS (7/7) |
| **P0-2** (guard) — stale-path guard over accepted/current docs | `b3_stale_path_guard` | `P0-2 (guard) — stale-path guard` | PASS (7/7) |
| **P0-3** — Control Room repo root wrong after the move | `a1_control_room_paths` | `P0-3 — Control Room repo root re-point` | PASS (8/8) |
| **P1-1** — reproduction environment not updated | `a2_repro_environment` | `P1-1 — Reproduction environment + CI gates` | PASS (7/7) |
| **P1-2** — CLI command-resolution bug | `a3_cli_resolution` | `P1-2 — CLI longest-prefix resolution` | PASS (7/7) |
| **P1-2** (packaging) — wheel is not an honest checkout | `a4_cli_packaging` | `P1-2 (packaging) — CLI checkout-only + wheel smoke gate` | PASS (7/7) |
| **P1-3** — experiment/workflow split semantically unreliable | `c1_artifact_metadata` | `P1-3 (schema) — validated artifact-identity metadata` | PASS (7/7) |
| **P1-3** (placement) — misplacements survive the substring classifier | `c2_reclassify` | `P1-3 (placement) — re-home the two misplacements` | PASS (7/7) |
| **P1-3** (backfill) — metadata missing from all 77 specs | `c3_metadata_backfill` | `P1-3 (backfill) — explicit identity metadata on all 77 specs` | PASS (6/6) |
| **P1-4** — lifecycle index does not identify current work | `d1_lifecycle_semantics` | `P1-4 (semantics) — per-kind lifecycle status derivation` | PASS (6/6) |
| **P1-4** (index) — STATUS.md does not answer "what remains" | `d2_status_rewrite` | `P1-4 (index) — identity columns + runnable-vs-done view` | PASS (6/6) |
| **Debt-2** — dependency lint not airtight; runtime→control coupling | `e1_lint_relative_and_protocols` | `Debt-2 — relative-import lint + runtime→control inversion` | PASS (7/7) |
| **Debt-3** — measured-signal vocabulary inconsistent | `e2_signal_registry` | `Debt-3 — one signal registry` | PASS (7/7) |
| **Debt-1** — local monoliths (Control Room) | `e3_split_control_room` | `Debt-1 — split the Control Room monolith` | PASS (7/7) |
| **Debt-1** (second) — local monoliths (story) | `e4_split_story` | `Debt-1 (second) — split runtime/story.py into a package` | PASS (6/6) |
| *(this gate)* | `f1_repair_verification` | `f1_repair_verification — release gate` | PASS (7/7) |

**Orphan check: zero.** Every P0/P1 finding and every "Architectural debt that remains" item
(Debt-1/2/3) has at least one phase with a PASS entry; there are no phases without a finding and
no findings without a phase.

## 2. Full suite

- `pytest tests/ -m "not external"` → **1286 passed, 0 failed** (106 deselected as external-service).

Two pre-existing `f6acbcf41` failures were resolved here as release-blockers:
- `docs/reviews/refactor_repair_review.md` gained its `status: accepted` front-matter
  (`test_doc_lifecycle`).
- `experiments/specs/refactor_repair_release.yaml` was re-homed to
  `workflows/repository/refactor_repair_release.yaml` with identity metadata
  (`test_experiments_specs_flat_dir_is_drained`).

## 3. Guard suites (all green)

`test_dependency_direction` · `test_data_flow` · `test_experiment_workflow_classification` ·
`test_script_classification` · `test_doc_lifecycle` · `test_agent_config_render` ·
`test_stale_path_guard` · `test_signal_registry` · `test_control_room_paths` (+
`test_experiment_spec` / `test_compile_experiment` / `test_artifact_identity` / `test_spec_status` /
`test_cli_resolution`) → **203 passed**.

## 4. Compile gate

`compile_spec(load_spec(p))` succeeds for every spec and `validate_spec(p) == []` on all of them,
with `artifact_kind` matching its directory → **78/78 PASS**.

## 5. CI-equivalent gates (local)

- `docker build .` → **PASS** (image built; the `experiments/definitions/` COPY path fixed in P1-1 resolves).
- `agentic-dynamics --help` → **PASS** (exit 0).
- `bash scripts/reproduce.sh --dry-run` → **PASS** (exit 0).

## 6. Invariant audit

- **Redis isolation** — the framework queue lives on port **6380** (`FINOPS_REDIS_PORT` default
  6380: `apps/control_room/server.py`, `knowledge_stream.py`); the story-agent Redis on **6379** is
  documented as a test sandbox that must never be ported. PASS.
- **Firebase dual-host** — `apps/website/.firebaserc` lists both `ai-finops-rulebook` (default) and
  `agentic-dynamics`. PASS.
- **CAP frozen** — the Context Abstraction Plane design + verify docs are `status: accepted`, the
  ARCHITECTURE.md marks the CAP reserved homes **frozen**, and the physical placeholder files
  (`core/contracts.py`, `control/{facts,rules,validator,decisions,context_compiler}.py`,
  `control/reducers/`) remain uncreated. PASS.

## 7. Verdict

**PASS — the refactor-repair release is complete.** All 17 phases are green-committed, the full
suite and every guard suite are green, the compile gate admits all 78 specs, the CI-equivalent
gates pass locally, and the operational invariants (Redis isolation, dual-Firebase, frozen CAP)
survive. The repository matches its own architecture and its runtime paths, agent instructions,
artifact taxonomy, and lifecycle model now describe the tree that is actually there.
