# Review — Runtime-RAG Knowledge Base & Prompt-Constructor Proposals (3-model grid)

**Date:** 2026-08-15
**Spec:** `experiments/specs/rag_knowledge_base.yaml` (v0.1, exploratory)
**Grid:** 3 cells — one workflow, factor `model` ∈ {`deepseek/deepseek-v4-pro`, `anthropic/claude-fable-5`, `openai/gpt-5.6-sol`}
**Question asked of each cell:** independently research the state of the art in runtime RAG for AI agents, then design and propose an "agent intelligent knowledge base" — storage topology, runtime augmentation pipeline, and a separate prompt-constructor agent — plus an integration plan for this repo.
**Evidence tags:** `[M]` measured · `[C]` computed · `[H]` heuristic · `[X]` external · `[P]` policy/prior.

---

## 1. Verdict

All three proposals converge on the **same architecture** — a hybrid knowledge base (graph + dense vector + lexical/full-text + stream) feeding a **separate, cheap prompt-constructor agent** that augments the work item at the `workflow_runner.py` prompt seam — and all three independently reach the same three guardrail conclusions: reject Elasticsearch, keep everything behind the load-bearing rule ("measure before policy"), and never consume the still-unmeasured `confidence` signal.

Where they differ is **what each one got right**, and the differences are complementary rather than competing:

| Model | What it nailed | One-line characterization |
|---|---|---|
| DeepSeek-v4-pro | the *unit of knowledge* to inject | conceptual clarity, corpus-only |
| Claude Fable 5 | the *storage mechanics* against real infra | build-ready, bug-finding |
| GPT-5.6 Sol | the *system architecture* (identity, authority, validation) | most rigorous, live-researched |

