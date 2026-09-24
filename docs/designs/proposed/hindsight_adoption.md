---
status: proposed
---

# Hindsight pattern adoption contract

**Status:** PROPOSED (2026-09-24, controller-directed deep dive)

## 1. Decision

This document is the contract for borrowing patterns from the Hindsight dossier into
`agentic_dynamics`. It separates three outcomes: adopt a small pattern in our existing
mechanisms, refuse a pattern because it conflicts with our truth or control contract, or
defer a larger pattern to a named, measured follow-up. [P]

The adoption is **inspiration, not integration**. No Hindsight package, service call, SDK,
MCP server, plugin, endpoint, or vendored runtime is part of this proposal. Any future
experiment that treats Hindsight as an external arm must be separately specified, admitted,
measured, and reviewed. [P] [C]

The central local constraint is measured-or-absent: Hindsight's useful conservatism may
protect our records and renders, but an LLM must not become the source of a measured value,
an authority decision, a spend decision, or a permanence decision. [P] [C]

## 2. Evidence boundary

The external claims below are bounded to the committed dossier, not to a fresh network read.
The dossier records Hindsight source commit `a7eafb2f395b3c905e9e577da691414d3ca8d08c`, docs
v0.10, and the paths read from the shallow clone. [X] The local claims are grounded in the
repository surfaces named in each target row. [C]

The load-bearing evidence is:

- Hindsight's `engine/reflect/structured_doc.py` says raw markdown gives an LLM an
  opportunity to drift and makes a structured document the source of truth, with markdown
  as a deterministic render. Unchanged blocks are opaque, verbatim fragments. [X]
- Hindsight's `engine/reflect/delta_ops.py` separates malformed operation **shape** from
  unknown **references**, addresses sections and blocks by stable ids rather than positions,
  copies unmentioned content unchanged, and skips invalid references conservatively. [X]
- Hindsight's `engine/mental_model_refresh.py` names dry-run, watermarks, fallback reasons,
  and per-refresh traces. It also records the limitation that deletions are invisible to its
  staleness gate. [X]
- Hindsight's `engine/consolidation/prompts.py` requires reasons, preserves history, and
  states **NO COMPUTATION**: never calculate, derive, or adjust numeric values from partial
  facts. [X]
- Hindsight's `engine/search/fusion.py` uses RRF and documents that a small retrieval arm can
  be buried; its temporal analyzer warns that an untrusted date constraint is worse than no
  constraint because failure becomes invisible downstream. [X]
- Hindsight's `engine/reflect/agent.py` prioritizes curated material, falls back through
  observations to raw facts, and tightens bounded tool calls against remaining context.
  [X]

Those findings are not evidence that Hindsight is correct for this repository. The
dissection records the material differences: this repository carries authority, evidence
classes, tombstones, projection watermarks, admission leases, cost provenance, independent
verification, and a permanence gate; the external service does not provide those local
economics and control guarantees. [X] [C]

## 3. Adoption rules

1. Preserve the local authority order `POLICY > SOURCE > MEASURED > DERIVED > ADVISORY`.
   Curated text may improve navigation, but curation is not a replacement for evidence
   authority. [C] [P]
2. Preserve unknown, unavailable, and failed states. `null`, absent, failed, and empty are
   not interchangeable with zero or success. [C] [P]
3. Preserve history. Updates must retain lineage, reasons, and tombstones where the local
   contract requires them; deletion-blind freshness is explicitly refused. [C] [X]
4. Preserve scope. A missing or empty scope never means global, and no retrieval or
   augmentation pattern may widen a cell's scope. [C] [P]
5. Preserve gates. No adopted refresh, retrieval, analysis, or tool may bypass admission,
   test execution, independent verification, the control packet, or the permanence gate.
   [C] [P]
6. One concern per implementation unit. If a proposal needs more than roughly four files,
   two concerns, or more than one proof gate, it becomes a follow-up rather than a large
   execute slice. [P]

## 4. Target contract

