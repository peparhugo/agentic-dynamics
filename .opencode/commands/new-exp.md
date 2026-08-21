---
description: Create a new experiment config and run it through the perturbation pipeline
agent: build
subtask: true
---

Create a new experiment config and run it end-to-end.

> Spec direction: `compile_experiment.py` is written and can compile an `ExperimentSpec` YAML into cells, but this command still writes a config directly — no spec-authoring UI exists yet for this command specifically. Control rules (e.g. `model_cascade`/`dynamics`) consume measured `confidence` — measure before policy.

1. Load the "instrument" skill.
2. Determine the language and task. `$ARGUMENTS` may name a language (e.g. `/new-exp go`) and/or a task slug (e.g. `/new-exp go_rate_limiter`). If only a language is given, propose a fresh problem in that language not already covered by an existing config.
3. Create `experiments/definitions/configs/<name>.yaml` modeled on the closest same-language config:
   - Go → `go_crawler.yaml`, `go_jobqueue.yaml`, `go_grpc_chat.yaml`
   - Rust → `rust_git_store.yaml`, `rust_redis.yaml`, `rust_proxy.yaml`
   - TypeScript → `typescript_eventbus.yaml`, `typescript_multitenant_api.yaml`
   - Python → `task_manager.yaml`, `url_shortener.yaml`
4. The config needs: `name` (matches filename), `task` (detailed spec), `constraints` (8-10), `operators` (5-6 of the 10), `strengths`, `model` + `model_id`. For Go/Rust set `standardized.enforce_pytest: false` (correctness runs `go test`/`cargo test`, not pytest).
5. Run: `python scripts/run.py experiments/definitions/configs/<name>.yaml --model deepseek`
6. Verify output exists (GameReport + worktree at /tmp/exp_*), then report: cost, tokens, tests passed, strategy archetype, and the game report path.
7. Offer to run the downstream pipeline: `python scripts/analyze_worktrees.py` then `python scripts/pipeline.py --plan deploy`.
