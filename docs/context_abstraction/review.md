---
status: accepted
---
# Context Abstraction Plane — Architecture Review (audit phase)

**Spec:** `experiments/specs/context_abstraction_plane.yaml`
**Phase:** `review` (phase 1 of 3 — `review` → `design` → `verify`)
**Date:** 2026-08-20 · **Model:** anthropic/claude-opus-5 · **Branch:** `feature/context-abstraction-plane`
**Deliverable rule:** design-only. This phase adds exactly one file (`docs/context_abstraction/review.md`)
and modifies nothing under `src/`, `scripts/`, `tests/`, or `admin/`.

---

## 0. What this document is, and how to read it

This is an **audit**, not a design. Its job is to establish — with file:line citations that a
reader can check — what the repository *already* implements of the Context Abstraction Plane
proposal, what it partially implements under a different name, and what genuinely does not
exist. The design phase then builds only what is actually missing.

The proposal in the spec's `design_input` is explicitly labelled "authoritative seed —
challenge it against the code, do not paraphrase it into vagueness." Section 4 of this review
does exactly that: it lists the proposal claims that do **not** hold against the code, the
ones that hold only under a narrower reading, and the one significant piece of prior art the
proposal's own `grounding_facts` omit (the canonical-state round-2 observation/actuation
work). Section 5 turns the audit into a set of constraints the design phase inherits.

Three conventions used throughout:

- **Citations are `file:line`** and were read at the branch head listed above. Where a range
  is given, the range is the whole construct (dataclass, function) not just its first line.
- **EXISTS / PARTIAL / MISSING** are judged against the *proposal's* definition of the element,
  not against a charitable reading. PARTIAL means "a real mechanism exists that covers part of
  the element's contract"; it never means "something vaguely adjacent exists."
- **Evidence classes** follow the repo convention: `[M]` measured, `[C]` computed, `[H]`
  heuristic, `[P]` policy/prior, `[X]` external.

### Sources read

`experiments/specs/context_abstraction_plane.yaml`, `src/instrument/CONTEXT.md`,
`src/instrument/knowledge.py`, `retrieval.py`, `prompt_constructor.py`, `workflow_runner.py`,
`step_routing.py`, `experiment_spec.py`, `compile_experiment.py`, `ledger_ingestion.py`,
`observation_ingestion.py`, `actuation_ingestion.py`, `knowledge_stream.py`,
`knowledge_ingestion.py`, `policy_ingestion.py`, `supervisor.py`, `live.py`,
`pipeline_status.py`, `scripts/kb_worker.py`, `scripts/generate_manifest.py`,
`scripts/registry.py`, `scripts/supervise.py`, `scripts/run_workflow.py`,
`docs/supervisor_design.md`, `docs/canonical_state_r2_design.md`,
`docs/canonical_state_base_design.md`, `experiments/specs/spec_lifecycle.yaml`.

---

## 1. Verdict in one paragraph

The repository has an unusually complete **evidence plane** (immutable identity, ordered
authority, provenance, validity, supersession lineage, a durable stream, a registry with a
derived lifecycle state, and four-plus producer families) and an unusually complete
**execution plane** (worktree-scoped phase execution, per-phase commits, per-phase typed
ledger records, deterministic model routing, a validated spec/compiler gate). What it does
not have is anything in between: there is **no typed statement of current system state**.
Every "state" question the system can answer today is answered either by (a) re-reading and
re-deriving artifacts, (b) parsing prose out of a `text` field, or (c) reading ephemeral Redis
telemetry that carries no scope, no authority, and no validity window. Of the twelve proposal
elements audited below, **two EXIST**, **six are PARTIAL** (a real mechanism exists but covers
only part of the contract), and **four are MISSING**. Crucially, the two most control-adjacent
pieces the proposal assumes are greenfield — the actuation envelope and its safety gates —
already exist, built deliberately with zero call sites; the design must extend them rather
than invent a parallel decision type.

---

## 2. Component audit table

One row per proposal element. `Status` is EXISTS / PARTIAL / MISSING. `What exists today`
carries the citations; `Gap` is a one-line statement of what the proposal asks for that the
cited code does not deliver.

