"""Durable knowledge ingestion over Redis Streams.

This module is the *transport* for the knowledge base's change/freshness plane. It
moves small, pointer-only events (``knowledge.KnowledgeEvent`` — no body) through a
Redis Stream with consumer groups, acknowledgements, lease-timeout claims, capped
retries, and a dead-letter stream. It deliberately does **not** touch ``live.py``:
the dashboard telemetry plane (pub/sub, DB 1) stays separate from the durable
ingestion plane (streams, DB 2).

Isolation contract (load-bearing):
  - Host ``127.0.0.1``, port ``FINOPS_REDIS_PORT`` (default **6380**, the framework
    instance), **DB 2**. Keys are ``kb:v1:*``, the stream is ``kb:v1:changes``, the
    dead-letter stream is ``kb:v1:dead_letter``.
  - **Never port 6379** — the story-agent Redis on 6379 is a test sandbox that
    ``flushall()``s. The framework queue (DB 1) and the knowledge stream (DB 2) both
    live on 6380, isolated from the sandbox and from each other.

A consumer's job (the ingestion loop): read a pointer → read the source artifact →
verify ``content_hash`` → upsert idempotently keyed by ``knowledge_id`` → ``XACK`` only
after the destination confirms. A failed message stays pending, is claimed after the
lease timeout, retried up to ``MAX_RETRIES``, then dead-lettered.

Design: ``code_reviews/2026-08-15_rag-knowledge-base-proposal-review.md`` §7 and the
companion ``docs/rag_design.md`` §4.2 / §4.4.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

from .knowledge import Authority, KnowledgeEvent, KnowledgeRecord

# ── Connection / key contract ───────────────────────────────────

REDIS_HOST = os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6380"))
#: Knowledge stream lives on DB 2 of the framework instance. Never DB 0/1 (queue),
#: and never the 6379 story sandbox.
REDIS_DB = 2

STREAM_KEY = "kb:v1:changes"
DEAD_LETTER_KEY = "kb:v1:dead_letter"
CHECKPOINT_KEY = "kb:v1:checkpoints"  # ledger consumer's per-knowledge_id checkpoint hash

#: The three consumers. Each ack's only after its own destination confirms.
CONSUMER_GROUPS = ("kb-chroma-v1", "kb-neo4j-v1", "kb-ledger-v1")

LEASE_TIMEOUT_MS = 60_000      # [H] how long a crashed consumer's claim survives
MAX_RETRIES = 3                # [H] delivery attempts before dead-letter
CLAIM_BATCH = 100              # [H] max messages reclaimed per pass
RECONCILE_INTERVAL_S = 3600    # hourly manifest reconciliation


def connect(
    host: str = REDIS_HOST,
    port: int = REDIS_PORT,
    db: int = REDIS_DB,
) -> Any:
    """Connect to the knowledge stream Redis, reusing ``live.py``'s conventions.

    Unlike ``live.py``'s best-effort ``_connect`` (which no-ops on failure), ingestion
    **raises** — a downed stream must be visible, not silently dropped.
    """
    import redis

    client = redis.Redis(
        host=host,
        port=port,
        db=db,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_keepalive=False,
    )
    client.ping()  # fail fast; the caller retries with backoff
    return client


# ── Pointer events ──────────────────────────────────────────────

@dataclass
class StreamEntry:
    """A parsed stream message: the entry id plus its pointer event."""

    entry_id: str
    event: KnowledgeEvent


def decode_event(data: dict[str, Any]) -> KnowledgeEvent:
    """Parse a stream field dict into a :class:`KnowledgeEvent`, rejecting unknown contracts."""
    schema = str(data.get("schema_version", ""))
    if schema not in ("kb/v1", ""):
        raise ValueError(f"unknown schema_version {schema!r}")
    return KnowledgeEvent.from_dict(data)


def publish_event(
    r: Any,
    event: KnowledgeEvent,
    *,
    stream: str = STREAM_KEY,
    authorized: bool = False,
) -> str:
    """Append a pointer event to the change stream; return its entry id.

    WRITE GUARD: appending mutates the durable ingestion plane, so the caller must be an
    authorized writer. Authorization is granted when ``authorized=True`` is passed explicitly
    OR the ``FINOPS_KB_WRITE`` env flag is ``"1"``; otherwise this raises ``RuntimeError`` so a
    read-mostly process can never accidentally emit. ``scripts/kb_produce.py`` (and
    ``scripts/kb_produce_sources.py``) set the env flag for their whole run; the self-build
    emit path (``knowledge_ingestion.emit_phase_finding``) sets it only for the duration of the
    emit and restores it afterward.
    """
    if not authorized and os.environ.get("FINOPS_KB_WRITE") != "1":
        raise RuntimeError(
            "knowledge write not authorized: set FINOPS_KB_WRITE=1 or pass authorized=True"
        )
    return r.xadd(stream, event.to_dict())


def dead_letter(
    r: Any,
    event: KnowledgeEvent,
    entry_id: str,
    reason: str,
    *,
    dl: str = DEAD_LETTER_KEY,
) -> str:
    """Append a persistently-failing event to the dead-letter stream.

    Returns the dead-letter entry id. The caller is responsible for acking the original
    stream entry (via :func:`acknowledge`) so it stops being redelivered.
    """
    payload = {
        **event.to_dict(),
        "reason": reason,
        "source_entry_id": entry_id,
        "dead_lettered_at": datetime.now(timezone.utc).isoformat(),
    }
    return r.xadd(dl, payload)


# ── Consumer groups ─────────────────────────────────────────────

def create_consumer_group(
    r: Any, group: str, *, stream: str = STREAM_KEY, mkstream: bool = True
) -> bool:
    """Create a consumer group idempotently; returns True if created, False if it existed."""
    import redis

    try:
        r.xgroup_create(stream, group, id="0", mkstream=mkstream)
        return True
    except redis.exceptions.ResponseError as exc:
        if "BUSYGROUP" in str(exc):
            return False
        raise


def read_events(
    r: Any,
    group: str,
    consumer: str,
    *,
    count: int = 1,
    block_ms: int | None = None,
    stream: str = STREAM_KEY,
) -> list[StreamEntry]:
    """Read ``count`` new messages for ``consumer`` (XREADGROUP ``>``)."""
    kwargs: dict[str, Any] = {"count": count, "block": block_ms} if block_ms is not None else {"count": count}
    result = r.xreadgroup(group, consumer, {stream: ">"}, **kwargs)
    entries: list[StreamEntry] = []
    for _stream_key, messages in result:
        for entry_id, fields in messages:
            entries.append(StreamEntry(entry_id=entry_id, event=decode_event(fields)))
    return entries


def acknowledge(
    r: Any, group: str, *entry_ids: str, stream: str = STREAM_KEY
) -> int:
    """XACK one or more entries; returns the number acknowledged."""
    if not entry_ids:
        return 0
    return int(r.xack(stream, group, *entry_ids))


def pending_count(r: Any, group: str, *, stream: str = STREAM_KEY) -> int:
    """Return the group's pending-entry count (unacked/redelivery backlog)."""
    info = r.xpending(stream, group)
    return int(info.get("pending", 0))