The synthesized v1 build (this review's §7, and the companion spec `rag_knowledge_base_build.yaml`) is **Sol's skeleton + Fable-5's storage + DeepSeek's evidence-card insight**.

---

## 2. What actually ran

### 2.1 Cell outcomes

| Model | Result | Cost [M] | Wall time [M] | Tokens in/out/reasoning [M] | Cache reads [M] | Output docs [M] |
|---|---|---|---|---|---|---|
| `deepseek/deepseek-v4-pro` | ok | **$0.14** | 426 s | 222,976 / 18,952 / 24,174 | 1.65M | 83 KB (survey 28K · design 37K · proposal 18K) |
| `anthropic/claude-fable-5` | ok | **$6.19** | 1,171 s | 30\* / 78,990 / 0 | 1.27M | 114 KB (survey 49K · design 40K · proposal 25K) |
| `openai/gpt-5.6-sol` | ok (after resume) | **$10.59** | 1,801 s + 1,882 s | 428K / 50K / 15K | 4.07M | 139 KB (survey 47K · design 47K · proposal 45K) |

\* `[M]` The Claude adapter reports `tokens_in = 30` — a **measurement gap in `claude_adapter.py`**, not a real number. Claude's input tokens are not correctly surfaced; its $6.19 is driven by 78,990 output + 1.27M cache-read tokens. Flag this as an instrumentation defect independent of the RAG design (it also skews any future cost-per-token analysis for Claude cells).

### 2.2 Worktrees and commits

| Model | Worktree | survey | design | proposal |
|---|---|---|---|---|
| DeepSeek | `/tmp/pipeline/feature_rag-kb-deepseek` | `59689354e` | `f1d78f711` | `68a7008e5` |
| Fable 5 | `/tmp/pipeline/feature_rag-kb-fable5` | `a1febe0e9` | `cb8b246cc` | `8fb6ff982` |
| Sol | `/tmp/pipeline/feature_rag-kb-sol` | `1cf82085d` | `d6a7e3c7b` | `f1a5af24f` |

### 2.3 Operational incidents

- **Sol timed out** on the survey phase at the 1,800 s default (`ok: False`, `Timeout after 1800s`), after *writing* a complete 47 KB survey but before `run_workflow` could commit it. Recovered by committing the finished survey (`1cf82085d`) and re-running with `--resume --timeout 3600`. `[M]` Sol's per-phase wall time is ~15–30 min — the 1,800 s default is too short for it; use `--timeout 3600` for any Sol `agent_task` cell.
- **Research depth is not uniform.** `[M]` DeepSeek's survey states "nothing was live-fetched" (pre-2025 corpus knowledge + honest `[H]` extrapolation). Fable 5 did a mix. Sol's survey is the only one that did **live web research**: 32 external sources (`E1`–`E32`), cutoff-pinned (GitHub commit hashes, versioned doc snapshots), dated "sources checked 2026-08-15." The "latest/cutting edge" requirement was met *only* by Sol — this is the single biggest substantive gap between the intended and actual outcome for the other two.

---

## 3. Method note — what each model read, and how it was fact-checked

Two findings from cross-checking the proposals against source matter for interpreting this review:

### 3.1 The `.claude/` vs `.opencode/` convention split `[M]`

This repo carries **two parallel convention/agent surfaces**, both tracked in git:

| | OpenCode surface (deepseek, sol) | Claude Code surface (fable-5) |
|---|---|---|
| Project memory | `AGENTS.md` | `CLAUDE.md` (which `@import`s `AGENTS.md`) |
| Rules | `.opencode/instructions/mental-model.md`, `conventions.md` | `.claude/rules/mental-model.md`, `conventions.md` |
| Subagents/skills | `.opencode/skills/*` | `.claude/agents/*`, `.claude/skills/*` |
| Permissions | `opencode.json` | `.claude/settings.json` |

`claude-fable-5` runs through the `claude_cli` backend, so it read the `.claude/` stack; `deepseek` and `sol` ran through OpenCode and read `AGENTS.md` + `.opencode/`. This is a **confound on the `model` factor** (entangled with backend + convention-stack), and the two "parallel" stacks have already **drifted**: `diff` shows `.claude/rules/mental-model.md` differs from `.opencode/instructions/mental-model.md`. Fable-5's citations to `.claude/rules/conventions.md` / `.claude/rules/mental-model.md` are therefore *correct for its backend*, not errors.

### 3.2 Citation accuracy `[M]`

All three cells were checked out from commit `e29366cd9`. Every `file:line` citation in all three proposals was spot-checked (~40 in DeepSeek's; a representative sample in Fable-5's and Sol's) **against `e29366cd9`** — the commit they actually read — and all verified accurate. Two files (`workflow_runner.py`, `step_routing.py`) have since shifted ~9–49 lines in `main` (now `b56cb441c`) due to the concurrent `routing-follow-up` and `claude-tools-to-skills` merges; the proposals are not wrong, they are pinned to the version they saw. Reviewers must diff citations against `e29366cd9`, not `HEAD`.

---

## 4. DeepSeek-v4-pro — reviewed

**Cost: $0.14 · corpus-only · 83 KB.** The cheapest and fastest, and the one that did *not* meet the "latest/cutting edge" brief (explicitly self-flagged).

### Distinctive ideas

1. **The "evidence card"** — the injected unit should be a *derived one-line finding* ("`deepseek-v4-pro` under `remove_critical_constraint` → flail 0.62, cost $0.018"), precomputed **offline** from the run's already-measured vector (`load_runs`, `graph.py`), not raw retrieved steps and not synthesized at query time. The strongest single concept in the grid: *retrieve conclusions, not verbatim reasoning.*
2. **Provenance tiebreak in fusion** — RRF ties broken by the repo's own evidence order `[M] > [C] > [H] > [X]`.
3. **Static composer first, LLM constructor as a gated upgrade** — ship the deterministic header, let the meta-agent earn its place via a measured `augmentation_delta`.

### Weaknesses

- `[H]` The **graph leg weight (`w_graph = 0.5`) is an unmeasured prior**, admitted but not resolved.
- `[C]` It prices the constructor with **fork/cache reuse across phases** (stable prefix → ~120× cheaper), which §6 argues is the wrong default (see Sol, §6).
- `[H]` Internal inconsistency: its headers say "phase 3 of `rag_augmentation.yaml`" — that spec did not exist; the run executed under `rag_knowledge_base.yaml`.

---

## 5. Claude Fable 5 — reviewed

**Cost: $6.19 · 114 KB · bug-finding.** The most *build-ready* proposal; found two real defects by reading the code.

### Distinctive ideas

1. **Sparse leg = Neo4j's native full-text index**, not a new BM25 component. One Cypher query returns the text hit *and* its graph neighborhood — no cross-store join. `[X]` Its survey grounds this in the post-GraphRAG convergence (LightRAG, Zep/Graphiti) toward fusing graph+text in one engine.
2. **Two real, checkable bugs** `[M]` (verified against `graph.py:480-522` and `embeddings.py:83-87`):
   - `build_step_graph()` hardcodes `Step.doc_id = ''` and never populates `Step.text` — the dense↔graph join is **silently broken today**.
   - `ChromaStore.__init__` hardcodes `host="localhost", port=8000`, colliding with `admin/server.py`'s default port.
3. **`CodeModule` node type + `TOUCHED` edges** — persists the `codebase_graph.py` import graph (currently thrown away) so retrieval can answer "what else touched this module."
4. **Graph as a *boost*, not a peer** — `decay^hops · fused(anchor)` (decay 0.5): a structural neighbor is *categorically* weaker than a direct hit, so it decays rather than competing as a third ranked list. More principled than DeepSeek's flat `w_graph`.
5. **Structured, auditable constructor output** (`items_used`/`items_dropped`/`rationale`) — decisions become measurable signals, not buried prose.
6. **Redis Streams as a durable ingestion trigger** + `scripts/ingest_worker.py`, replacing manual `embed_sessions.py`.

### Weaknesses

- `[H]` Same fork-reuse assumption as DeepSeek (see §6).
- `[M]` Cites `scripts/embed_sessions.py` and `CHROMA_HOST` env pattern that were checked and exist — but its `tokens_in` gap (§2.1) means its own cost arguments are less precise than its rivals'.

---

## 6. GPT-5.6 Sol — reviewed

**Cost: $10.59 · 139 KB · live-researched.** The most rigorous and the only one that did real web research. It is the architectural skeleton the synthesis adopts.

### Distinctive ideas

1. **Knowledge base = disposable search views over authority.** Git + immutable artifacts are authoritative; Redis Stream carries only *pointers + hashes*; Chroma and Neo4j are rebuildable materialized views. This removes the multi-store-transaction problem the others hand-waved. `[P]`
2. **Canonical dual-ID identity** — `entity_id` (logical entity) and `knowledge_id` (immutable version), both sha256, with the *same* `knowledge_id` used in Redis event, Chroma doc, Neo4j node, citation, cache key, and ledger. Generalizes Fable-5's `doc_id` fix into an identity *contract*, and resolves the existing Chroma `_step_` vs Neo4j `_s` mismatch.
3. **Authority as an ordered ranking, not a blended feature** — `pinned policy > current source > measured > derived > advisory`. Policy is read directly from the checkout and *never* probabilistically retrieved; agent episodes/reviews are `advisory` and cannot override source or policy. This is the strongest idea in the entire grid: it classifies **trust**, not relevance.
4. **Deterministic query planner, no LLM query-rewriting in v1** — extract quoted strings, paths, stack frames, test names, CLI flags, dotted identifiers mechanically; don't entangle recall quality with constructor quality before either is measured. `[P]`
5. **Anti-forking — the grid's one real disagreement.** DeepSeek and Fable-5 both proposed forking the constructor session across phases for ~120× cache savings. Sol **rejects it**: forking across unrelated work items silently carries the previous item's evidence forward — cross-item contamination. Instead, stable instructions/schema form a provider-cacheable *prefix*; new evidence is new input. `[H]` but well-argued, and the question is a **measurable experiment**, not an opinion.
6. **Typed constructor output + deterministic validator + one-repair** — schema fields (`hard_constraints`, `evidence_claims`, `conflicts_and_unknowns`, `acceptance_checks`, `allowed_tools`), a validator that rejects invented constraints, fabricated citations, privilege expansion, and lost work items, one repair call, then a deterministic renderer. Strongest anti-hallucination guard of the three.
7. **Six-arm ablation (A–F)**, not A/B — raw / deterministic-RAG / constructor-RAG / dense-only / lexical-only / no-graph-expansion, isolating *which* component earns its cost.
8. **Named degradation modes + an Elasticsearch admission gate** — every failure falls to a *named* mode (`lexical_graph_only`, `dense_local_exact`, `no_rag`) so degraded runs never silently pool with full-RAG; ES admitted only past a concrete held-out threshold (+5 pp exact-symbol Recall@20 or +2 pp task success, ≤20% p95 latency regression).

### Weaknesses

- `[C]` Highest cost by 17× over DeepSeek — justified by the research depth, but the default `--timeout` and a **freshness** target ("60 s p95") are aspirations, not measurements (`[H]`).
- `[H]` It is the *largest* design (10 modules + 7 test files); the build order (§3.5 of its proposal) is the mitigation, but the maintenance surface is real.

---

## 7. Synthesis — what to build

**The convergent core** (all three independently): hybrid graph + dense + lexical + stream; separate cheap `deepseek-flash` constructor; injection at the `workflow_runner` seam between `route_step()` and `run_agent()`; Redis Streams as the freshness trigger; reject Elasticsearch; measure-before-policy; never consume `confidence`.

**The best-of, component by component:**

| Concern | Winner | Rationale |
|---|---|---|
| Knowledge *unit* | **DeepSeek** | inject precomputed "evidence cards" (derived findings), not raw steps |
| Storage | **Fable-5** | Neo4j full-text (no cross-store join), graph-as-boost, `CodeModule` bridge, `doc_id`/`text` fix |
| Identity & authority | **Sol** | canonical dual-ID + 5-tier authority ordering + policy read directly, never retrieved |
| Retrieval | **Sol + Fable-5** | deterministic planner, RRF × authority/freshness/exact-id factors, bounded allowlisted graph expansion with `decay^hops` |
| Constructor | **Sol** | typed schema + deterministic validator + one-repair + deterministic renderer, **no cross-item fork** |
| Ingestion | **Sol + Fable-5** | Redis Streams `XADD`/`XREADGROUP`, pointer-only events, idempotent consumers, tombstoning |
| Evaluation | **Sol** | six-arm ablation + named degradation modes + concrete ES admission gate |

**The one unresolved design question** the grid surfaced (and which should be the *next* grid's arm): **does fork-reuse of the constructor's session earn its cache savings, or does cross-item contamination make it a false economy?** DeepSeek/Fable-5 say fork; Sol says don't. The v1 build adopts Sol's **stateless** stance (safer default), and the question is left as a measured `policy` factor later.

The companion spec `experiments/specs/rag_knowledge_base_build.yaml` encodes this synthesis as an `agent_task` workflow with seven committed phases in load-bearing order.

---

## 8. Comparison scorecard

Scored `[H]` on the axes the proposals themselves proposed (Sol §6.3 is the most complete; Fable-5 §6.2 overlaps). 1 = weak, 3 = strong.

| Axis | DeepSeek | Fable-5 | Sol |
|---|:--:|:--:|:--:|
| Repository grounding (real clients, seams, pricing, Redis topology) | 3 | 3 | 3 |
| Storage economy (unique job per store, service count justified) | 2 | 3 | 3 |
| Retrieval specificity (concrete query/count/fusion/bound/budget/citation) | 2 | 2 | 3 |
| Hook correctness (post-route, pre-backend, both backends) | 2 | 3 | 3 |
| Constructor isolation (separate, typed, validated, fallback) | 2 | 2 | 3 |
| Ingestion integrity (idempotent, replayable, scoped, deletable, sanitized) | 2 | 2 | 3 |
| Load-bearing compliance (measured/rule/unmeasured, rejects `confidence`) | 3 | 3 | 3 |
| Economics (constructor + executor + cache + storage + rework counted) | 3 | 2 | 3 |
| Evaluation validity (downstream improvement, not retrieval aesthetics) | 2 | 2 | 3 |
| Failure behavior (monotonic degradation, named modes) | 2 | 3 | 3 |
| **Research depth (live, cutting-edge, dated sources)** | **1** | **2** | **3** |

**Bottom line:** on pure *design*, Sol is the strongest and it's not close on the last three rows; on *build-readiness against the code actually here*, Fable-5 found the concrete bugs that any implementation must fix first; on *conceptual clarity*, DeepSeek's evidence-card is the idea that survives the synthesis. The three are a genuine "parts list," not three answers to one question.

---

## 9. Open questions and next grid

1. **Constructor fork-reuse vs contamination** — the one real disagreement. Next grid arm: `policy: [forked_constructor, stateless_constructor]`, measured on downstream `test_executed_success` + `cost_per_accepted_outcome`.
2. **`test_executed_success` into `LEDGER_FIELDS`** — all three independently flagged it as the missing correctness signal. This is a prerequisite instrumentation task before any RAG arm's outcome comparison is trustworthy.
3. **Neo4j full-text vs Elasticsearch at this corpus scale** — Sol's admission gate (Recall@20 / task success / latency) is the right falsifiable form; run it *before* ever provisioning ES.
4. **`tokens_in` gap in `claude_adapter.py`** — pre-existing, but it corrupts any cross-model cost attribution; fix it regardless of RAG.
5. **The `.claude/` ↔ `.opencode/` drift** — the two convention stacks have diverged; re-sync or accept the confound and record it in the spec.

---

## Appendix A — ledger summary

| Cell | status | total_cost_usd | ok |
|---|---|---|---|
| `20260814T223645Z.json` (deepseek) | ok | 0.140496 | true |
| `20260814T224910Z.json` (fable-5) | ok | 6.190276 | true |
| `20260814T225940Z.json` (sol, timed out) | failed | 5.169756 | false |
| `20260814T233748Z.json` (sol, resumed) | ok | 5.421503 | true |

Ledger dir: `experiments/results/workflows/rag_knowledge_base/`. Worktrees live in `/tmp/pipeline/feature_rag-kb-*` on branches `feature/rag-kb-*`; archive them with `scripts/pipeline.py` / `archive_worktrees` before cleanup.