| # | Proposal element | Status | What exists today (file:line) | Gap (one line) |
|---|---|---|---|---|
| 1 | **L0 — Evidence** (immutable observations/artifacts: test results, logs, commits, tool output, token events) | **EXISTS** | `knowledge.py:227-297` `KnowledgeEvent` (pointer-only, `content_hash`, `occurred_at`, `observed_at`); `knowledge.py:300-431` `KnowledgeRecord` (body + provenance + validity); `knowledge.py:184-203` two-sha256 identity; `knowledge_stream.py:129-194` durable Redis Streams append with a write guard; producers: `knowledge_ingestion.py` (finding), `code_ingestion.py` (code), `quality_ingestion.py` (report), `policy_ingestion.py:204` (policy), `story_ingestion.py`, `review_ingestion.py`, `ledger_ingestion.py:275-309` (ledger_job/ledger_attempt), `observation_ingestion.py:76-120` (supervisor verdicts); typed run artifacts at `workflow_runner.py:64-135` → `scripts/run_workflow.py:108` | Live token/tool events are **not** L0 evidence: `live.py:23,52` publishes them to the ephemeral pub/sub telemetry plane (DB 1) with no durable artifact, so the proposal's "token events" are evidence only in the aggregated per-phase form. |
| 2 | **L1 — Canonical facts** (typed, current, scope-bound statements: `current_commit`, `budget_remaining`, worker status, dependency failed) | **PARTIAL** | The *validity spine* exists: `generate_manifest.py:75-108` `_derive_lifecycle` → `current \| superseded \| tombstoned`; `generate_manifest.py:111-221` compacts to **one current row per `entity_id`**; `kb_worker.py:96-103,233-303` writes the append-only registry index and the predecessor-superseded marker; `registry.py:68,176-199` queries by `--lifecycle`. Per-cell current commit is derivable at `workflow_runner.py:207-213` (`_git_head`) and phase completion at `workflow_runner.py:215-235` | There is **no typed fact record**: a registry row is a *document version*, not a `subject/predicate/value` statement. `KnowledgeRecord` has no `predicate` or typed `value` field (`knowledge.py:310-356`) — the closest is the untyped `subject_id`/`subject_status` string pair (`knowledge.py:355-356`), and every numeric fact is embedded in prose `text` (see §3d). |
| 3 | **L2 — Job/phase state** (goal, acceptance criteria, attempts, blockers, risk) | **PARTIAL** | `workflow_runner.py:64-135` `PhaseResult` is a real per-phase typed ledger (status, model, tokens, cost, cache, confidence, `test_executed_success`, commit, augmentation provenance); `workflow_runner.py:137-171` `WorkflowRunResult` aggregates it; `workflow_runner.py:215-235` derives completed phases from git commit markers, enabling resume | No **acceptance criteria**, no **attempt lineage**, no **blockers**, no **risk**: `accepted`, `first_pass`, `attempt_number`, `parent_attempt_id`, `retry_reason` are declared in `experiment_spec.py:44-103` but written by nothing (verified: zero non-declaration call sites), and `run_workflow` has no retry loop at all — one pass per phase, `stop_on_error` (`workflow_runner.py:580-581`). |
| 4 | **L3 — Workflow state** (completed phases, critical path, dependencies, accumulated cost, deadline slack) | **PARTIAL** | Completed phases: `workflow_runner.py:215-235`. Accumulated cost: `workflow_runner.py:151-153` `total_cost_usd`. Compiled phase order: `compile_experiment.py:34` `PHASES` + `compile_spec:87-96` edges/feedback | **Critical path and dependencies do not exist as data**: workflow phases are a flat ordered list in `workflow.params.phases` with no declared inter-phase dependency edges, and the compiler DAG is a fixed 7-node chain (`compile_experiment.py:34`), not a job graph. `deadline_slack`/`due_at` are declared (`experiment_spec.py:52,56`) and written by nothing. |
| 5 | **L4 — Workload/program state** (priorities, aggregate capacity, portfolio budget, shared dependencies, business value) | **MISSING** | Nearest surface: `pipeline_status.py:23-63` `stage_summary` (queue depth, running/done/failed counts per stage) and the `story_status` hash read by `supervise.py:276-283` | This is **telemetry, not state**: DB 1 (`live.py:23`), unscoped, no authority, no validity window, no provenance, and it counts *jobs* not *capacity/priority/value*. `budget`, `policy_arm`, `policy_id`, `forecast_cost`, `actual_cost`, `rework_cost`, `reuse_value` are all declared ledger fields with zero writers. |
| 6 | **L5 — Intent and policy** (allowed models, maximum spend, permissions, compliance, outcome priorities) | **PARTIAL** | `policy_ingestion.py:127,204` discovers and registers repo policy documents as `authority=POLICY`/`[P]` records; `knowledge.py:61-85` pins POLICY at the top of the ordering; `retrieval.py:63-71` deliberately **omits** POLICY from the fusion multipliers so policy is never probabilistically retrieved; allowed models: `step_routing.py:168-201` (`model`/`allowed_models`/pool) validated at `step_routing.py:262-292`; spend/attempt caps: `experiment_spec.py:249-270` `StopSpec` | Policy exists as **prose documents plus per-spec config**, never as machine-checkable constraint facts. `StopSpec.budget_usd`/`max_attempts` are parsed and validated but no code compares them against actual spend or attempt counts; `.claude/settings.json` permissions are harness config, not a fact any rule can consume. |
| 7 | **CanonicalFact plane** (typed statement with scope, source, validity window, authority, abstraction level, derivation path, supporting evidence) | **MISSING** | Every *field* the proposal wants exists somewhere on `KnowledgeRecord`: authority `knowledge.py:322`, validity `knowledge.py:323-324`, observation time `knowledge.py:325`, scope `knowledge.py:316,327`, evidence class `knowledge.py:335`, lineage `knowledge.py:343,348`, extractor version `knowledge.py:320` | The record models **a document version, not a statement**. Missing as fields: `predicate`, typed `value`, `scope_type`, `abstraction_level`, `epistemic_status`, `evidence_ids` (plural — `causes`/`supersedes` are single-valued), `expires_at`, `reducer_version`. No dataclass in `src/instrument/` carries a `predicate` field (verified by search). |
| 8 | **Deterministic versioned reducers** (events → atomic facts → attempt → job → workflow → workload) | **PARTIAL** | Genuine deterministic versioned derivations exist and are the right prior art: `generate_manifest.py:75-108` (lifecycle, "index-only, computed, never stored"); `compile_experiment.py:226-243` `first_pass_quality` and `:257-330` `grit` (pure, over attempts, emit `RuleResult` with `produces` at `:215-223`); every `*_ingestion.py` module pins an `EXTRACTOR_VERSION` (`ledger_ingestion.py:59`, `knowledge_ingestion.py:119`, `code_ingestion.py`, `actuation_ingestion.py:62`) | These reducers **do not compose upward and do not emit facts**. `evaluate_rules` (`compile_experiment.py:343-377`) runs only measurement rules over a flat `attempts` list at analysis time and returns in-memory `RuleResult`s that are never persisted, never scoped, never versioned into a record, and never re-derived when upstream evidence is superseded. There is no attempt→job→workflow→workload reduction ladder. |
| 9 | **Context Compiler** (decision-type contract → scope-appropriate `ControlContext` snapshot with unknowns/conflicts/stale facts) | **MISSING** | Nearest analogues, both for *executors* not controllers: `prompt_constructor.py:156-207` (`ConstructionRequest` → `AugmentedPrompt`, schema-versioned at `:42`, validated at `:345`) and `retrieval.py:846+` `retrieve()` with its token-budgeted `select_evidence` (`:565-591`) and audit record `RetrievalAttempt` (`:610-658`) | Nothing assembles state *for a decision*. Both analogues take a **work item** and return **text**; neither takes a decision type, neither returns typed state tuples, and neither can express `unknown`, `conflicted`, or `stale` — `retrieve()` silently drops excluded candidates (`retrieval.py:441-442`) and down-ranks conflicts by a multiplier (`retrieval.py:51`) instead of surfacing them. |
| 10 | **ControlDecision** (typed action, target, parameters, `facts_used`, expected effect, preconditions, `snapshot_id`) | **PARTIAL — and further along than the proposal assumes** | The envelope, identity, authority, and action vocabulary already exist: `knowledge.py:141` registers `source_type="actuation"` as the single actuation-family member; `knowledge.py:160-173` `message_family()` classifies closed-by-default; `actuation_ingestion.py:70` `ACTUATION_KINDS = {steer, interrupt, escalate, retry, budget, deadline}`; `actuation_ingestion.py:91-160` `derive_actuation_record` builds it with `authority=POLICY`, `causes` required at construction (`:112-116`), identity `hash(target_session_id\|causes\|occurred_at)` (`:76-88`). Zero call sites by design (`actuation_ingestion.py:8-22`) | The payload is an **opaque JSON body inside `text`**, not a typed decision: no `preconditions`, no `expected_effect`, no `facts_used` list, no `snapshot_id`. `causes` is *one* observation id, so the provenance chain is single-threaded and cannot express "this decision used these seven facts." |
| 11 | **ControlValidator** (enforces policy/permissions/preconditions/fact contracts before execution) | **PARTIAL** | Three real, closed-by-default gates already exist: (a) the spec gate `experiment_spec.py:373-409` `validate_rules` refused via `compile_experiment.py:87-96`; (b) the routing gate `step_routing.py:207-238` `validate_preferences` (`FORBIDDEN_SIGNALS` at `:68`); (c) the transport gates `knowledge_stream.py:178-192` — write guard, `armed` actuation gate, and the `causes`-must-resolve-to-an-observation lineage gate; plus the human-authorization boundary at `docs/supervisor_design.md:102-116` | No validator checks a decision against **state**: nothing evaluates preconditions, nothing checks fact freshness or scope, nothing enforces a spend/permission ceiling at decision time. The three existing gates check *schema availability* (is this field name declared?), never *fact currency* (is this value true, now, in this scope?) — see §4.4. |
| 12 | **Scope hierarchy** (organization → program → workload → workflow → job → attempt, with controlled inheritance) | **PARTIAL** | Exactly **one** level is implemented, and implemented well: `workflow_runner.py:242-252` `cell_scope()` → `self-<worktree>`; `retrieval.py:392-406` `scope_excluded()` is a HARD pre-filter applied at `retrieval.py:973-981` and again on the graph leg at `:1018`; `knowledge.py:316,327` carry `repository_id`/`acl_scope`; `knowledge_ingestion.py:93` `REPOSITORY_ID = "agentic-dynamics"` is the default shared scope; the two Redis planes are genuinely split (knowledge DB 2 vs telemetry DB 1, `live.py:23`) | The scope is a **flat string with an equality test**, not a hierarchy: `scope_excluded` compares `!=` and has no notion of a parent scope, so there is no inheritance, no aggregation path, and no way for a job-scoped consumer to see workload-scoped policy without seeing sibling-job detail. Empty scope means "unknown/legacy," never "global" (`retrieval.py:396-405`) — the design must preserve that. |

