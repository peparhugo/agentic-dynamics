---
name: run-workflow
description: Validate/compile an ExperimentSpec YAML (compile_experiment.py's requires/produces gate) and execute an agent_task workflow through a git worktree, phase by phase (run_workflow.py). Use when asked to run a spec-driven workflow, check whether a spec's control rules have their information requirements met, or execute a multi-phase agent task with per-phase commits.
disable-model-invocation: false
user-invocable: false
argument-hint: ""
---

# Run Workflow Skill — Spec Validation + Execution

This skill wraps the *execute* half of the spec→DAG pipeline described in
`docs/architecture/current/2026-08-14_experiment-spec-and-compiler-design.md`: validate/compile an
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

Confirmed flag set (`scripts/run_workflow.py` — the runner-hardened CLI, cap_runner_hardening
p1/p2):

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
--phase-watchdog-min MIN      phase stall watchdog — an agent phase with no new transcript
                              step for MIN minutes is SIGTERM'd and fails STALLED + evidence.
                              Default FINOPS_PHASE_WATCHDOG_MIN env, else 20; 0 disables.
--no-commit                   flag — do not commit after each phase
--resume                      flag — skip phases that already have a "[workflow] <phase>"
                              commit; when the worktree has NO such commits, fall back to the
                              phases the derived spec index (experiments/specs/index.json)
                              shows as ok for this goal
--signals PATH                optional — JSON signals override {model: {field: value}}
--cap-snapshot                CAP I4 — compile + best-effort record a route_next_job/v1
                              ControlContext snapshot beside every routing decision (read-only
                              measurement; OFF by default)
--cap-shadow                  CAP I6 — everything --cap-snapshot does PLUS runs the fact-based
                              route_next_job_v1 rule beside route_step, validates its proposal
                              (C1-C10), records it as a shadow decision artifact — never
                              applied, never arms actuation. Implies --cap-snapshot. OFF.
--no-fact-emit                disable the CAP fact auto-emit hook for THIS invocation only
                              (the hook is default-ON: every completed run derives + emits its
                              own attempt/job/policy/workflow facts, best-effort, scoped to the
                              run's own repository_id / cell_scope)
--change-analysis             evidence-integrity e6 seam — inject the concrete
                              EvidenceChangeAnalyzer so every committed phase also hands its
                              typed delta to the phase-boundary evidence loop
                              (code_change_facts/v2). Best-effort, OFF by default.
--change-analysis-graph URI   bolt://host:port for the versioned-graph evidence loop
                              (CLI > FINOPS_NEO4J_URI > FINOPS_NEO4J_URL). Only consulted
                              with --change-analysis; a missing/unreachable graph degrades to
                              delta-only facts with graph_status (unavailable) — never a crash.
--orchestrator                run each agent phase as a SIBLING cell container with its scope
                              config (scripts/fleet/spawn_wrapper.py) instead of in-process.
                              OPT-IN. The container mounts the docker socket (ro); a phase
                              whose scope fails validation refuses BEFORE the socket call.
--only-phase NAME             run a SINGLE phase only — the sibling-cell entrypoint that
                              --orchestrator mode spawns per phase; the spec's phase list is
                              filtered to this name before the run.
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

### Phase-level hardening (spec markers, not CLI flags)

- `deploy_allowed: true` per-phase marker — a phase that runs `firebase deploy` without it
  fails `DEPLOY_GATE`.
- Commit-prefix enforcement — a manual commit during a phase that does not match
  `[workflow] <phase> — <goal prefix>` fails `COMMIT_PREFIX`.
- The relabel tree-identity gate — post-phase, the committed tree is compared against the
  discarded-trees ledger (`experiments/results/workflows/<spec>/discarded_trees.jsonl`); a
  discarded tree re-presented fails `RELABEL` unless an operator-signed
  `approvals/<spec>/<phase>_tree_reuse.md` authorizes it.
- Checkpoint phases — a phase declaring `checkpoint: true` that succeeds stops the run with
  `awaiting_operator_approval`; `--resume` refuses to proceed past an unsatisfied checkpoint
  unless `approvals/<spec>/<phase>_approval.md` is committed with a real operator signature.

### Ordering

1. (Optional, fast-fail) Run the `compile_experiment` `validate` snippet against the spec. Fix
   any `requires` gap (instrument the missing information) before proceeding.
2. Create/choose a git worktree at `--workdir`.
3. **Default execution path: the orchestrator.** Spec workflows with declared phase scopes
   (or any workflow whose isolation matters) run containerized:
   `docker-compose -f infrastructure/docker-compose.ladder.yml run --rm workflow-runner
   python3 scripts/run_workflow.py --orchestrator --spec <spec> --goal "<goal>"
   --model <model> --workdir <path>` — each phase spawns as a validated sibling cell
   (scope ∈ the vocabulary, phase-authorized, mount contract, network, write flags — all
   checked BEFORE the docker socket call). The fleet runs one orchestrator at a time (the
   socket lives in exactly one tier), so don't start a second orchestrator while one is
   running.
4. In-process (`python3 scripts/run_workflow.py` without `--orchestrator`) is the
   **fallback**, not the default: use it only when the fleet is occupied (an orchestrator
   run is in flight) or the run is trivial (deterministic measurement execution, e.g. a
   lab run). In-process phases are documented scopes, not enforced ones.
5. Each phase commits to the worktree (`"[workflow] <phase>"`) unless `--no-commit` is set.
6. Use `--resume` to re-run after an interrupted workflow — it skips phases whose commit
   already exists (falling back to the spec index's ok phases when the worktree has none)
   rather than re-running them.
7. After the run, `python scripts/spec_status.py` refreshes the spec lifecycle index
   (best-effort, `run_workflow.py` also refreshes it at the end of every run).

## Common gotchas

- `compile_experiment.py`'s inline snippet is not a script — do not invent a script wrapper for
  it; none exists.
- Don't add `--config` to `run_workflow.py` — its spec argument is `--spec`, not shared naming
  with `run.py`'s positional config.
- Don't invent flags for the runner hardening — the watchdog (`--phase-watchdog-min`), cap
  hooks (`--cap-snapshot`/`--cap-shadow`), and the orchestrator (`--orchestrator`/`--only-phase`)
  are the only CLI knobs; the deploy gate, commit-prefix, relabel, and checkpoint gates are
  **spec markers**, not flags.
- A spec whose control-rule `requires` aren't yet produced by a measurement rule in the ledger
  fails `validate_rules` — instrument that information first (see `agent_config/mental-model.md`'s
  load-bearing rule), don't work around the gate.