def delivery_count(r: Any, group: str, entry_id: str, *, stream: str = STREAM_KEY) -> int:
    """Return how many times an entry has been delivered to any consumer."""
    for entry in r.xpending_range(stream, group, min="-", max="+", count=CLAIM_BATCH):
        if entry.get("message_id") == entry_id:
            return int(entry.get("times_delivered", 0))
    return 0


def claim_pending(
    r: Any,
    group: str,
    consumer: str,
    *,
    min_idle_ms: int = LEASE_TIMEOUT_MS,
    count: int = CLAIM_BATCH,
    stream: str = STREAM_KEY,
) -> list[StreamEntry]:
    """Reclaim stale pending messages (XAUTOCLAIM) for ``consumer``.

    Returns the reclaimed entries, which ``consumer`` may now process. A claim resets
    ownership and increments the entry's delivery count.
    """
    _next_id, messages, _deleted = r.xautoclaim(
        stream, group, consumer, min_idle_time=min_idle_ms, start_id="0-0", count=count
    )
    return [
        StreamEntry(entry_id=entry_id, event=decode_event(fields))
        for entry_id, fields in messages
    ]


# ── Artifact verification + extraction ──────────────────────────

def verify_content_hash(artifact: bytes, expected: str) -> bool:
    """Return True when ``sha256(artifact)`` equals the event's ``content_hash``."""
    if not expected:
        return False
    digest = hashlib.sha256(artifact).hexdigest()
    return digest == expected