### Summary of the table

- **EXISTS (1):** L0 evidence.
- **PARTIAL (7):** L1, L2, L3, L5, reducers, ControlDecision, ControlValidator, scope hierarchy.
- **MISSING (4):** L4 workload state, CanonicalFact, Context Compiler — and, within the
  PARTIAL rows, the specific sub-elements named in each Gap cell.

The distribution matters for the design phase: the plane is **not** a greenfield subsystem.
Nine of twelve rows have a real mechanism to build on, and three of those mechanisms
(registry lifecycle, the actuation gates, the spec gate) are the load-bearing ones.

---

## 3. The four critical distinctions, grounded in code

The spec asks for four distinctions to be established against the code rather than asserted.
Each is confirmed below, with the specific lines that make it true.

### 3a. Retrieval is relevance ranking, not truth resolution

`retrieval.py` is a ranker end to end. The evidence is structural, not incidental:

1. **The output is an ordered list, not a value.** `fuse_candidates` (`retrieval.py:420-455`)
   sorts by `fused_score` descending and returns *all* survivors; `select_evidence`
   (`retrieval.py:565-591`) then takes a greedy prefix under a token budget. Nothing in the
   module ever returns "the current value of X."
2. **The score is a product of heuristics.** `compute_fused_score`
   (`retrieval.py:345-367`) = RRF base × authority multiplier × freshness × exact-identifier
   bonus × conflict penalty. The constants are explicitly tagged `[H]`
   (`retrieval.py:45-61`): `RRF_K = 60.0`, `LEXICAL_LEG_WEIGHT = 1.2`,
   `EXACT_IDENTIFIER_MULTIPLIER = 1.15`. A ranking assembled from heuristic multipliers is a
   *preference order*, and a preference order over documents can never be a truth claim about
   the world.
