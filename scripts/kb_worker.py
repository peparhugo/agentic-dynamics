"""Knowledge-base ingestion worker — run one consumer group against the change stream.

Structurally parallel to ``scripts/worker.py`` (the story BRPOP worker): a long-running
Python process on the host that connects to the framework Redis (6380) with backoff,
recreates the client after failures, and logs to stdout. The difference is the data
plane — Redis *Streams* with consumer groups instead of a BRPOP list — and the
destination: a knowledge store (Chroma / Neo4j / ledger checkpoint) instead of a story.

    python scripts/kb_worker.py --group kb-ledger-v1
    python scripts/kb_worker.py --group kb-chroma-v1 --once

Each group acks a message only after its own destination confirms the idempotent upsert
keyed by ``knowledge_id``; a failed message stays pending, is claimed after the lease
timeout, retried up to ``MAX_RETRIES``, then dead-lettered. Reconciliation re-emits
missing events hourly (see ``knowledge_stream.reconcile_missing``).
"""

import argparse
import json
import os
import socket
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import redis

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from instrument import knowledge_ingestion as ki  # noqa: E402
from instrument import knowledge_stream as ks  # noqa: E402

REDIS_HOST = os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6380"))

#: canonical-state round 2, step 8 — the flat, append-only registry index the
#: "kb-registry-v1" consumer group writes to. Deliberately the same durable,
#: human-greppable pattern as ``scripts/supervise.py``'s ``flags.jsonl``: one JSON line
#: per indexed record, never rewritten in place. ``generate_manifest.py``'s compaction
#: step (plan step 15, out of scope here) is what later collapses this append-only log
#: down to "one row per entity_id, newest wins" — this consumer does not resolve
#: superseded/tombstoned lifecycle state itself, it only records what it saw.
REGISTRY_INDEX_PATH = PROJECT_ROOT / "experiments" / "results" / "registry_index.jsonl"

REDIS_BASE_DELAY = 2.0
REDIS_MAX_RETRIES = 10
BLOCK_TIMEOUT_MS = 10_000
IDLE_POLLS_BEFORE_EXIT = 12
RECONCILE_EVERY_S = ks.RECONCILE_INTERVAL_S


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}][kb-worker] {msg}", flush=True)


def _connect_redis() -> redis.Redis:
    """Connect to the knowledge stream Redis (DB 2) with exponential backoff."""
    delay = REDIS_BASE_DELAY
    while True:
        try:
            r = ks.connect(host=REDIS_HOST, port=REDIS_PORT)
            return r
        except Exception as e:
            log(f"Redis unavailable: {e}; retrying in {delay:.0f}s")
            time.sleep(delay)
            delay = min(delay * 2, 60.0)


def _default_consumer(group: str) -> str:
    return f"{group}-{socket.gethostname()}-{os.getpid()}"


