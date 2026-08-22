---
status: accepted
---
# Context Abstraction Plane — Addendum A Review (I8–I10) — audit phase

**Refinements under audit:** I8 (`DomainProfile` / `ChallengeProfile`), I9 (`pattern` epistemic
class), I10 (typed session checkpoint) — the three post-closure increments of the frozen
design's Addendum A (`docs/designs/current/context_abstraction_design.md` §§A.1–A.5).
**Phase:** `review` (phase 1 of 3 — `review` → `design` → `verify`) of the follow-up
design-only spec the addendum itself mandates (`design.md:1468-1472`).
**Prior phases (frozen, unchanged):** `docs/context_abstraction/review.md`,
`docs/context_abstraction/design.md`, `docs/context_abstraction/verify.md`.
**Date:** 2026-08-22 · **Branch:** `feature/cap-addendum-design`
**Deliverable rule:** design-only. This phase adds exactly one file
(`docs/designs/current/context_abstraction_addendum_review.md`) and modifies nothing under
`src/`, `scripts/`, `tests/`, `apps/`, or `experiments/`.

---

## 0. What this document is, and how to read it

This is an **audit** of three increments, not a design of them. Its job is to establish, with
citations a reader can check, what the repository already implements of each refinement's
inputs and targets, and what the refinement silently assumes exists. The design phase then
builds only what is genuinely missing.

There is one structural fact that reshapes this audit relative to the frozen review, and it
must be stated before the tables:

> **The plane these increments refine does not exist in code yet.** Every CAP object the
> addendum builds on — `CanonicalFact`, `EPISTEMIC_MAP`, the reducers, the Context Compiler,
> `snapshot_id`, the `experiments/contexts/` contract directory — is *design-only*. The
> repository holds only **reserved homes** for them: `control/facts.py:1-8` (I0),
> `control/reducers/__init__.py:1-9` (I1–I3), `control/context_compiler.py:1-8` (I4),
> `core/contracts.py:1-8` (I5), `control/rules.py:1-8` + `control/validator.py:1-8` +
> `control/decisions.py:1-8` (I6), all documented as "frozen until post-consolidation CAP
> implementation" (`control/__init__.py:7-9`).

Consequently this review cites on **two planes**, and marks which:

- **CODE citations** (`file:line`) — the thing exists today and is auditable against the tree.
- **DESIGN citations** (`design.md:§…`) — the thing is part of the frozen design (or its
  addendum), *not* code. Where an addendum claim assumes a DESIGN-only object as if it were
  code, that is itself a finding (see §4, finding A-1).

Conventions are otherwise the frozen review's: EXISTS / PARTIAL / MISSING are judged against
the *refinement's* definition; PARTIAL never means "vaguely adjacent"; evidence classes are
`[M]/[C]/[H]/[P]/[X]`.

### Sources read

`docs/designs/current/context_abstraction_design.md` (frozen §§1–13 + Addendum A),
`docs/context_abstraction/review.md`, `docs/context_abstraction/verify.md`,
`src/agentic_dynamics/control/{facts,context_compiler,reducers/__init__,rules,validator,decisions,step_routing,routing}.py`,
`src/agentic_dynamics/control/__init__.py`,
`src/agentic_dynamics/runtime/{routing,workflow_runner}.py`,
`src/agentic_dynamics/runtime/story/models.py`,
`src/agentic_dynamics/experiment/experiment_spec.py`,
`src/agentic_dynamics/knowledge/{knowledge,ledger_ingestion}.py`,
`src/agentic_dynamics/reporting/{lab_contract,measurement_coverage}.py`,
`src/agentic_dynamics/core/{session_types,contracts}.py`,
`experiments/results/` (registry index + lab artifacts), `scripts/generate_manifest.py`.

---

## 1. Verdict in one paragraph

The three increments split cleanly by *where their inputs live*. **I8 (profiles)** has real,
working inputs — the spec `workflow.params` block, `RoutingPreferences`, the `SOURCE_TYPES`
vocabulary — but no destination: there is no profile record family, no profile file, no
profile key in the spec schema, and no reserved home for one. **I9 (patterns)** has a real,
rich input surface — the lab-contract v6 contribution lineage, the campaign results corpus,
the registry — but its *target* (`pattern` in `EPISTEMIC_MAP`) is additive to a map that is
itself not yet implemented. **I10 (checkpoint)** is the reverse: its target is well-specified
and its deterministic components *are* derivable today from `PhaseResult`/`WorkflowRunResult`
and the fork chain, but two of its fields (`verified_facts`, `context_snapshot_id`) name CAP
objects that do not exist, and the attempt-lineage ledger fields the fork decision implies
(`parent_attempt_id`, `escalation_from/to`) are declared-and-unwritten. The one risk shared by
all three is the same one the frozen design itself warns about: **profiles, patterns, and
checkpoints are all facts, and the fact layer is a forward reference** — so the increments'
measure-before-policy discipline must hold against a plane that cannot yet persist a single
fact.

