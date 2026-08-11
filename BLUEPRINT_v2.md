# Blueprint v2 — AI FinOps Dynamics: From Instrument to Discipline

**Status:** v0.5 deployed. v0.6 active. Target: v1.0 full balanced experiment.

---

## Part 1: Current State (v0.5)

### What we fixed across 3 rounds

**Round 1 — Audit Bugs (P0)**
- `compute_efficiency()` crash: now passes provider/model from model_id
- `pert_class` NameError in analyze_worktrees.py: assignment moved before first use
- Baseline correctness contamination: baseline_solution computed from actual baseline code
- Correctness pipeline: actual_correctness restored after heuristic re-eval
- README: --config → positional

**Round 2 — Site Consistency + Release Hygiene (P1)**
- og:url mismatches fixed (3 pages) + Firebase 301 redirects
- Recovery signals 6→7 (implemented trajectory distance signal)
- "verified" → "test-executed" across 12 locations
- Corpus vocabulary: sessions/worktrees/reports now consistent
- Pricing: snapshot label fixed, cache_read $0.14→$0.003625
- Package: reasoning-instrument → ai-finops-dynamics, heavy deps → optional
- CI: 5 test modules (was 3), build_data import check added
- GitHub: description, homepage, 9 topics
- New files: og-image.png, robots.txt, sitemap.xml, CITATION.cff
- Deployed at ai-finops-rulebook.web.app

**Round 3 — Golden Circle + Value Reframing**
- WHY: "Does your AI coding assistant make your system better, or just bigger?"
- HOW: "Controlled specification degradation — an experimental independent variable"
- WHAT: Pipeline, findings, Grit with value paragraph
- WHAT NEXT: "If you can measure it, you can route on it"
- New finding #4: "Success isn't value"
- New derived metric: AI Value Efficiency

### Current instrument architecture (21 modules)

```
Core:    perturb.py (regex operators) → opencode.py (session runner)
Measure: trajectory.py, solution.py, basin.py, efficiency.py,
         recovery.py (7 signals), recovery_cost.py, strategy.py
Valid:   constraint_detection.py, semantic_validation.py (AST/escape/markers)
Output:  game_report.py, lab_book.py
Service: sonar.py, graph.py (Neo4j), embeddings.py (ChromaDB)
```

### Current limitations

- Single-session experiments — cannot measure compounding decisions
- Python-only AST — no cross-language analysis
- Regex-based perturbations — shallow text manipulation
- Agent-authored tests only — evaluator_independent=False for all sessions
- No context complexity as independent variable
- No durable value measurement — captures cost + correctness, not value

---

## Part 2: The v1.0 Vision

### The Golden Circle

```
WHY:  Success isn't value — and nobody is measuring the difference.
HOW:  Treat specification quality as an experimental variable.
      Measure the full chain: decisions → behavior → cost → correctness → value.
WHAT: AI FinOps Dynamics — an open instrument.
```

### The Missing Measurement Chain

```
Current (v0.5):
  spec degradation → agent behavior → cost + correctness

Target (v1.0):
  spec × context × history → multi-session decisions
    → per-commit analysis (AST diff, Sonar, LSP, conventions, entropy)
    → aggregate analysis (Neo4j graph, review agents, cross-model comparison)
    → Durable Value Score
    → "better, or just bigger?"
```

### Durable Value Score (North Star Metric)

```
DVS = (correctness × architectural_fit × convention_adherence)
      ──────────────────────────────────────────────────────
      (session_cost + technical_debt_introduced + future_cost_impact)

DVS > 1 → net positive outcome
DVS < 1 → net negative outcome
```

---

## Part 3: v1.0 Experiment Architecture

### 3.1 Enhanced Perturbations: Flash V4 Mutation Compiler

**Module:** `src/instrument/mutation.py`

Use DeepSeek Flash V4 as a mutation compiler. One compilation per experiment config cell, producing a pinned, hashable `mutation.jsonl` artifact. All sessions in that cell consume the same mutation.

