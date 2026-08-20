---
status: accepted
---
# Semantic Monolith Review — external critique (2026-08-20)

**Provenance [X]:** operator-provided external critique, 2026-08-20. Received verbatim as
workflow input for the consolidation release. Not authored in-repo; retained here so the
staging workflow and its descendants have a citable artifact.

## The honest diagnosis

The repository is not primarily spaghetti code. It is a **semantic monolith**: several
individually coherent systems, several generations of architecture, and several kinds of
research artifact have accumulated under one repository and one vague package boundary.

| Dimension | Assessment |
|---|---|
| Core ideas | Strong and increasingly coherent |
| Individual modules | Often disciplined and well documented |
| Package boundaries | Weak |
| Repository navigation | Poor |
| Sources of truth | Too numerous |
| Historical cleanup | Insufficient |
| Conceptual scope | Much larger than the public framing |
| Risk of further expansion | High |

The problem is not that nothing makes sense. The problem is that too many things make
sense locally without a strong global partition.

## Findings

1. **`src/instrument/` means almost everything.** Perturbation science, experiment
   compilation, execution backends, workflow orchestration, routing, static analysis,
   knowledge graphs, embeddings, RAG, prompt construction, telemetry, testing,
   supervision, and emerging control-plane concepts. It now means "anything related to
   agents, experiments, execution, analysis, knowledge, or control" — effectively no
   boundary.

2. **`experiments/specs/` contains things that are not scientific experiments.**
   Genuine experimental definitions sit beside implementation projects and repo-development
   workflows (website rewrites, KB construction, queue steering, control-room development,
   documentation refreshes, data remediation, rebranding, workflow-routing implementation).
   The directory is a combined experiment registry, project backlog, agent task library,
   and architectural history — making it impossible to distinguish an experiment studying a
   hypothesis from an automated work order that changes the repository.

3. **Several generations coexist.** Deprecated `experiment.py`, `adapter.py`, `lab_book.py`
   sit alongside the newer spec/compiler architecture; multiple blueprints (BLUEPRINT,
   BLUEPRINT_v2, BLUEPRINT_v3), dated code reviews, handoffs, lab books, generated reviews,
   design proposals, verification documents, and parallel `.opencode` and `.claude`
   instruction surfaces. A healthy repository should answer "is this current, old, proposal,
   generated artifact, research result, or implementation task?" from the path.

4. **Architecture is being stored in prose because package boundaries cannot express it.**
   The architecture currently lives in README, BLUEPRINTs, CONTEXT files, code reviews,
   design docs, verification docs, experiment YAML, agent instructions, and source
   docstrings. There is no single architectural map that reliably supersedes the others.

5. **The public identity and the internal system have diverged.** The README principally
   describes a perturbation instrument, but the repository now also contains a reusable
   workflow execution engine, Redis queue transport, per-step routing, runtime knowledge
   construction, hybrid retrieval, prompt construction, supervisor and actuation records,
   and a designed canonical-fact and context-control plane. The internal repository is
   becoming a research operating system for agent experimentation and control.

## What the repository actually contains (six systems)

1. **Measurement apparatus** — perturbations, trajectories, correctness, Grit, recovery,
   cost, entropy, static analysis.
2. **Experiment platform** — ExperimentSpec, compiler, cells, grids, campaigns, comparisons,
   lab books.
3. **Agent execution runtime** — OpenCode/Claude adapters, workflow runner, worktrees,
   queues, workers, independent tests.
4. **Knowledge and augmentation system** — ingestion, immutable records, Chroma, Neo4j,
   retrieval, evidence cards, prompt constructor.
5. **Emerging control system** — routing, signal store, supervision, actuation records,
   canonical facts, context compilation, decisions.
6. **Research and publication environment** — corpora, generated results, website, control
   room, reviews, handoffs, blueprints, paper drafts.

Each is substantial enough to be a major package. They are currently presented as parts of
one "instrument."

## The good news

There is a strong architecture buried inside the sprawl:

