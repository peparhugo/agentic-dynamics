---
name: run-workflow
description: Validate/compile an ExperimentSpec YAML (compile_experiment.py's requires/produces gate) and execute an agent_task workflow through a git worktree, phase by phase (run_workflow.py). Use when asked to run a spec-driven workflow, check whether a spec's control rules have their information requirements met, or execute a multi-phase agent task with per-phase commits.
disable-model-invocation: false
user-invocable: false
argument-hint: ""
---

# Run Workflow Skill — Spec Validation + Execution

This skill wraps the *execute* half of the spec→DAG pipeline described in
`docs/designs/current/2026-08-14_experiment-spec-and-compiler-design.md`: validate/compile an
`ExperimentSpec` YAML, then run it as a phased `agent_task` workflow inside a git worktree.

## When to use this

- The user asks to "validate a spec," "check if this spec's control rules are satisfied," or
  "compile the DAG" for a file under `experiments/definitions/*.yaml` + `workflows/**/*.yaml`.
- The user asks to run a spec-driven workflow / `agent_task` end-to-end (as opposed to the
  linear `run.py`/`run_story.py` execution paths documented in the `instrument` skill).

This is distinct from `instrument`'s `run.py`/`run_story.py` — those run a single experiment or
story directly; this skill runs the spec/compiler layer that will eventually generalize them
(see `agent_config/mental-model.md`'s reuse map).

## `compile_experiment.py` — no CLI, inline snippet only

`src/agentic_dynamics/experiment/compile_experiment.py` has no `argparse`/`__main__` — it's a
pure library, and no `scripts/*.py` wraps it. There is no standalone script wrapper to run.
API:

```
agentic_dynamics.experiment.experiment_spec.load_spec(path) -> ExperimentSpec
agentic_dynamics.experiment.experiment_spec.validate_rules(spec) -> list[str]
agentic_dynamics.experiment.compile_experiment.compile_spec(spec) -> DAG   # .names(), .edges, .feedback, .topological_order()
agentic_dynamics.experiment.compile_experiment.SpecError(ValueError)
```

**Validate mode** — runs only the requires/produces gate (the load-bearing rule: a control rule
whose `requires` aren't yet produced by any measurement rule fails validation):

```bash
python3 -c "
import sys, json
from pathlib import Path
sys.path.insert(0, 'src')
from agentic_dynamics.experiment.experiment_spec import load_spec, validate_rules
from agentic_dynamics.experiment.compile_experiment import compile_spec, SpecError

spec_path, mode = sys.argv[1], sys.argv[2]
spec = load_spec(Path(spec_path))

if mode == 'validate':
    errors = validate_rules(spec)
    print(json.dumps({'valid': not errors, 'errors': errors}))
    sys.exit(1 if errors else 0)
else:
    try:
        dag = compile_spec(spec)
    except SpecError as e:
        print(json.dumps({'valid': False, 'errors': e.errors}))
        sys.exit(1)
    print(json.dumps({'valid': True, 'phases': dag.names(), 'edges': dag.edges,
                       'feedback': dag.feedback, 'topological_order': dag.topological_order()}))
" workflows/research/routing_kb_more_itertools.yaml validate
```

**Compile mode** — swap the final positional arg to `compile` to also build the DAG and print
`phases`/`edges`/`feedback`/`topological_order`:

```bash
python3 -c "..." workflows/research/routing_kb_more_itertools.yaml compile
```

Both modes take exactly two positional args: the spec YAML path, then `validate` or `compile`.
Exit code `1` on either a validation error list (`errors` non-empty) or a `SpecError` raised
during `compile_spec`. Exit code `0` means the gate passed.

## `run_workflow.py` — the execute phase

Confirmed flag set (`scripts/run_workflow.py`):

```
--spec PATH                   required — an ExperimentSpec YAML
--goal TEXT                   required — feature/task prompt, substituted for {goal}
--model PROVIDER/MODEL        required — e.g. deepseek/deepseek-v4-pro
--workdir PATH                required — git worktree to run in
--backend opencode|claude_cli default: auto-detected from --model
--thinking-effort STR         default: "high"
--thinking-budget-tokens INT  default: 0
--output-token-limit INT      default: 0
--timeout INT                 default: 1800 (per-phase timeout, seconds)
--no-commit                   flag — do not commit after each phase
--resume                      flag — skip phases that already have a "[workflow] <phase>" commit
--signals PATH                optional — JSON signals override {model: {field: value}}
```

`--spec`/`--goal`/`--model`/`--workdir` are **required, no positional fallback** — unlike
`run.py`'s config, which is a bare positional (see the `instrument` skill).

```bash
python3 scripts/run_workflow.py \
  --spec workflows/research/routing_kb_more_itertools.yaml \
  --goal "Add rate limiting to the API" \
  --model deepseek/deepseek-v4-pro \
  --workdir /tmp/wf_abc123 \
  --thinking-effort high --timeout 1800
```

`run_workflow.py` imports `run_workflow()` from `agentic_dynamics.runtime.workflow_runner`, and
`load_spec()` from `agentic_dynamics.experiment.experiment_spec` — it re-validates the spec
internally on every invocation. A prior `compile_experiment` `validate` pass is a fast-fail
convenience — it surfaces a requires/produces error before you spend time setting up a worktree —
not a hard prerequisite the script itself checks for.

### Ordering

1. (Optional, fast-fail) Run the `compile_experiment` `validate` snippet against the spec. Fix
   any `requires` gap (instrument the missing information) before proceeding.
2. Create/choose a git worktree at `--workdir`.
3. Run `run_workflow.py` with `--spec`/`--goal`/`--model`/`--workdir`. Each phase commits to the
   worktree (`"[workflow] <phase>"`) unless `--no-commit` is set.
4. Use `--resume` to re-run after an interrupted workflow — it skips phases whose commit already
   exists rather than re-running them.

## Common gotchas

- `compile_experiment.py`'s inline snippet is not a script — do not invent a script wrapper for
  it; none exists.
- Don't add `--config` to `run_workflow.py` — its spec argument is `--spec`, not shared naming
  with `run.py`'s positional config.
- A spec whose control-rule `requires` aren't yet produced by a measurement rule in the ledger
  fails `validate_rules` — instrument that information first (see `agent_config/mental-model.md`'s
  load-bearing rule), don't work around the gate.