3. **Authority is used as a multiplier, not a resolver.** `AUTHORITY_MULTIPLIER`
   (`retrieval.py:63-71`) turns the ordinal trust hierarchy into a scalar weight. That is the
   right thing for ranking and the wrong thing for truth: a sufficiently well-matched
   `ADVISORY` candidate can outrank a `MEASURED` one, because the multiplier is finite and
   the RRF base varies freely.
4. **Conflict is *penalised*, not *surfaced*.** `CONFLICT_MULTIPLIER = 0.70`
   (`retrieval.py:51`) and `is_conflict_relationship` (`retrieval.py:414-415`) mean a
   contradiction makes a candidate rank lower and still appear. There is no code path in the
   module that returns "conflicted" as a status. This is precisely the proposal's point:
   relevance degradation is not conflict resolution.
5. **Exclusion is silent.** `fuse_candidates` drops any candidate whose
   `freshness_multiplier` returns `None` (`retrieval.py:437-442`) — wrong-commit, wrong-scope,
   or POLICY — with no record in the returned list. `RetrievalAttempt`
   (`retrieval.py:610-658`) audits what *was* selected; a controller reading the result cannot
   distinguish "no evidence exists" from "all evidence was scope-excluded."

**Conclusion:** the plane must sit above `retrieval.py` and must not consume its output as
state. Retrieval answers "what is worth reading about X"; a canonical fact answers "what is X,
right now, in this scope." The proposal's hard rule (7) — do not redesign `retrieval.py` — is
correct and should stand.

### 3b. `RouteState` knows model economics but not workload state

`RouteState` (`step_routing.py:321-330`) has exactly five fields:

```python
pool: list[str]                  # eligible model ids
prev_model: str | None           # prior step's model (cache continuity)
prev_session_id: str = ""        # prior step's session (fork target)
prev_cache_read_tokens: int = 0  # prior step's cache footprint
context_tokens: int = 0          # context size
```

Everything the router does with that state is model economics: `_effective_cost`
(`step_routing.py:335-340`) adds `cache_switch_penalty` (`step_routing.py:298-315`, priced
from `PROVIDER_PRICING`); `_score_eligible` (`step_routing.py:351-401`) normalises measured
per-model signals; `_select` (`step_routing.py:404-418`) is a deterministic argmax with
continuity and cost tie-breaks. The signal vocabulary itself (`step_routing.py:50-65`) is
per-model quality/cost aggregates: correctness, cost, efficiency, cache-hit rate, constraint
score, code-quality score, novelty, composite.

**Fields `RouteState` lacks** — every one of which the proposal's L2–L5 layers require:

| Missing from `RouteState` | Layer it belongs to | Is it recorded anywhere today? |
|---|---|---|
| `budget_remaining` / spend-to-date vs cap | L3/L4 | No — `StopSpec.budget_usd` (`experiment_spec.py:253`) is parsed, never compared |
| `deadline` / `deadline_slack` / `due_at` | L3 | No — declared at `experiment_spec.py:52,56`, zero writers |
| dependency state (blocked-by, dependency failed) | L3 | No — no inter-phase/inter-job edges exist |
| critical path / remaining phases | L3 | Partially — remaining phases derivable from `workflow_runner.py:215-235`; criticality undefined |
| job priority | L4 | No |
| failure history / attempt number / retry reason | L2 | No — declared, zero writers |
| capacity (workers, concurrency) | L4 | Telemetry only (`pipeline_status.py:30-63`), not scoped state |
| risk / blocker | L2 | No |
| business value | L4 | No — `value`, `reuse_value` declared, zero writers |
| permissions / compliance constraints | L5 | No — prose policy records only |

So `route_step` (`step_routing.py:424-469`) is, exactly as the proposal says, **one
deterministic control policy over one narrow state** — and a good one: pure, no I/O, no RNG
(`step_routing.py:10-13`), deterministic to the tie-break. The design should keep it and
place it *under* the plane as a reference control rule, not extend it into a general
controller. Note also that a workload-aware router is not achievable by adding fields to
`RouteState`: the missing values are not *unmeasured*, they are *unmodelled* — nothing in the
system decides who owns a budget or a deadline.

### 3c. `workflow_runner` constructs execution context, not canonical workflow state

The per-phase prompt is built by `_build_phase_prompt` (`workflow_runner.py:173-176`):

```python
prompt = str(phase.get("prompt", ""))
prior_summary = "\n".join(f"- {p}" for p in prior) if prior else "(none)"
return prompt.replace("{goal}", goal).replace("{prior_phases}", prior_summary)
```

and `prior` is appended at `workflow_runner.py:561` as `f"{name} ({pr.status})"` — i.e. the
"workflow state" an agent phase receives is a bulleted list of **phase-name/ok-or-failed
strings**. Three consequences:

1. **It is text, not state.** There is no structure to query, no scope, no validity, no
   authority. A downstream phase cannot ask "did the test phase verify?"; it can only read the
   word `ok`.
2. **It is per-run and in-memory.** `prior` is a local list; `WorkflowRunResult`
   (`workflow_runner.py:137-171`) is serialised once at the end by `scripts/run_workflow.py:108`
   to `experiments/results/workflows/<spec>/<ts>.json`. As `spec_lifecycle.yaml` itself notes,
   those files are write-only — no reader, aggregator, or index consumes them.
3. **The one durable state derivation is git, not a state store.** `_completed_phases`
   (`workflow_runner.py:215-235`) reconstructs progress by grepping the worktree's git log for
   `[workflow] <phase>` commit markers, which is how `resume=True` works. This is a genuine
   deterministic reducer over immutable evidence (commits) — and it is exactly the shape the
   plane should generalise — but it produces a Python `set[str]` inside one function call, not
   a fact anyone else can read.