The target rows below are the complete map requested by the directive. Each row names what
is borrowed, what is refused or deferred, the exact files, one proving gate, and one primary
risk. A row marked **ready** is a planned bounded unit, not a claim that its code has landed
in this documentation-only slice. [P]

### 4.1 Mental model: curated generated file map

**Adopt.** Borrow the structured-document rationale as guidance: keep stable, human-owned
prose distinct from machine-derived entries; preserve untouched material; describe freshness
with separate "seen" and "written" questions; and use named fallback or unknown states.
The existing generator remains the authority for generated output. [X] [C]

**Refuse or defer.** Do not introduce a generic delta engine, parse all Markdown into a
lossy typed AST, or claim that a refresh trace or per-document watermark already exists.
The dossier's warning about typed-AST collapse and its deletion-blind staleness limitation
make both choices unsafe without a separate design. [X]

**Exact target files.** `agent_config/mental-model.md` is the authored source;
`.opencode/instructions/mental-model.md` and `.claude/rules/mental-model.md` are generated
outputs. [C]

**One gate.** `python3 scripts/_gen_instructions.py --check` plus the existing
`tests/test_agent_config_render.py` render gate, treated as one generated-surface gate.
[P]

**Risk.** Readers may mistake Hindsight's curated "mental model" for this repository's
generated file map and infer that automatic belief refresh is authoritative. [X] [C]

**Ready unit.** `u2_curated_surface_guidance`: add only conservative source guidance and
regenerate the mirrors. [P]

**Follow-ups.** F1, a typed operation format for hybrid documents, must specify stable ids,
shape/reference validation, byte-preserving copy-through, and full-refresh fallback before
any implementation. F2, scoped `last_seen`/`last_written` state, must specify deletion and
tombstone behavior. F3, generator refresh traces, must specify durable retention and
provenance before adding storage. [P] [X]

### 4.2 Agents: operator behavior and evidence discipline

**Adopt.** Give the AIO a concise operational rule: read current control state, respect cell
scope and authority, treat failed retrieval as failed rather than empty, preserve unknowns,
and record consequential refresh or routing decisions. This is a local operating rule, not a
new memory persona or a synthetic belief loop. [X] [C]

**Refuse or defer.** Do not instruct an agent to consolidate facts into unverified beliefs,
steer a run from an observe-only rail, submit a workflow from inside a child run, or replace
the permanence decision with a curated answer. [C] [P]

**Exact target files.** `agent_config/agents/aio-control.md` is the authored source;
`.opencode/agents/aio-control.md` and `.claude/agents/aio-control.md` are generated mirrors.
[C]

**One gate.** `tests/test_agent_config_render.py` with
`python3 scripts/_gen_instructions.py --check` as the generated-agent gate. [P]

**Risk.** Guidance that sounds like a reflect loop could silently grant an agent authority
to infer, steer, or spend. The text must retain the controller/AIO distinction and the
observe-only rule. [C] [P]

**Ready unit.** `u3_agent_refresh_guidance`: add the operator rule in the source and
regenerate both mirrors. [P]

**Follow-up.** F4, a read-only trace/reporting surface for agent refresh decisions, requires
a named schema, no network write, scope binding, and a static or pure gate before a tool or
plugin is added. [P] [X]

### 4.3 Tools: no new adapter in this proposal

**Adopt.** Apply the pattern only as a tool-contract criterion: a future read tool may expose
metadata, provenance, scope, and named unavailable states rather than flattening them into a
successful empty response. [X] [C]

**Refuse or defer.** Do not add a Hindsight client, MCP bridge, SDK wrapper, external memory
endpoint, or tool that writes knowledge as a side effect of retrieval. Existing adapters
compose the repository's own commands and control gates. [P] [C]

**Exact target files.** The hand-authored tool seam is `.opencode/tools/*.ts`; no existing
tool is selected for modification by this contract. If F4 is approved, its named tool must
be an explicit new file under `.opencode/tools/` and its command implementation must be
identified before coding. [C] [P]

