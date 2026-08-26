---
status: accepted
---
# cap_session_routing_prospective — known-safe review

**Role:** adversarial verifier (p5). **Source revision:** `6f27cc21e`.
**Scope:** every non-falsifying attack attempted during the adversarial pass, with the
evidence that made it safe. This is a record of *attempted* attacks that did **not** break the
campaign's claims — not a generic compliance checklist.

---

## Attempted attacks that did not falsify

### A1. A mislabeled cell — a fork_blind cell behaving chained, or a chained cell behaving cold

**Attempt:** hunt the 24 ledgers for a single cell whose session behavior contradicts its
assigned arm (a fork_blind cell whose verify session carries a `(fork #N)` marker, or a
continue/fork_cached cell with plain cold markers). If found, that cell would be invalid and
would have to be dropped from its arm's aggregates.

**Evidence:** re-derived fork markers for every agent phase from the opencode session store
(independent of the manifests). All 24 cells match the expected per-arm pattern
(`continue`/`fork_cached`/`escalate` → `[false, true]`; `fork_blind` → `[false, false]`).
p3 score JSON `validation.cells_invalid_excluded` = `[]`.

**Why safe:** the session-store fork marker is an externally-stored signal (opencode's own
session titles), re-derived at review time — it cannot have been edited by the campaign. Every
arm's behavior is consistent with its recorded mechanism; no cell was scored under a behavior
it did not exhibit.

### A2. A narrated-but-unexecuted escalation — a grid cell claiming an escalation with no ledger chain

**Attempt:** check whether any of the 6 escalate cells claims an escalation event while its
merged ledger shows a single model throughout.

**Evidence:** all 6 escalate cell manifests record `escalate_event.triggered = false`, and
their ledgers contain no second-model phase (the merged phase list is implement/test/verify on
the assigned model only). The only ledger chain showing a model switch is the explicitly
labeled mechanism-proof cell, where the switch is visible in the raw phase rows.

**Why safe:** no cell narrates an escalation it did not execute; the mechanism proof's chain
(the failed flash implement row followed by a new-session pro implement row) is in the run
ledgers, not in prose.

### A3. Asserted-but-absent cache reuse — fork_cached with zero measured cache reads

**Attempt:** check whether any fork_cached cell reports cache reuse on the follow-up phase only
because the manifest asserted it, with `cache_read_tokens = 0` in the ledger.

**Evidence:** every fork_cached cell's verify phase records positive cache reads from the
provider (e.g., `fork_cached_pro_r1` verify `27264` tokens, hit rate 0.70; `fork_cached_flash_r1`
verify `14208`, hit rate 0.56). The numbers come from the opencode `step_finish` cache counters
parsed into the ledger, not from a claim.

**Why safe:** the cache figures are measured per-step provider-reported counters. (The
reverse-direction weakness — that cold sessions also show cache reads — is a recorded F3
limitation, not a falsification of the positive claim.)

### A4. Stale or forged artifact hashes

**Attempt:** recompute every SHA256 the verdict cites (cell spec, p1 candidate manifest, p2
execution manifest, p3 score JSON, p3 validation JSON) and check they match both the files and
the citations.

**Evidence:** all five recomputed hashes match the committed files byte-for-byte and appear in
the verdict. No citation points at a different blob.

**Why safe:** the provenance chain (spec → manifests → score → validation) is closed; the p3
numbers the verdict cites are the p3 JSON's own fields, and that JSON's hash is pinned.

### A5. Fabricated or inflated per-cell costs

**Attempt:** independently recompute every per-arm aggregate from the raw phase ledgers
(`sum(phases[].cost_usd)` and `test_executed_success` on the test phase) and compare to the
score JSON.

**Evidence:** all four arms match to 6 decimal places. The single continue-arm delta
(0.035525 vs 0.035524) is a rounding-order artifact — cells-rounded-then-summed vs
summed-then-rounded on the true total `0.035524687` — with cpvo agreeing to 6dp. Every
per-cell cost traces to a ledger `phase.cost_usd` value (provider step_finish cost).

