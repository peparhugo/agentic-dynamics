---
status: accepted
---

# Fleet-ladder proposal — known-safe list (re-verify)

**Status: accepted · Date: 2026-08-29T18:00Z · Source: p1_reverify of the `fleet_ladder_revision`
spec (spec_sha256 `0d30d4bc…`, escalated to deepseek-v4-pro).** The attacks that did **not**
falsify the **REVISED** proposal (`docs/fleet/00_proposal.md`, p0_revise). **REPLACES** the p5
known-safe list — the p5 placement defects (F-A2, F-A7) are now fixed, so their caveat is
withdrawn, and the revision's new mechanisms (D-9/D-10/D-11/D-13/D-14/D-15) are added as
newly-verified protections.

## The known-safe list

| # | attack | why it survived |
|---|---|---|
| KS-1 | The ladder topology (cell → orchestrator → supervisor) is complete | every p1 unit is placed on a tier; the data plane stays dockerized unchanged (design §4); the opencode server is now *classified* (operator-side) rather than left ambiguous |
| KS-2 | The guard **code** is never touched | the revision edits zero source files — the write guard (`knowledge_stream.py:184-186`), the actuation-armed gate (`:188-191`), the lineage check (`:194-198`) and `scope_excluded` (`retrieval.py:395-408`) are placed, never modified; only env is per-unit (and now explicitly enumerated per tier, D-15) |
| KS-3 | G2 actuation-armed preserved | no tier ever sets `FINOPS_ACTUATION_ARMED`; zero actuation producers exist |
| KS-4 | G3 lineage preserved | code-side, untouched by placement; the `SOURCE_TYPE_INDEX_KEY` population continues on every non-actuation event |
| KS-5 | G4 registry append discipline | the kb-registry consumer remains the sole appender; every producer (P1-P10, F-1, F-2) writes only via the stream — no direct index writes in any tier |
| KS-6 | G5 scope (two-channel) | per-cell `self-<worktree>` / `FINOPS_CELL_ID`; the orchestrator's emit_self is scoped to the cell; retrieval's hard filter unchanged |
| KS-7 | The neo4j bridge is buildable from the proposal alone | tier (cell), image (`fleet/base` + `[neo4j]` extra), access (`create_knowledge_schema` + idempotent `MERGE` on `knowledge_id` + edges + the `knowledge_text_ft` fulltext write), guards (no stream write-back), supervision (restart on-failure, heartbeats, `pending = 0` + lexical-leg-non-empty measure) — all specified, referencing the real handler `kb_worker.py:367-463` |
| KS-8 | The resurrected RRF leg | the read side is ALREADY live (the lexical leg returns real hits today — p1 K-3); slice 3's real work is the supervised consumer + the `rag_augment` product gate, both specified |
| KS-9 | No self-activation / master-control boundary | the proposal awaits the operator's sign-off; the supervisor is KB-read-only and holds no permanence power; the supervisor never decides what becomes chronological history |
| KS-10 | The 4-wide grid shape | unchanged, now container-to-container (design §4) — a bounded transport change, not a shape change |
| KS-11 | The migration rollbacks | story/analysis pools are additive (BRPOP is atomic — no double-processing); the review path is a sequenced cut-over (never both live); slice 4 is read-only tests — no destructive step |
| KS-12 | The batch producers' write discipline | P7-P10 keep their in-code `FINOPS_KB_WRITE=1`-for-the-run convention (`kb_produce.py:186`, `kb_produce_sources.py:333`, `kb_produce_facts.py:1245`, `kb_produce_campaign_evidence.py:253`) unchanged inside the containers |
| KS-13 | The data-chain single-writer for the stores | the consumer store-writes are per-store single consumers (one kb-chroma, one kb-ledger, one kb-registry, one kb-neo4j container), and the registry compaction stays in `generate_manifest.py` |
| KS-14 | The queue isolation invariant | the ladder never touches 6379 (the story-agent sandbox); the framework queue stays on 6380, the KB stream on db2, the new `fleet:commands` channel on 6380 db1 (the control plane — the DB reservation doc, `docker-compose.experiment.yml:20-27`) |
| KS-15 | The flag auto-clear write-back fires (was F-A2) | the kb-registry consumer is the one kb-worker container granted `FINOPS_KB_WRITE=1` (D-11), so the env gate (`kb_worker.py:198`) + `authorized=True` (`:212`) both pass; G6's strength governs the single exception |
| KS-16 | The orchestrator env is unambiguous (was F-A7) | the orchestrator never carries `FINOPS_KB_WRITE=1` at the container level (D-15); F-1/F-2/P11 authorize in code (`_authorized_kb_write()` / `authorized=`) — no global write authorization |
| KS-17 | The supervisor satisfies the mount contract (was F-A3) | D-13: configs → `repo ro` (compose files), logs → the `fleet-logs` named volume (not a host path); no host path beyond the four + the D-2 auth set |
| KS-18 | The socket + watcher are specified (was F-A4) | D-14: static pools + `restart: on-failure`; read-only watcher; resize/drain via `fleet:commands` + the spawn-wrapper validation; the audit surface named |
| KS-19 | The host footprint holds (was F-A5) | D-9 reclassifies the opencode server + db as operator-side (outside the ladder); the host's footprint of ours is the bootstrap unit only |
| KS-20 | The review migration is sequenced (was F-A6) | D-10: a cut-over (stop the host `trigger_reviews` first), never additive — no double-review window |

**The boundary of this list:** the seven p5 findings F-A1…F-A7 are now **closed** (see
`fleet_ladder_proposal_reverify.md`); this list records the 14 surviving p5 protections (KS-1…
KS-14, with the F-A2/F-A7 caveats withdrawn) plus the 6 newly-verified revision mechanisms
(KS-15…KS-20). Nothing here overrides the re-verify's SUPPORT verdict.

**LOG (p1_reverify):** 20 known-safe attacks recorded (14 surviving from p5 + 6 from the
revision). **PASS (known-safe half)** — replaced known-safe list committed; the overall verdict
is SUPPORT per the re-verify doc.
