---
status: accepted
---

# Fleet-ladder proposal — adversarial verification

**Status: accepted · Date: 2026-08-29T16:20Z · Source: p5_adversarial of the `fleet_ladder_plan`
spec (spec_sha256 `0d30d4bc…`).** Target: `docs/fleet/00_proposal.md`. Method: attack in the
prescribed order — access-matrix completeness, guard preservation, the constraints, the neo4j
bridge, migration feasibility. Each finding cites the proposal line, the prior-phase artifact,
and the code. **A failed attack is NOT a finding; a real hole is.**

## The finding table

| # | attack area | severity | finding |
|---|---|---|---|
| **F-A1** | access-matrix completeness | **FAILED** | **R10 is unmapped.** p2's R10 (`scripts/bundle_artifacts.py:53,116` — the registry reference check) appears in NO tier's read list (§1b lists cell `R1,R2,R3,R5,R6`, orchestrator `R1-R4,R5,R6`, supervisor `R7,R8,R9,F-6`, operator `R7,R9`). The completeness line ("16 reads (R1-R9, F-3…F-6)", p4:58) silently drops R10 and miscounts: R1-R9 + F-3…F-6 = **13 reads**, not 16; and 13 writes + 4 consumers + 13 reads + 6 guards = **36, not 37**. The honest 37-touch count requires R10 back (14 reads → 37 total). |
| **F-A2** | guard preservation | **FAILED** | **G6 contradicts D-11 and disables the flag auto-clear.** §6 G6 ("the kb-worker containers get **no** `FINOPS_KB_WRITE`", p4:149) conflicts with the flag auto-clear, which REQUIRES `FINOPS_KB_WRITE=1` (`kb_worker.py:198-203`: `if os.environ.get("FINOPS_KB_WRITE") != "1": return  # observe only`). Under G6's placement the tombstone write-back (D-11's "one audited exception") never fires — D-11's promise is dead on arrival. The kb-registry container must either carry `FINOPS_KB_WRITE=1` (an authorized writer, audited per D-11) or the auto-clear must be explicitly accepted as degraded. |
| **F-A3** | constraints (mount contract) | **FAILED** | **The supervisor violates the four-mount contract the proposal's own guard enforces.** §1a/§2 give the supervisor "fleet configs ro, logs rw" (p4:44,86) — two mounts outside the four-category contract ("worktree rw / results rw / repo ro / auth ro — **nothing else**"). The design grants them (§2/§4) but §3/§9's guard ("no path outside the four", and the slice-4 compose-contract guard test) would **fail the supervisor's own compose file**. The proposal inherits the design's §3-vs-§2/§4 contradiction unresolved: either the slice-4 guard whitelists the supervisor's two mounts (making the four-mount contract a cell/orchestrator contract) or the configs/logs ride inside results/repo. |
| **F-A4** | constraints (socket + the watcher) | **FAILED** | **The fleet manager's pool/watcher mechanism is unspecified and either needs the socket or overstates the R3 fix.** D-3 bans the socket from the supervisor (p4:23) and says "fleet-level spawn/drain is executed by the orchestrator", but the fleet manager's core job (§1a: "pools, watcher", p4:44) is a **continuous per-queue operation**, not a grid wave. If it scales/spawns cell containers it needs the socket (violating D-3); if the pools are static (`--scale`, p4:70) + docker's own restart, then "the queue watcher live (fixes R3)" must be restated as "static pools + docker restart + a monitor" — and the supervisor→orchestrator command channel D-3 implies is never specified. |
| **F-A5** | constraints (host footprint) | **FAILED** | **D-9 keeps a host-native service, contradicting the design's host-footprint claim.** The design §2: "The host's footprint of ours: the bootstrap unit only." D-9 (p4:29,46) keeps the opencode server (4096) + its 62 GB db host-native as a "supervisor-MANAGED unit". Either it is **part of master control** (the chat's server — operator-side, outside the ladder, and then "supervisor-managed" is wrong) or it is a second host service (violating the footprint). The proposal must classify it one way or the other. |
| **F-A6** | migration feasibility | **FAILED** | **Slice 1's "additive" rollback + D-10 creates a double-review window.** The host `trigger_reviews` → `review_all` is live today (p1 §2). Slice 1 adds the containerized review unit (D-10) while the rollback keeps the ad-hoc processes running ("the old setsid nohup workers still run", p4:135). During the migration both fire `review_all` → double reviews. The slice must sequence the review migration (stop the host trigger first) or the "additive" claim is unsafe for the review path. |
| **F-A7** | guard preservation | **FAILED (placement ambiguity)** | **Orchestrator env inheritance could silently set `FINOPS_KB_WRITE` globally.** §2 says the orchestrator gets "same env + mounts" (p4:83), and the cell env includes the write-flag line (p4:77). If the orchestrator container inherits `FINOPS_KB_WRITE=1`, then EVERY process inside it — including the agent phases that run there — is an authorized stream writer, weakening G1. The real mechanism for F-1/F-2/P11 is the in-code `_authorized_kb_write()` context manager (`knowledge_ingestion.py:439-440`), which works WITHOUT the env. The proposal must state the orchestrator does **not** set the env; "temporary" cannot be expressed in compose env. |

