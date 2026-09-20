# Contemplation prompts v1 — fan-out from one aio-control fork point

Ten analysis-only contemplations, fanned from ONE parent session. All run in-process,
sequentially, against the parent's live store; each is prefixed by the command's safety
clause, MoE method, and evidence block. Each block ends with a falsifier requirement.

## 01 — The repair loops
Reconstruct every repair cycle in this work where effort compounded without net progress
(repairing a repair, re-litigating a settled decision, re-diagnosing a failure class). For
each: the trigger that started it, the observable that would have caught it at cycle one, and
the smallest STRUCTURAL change that removes the class rather than the instance. Rank the
changes by how early they would have fired. End with one falsifier for your leading claim.

## 02 — Net-negative actions
Identify the actions in this history that were net-negative: cost exceeded value, or they
created new failure modes (ad-hoc host scripts, pattern process kills, over-wide edits,
guessing at configuration). For each: what made it attractive at the moment (the local
gradient), and what cheap guard — a tool refusal, a checklist line, a default — would have
redirected it without slowing legitimate work. End with one falsifier for your leading claim.

## 03 — The feedback structure
Map the feedback loops that governed this work — including the loops the agent was inside:
operator corrections steering behavior, CI gates catching defects, memory/capsule staleness,
cost visibility (or its absence), acceptance oracles. For each loop: damping or amplifying?
delay? Where did the loop help and where did it oscillate? Which single loop, if inverted or
closed, changes the most downstream behavior? End with one falsifier for your leading claim.

## 04 — Pivotal moments
Pick three pivotal moments in this history (a rejected approach, an accepted one, a failure
that changed the plan). For each: what the opposite choice would have changed, and what
evidence would distinguish your counterfactual story from hindsight bias. Prefer moments where
the evidence for the actual choice was weak at the time. End with one falsifier for your
leading claim.

## 05 — Smallest set of changes
Propose the smallest set of changes (system, process, prompt, measurement) that would most
change future trajectories of this project, ranked by evidence strength. For each: the
mechanism of effect, the evidence you are leaning on, the cost, and the failure mode if you
are wrong. Prefer changes that make a failure class impossible rather than a task faster.
End with one falsifier for your leading claim.

## 06 — The measurement that was missing
Across this arc, where did we measure the wrong quantity (or nothing at all) — acceptance
without quality, cost without attribution, success without verification, progress without a
loop-detector? Name the single most consequential missing instrument. Specify it concretely:
what it records, when, from which source, and its failure mode (what gaming it invites).
End with one falsifier for your leading claim.

## 07 — Oracle audit
Audit the acceptance oracles used here: binary test suites, host-side re-runs, arm-blind
model reviews, the render gate, ledger checks. For each: what did it actually verify, what
could pass it falsely, and what did it fail to see? Then design a stronger oracle for
delivery work that keeps independence and adds quality/rework signal at bounded cost.
End with one falsifier for your leading claim.

## 08 — Division of labor
Study the human interventions in this history — corrections, refusals, re-directions,
urgency. Where did the operator's attention change the outcome most, and where was it spent
on what the system should have caught itself? Propose the division-of-labor rule: what this
system must decide alone, what it must surface, and what must always wait for the human.
End with one falsifier for your leading claim.

## 09 — The cost structure
Analyze the economics of this work: where time, tokens, cache, retries, and human attention
were spent versus where value was created. Which costs were invisible at decision time
(rework, re-proof, repeated diagnostics)? Propose the cheapest instrumentation change that
would have made the largest invisible cost visible before it was paid.
End with one falsifier for your leading claim.

## 10 — The next controlled experiment
Synthesize your answers above into ONE controlled experiment this project should run next:
the question, the task family, the arms, the acceptance oracle, the sample size, the decision
rule, the budget, and the stopping conditions. State explicitly what would make the result
uninformative, and why this experiment beats the last pilot. End with one falsifier for your
leading claim.

## 11 — Steelman the opposite
Construct the strongest possible case that this project's frame is wrong or overbuilt:
measurement-driven control, the fork/contemplation architecture, the milestone structure
itself. What would a competent outsider do instead, and what evidence would show they are
right? Argue the opposite position as if you held it. Then state which of your earlier
insights survive this attack and which do not. End with one falsifier for your leading claim.

## 12 — Risk and authority red-team
Map where this system can act beyond its granted authority: agent forks, host-side commands,
pattern kills, merges, caps, scope exceptions. For each: the realistic worst outcome in the
next quarter, the guard that would stop it, and whether the risk is consciously accepted.
Rank by (probability x blast radius) / guard cost. Name the ONE guard to build first.
End with one falsifier for your leading claim.

## 13 — Belief audit
Inventory the beliefs currently steering decisions here, each with its evidence class and
freshness (measured, hedged, assumed, stale). Find the beliefs held with stale or absent
evidence that still steer (e.g. a no-change verdict from one small task). For each: what
would retire or confirm it, and what decision it currently blocks. End with one falsifier for
your leading claim.

## 14 — The controller model
Model the human controller: what they actually optimize, what they tolerate, what they refuse.
Where did this system misread them in this history (expectations, pace, authority)? Propose
how to surface decisions so human attention lands only where it changes outcomes, including
what should interrupt versus what should batch. End with one falsifier for your leading claim.

## 15 — Continuity audit
Determine what the NEXT session of this agent needs that the current records do not carry.
Walk the spine end-to-end: session close -> session open, binding updates, capsule snapshots.
Where does compaction or handoff silently lose state (intent, lineage, blockers, corrections)?
Propose the smallest record change that closes the gap, and how to test it. End with one
falsifier for your leading claim.

## 16 — Scale and transfer
Examine what breaks at ten times this workload, with other models, and with multiple
operators: which choices here are scale-dependent (concurrency, budgets, isolation, review
capacity, knowledge relevance)? Which knowledge from this arc transfers to those futures and
which is local to this moment (model quirks, host specifics, one-task verdicts)?
End with one falsifier for your leading claim.

## 17 — The questions themselves (meta)
Audit the question set you are part of. Sibling forks from this same parent are asking:
repair loops; net-negative actions; feedback structure; pivotal moments; smallest changes;
missing measurement; oracle audit; division of labor; cost structure; next experiment;
steelman the opposite; risk/authority red-team; belief audit; controller model; continuity
audit; scale/transfer. Which of these are well-posed, which are redundant, which are missing
entirely? What single different question would change the most? Write the TWO strongest NEW
questions for the next wave, each with the reason it yields insight the current set cannot,
and state how you would score whether this contemplation practice was worth its cost.
End with one falsifier for your leading claim.
