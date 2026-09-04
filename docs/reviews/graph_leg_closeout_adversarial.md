---
status: accepted
kind: review
spec: graph_leg_closeout
phase: g9_adversarial
run: run-57b8ec179e30
generated_at: 2026-09-04T03:55:00Z
---

# graph_leg_closeout — adversarial review (g9)

**Independent falsification** of the graph-leg close-out, run in a DIFFERENT session/model (pro)
than the flash author. Nothing here is asserted — every claim below was re-derived against the
actual code at the branch HEAD and the live graph at probe time (2026-09-04). The review
attacked the three threads + the leak surface in order; a "bare PASS" would be a failed review,
so findings (accepted limitations with reasoning) are surfaced even where the threads are
honestly closed.

Branch under review: `feature/graph-leg-closeout`, HEAD `dad1b5e48` (p0 → a1 → c1 → b1 → b2 →
a2 → c2 → c3). Live state: kb-neo4j-v1 consumer caught up (lag 0); the ONE real
`PRODUCED_BY` edge from c3 present in the store; throwaway a2 unit removed.

## 1. IDLE-EXIT (Thread 1) — VERIFIED CLOSED

- **`--once` exits 0 after one batch**: ran `python3 scripts/kb_worker.py --group
  kb-registry-v1 --consumer g9-once-probe --once` (isolated `FINOPS_CONTROL_DB`) → one batch
  (`processed=0`, a quiet group), `Done. processed=0`, **exit 0**. The `--once` break fires
  after its single poll; no idle-exit path is reachable.
- **Daemon survives 12+ empty polls**: `tests/test_kb_worker.py::test_daemon_mode_never_idle_exits_after_empty_polls`
  (bounded real `_poll_loop` run past the OLD 12-poll threshold) + both `--once` tests pass
  (`3 passed`). The `_poll_loop` has no idle-exit (the removal at `e6409b07b`); the loop's only
  exits are the `--once` break and an uncaught operator signal.
- **a2 evidence honest**: `systemctl --user list-unit-files 'agentic-dynamics-kb-idletest*'` →
  `0 unit files listed` (the throwaway unit is gone); the three live units are
  `Restart=always` + `active` (unchanged — the documented live-op mitigation was never edited);
  `infrastructure_kb-neo4j_1 Up 2 hours` (untouched); no `kb-idletest-a2` process remains. The
  a2 evidence's "5.5 min idle, 0 restarts, same PID" is consistent with the observed teardown.

## 2. EXPANSION (Thread 2) — VERIFIED CLOSED (with F1/F2 below)

- **Allowlist == writers ∪ claims**: grepped every remaining allowlisted rel for a writer —
  `DEFINES` (graph.py:996), `IMPORTS` (:800 legacy + :1013 versioned), `CALLS` (:1028),
  `TESTED_BY` (:1052), `SUPERSEDES` (:1123 + kb_worker:471), `CONTAINS` (:960/:995),
  `PRODUCED_BY` (graph.py:863 — the c2 writer). `CONTRADICTS`/`PRECEDES` have no writer and are
  pruned. This is exactly the c1 claim + the live writers.
