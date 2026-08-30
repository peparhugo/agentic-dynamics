---
status: accepted
---
# Context Abstraction Plane — Addendum A (I8–I10) Architecture Review (audit phase)

**Spec:** Addendum A of `docs/architecture/current/context_abstraction_design.md` (§A, lines 1460–1604) —
the three post-closure refinements I8 (`DomainProfile`/`ChallengeProfile`), I9 (`pattern`
epistemic class), I10 (typed session checkpoint).
**Phase:** `review` (phase 1 of 3 — `review` → `design` → `verify`), in the same shape
`docs/reviews/context_abstraction_review.md` was for the frozen design's §§1–13.
**Date:** 2026-08-22 · **Model:** deepseek/deepseek-v4-pro · **Branch:** `feature/cap-addendum-design`
**Deliverable rule:** design-only. This phase adds exactly one file
(`docs/reviews/context_abstraction_addendum_review.md`) and modifies nothing under
`src/`, `scripts/`, `tests/`, or `admin/`.

---

## 0. What this document is, and how to read it

This is an **audit**, not a design. It establishes — with `file:line` citations a reader can
check — what the repository *already* implements of the three addendum refinements, what it
partially implements under a different name, and what is genuinely missing. The design phase
then builds only what is actually missing, under the addendum's own discipline ("schemas are
sketches, no file is created by this addendum" — `context_abstraction_design.md:1468`).

Two things make this audit different from the frozen design's review, and they matter to how
every claim below is read:

1. **The frozen design's §§1–13 are *designed but not implemented*.** The CAP implementation
   (I0–I7) has only **reserved homes** — empty stubs that exist so the implementation is
   "drop-in" (`control/__init__.py:7-9`). `control/facts.py` (I0), `control/reducers/` (I1–I3),
   `control/context_compiler.py` (I4), `core/contracts.py` (I5), and
   `control/rules.py`/`validator.py`/`decisions.py` (I6) are all placeholder modules. So when
   the addendum says I8/I9/I10 extend `EPISTEMIC_MAP`, `is_canonical()`, `snapshot_id`, or
   `requires_facts`, it is extending **design sketches**, not running code. Every such
   reference is flagged `[design-only]` below.
2. **The addendum's own "exists today" surface is the *current* repo**, which has moved since
   the frozen review. `RoutingPreferences` and the routing contract moved to
   `runtime/routing.py` (Debt-2 split); a `signal_registry.py` now owns the measured-signal
   vocabulary; `lab_contract.py` is at v6; `_results_summary.json` is retired as a lab input.
   The citations below are the current locations, re-verified at this branch head.

Conventions (inherited from `docs/reviews/context_abstraction_review.md:28-36`): **EXISTS / PARTIAL /
MISSING** are judged against the addendum's *definition* of the element, never a charitable
reading; citations are `file:line`; evidence classes follow the repo tags
`[M] [C] [H] [P] [X]`.

### Sources read

`docs/architecture/current/context_abstraction_design.md` (full, incl. Addendum A),
`docs/reviews/context_abstraction_review.md`, `docs/verification/context_abstraction_verify.md`,
`src/agentic_dynamics/experiment/experiment_spec.py`,
`src/agentic_dynamics/runtime/workflow_runner.py`,
`src/agentic_dynamics/runtime/routing.py`, `src/agentic_dynamics/control/step_routing.py`,
`src/agentic_dynamics/control/routing.py`, `src/agentic_dynamics/control/facts.py`,
`src/agentic_dynamics/control/context_compiler.py`, `src/agentic_dynamics/control/__init__.py`,
`src/agentic_dynamics/core/session_types.py`,
`src/agentic_dynamics/measurement/signal_registry.py`,
`src/agentic_dynamics/reporting/measurement_coverage.py`,
`src/agentic_dynamics/knowledge/knowledge.py`, `src/agentic_dynamics/knowledge/ledger_ingestion.py`,
`src/agentic_dynamics/knowledge/knowledge_ingestion.py`, `src/agentic_dynamics/knowledge/spec_ingestion.py`,
`src/agentic_dynamics/reporting/lab_contract.py`, `src/agentic_dynamics/reporting/canonical_corpus.py`,
`src/agentic_dynamics/runtime/story/models.py`,
`experiments/definitions/{routing_kb_experiment_design,rag_bare_vs_augmented,explanation_tax}.yaml`,
`experiments/CONTEXT.md`, `scripts/lab_manifest.json`.

---

## 1. Verdict in one paragraph

All three refinements are, as the addendum itself claims, **post-closure**: they extend a plane
that is still design-only, and they extend it in exactly the places the current repo is *weakest*
— where a free-form prose block stands in for a typed profile, where a retired summary file
still feeds the finding producer, and where a session's durable residue is a bulleted string and
a git log. Of the three: **I8** has a real configuration surface to generalize (`workflow.params`
blocks, `RoutingPreferences`, `signal_registry.Signal`) but **no typed profile object and no
consuming code**; **I9** has the exact contribution-lineage primitive it needs (`lab_contract.py`
v6 `record_id`/`refs_digest`) but **no `EPISTEMIC_MAP` in code** (design-only) and a retirement
edge it must not trip over (`_results_summary.json`); **I10** has the richest raw material —
`PhaseResult`/`WorkflowRunResult` are typed and written, git-derived phase completion works —
but **the four fields the checkpoint claims as DERIVED split unevenly**: `completed`,
`current_revision`, and `acceptance_state` are derivable today, while `verified_facts` and
`context_snapshot_id` have **no producer** (the fact layer and the snapshot are design-only),
and the three narrative fields (`open_hypotheses`, `failed_approaches`, `next_action`) have no
capture surface at all. **Four of the addendum's load-bearing primitives are design sketches, not
code**: `EPISTEMIC_MAP`, `is_canonical()`, `FactRequirement`/`requires_facts`, and `snapshot_id`.
The design phase must treat those four as *planned* (their reserved homes exist) rather than
*existing*, or it will hand I8/I9/I10 fields that nothing produces — the precise
`deadline_slack` failure the frozen review documented (`review.md` §3d(ii)).

