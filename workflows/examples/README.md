# workflows/examples/ — the four canonical workflow-v1 shapes

The **positive cases** for the Wave-3 authoring contract: each file validates against
`workflows/schema/workflow-v1.schema.json` (draft 2020-12) AND passes
`workflows/lint_workflow.py` with zero findings. A new operational workflow is scaffolded
from these (`workflow new`, Wave-3 a3) — never copied from a historical ExperimentSpec
YAML under `workflows/repository|operations|research`.

Every example carries the minimal prompt the schema requires. Prompt text is **scaffolded
instruction, never gate evidence** — each gate's evidence is its executor (`test`/`command`
verdict, or a human approval), which is exactly why no example trips `prompt-as-evidence`.

## The four shapes (documented structural signatures)

| Example | Shape | Structural signature (what the tests assert) |
|---|---|---|
| `minimal-agent-workflow.yaml` | **the smallest valid workflow** — one agent step + one test gate | 2 steps; kinds `[agent, gate]`; executors `[agent, test]`; workspace `isolated`; promotion requires exactly one gate (`[verify]`). The shortest of the four. |
| `approval-workflow.yaml` | **an approval checkpoint** — agent step + verifier gate + controller approval | 3 steps; kinds `[agent, gate, approval]`; the only example with a `kind: approval` / `executor: human` step; promotion requires the gate AND the approval (`[verify, approve]`). |
| `research-workflow.yaml` | **a measurement/research run** — repeatable and runnable, produces no candidate | workspace `readonly`; 3 steps; kinds `[task, agent, agent]`, every step `research_readonly`; **no gate/approval steps and no promotion block** (nothing mutates, so nothing is gated; repeatability is the verification). |
| `publication-workflow.yaml` | **a gated publication pipeline** — build + HTML-consistency + receipt + deploy gates | 4 steps; kinds `[task, gate, gate, gate]`; executors all `command`; **no `agent` step at all** (fully deterministic); promotion requires three gates (`[html-consistency, receipt, deploy]`). |

The four are pairwise structurally distinct: they differ on workspace mode, step-kind
sequence, executor set, and/or the required-gate list — `tests/test_workflow_examples.py`
asserts each signature against the file AND asserts the signatures are all different.

## Using an example as a scaffold

```bash
# validate + lint an example (or any workflow-v1 file)
python -c "from workflows import lint_workflow as lw; r=lw.lint_path('workflows/examples/minimal-agent-workflow.yaml'); print('ok' if r.ok else r.codes)"
```

These four files are workflow-v1 definitions — a **different document kind** from the
ExperimentSpec corpus. They are deliberately excluded from the ExperimentSpec lifecycle
index (`experiment_spec.committed_spec_paths` filters documents shaped like a workflow-v1
definition), so the historical corpus and its guards are untouched by their presence.