def build_handler(group: str, r: redis.Redis):
    """Resolve the destination handler for a named consumer group.

    Each handler performs the idempotent upsert keyed by ``knowledge_id`` and must
    raise on failure so the caller leaves the entry pending (retry → dead-letter).
    """
    if group == "kb-ledger-v1":
        def handler(record):
            # The ledger consumer's destination is the checkpoint hash — it records
            # that this knowledge_id was observed and indexed_at (for freshness/lag).
            r.hset(ks.CHECKPOINT_KEY, record.knowledge_id, record.indexed_at)

        return handler

    if group == "kb-registry-v1":
        def handler(record):
            # Append one compacted line to the flat, append-only registry index —
            # deliberately the same durable/human-greppable pattern as flags.jsonl (see
            # REGISTRY_INDEX_PATH's module-level docstring). "lifecycle_state": "current"
            # is a fixed marker, not a computed value: this consumer sees each record
            # exactly once, in isolation, so it cannot itself determine whether a LATER
            # record has since superseded this one — that resolution is
            # generate_manifest.py's compaction step (plan step 15), which takes the
            # latest-by-indexed_at row per entity_id from this file.
            #
            # ``record.supersedes`` is the round-1 supersession-chain field (canonical-state
            # design §1) — present on KnowledgeRecord, None for a first version.
            #
            # ``logical_locator``/``source_uri`` (plan step 16 addition): scripts/registry.py's
            # `show <id>` command resolves a story_id/session_id/cell_id query against
            # `logical_locator` (the SAME field every producer's identity formula folds
            # into entity_id — see docs/canonical_state_r2_design.md §3's table), so the
            # index line must carry it, not just the two derived hash identities.
            line = {
                "knowledge_id": record.knowledge_id,
                "entity_id": record.entity_id,
                "source_type": record.source_type,
                "logical_locator": record.logical_locator,
                "source_uri": record.source_uri,
                "lifecycle_state": "current",
                "observed_at": record.observed_at,
                "indexed_at": record.indexed_at,
                "supersedes": record.supersedes,
                "causes": record.causes,
            }
            REGISTRY_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(REGISTRY_INDEX_PATH, "a") as f:
                f.write(json.dumps(line) + "\n")

        return handler

    if group == "kb-chroma-v1":
        def handler(record):
            from instrument.embeddings import ChromaStore

            store = ChromaStore(collection_name="knowledge_chunks_v1")
            store.upsert(
                [record.knowledge_id],
                [record.text],
                metadatas=[{
                    "knowledge_id": record.knowledge_id,
                    "entity_id": record.entity_id,
                    "authority": record.authority.name,
                    "source_uri": record.source_uri,
                    "commit_sha": record.commit_sha,
                    "content_hash": record.content_hash,
                    # Scope isolation on the dense leg: retrieval.py's _dense_filter and
                    # scope_excluded key off these, so the Chroma metadata MUST carry them or the
                    # dense leg returns nothing under any non-empty repository scope.
                    "repository_id": record.repository_id,
                    "acl_scope": record.acl_scope,
                }],
            )

        return handler

    if group == "kb-neo4j-v1":
        def handler(record):
            from instrument.graph import Neo4jClient

            client = Neo4jClient()
            try:
                client.create_knowledge_schema()
                # ``source_type`` is stored here (alongside the citation fields) so the KB
                # can answer "what kinds of knowledge do we hold" without a cross-store join —
                # the verify step of the sources run depends on it (findings alone are not
                # enough). logical_locator / language / evidence_class carry the citation
                # provenance the retrieval leg may want to surface.
                #
                # canonical-state round 2, step 8 (gap d): the date-spine fields
                # (valid_from/observed_at/indexed_at) and the lineage fields
                # (supersedes/causes) are now persisted too — the base inventory found
                # this SET clause silently dropped all five. ``valid_to``/
                # ``lifecycle_state`` stay unwritten on purpose: both are computed at
                # read time only (round 1's argument, unchanged by this round) — writing
                # them here would make the graph a second source of truth for a value
                # that must always be derived from "is there a newer knowledge_id for
                # this entity_id", never stored and risk going stale.
                #
                # ``record.supersedes`` is the round-1 supersession-chain field — present on
                # KnowledgeRecord (canonical-state design §1), None for a first version.
                supersedes = record.supersedes
                client._run(
                    "MERGE (k:Knowledge {knowledge_id: $id}) "
                    "SET k.entity_id = $eid, k.text = $text, k.source_uri = $uri, "
                    "k.authority = $authority, k.commit_sha = $commit, "
                    "k.source_type = $stype, k.logical_locator = $loc, "
                    "k.language = $lang, k.evidence_class = $ev, "
                    "k.repository_id = $repo, k.acl_scope = $acl, "
                    "k.valid_from = $valid_from, k.observed_at = $observed_at, "
                    "k.indexed_at = $indexed_at, k.supersedes = $supersedes, "
                    "k.causes = $causes "
                    "WITH k "
                    "FOREACH (_ IN CASE WHEN $supersedes IS NOT NULL THEN [1] ELSE [] END | "
                    "    MERGE (prev:Knowledge {knowledge_id: $supersedes}) "
                    "    MERGE (k)-[:SUPERSEDES]->(prev) "
                    ")",
                    {
                        "id": record.knowledge_id,
                        "eid": record.entity_id,
                        "text": record.text,
                        "uri": record.source_uri,
                        "authority": record.authority.name,
                        "commit": record.commit_sha,
                        "stype": record.source_type,
                        "loc": record.logical_locator,
                        "lang": record.language,
                        "ev": record.evidence_class,
                        "repo": record.repository_id,
                        "acl": record.acl_scope,
                        "valid_from": record.valid_from,
                        "observed_at": record.observed_at,
                        "indexed_at": record.indexed_at,
                        "supersedes": supersedes,
                        "causes": record.causes,
                    },
                )
            finally:
                client.close()

        return handler

    raise ValueError(f"unknown consumer group: {group!r}")