---

## 2. Component audit table

| # | Addendum element | Status | What exists today (file:line) | Gap (one line) |
|---|---|---|---|---|
| **I8.1** | `DomainProfile` / `ChallengeProfile` typed objects | **MISSING** | No such dataclasses anywhere (`grep` over `src/`, `scripts/`, `tests/` returns zero non-doc hits). The addendum's schemas (`context_abstraction_design.md:1499-1517`) are sketches. | Two frozen versioned objects with no code, no home, and no consumer. |
| **I8.2** | Spec-driven "context blocks" (the profile's input surface) | **PARTIAL** | A free-form `context:` block is authored inside `workflow.params` on real specs: `experiments/definitions/routing_kb_experiment_design.yaml:25-52` (`brief`, `load_bearing_rule`, `prior_art`), `experiments/definitions/rag_bare_vs_augmented.yaml:20-30` (`prior`, `prerequisites`), `experiments/definitions/explanation_tax.yaml:23`. It lives in `Workflow.params: dict[str, Any]` (`experiment_spec.py:227`) and is **not a top-level `SPEC_KEYS` member** (`experiment_spec.py:86-118`), so it bypasses the unknown-key warning. | The block is **untyped, unvalidated prose consumed by no code**: `run_workflow` reads `rag_augment`/`rag`/`preferences`/`signals`/`fork`/`phases` from `workflow.params` (`workflow_runner.py:423,425,483,485`) but never `context` (verified by grep — zero readers in `src/` or `scripts/`). |
| **I8.3** | Contract YAML directory `experiments/contexts/` | **MISSING** | Does not exist (`ls experiments/contexts/` → nothing). The frozen design proposed it at `context_abstraction_design.md:741-743`; I4's reserved home `control/context_compiler.py:1-8` is an empty stub. | The "sole gate" the addendum promises (`context_abstraction_design.md:1495`) has no file form and no reader. |
| **I8.4** | `RoutingPreferences` (the objective language I8's `ChallengeProfile.context_requirements` would *not* reinvent) | **EXISTS** | `runtime/routing.py:88-99` `RoutingPreferences` (ordered `objectives`), `runtime/routing.py:68-84` `Objective`; parsed from `workflow.params.preferences` at `workflow_runner.py:483`; re-exported at `step_routing.py:43`. Validated by `validate_preferences` (`runtime/routing.py:192-224`) against `MEASURED_SIGNALS` (`:55`) and `FORBIDDEN_SIGNALS` (`:59`), both derived from `signal_registry` (`:20-24`). | None — this is the closest ready-made objective surface; I8's `verification_policy`/`deliberation`/`session_policy` have **no** such surface. |
| **I8.5** | A typed "profile/contract" registry to model (the closest prior art) | **PARTIAL** | `measurement/signal_registry.py:40-52` `Signal` is a frozen per-signal contract (`name`, `producer`, `evidence_class`, `scope`, `value_type`, `measured`, `permitted_consumers`, `freshness`); `SIGNALS` at `:58-118` registers each once; consumer labels `ROUTING`/`CASCADE` at `:32-37`. | It models **signals**, not **domains/challenges**. The *pattern* (one frozen registry table, producer + permitted-consumer declared per entry) is exactly what `DomainProfile`/`ChallengeProfile` need — but the object is new. |
| **I8.6** | Where profile data would persist (KB `source_type` rows) | **PARTIAL** | `SOURCE_TYPES` (`knowledge.py:125-150`) holds the per-type nominal authority/evidence; `spec` (`:147`) and `policy` (`:131`) are the two POLICY-authority precedents. `SourceTypeSpec` (`knowledge.py:104-119`) states the authority column is documentation, decided at construction time. `spec_ingestion.py:76,80,302-303` shows a declared-profile-shaped producer already exists: `source_type="spec"`, extractor `spec-lifecycle/v1`, `authority=POLICY`, `evidence_class="[P]"`, with a supersede lineage (`spec_ingestion.py:229,291`). | No `profile` row and no `profiles` producer exist; the `spec`/`policy` producers are the template a `profile` producer would copy, but profile *content* (predicates, patterns, verification tools) is not expressed by either today. |
| **I8.7** | Reserved home: `control/facts.py` vs a new `control/profiles.py` | **PARTIAL** | `control/facts.py:1-8` is reserved, by name, for `CanonicalFact` + `FACT_PREDICATES` + `EPISTEMIC_MAP` + `verify_chain` — the *fact schema*, not the profile schema. `control/__init__.py:7-9` enumerates the reserved homes and lists **no** profiles home. | Profiles are a distinct object (declared inputs to the compiler, not reduced facts); `facts.py` is committed to something else. A new `control/profiles.py` (or `experiment/profiles.py`) is the clean fit, but it is **unreserved today** and the design must name it. |
| **I8.8** | What routing already selects (`route_step`) | **EXISTS — narrow** | `step_routing.route_step` (`step_routing.py:188-233`) selects exactly one thing: a **model id** (`str`). Its inputs are the phase selector (`runtime/routing.py:153-157`: `model` pin / `allowed_models` subset) and `RouteState` (`runtime/routing.py:284-292`: `pool`, `prev_model`, `prev_session_id`, `prev_cache_read_tokens`, `context_tokens`). The only "strategy" it prices is the cache-prefix loss of a switch (`step_routing.py:76-93`). | "Routing generalizes from model routing to execution-strategy routing" (addendum A.1): **nothing** selects `deliberation` stages, `session_policy`, or `verification_policy` today. The generalization is a *new decision type*, not an extension of `route_step`. |
| **I9.1** | `EPISTEMIC_MAP` + `is_canonical()` | **[design-only]** | Both live only in the frozen design (`context_abstraction_design.md:385-399` the map; `:403-417` the predicate). In code they are *named as future contents* of `control/facts.py:3` ("Will hold `CanonicalFact`, `FACT_PREDICATES`, `EPISTEMIC_MAP`, and `verify_chain`"), and no such names exist in `src/` (`grep` — zero hits). The closest *real* mapping is `SOURCE_TYPES` nominal authority/evidence (`knowledge.py:125-150`) + the `Authority` `IntEnum` (`knowledge.py:61-85`), with `DERIVED`/`[C]` already exercised by the `report` entropy arm (`knowledge.py:130` comment). | The addendum's `"pattern": (Authority.DERIVED, "[C]")` row (`context_abstraction_design.md:1540`) is an addition to a table **that does not exist in code**. The design must land the map before the row can mean anything. |
| **I9.2** | Lab-contract v6 ref format (`source_experiment` reuses it) | **EXISTS** | `lab_contract.py:114` `CONTRACT_VERSION = "lab-contract/v6"`; the f2 contributor fields `used_record_refs_sha256`/`excluded_record_refs_sha256`/`used_unique_records`/`used_contributions` at `lab_contract.py:149-152,195-198`; `record_id()` returns the table-qualified `"<table>:<entity_id>:<knowledge_id>"` (`lab_contract.py:365-384`); `refs_digest()` hashes the sorted ref set (`lab_contract.py:352-362`). | The addendum's `source_experiment: "finding:<entity_id>:<knowledge_id>"` (`context_abstraction_design.md:1550`) is **byte-compatible** with `record_id()`'s format. No gap — this is the one reuse the addendum can take verbatim. |
| **I9.3** | Campaign results as stored today (what a pattern reducer would consume) | **PARTIAL** | Contract-bearing lab outputs: 8 `experiments/results/lab_*.json` (verified `ls`), each with a `lab_contract` block, guarded by `tests/test_lab_outputs_canonical.py`. The canonical corpus is the registry `experiments/data_manifest.json`, resolved by `canonical_corpus.py` (`TABLES = ("story","review","analysis","finding")` at `:81`; `CanonicalTables` at `:838`; `.rows()` at `:876`). The `finding` records a reducer would reduce carry structured signals — `confidence`/`perturbation_strength`/`test_executed_success` as `KnowledgeRecord` fields (`knowledge.py:342-345`) with `MEASURED`/`[M]` (`knowledge_ingestion.py:97,284-285`). | The natural pattern input (finding records) exists and is typed **on the record**, but the producer still derives findings from the **retired** `_results_summary.json` (`knowledge_ingestion.py:67`) — the same summary `experiments/CONTEXT.md` declares "not a build input and not a lab input". A pattern reducer must consume the *registry's* finding rows, not re-read the retired summary. |
| **I10.1** | `PhaseResult` / `WorkflowRunResult` fields | **EXISTS** | `PhaseResult` (`workflow_runner.py:75-150`): `phase`, `kind`, `status`, `spec_id`, `model`, `duration_s`, `commit_hash`, `error`, `tokens` (dict with `in/out/reasoning/answer/explanation/total`, written at `:605-612`), `cost_usd`, `cache_read_tokens`/`cache_write_tokens`/`cache_hit_rate`, `session_id`, `files_created/modified`, `final_response`, `confidence`, augmentation provenance (`raw_prompt_hash` … `fallback_mode`), `test_executed_success`, `tests_passed/total`. `WorkflowRunResult` (`workflow_runner.py:153-190`): `spec_name`, `model`, `workdir`, `goal`, `phases`, `spec_id`, `git_sha`, `started_at`, `ended_at`, plus `total_cost_usd` (`:170-171`) and `ok` (`:174-175`). | None — these are the richest typed L0 the repo has, and the checkpoint's DERIVED fields map onto them directly (see §3c). |
| **I10.2** | Ledger attempt fields (`parent_attempt_id`, `escalation_from/to`, `cache_hit`, `tokens`) | **PARTIAL** | **Declared** in `LEDGER_FIELDS` (`experiment_spec.py:159-176`): `attempt_number`, `parent_attempt_id`, `retry_reason`, `escalation_from`, `escalation_to`, `cache_hit`, `tool_calls`, `first_pass`, `accepted` — with **zero writers** outside the declaration (re-verified; cf. `review.md` §3d(ii)). **Written** attempt data is `PhaseResult` (above) and the KB projection `ledger_attempt` (`ledger_ingestion.py:204-269`), which stores tokens/cost/confidence as a **formatted prose string** (`ledger_ingestion.py:243`) and only `commit_sha`/`extractor_version`/`language`/`test_executed_success`/`confidence`/`perturbation_strength` as typed extras (`:259-267`). `cache_hit` (LEDGER name) ≠ `cache_hit_rate`/`cache_read_tokens` (`workflow_runner.py:93-95`) — a naming mismatch, not a measurement gap. | Retry/escalation lineage — the very thing I10's `failed_approaches`/fork provenance would stand on — is **declared but never written**. A checkpoint that claims attempt lineage is claiming data that does not exist. |
| **I10.3** | `snapshot_id` definition (§6.4) | **[design-only]** | Formula at `context_abstraction_design.md:925-947` (`sha256(contract_version | decision_type | scope_path | sorted(fact_ids) | digest(unknowns) | digest(conflicts) | digest(stale))`, `compiled_at` excluded). No code produces it: `control/context_compiler.py:1-8` is an empty stub, and `snapshot_id`/`ControlContext` exist nowhere in `src/` (`grep` — zero hits). | The checkpoint field `context_snapshot_id` (`context_abstraction_design.md:1577`) references an identity **nothing computes today**. It is the single most producer-less field in the addendum. |
| **I10.4** | `session_types` vocabulary | **EXISTS — partial overlap** | `core/session_types.py` is the single task-type/session-pattern vocabulary: `TASK_TYPES` (`:40-42`: `greenfield, feature_addition, integration, refactor, cross_cutting`), `DEFAULT_TASK_TYPE` (`:44`), `EXPERIMENT_SESSION_PATTERNS` (`:55-65`), `normalize_task` (`:68-74`). Consumed by `story.SessionSpec.task_type` (`runtime/story/models.py:23`) and `control.routing` (`routing.py:14`). | The addendum's `ChallengeProfile.challenge` values (`greenfield | cross_cutting | small_change | research | incident | migration`, `context_abstraction_design.md:1512-1513`) **overlap but do not equal** `TASK_TYPES` — two vocabularies for the same axis. The design must reconcile them or declare the mapping. |
| **I10.5** | Session continuation/fork machinery (what I10 turns into a CAP decision) | **EXISTS — as token economics** | Fork is cache-continuity: `fork_enabled` (`workflow_runner.py:476`), `session_id`/`fork` only when `prev_model == model_i` (`workflow_runner.py:591-597`), the `prev_session_id`/`prev_model`/`prev_cache_read_tokens` chain (`workflow_runner.py:490-492,618-623`), priced by `cache_switch_penalty` (`step_routing.py:76-93`). | Exactly the addendum's target: continuation/fork is today a **token-management detail** (cache reads), with no typed residue beyond `session_id` on `PhaseResult` (`workflow_runner.py:96`). The checkpoint-as-decision does not exist. |

**Summary: EXISTS (4) — `RoutingPreferences`/objective language (I8.4), `route_step`'s model
selection (I8.8), the lab-contract v6 ref format (I9.2), `PhaseResult`/`WorkflowRunResult`
(I10.1); [design-only] (2) — `EPISTEMIC_MAP`/`is_canonical` (I9.1), `snapshot_id` (I10.3);
MISSING (3) — the profile objects (I8.1), the contract directory (I8.3), the whole profile
generalization of routing (inside I8.8); PARTIAL (the rest).** The distribution is the story: the
addendum is **not** greenfield — its reuse targets (`record_id`, `RoutingPreferences`,
`PhaseResult`, `signal_registry.Signal`) are real and current — but its four load-bearing
*extensions* sit on top of a plane that is still design-only, and one of its reuse targets
(`_results_summary.json`) is retired.

---

## 3. The three refinements, grounded in code

### 3a. I8 — the profile input surface exists as prose, and no code consumes it

The addendum's thesis for I8 is that the "shared execution experience plus a small filtered
domain context" framing is "made literal" — a domain-generic kernel, a profile as the filter, the
contract as the gate (`context_abstraction_design.md:1524-1526`). The repository already has
*three* surfaces a profile could generalize, at three different degrees of typing:

1. **The `workflow.params.context` block — prose, unvalidated, unread.** Three committed specs
   author a `context:` block with real content (`routing_kb_experiment_design.yaml:25-52`,
   `rag_bare_vs_augmented.yaml:20-30`, `explanation_tax.yaml:23`). But `Workflow.params` is
   `dict[str, Any]` (`experiment_spec.py:227`), `context` is **not** in `SPEC_KEYS`
   (`experiment_spec.py:86-118`) so it never trips the unknown-key warning (`experiment_spec.py:533-540`),
   and `run_workflow` reads seven distinct `workflow.params` keys — `rag_augment`, `rag`,
   `preferences`, `signals`, `fork`, `phases`, `language`/`model_pool` (`workflow_runner.py:423,425,483,485,476`)
   — but **never `context`**. The block is authored prose the LLM phases themselves may read from
   the spec file; it is not data the compiler or runner acts on. This is precisely the shape the
   frozen review's §3d(iv) called the "prose-projection defect", one level up.
2. **`workflow.params.preferences` — typed, validated, but model-only.** `RoutingPreferences`
   (`runtime/routing.py:88-99`) is the one profile-shaped object that *is* consumed: parsed
   (`workflow_runner.py:483`), validated against the measured-signal vocabulary
   (`runtime/routing.py:192-224`), and scored (`step_routing.py:115-165`). Its `Objective`
   (`runtime/routing.py:68-84`) is the objective language the frozen design §6.1 already decided
   the contract should *reuse* rather than reinvent (`context_abstraction_design.md:781-782`).
   I8's `ChallengeProfile.context_requirements`/`verification_policy`/`deliberation`/`session_policy`
   (`context_abstraction_design.md:1514-1517`) have **no** analogous typed surface — the design
   must decide whether these are new `RoutingPreferences`-style blocks, new `signal_registry`-style
   registry rows, or new `context:`-block fields.
3. **`signal_registry.Signal` — the right *shape*, the wrong *object*.** `Signal`
   (`measurement/signal_registry.py:40-52`) already does the thing a profile needs most: it
   declares, once, per signal, its producer, evidence class, scope, value type, measured status,
   and **permitted consumers** (`permitted_consumers`, with `ROUTING`/`CASCADE` labels at
   `:32-37`). A `DomainProfile`/`ChallengeProfile` registry would be this pattern lifted from
   signals to domains/challenges. The `verified`-vs-`declared` distinction the profile needs is
   *also* already half-expressed: `signal_registry` marks `measured` vs `not instrumented`
   (`:93-96`), and the addendum's "profiles are declared (POLICY), their performance is measured
   later" (`context_abstraction_design.md:1530-1532`) maps onto that exact axis.

**Where profile data would persist:** the KB already has the *envelope* for a declared profile —
`source_type="spec"` is a POLICY-authority, supersede-carrying producer (`spec_ingestion.py:76,80,302-303,229,291`),
and `SOURCE_TYPES` is explicitly open to additive registration (`knowledge.py:100-101` "a
brand-new `source_type` introduced later defaults to observation"). A `profile` `source_type`
registering `SourceTypeSpec("observation", Authority.POLICY, "[P]")` is a copy of the `spec` row
(`knowledge.py:147`), not a new mechanism. **The reserved home is `control/facts.py` *only* for the
fact schema** (`facts.py:1-8`); profiles are inputs, not facts, and `control/__init__.py:7-9`
lists no profiles home — so the design must reserve one (a new `control/profiles.py`, or the
`experiment` plane where the compiler's inputs already live).

**What routing already selects:** `route_step` (`step_routing.py:188-233`) returns a **single
model id**. Its `RouteState` has five fields, all model/cache economics
(`runtime/routing.py:284-292`). Nothing in it selects *stages*, *verification*, or *session
policy*. The addendum's "execution-strategy routing" (`context_abstraction_design.md:1484`) is a
**new decision type** whose `allowed_actions`/contract do not exist (`experiments/contexts/` is
absent, §I8.3) — not a field added to `route_step`.

### 3b. I9 — the pattern class is one additive row on a table that is still design-only

The addendum's I9 is the smallest increment — one `EPISTEMIC_MAP` row plus a required payload
(`context_abstraction_design.md:1538-1551`). Its audit reduces to two facts:

1. **The map it extends does not exist in code.** `EPISTEMIC_MAP` and `is_canonical()` are
   `context_abstraction_design.md:385-417`, and `control/facts.py:3` names them as *future*
   contents of a reserved stub. The nearest real machinery is `SOURCE_TYPES` (`knowledge.py:125-150`),
   whose nominal authority/evidence columns are *documentation, not a validator*
   (`knowledge.py:110-113`) — the `DERIVED`/`[C]` pairing the `pattern` row wants is already
   conventional there (`knowledge.py:130`). So `"pattern": (Authority.DERIVED, "[C]")` is a
   one-line addition to a table that has to be *built first* (I0). The addendum's hard rule —
   "minted only by a deterministic reducer… an LLM may propose only ADVISORY"
   (`context_abstraction_design.md:1553-1554`) — has its enforcement point in `is_canonical()`,
   which is design-only; **there is no code today that structurally excludes an ADVISORY fact from
   a control path**, because the control path itself is not built.
2. **Its `source_experiment` reuse is exact — but its input corpus has a retirement edge.**
   `record_id()` produces `"<table>:<entity_id>:<knowledge_id>"` (`lab_contract.py:365-384`), and
   the addendum's `source_experiment: "finding:<entity_id>:<knowledge_id>"`
   (`context_abstraction_design.md:1550`) is that format verbatim; `refs_digest()`
   (`lab_contract.py:352-362`) is the deterministic hash a `PatternPayload` would fold its
   evidence refs into. The finding records to reduce over are typed on the record
   (`knowledge.py:342-345`) and carried as `MEASURED`/`[M]` (`knowledge_ingestion.py:97,284-285`).
   **But** the finding producer still reads `_results_summary.json` (`knowledge_ingestion.py:67`),
   the file `experiments/CONTEXT.md` declares retired ("not a build input and not a lab input").
   A pattern reducer must consume the canonical corpus (`canonical_corpus.TABLES`,
   `canonical_corpus.py:81`) — the *registry's* finding rows — and the design must state that
   plainly, or it will cite a retired artifact as evidence.

### 3c. I10 — the checkpoint's DERIVED/ADVISORY split, checked field-by-field

The addendum's `SessionCheckpoint` (`context_abstraction_design.md:1567-1578`) claims six
DERIVED fields and three ADVISORY. Checked against what actually exists:

| `SessionCheckpoint` field | Claimed grade (`design.md:1570-1577`) | Actually derivable today? |
|---|---|---|
| `goal` | — | **YES** `[M]` — `WorkflowRunResult.goal` (`workflow_runner.py:160`), threaded to every phase (`workflow_runner.py:440`). |
| `completed` | DERIVED | **YES** `[M]` — `_completed_phases` greps `[workflow] <phase>` commit markers (`workflow_runner.py:235-254`), with an index fallback (`:290-328`); also `PhaseResult.status` (`workflow_runner.py:81`). |
| `current_revision` | DERIVED | **YES** `[M]` — `_git_head` (`workflow_runner.py:227-232`), `WorkflowRunResult.git_sha` (`:165`), `PhaseResult.commit_hash` (`:88`). |
| `verified_facts` | DERIVED | **NO** — there are no canonical facts (`control/facts.py:1-8` is a stub). The nearest field is `PhaseResult.selected_evidence_ids` (`workflow_runner.py:106`), which is RAG *retrieval* evidence, not canonical facts. Claiming "canonical fact ids, by reference" is claiming a layer that does not exist. |
| `open_hypotheses` | ADVISORY | **NO capture surface** — nothing records a session's hypotheses; `PhaseResult.final_response` (`workflow_runner.py:99`) is the only raw text, unparsed. |
| `failed_approaches` | ADVISORY | **PARTIAL** — `PhaseResult.error`/`status=failed` (`workflow_runner.py:89,81`) record *that* a phase failed, but no per-approach narration; `retry_reason` is declared-and-unwritten (`experiment_spec.py:161`). |
| `next_action` | ADVISORY | **NO capture surface** — nothing proposes a next action; there is no decision envelope (`control/decisions.py:1-8` is a stub). |
| `acceptance_state` | DERIVED | **YES** `[C]` — `test_executed_success` (`workflow_runner.py:113`) + `status` (`:81`); but `first_pass`/`accepted` (the *full* acceptance vocabulary) are declared-and-unwritten (`experiment_spec.py:175-176`). |
| `context_snapshot_id` | — | **NO** — `snapshot_id` has no producer (`control/context_compiler.py:1-8`; formula at `context_abstraction_design.md:925-947` is design-only). |

So the split is **three derivable (`completed`, `current_revision`, `acceptance_state`), two
producer-less (`verified_facts`, `context_snapshot_id`), and three with no capture surface
(`open_hypotheses`, `next_action`, `failed_approaches` half-captured)**. The design must either
(i) instrument the two producer-less DERIVED fields (which requires I0/I4 to land first), or
(ii) demote them to ADVISORY/absent in the checkpoint's v1 — the same measure-before-policy call
the frozen design made for `budget_remaining`/`deadline_slack` (`context_abstraction_design.md:1289-1295`).

**The `session_routing` invariants** the addendum states (`context_abstraction_design.md:1580-1584`):
`continue` requires equal `context_snapshot_id` + unchanged goal/phase/model; `fork` requires a
checkpoint; `escalate` requires a checkpoint + model change. Today the *only* analogous logic is
the fork chain (`workflow_runner.py:591-597`), which keys off `prev_model == model_i` alone — it
has no notion of snapshot identity (none exists) and no notion of a checkpoint. I10's whole
decision vocabulary is greenfield.

---

## 4. Claims that do NOT hold (or hold only under a narrower reading)

1. **"The contract remains the sole gate" (`context_abstraction_design.md:1494-1496`) assumes a
   gate and a contract.** The contract directory `experiments/contexts/` does not exist (§I8.3),
   and `requires_facts`/`FactRequirement` are design-only (`context_abstraction_design.md:959-985`;
   the reserved home `core/contracts.py:1-8` is empty). The sole-gate property is a *promise about
   code that is not written*. The design must not claim a profile "cannot widen a controller's
   view" as an established fact — it is a constraint to be enforced by I5's `validate_fact_contracts`,
   which does not exist.
2. **I8's "profiles are L4's producer" (`context_abstraction_design.md:1488-1490`) is the
   `LEDGER_FIELDS` trap re-entered unless the non-empty-producer invariant lands first.** The
   frozen design's own fix for "declared but written by nothing" is `PredicateSpec.produced_by`
   non-empty (`context_abstraction_design.md:444-448`) — also design-only. Profiles are declared
   (POLICY) at construction; that is *fine* only because a declared fact has an author (the
   operator). But the profile's `predicates`/`patterns`/`policies` fields point at fact ids that
   must each have a producer, or the profile is a bag of dangling names — the exact defect
   `review.md` §3d(ii) documented (23 `LEDGER_FIELDS` names, zero writers).
3. **I9's "`is_canonical()` unchanged" (`context_abstraction_design.md:1555`) presumes an
   `is_canonical()` to leave unchanged.** It does not exist in code (`facts.py:3` names it as
   future). "Unchanged" can only mean "unchanged from the design sketch"; the design phase should
   say so rather than implying a stable, tested predicate.
4. **I10's `verified_facts` as DERIVED is the sharpest over-claim.** "canonical fact ids, by
   reference" (`context_abstraction_design.md:1572`) requires canonical facts to exist. They do
   not (`control/facts.py:1-8` is a stub; no `source_type="fact"` in `SOURCE_TYPES`,
   `knowledge.py:125-150`). As written, a v1 checkpoint would carry this field empty forever —
   the same shape as `deadline_slack` passing today's gate (`review.md` §4.4.1).
5. **The `challenge` vocabulary collides with `TASK_TYPES`.** `ChallengeProfile.challenge` is
   `greenfield | cross_cutting | small_change | research | incident | migration`
   (`context_abstraction_design.md:1512-1513`); `TASK_TYPES` is `greenfield | feature_addition |
   integration | refactor | cross_cutting` (`core/session_types.py:40-42`). Two of the six
   challenge values are already task types, four are new, and `feature_addition`/`integration`/
   `refactor` are task types with no challenge counterpart. The repo *just* consolidated
   session/task vocabularies into one leaf module (`session_types.py:1-28`, "the one source of
   truth"); the design must not re-fork it by introducing a parallel axis without a declared
   mapping.

---

## 5. What the design phase inherits (constraints)

1. **Treat `EPISTEMIC_MAP`, `is_canonical()`, `FactRequirement`, and `snapshot_id` as planned,
   not existing.** All four are design sketches with empty reserved homes (`control/facts.py:1-8`,
   `core/contracts.py:1-8`, `control/context_compiler.py:1-8`). The addendum design's schemas
   must therefore state, per field, whether it is *new-in-I8/I9/I10* or *waits-on-I0/I4/I5* — or
   it hands a field to a consumer that can never be filled.
2. **A profile is a `source_type` registration, not a new store.** Persist profiles exactly as
   `spec`/`policy` are persisted: additive `SOURCE_TYPES` row (POLICY/`[P]`, `knowledge.py:147`),
   a `profiles` producer copying `spec_ingestion.py`'s shape (`:235-303`), supersede lineage for
   versioning (`:229,291`). No new transport (hard rule 2).
3. **The contract/objective reuse is already decided — honor it.** The frozen design says the
   contract reuses `RoutingPreferences`' objective language rather than inventing a third
   (`context_abstraction_design.md:1434`). I8's `context_requirements` must resolve through the
   same vocabulary, or it reproduces the "gate already duplicated" defect (`review.md` §4.4).
4. **A pattern reducer consumes the canonical corpus, not `_results_summary.json`.** The summary
   is retired as a lab/build input (`experiments/CONTEXT.md`); the reducer's input is
   `canonical_corpus.TABLES` (`canonical_corpus.py:81`) finding/review rows, and its
   `source_experiment`/evidence refs use `record_id()` (`lab_contract.py:365-384`) + `refs_digest()`
   (`:352-362`), not a new cite format.
5. **Reserve a profiles home explicitly.** `control/facts.py` is committed to the fact schema
   (`facts.py:1-8`); profiles are compiler inputs. The design must name a new home (candidate:
   `control/profiles.py`, or the `experiment` plane) and extend `control/__init__.py:7-9`'s
   reserved-homes list, in the same zero-call-sites style the CAP homes already use.
6. **The checkpoint's DERIVED fields that have no producer must be demoted, not silently empty.**
   `verified_facts` and `context_snapshot_id` cannot be DERIVED in v1. Either demote to
   ADVISORY/absent (with an explicit `unknown`), or gate I10 on I0/I4 landing — the design must
   choose, mirroring the frozen design's `budget_remaining` decision
   (`context_abstraction_design.md:1289-1295`).

---

## 6. Open questions (the design must answer these with schemas) + hard-rule risks

### OQ1 — I8: what is a `DomainProfile` *in the storage model*, and what is its `entity_id`?

`DomainProfile`/`ChallengeProfile` are declared (POLICY) objects. Give the schema for: (a) the
`source_type` row (name, message family, nominal authority/evidence), (b) the `entity_id`/`source_uri`
/`logical_locator` triple that makes a profile a version-chain record (per
`knowledge.compute_entity_id`, `knowledge.py:192-199`), and (c) how a profile *supersedes* (the
`spec_ingestion.py:229,291` precedent) without colliding with a spec record. Is a profile one
record per (domain, version) or one record per (domain, predicate) bundle?

### OQ2 — I8: how do `context_requirements` resolve through `requires_facts` without a third gate?

`ChallengeProfile.context_requirements: tuple[FactRequirement, ...]`
(`context_abstraction_design.md:1514`) names `FactRequirement`, which is design-only. Give the
schema for how a profile's requirements compose with a decision-type contract's `requires_facts`
(§6.1/§7) *and* the existing `validate_preferences` (`runtime/routing.py:192-224`) — or state
plainly that profiles are compiled by the same I5 validator and no profile field bypasses it.

### OQ3 — I8: what does "execution-strategy routing" select, and what is its `allowed_actions`?

`route_step` selects a model (`step_routing.py:188-233`). Give the new decision type's contract
(`experiments/contexts/<decision_type>.yaml`, absent today), its `allowed_actions` vocabulary, and
the exact inputs it reads that `RouteState` (`runtime/routing.py:284-292`) does not. Name the
reference baseline it is measured against (the addendum says routing generalizes; against what
incumbent, and with which `compare_arms` loss?).

### OQ4 — I9: what is the reducer's input contract, and where does `support` come from?

`PatternPayload` requires `support: int` ("n of observations") and `uncertainty`
(`context_abstraction_design.md:1547-1548`). Give the reducer signature (`consumes`/`produces`),
name the exact corpus slice (finding table via `canonical_corpus`, `:81`) and the population
definition (`population: str`), and state how `support`/`uncertainty` are computed from real
records — with the coverage invariant "unavailable = null, never zero"
(`measurement_coverage.py:20-21`) as the boundary on fabrication.

### OQ5 — I9: how is the `pattern` row's authority made non-colliding with `DERIVED` facts?

`"pattern": (Authority.DERIVED, "[C]")` (`context_abstraction_design.md:1540`) is a *nominal*
authority on `SOURCE_TYPES` (`knowledge.py:110-113`: documentation, not a validator). Give the
`EPISTEMIC_MAP` row plus the `PatternPayload` → `CanonicalFact` field mapping, and the
`is_canonical()` interaction that keeps an LLM-proposed ADVISORY pattern structurally uncitable.

### OQ6 — I10: which checkpoint fields are v1-DERIVABLE, and what is the demotion rule?

Per §3c, `completed`/`current_revision`/`acceptance_state` are derivable; `verified_facts`/
`context_snapshot_id` have no producer; three narrative fields have no capture surface. Give the
v1 `SessionCheckpoint` schema with the *final* grade per field, the `on_missing`/`unknown` form
for the producer-less two, and whether `open_hypotheses`/`failed_approaches`/`next_action` are
ADVISORY annotations on the checkpoint record or separate `source_type` rows.

### OQ7 — I10: what is the `session_routing` decision's identity and the snapshot it binds?

`continue` requires `context_snapshot_id` equality (`context_abstraction_design.md:1581-1584`).
Given `snapshot_id` is design-only, give the `session_routing` contract (absent today), its
`snapshot_id` semantics for a *session* (a session has no single `decision_type`), and how the
fork invariants are validated when no snapshot producer exists in v1. Does the shadow-mode
session policy (`context_abstraction_design.md:1594-1595`) record decisions through the existing
`actuation` envelope (`actuation_ingestion.py`, `knowledge.py:149`), or a new observation type?

### Hard-rule risks per increment

| Increment | Hard rule at risk | The specific failure mode |
|---|---|---|
| **I8** | (6) generalized load-bearing rule / measure-before-policy | Profiles are declared (POLICY) with no producer; their `predicates`/`patterns`/`policies` point at fact ids. If any named fact lacks a producer, the profile is a bag of dangling names — the `LEDGER_FIELDS` failure (`review.md` §3d(ii)) at the profile level. |
| **I8** | (7) don't fork the gate | `context_requirements` vs `requires_facts` vs `validate_preferences` (`runtime/routing.py:192-224`) — three vocabularies for "what may this decision see" is exactly the duplication `review.md` §4.4 flagged. |
| **I9** | (3) deterministic reducers only; LLM → ADVISORY | `is_canonical()` is design-only; until it (and C5) exist, nothing structurally excludes an LLM-proposed pattern from a control path. The reducer must be pure (injected clock, `record_factory`'s discipline), or `support`/`uncertainty` become fabrication. |
| **I9** | (data-integrity) no retired inputs | `_results_summary.json` is retired as a lab/build input (`experiments/CONTEXT.md`) yet still feeds the finding producer (`knowledge_ingestion.py:67`). A pattern reducer reading it directly would cite a quarantined artifact. |
| **I10** | (6) no producerless fields | `verified_facts` and `context_snapshot_id` are DERIVED-claimed but producer-less (no facts, no snapshot). Shipping them as DERIVED is the `deadline_slack` failure (`review.md` §4.4.1) verbatim. |
| **I10** | (5) observe-only rail / (8.6) no automated actuation | `session_routing` proposes `fork`/`escalate` — actuation-shaped actions. `AUTOMATABLE_ACTIONS` is `{continue, route}` (`context_abstraction_design.md:1196`); `fork`/`escalate` must stay shadow-mode/recorded until the evidence-seed experiment, or the human-gated boundary is crossed. |

---

## Appendix — citation index

| Concern | Primary citations |
|---|---|
| Profile input surfaces (context block, preferences, signals) | `experiments/definitions/routing_kb_experiment_design.yaml:25-52`; `rag_bare_vs_augmented.yaml:20-30`; `explanation_tax.yaml:23`; `experiment_spec.py:86-118,227,533-540`; `workflow_runner.py:423,425,476,483,485` |
| Routing contract + `route_step` + `RouteState` | `runtime/routing.py:42-52,55,59,68-84,88-99,153-157,192-224,284-292`; `step_routing.py:76-93,115-165,188-233` |
| Signal registry (profile-shape prior art) | `measurement/signal_registry.py:32-37,40-52,58-118` |
| KB `source_type` + authority + identity | `knowledge.py:61-85,100-119,125-150,192-211`; `spec_ingestion.py:76,80,229,235-303` |
| Reserved CAP homes | `control/__init__.py:7-9`; `control/facts.py:1-8`; `control/context_compiler.py:1-8`; `core/contracts.py:1-8`; `control/decisions.py:1-8` |
| Lab contract v6 + corpus | `lab_contract.py:114,149-152,195-198,352-362,365-384`; `canonical_corpus.py:81,838,876`; `experiments/CONTEXT.md` (retired summary) |
| Finding producer + structured signals | `knowledge_ingestion.py:67,97,249-250`; `knowledge.py:342-345` |
| Phase/run ledger + fork + git completion | `workflow_runner.py:75-150,153-190,227-254,290-328,476,490-492,591-597,605-612,618-623` |
| Declared-but-unwritten attempt fields | `experiment_spec.py:135-194` (esp. `:159-176`); `ledger_ingestion.py:173,204-269` |
| Session/task vocabulary | `core/session_types.py:40-74`; `runtime/story/models.py:23` |
| Coverage primitive (null-not-zero) | `measurement_coverage.py:20-21,55-83,111-131` |
| Frozen design anchors (§3.4, §6.4, Addendum A) | `context_abstraction_design.md:385-417,925-947,1482-1604` |

---

## Log

| Check | Result |
|---|---|
| Every "exists today" claim carries `file:line` | **PASS** — §2 and §3 cite current locations, re-verified at branch head `feature/cap-addendum-design`. |
| Design-only boundary: no `src/`/`scripts/`/`tests/`/`admin/` modified | **PASS** — `git status --porcelain` shows only this new file. |
| Adversarial critique (claims that do not hold) | **PASS** — §4, five items. |
| Numbered OQ list with schema requirements | **PASS** — §6, OQ1–OQ7. |
| Hard-rule risk per increment | **PASS** — §6 table. |