**Mutation types:**
- Specification mutators (10, prompt-level): inject_false_premise, remove_constraint, insert_contradiction, invert_constraint, inject_phantom_success, inject_competing_goal, inject_alien_vocab, shift_framing, reverse_causality, force_abandonment
- Codebase mutators (10, source-level): inject_bug, add_dead_code, introduce_coupling, duplicate_abstraction, break_convention, corrupt_docstring, remove_error_handling, weaken_type_hints, scatter_logic, circular_dependency

### 3.2 Multi-Session Story Format

**Module:** `src/instrument/story.py`

Each experiment cell is a *story* of N sequential sessions, each producing one git commit, each building on the prior session's HEAD.

```
STORY: "Build a task management API"
  Session 1 → Commit A: Core models + CRUD (greenfield)
  Session 2 → Commit B: Auth middleware (feature addition)
  Session 3 → Commit C: Async notification worker (integration)
  Session 4 → Commit D: Refactor to repository pattern (refactor)
  Session 5 → Commit E: Rate limiting + pagination (cross-cutting)
```

### 3.3 Multi-Language Design

**Module:** `src/instrument/language.py`

Abstract language-specific analysis behind `LanguageProfile` interface, backed by tree-sitter (AST) and LSP servers (diagnostics).

Supported: Python, TypeScript, Go, Rust
Adding a language: grammar file + LanguageProfile + convention YAML

### 3.4 Per-Commit Analysis

| Layer | Tool | Metrics |
|-------|------|---------|
| AST Diff | tree-sitter | File/function/class delta, import graph, coupling |
| SonarQube Delta | SonarQube | Bugs, smells, complexity, duplications, ratings |
| LSP Diagnostics | pyright/ts-server/gopls/rust-analyzer | Type errors, dead code, interface violations |
| Convention Adherence | Per-language YAML rules | Naming, patterns, error handling, docstrings |

### 3.5 Aggregate Analysis

| Layer | Tool | Metrics |
|-------|------|---------|
| Neo4j Graph | Neo4j + APOC + GDS | Modularity, centrality, coupling, dependency direction |
| Architectural Entropy | entropy.py | Function length, module size, import graph, naming, file responsibility entropy |
| Review Agents | Claude/GPT-5.6 | Commit review, story review, cross-model comparison |

### 3.6 Review Agent Pool

| Agent | Runs When | Output | Cost |
|-------|-----------|--------|------|
| Test Generator (Flash V4) | Pre-experiment | held_out_tests/ | ~$0.05 |
| Commit Reviewer (GPT-5.6) | Per commit | commit_review_{id}.json | ~$0.02 |
| Story Reviewer (Claude) | Per story | story_review_{id}.json | ~$0.10 |
| Cross-Model Comparator (Claude) | Per task type | comparison_{story}.md | ~$0.20 |
| Bug Validator (Flash V4) | Per seed | bug_validity.json | ~$0.01 |

### 3.7 Codebase Catalog

**Location:** `experiments/codebases/`

| Tier | LOC | Example |
|------|-----|---------|
| 1: Minimal | 100-500 | flask-todo, express-todo, gin-todo, actix-todo |
| 2: Small | 500-2000 | fastapi-auth-api, nest-auth, echo-auth, axum-auth |
| 3: Medium | 5000-15000 | fastapi-realworld, nest-realworld, gin-realworld |
| 4: Large | 20000-50000 | sentry-sdk (fork), typeorm (fork), gitea-lite (fork) |

Each tier × language × 2 qualities (good seams / bad seams).
Bad seams generated by Flash V4 degradation of good fork.

### 3.8 Scale Infrastructure

Docker Compose worker pool with Redis queue.
opencode manages API keys internally — workers only need opencode installed and the API config already present.

```
infrastructure/
├── docker-compose.experiment.yml
├── Dockerfile.worker
└── scripts/
    ├── enqueue.py
    ├── worker.py
    └── monitor.py
```

At 8 replicas × ~3 min/session: ~150 sessions/hour.
Full 540-session experiment: ~3.6 hours.

---

## Part 4: New Instrument Modules (v0.6 → v1.0)

