# workflows/schema/ — the workflow-v1 authoring contract

The authoring contract behind the Wave-3 `workflow` surface. A NEW operational
workflow is authored against `workflow-v1.schema.json` (JSON Schema, draft
2020-12) and passes `workflows/lint_workflow.py` before it runs — a workflow is
**scaffolded, never copied from a historical YAML**.

The historical ExperimentSpec corpus (`workflows/repository|operations|research`)
is **the lab, not the template**: it is a different document kind (top-level
`name/question/version/artifact_kind`…), is untouched by this schema, and is never
expected to lint clean as a workflow-v1 definition.

## The document shape

```yaml
apiVersion: agentic-dynamics.io/v1
kind: Workflow
metadata:
  name: <slug>
  revision: "1"          # the definition's version — a run certifies its exact revision
  lifecycle: development # development | stable | deprecated (the DEFINITION's lifecycle)
spec:
  baseRef: main          # the ref a promotion advances candidates toward
  workspace:
    mode: isolated       # isolated | shared | readonly
  concurrency:
    group: <group>       # runs sharing a group obey the same policy
    policy: serial       # serial | bounded (needs maxRuns) | parallel
  steps:
    - id: implement
      kind: agent        # agent (mutating) | task (mutating when it writes)
                         # | gate (machine check) | approval (controller/human)
      executor: agent    # agent | test | command | human
      scope: implementation   # the five-scope machine vocabulary
      needs: []          # step ids this step depends on
      candidateFrom:     # the mutating step whose candidate this step consumes
      gate: {executor: test, blocking: true}   # inline self-gate on a mutating step
      prompt: |          # scaffolded instructions — NEVER gate evidence
        ...
  promotion:
    candidateFrom: implement   # the step whose final candidate is promoted
    strategy: squash-merge     # squash-merge | merge-commit | fast-forward
    requiredGates: [verify]    # ≥1 gate/approval step id that must pass
```

**There is NO operational status field.** A workflow's status (running / awaiting
approval / promotable / …) is derived from run evidence ("completion follows the
revision") — authored `status:` anywhere in a definition is a lint error.

## The seven rejections (schema + linter)

The JSON Schema expresses the structural contract; `workflows/lint_workflow.py`
validates the schema fields **and** the semantic rules below (named error codes in
parentheses — stable strings a caller can assert on).

| Rejection | Code | Expressible in schema? |
|---|---|---|
| Authored operational status anywhere in the definition | `authored-status` | shape-level (`additionalProperties`); the linter scans every key |
| Unknown step kind | `unknown-step-kind` | yes (enum) |
| Missing concurrency policy (or concurrency block) | `missing-concurrency` | yes (required) |
| Mutating step with no downstream verification | `mutating-without-verification` | **no — semantic** |
| Promotion without required gates | `promotion-without-gates` | minItems only — a gate list naming non-gates needs the linter |
| Gate not bound to a candidate sha | `unbound-gate` | **no — semantic** |
| Prompt text as the sole evidence for a required gate | `prompt-as-evidence` | **no — semantic** |

A gate step is *bound* when it names a mutating `candidateFrom`, or has exactly one
mutating step in its needs-closure. A *required* gate (bound, or listed in
`requiredGates`) must carry a machine executor (`test`/`command`); its evidence is
the executor's verdict, never prose. A controller approval (`kind: approval`,
executor `human`) is legitimate human gate evidence.

## Usage

```python
from workflows import lint_workflow as lw

report = lw.lint_path("workflows/examples/minimal-agent-workflow.yaml")
report.ok              # True only when schema + every semantic rule pass
report.codes           # the named error codes, e.g. ["mutating-without-verification"]
```

The `workflow lint` / `workflow new` / `workflow plan --json` command surface (Wave
3, a3) wires this module into the CLI.