**One gate.** A future F4 static tool-contract gate: inspect the selected tool's declared
input/output/error schema and assert no network or knowledge write path; no runtime service
gate is appropriate for this deferred item. [P]

**Risk.** A convenience adapter can turn an external service into an undeclared dependency,
or make a failed leg look like an empty successful answer. [P] [X]

**Follow-up.** F4 is the only tool follow-up; it is not scheduled in the eight-unit plan.
[P]

### 4.4 Hooks: preserve the local plugin seam

**Adopt.** Borrow traceability as a design requirement for any future local hook: record
what triggered it, which scope it read, what it did, and whether it was skipped or failed.
The hook must remain observe-only unless a separately authorized control action exists.
[X] [C]

**Refuse or defer.** Do not install a Hindsight hook, auto-refresh hook, external webhook,
or plugin that writes the knowledge stream or changes routing. [P]

**Exact target files.** `.opencode/plugins/aio-context.ts` and `.opencode/plugins/README.md`
are the current hand-authored plugin seam. No file in this seam is changed by this unit or
by the planned adoption units. [C]

**One gate.** A future F5 hook gate: a no-network, no-KB-write plugin test or static audit
that proves the hook's inputs, outputs, scope, and skip/failure behavior. [P]

**Risk.** A hook runs outside the obvious phase boundary and can bypass admission,
provenance, or the one-writer rule while appearing to be harmless context enrichment. [C]

**Follow-up.** F5 is a plugin-seam evaluation only if a concrete local gap is named; the
Hindsight service itself is never the gap-closing mechanism. [P]

### 4.5 Setup: no external memory configuration

**Adopt.** Keep setup explicit about local generated surfaces and permissions. The only
borrowed setup principle is fail-closed configuration: an absent or unknown integration
must not be interpreted as enabled or free. [C] [P]

**Refuse or defer.** Do not add a Hindsight URL, API key, package, MCP server, integration
profile, or external memory environment variable to `opencode.json`. The directive is
pattern adoption, not service integration. [P]

**Exact target files.** `opencode.json` is the hand-authored project configuration. No
change is proposed. [C]

**One gate.** A future F6 configuration audit: parse `opencode.json` and assert that the
approved command and permission surface contains no undeclared external-memory dependency.
[P]

**Risk.** A setup-only change can make an external service a hidden requirement for cells,
breaking no-egress execution and reproducibility. [P] [X]

**Follow-up.** F6 is a no-dependency configuration audit, not an integration task. [P]

### 4.6 Architecture: make the boundary authoritative

**Adopt.** Record the inspiration-only boundary, the conservative refresh pattern, and the
fact that knowledge, measurement, control, and reporting remain separate planes. The
dependency direction and the local gates remain authoritative. [C] [P]

**Refuse or defer.** Do not add Hindsight to the dependency graph or create a parallel
memory plane. Do not copy deletion-blind freshness, belief consolidation, or curation-first
ordering over the evidence authority axis. [X] [C]

**Exact target files.** `ARCHITECTURE.md` is the architectural authority. Related claims,
if a later design is approved, belong in the relevant existing file under
`docs/architecture/current/`; this proposal does not edit those files. [C]

**One gate.** `tests/test_dependency_direction.py` is the architecture-boundary gate. [P]

**Risk.** A broad architecture edit can turn an external comparison into an accidental
commitment, or create a tier violation by making a reporting or knowledge helper depend on
control internals. [C] [X]

**Ready unit.** `u8_architecture_boundary`: record only the no-integration and dependency
direction boundary. [P]

**Follow-up.** F7 is a separate design for scoped freshness and typed document operations;
it must not be smuggled into the architecture edit. [P]

### 4.7 Knowledge base: preserve evidence, history, and absence

**Adopt.** Use the dossier's required reasons, history preservation, conservative invalid
operation behavior, and NO COMPUTATION rule as confirmation of local contracts. In our own
terms, every producer keeps authority and evidence class, lineage uses `supersedes` or
`causes`, deletion is a reasoned tombstone, and an absent numeric observation stays absent.
[X] [C]

