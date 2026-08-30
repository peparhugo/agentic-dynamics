---
status: proposed
---
# Idea (Deferred) — Reasoning Measurement in the Fact Plane

**Status: proposed as a RECORDED IDEA — explicitly NOT in the implementation queue.** This
document exists so the idea, its rationale, and its deferral decision survive in writing. It is
not a workflow spec; nothing in it is scheduled, wired, or launchable.

## The idea

Give the fact plane a derived reasoning signal so rules *could* consume "how much / how well the
model thought" — e.g. a `think_do_ratio` predicate (`[C]`, derived): per-attempt reasoning
content vs the verified outcome that followed, plus a per-model coverage annotation.

## Why it's attractive (the potential, unexercised)

- **Overthinking detection**: reasoning spend vs cost-per-verified-outcome — a routing signal
  ("this task type doesn't reward deep reasoning; route to the cheaper tier").
- **Think-do coupling**: high coupling = the model acts on what it reasoned; low = narration and
  action disconnected (the existing lab's hypothesis, elevated from post-hoc to citable).
- **Flail early-warning**: reasoning patterns that precede failure (lab_flail_triggers' territory).
- **Live surfacing**: a Control Room "Live Reasoning" panel is only worth building if the signal
  behind it is measured — display of a signal that matters, not a view of nothing.

## What already exists (the capture layer — no new capture needed)

| Piece | State |
|---|---|
| `tokens_reasoning` ledger field | exists; **Claude usage reports 0** (thinking folds into `output_tokens` — billing is correct, breakout is not available) |
| Reasoning CONTENT in trajectories | captured — `session.jsonl` + claude CLI thinking blocks; `claude_adapter.py:125` already extracts `{"type": "reasoning", text}` parts |
| `lab_think_do_coupling.py` | measures think-do coupling from session reasoning — but **quarantined** (built on the retired `_results_summary.json`; output in `legacy_labs/`, not publishable) |
| `analyze_trajectories.py`, `lab_flail_triggers.py` | post-hoc reasoning analysis |
| `FACT_PREDICATES` | **zero reasoning predicates** — the gate refuses any rule that requires one |

## Why it's deferred (the decision, per the load-bearing rule)

1. **Nothing consumes it.** No rule, arm, or pattern currently requires a reasoning signal. Per
   the core discipline — instrument what a policy consumes; the gate refuses what isn't measured —
   measuring reasoning *before* a consumer exists is machinery-for-machinery's-sake.
2. **The lab already answers the question** when asked (post-hoc). Elevating it to the fact
   plane changes its epistemic lane (ADVISORY/H → DERIVED/C) and costs a reducer + coverage
   honesty work; that cost is only justified by a consumer.
3. **The honest measurement caveat is real**: a cross-model reasoning comparison must carry
   coverage per source — Claude's thinking is content-derived (from the stream), DeepSeek/OpenAI's
   is usage-derived; a naive `tokens_reasoning` comparison would silently bias toward models that
   expose the breakout.

## What would un-defer it (the triggers)

- A routing arm whose hypothesis needs reasoning (e.g. "escalate when think-do coupling is low",
  "route cheap when reasoning spend is high relative to verified outcome") — written as a spec
  with `requires_facts: [think_do_ratio]`; the gate then demands the predicate, and the
  measurement follows the consumer.
- The Control Room Live-Reasoning panel is built (D4 surface) — display follows measurement.

## Explicitly out of scope

- No predicate, no reducer, no workflow spec, no launch, no queue entry. This document is the
  idea on paper, deferred by decision, re-openable only by one of the triggers above.
