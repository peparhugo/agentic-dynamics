---
status: accepted
---

# Fleet-ladder proposal — known-safe list (round 2 re-verify)

**Status: accepted · Date: 2026-08-29T19:05Z · Source: p1_reverify (round 2) of the
`fleet_ladder_revision` spec (spec_sha256 `0d30d4bc…`, escalated to deepseek-v4-pro).** The
attacks that did **not** falsify the **REVISED** proposal (`docs/fleet/00_proposal.md`, p0_revise
round 2). **REPLACES** the round-1 known-safe list — the 20 round-1 protections survive, and the
three operator-refinements (D-16/D-17/D-18) are added as newly-verified protections.

## The known-safe list

| # | attack | why it survived |
|---|---|---|
| KS-1 | The ladder topology (cell → orchestrator → supervisor) is complete | every p1 unit is placed; the data plane stays dockerized unchanged; the opencode server is classified operator-side |
| KS-2 | The guard **code** is never touched | the revision edits zero source files; the write guard, actuation-armed gate, lineage, and `scope_excluded` are placed, never modified; env is per-unit and per-tier (D-15) |
| KS-3 | G2 actuation-armed preserved | no tier and no scope ever sets `FINOPS_ACTUATION_ARMED`; zero actuation producers |
| KS-4 | G3 lineage preserved | code-side, untouched by placement |
| KS-5 | G4 registry append discipline | the kb-registry consumer remains the sole appender; producers write only via the stream |
| KS-6 | G5 scope (two-channel) | per-cell `self-<worktree>` / `FINOPS_CELL_ID`; orchestrator emit_self scoped; retrieval hard filter unchanged |
| KS-7 | The neo4j bridge is buildable from the proposal alone | tier/image/access/guards/supervision all specified, referencing the real handler `kb_worker.py:367-463` |
| KS-8 | The resurrected RRF leg | the read side is already live; slice 3's work is the supervised consumer + the `rag_augment` gate |
| KS-9 | No self-activation / master-control boundary | the proposal awaits sign-off; the supervisor is KB-read-only, holds no permanence power |
| KS-10 | The 4-wide grid shape | unchanged, now container-to-container |
| KS-11 | The migration rollbacks | story/analysis additive (BRPOP atomic); review sequenced cut-over; slice 4 read-only tests |
| KS-12 | The batch producers' write discipline | P7-P10 keep their in-code `FINOPS_KB_WRITE=1`-for-the-run convention inside the containers |
| KS-13 | The data-chain single-writer for the stores | per-store single consumers; registry compaction stays in `generate_manifest.py` |
| KS-14 | The queue isolation invariant | the ladder never touches 6379; framework queue on 6380, KB stream on db2, `fleet:commands` on 6380 db1 — **now structural (D-17: `fleet-net` does not attach 6379)** |
| KS-15 | The flag auto-clear write-back fires (was F-A2) | kb-registry consumer granted `FINOPS_KB_WRITE=1` (D-11); env gate + `authorized=True` both pass |
| KS-16 | The orchestrator env is unambiguous (was F-A7) | orchestrator never carries `FINOPS_KB_WRITE=1` (D-15); F-1/F-2/P11 authorize in code |
| KS-17 | The supervisor satisfies the mount contract (was F-A3) | D-13: configs → `repo ro`, logs → the `fleet-logs` named volume; no host path beyond the four + D-2 |
| KS-18 | The socket + watcher are specified (was F-A4) | D-14: static pools + read-only watcher + resize/drain via `fleet:commands` + spawn-wrapper validation |
| KS-19 | The host footprint holds (was F-A5) | D-9 reclassifies the opencode server + db operator-side; footprint of ours = the bootstrap unit only |
| KS-20 | The review migration is sequenced (was F-A6) | D-10: cut-over, never additive — no double-review window |
| KS-21 | The scope vocabulary is closed (new — D-16) | a five-scope enum; each scope = a declared config; the spawn-wrapper rejects any undeclared scope before the socket call |
| KS-22 | The spawn-wrapper's validation is complete (new — D-16) | five ordered checks (scope ∈ vocab → phase-authorized → mounts ⊆ declared → network = declared → env = declared); no spawn path past them |
| KS-23 | The network policy is structurally sound (new — D-17) | `fleet-net` membership (not a port convention) excludes the portal / opencode server / 6379 / host; the egress proxy is the single internet point |
| KS-24 | The binary attach is symlink-complete + fail-loud (new — D-18) | the image carries the generic toolchain only; the CLIs attach via the auth mounts (D-2 carries the symlink AND its target); the slice-4 binary-resolution probe fails loudly on a broken chain |
| KS-25 | The scope model preserves the mount contract (new — D-16) | every scope is a subset of the four categories + the D-2 auth set; the doc-writing scopes write into their worktree, never a fifth host path |

**The boundary of this list:** the seven p5 findings F-A1…F-A7 remain **closed** (see
`fleet_ladder_proposal_reverify.md`); this list records the 20 surviving protections (KS-1…KS-20,
four of them the closed F-A2/F-A3/F-A5/F-A6→KS-15/17/19/20) plus the 5 newly-verified round-2
mechanisms (KS-21…KS-25, where KS-14 is *strengthened* to structural by D-17). Nothing here
overrides the re-verify's SUPPORT verdict.

**LOG (p1_reverify round 2):** 25 known-safe attacks recorded (20 surviving from round 1 + 5
from the operator-refinements). **PASS (known-safe half)** — replaced known-safe list committed;
the overall verdict is SUPPORT per the re-verify doc.
