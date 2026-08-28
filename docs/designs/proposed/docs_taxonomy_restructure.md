---
status: proposed
---

# Docs Taxonomy Restructure — design

**Status: PROPOSED — not accepted; nothing below moves a file.** This is the intake
document (docs/designs/proposed/) for the external review's **P2**: *"document taxonomy is
still overloaded: docs/designs/current/ mixes architecture designs, preregistrations, rerun
plans, result interpretations, postmortems, stabilization plans, website redesign material;
the distinction between 'design' and 'result' is being lost."*

**Inventory date:** 2026-08-28. **Corpus:** 200 markdown files (7 root + 193 under `docs/`).
**Constraint:** the 2d campaign (`cap_adaptive_2d`, workflows/repository/cap_adaptive_2d.yaml)
is RUNNING while this doc is written; its wrapper phases hard-code
`docs/designs/current/cap_adaptive_2d_design.md` + `docs/designs/current/cap_adaptive_2d_preregistration.md`
and deliver its verdict to `docs/designs/current/cap_adaptive_2d.md` (§x1_compile_and_setup,
x3 verdict, x4 adversarial, x5 release phases). **Phase 2 (the moves) MUST NOT run while any
campaign is in flight** — see §(e).

---

## (a) Current vs proposed tree

### Current tree (200 files)

```
docs/
├── ARCHITECTURE.md (root)  + 6 other root .md (AGENTS/CLAUDE/CODE_OF_CONDUCT/CONTRIBUTING/HANDOFF/README)
├── *.md  flat (40)         # verify/survey/fixplan/redesign/rebrand/routing/opencode-docs/… — unclassified scatter
├── archive/ (10)           # superseded blueprints + dated handoffs — guard-compliant, KEEP
├── consolidation/ (10)     # S0–S6 release records (design, stage_map, stage_*_verification, verification)
├── context_abstraction/ (2)   # implementation_notes + review (orphan pair beside current/context_abstraction_design.md)
├── control_room_ui/ (4)    # design/research/verify/rebuild_verify (website surface material)
├── designs/
│   ├── *.md (3)            # control_room_refresh_{audit,design,qa} — website redesign material
│   ├── current/ (47)       # ← THE OVERLOADED DIR (P2): 13 architecture, 9 experiment designs,
│   │                       #   3 preregistrations, 15 verdicts, 1 postmortem, 2 verifies, 1 review,
│   │                       #   1 website design, 1 release manifest, 1 deferred idea
│   ├── implemented/ (13)   # canonical_state_*, impl_* — guard-compliant, KEEP
│   └── proposed/ (0→)      # intake for proposed designs (this doc)
├── release/ (1)            # branch_protection_settings
├── review/ (34)            # 19 closure/internal reviews + 8 verification reports + 7 impl_* records
├── reviews/ (28)           # adversarial + known-safe pairs (per-campaign falsification records) — KEEP
└── spec_lifecycle/ (1)     # verify.md
```

The overload is measurable: `docs/designs/current/` holds 47 files of **ten different kinds**;
`docs/review/` and `docs/reviews/` are two siblings for one concern; the flat `docs/` root
holds 40 files whose only taxonomy is their filename suffix (`_verify`, `_design`, `_plan`,
`_survey`, `_spec`, `_idea`, `_notes`, `_audit`).

### Proposed tree (review structure, adapted to this corpus)

