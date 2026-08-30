---
status: proposed
---

# The trajectory graph — session.jsonl as structure + semantics (Part D of the graph-analysis family)

**Status: PROPOSED (2026-08-29, operator-directed).** The next analysis layer after the
Δ-entropy instrument: analyze each agent's `session.jsonl` transcript as BOTH a **graph** (the
steps as typed nodes, the transitions as edges — the tool-use sequencing, the thought-process
cycles, the per-model grammars) and a **semantic surface** (the thinking blocks' content —
embedded, clustered into roles, profiled per model). Two stores, each for its purpose: **neo4j
for the structure** (the trajectory graphs, the motifs, the fingerprints) and the **existing
chroma `session_embeddings` collection for the semantics** (the thinking content) — both
already running in the machine. The operator's taxonomy observation is the load-bearing pin:
**the models emit different artifacts** — claude CLI emits thinking blocks, gpt emits patches,
opencode records reasoning events — so the step-classifier's contract must handle the
modalities before any comparison is meaningful.

## 1. What is analyzed (the input surface)

`session.jsonl` per agent session — already parsed into step-level rows by
`scripts/analyze_trajectories.py` (steps, tool calls, tokens, latency per step) — the new
layer adds: the **step types** (think / tool_call / output), the **transition edges**, the
**thinking-block text** (when the modality carries it), and the **outcome join** (the session's
cell → `test_executed_success`).