```
NEW:
  mutation.py         # Flash V4 mutation compiler
  language.py          # Multi-language profile + tree-sitter wrapper
  story.py             # Multi-session orchestrator
  lsp_diagnostics.py   # LSP analysis per language
  entropy.py           # Architectural entropy
  codebase_graph.py    # Neo4j import + graph metrics
  review.py            # Agent review system
  value_score.py       # Durable Value Score

MODIFIED:
  perturb.py           # Add codebase mutators + Flash V4 path
  basin.py             # Python ast → tree-sitter
  semantic_validation.py  # Python ast → tree-sitter
  solution.py          # Add architectural_fit field
  strategy.py          # Add value-based archetype dimension
  game_report.py       # Add DVS, commit review, story coherence sections
```

---

## Part 5: Phased Roadmap

### v0.6 — Story Format + Enhanced Perturbations + Python/TS
**Sessions:** ~120  |  **Cost:** ~$5.50

- mutation.py: Flash V4 compiler for 20 operators
- story.py: Multi-session orchestrator
- language.py: LanguageProfile + tree-sitter for Python + TypeScript
- Story catalog: 2 stories × 2 languages
- Per-commit analysis: AST diff, Sonar, conventions
- Commit reviewer agent

### v0.7 — Neo4j + Entropy + Review Agents
**Sessions:** 0 (re-analysis)  |  **Cost:** ~$5

- codebase_graph.py: Neo4j graph metrics
- entropy.py: 5-dimension architectural entropy
- review.py: Full agent pool (test gen, story review, cross-model comparison)
- value_score.py: DVS calculation

### v0.8 — LSP + Independent Tests
**Sessions:** +120  |  **Cost:** ~$8

- lsp_diagnostics.py: Per-language LSP analysis
- Independent test generation (Flash V4, pre-experiment)
- Convention rule files for Python + TypeScript

### v0.9 — Scale Infrastructure + Full Matrix
**Sessions:** +300  |  **Cost:** ~$30

- Docker Compose worker pool
- Bad seams codebase variants
- Full experiment matrix

### v1.0 — DVS + Formal Release
**Sessions:** 540 total  |  **Cost:** ~$48.50 total

- DVS per model per story per codebase tier
- Decision Horizon measurement
- v1.0.0 git tag + Zenodo DOI

---

## Part 6: v1.0 Experiment Matrix

```
Independent Variables:
  Story type (5)           — task_manager, static_site, notification, auth_gw, pipeline
  Codebase tier (3)        — minimal, small, medium
  Codebase quality (2)     — good seams, bad seams
  Model (4)                — DeepSeek V4 Pro, Claude Fable 5, GPT-5.6, GPT-5-mini
  Mutation (3)             — clean, inject_bug_s0.7, false_premise_s0.7
  Repetitions (2)

Total cells: ~540  |  Data points: ~16,200  |  Total cost: ~$48.50
```

---

## Part 7: Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Flash V4 mutations are low-quality | Human review gate. Fall back to regex on failure. |
| Multi-session stories diverge | Bounded, specific task per session. No open-ended sessions. |
| tree-sitter grammars are buggy | Python/TS grammars are mature. Go/Rust deferred. |
| Review agents hallucinate scores | Structured JSON with explicit criteria. 10% human sampled. |
| Docker scaling ceiling | Start with 4 replicas. Scale incrementally. |
| Independent test generation too hard | Flash V4 writes tests from spec. Human reviews sample. |
| DVS is too reductive | DVS is ONE metric. Full layers always available. |

---

## Part 8: Infrastructure Note

opencode manages API keys internally through its own configuration.
Docker workers do NOT need API keys in environment variables — they only need
opencode CLI installed and the user's opencode config mounted read-only.

```yaml
# Worker volumes — no API keys required
volumes:
  - ~/.config/opencode:/home/worker/.config/opencode:ro
  - ~/.local/share/opencode:/home/worker/.local/share/opencode:ro
```

---

*Generated from two full audits, three rounds of fixes, Golden Circle reframing, and full v1.0 architecture design. August 2026.*
