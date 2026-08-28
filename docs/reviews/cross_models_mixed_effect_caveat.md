---
status: accepted
---

# cross_models corpus — data-quality caveat (mixed-effect runs)

**Date:** 2026-08-28 · **Records:** the cross-models campaign (flash → haiku → sonnet → sol → terra
story cells, completed 2026-08-28) and the accumulated story corpus it completed (237 stories).

## The caveat

**The haiku/sonnet per-condition success rates are NOT clean treatments of the intended
conditions.** The operator's observation at review time: the Claude CLI sessions were timing out
and otherwise failing backend-side during those runs — a mixed effect of (a) the intended
condition (clean / bad_seed / early_degrade) and (b) CLI/backend execution artifacts (timeouts,
session resets, truncated sessions). The measured rates for `claude-haiku-4-5` (58.3% clean /
50% bad_seed / 58.3% early_degrade) and `claude-sonnet-5` (73.3% clean / 87.5% bad_seed / 58.3%
early_degrade) therefore confound capability with execution reliability.

**What is NOT claimed from this corpus:**

- No per-condition mechanism for the Claude models (the "no degradation gradient" reading is
  undermined — the runs were not clean per-condition treatments).
- No "capability cliff" attribution to the models themselves for the Claude pair.

**What remains usable (with the caveat):**

- The cost-per-success frontier of the deepseek/openai family (flash → luna → pro at ≤ $0.17/
  story, ≥ 96.8% success) — those runs are not implicated in the caveat and their rates are
  consistent with the pre-caveat corpus.
- The absolute costs (sonnet ≈ $150 of the $340 corpus spend; sol $3.82/story) — cost fields
  are execution records, not condition outcomes.
- The routing implication (the control plane's model recommendations should weight the
  cost-per-success frontier) stands directionally but should be re-measured with clean runs
  before it becomes a policy.

## Remediation status

The backend reliability defects (the bare-`python` PATH issue, the analyze timeout, the
`python3` invocations) were fixed during the campaign's own operations; the operator notes
"we have fixed this". **The next cross-model run on the Claude models should be executed under
the fixed runner and the rates re-measured before any policy consumes them.** The lab-book
aggregations derived from this corpus carry this caveat transitively until re-measured.

## Guard

This document is a human-recorded data-quality note (provenance [H] — operator observation at
review of the campaign results; the execution artifacts are [M]). It does not alter the
measured artifacts; it restricts their interpretation until clean re-runs exist.