---

## 2. Component audit table

| # | Refinement element | Status | What exists today (citations) | Gap (one line) |
|---|---|---|---|---|
| I8 | `DomainProfile` / `ChallengeProfile` | **MISSING** (inputs PARTIAL) | Config surfaces exist: `ExperimentSpec.workflow.params` free-form dict (`experiment_spec.py:223-236`, consumed at `workflow_runner.py:403,411-414,422-425,476,481-488`); `RoutingPreferences`/`Objective` (`runtime/routing.py:67-99`); `StepSelector`/`parse_step_selector` (`runtime/routing.py:144-157`). Persistence vocabulary exists: `SOURCE_TYPES` (`knowledge.py:125-150`) with `Authority` ordering (`knowledge.py:61-85`) — but no `profile` (or `fact`) row. Routing selects a **model only** (`step_routing.py:188-233`) | No profile object, no profile source_type/predicate, no spec key, no reserved home (`control/profiles.py` absent; `control/__init__.py:7-9` reserves no profile home) |
| I9 | `pattern` epistemic class + payload | **MISSING** (input lineage EXISTS) | `EPISTEMIC_MAP`/`is_canonical()` are DESIGN-only (`design.md:382-417`; reserved home `control/facts.py:1-8`). Lab-contract v6 contribution lineage is CODE: `lab_contract.py:114,135-154,213-248,352-384`. Campaign corpus is CODE+data: lab JSONs + `_results_summary.json` + `registry_index.jsonl` + `kb/<knowledge_id>.json` | No `pattern` row exists (the map it extends is itself unimplemented); no reducer consumes the corpus yet (`control/reducers/__init__.py:1-9` empty) |
| I10 | typed session checkpoint | **PARTIAL** | Deterministic fields derivable from `PhaseResult`/`WorkflowRunResult` (`workflow_runner.py:75-190`) and the fork chain (`:490-492,596-597,620-621`); story-side continuation signals exist (`story/models.py:105-106,113-115`). But `snapshot_id` is DESIGN-only (`design.md:925-947`; `context_compiler.py:1-8` empty), and `parent_attempt_id`/`escalation_from/to`/`cache_hit` are declared-unwritten (`experiment_spec.py:160-163,172`) | Two checkpoint fields name CAP objects that do not exist; the fork-lineage ledger fields the session-routing decision consumes are unmeasured |

**Distribution:** all three increments are greenfield *at the plane level* — none of I8/I9/I10
is "already partially built" the way the actuation envelope was (§4.1 of the frozen review).
What differs is the *input* readiness: I8's inputs are ~complete, I9's inputs are complete and
rich, I10's inputs are complete *except* for the two CAP-object fields. That ordering should
dictate the design's increment order, not the addendum's I8→I9→I10 numbering (§6, OQ-9).

---

## 3. I8 — profiles (what exists, where it would persist, which home fits, what routing selects)

### 3a. Configuration surfaces that exist today

Three surfaces exist, and none of them is a profile:

1. **The spec context block = `workflow.params`.** This is a free-form `dict`
   (`Workflow.params`, `experiment_spec.py:223-236`) with no declared schema. In practice it
   is where per-run context lives: `phases` (`workflow_runner.py:403`), `language`
   (`:411-414`), `rag_augment` + the `rag` sub-dict (`:422-425`), `fork` (`:476`), and the
   routing triple `model_pool` / `preferences` / `signals` (`:481-488`). This is the closest
   thing today to a "spec context block," and it is **the** place a `DomainProfile`'s
   `predicates`/`verification` or a `ChallengeProfile`'s `context_requirements` would have to
   *attach to* the spec — but the top-level `SPEC_KEYS` vocabulary
   (`experiment_spec.py:86-118`) has no `profiles`, `domain`, or `challenge` key, so a profile
   cannot be authored in a spec YAML without a schema change.