```
ExperimentSpec → compiled grid/workflow → execution → ledger and evidence
→ measurement and canonical facts → decision-specific context
→ validated policy decision → execution
```

The Context Abstraction Plane clarified that spine rather than weakening it. So this is
recoverable without abandoning the work. But the next major task should be consolidation,
not another subsystem.

## The nine recommendations

1. **Freeze architectural expansion.** Do not implement I0–I7 from the Context Abstraction
   Plane immediately. First create the structural homes those components will occupy
   (CanonicalFact, reducers, context compiler, fact contracts, control rules, control
   validator, decision records). The design remains; implementation pauses until the
   package map exists.

2. **Turn the repository into an explicit modular monorepo.** One installable repo —
   `src/agentic_dynamics/` with `core/`, `experiment/`, `measurement/`, `runtime/`,
   `adapters/`, `knowledge/`, `control/`, `reporting/`. The critical improvement is that a
   path tells you what conceptual plane a module belongs to.

3. **Separate experiments from workflows.** `experiments/{definitions,campaigns,fixtures,
   results}` vs `workflows/{repository,operations,research,examples}`. `rag_bare_vs_augmented`
   etc. remain experiments; `website_rewrite`, `control_room_portal`, `rag_knowledge_base_build`
   etc. become workflows.

4. **Establish one current architectural authority.** One root `ARCHITECTURE.md` answering:
   planes, package boundaries, dependency direction, implemented vs proposed, the canonical
   execution loop, and which documents supersede which. Detailed designs live under
   `docs/designs/{current,implemented}` and `docs/archive/`. Move BLUEPRINTs, old handoffs,
   superseded reviews, and obsolete design proposals out of the root. A design carries
   structured status: `proposed | accepted | implementing | implemented | superseded |
   abandoned`, plus `supersedes:` and `implemented_by:`.

5. **Collapse the script surface.** Replace the enduring commands with one CLI
   (`agentic-dynamics experiment run`, `... workflow run`, `... queue worker/monitor`,
   `... analyze worktrees/trajectories`, `... data build`, `... knowledge ingest`,
   `... registry query`, `... site build`). Classify remaining scripts as maintained
   command / one-time migration / historical analysis / deprecated. One-time migrations
   should not live indefinitely beside the maintained runtime.

6. **Eliminate duplicate instruction surfaces.** `.opencode/` and `.claude/` should not both
   be manually authoritative. One canonical source (`agent_config/`) generates the other.

7. **Delete deprecated code rather than merely labelling it.** Remove `experiment.py`,
   `adapter.py`, `lab_book.py` (or move to `src/agentic_dynamics/legacy/` with no imports
   from current modules). "Deprecated but still mixed into the package" is not meaningful
   cleanup.

8. **Add dependency rules.** Enforce a directional graph: `core` ←
   `experiment/measurement/runtime/knowledge` ← `control` ← `applications`. core imports
   nothing from higher layers; measurement does not import control; knowledge does not
   actuate; retrieval never supplies canonical facts; control consumes facts, not arbitrary
   retrieved text; apps may compose layers but contain no domain rules; scripts become thin
   CLI adapters only. Checked automatically, not just documented.

9. **Treat the website and control room as applications.** Move them under
   `apps/{website,control-room}`. They consume the system; they are not part of the Python
   measurement library. Domain results → publication data → website, not interleaved with
   runtime architecture.

## The blunt summary

The repository is currently a measurement instrument, research laboratory, workflow engine,
distributed queue system, knowledge base, RAG stack, control-plane prototype, website,
dashboard, publication archive, and AI development environment — all pretending to be one
Python package called `instrument`. The underlying intellectual work is not the mess; the
repository topology no longer reflects the intellectual structure.

The recommended next move: pause Context Abstraction Plane implementation long enough to do
**one consolidation release** whose only outcome is: one architectural spine, clear bounded
packages, experiments separated from work orders, one CLI, one instruction source, one
current architecture document, old generations archived or deleted. After that,
implementing canonical facts and the context compiler will make the codebase clearer;
implementing them in the present structure will make it materially worse.
