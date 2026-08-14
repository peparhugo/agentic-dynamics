---
description: Run an experiment config through the perturbation pipeline
agent: build
subtask: true
---

Run an experiment config through the full pipeline: perturb → invoke → evaluate → report.

First, load the "instrument" skill if not already loaded. Then:

1. If a config name is specified ($ARGUMENTS), use `experiments/configs/$ARGUMENTS.yaml`.
   Available configs (34 total): baseline, url_shortener, task_manager, twitter_timeline, web_crawler, search_kv_store, mint_financial, social_graph, collaborative_editor, data_table, form_wizard, notification_system, autocomplete_search, typescript_ssg, typescript_ssg_claude, typescript_ssg_gpt5, typescript_ssg_gpt5mini, typescript_eventbus, typescript_multitenant_api, flask_maintenance, fastapi_maintenance, architecture_redesign, rust_git_store, rust_redis, rust_proxy, go_crawler, go_jobqueue, go_grpc_chat, comparative, constraint_detection, recovery_cost, iterative_build, factorial_compound, silent_mode_sweep.

2. If no config specified, list the available configs and ask which to run.

3. Run: `python scripts/run.py --config experiments/configs/<name>.yaml --model deepseek`

4. Report the results: cost, tokens, tests passed, strategy archetype, game report path.

Use `--model $2` if a second argument is provided (e.g. `/run-exp task_manager claude`).

Spec direction: `compile_experiment.py` is written and can compile an `ExperimentSpec` from
`experiments/specs/*.yaml` into cells; policy is a factor level and its control rules require
`confidence` (not yet instrumented). See `code_reviews/2026-08-14_experiment-spec-and-compiler-design.md`.
