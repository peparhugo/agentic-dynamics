---
status: proposed
---

# Prompt-branch pilot — pre-registration (2026-09-19)

**Status.** Checkpoint FROZEN (`experiments/results/prompt_branch_pilot/checkpoint.json`,
sha256 `264e27899810ef7475f4f24abd3d0a7284960aee8a1c3ad99ddd4e703226dd3f`). Execution is
gated on ONE spend authorization: the campaign scope `prompt_branch_pilot` needs a budget cap
installed (the admission gate denies an uncapped scope; installing a cap is a P0 controller act
and is requested, not assumed — see §Authorization).

**Research question.** For the same approved task checkpoint, do different investigation
instructions improve independently accepted outcomes, knowledge use, operator effort, cost and
elapsed time while retaining useful prefix-cache reuse?

**Task (one bounded task, fixed objective oracle).** Implement a pure-Python, stdlib-only
package `taskman` (exposing `TaskManager`) satisfying the behavioural contract in
`tests/flash_ladder/taskman_contract_test.py` at source commit
`0eb4b4592ccf72eac526da1d500bf9747e455f48`. The oracle is the unchanged contract test; no test
file may be modified. Why this task: bounded, objective, proven cell cost (~$0.09) through the
ordinary fleet path, prompt-strategy-sensitive (design + verification choices), and independent
of the in-flight Story A candidate. The finished answer is not in the checkpoint — the contract
test defines the requirement; the implementation is the arm's output.

**Execution mode — shared-prefix prompt branching (NOT native history forking).** One fleet
submission per cell (the ordinary durable path: `fleet_manager submit` / the `run_workflow`
tool with `orchestrator: true`), sequential at concurrency 1. Each cell is an independent
Docker session receiving the immutable common prefix plus its arm instruction as the tail. The
runner's `fork: true` is deliberately NOT used: under the Docker path it is silently inert
(the child gets a fresh session; sibling state namespaces are never shared), and claiming a
fork would be false. Native conversation-history forking remains a distinct, unclaimed
capability. Boundary evidence: `docs/reviews/prompt_branch_boundary.md`.

**Checkpoint (frozen inputs).**
- `checkpoint.json` (machine-readable; sha above) in
  `experiments/results/prompt_branch_pilot/`.
- Common prompt prefix: the spec's `context.domain_context` + `\n\n` + `common_task.txt`
  (final-prompt prefix sha256 `43237bf913da1661f90fb822b5959070209681a718c3ce4fb504d648c4f295ce`).
- Assembly rule: `goal = common_task if suffix == '' else common_task + '\n\n' + suffix`;
  `final_prompt = common_prefix if suffix == '' else common_prefix + '\n\n' + suffix`. The
  phase template renders `{domain_context}\n\n{goal}\n`, so every arm's prompt starts with the
  common prefix and carries its instruction at the tail.
- Frozen source: `0eb4b4592ccf...`; spec `workflows/repository/prompt_branch_pilot.yaml`
  (sha256 `6c415ad3396f8e3db6a9ec0af32498fa87df24cac6ba0cc174c953f60f3ae8a0`).
- Model/version: `deepseek/deepseek-v4-flash` (runner-resolved version recorded per cell);
  reasoning defaults (thinking_effort high, budgets 0); the cell's standard tool surface;
  `rag_augment: false` (knowledge frozen in the prefix; no per-cell retrieval or constructor —
  this keeps the prefix byte-identical across arms; augmentation is a separate future arm).
- Evaluator, allocation, budget and stop rules: below.

**Arms.** Exact texts in `experiments/results/prompt_branch_pilot/suffix_A*.txt`; hashes in
`checkpoint.json`.
- **A0 — Baseline** (suffix `""`): current approved delivery prompt, no additional perspective.
- **A1 — Evidence-first Principal Engineer**: establish the invariant the contract test
  requires, inspect the closest existing pattern, choose the smallest implementation, then
  re-verify the original requirement from scratch.
- **A2 — Adversarial pre-mortem**: enumerate false-success and regression modes, choose bounded
  checks that would catch them, then implement and run those checks alongside the required test.
