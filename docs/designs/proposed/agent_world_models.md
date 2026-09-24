---
status: proposed
---

# Agent world models — the V/M/C split applied to `agentic_dynamics`

**Status:** PROPOSED (2026-09-24, controller-directed; the session's synthesis of the World Models
reading). **Sources (inspiration only — no literal integration):**
[worldmodels.github.io](https://worldmodels.github.io/) (Ha & Schmidhuber, *Recurrent World Models
Facilitate Policy Evolution*, NeurIPS 2018), the reproduction blog
[blog.otoro.net/2018/06/09/world-models-experiments](https://blog.otoro.net/2018/06/09/world-models-experiments/),
and the reference repo `hardmaru/WorldModelsExperiments` (read, not vendored).

## 1. Why this document

The controller's standing observation: the system measures everything and feeds almost none of it
back into the agent's field of view. "We're flying blind" / "the entire thing keeps getting lost
while you are triaging and building". This document fixes the concept so the next session can act
on it: the agent's **world model** — `V` (compression), `M` (prediction), `C` (control) — mapped to
our existing planes, plus the loop that closes: **rollouts → retrain M → retrain C inside M → more
rollouts** (curiosity where M is wrong) **+ replay**.

## 2. The claim (three lessons worth stealing)

1. **Capacity belongs in the model, not the policy.** The World Models agent solved CarRacing with
   a **867-parameter linear controller** acting on features from a 4.3M-parameter VAE + 422k-
   parameter MDN-RNN. The win was the representation, not the actor.
2. **`h_t` — the future-distribution state — is the difference between wobbling and driving.**
   V-only (current-observation latent `z`): score 632 ± 251, "wobbly and unstable". Adding the
   RNN's hidden state `h_t` (which carries the *distribution of what is likely next*): **906 ± 21**,
   solved. The controller does not plan; it acts from `[z_t, h_t]`.
3. **Train inside a noisy dream, and never let the agent feed on its own model.** Sampling the
   model's future with temperature `τ` prevents the agent from exploiting the model's
   imperfections ("cheating the world model" — policies that look great against M, fail in
   reality). Too-cold dreams collapse modes and produce agents that fail the real world; calibrated
   uncertainty transfers. Their loop iterates: rollouts → retrain M → retrain C inside M → more
   rollouts (curiosity = where M is wrong), with **replay** consolidation — "less like dreaming,
   more like thought".

## 3. The mapping

| World Models | Here | Where it lives today |
|---|---|---|
| **V** — compress the observation | The knowledge plane: **code graph + registry/corpus + mental-model surfaces**. The compressed, structured representation of "what this system is". | Neo4j code graph (`kb-neo4j-v1` current; 244 CodeModule / 32k SymbolVersion / 5.4k CALLS…); `experiments/results/registry_index.jsonl` + `kb/`; `agent_config/mental-model.md` (+ mirrors); `docs/` corpus |
| **M** — model the distribution of next states | **Our measurements**: confidence, basin escape, grit, entropy, failure classes, routing recommendations, cost/latency forecasts — the model of *what happens when an agent like this meets work like this*. | `experiments/results/` (trajectories, lab books, usage/settlement), `control.routing` + `control.model_policy`, the register's failure classes, the control db's run/step history |
| **C** — the controller | Model choice, phase briefs, the AIO decision loop, routing, gates, admission. **We keep tuning C** — and this session's fixes (per-unit prompts, independent verifier, host acceptance) were all C-side. | `workflows/**`, `agent_config/`, `control/` policies, the AIO's packet loop |
| **Dream rollouts** | **Contemplation**: forked `t+1` questions at session end — hypothetical futures sampled instead of stepping the environment. | `contemplation_fanout.yaml`, `fork_branch.yaml`, `fork_seed.yaml`, close records |
| **Replay / consolidation** | Session close + `reflect` + the register: replaying recent experience into durable, retrievable structure — "less like dreaming, more like thought". | `session close`, `reflect`, `docs/reviews/loose_ends_register.md`, KB close/reflection records |
| **Temperature `τ`** | **Perturbation conditions** (clean/bad_seed/early_degrade/late_degrade) and the adversarial gates: measured robustness under calibrated noise. | `PerturbationCondition`, measurement operators, adversarial reviews |

## 4. The diagnosis: our agents wobble because they act on `z` alone

Observed on 2026-09-24, several times in one night: slices that **sweep** their successors'
work; successors that fire `NO_CHANGES` because nothing was left; a drawer that **fabricates**
`requested_id` client-side instead of asking the server; priors that land 194 lines of production
code despite a notes-only fence. In V/M/C terms: every one of these is an actor optimizing against
an **under-modeled world** — the brief and current files (`z`) with no distribution over "how this
class of work fails here" (`h`). We fixed each instance with a **fence** (C-side reward shaping).
The paper says the durable fix is the other direction: **make the model good enough to act from,
and train under uncertainty so exploitation is unattractive.**

## 5. The loop we will build (applied, not integrated)

```
rollouts (runs)                      →  already our daily practice (queue, fleet, cells)
  M: compress outcomes into            →  the missing serving path: outcome models as RETRIEVED
     served predictions                    PREDICTIONS (failure-class lookup, routing, forecasts)
  C: phase-aware context selection     →  route each phase the right context layers (below)
  rollouts again                       →  every run feeds the corpus by construction
  curiosity = where M is wrong         →  register rows where a prediction failed / M had no data
  replay = close + reflect             →  structured consolidation into the next session's h_t
```

**Non-negotiable inherited disciplines:** predictions are **measured or absent** (no fabricated
zeros); every served prediction carries provenance ([M]/[C]/[H]); the model never becomes ground
truth for verification (independent verifier stays independent); the loop adds **no new service** —
it composes retrieval + measurement + control planes that exist.

## 6. Context layers (what "retrieve different layers" means)

Retrieval should serve the layer the *phase* needs, not one fused slice:

| Layer | Content | Feeds |
|---|---|---|
| **L0 task** | goal, brief, phase | always (today's only layer) |
| **L1 structure** (`z`) | code graph, module map, mental-model surfaces | plan/prior phases — "what is this system" |
| **L2 history** (`h` memory) | register rows, close/decision records, prior attempts on this spec | every phase at open — "what happened here before" |
| **L3 outcomes** (`h` future) | measured distributions: failure classes, routing, cost/latency, what-changed-last-time | risk/planning moments — "what is likely next" |
| **L4 self** | the AIO self-knowledge layer (sessions, decisions, beliefs, scoreboard) | the controller's own decisions |

L3 barely exists as retrieval today even though the corpus to build it is sitting in
`experiments/results/`. L2 exists as prose for humans, not records for agents.

## 7. Contemplation as M-rollout (the operator's thread, formalized)

At session end, fork `t+1` questions. Today each fork is an LLM opinion with no `h`. In this frame
each fork is a **sample from M**, and the pipeline should be:

1. **Fork** — enumerate candidate futures (existing contemplation specs).
2. **Score** — against L3: does this future resemble a measured failure class? what did the corpus
   say the last K times? (retrieval over trajectories/outcomes, not vibes).
3. **Consolidate** — survivors become (a) register rows / named follow-ups, (b) the next session's
   `h_{t+1}` via the close record and opening prompt.
4. **Learn** — predictions that failed are curiosity signals: M is wrong here; queue the gap.

The close record → opening-prompt chain we already run by hand **is** replay; this makes it
structured, scored, and retrievable.

## 8. What exists / what is missing (honest)

| Exists | Missing |
|---|---|
| The V-substrate (graph + corpus + registry), live and current | An agent-facing serving path that returns **structure** on demand (the graph-question-first discipline is manual) |
| The M-substrate (measurements, trajectories, lab books) | Predictions **served** into prompts; failure-class retrieval; forecast consumption |
| C controls (routing, policies, briefs) | **Phase-aware layer selection** (which context, when) |
| Contemplation specs + close/reflect | Fork **scoring** against outcomes; consolidation into `h_{t+1}` |
| Perturbation/temperature machinery | Using τ deliberately when *training/planning* (noised briefs), not only when measuring |
| Independent verification + acceptance (anti-cheat) | Closing curiosity: register where the model had no data |

## 9. First steps (for the next session — bounded, one unit each)

1. **Layer-aware retrieval** in the (`now default-ON`) augmentation seam: a phase-kind → layer
   routing rule (L1 for priors, L2 always, L3 at risk points), with the routing choice recorded
   per phase (so it becomes measurable).
2. **Serve L3**: the smallest true prediction — "failure classes adjacent to this plan" — as
   retrieved evidence with provenance, starting from the register's own class vocabulary.
3. **Contemplation scoring**: extend the fork specs so each fork is scored against the corpus and
   the survivors consolidate into the close record (no new service; retrieval + records).
4. **Curiosity rows**: where a served prediction was wrong or absent, write the register row the
   loop consumes.

References for the next session: this doc; `docs/designs/proposed/self_knowledge_layer.md`;
`docs/designs/proposed/system_knowledge_abstraction.md`; register L57 (graph-grounded mental
models), L60 (this). Companion change in this PR: the retrieval seam default flips ON
(`rag_augment` + the cell env's `FINOPS_NEO4J_URI`) — the first closing of the loop.
