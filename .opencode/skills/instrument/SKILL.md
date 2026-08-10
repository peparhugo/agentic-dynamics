# Reasoning Topology Instrument

Run perturbation experiments through opencode to measure how
language models explore unfamiliar reasoning trajectories under stress.

## Quick Start

```bash
# Run any experiment config through opencode
python scripts/run.py --config experiments/configs/twitter_timeline.yaml --model deepseek

# Quick 4-operator cross-model comparison
python scripts/run.py --config experiments/configs/comparative.yaml --model deepseek

# List all available configs (34 total)
ls experiments/configs/*.yaml
```

## Experiment Configs (34 total)

### Backend Systems (Python/Flask)
| Config | Problem |
|--------|---------|
| `baseline` | URL shortener (warmup/calibration) |
| `url_shortener` | URL shortener (comparison-ready) |
| `task_manager` | Task manager API |
| `twitter_timeline` | Twitter timeline + search |
| `web_crawler` | Distributed web crawler |
| `search_kv_store` | Search engine KV store |
| `mint_financial` | Mint.com financial aggregator |
| `social_graph` | Social network graph |

### Frontend UI (JavaScript/TypeScript)
| Config | Problem |
|--------|---------|
| `collaborative_editor` | Google Docs real-time collaboration |
| `data_table` | 100K-row virtual data grid |
| `form_wizard` | Multi-step enterprise form wizard |
| `notification_system` | Real-time notification delivery |
| `autocomplete_search` | Instant search widget |

### TypeScript Node.js
| Config | Problem |
|--------|---------|
| `typescript_ssg` | CLI static site generator |
| `typescript_ssg_claude` | Same SSG — Claude variant |
| `typescript_ssg_gpt5` | Same SSG — GPT-5 variant |
| `typescript_ssg_gpt5mini` | Same SSG — GPT-5-mini variant |
| `typescript_eventbus` | Event bus system |
| `typescript_multitenant_api` | Multi-tenant API |

### Maintenance
| Config | Problem |
|--------|---------|
| `flask_maintenance` | Flask app maintenance |
| `fastapi_maintenance` | FastAPI maintenance |
| `architecture_redesign` | Cross-language architecture refactor |

### Rust, Go
| Config | Problem |
|--------|---------|
| `rust_git_store` | Git storage backend |
| `rust_redis` | Redis implementation |
| `rust_proxy` | Network proxy |
| `go_crawler` | Web crawler |
| `go_jobqueue` | Job queue |
| `go_grpc_chat` | gRPC chat |

### Methodology
| Config | Purpose |
|--------|---------|
| `comparative` | 4-operator cross-model comparison |
| `constraint_detection` | Constraint detection test |
| `recovery_cost` | Recovery cost measurement |
| `iterative_build` | Multi-phase iterative development |
| `factorial_compound` | Full-factorial design |
| `silent_mode_sweep` | Silent mode sweep |

## How It Works

1. Opencode runs `python scripts/run.py <config>` via Bash
2. `run.py` applies perturbations, spawns opencode session, captures trajectory
3. Instrument measures: correctness, cost (tokens/$/joules), basin escape, recovery
4. Classifies strategy archetype: Conservative / Exploratory / Exploitative / Flailing
5. Generates GameReport markdown to `experiments/results/reports/`

## Models

| Model | Env Var | Notes |
|-------|---------|-------|
| `deepseek` | `DEEPSEEK_API_KEY` | Primary case study. 37B active MoE params. |
| `codex` | (requires `which codex`) | Codex CLI |
| `claude` | `ANTHROPIC_API_KEY` | ~500B estimated params |
| `gpt5` | `OPENAI_API_KEY` | GPT-5 |
| `gpt5mini` | `OPENAI_API_KEY` | GPT-5-mini |

## Perturbation Operators

**Manifold** (push off linguistic surface):
- `inject_alien_vocab`, `shift_framing`, `reverse_causality`, `force_abandonment`

**Semantic** (probe reasoning coherence):
- `inject_false_premise`, `invert_constraint`, `insert_contradiction`
- `remove_critical_constraint`, `inject_phantom_success`, `inject_competing_goal`

Set `strength` in config YAML (0.0–1.0).
