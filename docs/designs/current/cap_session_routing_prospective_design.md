---
status: accepted
---

# cap_session_routing_prospective — design: the 4-arm session-policy study, LIVE

**Status: accepted** · Predecessor: `cap_session_routing_spec` (retrospective, completed) +
the addendum design `docs/designs/current/context_abstraction_addendum_design.md` §4.4
(`session_policy_evidence_seed` — the frozen prospective shape this campaign executes).

## 1. What this campaign is

The retrospective replay (`scripts/retro_session_routing.py`,
`experiments/results/session_routing_retrospective.json`) measured the arms on EXISTING
ledger rows: fork_cached n=246 cpvo $1.2658, escalate n=7 cpvo $3.9238 — the "escalation
premium" ≈ 3.1× (cap_pattern_minting.md:150-156), "not v1-mintable". A retrospective dataset
CANNOT estimate the causal effect of session policy: arms were never randomized; the
checkpoint arms were never recorded (CAP I10 forward-only — `checkpoint_snapshot_identity`
is declared-never-emitted). THIS campaign runs the arms LIVE: randomized cells where the
session policy is the assigned arm, outcomes measured per arm on the immutable commits.

## 2. Arms (the factor) — executable-now with documented proxies

| arm | live behavior (what the cell's runner does at phase boundaries) | checkpoint-typed proxy |
|---|---|---|
| `continue` | one session for the whole cell (fork: false) — cache reuse, stale-context risk | the no-checkpoint baseline |
| `fork_blind` | a new session per phase, same model, cold cache | fork without checkpoint |
| `fork_cached` | a new session per phase, same model, warm cache (the prior phase's context) | fork-with-checkpoint simulated by cache reuse (the retro proxy, n=246) |
| `escalate` | a failed phase is re-run in a NEW session on the OTHER model (pro <-> flash) | escalate-with-checkpoint; model_change_required gate |

**Honest boundary (recorded, not silent):** the typed checkpoint arms
(`fork_with_checkpoint`, `escalate_with_checkpoint` with a real `context_snapshot_id`) are
NOT executable — checkpoints have zero production capture (I10). The proxies above are the
evidence spec's own arm definitions (`cap_session_routing_evidence.yaml` v0.2: `fork_cached`
= new session + cache_read_tokens > 0; `escalate` = failed run then successful run on the
other model). The campaign records the proxy mapping in every manifest; the I10-gated typed
arms are listed as not-run, never estimated.

## 3. Factors and design (the addendum's frozen shape, executed)

- `session_policy`: [continue, fork_blind, fork_cached, escalate]
- `model`: [deepseek/deepseek-v4-pro, deepseek/deepseek-v4-flash] (the escalate arm's target
  is the OTHER model; the model x policy interaction must be estimable — addendum F5)
- `repetition`: [r1, r2, r3] (within-cell variance for the uncertainty term — addendum)
- Design: factorial — 24 cells. `stop.budget_usd = 40.0` (the addendum's figure).

## 4. The cell (the stimulus)

One small multi-phase agent_task workflow — the calibration-cell pattern — where the assigned
session policy governs phase-boundary behavior. The cell spec is authored by p1 per this
design (a small build task: implement + test + verify phases against a seeded app). fork is
CONTROLLED BY THE ARM, not the runner (addendum: `fork: false` — arms control forking).

## 5. Outcome rule (the addendum's, reusing what is measured)

`session_policy_outcome` requires `[test_executed_success, confidence, tokens_in, tokens_out,
tokens_answer, tokens_explanation, perturbation_strength]` (all ledger-measured) and produces
`[session_verified_success, session_context_growth]`. Cost per verified success (cpvo),
cache utilization (cache_hit, tokens_in delta across phases), rework (failed phases),
repeated failures, and latency are computed from the ledgers per arm — the addendum's
measured list: "verified success, total cost, cache utilization, latency, rework, repeated
failures, context-token growth."

## 6. Verdict question

Does the assigned session policy change verified-success-per-dollar (cpvo) net of cache and
context-pressure effects — LIVE, vs the retrospective's arms? The retrospective escalation
premium (3.1×) is tested under randomization; the campaign reports per-arm cpvo + verified
success + the model interaction. Descriptive at n=3 per policy-model cell (like every prior
campaign); no gate is cleared; the 3.1× premium is either confirmed, moved, or falsified with
live numbers.

## 7. Acceptance criteria

1. Every cell's manifest records the arm + the proxy mapping (fork_cached/escalate semantics).
2. The escalate arm actually changed models on failure (provable in the ledger: failed phase
   -> new session, other model); a narrated-but-unexecuted escalation is a FAILED finding.
3. Per-arm cpvo, verified-success rate, cache utilization, rework, latency from the ledgers.
4. The retrospective comparison table (retro vs live per arm) with the numbers.
5. No gate-clearing claim; the I10-gated typed arms listed as not-run.