2. **`RoutingPreferences` + `Objective`.** The only *typed* preference surface today
   (`runtime/routing.py:67-99`): an ordered list of `{signal, direction, weight}` over the
   measured signal vocabulary (`MEASURED_SIGNALS`/`FORBIDDEN_SIGNALS`, `:55-59`). The frozen
   design explicitly reuses this as its contract `objectives` language (`design.md:780-789`)
   rather than inventing a second one — the same reuse is available to `ChallengeProfile`.
3. **`StepSelector` / `parse_step_selector` / `validate_step_selector`** (`runtime/routing.py:144-186`):
   the per-phase pin / allowed-subset / full-pool semantics that a profile's
   "execution-strategy routing" would generalize *from*.

**The contract YAML directory does not exist.** `experiments/contexts/` is absent from the
tree (verified: no such directory), and the one contract the frozen design defines,
`route_next_job/v1`, is specified in prose at `design.md:739-822`, not as a file. A
`ChallengeProfile` that "resolves through the same `requires_facts` mechanism" (`design.md:1496`)
is therefore resolving against a contract surface that has no material form yet.

### 3b. Where profile data would persist

Profiles are `declared` facts (`design.md:1530-1532`: POLICY at construction, performance
measured later). Their persistence path is therefore **the fact pipeline** — not a new record
family. That pipeline's vocabulary is the thing to audit:

- `SOURCE_TYPES` today (`knowledge.py:125-150`) has thirteen rows — `finding, code, report,
  policy, story, review, ledger_job, ledger_attempt, observation, flag, meta_session, spec,
  actuation` — and **no `fact` row**; the `"fact"` row is a DESIGN proposal
  (`design.md:311-313`), and there is **no `profile` row at all**, even in the design. So the
  design must answer whether a profile is (a) a `fact` with a `profile`-scoped predicate, (b)
  a new `SOURCE_TYPES` row (additive registration, the `spec` pattern at `knowledge.py:140-147`),
  or (c) a `declared` fact whose `subject_type` is `domain`/`challenge`.
- The authority a `declared` profile fact carries is `POLICY` (the ordering at
  `knowledge.py:61-85`, and the frozen design's `EPISTEMIC_MAP["declared"]` at `design.md:396`).
  That is correct *only if* the profile is operator-authored. The addendum leaves ambiguous
  who authors a profile (`design.md:1530-1532` says "declared at construction" but not by
  whom); if an LLM proposes profile contents, hard rule 3 forces those to ADVISORY and
  structurally uncitable (`is_canonical`, `design.md:403-417`) — see §7 risk R-2.
- The payload-in-`text` persistence (`design.md:333-370`) means a profile's typed fields
  (`canonical_sources`, `predicates`, `policies`, `patterns`, `verification`) must serialize
  to canonical JSON, exactly as the fact payload does — the prose-projection defect the frozen
  review documented (`review.md` §3d(iv), `ledger_ingestion.py:173,243`) must not recur.

### 3c. Which reserved home fits — `control/facts.py` vs a new `control/profiles.py`

The reserved-home map is authoritative and **does not reserve a profiles home**:

- `control/__init__.py:7-9` lists: `facts.py` (I0), `reducers/` (I1–I3), `context_compiler.py`
  (I4), `rules.py` + `validator.py` + `decisions.py` (I6), and `core/contracts.py` (I5).
- `control/facts.py:1-8` is reserved for "`CanonicalFact`, `FACT_PREDICATES`, `EPISTEMIC_MAP`,
  and `verify_chain`". A `DomainProfile`/`ChallengeProfile` dataclass could live here as a
  *declared-source* construct (alongside `PredicateSpec`, the "declared source" half of the
  load-bearing rule, `design.md:426-457`) — profiles are, precisely, declarations of which
  predicates/policies/patterns a domain registers.
- The alternative, a new `control/profiles.py`, would be **the first reserved home added since
  the map froze**, and it must satisfy the rec-8 constraint that `control` "consumes facts, not
  arbitrary retrieved text" and must not import `knowledge.retrieval` or
  `knowledge.prompt_constructor` (`control/__init__.py:11-12`).

*Auditor's read:* `control/facts.py` (or the `FACT_PREDICATES`/`PredicateSpec` surface it
will hold) is the more consistent home for the *schema*; a `profiles.py` is defensible only if
profiles acquire behavior (selection logic, a loader) that does not belong on the fact schema.
The design must name one and justify it against the reserved-home map, because the map is what
the consolidation guards test against.

