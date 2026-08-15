# Finding: an async worker self-healed its own data by writing and running a new experiment

**Date:** 2026-08-15
**Class:** emergent behavior — self-recommending experiments
**Provenance:** [M] measured · [C] computed · [H] heuristic · [P] policy/prior

## The observation [M]

We gave an `agent_task` workflow a single high-level goal — *"Instrument the four missing
ledger fields, recompute derived metrics, re-run contaminated cells, re-admit the policy
arms"* — and ran it as an async worker in a git worktree (`feature/remediation-integrity`).
The worker, a DeepSeek session with no per-step human steering, did the following in order:

1. **`scope`** — diagnosed the repository's own data contamination and wrote a re-run
   inventory (`docs/remediation_plan.md`): 16 `manifold`-labeled cells (dead 2-way
   taxonomy), up to 85 `early/late_degrade` cells whose mutation compiler had *silently*
   fallen back to clean (P0-7), and wrong-baseline cells (P0-8).
2. **`instrument`** — healed the instrumentation: added `confidence`,
   `perturbation_strength`, `test_executed_success`, and the `answer`/`explanation` token
   split to `LEDGER_FIELDS` and the result schemas.
3. **`recompute`** — regenerated all derived metrics from the existing worktrees/DB.
4. **`rerun_contaminated`** — **authored a new experiment** (which cells to re-run, under
   what condition) and **executed it**: enqueued ~33 contaminated story cells to the Redis
   queue and spawned **8 parallel workers** to drain it [M]. Queue total went 142 → 175,
   `queued` 0 → 67, `running` 1 → 7, across three providers (`deepseek-v4-pro`,
   `deepseek-v4-flash`, `gpt-5.6-luna`).

In other words: **we handed an async worker a task, and it self-healed its knowledge base
and wrote a new experiment to do so.**

## Why it worked — the mechanism

This is not an accident of one clever prompt. It is the architecture working as designed:

- The **spec is declarative** (`workflow` + `factors` + `rules` with `requires`/`produces`).
  A phase is a *goal + constraints*, not a script, so an agent can carry it out without a
  human encoding every step.
- The **load-bearing rule** ("measure before policy") made the *diagnosis* (what's
  unmeasured/contaminated) a compiler-checkable fact rather than a remembered TODO. The
  worker's `scope` phase just read the same gate the compiler enforces.
- The **queue** (`enqueue → worker → monitor`) is the execution substrate. The worker didn't
  run cells inline; it enqueued them and spawned workers — the same transport the whole
  framework uses. "Everything can be a session" includes *queue orchestration* as a session
  activity.

## Why this is the finding you were looking for [H][P]

The spec/compiler DAG reserves an **`adapt`** phase — "read per-arm regret, tweak one factor,
emit the next grid" — which we had not yet built. What we observed is that a *primitive
`adapt` emerged on its own*: the worker observed (diagnosis) → authored a new experiment
(re-run inventory) → executed it (enqueue + workers) → will measure the delta. That is the
campaign loop's core primitive, done autonomously rather than by an operator.

Once the knowledge-base branch and the ledger merge, the same worker shape generalizes from
"re-run contaminated cells" to **self-recommending experiments for system optimization and
routing policies** — because the input to `observe` becomes "the whole measured corpus +
KB," and the output of `recommend` becomes "a new `ExperimentSpec`," not just "a re-run list."

## The constraint to respect going forward [P]

**Provider rotation.** Eight workers all pulling one provider's queue will burn through a
single provider's rate limit. `scripts/enqueue.py --interleave` round-robins cells across
providers so concurrent workers spread. **Any self-recommending experiment MUST enqueue with
`--interleave`** (and the remediation spec should be corrected to say so). This is a hard
constraint, not a preference: it is the difference between a self-healing loop and a
self-DoS loop.

## Next steps

1. Correct the running `remediation_data_integrity` spec to require `--interleave` in its
   enqueue phases.
2. Adopt `self_recommending_experiment.yaml` (written alongside this finding) as the reusable
   shape for the `adapt` loop.
3. Merge the KB branch + ledger; point `observe` at the combined corpus so `recommend` can
   propose routing-policy and system-optimization experiments, not just data re-runs.
