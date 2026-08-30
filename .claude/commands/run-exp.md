---
description: Run an experiment config through the perturbation pipeline
---

Run an experiment config through the full pipeline: perturb → invoke → evaluate → report.

First, load the "instrument" skill if not already loaded. Then:

1. If a config name is specified ($ARGUMENTS), use `experiments/definitions/configs/$ARGUMENTS.yaml`.
   Configs live at `experiments/definitions/configs/*.yaml` — list the directory to see what is
   available (`baseline`, `task_manager`, `url_shortener`, and the `go_`/`rust_`/`typescript_`
   language families are representative; `plans.yaml` is the pipeline plan, not an experiment config).

2. If no config specified, list the available configs and ask which to run.

3. Run: `python scripts/run.py experiments/definitions/configs/<name>.yaml --model deepseek`

4. Report the results: cost, tokens, tests passed, strategy archetype, game report path.

Use `--model $1` if a second argument is provided (e.g. `/run-exp task_manager claude`).

Spec direction: `agentic_dynamics.experiment.compile_experiment` is written and can compile an
`ExperimentSpec` from `experiments/definitions/*.yaml` + `workflows/**/*.yaml` into cells; policy
is a factor level and its control rules consume measured information (`confidence` is now
measured). See `docs/architecture/current/2026-08-14_experiment-spec-and-compiler-design.md`.
