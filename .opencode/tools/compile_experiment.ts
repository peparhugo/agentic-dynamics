import { tool } from "@opencode-ai/plugin"

// CONVENTION BREAK: compile_experiment.py has no CLI (no argparse / __main__) — it's a
// pure library, and no scripts/*.py wraps it. Every other tool in this directory shells
// to a scripts/*.py file; this one shells to an inline `python3 -c` snippet instead.
// See docs/opencode_docs_spec.md §3.1 for the (a)/(b) tradeoff — this ships option (a).
const PY_SNIPPET = `
import sys, json
from pathlib import Path

sys.path.insert(0, "src")
from instrument.experiment_spec import load_spec
from instrument.compile_experiment import compile_spec, validate_rules, SpecError

spec_path, mode = sys.argv[1], sys.argv[2]
spec = load_spec(Path(spec_path))

if mode == "validate":
    errors = validate_rules(spec)
    print(json.dumps({"valid": not errors, "errors": errors}))
    sys.exit(1 if errors else 0)
else:
    try:
        dag = compile_spec(spec)
    except SpecError as e:
        print(json.dumps({"valid": False, "errors": e.errors}))
        sys.exit(1)
    print(json.dumps({
        "valid": True,
        "phases": dag.names(),
        "edges": dag.edges,
        "feedback": dag.feedback,
        "topological_order": dag.topological_order(),
    }))
`

export default tool({
  description:
    "Validate or compile an ExperimentSpec YAML (src/instrument/compile_experiment.py — written, no standalone CLI). validate runs the requires/produces gate only; compile also builds the phase DAG.",
  args: {
    spec: tool.schema.string().describe("Path to an experiments/specs/*.yaml file"),
    mode: tool.schema.enum(["validate", "compile"]).optional().default("validate"),
  },
  async execute(args, ctx) {
    const result = await Bun.$`python3 -c ${PY_SNIPPET} ${args.spec} ${args.mode}`.cwd(ctx.directory).nothrow()
    const output = result.stdout.toString().trim()
    const err = result.stderr.toString().trim()

    if (result.exitCode !== 0 && !output) {
      return { output: err || `compile_experiment ${args.mode} failed (exit ${result.exitCode})`, metadata: { spec: args.spec, mode: args.mode, exit_code: result.exitCode } }
    }

    return {
      output,
      metadata: { spec: args.spec, mode: args.mode, timestamp: new Date().toISOString() },
    }
  },
})