The augmentation seam confirms the framing: when `rag_augment` is on
(`workflow_runner.py:464-486`), the runner calls `retrieve → construct → render` to build a
*better prompt* and records the augmentation provenance on `PhaseResult`
(`workflow_runner.py:86-96`). It assembles **execution context for one work item**, precisely
as the proposal claims. The opt-in `emit_self` path (`workflow_runner.py:254-267,558-559` →
`knowledge_ingestion.py:512+`) is the only place the runner writes knowledge back, and it
writes an ADVISORY-or-MEASURED *finding* into the cell's own scope — a document, not a fact.

### 3d. The ledger's fields are L0/L1-grade material — but only some are actually measured

This is the most consequential part of the audit, because the proposal's `grounding_facts` (6)
asserts the ledger "already carries" a list of fields. That is true of the **declared
vocabulary** and false of the **written data**.

Two separate things share the name "ledger":

- **`LEDGER_FIELDS`** (`experiment_spec.py:44-103`) — a `frozenset` of 50+ field *names* used
  by `validate_rules` (`experiment_spec.py:397-409`) as the set of information a rule may
  require. It is a **schema vocabulary**, not storage. Nothing asserts a field in this set is
  ever written.
- **The written ledger** — `PhaseResult`/`WorkflowRunResult` JSON
  (`workflow_runner.py:64-171` → `scripts/run_workflow.py:108`), `StoryResult` JSON, and their
  KB projections `ledger_job`/`ledger_attempt` (`ledger_ingestion.py:128-269`).

I checked each declared field for a non-declaration writer. Results:

**(i) L1 facts derivable TODAY with zero new instrumentation** (source is a typed field in a
written artifact, or a deterministic function of one):

| Candidate L1 fact | Scope | Derivable from | Grade |
|---|---|---|---|
| `current_commit` | job/cell | `workflow_runner.py:207-213` `_git_head`; `PhaseResult.commit_hash` (`:71`) | `[M]` |
| `phase_completed(phase)` | workflow | `workflow_runner.py:215-235` (git commit markers) | `[M]` |
| `phases_remaining` | workflow | completed set vs `workflow.params.phases` | `[C]` |
| `accumulated_cost_usd` | job/workflow | `workflow_runner.py:151-153` `total_cost_usd` over `PhaseResult.cost_usd` (`:78`) | `[M]` |
| `tokens_consumed{in,out,reasoning,answer,explanation}` | attempt | `workflow_runner.py:526-533`; `story.py:234-235,258-259` | `[M]` |
| `cache_hit_rate`, `cache_read/write_tokens` | attempt | `workflow_runner.py:534-537` (`PhaseResult:79-81`) | `[M]` |
| `test_executed_success` | phase/job | `workflow_runner.py:435-437` via `test_runner.run_suite`; carried on records at `ledger_ingestion.py:180,264` | `[M]` |
| `execution_confidence` | attempt | `workflow_runner.py:531` `AgenticResult.confidence` | `[H]` — advisory only |
| `perturbation_strength` | job | `ledger_ingestion.py:181,266` | `[M]` |
| `model_used` / `provider` | attempt | `PhaseResult.model` (`:69`); `ledger_ingestion.py:164-166` | `[M]` |
| `phase_status(ok\|failed)` | phase | `PhaseResult.status` (`:68`) | `[M]` |
| `session_id`, `worktree_id`, `language` | attempt/job | `PhaseResult.session_id` (`:83`); `ledger_ingestion.py:177,179` | `[M]` |
| `evaluator_independent` | outcome | `solution.py:43` `SolutionMetrics` | `[M]` |
| `record_lifecycle(current\|superseded\|tombstoned)` | knowledge entity | `generate_manifest.py:75-108`; `kb_worker.py:96-103` | `[C]` |
| `supervisor_verdict(subject_id, subject_status)` | cell | `observation_ingestion.py:76-120` (`authority=ADVISORY`, `:111`) | `[H]` — advisory, never canonical |
| `cell_run_status(queued\|running\|done\|failed\|timeout)` | cell | `pipeline_status.py:30-63` over `story_status` | `[M]`, but telemetry-plane (see caveat) |

**(ii) Declared in `LEDGER_FIELDS` but written by NOTHING** (verified: zero occurrences outside
`experiment_spec.py`/`compile_experiment.py`):

`spec_id`, `policy_arm`, `policy_id`, `budget`, `due_at`, `forecast_cost`, `forecast_latency`,
`actual_cost`, `deadline_slack`, `attempt_number`, `parent_attempt_id`, `retry_reason`,
`escalation_from`, `escalation_to`, `provider_model_version`, `leased_at`, `first_token_at`,
`queue_wait_ms`, `service_time_ms`, `first_pass`, `accepted`, `rework_cost`, `reuse_value`,
`tokens_answer`/`tokens_explanation` *under those names* (the split exists as
`answer_tokens`/`explanation_tokens` at `story.py:234-235` and `workflow_runner.py:530-531`, so
this one is a naming mismatch, not a measurement gap).

**(iii) Facts requiring genuinely new measurement or new modelling:**

