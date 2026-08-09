# Reasoning Topology Instrument

Run perturbation experiments through opencode to measure how
language models explore unfamiliar reasoning trajectories.

## Usage

```
# Run any experiment config through opencode
python scripts/run.py experiments/configs/twitter_timeline.yaml --model deepseek

# Quick 4-operator comparison
python scripts/run.py experiments/configs/comparative.yaml --model deepseek

# All available configs
ls experiments/configs/*.yaml
```

## Experiment Configs (12 total)

### Backend Systems
| Config | Problem |
|---|---|
| `baseline` | URL shortener (warmup) |
| `twitter_timeline` | Twitter timeline + search |
| `web_crawler` | Web-scale distributed crawler |
| `search_kv_store` | Search engine KV store |
| `mint_financial` | Mint.com financial aggregator |
| `social_graph` | Social network graph infrastructure |

### UI/UX Frontend
| Config | Problem |
|---|---|
| `collaborative_editor` | Google Docs real-time collab |
| `data_table` | 100K-row virtual data grid |
| `form_wizard` | Multi-step enterprise form wizard |
| `notification_system` | Real-time notification delivery |
| `autocomplete_search` | Instant search widget |

### Multi-Model
| Config | Problem |
|---|---|
| `comparative` | 4-operator cross-model comparison |

## How it works

1. Opencode runs `python scripts/run.py <config>` via Bash
2. The script calls the model through httpx with API key from env
3. Results written to `experiments/results/<name>.md` + `.json`
4. Opencode reads the results and summarizes

## Models
- `deepseek` — DeepSeek v4 Pro (set `DEEPSEEK_API_KEY`)
- `codex` — Codex CLI (requires `which codex`)
- Add more in `scripts/run.py` INVOKE_BUILDERS