```
docs/
├── architecture/current/          # 23 files — mechanism designs of the framework itself
├── experiments/
│   ├── designs/                   #  9 — experiment/campaign designs + rerun plans (pre-data)
│   ├── preregistrations/          #  3 — committed-before-data protocols
│   ├── results/                   # 15 — measured verdicts / result interpretations
│   └── indexes/                   #  N — GENERATED per-experiment index (phase 3)
├── postmortems/                   #  1 — cap_terra_postmortem
├── verification/                  # 30 — verify/survey/audit/closure-verification reports
├── website/                       #  7 — website redesign material
│   └── control_room_ui/           #  8 — Control Room surface material (design+verify+refresh)
├── release/                       # 15 — release manifests, stabilization plans, release records
│   └── consolidation/             # 10 — S0–S6 release records (kept together; a release, not docs)
├── reviews/                       # 49 — ALL review material (adversarial pairs + closure/internal reviews)
├── designs/
│   ├── implemented/               # 21 — implemented design records (+ impl_* implementation records)
│   └── proposed/                  #  2 — intake (this doc + the deferred reasoning-measurement idea)
└── archive/                       # 10 — unchanged (superseded lineage, guard-compliant)
```

**Adaptations to the review's 8-dir structure** (explicit, each with a reason):

1. **`ARCHITECTURE.md` stays at the root**, not under `docs/architecture/current/`. It is the
   single architectural authority referenced *by name* in every `docs/archive/`
   `superseded_by: ARCHITECTURE.md` lineage field, in `tests/test_doc_lifecycle.py`
   `AUTHORITATIVE_DOCS`, in `tests/test_stale_path_guard.py`'s allowlist, and in the README.
   Moving it would force a lineage rewrite of 10 archive files + test edits for zero taxonomy
   gain. New architecture designs move into `docs/architecture/current/`; if a future
   consolidation wants ARCHITECTURE.md itself relocated, that is a separate, smaller change.
2. **`docs/website/` is added** (review structure has no website home). Website redesign
   material is a product-surface concern, not an experiment; it gets its own subtree
   (`docs/website/` + `docs/website/control_room_ui/`), which also absorbs
   `docs/control_room_ui/` and the flat `docs/designs/control_room_refresh_*` trio.
3. **`docs/experiments/indexes/`** is added for the per-experiment generated index (§(c)).
4. **`docs/review/` is emptied into `docs/reviews/`** (+ `docs/verification/` + the
   implemented-records home) — one reviews home, one verification home, removing the
   review/reviews split.
5. **`docs/designs/current/` is fully retired as a path family** (all 47 files redistribute).
   The proposed → accepted → "moves to current/" convention becomes proposed → accepted →
   "moves to the kind home" (`docs/architecture/current/` for mechanism designs,
   `docs/experiments/designs/` for experiment designs). The retired family is enforced by the
   stale-path guard (§(d)).
6. **`docs/release/consolidation/`** keeps the S0–S6 records together: they are one release
   record (a release, not a topic), even though some filenames say `_verification` — the
   stage verifications are inseparable from the release record and would lose context split
   into `docs/verification/`.
7. **`docs/context_abstraction/` and `docs/spec_lifecycle/` dissolve** into the kind homes
   (implemented-records, reviews, verification).

Per-kind move counts (193 docs files, totals reconcile):

| Destination | From flat docs/ | From designs/current | From other dirs | Total |
|---|---|---|---|---|
| architecture/current | 10 | 13 | — | 23 |
| experiments/designs | — | 9 | — | 9 |
| experiments/preregistrations | — | 3 | — | 3 |
| experiments/results | — | 15 | — | 15 |
| postmortems | — | 1 | — | 1 |
| verification | 19 | 2 | review/ 8 + spec_lifecycle 1 | 30 |
| website (+ control_room_ui) | 7 | 1 | designs/ 3 + control_room_ui/ 4 | 15 |
| release (+ consolidation) | 4 | 1 | consolidation/ 10 | 15 |
| reviews | — | 1 | review/ 19 + context_abstraction 1 | 49 (21 stay) |
| designs/implemented | — | — | review/ 7 + context_abstraction 1 | 21 (13 stay) |
| designs/proposed | — | 1 | — | 2 (1 stays) |
| archive / release (stay) | — | — | — | 10 |
| **Total** | **40** | **47** | **54** | **193** |

---

## (b) Per-kind definitions — the load-bearing distinction