## Per-attack detail

### (1) Access-matrix completeness — FAILED (F-A1)
Cross-checked §1b against p2's R1-R10 + p3's F-1…F-6. Every touch EXCEPT R10 is placed;
F-1…F-6 absorbed correctly (D-4…D-7). The arithmetic failure is itself evidence: the stated
breakdown does not sum to the claimed 37.

### (2) Guard preservation — FAILED (F-A2, F-A7)
- G1 write-guard **code** (`knowledge_stream.py:184-186`) is untouched — no code edit anywhere
  in the proposal; only env placement changes. The **placement** has the F-A7 ambiguity and the
  F-A2 contradiction.
- G2 actuation-armed (`:188-191`): never set in the ladder — preserved.
- G3 lineage (`:194-198` + `SOURCE_TYPE_INDEX_KEY`): code-side, untouched — preserved.
- G4 registry append: the kb-registry consumer remains the sole appender; producers write only
  via the stream — preserved.
- G5 scope (`self-<worktree>`/`scope_excluded`): per-cell env — preserved.
- G6 consumer read-only: the stated placement disables the flag auto-clear (F-A2).

### (3) The constraints — FAILED (F-A3, F-A4, F-A5)
- Host bootstrap only: **violated/ambiguous** (F-A5 — the opencode server).
- Master control = the operator chat, no self-activation: **held** — nothing self-activates,
  the supervisor is KB-read-only, the sign-off gate is explicit.
- Socket in the orchestrator tier ONLY: **held for the socket mount, broken for the watcher
  mechanism** (F-A4).
- Mount contract, nothing beyond the four: **violated by the supervisor's own mounts** (F-A3).

### (4) The neo4j bridge — NOT FALSIFIED
The kb-neo4j-v1 spec is buildable from the proposal alone: tier (cell), image (`fleet/base` +
`[neo4j]` extra), access (stream read → `create_knowledge_schema` + idempotent `MERGE` on
`knowledge_id` + edges + the `knowledge_text_ft` write), guards (no write-back — G6, no env),
supervision (restart on-failure, heartbeats, `pending=0` + lexical-leg-non-empty measure),
slice-3 preconditions (D-12 head reset + MERGE reconciliation). The handler it references is
real (`kb_worker.py:367-463`). **Known-safe.** (Buildability nit, not a finding: D-12's group
reset is `XGROUP SETID` — the proposal doesn't say who runs it in slice 3.)

### (5) Migration feasibility — FAILED (F-A6)
Slices are individually bounded and 3 of 4 have additive/read-only rollbacks. The running
campaigns + the data chain are protected by the additive rollback **except** the review path
(F-A6). The 2,640-DLQ triage and the 26,877-entry head reset are bounded (D-12).

**VERDICT: FAIL — 7 findings (F-A1…F-A7).** The proposal is not verifiable as committed: the
access matrix is incomplete (R10), one guard placement disables a shipped feature (F-A2), the
mount contract is self-contradicted (F-A3), the socket constraint is either broken or
overstated (F-A4), the host footprint is unclassified (F-A5), the review migration double-fires
(F-A6), and the orchestrator env is ambiguous (F-A7). The proposal must be revised; the
companion `fleet_ladder_proposal_known_safe.md` lists what survived.

**LOG (p5):** finding table = 7 FAILED (F-A1…F-A7) + 0 safe on completeness; the neo4j bridge
and the guard code survived; constraints partially failed. **FAIL** — adversary committed.