**Refuse or defer.** Do not replace deterministic producers with LLM fact extraction, do
not write consolidated beliefs as measured facts, and do not derive arithmetic from partial
records. Do not copy Hindsight's deletion cascade or deletion-blind staleness behavior into
the append-only registry. [X] [C]

**Exact target files.** The immediate proof seam is
`src/agentic_dynamics/knowledge/knowledge.py`. The surrounding producer and projection
surfaces are `src/agentic_dynamics/knowledge/knowledge_stream.py`,
`src/agentic_dynamics/knowledge/knowledge_ingestion.py`,
`src/agentic_dynamics/knowledge/ledger_ingestion.py`,
`src/agentic_dynamics/knowledge/story_ingestion.py`,
`src/agentic_dynamics/knowledge/review_ingestion.py`,
`src/agentic_dynamics/knowledge/policy_ingestion.py`,
`src/agentic_dynamics/knowledge/code_ingestion.py`,
`src/agentic_dynamics/knowledge/quality_ingestion.py`,
`src/agentic_dynamics/knowledge/record_factory.py`,
`scripts/kb_worker.py`, `scripts/generate_manifest.py`, and `scripts/registry.py`. [C]

**One gate.** `tests/test_knowledge.py` is the knowledge-contract gate: operation, reason,
lineage, authority, evidence class, and absent values must round-trip without service
imports or arithmetic. [P]

**Risk.** A consolidation-inspired convenience can erase provenance, collapse unknown into
zero, or shrink append-only state. Any conflict is resolved in favor of the local evidence
and tombstone contract. [C] [X]

**Ready unit.** `u4_knowledge_epistemic_proof`: make this boundary explicit in the local
knowledge contract and add the focused existing-test assertion. [P]

### 4.8 Retrieval: conservative multi-leg evidence

**Adopt.** Retain deterministic dense-plus-lexical RRF, hard per-cell scope filtering,
evidence cards, and named failure or unavailable outcomes. Borrow the dossier's warning that
a failed retrieval leg is not an empty result, and that an untrusted extracted constraint
must not masquerade as a real constraint. [X] [C]

**Refuse or defer.** Do not add Hindsight's temporal, graph, cross-encoder, or interleave
arms in this contract. Neo4j being projected does not by itself authorize a new fusion arm;
any such arm needs an experiment spec, measured quality/cost/latency, and an independent
gate. [X] [C] [P]

**Exact target files.** The immediate seam is
`src/agentic_dynamics/knowledge/retrieval.py`. Its local projection/fusion context is
`src/agentic_dynamics/knowledge/embeddings.py`,
`src/agentic_dynamics/knowledge/graph.py`,
`src/agentic_dynamics/knowledge/neo4j_vectors.py`, and
`src/agentic_dynamics/knowledge/knowledge_stream.py`. [C]

**One gate.** `tests/test_retrieval.py` is the dependency-free retrieval-bound gate: an
outside-scope candidate never reaches fusion, and a leg failure remains distinguishable from
an empty successful result. [P]

**Risk.** More arms can improve recall while hiding extraction failure, widening scope, or
making an unavailable projection look current. The existing hard pre-filter and named
failure state are non-negotiable. [C] [X]

**Ready unit.** `u5_retrieval_failure_proof`: make the failure distinction explicit without
adding a temporal, graph, interleave, or external arm. [P]

**Follow-up.** F8 is a research arm for temporal and eventually graph retrieval, with an
ExperimentSpec, corpus-backed baseline, cost/latency measurement, and a comparison gate.
[P] [X]

### 4.9 Augmentation: preserve the base prompt and budget boundary

**Adopt.** Retain the retrieve -> construct -> render seam, named fallback modes, bounded
context construction, and phase non-blocking behavior. Borrow the reflect loop's principle
that a tool result which is unusable or over budget is worse than a bounded round trip. [X]
[C]