### 3d. What routing already selects

`step_routing.route_step` (`control/step_routing.py:188-233`) selects **exactly one thing: a
model id** for one workflow step, from a `RouteState` (`runtime/routing.py:285-292`) over a
per-model `ModelSignals` score (`:99-165`), priced for cache-switch penalty (`:76-93`). It has
no notion of domain, challenge, deliberation stage, or session policy. The addendum's claim
that routing "generalizes from model routing to execution-strategy routing"
(`design.md:1484`) is therefore **a new selection axis**, not an extension: the design must
state whether a profile *feeds* `route_step` (as a wider `signals`/constraint input), *sits
above* it (choosing a deliberation/session strategy that then calls `route_step` for the
model), or *replaces* it. The frozen design's own placement ("`step_routing` stays one
policy… the controller compiles a snapshot *around* the runner", `design.md:104,1200-1209`)
says the model-level router is not where strategy routing lives — which is a constraint the
I8 design must not contradict.

---

## 4. I9 — patterns (the epistemic class, the v6 cite format, what a reducer consumes)

### 4a. `EPISTEMIC_MAP` + `is_canonical` — the target is DESIGN-only

The addendum says the map "gains one additive row" (`design.md:1539-1540`). That is accurate
as a statement about the *design*, and misleading as a statement about the *repository*:

- `EPISTEMIC_MAP` and `is_canonical()` exist only in the frozen design at `design.md:382-417`.
  In code, their reserved home `control/facts.py` is 8 lines of docstring (`control/facts.py:1-8`).
- Consequence: the `"pattern": (Authority.DERIVED, "[C]")` row is additive to **a map that has
  not been built**. There is no construction-time computation to extend, no `is_canonical`
  predicate to preserve. The design of I9 must target the I0 schema (the not-yet-written
  `EPISTEMIC_MAP` in `facts.py`), and must state that `is_canonical()` stays unchanged by
  asserting *why* `DERIVED`/`[C]` already places `pattern` inside `authority >= Authority.DERIVED`
  (`design.md:414`). If that inequality is not already the rule, adding `pattern` would be a
  semantic change, not an additive row — which is the precise thing the verify phase must test.
- The additive-row pattern itself has a *code* precedent worth citing: the `spec` source_type
  was added to `SOURCE_TYPES` the same way (`knowledge.py:140-147`), and `message_family()`
  defaults any unregistered type to `"observation"` (`knowledge.py:168-181`) — the closed-by-
  default posture the `pattern` class inherits. `EPISTEMIC_MAP` has **no** such default
  machinery: an unrecognized `epistemic_status` has nowhere to fall back, so the design must
  decide what a reducer emitting `epistemic_status="pattern"` does before I0 lands.

### 4b. The lab-contract v6 ref format — this is the real, working primitive

The addendum's `source_experiment` ("lab-contract ref, e.g.
`finding:<entity_id>:<knowledge_id>`", `design.md:1550`) reuses a primitive that **does** exist,
in full, in code:

- `CONTRACT_VERSION = "lab-contract/v6"` (`lab_contract.py:114`), with the table-qualified
  contributor refs and their digests as required fields: `used_record_refs_sha256` /
  `excluded_record_refs_sha256` (`:149-150`), `used_unique_records` / `used_contributions`
  (`:151-152`).
- `ContributionReport` carries the exact refs: `used_record_refs` / `excluded_record_refs`
  (`:245-246`), `used_unique_records` / `used_contributions` (`:247-248`).
- `refs_digest` (`:352-362`) and `record_id` (`:365-384`) define the format: `story`/`review`/
  `finding` → `"<table>:<entity_id>:<knowledge_id>"`; `analysis` → `"analysis:<story_entity_id>:<content_digest>"`.
- The allowed tables are closed: `_TABLES = ("story", "finding", "review", "analysis")`
  (`:167`). **This matters for I9**: `source_experiment` names a `finding` ref, which is
  in-vocabulary — but if a pattern is learned over a *campaign* (many findings/stories), the
  single-valued `source_experiment` string cannot express that set, and the pattern's
  `evidence_ids` (`design.md:253-254`) becomes the multi-record carrier. The design must
  reconcile the single `source_experiment` with the plural `evidence_ids`, and the frozen
  review's own finding about single-valued `causes` (`review.md` §4.1) is the same trap in a
  different key.

