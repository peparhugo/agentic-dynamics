# `experiments/` — Experiment Ecosystem

34 experiment YAML configs (+ `plans.yaml`), 224+ game reports, 19 active lab books, 6 peer reviews.

## `experiments/specs/` — ExperimentSpec YAML (proposed)

The spec/compiler introduces an `ExperimentSpec` layer above the configs. A spec declares
`workflow`, `factors` (model, condition, **policy** as a first-class factor), `design`
(factorial), `rules` (measurement vs control), `metrics`, `comparison`, `writeup`, `stop`, and
`adapt`. Flagship: `experiments/specs/routing_regret.yaml`:

```yaml
factors:
  - {name: model,     levels: [flash, luna, pro, haiku, terra, sonnet, sol]}
  - {name: condition, levels: [clean, bad_seed, early_degrade, late_degrade]}
  - {name: policy,    levels: [cheapest, premium_static, quality_cascade, dynamics]}
rules:
  - {name: model_cascade, plane: control, evidence_class: "[H]",
     requires: [confidence], produces: [escalation_decision]}   # ← refused until confidence is measured
```

The compiler refuses `dynamics`/`model_cascade` until `confidence` is instrumented (measure
before policy). Design: `code_reviews/2026-08-14_experiment-spec-and-compiler-design.md`.

## `experiments/configs/` — 34 Experiment Definitions

Each YAML defines: task description, constraints, perturbation operators, strength levels, model, turns.

### Backend (Python/Flask)
| Config | Problem |
|--------|---------|
| `baseline.yaml` | URL shortener (warmup/calibration) |
| `url_shortener.yaml` | URL shortener (comparison-ready) |
| `task_manager.yaml` | Task manager API |
| `twitter_timeline.yaml` | Twitter timeline + search |
| `web_crawler.yaml` | Distributed web crawler |
| `search_kv_store.yaml` | Search engine KV store |
| `mint_financial.yaml` | Mint.com financial aggregator |
| `social_graph.yaml` | Social network graph infrastructure |

### Frontend (JavaScript/TypeScript)
| Config | Problem |
|--------|---------|
| `collaborative_editor.yaml` | Google Docs real-time collaboration |
| `data_table.yaml` | 100K-row virtual data grid |
| `form_wizard.yaml` | Multi-step enterprise form wizard |
| `notification_system.yaml` | Real-time notification delivery |
| `autocomplete_search.yaml` | Instant search widget |

### TypeScript (Node.js)
| Config | Problem |
|--------|---------|
| `typescript_ssg.yaml` | CLI static site generator + live reload |
| `typescript_ssg_claude.yaml` | Same SSG — Claude variant |
| `typescript_ssg_gpt5.yaml` | Same SSG — GPT-5 variant |
| `typescript_ssg_gpt5mini.yaml` | Same SSG — GPT-5-mini variant |
| `typescript_eventbus.yaml` | Event bus system |
| `typescript_multitenant_api.yaml` | Multi-tenant API |

### Maintenance / Refactor
| Config | Problem |
|--------|---------|
| `flask_maintenance.yaml` | Flask app maintenance |
| `fastapi_maintenance.yaml` | FastAPI maintenance |
| `architecture_redesign.yaml` | Cross-language architecture refactor |

### New Languages (Rust, Go)
| Config | Problem |
|--------|---------|
| `rust_git_store.yaml` | Git storage backend |
| `rust_redis.yaml` | Redis implementation |
| `rust_proxy.yaml` | Network proxy |
| `go_crawler.yaml` | Web crawler |
| `go_jobqueue.yaml` | Job queue |
| `go_grpc_chat.yaml` | gRPC chat |

### Methodology Experiments
| Config | Purpose |
|--------|---------|
| `comparative.yaml` | 4-operator cross-model comparison |
| `constraint_detection.yaml` | Tests whether models notice removed constraints |
| `recovery_cost.yaml` | Recovery cost measurement |
| `iterative_build.yaml` | Multi-phase iterative development |
| `factorial_compound.yaml` | Full-factorial: 2 models × 3 perturbations × 2 phases × 3 reps |
| `silent_mode_sweep.yaml` | Silent mode sweep config |

## `experiments/results/` — Aggregate Data + Reports

| File | Description |
|------|-------------|
| `_results_summary.json` | Aggregate results (consumed by lab scripts + build_data.py) |
| `_trajectory_summary.json` | Per-transcript trajectory metrics |
| `_trajectory_aggregate.json` | Per-model comparable trajectory aggregates |
| `typescript_ssg_*.json` | Per-model SSG results (deepseek, claude, gpt5) |
| `lab_*.json` | Lab book analysis outputs (13 files) |
| `README.md` | Dataset access instructions (inventory CLI) |
| `reports/` | **224+ game reports** — per-experiment Markdown + artifact directories |

## `experiments/lab_books/` — 20 Experiment Plans

Methodology documents defining hypothesis, data sources, analysis steps, interpretation.
Implemented by the 19 active `scripts/lab_*.py` scripts.

| Document | Question |
|----------|----------|
| `lab_claude_audit.md` | Where did Claude's $47.54 go? |
| `lab_grit_matrix.md` | Correctness × escape × cost visualization |
| `lab_correctness_premium.md` | Does Claude's premium buy anything? |
| `lab_flail_triggers.md` | What makes a model flail? |
| `lab_tool_archetypes.md` | Does tool choice predict code quality? |
| `lab_task_routing.md` | Optimal model-per-task routing |
| `lab_basin_topology.md` | Attractor basin classification |
| `lab_survival_horizon.md` | Sessions-to-bankruptcy analysis |
| `lab_reasoning_divergence.md` | Reasoning trajectory divergence under perturbation |
| `lab_semantic_clusters.md` | Semantic clustering of reasoning patterns |
| `lab_cross_model_reasoning.md` | Cross-model reasoning comparison |
| `lab_basin_topology_neo4j.md` | Basin topology via Neo4j graph analysis |
| `lab_opencode_meta_analysis.md` | Meta-analysis of opencode experiment patterns |
| `lab_story_review.md` | Review patterns across multi-session stories |
| `lab_story_arc.md` | Quality/cost arc across story sessions |
| `lab_condition_effects.md` | Perturbation condition effects |
| `lab_cache_economics.md` | Cache-hit economics |
| `lab_quality_frontier.md` | Quality-per-cost frontier |
| `lab_verification_frontier.md` | Verification depth vs correctness |
| `lab_verification_value.md` | Independent verification value |

## `experiments/reviews/` — 6 Peer Review Documents

Independent model reviews of experiment methodology and findings:

| Document | Description |
|----------|-------------|
| `claude_soundness_audit.md` | Claude methodology audit v1 |
| `claude_soundness_audit_v2.md` | Claude methodology audit v2 |
| `final_claude_audit.md` | Final Claude audit conclusions |
| `gpt56_ux_review.md` | GPT-5.6 UX review v1 |
| `gpt56_ux_review_v2.md` | GPT-5.6 UX review v2 |
| `final_gpt56_review.md` | Final GPT-5.6 review |

## `inventory.json`

Persistent registry of all experiments, worktrees, and sessions. Generated by `scripts/inventory.py refresh`.