**Refuse or defer.** Do not add a Hindsight reflect agent, tool loop, service call, or
knowledge write to prompt construction. Augmentation must not publish facts, bypass
admission, or replace a valid base prompt with partial or empty augmented content. [C] [P]

**Exact target files.** `src/agentic_dynamics/knowledge/augment.py` and
`src/agentic_dynamics/knowledge/prompt_constructor.py` are the augmentation seam. [C]

**One gate.** `tests/test_prompt_constructor.py` is the pure augmentation gate: failure
preserves the base prompt, the fallback reason remains inspectable, and no optional service
or knowledge write is required. [P]

**Risk.** A budgeted multi-tool loop can look like harmless context expansion while spending
outside the phase lease or allowing partial evidence to become an instruction. [C] [X]

**Ready unit.** `u6_augmentation_fallback_proof`: make fallback and budget boundaries
explicit with base-dependency tests only. [P]

**Follow-up.** F9 is a measured comparison of a local budgeted reflection loop against the
current seam. It requires admission accounting and cost/quality/latency evidence before any
implementation. [P] [X]

### 4.10 Analysis: corpus provenance and unavailable outcomes

**Adopt.** Keep analysis tied to the canonical registry corpus and make provenance, source
identity, and unavailable input visible. Borrow refresh-trace and cadence questions only as
analysis design inputs, not as permission to synthesize missing results. [X] [C]

**Refuse or defer.** Do not render an unreadable corpus as zero, stale data, or a successful
empty experiment. Do not make the reporting plane an LLM belief store. [C] [P]

**Exact target files.** The immediate seam is
`src/agentic_dynamics/reporting/canonical_corpus.py`; downstream report and lab consumers
include `src/agentic_dynamics/reporting/game_report.py`,
`src/agentic_dynamics/reporting/lab_contract.py`,
`src/agentic_dynamics/reporting/lab_manifest.py`,
`src/agentic_dynamics/reporting/measurement_coverage.py`,
`src/agentic_dynamics/reporting/workflow_metrics.py`, and the maintained
analysis entry points `scripts/analyze_worktrees.py`, `scripts/analyze_trajectories.py`,
and `scripts/generate_manifest.py`. [C]

**One gate.** `tests/test_data_flow.py` is the reporting provenance gate: corpus identity
and provenance survive, while unavailable input remains a named unavailable state distinct
from an empty measured result. [P]

**Risk.** A refresh or compaction convenience can turn a missing projection into a confident
number, contaminating policy inputs and economic conclusions. [C] [P]

**Ready unit.** `u7_analysis_provenance_proof`: preserve the canonical-corpus boundary and
prove it in the existing data-flow target. [P]

**Follow-ups.** F10 covers durable refresh traces for analysis generators. F11 covers
coalescing and minimum-interval scheduling for expensive rebuilds. Both require a named
cadence, cost, and corpus-backed measurement before code. [P] [X]

### 4.11 Further surfaces proved by the dive: self-knowledge and derived surfaces

**Adopt.** Treat the repository's self-knowledge records and derived surfaces as the local
analogs of curated models and refresh traces, but keep their semantics recorded rather than
synthetic. A session close, decision record, belief update, scoreboard, or generated surface
must remain attributable to its source event and current revision. [C] [X]

**Refuse or defer.** Do not add a second reflection store, make a generated snapshot the
current control packet, or use a curated document to overrule the controller, admission
leases, supervisor flags, or permanence gate. [C] [P]

**Exact target files.** The self-knowledge seams are `scripts/session_open.py`,
`scripts/session_close.py`, `scripts/decision_record.py`, `scripts/reflect.py`,
`src/agentic_dynamics/knowledge/session_ingestion.py`,
`src/agentic_dynamics/knowledge/decision_ingestion.py`,
`src/agentic_dynamics/knowledge/reflection_ingestion.py`,
`src/agentic_dynamics/knowledge/belief_ingestion.py`, and
`src/agentic_dynamics/knowledge/scoreboard.py`. Derived-surface seams are
`scripts/_gen_instructions.py`, `scripts/sync_surfaces.py`, `scripts/spec_status.py`,
`scripts/build_data.py`, and `scripts/generate_manifest.py`. [C]