| Fact the proposal names | Why it is not derivable today |
|---|---|
| `budget_remaining` | Requires a budget *allocation* fact (who owns what cap, at what scope) plus spend accounting against it. `StopSpec.budget_usd` (`experiment_spec.py:253`) is per-spec config that nothing enforces. **Modelling gap, not just instrumentation.** |
| `deadline_slack` | No deadline is ever recorded anywhere. Same modelling gap. |
| `dependency_failed` | No dependency edges exist between phases or jobs; the compiled DAG is fixed (`compile_experiment.py:34`). |
| `critical_path` | Undefined without dependencies. |
| attempt/retry lineage (`attempt_number`, `retry_reason`, escalation) | `run_workflow` has no retry loop (`workflow_runner.py:580-581` breaks on failure); retries exist only in the review worker's `retry_N` status convention (`pipeline_status.py:43-49`). |
| queue timings (`leased_at`, `queue_wait_ms`, `service_time_ms`) | The BRPOP transport records status transitions but no lease timestamps. |
| `first_pass` / `accepted` | No acceptance decision is recorded; acceptance is implicit in `test_executed_success` today. |
| worker capacity / concurrency | Worker processes are unregistered; only their effects show in the status hash. |
| priority, business value, portfolio budget | Nothing in the system models these at all (L4). |
| permissions / compliance constraints | Policy exists as prose (`policy_ingestion.py:204`) and harness config, not as constraint facts. |

**(iv) The prose-projection defect.** Even for the facts in group (i), the *knowledge-plane*
projection loses their types. `build_job_record` writes:

```python
text = f"job {job_id} [{model}]: cost={cost!r} total_tokens={total_tokens!r}"   # ledger_ingestion.py:173
```

with typed `extra_fields` limited to `worktree_id`, `extractor_version`, `language`,
`test_executed_success`, `perturbation_strength` (`ledger_ingestion.py:176-182`).
`build_attempt_record` does the same (`ledger_ingestion.py:243`, extras at `:259-267`). So
**cost and tokens are only retrievable by re-parsing a formatted string**. Any plane that
reads canonical facts from the registry must therefore either (a) add typed fields to the
projection, or (b) read facts from a new fact store fed by reducers over the typed run
artifacts — with (b) preferred, since the artifacts already carry full types and the record's
`content_hash` must stay stable.

---

## 4. Proposal claims that do NOT hold (or hold only under a narrower reading)

The spec explicitly invites this. Seven items.

### 4.1 "NEW `control_agent.py` / `control_validator.py`" understates what exists — the actuation family is already built and gated

`design_input` (7) places `ControlDecision` and the validator entirely in greenfield. In fact
the canonical-state round-2 work already landed:

- `knowledge.py:141` registers `"actuation"` with `message_family="actuation"`,
  `authority=POLICY`, `evidence_class="[P]"`; `knowledge.py:155-157` derives `ACTUATION_TYPES`
  as an *allowlist*, and `message_family()` (`:160-173`) defaults any unregistered type to
  the safe `"observation"` family.
- `actuation_ingestion.py:70` fixes the action vocabulary:
  `{steer, interrupt, escalate, retry, budget, deadline}` — which already covers six of the
  proposal's nine actions (`route`, `split`, `parallelize`, `pause`, `rollback`, `stop`,
  `continue` are the additions; `escalate`/`retry` overlap).
- `actuation_ingestion.py:91-160` builds the record, **requiring `causes` at construction
  time** (`:112-116`) and using an identity of `hash(target_session_id|causes|occurred_at)`
  (`:76-88`) — one identity per candidate, never a version chain.
- `knowledge_stream.py:182-192` enforces two independent, closed-by-default gates: the
  `armed` flag (`FINOPS_ACTUATION_ARMED`, orthogonal to `FINOPS_KB_WRITE` by explicit design)
  and the lineage gate requiring `causes` to resolve to an indexed observation-family record.
- The module has **zero call sites by design**, and its docstring states the one legitimate
  future call site (human-gated Control Room handlers) and the one legitimate condition for an
  automated caller: "only once a control rule for actuation exists in a compiled
  `ExperimentSpec` — the same `requires`/`produces` gate `compile_experiment.py` already
  enforces" (`actuation_ingestion.py:8-22`).

**Why this matters:** that last sentence is the Context Abstraction Plane's own thesis, written
into the codebase months earlier. The design must therefore **extend the actuation record into
the typed `ControlDecision`** (adding `facts_used`, `snapshot_id`, `preconditions`,
`expected_effect` to its payload) rather than introduce a second, competing decision envelope.
Two decision types with two lineage gates would be strictly worse than one. This is the single
largest correction the audit makes to the proposal.

### 4.2 "The supervisor never steers" is true of the supervisor and false of the system

