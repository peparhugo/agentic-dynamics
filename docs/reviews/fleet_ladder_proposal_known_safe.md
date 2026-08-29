---
status: accepted
---

# Fleet-ladder proposal — known-safe list

**Status: accepted · Date: 2026-08-29T16:20Z · Source: p5_adversarial of the `fleet_ladder_plan`
spec (spec_sha256 `0d30d4bc…`).** The attacks that did **not** falsify the proposal
(`docs/fleet/00_proposal.md`). Companion to `fleet_ladder_proposal_adversary.md` (which lists
the 7 FAILED findings F-A1…F-A7 this list does NOT override).

## The known-safe list

| # | attack | why it survived |
|---|---|---|
| KS-1 | The ladder topology (cell → orchestrator → supervisor) is complete | every p1 unit is placed on a tier; the data plane stays dockerized unchanged (design §4) |
| KS-2 | The guard **code** is never touched | the proposal edits zero source files — the write guard (`knowledge_stream.py:184-186`), the actuation-armed gate (`:188-191`), the lineage check (`:194-198`) and `scope_excluded` (`retrieval.py:395-408`) are placed, never modified; only env is per-unit |
| KS-3 | G2 actuation-armed preserved | no tier ever sets `FINOPS_ACTUATION_ARMED`; zero actuation producers exist (D-11's audit covers the only exception) |
| KS-4 | G3 lineage preserved | code-side, untouched by placement; the `SOURCE_TYPE_INDEX_KEY` population continues on every non-actuation event |
| KS-5 | G4 registry append discipline | the kb-registry consumer remains the sole appender; every producer (P1-P10, F-1, F-2) writes only via the stream — no direct index writes in any tier |
| KS-6 | G5 scope (two-channel) | per-cell `self-<worktree>` / `FINOPS_CELL_ID`; the orchestrator's emit_self is scoped to the cell; retrieval's hard filter unchanged |
| KS-7 | The neo4j bridge is buildable from the proposal alone | tier (cell), image (`fleet/base` + `[neo4j]` extra), access (`create_knowledge_schema` + idempotent `MERGE` on `knowledge_id` + edges + the `knowledge_text_ft` fulltext write), guards (no stream write-back), supervision (restart on-failure, heartbeats, `pending = 0` + lexical-leg-non-empty measure) — all specified, referencing the real handler `kb_worker.py:367-463` |
| KS-8 | The resurrected RRF leg | the read side is ALREADY live (the lexical leg returns real hits today — p1 K-3); slice 3's real work is the supervised consumer + the `rag_augment` product gate, both specified |
| KS-9 | No self-activation / master-control boundary | the proposal awaits the operator's sign-off; the supervisor is KB-read-only and holds no permanence power; the supervisor never decides what becomes chronological history |
| KS-10 | The 4-wide grid shape | unchanged, now container-to-container (design §4) — a bounded transport change, not a shape change |
| KS-11 | The migration rollbacks | slices 1-2 are additive (the ad-hoc scripts remain runnable), slice 4 is read-only tests — no destructive step in the plan |
| KS-12 | The batch producers' write discipline | P7-P10 keep their in-code `FINOPS_KB_WRITE=1`-for-the-run convention (`kb_produce.py:186`, `kb_produce_sources.py:333`, `kb_produce_facts.py:1245`, `kb_produce_campaign_evidence.py:253`) unchanged inside the containers |
| KS-13 | The data-chain single-writer for the stores | the consumer store-writes are per-store single consumers (one kb-chroma, one kb-ledger, one kb-registry, one kb-neo4j container), and the registry compaction stays in `generate_manifest.py` |
| KS-14 | The queue isolation invariant | the ladder never touches 6379 (the story-agent sandbox); the framework queue stays on 6380, the KB stream on db2 (the DB reservation doc, `docker-compose.experiment.yml:20-27`) |

**The boundary of this list:** the seven FAILED findings (F-A1…F-A7) stand. KS-2 must not be
read as "the guards are fully preserved" — F-A2 (the flag auto-clear disabled by G6's
placement) and F-A7 (the orchestrator env inheritance ambiguity) are placement defects on
otherwise-preserved code.

**LOG (p5):** 14 known-safe attacks recorded. **PASS (known-safe half)** — known-safe list
committed; the overall proposal verdict is FAIL per the adversary doc.