- **Live expansion is warning-free**: re-ran the post-b1 7-rel union query over a code seed —
  **0 server notifications** (the b2 residual `UnknownRelationshipTypeWarning` for PRODUCED_BY
  is gone now that c3's real edge created the rel-type token). The neo4j per-query warning
  noise the thread existed to kill is gone.

## 3. ASSOCIATIVE (Thread 3) — VERIFIED CLOSED (with F3/F4 below)

- **c2 writer really writes the edge on a real record**: `spec:admission_leases` ↔ finding
  `bf82d637…` — exactly one `PRODUCED_BY` edge in the live store (re-queried). The replayed
  record's `knowledge_id` matches its registry id (a true replay, not a fabrication).
- **Idempotent on replay**: replayed the record through `merge_wave_finding_produced_by`
  twice → `edge_merged` both times, edge count **stays 1**.
- **Graph-write failure degrades**: `tests/test_assoc_edge_writer.py` (4 passed) — a raising
  client → the emit path returns `skipped`, logs `[warn] assoc edge skipped`, and the durable
  artifact + registry row still land (`emit_record` returns `new`). Best-effort holds.

## 4. LEAK CHECK — no cross-tenancy leak; authority direction is clean

Probed with exact-scope vs broad retrieval over the live edge:

| Reader scope | Finding→spec crossing |
|---|---|
| `wave:admission_leases` / `wave:admission_leases` (the finding's own tenancy) | **0** (spec does not cross — fail-closed) |
| `agentic-dynamics` / `public` (the spec's tenancy, seeded from the spec) | **0** (finding does not cross back) |
| broad / empty (legacy-only path) | **1** — reaches `spec:admission_leases` (the intended path) |

Authority direction is clean: the source is `authority=DERIVED, [C]` (a deterministic wave
conclusion) and the target is `authority=POLICY` (the spec) — a derived record CITING its policy
source, never the reverse, and never a fabricated authority. The writer writes the source node
with the RECORD's own tenancy (`wave:<spec>`), not a lifted org scope. No k1-style opt-in
regression: the c2 writer is default-on in `emit_record` (fires on every new wave-conclusion
emit); nothing retrieval-side was touched.

## Finding table

| # | Severity | Thread | Finding | Disposition |
|---|---|---|---|---|
| F1 | Low | Expansion | `AFFECTS` was pruned from the allowlist but its WRITER still exists — `populate_versioned_graph` MERGEs AFFECTS when fed `issues`/`diagnostics`. No call site feeds them (zero live edges), so the prune is sound today, but if Sonar/LSP wiring later feeds diagnostics, AFFECTS edges will appear that expansion cannot traverse. | **ACCEPTED** — dormant writer, zero edges, no feeder; the re-allowlist trigger is documented in the graph.py comment and the b1 frozen test. The spec hard rule ("a name may stay only if a writer exists") is permissive and did not require keeping AFFECTS. |
| F2 | Low | Expansion | `PRODUCED_BY` is now in `IMPACT_EXPANSION_RELS` (defined as `ALLOWED − SUPERSEDES`), yet a finding→spec edge is not an executor-impact/blast-radius edge. Impact traversal (`evidence_analyzer`) now emits a PRODUCED_BY rel pattern. | **ACCEPTED** — harmless: the impact traversal is over versioned `SymbolVersion`/`ModuleVersion` (scoped), and PRODUCED_BY edges connect unversioned Knowledge leaves, so the term never matches. A follow-on could narrow IMPACT to the true impact rels. |
| F3 | Med | Associative | The first-family edges are traversable ONLY under the broad/legacy path. The endpoints carry different tenancy (`wave:<spec>` vs `agentic-dynamics`/`public`), so an exact-scope org-root query — the likely production retrieval shape — cannot traverse finding→spec (verified fail-closed above). | **ACCEPTED** — c1 §4 documented this as the family's reachability caveat; the fix is a later org-scoped family (session/verdict records). Not a leak: fail-closed, never over-permissive. |
| F4 | Low | Associative | c1 §5.3 says the Knowledge-only leaf count "drops by 1" per replayed record; the c3 probe measured **Δ−2** for the first edge (BOTH endpoints were leaves — the finding AND the spec hub). The "1" is the per-further-record marginal once the hub is non-leaf. | **ACCEPTED** — c3's evidence is the authoritative measurement; c1 §5.3's "up to 66" remains a correct upper bound. (Optionally fix the c1 wording later; not load-bearing.) |
| F5 | Low | Guard | The b1 "writers ∪ claims" invariant is enforced by a HARDCODED frozen set + pruned-absent asserts, not a live grep for writers. A future writer for a pruned name (e.g. AFFECTS) would not trip the test unless someone edits the constant. | **ACCEPTED** — the frozen test does catch any manual re-addition of a dead name and any accidental prune of a live name; the live-grep depth is a possible later hardening, not a correctness gap. |

No FAIL findings — no thread is open on its own terms, and no live-op change went undocumented.

## Release verdict

**MERGE-READY.** Each of the three threads is honestly closed — Thread 1 by code (a1) +
supervisor evidence (a2), Thread 2 by the prune (b1) + live warning-free probe (b2), Thread 3 by
the design (c1) + writer (c2) + live probe (c3). The single live-graph write (c3's one real
`PRODUCED_BY` edge on `admission_leases`) and the a2 throwaway unit were both authorized,
documented, and the throwaway was removed; the three live systemd units (still `Restart=always`)
and the kb-neo4j container were never touched. The findings above are accepted limitations with
recorded reasoning, none of which invalidates the close-out. Gate suites green at review time:
`test_graph`, `test_versioned_graph`, `test_change_analyzer`, `test_retrieval`,
`test_assoc_edge_writer`, `test_kb_worker` — **205 passed**.