- **A3 — Goal-conditioned prompt**: ONE bounded constructor call (`constructor_prompt.txt`,
  sha256 `d4e2232835c4908a1ace40e5db021cc4fa3cbd9f4c7a9b45d6934745a9ad0228`) generates the
  instruction from the frozen checkpoint; a deterministic validator rejects scope/permission/
  acceptance/private-context violations or expected-answer hints; the SAME frozen suffix is
  used for all three A3 cells; the constructor's cost and latency are counted. This arm tests a
  prompt-generation strategy, not a cost-free wording change.

**Allocation (rotation, recorded).** 12 cells, sequential, concurrency 1:
`A0-r1 A1-r1 A2-r1 A3-r1 | A1-r2 A2-r2 A3-r2 A0-r2 | A2-r3 A3-r3 A0-r3 A1-r3`.
Request keys: `aio-explicit:prompt_branch_pilot:<cell>` (one durable submission identity per
cell).

**Measurement (all scored attempts, including failures).**
- Outcome: independent contract-test verdict (host-side re-run on the exported artifact),
  the cell's own `test_executed_success`, first-pass result, failure category, repair/retry
  count.
- Cache: token-weighted input cache reads / (reads + misses) from the cell's OpenCode session
  DB via `scripts/session_cache_report.py` (provider-normalized; `tokens.cache.read` = hit,
  `tokens.input` = miss; first request and overall recorded; missing telemetry distinguished
  from a measured zero). `AgenticResult.cache_hit_rate` is NOT used as the input-cache metric.
- Cost: per cell, from recorded pricing/provenance (settlement vs reservation kept separate);
  shared preparation (constructor) cost recorded once at campaign level; evaluator cost counted.
- Time: queue wait, execution, evaluation, elapsed; no summing of overlapping parallel
  durations.
- Identities: checkpoint/spec/source, prefix + suffix hashes, prompt sha256 from the prepared
  step, run/attempt ids, candidate sha per cell.
- Human intervention: recorded with reasons (target: none beyond declared infrastructure
  policy).

**Evaluator (fixed; arm-blind).** `prompt-branch-evaluator/v1`: layer 1 deterministic
(contract-test re-run, tests-modified check, diff/sha capture); layer 2 one bounded
`deepseek-v4-flash` review per cell over the exported artifact + fixed rubric (requirement
satisfaction, meaningful verification, regressions, knowledge use, necessary human
intervention), arm label withheld; outputs decision/reasons/evidence refs/assumptions/tests.
Costs counted.

**Budget.** Stop budget $2.00; estimate ~$1.1 (12 × ~$0.09) + constructor/evaluator ~$0.03.
Admission armed; per-phase reserve $0.50, hard cap $2.00. The campaign cap request: budget
2.0 / concurrency 1.0 (the established wave level).

**Stop rules.** Stop at the approved budget, twelve scored attempts, or a demonstrated
infrastructure/comparability failure. A failed attempt is an outcome and stays recorded as a
failure; at most ONE bounded infrastructure rerun per cell (retains the original failure and
lineage); no cap raise; no silent replacement of failed cells with additional successes.

**Decision rule.** Primary: verified useful outcomes per total cost, with elapsed time and
intervention visible. Cache hit rate is a contributing measurement; a higher hit rate with
worse work is not a winner. If no attempt is accepted, report no accepted outcome and an
undefined cost-per-accepted-outcome. Twelve related attempts on one task are NOT twelve
independent proofs; held-out tasks and repeatable acceptance are required before proposing any
broad default change.

**Isolation + retention.** Cell outputs stay isolated until evaluation. No cell emits findings
into shared scope (`rag.emit_self: false`); no arm's output or task-local discovery enters
another arm's frozen input. After evaluation, material findings are published through the
existing finding-artifact → event → ingestion → registry path with experimental scope and
appropriate authority (measured results; negative outcomes retained as conditional evidence).
No arm may promote itself, rewrite its evaluator, or change global rules.

**Authorization (missing decision, requested once).** Installing the campaign cap for
`prompt_branch_pilot` is a P0 controller act. Requested: authorize the launch with
`--campaign-budget-usd 2.0 --campaign-concurrency 1` (the launcher records the cap change as
the controller act, per the established wave pattern), or name an existing campaign scope to
use instead. Until then the pilot does not run; nothing above spends.
