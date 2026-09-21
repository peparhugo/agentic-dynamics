# Item 5 — broad vs forks: the rating package (AIO-prepared, 2026-09-21)

**Purpose.** The controller rates one broad analysis (arm A) against four focused forks + synthesis
(arm B) on the same evidence; the rating decides the fork policy. This brief assembles the three
named measures — *new validated findings · misleading recommendations · reading/rework time* — with
the verification the AIO performed on top of the arms. It is advisory; the rating is the
controller's.

## What ran

| arm | run | phases | cost | output | answer delivery |
|---|---|---|---|---|---|
| A (broad) | `run-62f5d3886939` (`item5_broad`) | 1 | $0.061662 | 14,159 chars | n/a (single phase) |
| B (forks+synthesis) | `run-7cf09daf2b34` (`item5_forks`) | 4 lenses + synthesis | $0.083764 | 58,774 chars | 4/4 complete (manifest) |

Both arms read the same four evidence files; both specs carry `budget_usd: 0.10`; neither arm
approached it. Cost ratio 1.36×; output ratio 4.2×.

## Measure 1 — new validated findings

**Convergent core (both arms, verified against the record):** the synthesis-input bound and its
correction; the verified delivery/emission repairs; "acceptance ≠ effect" as the arc's recurring
failure class; the retrieval gap and the audit's now-fired re-run trigger; the pilot as a ceiling
null; the loop's missing artifacts; the economics/attention bound.

**Arm B beyond arm A (checkable, and the AIO re-verified where noted):**

1. **The corpus-arithmetic catch** — the audit's category counts sum to **54,103**, not the stated
   54,286 (183-record gap; only the lifecycle totals reach 54,286). *Re-verified by hand: 54,103.*
2. **A nine-pair contradiction inventory** — including the emission-status contradiction (accepted
   record says "no KB emission today" vs emission verified end-to-end in the same package) and the
   "self-contained vs not carried by this branch" pair.
3. **Explicit D1 flagging** (is `final_response` persisted?). *Settled by the AIO against the
   checkout: it IS persisted — `runtime/workflow_runner.py:425`; the review's "to_dict omits it"
   described the pre-repair state. Both accepted docs were right about different moments.*
4. **A ranked option set with the disagreement preserved** — two lenses converged on the audit
   re-run, one on delivery-proof, one on the stale-next-action bounded fix; the synthesis ranked
   rather than averaged them.

**Arm A beyond arm B:** F8 (the broad pass must label its own window as a bound — and noting the
comparison was finally fair once `{prior_answers}` was repaired); the crisp A1–A5 acceptance
ladder for the audit re-run; the explicit "not next" list.

**Net:** the arms converge on the substance. B adds independently checkable catches and
disagreement visibility; A is denser per word.

## Measure 2 — misleading recommendations

On the AIO's read, **neither arm carries a materially wrong recommendation.** Two qualifications
the rating should absorb:

- Arm A's "the loop is not buildable yet / premature to build" was correct against its evidence
  but is now time-stale: v1→v1.2 were built and conformance-tested the same day (referenced by
  neither arm; the evidence files pre-date the build).
- Arm B's risks lens over-weights D1 as a blocker (it settles in one read) — but its underlying
  recommendation (make delivery provable: complete response + lineage labels) stands: the
  manifest still lacks lineage labels, so even arm B's synthesis cannot prove *which* complete
  texts it received.

## Measure 3 — reading / rework time

| | arm A | arm B |
|---|---|---|
| output | 14.2 KB ≈ 2.1k words | 59.1 KB ≈ 9.0k words |
| estimated read | ~9 min | ~36–40 min (4.2×) |
| re-read shape | one pass | 5 self-contained sections (~7–8 min each) |

No dedup was applied to arm B: each lens restates the convergent core. The attention cost is the
real price difference; the dollar difference is 2.1¢.

## Advisory rating (for the controller to accept or overturn)

- **For this corpus and this decision: arm A was the better value** — the same top-line findings,
  a quarter of the reading, no misleading recommendations, and an explicit self-bound.
- **Arm B earned its cost only where disagreement visibility and adversarial checking pay** — the
  arithmetic catch, the contradiction inventory, and the preserved option spread are products a
  single window did not produce. Those matter most when a missed contradiction is expensive.
- **Proposed fork policy v0** (subject to the controller's rating): default to the broad single
  pass; spend forks on demand — a high-stakes decision, or a question with a real option spread —
  and cap breadth (2–3 lenses) to bound the controller's attention; keep the delivery manifest
  requirement for any synthesis.

## The one scheduling outcome both arms demand

**Re-run the standing retrieval audit now.** Its own trigger has fired (all 20 `emit_self` opt-outs
were flipped), and nothing yet measures whether the newly emitted analysis is actually retrievable.
Both arms independently rank it the cheapest decisive move — and the negative result it can return
("emission alone did not fix retrieval") has a defined stop: do not build retrieval-dependent
plans on an unverified corpus. *Status note: the AIO ran this re-audit on 2026-09-21 in the same
session; see the session close / `docs/reviews/retrieval_audit.md` update.*
