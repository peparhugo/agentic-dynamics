---
status: accepted
---

# Fleet-ladder proposal — re-verification (the revision round)

**Status: accepted · Date: 2026-08-29T18:00Z · Source: p1_reverify of the `fleet_ladder_revision`
spec (spec_sha256 `0d30d4bc…`, escalated to deepseek-v4-pro).** Target: the **REVISED**
`docs/fleet/00_proposal.md` (p0_revise, which closed F-A1…F-A7). Method: re-run the p5 attack
surface (the 7 findings) AND the revision's new surface, in the prescribed order — access-matrix
completeness, guard preservation, the constraints, the neo4j bridge, migration feasibility, then
the new decisions D-9/D-10/D-11/D-13/D-14/D-15. **A failed attack is NOT a finding; a real hole
is.**

## The finding-by-finding closure table

| # | p5 finding | re-verify | resolution in the doc | closed by the mapping itself? |
|---|---|---|---|---|
| **F-A1** | R10 unmapped + the 37-touch miscount | **CLOSED** | the p2 read **R10** (`bundle_artifacts.py:53,116`) is placed on the **supervisor** tier (§1b reads, read-only over the results mount); the p3 **risk R10** (review-worker revival) is disposed by D-10 in §0's risk dispositions; the completeness line is corrected to **14 reads (R1-R10, F-3…F-6) → 13 + 4 + 14 + 6 = 37** | yes — §1a + §1b + §0 |
| **F-A2** | G6-vs-D11 dead (the flag auto-clear never fires) | **CLOSED** | **the guard wins**: D-11 grants the **kb-registry consumer `FINOPS_KB_WRITE=1`**, so the flag auto-clear's env gate (`kb_worker.py:198`) AND the code `authorized=True` (`:212`) both pass and the tombstone write-back fires. G6 is restated to the guard's actual code (§6); the cell env line names the one exception (§2) | yes — §0 (D-11) + §2 + §6 |
| **F-A3** | supervisor mount-contract breach | **CLOSED** | **D-13**: "fleet configs" → the repo's own compose files (already `repo ro`); "logs" → the `fleet-logs` docker **named volume** (not a host path). The supervisor mounts a subset of the four + that named volume; no host path beyond the four + the D-2 auth set | yes — §0 (D-13) + §1a + §1b + §2 |
| **F-A4** | socket/watcher mechanism unspecified | **CLOSED** | **D-14**: static pools + `restart: on-failure` (no socket for restart); the watcher is **read-only** (never spawns); a resize/drain is the supervisor→orchestrator command over Redis `fleet:commands` (db1, 6380), validated by the orchestrator's **spawn-wrapper** (compose allowlist + mount contract) before the socket call; the audit surface is named (§2) | yes — §0 (D-14) + §2 + §5 |
| **F-A5** | host-footprint D-9 | **CLOSED** | **D-9 reclassified**: the opencode web server (4096) + 62 GB db are **operator-side master control** (the operator's own chat server), outside the ladder — not a ladder unit, not supervisor-managed (§1a/§2). The host's footprint of ours stays the bootstrap unit only | yes — §0 (D-9) + §1a + §2 + §5 |
| **F-A6** | double-review window | **CLOSED** | **D-10 sequenced**: the review migration is a **cut-over, never additive** — stop the host `trigger_reviews` + drain its in-flight `review_all` BEFORE the containerized path starts; the slice-1 rollback is split (story/analysis additive, review cut-over) (§5) | yes — §0 (D-10) + §5 |
| **F-A7** | orchestrator env ambiguity | **CLOSED** | **D-15**: the orchestrator **never carries `FINOPS_KB_WRITE=1`** at the container level; F-1/F-2/P11 authorize in code (`_authorized_kb_write()` at `knowledge_ingestion.py:439-440` for F-1/P11, the `authorized=` param for F-2) — "temporary" cannot live in compose env (§2/§6) | yes — §0 (D-15) + §2 + §6 |

## Per-attack detail

### (1) Access-matrix completeness — PASS (F-A1 re-attacked)
Every touch is placed: R10 is now in the supervisor's read list (§1b), next to R7/R8/R9/F-6.
The arithmetic sums: 13 writes (P1-P11, F-1, F-2) + 4 consumer store-writes (C1-C4) + 14 reads
(R1-R10, F-3…F-6) + 6 guards (G1-G6) = **37**. The "16 reads (R1-R9…)" error is gone; the
count is honest. The p3 risk R10 (review-worker revival) is explicitly disposed → D-10. **No
unmapped touch.**

### (2) Guard preservation — PASS (F-A2, F-A7 re-attacked)
- **G1 write guard** (`knowledge_stream.py:184-186`): code untouched. Placement now enumerates
  the env holders precisely: P1-P10 cell writers + the kb-registry consumer (D-11). The
  orchestrator does **not** set it (D-15) — its F-1/F-2/P11 writes use the code-side
  `_authorized_kb_write()` / `authorized=` seam, which works without the env. The F-A7 ambiguity
  is gone: the compose env is explicit per tier, and "temporary" is expressed in code, not env.
- **G2 actuation-armed** (`:188-191`): never set in the ladder — preserved.
- **G3 lineage** (`:194-198`): code-side, untouched — preserved.
- **G4 registry append**: the kb-registry consumer remains the sole appender; producers write
  only via the stream — preserved.
- **G5 scope** (`self-<worktree>` / `scope_excluded`): per-cell env — preserved.
- **G6 consumer read-only**: the kb-registry consumer is the ONE kb-worker container granted
  `FINOPS_KB_WRITE=1` (D-11), so the flag auto-clear's env gate passes. This is the guard's
  **own** mechanism (the env gate at `:198`), not a bypass — the gate still governs, and the
  slice-4 guard test asserts exactly one consumer carries the env. The D-11/F-A2 contradiction is
  resolved in the guard's favor: the env gate is what makes the exception auditable.

### (3) The constraints — PASS (F-A3, F-A4, F-A5 re-attacked)
- Host bootstrap only: **held** — D-9 reclassifies the opencode server + db as operator-side
  (outside the ladder); the host's footprint of ours is the bootstrap unit only.
- Master control = the operator chat, no self-activation: **held** — the supervisor is
  KB-read-only, the sign-off gate is explicit, nothing self-activates.
- Socket in the orchestrator tier ONLY: **held** — the supervisor has no socket (D-3/D-14); the
  watcher is read-only; spawn/drain is the orchestrator's socket call, gated by the spawn-wrapper.
- Mount contract, nothing beyond the four: **held** — D-13 absorbs the supervisor's two
  out-of-contract mounts (configs → `repo ro`; logs → a docker named volume, not a host path);
  no tier mounts a host path beyond the four + the D-2 auth five-dir set.

### (4) The neo4j bridge — NOT FALSIFIED (unchanged)
The kb-neo4j-v1 spec is intact and buildable from the proposal alone: tier (cell), image
(`fleet/base` + `[neo4j]`), access (stream read → `create_knowledge_schema` + idempotent `MERGE`
+ edges + the `knowledge_text_ft` fulltext write), guards (no write-back — G6, no env — D-11 is
the *registry* consumer's env, not neo4j's), supervision (restart on-failure, heartbeats,
`pending=0` + lexical-leg-non-empty measure), slice-3 preconditions (D-12). The §4 guard note is
now precise about the flag auto-clear's two gates. **Known-safe.**

### (5) Migration feasibility — PASS (F-A6 re-attacked)
The review path is now a sequenced cut-over (stop the host `trigger_reviews` + drain its
in-flight `review_all` first), so no double-review window. The story/analysis pools stay additive
(BRPOP is atomic — no double-processing). The running campaigns + the data chain are protected
by the additive/cut-over rollbacks; the 2,640-DLQ triage and the 26,877-entry head reset remain
bounded (D-12).

### (6) The revision's new surface — attacked, no new finding
- **D-13's named volume** (`fleet-logs`): a docker-managed volume, not a host bind-mount — it
  does not extend the host footprint and does not enter the "no other host path" rule. The
  slice-4 guard test must whitelist it (the named volume, not a host path); the proposal states
  this.
- **D-14's `fleet:commands` channel** (Redis 6380 db1): consistent with the two-channel rule (the
  control/telemetry plane is db1; the KB stream is db2; 6379 is never touched). A compromised
  supervisor can only emit bounded `{scale|drain, service, count}` commands, and the spawn-wrapper
  re-validates each against the compose allowlist + the mount contract — the blast radius is
  bounded to the declared services.
