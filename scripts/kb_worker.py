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
import os
import socket
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import redis

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from instrument import knowledge_stream as ks  # noqa: E402

REDIS_HOST = os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6380"))

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
                }],
            )

        return handler

    if group == "kb-neo4j-v1":
        def handler(record):
            from instrument.graph import Neo4jClient

            client = Neo4jClient()
            try:
                client.create_knowledge_schema()
                client._run(
                    "MERGE (k:Knowledge {knowledge_id: $id}) "
                    "SET k.entity_id = $eid, k.text = $text, k.source_uri = $uri, "
                    "k.authority = $authority, k.commit_sha = $commit",
                    {
                        "id": record.knowledge_id,
                        "eid": record.entity_id,
                        "text": record.text,
                        "uri": record.source_uri,
                        "authority": record.authority.name,
                        "commit": record.commit_sha,
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
        outcome = ks.process_entry(r, group, entry.entry_id, entry.event, handler)
        processed += 1
        log(f"claimed {entry.entry_id} {entry.event.knowledge_id[:12]} -> {outcome}")

    # Read new messages (block briefly so the loop is not a busy spin).
    for entry in ks.read_events(r, group, consumer, count=ks.CLAIM_BATCH, block_ms=BLOCK_TIMEOUT_MS):
        outcome = ks.process_entry(r, group, entry.entry_id, entry.event, handler)
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
