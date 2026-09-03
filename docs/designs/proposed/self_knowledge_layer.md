# The self-knowledge layer (loop 2) — design

**Status:** proposed (2026-09-03). The finding layer (loop 1's distilled layer, `kb_finding_layer`
spec) is in flight; this design is its successor: the machine pointed at itself.

## The frame: two learning loops

**Loop 1 — the machine learns about AI economics** (the instrument). Waves → cells → measured
findings → control rules → policy arms → grids → campaigns. This is what the repo was built for,
and the finding layer (`kb_finding_layer`) finally gives its distilled conclusions a durable
home (phase findings by default, backfilled wave verdicts, retrieval order, the narrator).

**Loop 2 — the system learns about itself operating.** Its own success rates, its failure modes,
the controller's preferences, the agent's (AIO's) mistakes. This loop does not exist yet. Every
AIO session today starts as a fresh prior: compaction erases the previous session's posterior,
and the doctrine (stable rules) cannot carry situated decisions, accumulated experience, or
reflection. The result is visible in every session boundary: re-derived state, re-litigated
decisions, re-learned preferences.

The two loops share the same piping — the knowledge stream, the consumer groups, the
evidence_class authority ladder, supersede chains, the outbox, the control db. Loop 2 is not a
new architecture; it is **consistency of production** for a small set of always-on record types.

## The memory layers

| Layer | What it stores | Today | Need |
|---|---|---|---|
| Episodic / chronological | The session story: opened with X, ran waves Y, hit Z, parked W | Ledgers (skeleton); `meta_session` records exist (27, embryonic) | Session records as the SPINE: open retrieves the last close, close writes its own |
| Associative / causal | What X is connected to and why | Graph leg EMPTY (`graph_paths: 0`) | The graph populated so causality is traversable — the dependence structure for a Bayesian |
| Experience / situational | What happened when we acted | Scattered across docs/reviews/* | Indexed by situation, surfaced at the moment of authoring |
| Reflective / meta | What we'd do differently; how we work | Nothing | A standing reflection series each session appends to |

## The Bayesian–frequentist synthesis

The controller is "a Bayesian who applies frequentist." The architecture already carries the
skeleton of belief tracking:

- **Priors** = the doctrine + the evidence_class ladder ([P] policy / [M] measured / [C] derived /
  [H] heuristic — a prior-authority ladder by construction).
- **Frequentist evidence** = measured outcomes accumulating every wave: pass rates,
  adversarial-finding rates, cost-per-merge, time-to-merge, false-positive frequency,
  wave-convergence counts.
- **Posteriors** = updated beliefs ("flash converges in ~1 wave on in-process work, ~4 on
  container seams" — a posterior currently held in-conversation and lost at compaction).

**The missing piece is the update protocol.** Records are written once. Nothing increments or
revises an existing belief when new evidence arrives — no "confirmed again (n=7)", no
"disconfirmed, supersede". The supersede chain does versioning for content; nothing does it for
**confidence**. A Bayesian machine needs belief records carrying `n_confirmations`,
`n_disconfirmations`, `last_updated`, `posterior_confidence` — updated by the wave outcome
signal (the adversarial verdict is the outcome signal; merge/no-merge is the payoff).

## The game-theory layer

This is an iterated game. Players: the controller (human), the AIO (delegated agent), and the
machine (waves, adversaries, gates). If it is a game, the KB needs game records:

- **The move**: spec authored → wave run → adversary verdict → merge / defer / park.
- **The payoff**: knowledge gained, cost, trust, time — measured.
- **The strategy ledger**: which shapes of moves win — big waves vs. small, opt-in vs.
  default-on, smoke-first vs. code-first.

The second-order question then becomes answerable: *what move should I make next given the
game history?* That requires the scoreboard to exist first.

## The record types (the wishlist, consolidated)

1. **Session records** — the spine. Open: retrieve the last session's close (decisions, open
   threads, parked items). Close: write this session's (what ran, what merged, what parked,
   what the AIO got wrong).
2. **Decision records with rationale** — "we chose X because Y". Parked fleet, flash-over-sonnet,
   the AIO name: each is a decision the next session must not re-litigate.
3. **Belief records with the update protocol** — hypotheses with n_confirm / n_disconfirm,
   updated by wave outcomes. The Bayesian engine.
4. **The controller model** — learned preferences: catches lies over green, values honest
   status, chose cost-efficiency, values the adversarial process. Retrievable preferences, not
   re-learned on correction.
5. **The game scoreboard** — wave count, merge rate, adversarial-finding rate, cost/wave,
   time-to-merge, false-positive incidents. The frequentist base.
6. **Reflection records** — a standing series each session appends to ("what I got wrong, what
   surprised me, what I'd change about my own process"); multi-session contemplation is their
   accumulation.
7. **Failure taxonomy with signatures** — the recurring classes (false-green gates,
   self-modifying runs, unwired seams, surface-sync drift) indexed so the AIO pre-detects
   rather than re-diagnoses.
8. **The associative layer activated** — the graph leg populated (currently `graph_paths: 0`).

## Producers (always-on, not opt-in)

The k1 lesson from `kb_finding_layer`: findings were opt-in and never produced. Loop 2 makes
the same mistake unless its producers are default-on:

- The session spine (open + close) — the AIO's operating cadence emits it.
- Wave verdicts — the run completion emits a narrative record (verdict, cost, adversary
  findings, merge state) — the "what happened and why" the AIO currently re-derives.
- Decisions — the verified-command wrappers (promote, publish) emit the decision + rationale.
- Belief updates — each wave outcome updates the hypotheses it bears on.
- Scoreboard rows — each completed wave appends its measured row.
- Reflections — the AIO session appends at close.

## Success criterion

Loop 2 is working when the next session is **strictly better than the last** because it
retrieves its own accumulated posterior — session history, decisions, beliefs, scoreboard,
reflections — instead of starting from the doctrine alone and re-deriving everything by grep.
The AIO becomes continuous across sessions rather than amnesiac between them.