The review's sharpest point: "design" vs "preregistration" vs "result" are being conflated.
The definitions below are **temporal + evidential**, not topical. Each kind answers one
question, is written at one point in the cycle, and carries one evidence class:

| Kind | Answers | Written | Evidence | Status vocabulary | Home |
|---|---|---|---|---|---|
| **Architecture design** | What mechanism do we build into the framework? (planes, CAP, supervisor, spec/compiler, routing, instrumentation seams) | before implementation | none — proposal | proposed → accepted → implemented | docs/architecture/current/ |
| **Experiment design** | What study do we run, and how? (arms, cells, stimulus, outcome, protocol sketch) | before data | none — proposal (numbers NOT committed) | proposed → accepted | docs/experiments/designs/ |
| **Rerun plan** (subclass of experiment design) | What do we change and re-run? (tweak one variable) | before data of the rerun | prior verdicts only | accepted | docs/experiments/designs/ |
| **Preregistration** | What EXACTLY is committed before any cell runs? (fixed arms, outcome metric, margin, seed, stop rule, model/backend, SHA-pinned spec) | after design acceptance, BEFORE data | none — commitment (SHA-pinned) | accepted | docs/experiments/preregistrations/ |
| **Result / verdict** | What did the campaign MEASURE, and what is the decision? (score, non-inferiority, abstention curves, acceptance) | after data | [M] measured | accepted (= the finding is accepted as measured) | docs/experiments/results/ |
| **Postmortem** | What failed, at what cost, and what does the process change? | after a failed run | [M] measured | accepted | docs/postmortems/ |
| **Verification** | Did the implementation meet the design/claim? (verify reports, surveys, audits, closure verifications, scans) | after implementation | [M]/[C] check evidence | accepted | docs/verification/ |
| **Adversarial review** | Can an independent model falsify the verdict? (adversary + known-safe pairs) | after a result | [H] attempted falsification | accepted | docs/reviews/ |
| **Release / stabilization** | What ships, through which gates? (release manifest, stabilization plan, release records) | at ship time | mixed | accepted | docs/release/ |
| **Website redesign material** | What changes on the product surface (site/app), and did it measure better? | anytime | mixed | accepted | docs/website/ |