**The model-artifact taxonomy (the step-classifier's contract — pinned):**

| modality | emitted by | step-classification impact |
|---|---|---|
| **thinking blocks** | claude CLI (the reasoning output) | a `think` step type carrying the block text — the semantic-range leg's input |
| **patches** (unified diffs) | gpt-family (the output shape) | a `patch` step type — distinct from an edit-tool call (the model emitted the diff vs the tool applied it) |
| **reasoning events** | opencode sessions (the recorded events) | a `think` step type (the reasoning event text when present) |
| **tool calls** | all backends (the agent's tool use) | a `tool_call` step type with the tool name + the arguments shape + the exit code |
| **text output** | all backends | an `output` step type (the artifact text) |

The classifier maps each session event to exactly one step type; an event whose modality is
unrecognized is flagged, never guessed (the same discipline as the confidence-null).

## 2. Part D1 — the trajectory graph (neo4j — the structure)

**The ingestion:** each session.jsonl → a step subgraph: the step nodes (typed, with the
attributes: tool name, tokens, duration, exit) + the transition edges (step N → N+1, typed by
the pair: think→tool_call, tool_call→tool_call, tool_call→think, …) + the session/cell/campaign
containment edges (the graph already carries the Knowledge nodes; the sessions attach as their
own node family).

**The analyses the graph enables:**

1. **The per-model grammars** — the tool-transition matrices (the directed edge weights per
   model): the edit→test→bash→read cycles, the retry loops, the think-before-edit ratios. Each
   model's trajectory grammar becomes a **fingerprint vector** — comparable across the corpus,
   and the qualitative findings' "work-style" texture (the hygiene/debt profiles) gains a
   process-side twin.
2. **The motifs** — the loop/cycle detection as graph queries: the flail signature (the
   repeated failure cycles — the flail_triggers lab's evidence, now a queryable motif), the
   think→act→reflect cycles, the dead-end branches (a tool_call with no subsequent edit). The
   supervisor's "moving in circles" lens becomes automated: a session whose step graph has
   repeating identical subpaths IS the loop signature.
3. **The per-step cost structure** — the tokens/duration attached to the step nodes: where the
   cost concentrates (thinking vs tool calls vs outputs), the cost-per-step-type profiles per
   model — the routing posture's quantitative side extended to the process.

## 3. Part D2 — the semantic range of thinking (chroma — the semantics)

**The pipeline:** the thinking-block texts (the `think` step type's content, from the claude
thinking blocks + the opencode reasoning events) → embedded into the existing
`session_embeddings` collection → **clustered into semantic roles** (planning / debugging /
self-correction / metacognition / explanation / requirement-elaboration) → the per-model
semantic profiles.

**The measured constructs:**

1. **The semantic range** — the diversity of the roles a model's thinking covers (the cluster
   entropy of its thinking blocks): a wide-range thinker (planning + metacognition +
   self-correction) vs a narrow one (debugging only). The operator's "the semantic range of
   thinking" operationalized.
2. **The dwell patterns** — where the thinking concentrates in the trajectory: before first
   edits (planning), after test failures (debugging/self-correction), at the end
   (explanation/verification) — the think-placement profile per model.
3. **The thinking-to-output ratio** — the tokens spent thinking vs emitting (per model, per
   outcome class) — a process-efficiency axis.

## 4. Part D3 — the outcome join

The trajectory features (the transition matrices, the motif counts, the semantic profiles, the
think/act ratios) joined with `test_executed_success` + the review texture: which signatures
precede success, which precede failure — the per-model process signatures vs their outcomes.
The flail motif is the known case: does the failing sessions' graph show the repeating-cycle
signature the flail lab measured? The Δ-entropy instrument (the graph-family's Part B) is the
PRODUCT axis; the trajectory graph is the PROCESS axis — the two join in the campaign
measurements.

## 5. The tooling call (neo4j vs alternatives — the decision)

- **neo4j for the structure:** the transitions, the motifs, the fingerprints are graph queries
  — the sequencing IS a graph problem. The trajectory graphs ride the same neo4j instance the
  retrieval bridge + the code graph use (the fleet ladder's slice 3, then Parts A/C/D1).
- **chroma for the semantics:** the thinking content is a similarity/clustering problem — the
  existing `session_embeddings` collection (2,215 records) is the natural store; the semantic
  roles come from the embedding clusters + a labeled classifier.
- **Rejected for this phase:** a pure tabular analysis (the step rows exist but the SEQUENCING
  is lost), a pure text-LLM analysis (expensive + non-deterministic for the corpus scale — the
  embeddings + clusters are deterministic and cheap).

## 6. The sequencing

1. The ladder's **slice 3** (the retrieval bridge) lands the neo4j instance the graph analysis
   rides.
2. **D1** — the trajectory-graph ingestion + the per-model grammars + the motifs (the flail
   signature as the verification fixture).
3. **D2** — the semantic-range pipeline (the thinking blocks → embeddings → roles → profiles).
4. **D3** — the outcome join + the campaign integration (the process axis alongside the ΔH
   product axis).
5. Each part bounded (the flash-sized-phase rule), each with the tests + the rollback (the
   graph + embeddings are additive; a backend failure degrades the analysis, never the
   campaigns).

## 7. Guard

The step-classifier's contract (the modality table) is the load-bearing pin — a comparison
across models whose artifacts are classified inconsistently (claude's thinking vs gpt's patch
vs opencode's events) is a FAILED finding. The semantic roles are disclosed (the embedding +
clustering method, the labeled examples per role); a hidden role definition is a FAILED
finding. The motif definitions are pinned (the cycle detection's exact subpath rules) — the
flail signature's known case must reproduce. The outcome join cites the test-runner's
verdicts, never the agent's narrative. Every number cites its source.

**LOG:** the operator's direction mapped to the two-store architecture (neo4j for the structure,
chroma for the semantics — both already in the machine); the model-artifact taxonomy pinned as
the classifier's contract (claude thinking / gpt patch / opencode reasoning events — the
modality-aware step types); D1 the trajectory graph (the per-model grammars, the motifs with
the flail signature as the fixture, the per-step cost structure); D2 the semantic range
(embeddings → roles → the per-model profiles: range, dwell, think-to-output); D3 the outcome
join (the process axis vs the ΔH product axis); the tooling decision; the sequencing;
the guard. **PROPOSED — joins the graph-analysis family (Part D) behind the ladder's slice 3.**
