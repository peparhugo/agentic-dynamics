---
status: accepted
kind: adversarial
spec: control_room_design_determination
phase: adversarial
targets:
  - docs/website/control_room_ui/design_brief.md
  - docs/website/control_room_ui/design_candidates.md
  - docs/website/control_room_ui/design_evaluation.md
generated_at: 2026-09-14T02:10:00Z
---

# Control Room design determination — adversarial review of the evaluation and the winner

Target: the determination chain `design_brief.md` (d1, criteria), `design_candidates.md` (d2,
directions), `design_evaluation.md` (d3, winner = Candidate 1 "The Scroll-Synthesized Instrument",
4.72/5). Method: re-derive every load-bearing `[M]` citation from the tree at `HEAD` (`15b647042`)
and from the pinned commits; attack the criteria, the evidence, the winner, and feasibility. No
praise; each finding states the flawed claim, the required correction, and the acceptance that
proves it. All hashes below were recomputed in this worktree, not quoted.

## Summary (severity-ranked)

| # | Sev | Finding | Contract broken |
|---|---|---|---|
| A-1 | high | The parity inventory is byte-anchored to `349f06753`, not the declared `1457b9299` | C7, C8 evidence base |
| A-2 | high | `queue_wait`/`service_time` are already served; the winner's C4/C7 rest on a route that does not exist | C4, C7, D2 |
| A-3 | high | "Step durations" already exist at `HEAD`; the brief's central gap is mis-stated | C3, C4, D2 |
| A-4 | high | The scroll "conflict" is broader than admitted; the shipped render gate forbids page scroll | D1, C7, No-regression |
| A-5 | high | d1 pre-committed the winner; two `status: accepted` determinations disagree | process validity |
| A-6 | high | The weight/sensitivity analysis cannot falsify the winner; the brief's own elements score zero separation | C1–C8 weighting |
| A-7 | medium | C3's "all three tie at 5" is false: Candidate 3 omits the failure chart | C3 |
| A-8 | medium | C8 "fidelity to the old dashboard" actually measures conformance to the facelift palette | C8 |
| A-9 | medium | The winner's headline chart mechanisms are v2-only, unpaired to any direction anchor | D6, EV-9 |
| A-10 | medium | C7=5 hides the new route's ledger enumeration and absent `queue_timings.jsonl` | C7, D2 |
| A-11 | medium | The old room's 57 mutating control ids are dropped and not placed by the winner | C8, Authority |
| A-12 | low | The "old dashboard" rejection is misquoted and was a superseded work order | C8 premise |
| A-13 | low | Route counts are unreproducible and internally unreconciled (47/44 vs 34/36) | C7 basis |

---

## A-1 — high — The parity inventory is anchored to a commit the determination never names