### 4c. How campaign results are stored today — what a pattern reducer would consume

A `pattern` is minted "only by a deterministic reducer from measured evidence"
(`design.md:1553`). The measured evidence a reducer would read is all present today:

- **Lab artifacts:** `scripts/lab_*.py` (twenty producers) emit `experiments/results/lab_*.json`,
  each embedding a `lab_contract` block via `attach_contribution` (`lab_contract.py:581-617`) —
  which is exactly the "which records produced this result" attestation a pattern reducer needs
  to compute `support` and `population`.
- **The raw attempt summary:** `experiments/results/_results_summary.json` — the per-attempt
  measured rows (cost/correctness/confidence per model per task).
- **The registry:** `experiments/results/registry_index.jsonl` (append-only; rows carry
  `entity_id`, `knowledge_id`, `source_type`, `lifecycle_state`, `supersedes`, `causes`) plus
  the per-record artifacts `experiments/results/kb/<knowledge_id>.json`, compacted into
  `experiments/data_manifest.json` by `scripts/generate_manifest.py` (`:300`).
- **The canonical resolver:** `reporting/canonical_corpus.py` (imported at `lab_contract.py:93-98`)
  is the resolver the labs already consume, so a pattern reducer has a ready-made, scope-safe
  way to resolve `evidence_ids` to payloads rather than re-reading the tree.

