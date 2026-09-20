---
status: accepted
---

# Contemplation prompts v2 — divergence-forced wave, built from wave 1's own gaps

Rules (enforced in the shared context, not restated per prompt): begin with your ENTRY CLAIM —
one falsifiable sentence, first line; do NOT restate the shared history; name your lens pair;
cite a wave-1 sibling only to say precisely what you ADD beyond it; prefer an EXECUTABLE
artifact (a test, a detector, a spec with paths and commands) over prose; end with one
falsifier. Wave 1's corpus (seventeen answers incl. the synthesis) is in the shared context.

## 01 — The mechanization test
Entry claim: the controller's five findings are reproducible by a differential harness, and
the harness is cheaper than the review it replaces. Design it concretely: the inputs (config
variants, usage shapes, message sequences incl. completed/pending compactions), the expected
detections (map each of the five findings to a case), the scoring (recall against the
reviewer, false-positive cost), the integration point (which test file, which CI job, which
command), and the two ways it could pass while being worthless. If you conclude it cannot
recover the five, say what only human attention can do and bound it.

## 02 — The prose-to-mechanism compiler
Entry claim: a rule that cannot be expressed as a boundary check should not be written as a
rule. Define the compiler: given a finding (yours or wave 1's), produce either (a) an
executable check with an owner, a location, and a refusal path, or (b) an explicit "prose
only — not enforced" label. Apply it to the FIVE strongest wave-1 remedies you can name;
for each, state the artifact it becomes or why it degrades to prose. Then apply it to your
own entry claim.

## 03 — The quality boundary (Q-A)
Entry claim: context fraction does not predict accepted-outcome rate below the native limit;
the 80% advisory is safe. Design the dose-response test against data that already exist
(same-spec family depth, DLQ incidence, acceptance, realized cost) plus the smallest new run
that would falsify you; state the decision rule that keeps or removes the advisory, and the
confounder that makes the existing data unusable (if any).

## 04 — The effect receipt
Entry claim: every effectful control act must leave a durable terminal record, and today's
submits are the only act that does. Enumerate the effectful acts (submit, restart, scale,
drain, cancel, promote, publish), specify the receipt (fields, storage, who writes it), the
verification that a claimed act produced its effect, and the smallest migration that closes
the swallowed-restart class without a second control store.

## 05 — The voluntary oracle
Entry claim: the human review was the highest-yield oracle in this arc and remains
unpinned — that is the largest unhedged risk in the system. Quantify its marginal yield
(findings per review, cost per finding, what it caught that machinery did not) and design
either the rail that replaces part of it or the explicit acceptance of the residual risk,
including who reviews the reviewer.

## 06 — The independence protocol
Entry claim: this fan-out's agreement is not evidence because the samples are correlated.
Design the cheapest protocol that makes convergence informative: cross-model arms (which
models, which questions), blind entry points, pre-registered divergence predictions, and the
scoring that distinguishes independent confirmation from shared-prior repetition.

## 07 — The contemplation cadence policy
Entry claim: contemplation without a required artifact is a net cost. Given wave 1's own
score (1/5 accepted-outcome, 3/5 question-generator), write the policy: required artifacts
per wave, maxima per N accepted outcomes or per budget, the trigger that promotes a question
into an experiment, and the trigger that replaces a wave with a single harness. Make the
policy falsifiable and cheap to enforce.

## 08 — The adjacent-quantity detector
Entry claim: the synthesis's law can be operationalized as a lint that flags adjacent-quantity
substitutions in any proposal. Build it: the pattern (what a substitution looks like in a
proposal), the checklist or check, the examples it must catch from this arc (at least five),
the false positives it will produce, and then APPLY IT TO THIS WAVE (this prompt set and the
wave-1 synthesis) and report what it flags, including yourself.

## 09 — Synthesis (wave 2)
Reconcile wave 1 and wave 2. Resolve the prose-vs-mechanism contradiction with a decision
(which side wins, under what boundary). List every surviving EXECUTABLE artifact or
falsifiable question, each with its owner and next command. Score wave 2 on the same axes
wave 1 used and compare honestly. Propose either wave 3's single sharpest question or the
one harness that replaces further waves, and state what would prove that choice wrong.