def process_batch(r, group, consumer, handler, *, once: bool) -> int:
    """Claim stale messages then read new ones; return how many were processed."""
    processed = 0

    # Reclaim messages left behind by a crashed/lagging consumer after the lease.
    for entry in ks.claim_pending(r, group, consumer):
        outcome = ks.process_entry(
            r, group, entry.entry_id, entry.event, handler,
            extractor=ki.extract_record,
        )
        processed += 1
        log(f"claimed {entry.entry_id} {entry.event.knowledge_id[:12]} -> {outcome}")

    # Read new messages (block briefly so the loop is not a busy spin).
    for entry in ks.read_events(r, group, consumer, count=ks.CLAIM_BATCH, block_ms=BLOCK_TIMEOUT_MS):
        outcome = ks.process_entry(
            r, group, entry.entry_id, entry.event, handler,
            extractor=ki.extract_record,
        )
        processed += 1
        log(f"new {entry.entry_id} {entry.event.knowledge_id[:12]} -> {outcome}")

    return processed


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a knowledge-base consumer group")
    parser.add_argument("--group", required=True, choices=ks.CONSUMER_GROUPS,
                        help="consumer group to run")
    parser.add_argument("--consumer", default=None, help="consumer name (default hostname+pid)")
    parser.add_argument("--once", action="store_true", help="process one batch then exit")
    args = parser.parse_args()

    group = args.group
    consumer = args.consumer or _default_consumer(group)
    log(f"Starting group={group} consumer={consumer} pid={os.getpid()}")

    r = _connect_redis()
    created = ks.create_consumer_group(r, group)
    log(f"consumer group {group} {'created' if created else 'already existed'}")

    handler = build_handler(group, r)
    last_reconcile = time.monotonic()

    empty_polls = 0
    processed_total = 0

    while True:
        try:
            processed = process_batch(r, group, consumer, handler, once=args.once)
        except redis.exceptions.ConnectionError as e:
            log(f"Redis connection error: {e}; reconnecting")
            time.sleep(10)
            r = _connect_redis()
            ks.create_consumer_group(r, group)
            continue
        except Exception as e:
            log(f"batch error: {e}\n{traceback.format_exc()}")
            time.sleep(5)
            continue

        processed_total += processed
        if processed == 0:
            empty_polls += 1
        else:
            empty_polls = 0

        # Hourly manifest reconciliation — re-emit any expected knowledge_id that the
        # stores do not yet contain (repairs missed hooks / Redis loss / consumer crash).
        if time.monotonic() - last_reconcile >= RECONCILE_EVERY_S:
            log("reconciliation pass (no manifest wired in v1 — see knowledge_ingestion)")
            last_reconcile = time.monotonic()

        if args.once:
            break
        if empty_polls >= IDLE_POLLS_BEFORE_EXIT:
            log(f"idle after {empty_polls} polls; exiting")
            break

    log(f"Done. processed={processed_total}")


if __name__ == "__main__":
    main()