`grounding_facts` (8) says the supervisor "observes and flags, never steers; any control
actuation design must preserve that boundary." The first half is exactly right:
`supervise.py:1-9` ("FLAG only, never steer"), `supervise.py:56` (the monitor prompt forbids
recommending steering), `supervise.py:391` (flags emitted only for non-healthy verdicts), and
`supervisor.py:1-6` (no OpenCode client dependency, "which prevents flag persistence and
stream indexing from crossing the observation-to-control boundary").

But the *system* does actuate. `docs/supervisor_design.md:100-151` specifies a
human-gated steer door — `POST /api/flags/<sid>/steer` calling
`OpenCodeClient.send_input(session_id, prompt, delivery="steer")` with the server, not the
browser, fixing `delivery` — behind a four-part authorization boundary (`:104-116`): the
session must be in the retained flag set, resolve to exactly one cell, match the
browser-supplied `cell_id`, and pass loopback/same-origin/size/idempotency checks. Interrupt
is a two-step one-way door (`:155+`).

**Restated correctly, the invariant the design must preserve is:** *no automated path may
actuate; a human operator may actuate through a narrow, authenticated, idempotent, per-session
door.* That is a statement about **who**, not about **whether**. It also gives the design a
ready-made authorization model to reuse for the controller: any future automated actuation
must satisfy the *same* boundary plus the spec gate, not a new one.

### 4.3 "Exactly one canonical representation per fact, or explicitly unknown/conflicted" — half exists, and the missing half is not a reuse

The "exactly one current" half is genuinely implemented: `_compact_registry_index`
(`generate_manifest.py:111-221`) reduces the append-only index to **one row per `entity_id`**,
with supersession resolved by pointer (`:166-171`), tombstones treated as terminal
(`:186-192`), and a documented degenerate fallback (`:194-197`). `registry.py:68` exposes
`current | superseded | tombstoned`.

The "or explicitly unknown/conflicted" half does **not** exist:

- `_derive_lifecycle` (`generate_manifest.py:75-108`) can emit only three states; there is no
  `conflicted` and no `unknown`.
- The only conflict machinery in the repo is retrieval's ranking penalty
  (`retrieval.py:51,414-415`) — which, per §3a, down-ranks rather than reports.
- Absence is indistinguishable from exclusion in retrieval results (§3a, point 5).

So `conflicted` and `unknown` are **new lifecycle/epistemic states to be designed**, not
existing machinery to be reused. The design should say so plainly rather than implying the
registry already models them.

### 4.4 The existing gate proves *schema availability*, not *fact currency* — which is the strongest argument FOR fact contracts

`validate_rules` (`experiment_spec.py:373-409`) computes `available = LEDGER_FIELDS ∪ {produces
of every measurement rule}` and errors when a rule's `requires` is not in that set. Three
observations, all of which the design should cite as motivation:

1. **It checks names, not values.** `budget` and `deadline_slack` are in `LEDGER_FIELDS`
   (`experiment_spec.py:51,56`) and written by nothing (§3d(ii)). A control rule requiring
   `deadline_slack` **passes the gate today** and would consume a value that has never existed.
   This is the concrete failure the proposal's `max_age_seconds` / `on_missing` contract fixes.
2. **It does not distinguish planes when checking requires.** The loop at
   `experiment_spec.py:402-408` applies the same check to measurement and control rules alike;
   the `plane` field is validated for membership (`:387-390`) but never used to differentiate
   the requirement semantics. Fact contracts should make direction explicit.
3. **The gate is already duplicated.** `step_routing.py:207-238` `validate_preferences` is a
   second implementation of the same idea over a different vocabulary (`MEASURED_SIGNALS`,
   `:63-65`), with its own hard-coded `FORBIDDEN_SIGNALS = {"confidence"}` (`:68`) — note that
   `confidence` is simultaneously forbidden there and present in `LEDGER_FIELDS`
   (`experiment_spec.py:99`), because the two gates encode different judgments about the same
   field. A third parallel gate for fact contracts would be a mistake; the design should
   generalise `RuleSpec.requires` so that both existing gates can eventually express
   themselves in it.

### 4.5 `epistemic_status` partly duplicates an axis that already exists

`design_input` (3) proposes `epistemic_status ∈ {observed, verified, derived, declared,
advisory}` **alongside** `authority`. But `KnowledgeRecord` already carries *two* axes:
`authority` (`knowledge.py:322`, the ordinal trust ranking) **and** `evidence_class`
(`knowledge.py:335`, `[M]/[C]/[H]/[P]/[X]`), and producers already use them jointly and
non-redundantly — e.g. `quality_ingestion` maps SonarQube/LSP → `MEASURED`/`[M]` but entropy →
`DERIVED`/`[C]`, and `derive_phase_record` (`knowledge_ingestion.py:466-468`) selects
`MEASURED` vs `ADVISORY` *based on whether `test_executed_success` is a real bool*. That last
rule is very nearly the proposal's `observed` vs `verified` distinction, already implemented.

The design should therefore **map** `epistemic_status` onto the existing pair (or justify the
third axis explicitly with cases the pair cannot express) rather than adding a third
overlapping provenance field. Adding a third axis without a mapping rule invites the exact
failure the authority hierarchy was built to prevent: two producers disagreeing about which
field is authoritative.

### 4.6 "Token events" as L0 evidence overstates the telemetry plane

`design_input` (1) lists "token events" among L0's immutable observations. Live token/tool
events go to `live.LivePublisher` on Redis DB 1 (`live.py:23,52,113`) — pub/sub, ephemeral,
unscoped, with no content hash, no artifact, and no identity. They are consumed by the Control
Room SSE terminal and by `supervise.py:285+`'s activity sampling. They are *not* durable
evidence. Only their per-phase aggregates (`PhaseResult.tokens`, `workflow_runner.py:526-533`)
survive. The design's own hard rule — "the plane reads canonical state from the knowledge
plane, never from live telemetry" — is correct and should be stated as a consequence of this
fact, not merely as a preference.

### 4.7 Two smaller corrections

- **`JobRecord` / `AttemptRecord` are documentation, not code.** They are described in
  `.claude/rules/mental-model.md` and `src/instrument/CONTEXT.md`, but no such dataclasses
  exist in `src/` (verified by search). The written per-run types are `PhaseResult`
  (`workflow_runner.py:64-135`) and `StoryResult`/`SessionResult` (`story.py`). Design
  language should say "the ledger schema as documented" and cite the real types.
- **`spec_lifecycle` as "the plane's first consumer" is a forward reference, not prior art
  yet.** `grounding_facts` (9) calls it RUNNING NOW; the spec
  (`experiments/specs/spec_lifecycle.yaml:20-27`) confirms `SOURCE_TYPES`
  (`knowledge.py:125-142`) has no `spec` type today and the registry contains no spec records.
  It is the right first consumer, but the design must not assume its output exists.

---

## 5. What the design phase inherits (constraints derived from this audit)

Stated here so the design can cite them rather than re-derive them.

1. **Build the fact plane above the evidence plane; reuse identity, authority, validity, and
   supersession verbatim.** `compute_entity_id`/`compute_knowledge_id`
   (`knowledge.py:184-203`), the `Authority` ordering (`:61-85`), `valid_from`/`valid_to`
   (`:323-324`), and `supersedes` (`:348`) are exactly the primitives a CanonicalFact needs.
   Do not fork them.
2. **The registry compaction is the validity spine.** `generate_manifest.py:75-108,111-221`
   already answers "which version is current" deterministically. Fact currency should reduce
   through the same mechanism, extended with `conflicted`/`unknown` (§4.3).
3. **Extend the actuation record; do not add a second decision type.** §4.1.
4. **The gate to generalise is `validate_rules`, and its current weakness is the argument for
   fact contracts.** §4.4. Any new gate must subsume, not parallel, `validate_preferences`.
5. **Facts must be typed at derivation time.** The prose projection in `ledger_ingestion.py:173,243`
   means the design cannot read numeric facts back out of the registry; reducers should run
   over the typed run artifacts (`workflow_runner.py:64-171` → `run_workflow.py:108`) and emit
   typed facts. §3d(iv).
6. **Preserve the one-way scope filter's semantics while adding hierarchy.** `scope_excluded`
   (`retrieval.py:392-406`) treats empty as *unknown/legacy*, never *global*. A hierarchical
   scope must keep that: inheritance is an explicit parent link, not an empty-string wildcard.
7. **Keep the two Redis planes separate.** Knowledge on DB 2 (`knowledge_stream`), telemetry on
   DB 1 (`live.py:23`). The plane reads facts from the knowledge plane only. §4.6.
8. **Honour measure-before-policy literally.** Group (i) of §3d is the *only* set of facts a
   first control rule may consume without new instrumentation. `budget_remaining` and
   `deadline_slack` — the two most tempting control inputs — are modelling gaps, not
   measurement gaps, and must be declared before they can be measured.
9. **Actuation authority is human-gated.** §4.2. Any automated actuation the design proposes
   must pass both the spec gate and the existing authorization boundary, and the design should
   state plainly that it proposes no automated actuation in its first increment.

---

## 6. Open items handed to the design phase

These are questions the audit surfaced that the `open_questions` block does not directly ask,
and that the design should answer or explicitly defer:

1. **Where do facts live?** A new store, a `fact` `source_type` in the existing registry
   (`knowledge.py:125-142`), or a derived index like the manifest? The audit favours a
   registered `source_type` so the supersession/lifecycle machinery applies unchanged — but
   that requires solving §3d(iv)'s typing problem.
2. **Does a fact supersede by `entity_id` (one fact per subject+predicate+scope) or accumulate
   like observations (`observation_ingestion.py:62-70` folds the timestamp into identity so
   verdicts never collide)?** These are opposite identity strategies and the choice determines
   whether "current value" is a lookup or a max-by-time scan.
3. **What re-derives a fact when its upstream evidence is superseded** — a staleness flag
   computed at read time (like `_derive_lifecycle`, cheap and always correct) or an eager
   re-derivation pass (expensive, needs a scheduler)? The registry precedent is read-time
   derivation.
4. **How does `epistemic_status` map onto `authority` × `evidence_class`?** §4.5.
5. **Which of the nine proposal actions ship first**, given that only `retry`, `escalate`,
   `budget`, `deadline`, `steer`, `interrupt` are in the existing `ACTUATION_KINDS`
   (`actuation_ingestion.py:70`) and `route` is already implemented deterministically
   (`step_routing.py:424-469`)?

---

## Appendix — citation index

| Concern | Primary citations |
|---|---|
| Identity + authority + record schema | `knowledge.py:61-85,104-142,160-173,184-212,227-297,300-431` |
| Retrieval as ranking | `retrieval.py:45-71,242-270,345-367,392-406,420-455,565-591,610-658,973-981,1018` |
| Executor prompt construction | `prompt_constructor.py:42,108-142,156-207,345,461,518-589` |
| Phase execution + per-phase ledger | `workflow_runner.py:64-135,137-171,173-176,207-235,242-267,422-587` |
| Model routing policy | `step_routing.py:50-68,207-238,262-292,298-315,321-330,335-418,424-469` |
| Spec schema + the gate | `experiment_spec.py:44-103,157-187,249-270,373-409,412-452` |
| Compiler DAG + rule evaluation | `compile_experiment.py:34,87-96,107-128,142-209,215-243,257-330,343-377` |
| Ledger→KB projection | `ledger_ingestion.py:59-69,75-96,128-198,204-269,275-309` |
| Observation (supervisor verdicts) | `observation_ingestion.py:52-56,62-70,76-120` |
| Actuation envelope + gates | `actuation_ingestion.py:1-38,62-70,76-160`; `knowledge_stream.py:129-194` |
| Registry lifecycle | `kb_worker.py:96-103,233-303`; `generate_manifest.py:75-108,111-221`; `registry.py:68,176-199,220-232` |
| Supervisor boundary | `supervisor.py:1-6,15-19,106-157`; `supervise.py:1-9,56,333-392`; `docs/supervisor_design.md:3-8,100-151` |
| Telemetry plane | `live.py:23,52,113`; `pipeline_status.py:23-63` |
| Policy records | `policy_ingestion.py:127,204`; `retrieval.py:63-71` (POLICY excluded from fusion) |
| Self-build emit | `knowledge_ingestion.py:93,119,450-509,512+`; `workflow_runner.py:254-267,558-559` |
| Prior canonical-state design | `docs/canonical_state_r2_design.md:180-292`; `docs/canonical_state_base_design.md:36-120,407+` |