- **D-15's env removal from the orchestrator**: nothing the orchestrator runs needs the env — P1-P10
  are cell units; F-1/F-2/P11 authorize in code. No write path regresses.
- **D-9's reclassification**: the operator's chat server is the operator's own process, outside
  the ladder — it neither expands "our" host footprint nor needs supervisor management.
- **R10 on the supervisor**: the bundle reference check reads `registry_index.jsonl` +
  `data_manifest.json` over the results mount the supervisor already has — no new mount.

## VERDICT: SUPPORT

All 7 findings (F-A1…F-A7) are closed — each resolution lives in the doc and the mechanism is
closed by the mapping itself (the access matrix, the decisions table, the compose layout, the
migration slices). The guards (G1-G6) hold at full strength (the F-A2/F-A7 placement defects are
fixed without touching guard code); the four constraints hold; the neo4j bridge is intact; the
migration is feasible with no overlapping review window; and the revision's new surface (D-9,
D-10, D-11, D-13, D-14, D-15) introduces no new finding. The companion
`fleet_ladder_proposal_known_safe.md` is REPLACED with the re-verify's known-safe list.

**LOG (p1_reverify, deepseek-v4-pro):** 7/7 findings re-checked CLOSED (mechanism closed by the
mapping, not prose); guards re-traced G1-G6 at full strength; constraints held (bootstrap-only,
no self-activation, socket-orchestrator-only, four-mount contract incl. the supervisor); neo4j
bridge NOT FALSIFIED; migration feasible (review cut-over); new surface (D-9/D-10/D-11/D-13/D-14/
D-15) attacked — no new finding. **SUPPORT** — re-verify committed; awaiting the operator's
sign-off.