*What is NOT present:* any reducer that reads any of this to emit a fact — `control/reducers/`
  is empty (`__init__.py:1-9`). So I9's reducer is greenfield *consumer* code over a mature
  *input* corpus. The design's main I9 task is the mapping from a lab's `used_record_refs` and
  a campaign's `_results_summary.json` rows to `PatternPayload.{population, conditions,
  support, uncertainty}` — and it must state which of those five fields are deterministic
  functions of the refs (population, support) vs which require a modelling decision
  (conditions, uncertainty).

---

## 5. I10 — checkpoint (what is derivable today, what is ADVISORY, what is blocked)

### 5a. The run-artifact fields the checkpoint's deterministic half draws from

`PhaseResult` (`workflow_runner.py:75-150`) and `WorkflowRunResult` (`:153-190`) are the
typed per-run ledger. The fields relevant to a checkpoint:

| Checkpoint field (A.4) | Derivable today? | Source (CODE) |
|---|---|---|
| `goal` | **YES** | `WorkflowRunResult.goal` (`workflow_runner.py:160`) |
| `completed` | **YES** | `PhaseResult.status == "ok"` per phase (`:81,628-629,644`); `_completed_phases` via git markers (`:235-254`) with the index fallback `_completed_phases_from_index` (`:290-328`) |
| `current_revision` | **YES** | `WorkflowRunResult.git_sha` (`:667`) / `PhaseResult.commit_hash` (`:636`) |
| `acceptance_state` | **PARTIAL** | `PhaseResult.test_executed_success` (`:113`, written `:511`) + `status`; but "acceptance criteria" are not a first-class object (frozen review §2 row 3) — the checkpoint can encode *test-verified*, not *accepted* |
| `verified_facts` | **NO — blocked on I0–I4** | fact ids by reference; the fact store does not exist (`control/facts.py:1-8`) |
| `context_snapshot_id` | **NO — blocked on I4** | `snapshot_id` is DESIGN-only (`design.md:925-947`); `context_compiler.py:1-8` is empty |

The **ADVISORY** half of the checkpoint — `open_hypotheses`, `failed_approaches`, `next_action`
(`design.md:1573-1575`) — is, by the addendum's own labels, the "session's own account": it has
no measured producer today and *should* have none. The one existing ADVISORY-quality source it
could ride on is `AgenticResult`'s narration and `PhaseResult.final_response`
(`workflow_runner.py:626`), but nothing persists a structured hypotheses/failures list. The
design must name the producer of these three ADVISORY annotations, and pin them as
`epistemic_status="advisory"` so `is_canonical`/C5 exclude them (`design.md:403-417,1183`).

### 5b. The ledger attempt fields the fork decision implies — declared, not written

`session_routing`'s `fork` / `compress_and_fork` decisions (`design.md:1580-1585`) imply
attempt lineage. The ledger's declared vocabulary has the names; the written data does not:

- **Declared-and-unwritten** (verified by the frozen review §3d(ii), re-read here):
  `parent_attempt_id` (`experiment_spec.py:160`), `retry_reason` (`:161`),
  `escalation_from`/`escalation_to` (`:162-163`). Nothing in `run_workflow` writes them —
  the runner has no retry loop, one pass per phase with `stop_on_error` (`workflow_runner.py:663-664`).
- **Naming mismatch, not a gap:** `cache_hit` is declared (`experiment_spec.py:172`), but the
  written fields are `cache_hit_rate` (`workflow_runner.py:95,617`) and
  `cache_read_tokens`/`cache_write_tokens` (`:93-94`), and `story/models.py:156-159` writes the
  same under the `agentic` block. A checkpoint reducer that wants "did the fork keep the cache
  prefix" reads `cache_read_tokens`/`prev_cache_read_tokens`, not `cache_hit`.
- **What *is* actually measured about continuation:** the fork chain itself —
  `prev_session_id`/`prev_model`/`prev_cache_read_tokens` (`workflow_runner.py:490-492`), the
  fork decision (`:591-597`), and the session-id handoff (`:618-621`) — plus the story-side
  `continuation_used`/`continuation_cost_usd` (`story/models.py:105-106`). These are the real,
  typed inputs a checkpoint's "was this session a continuation?" must use; the LEDGER_FIELDS
  names are not.

*Consequence for the load-bearing rule:* a `session_routing` contract whose invariants consume
`parent_attempt_id` or escalation fields would be *consuming a declared-but-never-written
value* — the exact `deadline_slack` failure the frozen review documented (`review.md` §4.4).
The design must either instrument those fields first (measure-before-policy) or express the
fork decision over the fork-chain fields that are actually written.

### 5c. `snapshot_id` and `session_types` — one DESIGN reference, one CODE vocabulary

- `snapshot_id` is specified at `design.md:925-947` (content-addressed over contract + scope +
  fact ids + negative collections, `compiled_at` excluded). It is **not** in code, and the
  checkpoint's `context_snapshot_id` therefore references a value the system cannot yet produce.
  The `continue` invariant that "the checkpoint's `context_snapshot_id` equals the freshly
  compiled snapshot's id" (`design.md:1581-1583`) is uncheckable until I4 lands.
- `session_types` **does** exist: `TASK_TYPES = {greenfield, feature_addition, integration,
  refactor, cross_cutting}` (`core/session_types.py:40-42`), `DEFAULT_TASK_TYPE` (`:44`),
  `EXPERIMENT_SESSION_PATTERNS` (`:55-65`), `normalize_task` (`:68-74`). The addendum's
  `ChallengeProfile.challenge` vocabulary (`greenfield | cross_cutting | small_change |
  research | incident | migration`, `design.md:1512-1513`) **overlaps but does not equal**
  `TASK_TYPES`: only `greenfield` and `cross_cutting` are shared; `small_change`, `research`,
  `incident`, `migration` are new; `feature_addition`, `integration`, `refactor` are dropped.
  This is a genuine second vocabulary for the same axis (problem archetype), and the design
  must decide: extend `TASK_TYPES`, or declare `challenge` a separate orthogonal axis — the
  `core/session_types.py:1-8` docstring's whole purpose is that a stray free-form string must
  not silently fork a vocabulary, so this cannot be left unaddressed.

---

## 6. Open questions the design must answer (with schemas)

Each names the schema it obliges. "Schemas" means dataclass/YAML sketches in the frozen
design's own convention (`design.md:30-37`), not prose.

1. **OQ-1 (I8, home + persistence).** Where do `DomainProfile`/`ChallengeProfile` live and
   persist? Decide among: (a) `control/facts.py` as a declared-source schema beside
   `PredicateSpec`, (b) a new `control/profiles.py` (the first post-freeze reserved home —
   justify against `control/__init__.py:7-9`), and (c) spec-YAML top-level keys (which requires
   extending `SPEC_KEYS`/`ExperimentSpec`, `experiment_spec.py:86-118,430-571`). Schema: the
   profile→fact mapping — which `predicate` names, which `subject_type`, which `source_type`
   (`fact`? a new `profile` row?), and the canonical-JSON payload shape.

2. **OQ-2 (I8, the challenge vocabulary).** What is the `challenge` archetype vocabulary, and
   its relationship to `session_types.TASK_TYPES` (`core/session_types.py:40-42`)? Schema: the
   enum/`frozenset` and an explicit mapping or a statement of orthogonality, since the two sets
   overlap but do not match.

3. **OQ-3 (I8, routing composition).** How does "execution-strategy routing" sit relative to
   `route_step` (`step_routing.py:188-233`)? Schema: the new decision-type contract
   (`decision_type`, `allowed_actions`, `requires_facts`) and where the profile's
   `deliberation`/`session_policy`/`verification_policy` become inputs — above, beside, or
   inside the model router (must not contradict `design.md:1200-1209`).

4. **OQ-4 (I9, the reducer's `consumes`).** What exactly does the pattern reducer consume, and
   how does it map the lab-contract v6 lineage to the pattern's provenance? Schema: the
   `ReducerSpec.consumes` tuple, and the `used_record_refs` → `source_experiment` +
   `evidence_ids` mapping, including how a *campaign* (multi-record) population is represented
   when `source_experiment` is single-valued (`lab_contract.py:167,365-384`).

5. **OQ-5 (I9, identity + validity).** What is a pattern's `fact_entity_id` key, and how does
   `validity_window` interact with the version-chain identity and the conflict ladder
   (`design.md:689-699`)? Schema: the identity formula, and the rule for two patterns over the
   same population with overlapping windows (supersede vs `conflicted`).

6. **OQ-6 (I9, deterministic support).** How are `support`/`uncertainty` derived
   deterministically, honoring the m2 null-not-zero rule (`measurement_coverage.py:20-21,54-108`)?
   Schema: the reducer's computation of each field when `n_available = 0` vs `n_available > 0`.

7. **OQ-7 (I10, the canonical/ADVISORY split).** Which checkpoint fields are persisted as
   canonical facts (predicate `session_checkpoint/v1`) vs ADVISORY annotations, and how are the
   ADVISORY ones structurally excluded from `facts_used` (C5, `design.md:1183`)? Schema: the
   `SessionCheckpoint` field → epistemic_status mapping, and the producer of the three ADVISORY
   fields.

8. **OQ-8 (I10, the actuation boundary).** How do `fork`/`compress_and_fork`/`escalate` stay in
   shadow mode (recorded, surfaced, never applied) — i.e., outside `AUTOMATABLE_ACTIONS`
   (`design.md:1191-1197`) — until the 4-arm evidence-seed experiment lands? Schema: the
   `session_routing` contract with `allowed_actions` and the shadow-mode recording path.

9. **OQ-9 (I10, sequencing + degradation).** Two checkpoint fields (`verified_facts`,
   `context_snapshot_id`) depend on I0–I4, which are unimplemented. Does I10 land after I4, or
   does the checkpoint degrade (`context_snapshot_id: null` classified `unknown`, `on_missing:
   classify`)? Schema: the increment ordering and the degradation contract for the blocked
   fields.

10. **OQ-10 (I10, attempt lineage).** The fork decision implies `parent_attempt_id` /
    `escalation_from/to`, which are declared-unwritten (`experiment_spec.py:160-163`). Does the
    design instrument them (measure-before-policy), or express the fork decision over the
    already-written fork-chain fields (`workflow_runner.py:490-492,591-621`;
    `story/models.py:105-106`)? Schema: the choice and, if instrumentation, the writer.

---

## 7. Hard-rule risks per increment

Keyed to the frozen design's rule table (`design.md:41-49`) plus the load-bearing rule.

**I8 (profiles)**
- **R-1 — hard rule 6 (gate).** A profile registers `predicates`; each must have a
  non-empty `produced_by` (the `PredicateSpec` invariant, `design.md:444-448`). Risk: a
  profile naming a `predicate` nothing produces reproduces the `LEDGER_FIELDS`-declared-zero-
  writers failure verbatim.
- **R-2 — hard rule 3 (ADVISORY always).** `declared` = POLICY is correct only for
  operator-authored profiles (`design.md:396,1530-1532`). Risk: an LLM-authored profile
  (`deliberation`, `session_policy`, `canonical_sources`) would be ADVISORY and must be
  structurally uncitable — the design must pin authorship, or it silently promotes heuristic
  context to POLICY.
- **R-3 — hard rule 7 (no redesign).** Profiles must persist as facts, not a new record family
  or store. Risk: a `profile` source_type with its own identity/validity rules forks the two-
  identity / two-plane discipline (`knowledge.py:8-11,192-211`).

**I9 (patterns)**
- **R-4 — hard rule 3.** Minting `pattern` requires a deterministic reducer; `support`/
  `uncertainty` must be computed, never defaulted. Risk: `support=0` vs no-data collapse is the
  exact m2 defect `measurement_coverage.py` was built to kill (`:1-21`).
- **R-5 — hard rule 4 (one canonical or explicit conflict).** A `pattern` is version-chained,
  but `validity_window` is a range; overlapping windows over one population must resolve as
  `superseded` or `conflicted`, not silently coexist (conflict ladder, `design.md:689-699`).
- **R-6 — additive-to-a-map-that-does-not-exist.** The `"pattern"` row is additive to
  `EPISTEMIC_MAP`/`is_canonical()` which are DESIGN-only (`control/facts.py:1-8`). Risk:
  designing against code that is not there, and the addendum's own wording
  (`design.md:1536-1537`) implying the map is live. The design must target the I0 schema.

**I10 (checkpoint)**
- **R-7 — hard rule 5 (observe-only rail + authority).** The ADVISORY half of the checkpoint
  (`open_hypotheses`, `failed_approaches`, `next_action`) must never be citable; `next_action`
  never applied (outside `AUTOMATABLE_ACTIONS`, `design.md:1191-1197`). Risk: `fork`/
  `compress_and_fork` are actuations that must stay in shadow mode until the 4-arm experiment
  lands.
- **R-8 — load-bearing rule (measure-before-policy).** The `continue` invariant consumes
  `context_snapshot_id` (`design.md:1581-1583`), a value with no producer (I4 unimplemented).
  Risk: a session-routing contract whose invariant consumes an unproduced fact is exactly the
  `deadline_slack` refusal case (`review.md` §4.4). The design must either defer I10 past I4 or
  classify the field `unknown`.

**Cross-cutting**
- **R-9 — the two citation planes.** All three increments sit on a plane that is itself a
  forward reference. The design must tag every reference as CODE (`file:line`) or DESIGN
  (`design.md:§`) and must not let an addendum claim transitively assume a CAP object exists.
- **R-10 — the closure deltas bind.** `measurement_coverage.py` m2, `control/routing.py`'s
  nullable `n_cost`/`n_outcome` (`:76-81,149-156`), and the v6 cite format (`lab_contract.py:114`)
  are the *only* three closure primitives the addendum names (`design.md:1599-1604`); each
  increment's reducers must reuse them rather than re-implement, or the finding-economics
  closure's signoff (`design.md:1462-1465`) is undercut.

---

## Appendix — citation index

| Concern | Citations |
|---|---|
| Reserved CAP homes | `control/facts.py:1-8`; `control/reducers/__init__.py:1-9`; `control/context_compiler.py:1-8`; `core/contracts.py:1-8`; `control/rules.py:1-8`; `control/validator.py:1-8`; `control/decisions.py:1-8`; `control/__init__.py:7-12` |
| Spec config surfaces | `experiment_spec.py:86-118,223-236,430-571`; `workflow_runner.py:403,411-414,422-425,476,481-488` |
| Routing contract + policy | `runtime/routing.py:42-59,67-99,105-157,192-245,285-292`; `control/step_routing.py:76-93,188-233` |
| KB vocabulary + authority | `knowledge.py:61-85,125-150,168-181,192-211` |
| Ledger schema (declared) | `experiment_spec.py:135-194,270-300` |
| Ledger→KB projection | `ledger_ingestion.py:59-69,75-96,128-198,204-269,275-309` |
| Run artifacts (checkpoint inputs) | `workflow_runner.py:75-190,227-254,290-328,490-492,591-621,663-667`; `story/models.py:89-162,165-313` |
| Lab-contract v6 lineage | `lab_contract.py:93-98,114,135-154,167,213-248,352-384,581-617` |
| Coverage primitive (m2) | `measurement_coverage.py:1-21,54-108,111-124,136-156` |
| Task routing (nullable aggregates) | `control/routing.py:23-124,127-184` |
| Session vocabulary | `core/session_types.py:1-8,40-42,44,55-65,68-74` |
| Campaign corpus (data) | `experiments/results/lab_*.json`; `_results_summary.json`; `registry_index.jsonl`; `kb/<knowledge_id>.json`; `scripts/generate_manifest.py:300` |
| Frozen design (DESIGN refs) | `context_abstraction_design.md:311-313,333-370,382-417,426-457,689-699,739-822,925-947,1183,1191-1209,1460-1604` |
| Frozen review (prior art + §3d(ii)) | `docs/context_abstraction/review.md` §§2,3d,4.1,4.4 |