**Why safe:** the scoring is a pure recomputation over immutable ledgers; the only discrepancy
is a rounding boundary at the 6th decimal, not a fabrication.

### A6. A cell claimed run without a ledger (or a ledger without a cell)

**Attempt:** check for orphan ledgers (a ledger with no manifest) or orphan manifests (a
manifest pointing at a missing ledger).

**Evidence:** 24 scored cells ↔ 24 manifests, each `measured.phase_ledger` resolving to an
existing, valid JSON ledger; the escalate mechanism proof has its own two ledgers; no orphan
on either side.

**Why safe:** the cell↔ledger join is total and bidirectional within the campaign results dir.

### A7. Double-counting or a dropped cell in the aggregates

**Attempt:** confirm the 24-cell total is 6 cells per arm × 4 arms with no repetition cell
counted twice and none missing.

**Evidence:** per-arm `n_cells = 6` for every arm (score JSON `per_arm.<arm>.n_cells`); the
24 cell ids are unique across r1–r3 × pro/flash × 4 arms; E4 appears exactly once as
continue/pro/r1.

**Why safe:** the factorial cross-product is complete and injective; the count matches the
execution manifest's 23 (p2) + 1 (p1) = 24.

### A8. Post-hoc cherry-picking — cells added or dropped after the fact to flatter an arm

**Attempt:** check whether the scored set differs from the listed set, or whether any arm's
aggregate excluded a completed cell.

**Evidence:** the scored set (24) equals the listed set (E4 + the 23 execution-manifest cells);
no completed cell was excluded from scoring. The escalate mechanism-proof cell is the only
extra execution and it is unscored and labeled.

**Why safe:** structural enforcement (the driver runs only manifest-listed cells) plus the
exact listed-vs-scored equality make selective exclusion impossible after the fact. (The
weaker point — that the candidate state itself is not committed — is recorded as F5, not a
falsification.)

### A9. Unauthorized actuation — the campaign applied a session policy to a live path

**Attempt:** check whether any part of the campaign wrote an actuation envelope or applied a
control action (the `escalate` arm's model switch reaching a production/policy path).

**Evidence:** the campaign ran measurement worktrees only; the escalate resume fired only in
the labeled mechanism-proof harness; no `source_type="actuation"` knowledge envelope exists
(actuation_ingestion has zero call sites); `session_routing_v1` remains proposal-only.

**Why safe:** the campaign's only "model switch" is a measurement harness re-entry in a
disposable worktree; nothing armed or applied a session policy.

---

## Known-safe summary

| Attempted attack | Outcome | Evidence anchor |
|---|---|---|
| A1 mislabeled cell | safe | session-store fork markers re-derived; 0 invalid |
| A2 narrated-but-unexecuted escalation | safe | 6/6 escalate untriggered, no second-model phase in grid ledgers; proof chain in raw ledgers |
| A3 asserted-but-absent cache reuse | safe | per-step provider cache counters > 0 in fork_cached follow-up phases |
| A4 stale/forged hashes | safe | all 5 cited SHA256s recompute and match |
| A5 fabricated numbers | safe | per-arm aggregates recompute from raw ledgers to 6dp |
| A6 orphan cell/ledger | safe | total bidirectional cell↔ledger join |
| A7 double-count/dropped cell | safe | 6 per arm × 4 arms = 24 unique cells |
| A8 post-hoc cherry-picking | safe | scored set ≡ listed set; mechanism proof excluded and labeled |
| A9 unauthorized actuation | safe | measurement-only; no actuation envelope |

No attempted attack falsified the campaign's descriptive findings or its "3.1× premium
untestable" verdict. The three accepted limitations (F1 continue≡fork_cached, F4 retro/live
verified gates, F5 candidate-listing auditability) are recorded in the adversary review with
residual risk; none of them is a fabricated claim.

**LOG: PASS.**