def read_artifact(source_uri: str) -> bytes:
    """Read a source artifact's bytes.

    Supports a local filesystem path or a ``file://`` URI. A missing artifact raises
    ``FileNotFoundError`` — consumers must not upsert an unverifiable source.
    """
    path = source_uri
    if path.startswith("file://"):
        path = path[len("file://"):]
    from pathlib import Path

    return Path(path).read_bytes()


def default_extract(event: KnowledgeEvent, artifact: bytes) -> KnowledgeRecord:
    """Build a :class:`KnowledgeRecord` from a verified pointer + artifact bytes.

    This is the minimal v1 extractor: it decodes the artifact as UTF-8 text and carries the
    identity, provenance, and text through. A richer extractor (symbols, chunking, redaction,
    evidence class) belongs to ``knowledge_ingestion`` and may replace it via the injectable
    ``extractor`` arg — e.g. ``knowledge_ingestion.extract_record``, which parses the durable
    JSON artifact and reconstructs the full ``MEASURED`` record.
    """
    text = artifact.decode("utf-8", errors="replace")
    return KnowledgeRecord(
        knowledge_id=event.knowledge_id,
        entity_id=event.entity_id,
        source_uri=event.source_uri,
        source_type="",
        logical_locator="",
        repository_id="",
        branch="",
        worktree_id="",
        commit_sha=event.source_revision,
        content_hash=event.content_hash,
        extractor_version=event.schema_version or "kb/v1",
        embedding_version="",
        authority=Authority.DERIVED,
        valid_from=event.occurred_at,
        valid_to=None,
        observed_at=event.occurred_at,
        indexed_at=datetime.now(timezone.utc).isoformat(),
        acl_scope="",
        contains_sensitive_data=False,
        text=text,
        token_count=max(1, len(text.split())),
        language="",
        symbols=[],
        outcome_id="",
        test_executed_success=None,
        evidence_class="[C]",
    )


# ── The ingestion loop ──────────────────────────────────────────

def process_entry(
    r: Any,
    group: str,
    entry_id: str,
    event: KnowledgeEvent,
    handler: Callable[[KnowledgeRecord], None],
    *,
    max_retries: int = MAX_RETRIES,
    stream: str = STREAM_KEY,
    artifact_reader: Callable[[str], bytes] = read_artifact,
    extractor: Callable[[KnowledgeEvent, bytes], KnowledgeRecord] = default_extract,
) -> str:
    """Read → verify → extract → upsert → ack, one entry. Returns ``ok | retry | dead_letter``.

    The ``handler`` performs the idempotent upsert keyed by ``knowledge_id`` and must
    raise on any store failure. ``XACK`` happens only after the handler returns
    (destination confirmed). On failure the entry stays pending for a later claim; once
    its delivery count reaches ``max_retries`` it is dead-lettered.
    """
    try:
        artifact = artifact_reader(event.source_uri)
        if not verify_content_hash(artifact, event.content_hash):
            raise ValueError(f"content_hash mismatch for {event.source_uri!r}")
        record = extractor(event, artifact)
        handler(record)
    except Exception as exc:
        if delivery_count(r, group, entry_id, stream=stream) >= max_retries:
            dead_letter(r, event, entry_id, reason=repr(exc))
            acknowledge(r, group, entry_id, stream=stream)
            return "dead_letter"
        return "retry"

    acknowledge(r, group, entry_id, stream=stream)
    return "ok"


def reconcile_missing(
    r: Any,
    expected: Iterable[KnowledgeEvent],
    known_ids: set[str],
    *,
    stream: str = STREAM_KEY,
) -> list[str]:
    """Emit events whose ``knowledge_id`` is not yet known; returns the new entry ids.

    The hourly reconciliation pass feeds the union of repository manifests + result
    indexes as ``expected`` and the store inventories as ``known_ids``. Any expected id
    absent from the stores is re-emitted, repairing missed hooks, Redis loss, or a
    consumer crash.
    """
    emitted: list[str] = []
    for event in expected:
        if event.knowledge_id and event.knowledge_id not in known_ids:
            emitted.append(publish_event(r, event, stream=stream))
    return emitted