**Flawed claim.** Every phase pins the parity reference to the old dashboard at `1457b9299` and
calls it "verified": `design_brief.md` §0/§1.8/appendix, `design_candidates.md` §1.1/appendix,
`design_evaluation.md` appendix ("235 unique ids, 44 route registrations, 34 canonical endpoints
(`parity_inventory.json` `[M]`; verified)").

**Evidence.** `experiments/research/control_room/parity_inventory.json` records `old_ref: "main"`
(symbolic; no commit) and `inputs.old_index.sha256 =
e26d36a3886c362b77f21826181a81437bb62181081b2cde2aa514cf0eb67064`. That digest is byte-identical
to `git show 349f06753:apps/control_room/static/index.html` (802 lines; confirmed by recomputation),
and is **not** the digest of `1457b9299:apps/control_room/static/index.html`
(`c5742a9860dd0e803223df89a0b141fc8153d772270591c80be7e744ff741a75`, 847 lines). Same-style
`id="…"` extraction yields 235 unique ids on `349f06753` and 247 on `1457b9299`; `main` gained 12
unique ids between the two commits. The determination's "847-line index.html, 235 unique ids" is a
chimera of the later file's length and the earlier file's inventory. `349f06753` is an ancestor of
`HEAD`; the inventory was built during `control_room_ux_repair`/`u2_parity_inventory`, i.e. against a
Sep-1 `main`, and was never re-derived when the docs pinned the old room to `1457b9299`.

**Required correction.** Re-derive the parity inventory against the commit the docs actually name
(or re-pin the docs to `349f06753`), record that commit's SHA in `old_ref`, and re-state the
235/214/20/1 and `routes_dropped: 0` figures for the chosen anchor. C7 and C8 may not cite a
"verified" inventory that resolves to a different tree than the declared old dashboard.

**Acceptance.** `parity_inventory.inputs.old_index.sha256 == sha256(git show <declared-anchor>:apps/control_room/static/index.html)`
for the commit named in the prose, and the id count in the prose equals the count extracted from
that same commit.

---

## A-2 — high — `queue_wait`/`service_time` are already served; the winner's workforce score rides a route that does not exist

**Flawed claim.** `design_evaluation.md` EV-3/D2 and `design_candidates.md` §1.4 assert that
`queue_wait_ms`/`service_time_ms`/`first_token_at` "reach no route", so the winner must add "one
read-only exposure" and is scored C4=5 ("sourced from measured fields") and C7=5 on that basis.

**Evidence.** `_completions_block` in `src/agentic_dynamics/control/projections/sla_queue.py:166-200`
already builds per-settled-job rows carrying `model`, `enqueued_at`, `started_at`, `ended_at`,
`queue_wait_ms`, `service_time_ms`, `due_at`, `deadline_slack_ms`, served by `GET /api/queue/sla`
(`apps/control_room/routes/analytics.py:40`). The docs themselves list this route
(`design_brief.md` §1.4/§3.1; `design_candidates.md` §1.4). Per-model p50/p95 queue-wait and
service-time is therefore computable from an endpoint that exists at `HEAD`; the only timing fields
with no carrier are `first_token_at` and the `cost_inference`/`cost_orchestration` split. The winner
is nevertheless scored 5 on C4 and C7 while its defining workforce data is not reachable at the
scored revision (EV-3 admits "False as stated" and leaves the 5).

**Required correction.** Partition the signals by actual carrier — DB-derived step durations,
`/api/queue/sla`-derived queue/service, ledger-only first-token and cost split — and score C4/C7
against what is reachable now. The new route is justified only for the signals with no existing
carrier; it is not "one required read-only addition" for the whole workforce band.

**Acceptance.** A fixture that renders the per-model queue-wait/service distributions from endpoints
that exist at `HEAD`, with no new route, shows measured values; the new-route justification names
only `first_token_at` and the cost split.

---

## A-3 — high — "Step durations" need no new exposure; the brief's central gap is mis-stated

**Flawed claim.** `design_brief.md` §0 executive summary: "workforce and step durations require
exposing already-measured ledger fields (G-40 timings, G-41 cost split) through a read-only route."
`design_evaluation.md` EV-3/D2 repeats it and lists `started_at`/`ended_at`/duration among the
fields D2 will newly expose.

**Evidence.** The control DB `step_attempts` table carries `started_at` and `ended_at`
(`src/agentic_dynamics/control/control_db.py:959-976`), and `run_detail`
(`apps/control_room/services/operations.py:78-97`) returns `attempts` via `dataclasses.asdict`
through `GET /api/runs/<run_id>`. Per-attempt step/phase duration (`ended_at − started_at`) is
therefore available at `HEAD` with zero new code. The brief element is "step durations"; the
determination conflates it with queue-wait/service-time/first-token, inflating the required
exposure and mis-scoring the feasibility of the one element the old dashboard demonstrably lacked.

**Required correction.** State that measured per-attempt durations are reachable today through
`/api/runs/<run_id>`; drop `started_at`/`ended_at`/duration from D2's field list and reserve D2 for
first-token latency and the cost split.

**Acceptance.** An `/api/runs/<run_id>` fixture at `HEAD` shows a non-null per-attempt duration; D2's
enumerated fields contain no field already served by that route.

---

## A-4 — high — The scroll "conflict" is broader than admitted, and the shipped render gate forbids page scroll

**Flawed claim.** `design_evaluation.md` EV-1/D1: direction §18 acceptance criterion 2 is "a
resting-screen / first-viewport contract … not a whole-document ban," so admitting page scroll is a
clarification ("the intended reading"), and C7=5 / No-regression are unaffected.

**Evidence.** The accepted IA fixes the stronger rule: "the resting screen shows all seven
`ON-G1..G7` answers above the fold with **no page scroll**, no region scroll, and no navigation"
(`docs/research/control_room_ia.md:34`); "no scrolling of the page or of any required region"
(`:41-42`); and the mechanical check is "the page does not scroll, and the region's own
`scrollHeight ≤ clientHeight`" (`:331-332`). The shipped gate enforces it: the chart probe fails
`chart-page-scroll` when `scrollHeight > innerHeight + 1`
(`scripts/verify_control_room_rendering.py:984`), and the page-scroll geometry is captured at
`:568-571`. D1 cites only direction §18.2 and never IA §4/§10 or the gate it invalidates.

**Required correction.** Present D1 as an amendment to IA §4/§10 (and to the gate), not a
clarification of §18.2; name the invalidated assertions (`chart-page-scroll`, the page-height
geometry check) and price the gate rewrite in C7 and the No-regression acceptance.

**Acceptance.** The design is accompanied by a diff to `control_room_ia.md` §4/§10 and to
`verify_control_room_rendering.py`'s page-scroll assertion; C7 cannot score 5 until that diff exists.

---

## A-5 — high — The evidence phase pre-committed the winner; two "accepted" determinations disagree

**Flawed claim.** `design_evaluation.md` §1.1: "re-weighting after seeing the scores would be a
process violation, so the weights are held fixed," implying an independent evaluation.

**Evidence.** `design_brief.md` (d1, `status: accepted`) Part IV already selects "Candidate C" at
**4.48**; `design_evaluation.md` (d3, `status: accepted`) selects Candidate 1 at **4.72**.
`design_candidates.md` §2.0 states Candidate 1 "is the direction the d1 brief's Candidate C pointed
at." The same design moved scores between phases with no new evidence: C1 legibility 4→5, C7
feasibility 4→5. Both files carry `status: accepted`, so the repository's accepted record contains
two winners and two scores for the same design. The criteria and weights were fixed in the same
document that already declared the winner.

**Required correction.** Collapse to one accepted determination (supersede the other), and for every
score that changed between d1 and d3 cite the new anchor that justified it — not a re-reading. If
the d2 directions are meant to be an independent menu, they must be scored by an evaluation that did
not pre-select one of them.

**Acceptance.** Exactly one `status: accepted` determination names one winner and one score vector;
the score deltas from d1's Candidate C to d3's Candidate 1 are each justified by a new `file:line`
or hash.

---

## A-6 — high — The weight and sensitivity analysis cannot falsify the winner

**Flawed claim.** `design_evaluation.md` §4: "The ordering `C1 > C2 > C3` is stable under single-axis
perturbations"; the one joint re-scoring that reverses it (C2 best 4.61 vs C1 worst 4.44) is
dismissed as "incoherent."

**Evidence.** §4 perturbs only **scores**, never **weights**, and gives no falsification threshold.
The outcome is carried by arrangement/navigation criteria — C1 legibility / C5 scroll / C7
feasibility / C8 fidelity = 46 of 100 points — where the winner is scored by assertion. The brief's
named elements score **zero separation**: §2 records C3 (charts) as "all three tie at 5" and C4
(workforce) as "tie C1/C3". So charts, workforce, and step-durations — three of the five brief
elements — do not distinguish the winner at all; the third (scroll) is C5, a navigation criterion.
The joint-case dismissal is an argument that the three C2 upgrades share one mechanism; it is not a
computation, and it is the only case that reverses the order.

**Required correction.** Run a weight-perturbation sweep with a stated decision rule (e.g. "the
winner must hold under ±X points on every criterion weight"), and either score the brief's elements
differentially or state explicitly that the brief's elements do not decide the winner.

**Acceptance.** A weight-sweep table reporting the reweight at which the ordering flips and the
rule used to accept or reject the winner under it.

---

## A-7 — medium — C3's tie is miscounted: Candidate 3 omits the failure chart

**Flawed claim.** `design_evaluation.md` §3 C3: "The same set plus retry-rate / tokens-by-model …
Criterion winner: all three tie at 5."

**Evidence.** `design_candidates.md` §4.3 (Candidate 3's chart table) lists step/phase duration,
queue timing, first-token, retry-rate/tokens, cost/burn, provider window, throughput, phase
waterfall + mini-map, and dependency health — **no failure chart**. Candidate 1 (§2.3) and
Candidate 2 (§3.3) both carry `failure`. Candidate 3 cannot tie on chart coverage while lacking one
of the four charts the current catalog already ships (`charts.js:39-76`).

**Required correction.** Score C3 on the charts each candidate actually enumerates (C3 lacks
failure), or add the missing chart to Candidate 3 and re-score.

**Acceptance.** A per-candidate chart inventory diffed against the C3 scoring row; each candidate's
score reflects only its own list.

---

## A-8 — medium — C8 "fidelity to the old dashboard" measures the facelift's own palette

**Flawed claim.** `design_evaluation.md` §3 C8: C1 scores 5 because "every old id maps to a fixed
band home by its inventory `surface`."

**Evidence.** The inventory's `surface` field is the **new closed palette** (`R0`, `R1`, `L-SESSIONS`,
`L-REGISTRY`, …), generated by the `control_room_ux_repair` campaign (`phase: u2_parity_inventory`;
`old_ref: "main"`), and eight palette surfaces have **no** old item
(`summary.surfaces_without_old_item`: `L-COMPOSITION`, `L-FLEET`, `L-HEALTH`, `L-WORKFORCE`, `R3c`,
`R4c`, `R4d`, `SYSTEM`). So "old ids map to bands by their inventory surface" restates the facelift's
re-housing; it does not show that the old dashboard's own affordances survive. The inventory is also
internally inconsistent: `sum(summary.surface_counts) = 269` while `len(items) = 235` (recomputed).

**Required correction.** State the fidelity unit as the IA §14 palette explicitly (not "the old
dashboard"), fix the summary/items count mismatch, and run the class-P gate on the palette. C8's
pass condition must name the palette.

**Acceptance.** `sum(summary.surface_counts) == len(items)`; the C8 pass condition cites
`control_room_ia.md` §14, and the score is labelled palette-conformance, not old-dashboard fidelity.

---

## A-9 — medium — The winner's headline chart mechanisms are v2-only, unpaired to the direction

**Flawed claim.** `design_evaluation.md` D6/EV-9: "Every v2 mechanism the design adopts must cite a
direction basis; a mechanism that exists only in v2 is dropped." The same document scores the
winner's charts 5.

**Evidence.** Candidate 1's chart forms are the v2-only `O6` "log-scale duration bar with explicit
`UNKNOWN` height" and `HT3` "shared-axis span bars" (`design_candidates.md` §1.5/§2.3), cited to
`openhands`/`hatchet` anchors, not to direction §7/§10. v2 is `status: proposed`, 479 lines, on
`wt_facelift_review`, not on `main` (confirmed). The candidates doc does not pair any adopted v2 ID
to a direction anchor; D6's acceptance ("each adopted v2 mechanism ID is paired with a direction
anchor") is asserted, not demonstrated.

**Required correction.** Pair each v2 ID the winner uses with a direction § anchor, or drop it; the
pairing belongs in the determination, not in an assurance.

**Acceptance.** A table mapping every v2 mechanism ID in the winner's chart/workforce plan to a
direction section, with the dropped list enumerated.

---

## A-10 — medium — C7=5 hides the read route's aggregation cost and an absent data file

**Flawed claim.** `design_evaluation.md` §3 C7: C1=5, "the only server change is the single shared
read-only timing route … the cheapest of the three to build and gate."

**Evidence.** D2's aggregate mode (`GET /api/timings?aggregate=1&window=<n>`) reads the per-run
workflow ledger under `experiments/results/workflows/<spec>/<ts>_<run_id>.json`
(`scripts/run_workflow.py:1287-1301`) and `experiments/results/queue_timings.jsonl`
(`src/agentic_dynamics/runtime/queue_timings.py:34`). Enumerating all spec directories and parsing
every ledger on request (or maintaining an index) is a new read model, and mapping a control
`run_id` to a ledger filename requires a glob; `queue_timings.jsonl` is absent in this checkout and
is created only at runtime. None of this is anchored, and the document disposes of the criterion
definition by asserting "a new read registration is not a new class."

**Required correction.** Specify the enumeration/index, the `run_id`→file mapping, the refresh rule,
and the empty-state when `queue_timings.jsonl` does not exist; score C7 against that specification
rather than against an adjective.

**Acceptance.** A measured request-time fixture over N ledgers plus a stated response when the
timings file is missing; the C7 score cites that fixture.

---

## A-11 — medium — The old room's mutating controls are dropped and not placed by the winner

**Flawed claim.** `design_evaluation.md` §3 C8: C1=5, "every old id maps to a fixed band home"; the
Authority gate claims "every irreversible act behind its existing typed door."

**Evidence.** The inventory's capabilities record the mutating control families — `supervisor-controls`
(11 members), `claude-agent-controls` (16), `cell-panel` (11), `queue-controls` (7),
`design-controls` (12) — each with `facelift_members_dropped` equal to its full member set. Candidate
1's band table (`design_candidates.md` §2.2) mentions "owned actions"/"governed actions" generically
and enumerates none of watch/detach, pause/resume, steer, interrupt, docs-health approve, queue
clear, or daemon stop. C8=5 is asserted and the class-P gate it depends on does not exist.

**Required correction.** Map every mutating control id to its band/dock home and its typed door
before C8 can be scored; the placement table is the fidelity evidence, not the assertion.

**Acceptance.** A per-id placement table covering the mutating control members, exercised by the
class-P gate.

---

## A-12 — low — The "old dashboard" rejection is misquoted and was a superseded work order

**Flawed claim.** `design_brief.md` AD-3 and `design_candidates.md` §1.1 paraphrase
`workflows/repository/control_room_ui_rebuild.yaml:24-29` as "a layer on top of the clunk" and treat
it as the repository's only literal "old dashboard" policy.

**Evidence.** The file says "a layer of shit on top of the dashboard," and it is a `why_rebuild`
rationale inside a pre-facelift work order whose `authority` points at
`docs/control_room_ui/design.md`. It is not the controller's current brief; `design_brief.md` §4.1
itself admits "a repo-wide search found no document containing this phrase list verbatim." The
"working-set fidelity, not DOM reuse" reading is therefore an inference, and it is simultaneously
used as a settled premise for C8 and listed as an open controller decision (§6.4).

**Required correction.** Quote the source exactly, mark the reading as an open controller decision
(it already is in §6.4), and stop using a superseded work order's rationale as the premise of C8.

**Acceptance.** The exact quote appears with its commit/context, and the C8 rationale cites the open
decision rather than the rejection.

---

## A-13 — low — Route counts are unreproducible and unreconciled

**Flawed claim.** `design_evaluation.md` §3 C7 and appendix: "**47 route registrations at `HEAD`**,
**44 at `1457b9299`**, `routes_dropped: 0` … re-measured here `[M]`."

**Evidence.** `47` reproduces exactly (30 `GET` + 17 `POST`, the 47th being the static
`GET /`; `apps/control_room/routes/*.py`). But the same documents use `parity_inventory`'s
`old_routes: 34` / `facelift_routes: 36` / `routes_dropped: 0`, and no command or script is named
for the 47/44 measurement. The C7 pass condition ("no new endpoint class") is applied to a total
that includes a non-API static route, while the parity figure counts a different set.

**Required correction.** Name the counting command and scope (API endpoints vs all registrations),
reconcile 47/44 with 34/36, and exclude the static `/` route from the C7 endpoint count.

**Acceptance.** A one-line reproducible count whose printed total equals the number used in C7, and
one reconciled table of 47/44/36/34.

---

## What would falsify the winner

The determination names no test that could reject Candidate 1. Three exist and were not run:
(A) re-score after re-deriving the parity inventory at the declared old anchor (A-1);
(B) render the workforce band from endpoints that exist at `HEAD` (A-2/A-3) — if it is already
possible, C4/C7's gap narrative collapses; (C) run the weight sweep in A-6 — if the ordering flips
under a plausible reweight, the winner is an artifact of the weights. Until at least one of these is
executed, the 4.72 is a preference expressed as arithmetic.
