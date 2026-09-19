---
status: proposed
---

# Prompt-branch boundary — what the isolated execution path actually supports (Story B)

**Date:** 2026-09-19 · **Actor:** AIO · **Source:** main `0eb4b4592ccf72eac526da1d500bf9747e455f48`
**Question:** before launching the prompt-branch pilot, what kind of branching does the ordinary
(isolated, containerized) execution path actually support, and what must be labeled instead of
claimed?

## 1. The three source boundaries, verified directly

1. **Native OpenCode session forking exists — in-process only.** `run_opencode_agentic` takes
   `session_id` + `fork`; the flags are appended only when BOTH are present
   (`src/agentic_dynamics/adapters/opencode.py:454-455`: `--session <id> --fork`). The runner
   enables them only when `fork_enabled and prev_session_id and prev_model == attempt_model`
   (`runtime/workflow_runner.py:4363-4369`) — a model switch breaks the prefix by design. The
   `fork` option chains each phase from the PREVIOUS phase of the SAME run/process
   (`workflow_runner.py:3695-3698, 4066`); it is not a fixed checkpoint four siblings can share.
2. **The Docker path ignores local session/fork kwargs and starts fresh sessions.** The engine
   hands executor-internal kwargs (`session_id`/`fork` for cache chaining) through the phase
   dict for the LOCAL executor, with the comment "the Docker executor ignores them — its
   container has its own watchdog and its own fresh session"
   (`runtime/workflow_runner.py:1851-1855`). `StepRequest` carries no session/fork field at all
   (`runtime/executor.py:74-107`). Each cell's OpenCode state is a per-attempt namespace
   (`<spec>/<run-id>/<phase>/a<attempt>`, `scripts/fleet/docker_executor.py:149-160`) and the
   namespace is never shared between two cells — two concurrent sessions cannot read or write
   each other's state. **Consequence: setting `fork: true` on a Docker-run spec would be a
   silent no-op; it is NOT used and Docker forking is NOT claimed.**
3. **The prepared-step transport carries exact bytes, hash-verified.**
   `prepared-step/v1` (`runtime/executor.py:113-145`) carries the full final prompt +
   `prompt_sha256`; the child loads it with `load_prepared_step`, refusing absent/invalid/
   hash-mismatched documents (`executor.py:199-229`). The parent writes it inside the run
   clone at `<clone>/.fleet/prepared_steps/<phase>.a<attempt>.json` (git-excluded)
   (`scripts/fleet/docker_executor.py:190-207`) and the child executes those exact bytes — it
   never re-derives from the spec (`scripts/run_workflow.py:740-748`,
   `runtime/workflow_runner.py:1926-1983`).

## 2. What the pilot uses: **shared-prefix prompt branching**

Independent Docker sessions (one durable fleet submission per cell, sequential at concurrency
1) receive an immutable, approved common context prefix and a different appended instruction.
This is not a native conversation-history fork and is labeled as such everywhere.

- Assembly (frozen): `goal = common_task` (A0) or `common_task + "\n\n" + arm_suffix`;
  `final_prompt = common_prefix` (A0) or `common_prefix + "\n\n" + arm_suffix`, where
  `common_prefix = domain_context + "\n\n" + common_task` and the phase template renders
  `{domain_context}\n\n{goal}\n` so the arm instruction is the conversation tail.
- Frozen checkpoint: `experiments/results/prompt_branch_pilot/checkpoint.json`
  (sha256 `264e27899810ef7475f4f24abd3d0a7284960aee8a1c3ad99ddd4e703226dd3f`), texts in the
  same directory; plan in `docs/experiments/preregistrations/prompt_branch_pilot_preregistration.md`.

## 3. Deterministic checks (run 2026-09-19, before any paid execution)

Performed by loading the spec (`load_spec`), composing each arm's prompt with the runner's own
`_build_phase_prompt`, and round-tripping the executor's prepared-step codec:

| Check | Result |
|---|---|
| Phase template references `{domain_context}` (no appended block after the goal) | PASS |
| All arms' final prompts start with the common prefix bytes | PASS |
| A0's prompt is exactly `common_prefix + "\n"` (no hidden arm text) | PASS |
| A1/A2 suffix appended at the tail (`… + "\n\n" + suffix + "\n"`) | PASS |
| Suffixes pairwise distinct; final prompts pairwise distinct | PASS |
| The runner's 40-char goal prefix is identical across arms (`Implement a pure-Python, stdlib-only pac`) | PASS |
| Expected commit subject `[workflow] generate — Implement a pure-Python, stdlib-only pac` derivable for all arms | PASS |
| Prepared-step round-trip: `to_prepared_dict` → `load_prepared_step` verifies for every frozen arm | PASS (3/3) |
| Tampered prompt is REFUSED by the transport (hash mismatch) | PASS |
| Existing transport/isolation suites (`tests/test_prepared_step_exactness.py`, `test_prepared_step_transport.py`, `test_docker_executor_namespace.py`) | PASS (17 tests) |

Private-content exclusion for the checkpoint: the frozen texts contain only the task, the
oracle path, scope, constraints and the arm instructions — no coordinator history, no raw
private requests, no other arm's output, no held-out evaluation answers (checked).

## 4. Earliest divergence of the request — what is verified, what is not

- The bytes the adapter executes = `_build_standardized_prompt(prompt)` prepending a
  deterministic header (`adapters/opencode.py:354-400, 532-540`); with the pilot's fixed
  settings the header is CONSTANT across arms (it carries no timestamp), so the executed
  request = constant header + frozen prefix + arm suffix. Divergence starts at each arm's
  suffix (A0: at the end of the prefix).
- **Verified at this boundary:** parent→child transported prompt bytes and their hash
  (prepared-step load), and the final prompt composition (checks above). Once a cell runs, the
  same bytes are additionally verifiable from the cell's own records (the prepared step in the
  run clone + the child session transcript).
- **NOT verified:** equality of the provider's complete serialized request. OpenCode's own
  system instructions/tool schemas/working-directory rendering and the provider template sit
  outside this repository; their contribution to the prefix is not claimed to be identical at
  that boundary. The pilot therefore measures provider cache use DIRECTLY from the
  provider-reported token counters per cell (token-weighted input cache reads /
  (reads + misses) via `scripts/session_cache_report.py`), never from the prepared-prompt hash
  alone, and never via the convenience `AgenticResult.cache_hit_rate` (its denominator
  includes completion/reasoning tokens).
- **Isolation:** each cell gets its own run clone and its own per-attempt state namespace; a
  writable OpenCode database is never shared between workers; no isolation is weakened to
  improve a cache score.

## 5. Refusal semantics carried by the pilot

- A prepared step whose prompt does not match its carried hash is refused by the child (never
  repaired) — the tamper check above is the transport-level refusal.
- Unknown/absent arm instruction at submission time is prevented by construction (the goal is
  assembled from the frozen files and recorded per cell); A3's constructor output is validated
  before use and an invalid generation records an infrastructure failure (no silent retry).
- `fork: true` under the Docker path remains unsupported and unclaimed.