**The three-way test (P2's load-bearing rule).** For any doc, ask in order:

1. **Does it commit numbers before data?** → preregistration (a design that commits numbers
   before data is a *mislabeled preregistration*; a preregistration that commits nothing is a
   *mislabeled design*). The 2b/2c/2d family shows the correct pattern: `*_design.md` says
   "NOT a preregistration; nothing below commits a campaign", `*_preregistration.md` says
   "committed BEFORE any cell runs" and pins the campaign-spec SHA256.
2. **Does it contain measured campaign output?** (score, ratio, margin, decision) → result /
   verdict (or postmortem if the object is a failure). A design that reports measured output
   is a *verdict wearing a design's filename* — the corpus has 15 of these inside
   `docs/designs/current/` (e.g. `cap_2b.md` "verdict: the randomized static-vs-adaptive
   pilot", `cap_escalation_measurement.md` "verdict", `cap_adaptive_2c.md` "verdict").
3. **Is it a mechanism-of-the-framework proposal or a study proposal?** → architecture
   design vs experiment design. Framework mechanics (context abstraction plane, supervisor,
   spec/compiler, CAP gates, instrumentation seams, evidence integrity) are architecture;
   anything naming cells/arms/stimuli/outcome metrics is an experiment design.

Evidence-class convention: [M] measured / [C] computed / [H] heuristic / [P] policy — already
used across the corpus; verdicts must carry [M]-class findings, preregistrations carry none.

---

## (c) The generated per-experiment index

**Requirement (P2):** one generated index per experiment linking
spec → preregistration → assignment manifest → execution ledger → score → validation →
adversarial review → canonical records → superseding study.

**Format** — `docs/experiments/indexes/<name>_index.md`, generated, never hand-edited
(`status: accepted` in frontmatter, `kind: experiment_index`, `experiment: <name>`):

```markdown
---
status: accepted
kind: experiment_index
experiment: cap_2b
generated_at: 2026-08-28T00:00:00Z
---
# cap_2b — experiment index (generated)

| Chain link | Path | Evidence |
|---|---|---|
| Spec | workflows/repository/cap_2b.yaml (`cap_2b@0.1`, index.json status completed) | [P] |
| Design | docs/experiments/designs/cap_2b_design.md | [P] |
| Preregistration | docs/experiments/preregistrations/cap_2b_preregistration.md (SHA-pinned, pre-data) | [P] |
| Assignment manifest | workflows/repository/cap_2b.yaml (cells: 2 arms × N) + experiments/specs/STATUS.md row | [P] |
| Execution ledger | experiments/results/workflows/cap_2b/<run>.json (results_pointer from index.json) | [M] |
| Score | experiments/results/workflows/cap_2b/<run>.json → score fields | [M] |
| Validation (known-safe) | docs/reviews/cap_2b_known_safe.md | [H] |
| Adversarial review | docs/reviews/cap_2b_adversary.md | [H] |
| Verdict | docs/experiments/results/cap_2b.md | [M] |
| Canonical records | experiments/results/registry_index.jsonl + experiments/results/kb/<id>.json | [M] |
| Superseding study | cap_2a_rerun3 (supersedes chain from experiments/specs/STATUS.md) | [P] |
```

**Generator:** extend `scripts/spec_status.py` (the existing derived-spec-lifecycle
generator — one entry point, already reads `experiments/specs/index.json`, `STATUS.md`,
`results_pointer`) with a `render_experiment_indexes()` function, wired into `main()` via a
`--experiment-indexes` flag (default: render alongside STATUS.md). Per experiment name that
(a) appears in `experiments/specs/index.json` **or** has ≥1 artifact under
`docs/experiments/{designs,preregistrations,results}/` **or** has a `docs/reviews/<name>_*`
pair, the generator:

1. resolves the spec row from `experiments/specs/index.json` (`spec_path`,
   `results_pointer`, `supersedes`/`superseded_by`, status);
2. resolves each doc artifact by the `<name>_*` prefix convention in the new homes
   (designs/preregistrations/results/reviews);
3. writes the index table; missing links are rendered as `—` (never fabricated).

`scripts/spec_status.py` must keep its current outputs byte-compatible — the experiment
indexes are an additive render.

---

## (d) Guard-test migration plan

Current rules (tests/test_doc_lifecycle.py) and their fate:

| Guard test | Today | After the restructure |
|---|---|---|
| `test_every_document_has_status_field` | every root + docs md has `status` in {proposed, accepted, implementing, implemented, superseded, abandoned} | **unchanged.** Vocabulary stays 6-valued. Mapping onto the new tree: `docs/experiments/results/` verdicts are `accepted` findings; `docs/experiments/preregistrations/` are `accepted` commitments; `docs/architecture/current/`, `docs/experiments/designs/`, `docs/postmortems/`, `docs/verification/`, `docs/website/`, `docs/release/`, `docs/reviews/` entries are `accepted`; `docs/designs/proposed/` entries are `proposed`; `docs/designs/implemented/` entries are `implemented`. No new status values needed — the *kind* is carried by the directory, not the status |
| `test_archive_entries_are_superseded` | archive = superseded + superseded_by | **unchanged** (docs/archive/ untouched) |
| `test_current_designs_are_accepted` | every docs/designs/current/* = accepted | **generalized** → `test_kind_tree_statuses`: a `TREE_STATUS` dict {docs/architecture/current: accepted, docs/experiments/designs: accepted, docs/experiments/preregistrations: accepted, docs/experiments/results: accepted, docs/postmortems: accepted, docs/verification: accepted, docs/website: accepted, docs/release: accepted, docs/reviews: accepted, docs/designs/proposed: proposed} walked with the same glob-per-dir shape. The docs/designs/current/ entry is deleted (dir retired) |
| `test_implemented_designs_name_their_branch` | designs/implemented = implemented + implemented_by | **unchanged** — the dir grows to 21 files; the 7 `impl_*` records already carry `implemented` + `implemented_by` (they pass today by construction); `context_abstraction/implementation_notes.md` needs its frontmatter fixed at move time (status → implemented + `implemented_by: <context-abstraction branch>` — supplied in the move commit) |
| `test_no_blueprint_at_root` | no BLUEPRINT*.md at root | unchanged |
| `test_stale_cap_claims_absent_from_authoritative_docs` | CAP never "reserved/emerging" | unchanged (ARCHITECTURE.md/README.md stay at root) |
| `test_readme_spec_counts_match_index` | README spec count == index.json | unchanged (experiments/specs/* untouched by the restructure) |
| **NEW** `test_experiment_indexes_exist` | — | every experiment name with ≥1 artifact in `docs/experiments/{designs,preregistrations,results}/` (or a `docs/reviews/<name>_*` pair) has `docs/experiments/indexes/<name>_index.md` with `status: accepted` + `kind: experiment_index`; every linked path in the index resolves (exists-check, mirroring the resolution discipline of tests/test_agent_config_semantic.py) |

`tests/test_stale_path_guard.py` (the other guard that touches doc paths):

| Guard test | Change |
|---|---|
| `RETIRED_PATH_FAMILIES` | **add `"docs/designs/current/"`** — the P2-overload family itself. This makes `test_accepted_docs_use_no_retired_paths` and `test_agent_config_uses_no_retired_paths` enforce that no accepted doc and NO agent_config file references the retired dir → the forced repoint of agent_config + workflow YAMLs. (The other emptied dirs — `docs/review/`, `docs/consolidation/`, `docs/context_abstraction/`, `docs/control_room_ui/`, `docs/spec_lifecycle/` — are plain moves without family enforcement, to keep the allowlist churn bounded; extend later if desired.) |
| `ALLOWLIST` | **repoint every moved key** — `docs/review/` → `docs/reviews/` + `docs/verification/`; `docs/consolidation/` → `docs/release/consolidation/`; `docs/control_room_ui/` → `docs/website/control_room_ui/`; `docs/context_abstraction/` → `docs/reviews/context_abstraction_review.md` (+ its implemented sibling); `docs/spec_lifecycle/` → `docs/verification/`; the ~25 flat-file keys (routing_*, verify*, opencode_docs_*, claude_tools_to_skills_*, auto_posthoc_*, control_room_survey, operator_*, workflow_phase_*, agentic_dynamics_rebrand_*, remediation_*, fixplan, facelift, narrative, redesign, challenge, scope, spec, verify.md, architecture_visual) → their new homes. **Add `HANDOFF.md`** (root, accepted, historical dated log — it references designs/current). `test_allowlist_entries_all_resolve` enforces every key resolves, which is the mechanical check that the repoint is complete |
| `_scan_targets` | remove the now-dead `docs/designs/current/*` glob (dir retired) |

Other tests with path references (must be repointed IN the phase-2 commit, or they go red):

- `tests/test_agent_config_semantic.py` — no code change, but it resolves every backticked
  path in `agent_config/**`; green only after `agent_config/` is repointed AND
  `python scripts/_gen_instructions.py` is run (see §(e)).
- `tests/test_fact_auto_emit.py`, `tests/test_fact_auto_emit_adversarial.py` — docstrings
  reference `docs/designs/current/cap_fact_auto_emit_design.md` → repoint to
  `docs/architecture/current/`.
- `tests/test_test_runner_wiring.py` — docstring references
  `docs/designs/current/cap_test_runner_wiring.md` → repoint to `docs/architecture/current/`;
  the `files_created=["docs/scope.md"]` fixture must track `docs/scope.md` → `docs/architecture/current/scope.md`
  (check the mirror phase definition in workflows/repository/cap_test_runner_wiring.yaml).
- `tests/test_cap_2a_spec.py` — references `docs/reviews/cap_2a_shadow_calibration_{adversary,known_safe}.md`,
  paths that DO NOT move → **unchanged** (verification item only).
- 10 workflow YAMLs under `workflows/repository/` reference `docs/designs/current/`
  (cap_2a_shadow_calibration, cap_adaptive_2d, cap_e2_cascade_run, cap_grit_grid_execute,
  cap_routing_evidence_specs, cap_shadow_fact_disposition, cap_site_revamp3,
  cap_site_revamp4_diagrams, cap_story_bridge, cap_terra_postmortem) → repoint
  `canonical_sources:` to the new homes. `experiments/specs/STATUS.md` + `index.json` are
  doc-path-free (verified) → unaffected.

**Status-vocabulary mapping (the review's question, answered):** verdicts are `accepted`
findings — "accepted" means *the measured finding is accepted into the record*, not *the
proposal is approved*. The kind is carried by the directory (`results/`), the status by the
frontmatter. No vocabulary extension is proposed; adding a `verified` status would cascade
into every existing doc and the README/website provenance tags for no gain.

---

## (e) Cut-over sequencing

**Phase 1 — inventory + design (THIS TASK, DONE).** No moves, no commits. The inventory
table below is the record; the design doc is the proposal.

**Phase 2 — moves + guard updates, ONE commit, ONLY after every in-flight campaign ends.**
Hard constraint: **must not run while any campaign is in flight** — the 2d wrapper phases
(workflows/repository/cap_adaptive_2d.yaml §x1_compile_and_setup, x3, x4, x5) read
`docs/designs/current/cap_adaptive_2d_design.md` + `cap_adaptive_2d_preregistration.md` and
deliver `docs/designs/current/cap_adaptive_2d.md` + `docs/reviews/cap_adaptive_2d_*`; moving
those files breaks the running campaign. Completion of 2d ALSO deposits a new verdict
(`docs/designs/current/cap_adaptive_2d.md`) and review pair — phase 2 must move those too.
Sequence inside the single commit:

1. `git mv` every file per the inventory table (git history preserved; no content edits
   except the three frontmatter fixes: `reasoning_measurement_idea.md` → `status: proposed`,
   `context_abstraction/implementation_notes.md` → `implemented` + `implemented_by`,
   moved docs keep `accepted`).
2. Update `tests/test_doc_lifecycle.py` (§(d): generalize `test_current_designs_are_accepted`
   → `test_kind_tree_statuses`; keep the other rules).
3. Update `tests/test_stale_path_guard.py` (§(d): RETIRED_PATH_FAMILIES + ALLOWLIST repoint
   + dead glob removal) and the three repointed test files.
4. Repoint the 10 workflow YAMLs' `canonical_sources:` + `tests/test_test_runner_wiring.py`'s
   fixture.
5. Repoint `agent_config/` (mental-model.md, rules.md, skills/, agents/, commands/ — 28
   files reference `docs/designs/current`), then run `python scripts/_gen_instructions.py`
   to regenerate `.opencode/` + `.claude/` (each target validated against its platform
   schema). **Note: AGENTS.md is NOT machine-rendered** (verified: `_gen_instructions.py`
   emits only `.opencode/` + `.claude/` targets) — hand-edit AGENTS.md's four
   `docs/designs/current/` references (lines ~19, ~73, ~78, ~94) in the same commit, and
   HANDOFF.md's references.
6. Check `experiments/specs/STATUS.md` + `experiments/specs/index.json` — verified
   doc-path-free, but re-verify after phase 2 (they are regenerated by `scripts/spec_status.py`
   and must not drift).
7. Green gate: `python3 -m pytest tests/test_doc_lifecycle.py tests/test_stale_path_guard.py
   tests/test_agent_config_semantic.py tests/test_repo_hygiene.py -m "not external" -q`
   + `ruff check` on the touched test files.

**Phase 3 — the generated experiment index.** Implement the `render_experiment_indexes()`
extension of `scripts/spec_status.py` (§(c)), generate `docs/experiments/indexes/*.md`, add
the `test_experiment_indexes_exist` guard, and wire the generation into the regeneration
convention (spec_status.py + run_workflow.py end-of-run refresh). Deploy the website only
after the generated index exists (the site's provenance tags cite the review chain).

Rollback: phase 2 is one commit — `git revert` restores the exact tree; the guards are
updated in the same commit so no intermediate state is testable-green-but-inconsistent.

---

## Inventory table (path | kind | status | proposed new home)

Kind codes: **arch** architecture design · **expd** experiment design · **rerun** rerun plan
(subclass of expd) · **pre** preregistration · **res** result/verdict · **pm** postmortem ·
**ver** verification · **rev** review · **rel** release/stabilization · **web** website
material · **impl** implementation record · **keep** unchanged.

### Root (7) — all keep

| Path | Kind | Status | New home |
|---|---|---|---|
| AGENTS.md · CLAUDE.md · CODE_OF_CONDUCT.md · CONTRIBUTING.md · HANDOFF.md · README.md | keep | accepted | root (unchanged) |
| ARCHITECTURE.md | arch | accepted | root (unchanged — adaptation 1) |

### docs/ flat (40)

| Path | Kind | Status | New home |
|---|---|---|---|
| architecture_visual.md | arch | accepted | architecture/current/ |
| routing_design.md · routing_next_steps.md · routing_signal_store_notes.md | arch | accepted | architecture/current/ |
| challenge.md · scope.md · spec.md · ux.md | arch | accepted | architecture/current/ |
| claude_code_port.md · claude_tools_to_skills_scope.md | arch | accepted | architecture/current/ |
| facelift.md · narrative.md · redesign.md | web | accepted | website/ |
| opencode_docs_challenge.md · opencode_docs_scope.md · opencode_docs_spec.md | web | accepted | website/ |
| fixplan.md | web | accepted | website/control_room_ui/ |
| agentic_dynamics_rebrand_verify.md · auto_posthoc_survey.md · auto_posthoc_verify.md · claude_tools_to_skills_verify.md · control_room_posthoc_verify.md · control_room_survey.md · data_integrity_findings.md · operator_audit.md · operator_fix_verify.md · remediation_verify.md · routing_follow_up_verify.md · routing_survey.md · routing_verify.md · verify.md · verify_evidence.md · verify_evidence_redesign.md · verify_framework.md · workflow_phase_survey.md · workflow_phase_verify.md | ver | accepted | verification/ |
| agentic_dynamics_arxiv_draft.md · agentic_dynamics_rebrand_plan.md · agentic_dynamics_vision.md · remediation_plan.md | rel | accepted | release/ |

### docs/designs/ (3 flat) + current/ (47) + implemented/ (13) + proposed/

| Path | Kind | Status | New home |
|---|---|---|---|
| control_room_refresh_audit.md · control_room_refresh_design.md · control_room_refresh_qa.md | web | accepted | website/control_room_ui/ |
| 2026-08-14_experiment-spec-and-compiler-design.md · supervisor_design.md · context_abstraction_design.md · context_abstraction_addendum_design.md · cap_evidence_integrity_design.md · cap_fact_auto_emit_design.md · cap_gate_migration.md · cap_pattern_minting.md · cap_runner_hardening2_design.md · cap_story_bridge.md · cap_test_runner_wiring.md · visibility_matrix.md · visibility_matrix_decisions.md | arch | accepted | architecture/current/ |
| cap_2a_rerun2_design.md · cap_2a_rerun2_measurement_design.md · cap_2a_rerun3_design.md · cap_2b_design.md · cap_adaptive_2d_design.md · cap_e2_e3_run.md (rerun) · cap_grit_grid_runplan.md (rerun) · cap_session_routing_prospective_design.md · cap_stage0_stage1_prompt.md (rerun) | expd | accepted | experiments/designs/ |
| cap_2b_preregistration.md · cap_adaptive_2c_preregistration.md · cap_adaptive_2d_preregistration.md | pre | accepted | experiments/preregistrations/ |
| cap_2a_rerun2.md · cap_2a_rerun3.md · cap_2a_shadow_calibration.md · cap_2b.md · cap_adaptive_2c.md · cap_escalation_measurement.md · cap_fact_backfill_coverage.md · cap_fact_backfill_prereq.md · cap_gate_scan.md · cap_routing_evidence_specs.md · cap_session_routing_prospective.md · cap_shadow_fact_disposition.md · cap_shadow_measurement.md · cap_site_regression_analysis.md · cap_site_revamp_followup.md | res | accepted | experiments/results/ |
| cap_terra_postmortem.md | pm | accepted | postmortems/ |
| context_abstraction_verify.md · context_abstraction_addendum_verify.md | ver | accepted | verification/ |
| context_abstraction_addendum_review.md | rev | accepted | reviews/ |
| cap_site_revamp3_design.md | web | accepted | website/ |
| cap_stabilization_release.md | rel | accepted | release/ |
| reasoning_measurement_idea.md | arch | accepted → **proposed** | designs/proposed/ (frontmatter fixed) |
| canonical_state_base_design.md · canonical_state_base_inventory.md · canonical_state_base_verify.md · canonical_state_finalize_verify.md · canonical_state_implement_verify.md · canonical_state_r2_changes.md · canonical_state_r2_design.md · canonical_state_r2_plan.md · canonical_state_r2_verify.md · impl_rag_seam_split.md · impl_website_registry_repoint.md · impl_website_registry_repoint_audit.md · impl_website_repoint.md | impl | implemented | designs/implemented/ (keep) |

### docs/review/ (34) → reviews/ + verification/ + designs/implemented/

| Path | Kind | Status | New home |
|---|---|---|---|
| canonical_publication_review.md · finding_economics_review.md · measurement_contribution_review.md · public_truth_review.md · refactor_repair_review.md · semantic_integrity_review.md · semantic_monolith_review.md · restructure.md · architecture_review.md · bugs.md · code_review.md · control_room.md · website.md · knowledge_base.md · cap_e2_e3_review.md · cap_evidence_integrity_review.md · cap_pattern_minting_review.md · cap_story_bridge_review.md · cap_test_runner_wiring_review.md | rev | accepted | reviews/ |
| canonical_publication_verification.md · finding_economics_verification.md · measurement_contribution_verification.md · public_truth_verification.md · refactor_repair_verification.md · semantic_integrity_verification.md · review_verify.md · null_not_zero_sweep.md | ver | accepted | verification/ |
| impl_control_room_hardening.md · impl_kb_producer_factory.md · impl_kb_record_fidelity.md · impl_kb_write_path.md · impl_measurement_bug_fixes.md · impl_registry_canonicalize.md · impl_task_vocabulary_unify.md | impl | implemented | designs/implemented/ |

### docs/reviews/ (28) — keep (adversarial + known-safe pairs, site reviews, deploy gate)

### Other dirs

| Path | Kind | Status | New home |
|---|---|---|---|
| archive/* (10) | keep | superseded | archive/ (unchanged) |
| consolidation/* (10) | rel | accepted | release/consolidation/ |
| context_abstraction/implementation_notes.md | impl | accepted → **implemented** | designs/implemented/ (frontmatter fixed) |
| context_abstraction/review.md | rev | accepted | reviews/context_abstraction_review.md |
| control_room_ui/* (4) | web | accepted | website/control_room_ui/ |
| release/branch_protection_settings.md | rel | accepted | release/ (keep) |
| spec_lifecycle/verify.md | ver | accepted | verification/spec_lifecycle_verify.md |
| designs/proposed/docs_taxonomy_restructure.md (this doc) | arch | proposed | designs/proposed/ (keep) |