**One gate.** The existing `tests/test_data_flow.py` provenance gate is the single gate for
this deferred surface family: it must show source identity and named unavailable states
without treating a derived render as a measured fact. [P]

**Risk.** The analogy to Hindsight's reflection can blur the distinction between a recorded
decision and an LLM-generated belief, or between a stale snapshot and live control state.
[X] [C]

**Follow-up.** F12 is a separate self-knowledge refresh-trace design, if the controller
names a concrete gap. It must not alter the live Control Room surfaces or the L33
attention/order/age work. [P]

## 5. Planned units and boundaries

The plan expands this contract into eight bounded units. Their combined budget hint is
`$6.00`, within the workflow's `$8.00` ceiling; the budget is not evidence that any unit
has run or that a future cost is zero. [P]

| Unit | Concern | Exact implementation boundary | One gate |
|---|---|---|---|
| `u1_adoption_contract` | This contract | `docs/designs/proposed/hindsight_adoption.md` | `tests/test_doc_lifecycle.py` |
| `u2_curated_surface_guidance` | Generated mental-model guidance | `agent_config/mental-model.md` plus generated mirrors | `tests/test_agent_config_render.py` and generator check |
| `u3_agent_refresh_guidance` | AIO operator guidance | `agent_config/agents/aio-control.md` plus generated mirrors | `tests/test_agent_config_render.py` and generator check |
| `u4_knowledge_epistemic_proof` | Authority/history/absence proof | `src/agentic_dynamics/knowledge/knowledge.py`, `tests/test_knowledge.py` | `tests/test_knowledge.py` |
| `u5_retrieval_failure_proof` | Scope and failed-leg proof | `src/agentic_dynamics/knowledge/retrieval.py`, `tests/test_retrieval.py` | `tests/test_retrieval.py` |
| `u6_augmentation_fallback_proof` | Base-prompt fallback proof | `src/agentic_dynamics/knowledge/augment.py`, `src/agentic_dynamics/knowledge/prompt_constructor.py`, pure test | `tests/test_prompt_constructor.py` |
| `u7_analysis_provenance_proof` | Canonical-corpus unavailable proof | `src/agentic_dynamics/reporting/canonical_corpus.py`, `tests/test_data_flow.py` | `tests/test_data_flow.py` |
| `u8_architecture_boundary` | No-integration boundary | `ARCHITECTURE.md` | `tests/test_dependency_direction.py` |

This document does not claim that units `u2` through `u8` are implemented. Their later
slices must touch only their declared files, use base dependencies, keep generated mirrors
generated, and commit a diff. [P]

## 6. Explicit non-adoption list

- Hindsight runtime, package, service, API endpoint, SDK, MCP server, or plugin. [P]
- LLM consolidation as the source of measured facts, numeric values, authority, or the AIO
  self-knowledge spine. [X] [C]
- Deletion-blind freshness or cascade deletion that shrinks local append-only history.
  [X] [C]
- Curation priority replacing evidence authority. [X] [C]
- Retrieval arms, interleave fusion, cross-encoder ranking, or temporal extraction without a
  separately measured experiment. [X] [P]
- A reflection loop that spends without a lease, publishes knowledge as a side effect, or
  steers an observe-only rail. [C] [P]
- Changes to the Control Room live surfaces or the L33 attention/order/age work. [P]

## 7. Completion test for this contract

This proposal is complete when its front matter is `status: proposed`, every named target
has an exact file list, one gate, one risk, and a bounded adoption/refusal/defer decision,
and all oversized ideas have a named follow-up. [P] The documentation lifecycle gate is
`tests/test_doc_lifecycle.py`; later implementation units retain the individual gates in
the table above. [P]
