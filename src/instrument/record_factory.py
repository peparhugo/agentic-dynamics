"""Shared record-builder factory for the runtime-RAG knowledge base.

Every producer-side derivation path (:mod:`instrument.knowledge_ingestion`,
:mod:`instrument.code_ingestion`, :mod:`instrument.quality_ingestion`,
:mod:`instrument.policy_ingestion`, :mod:`instrument.story_ingestion`,
:mod:`instrument.review_ingestion`, :mod:`instrument.ledger_ingestion`,
:mod:`instrument.observation_ingestion`, :mod:`instrument.actuation_ingestion`)
ends in the same mechanical tail: compute the canonical ``entity_id``, build a
:class:`~instrument.knowledge.KnowledgeRecord` with *placeholder* derived identities, serialize
it to the durable per-record artifact, hash those bytes, and then *back-fill* the derived
``content_hash`` and ``knowledge_id``. That ordering is correctness-sensitive — the derived
identities and the volatile timestamps must never be part of the bytes ``content_hash`` covers,
or the hash becomes self-referential / re-derivation-dependent and producer idempotence breaks.
Before this module existed, the ~25-line back-fill dance was copy-pasted into all nine producers,
so a tenth producer was one silent mistake away from breaking identity for the whole corpus.

This module owns that invariant **once**. :func:`build_record` is the single choke point; each
producer keeps only its own *derivation* (how it maps its input to ``text`` + structured fields)
and calls the factory. :func:`record_to_artifact` lives here too (it is the serialization half of
the hash-input ordering), so the blanking rule and the builder that relies on it cannot drift
apart.

Design: ``docs/review/restructure.md`` R1 ("a single RecordBuilder factory — kill the 9-copy
boilerplate").
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import fields as _dataclass_fields
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from .knowledge import (
    Authority,
    KnowledgeRecord,
    compute_entity_id,
    compute_knowledge_id,
)

#: The set of field names a :class:`~instrument.knowledge.KnowledgeRecord` accepts, computed once
#: so :func:`build_record` can reject a mistyped ``extra_fields`` key loudly instead of silently
#: dropping it (a dropped field would change the hash without changing the intended record).
_RECORD_FIELDS = frozenset(f.name for f in _dataclass_fields(KnowledgeRecord))


def _now_iso(now: datetime | None = None) -> str:
    """Return ``now`` (or the current UTC instant) as an ISO-8601 timestamp.

    Injectable so tests can pin timestamps; production always uses the real clock. This is the
    single definition every producer imports — previously re-declared verbatim in all nine.
    """
    return (now or datetime.now(timezone.utc)).isoformat()


def _sha256_bytes(data: bytes) -> str:
    """Return the sha256 hex digest of raw bytes (the artifact-hash primitive).

    ``compute_content_hash`` in :mod:`instrument.knowledge` hashes *str*; the durable artifact is
    bytes, so this byte-level hash is what ``content_hash`` must equal.
    """
    return hashlib.sha256(data).hexdigest()


def record_to_artifact(record: KnowledgeRecord) -> bytes:
    """Serialize ``record`` to its durable per-record artifact bytes.

    This is the JSON serialization of ``record.to_dict()`` with stable (sorted) key ordering.
    Five *non-content* fields are blanked so the artifact is a pure function of the **stable**
    record content, and ``content_hash = sha256(artifact)`` is therefore reproducible:

    * ``knowledge_id`` / ``content_hash`` — the two derived identities. Blanking them avoids a
      self-referential hash (``content_hash`` covers the artifact; ``knowledge_id`` folds
      ``content_hash``).
    * ``valid_from`` / ``observed_at`` / ``indexed_at`` — the volatile observation/indexing
      timestamps (producer wall-clock). Excluding them makes ``content_hash`` — and thus
      ``knowledge_id`` — **stable across re-derivations**, which is exactly what makes the
      producer idempotent: the same input always yields the same id, so a re-run skips it.

    The real values travel in the pointer event (ids) or are reconstructed from it (timestamps)
    by ``knowledge_ingestion.extract_record``; every *stable* field survives the round trip.
    """
    data = record.to_dict()
    data["knowledge_id"] = ""
    data["content_hash"] = ""
    data["valid_from"] = ""
    data["observed_at"] = ""
    data["indexed_at"] = ""
    return json.dumps(data, sort_keys=True).encode("utf-8")


def build_record(
    *,
    source_type: str,
    source_uri: str,
    logical_locator: str,
    repository_id: str,
    revision: str,
    authority: Authority,
    evidence_class: str,
    text: str,
    extra_fields: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> KnowledgeRecord:
    """Build ONE :class:`~instrument.knowledge.KnowledgeRecord`, owning the hash-input ordering.

    This is the single place the canonical identity contract is applied end-to-end:

    * ``entity_id``    — ``sha256(repository_id | source_uri | logical_locator)``.
    * ``content_hash`` — ``sha256(record_to_artifact(record))`` (the durable per-record JSON
      artifact, with the derived ids + volatile timestamps blanked).
    * ``knowledge_id`` — ``sha256(entity_id | revision | content_hash | extractor_version)``,
      where ``extractor_version`` is read from ``extra_fields`` (each producer supplies its own
      generation literal).

    ``revision`` is the ``source_revision`` folded into ``knowledge_id``. The record's
    ``commit_sha`` field defaults to ``revision`` (``commit_sha`` *is* the ``source_revision`` for
    repository-backed units) but may be overridden via ``extra_fields`` — the handful of
    producers whose records carry no commit of their own (``review``/``observation``/``flag``/
    ``actuation``) pass ``commit_sha=""`` while still folding their ``REVISION_FALLBACK`` marker
    through ``revision``.

    ``extra_fields`` carries the per-producer structured surface that the factory's defaults do
    not cover (``extractor_version``, ``worktree_id``, ``observed_at``, ``language``, ``symbols``,
    ``outcome_id``, ``test_executed_success``, ``confidence``, ``perturbation_strength``,
    ``causes``, ``acl_scope``, ...). Unknown keys raise ``ValueError`` rather than being silently
    dropped — a mistyped field name must not change the hashed content invisibly.

    Because every producer funnels through this one function, byte-identity is preserved by
    construction: the same ``(source_type, source_uri, logical_locator, repository_id, revision,
    authority, evidence_class, text, extra_fields, now)`` yields the exact same
    ``entity_id``/``content_hash``/``knowledge_id`` as the pre-refactor nine-copy builders
    produced — no re-keying.
    """
    extra = dict(extra_fields or {})
    # Reject typos loudly: a dropped field would silently alter the hashed artifact.
    unknown = set(extra) - _RECORD_FIELDS
    if unknown:
        raise ValueError(f"unknown KnowledgeRecord field(s) in extra_fields: {sorted(unknown)}")

    ts = _now_iso(now)
    entity_id = compute_entity_id(repository_id, source_uri, logical_locator)

    # The common surface every producer shares. `commit_sha` defaults to `revision`; the fields a
    # producer genuinely varies are supplied via `extra_fields` (applied after these defaults).
    fields: dict[str, Any] = {
        "knowledge_id": "",  # back-filled below (folds content_hash)
        "entity_id": entity_id,
        "source_uri": source_uri,
        "source_type": source_type,
        "logical_locator": logical_locator,
        "repository_id": repository_id,
        "branch": "",
        "worktree_id": "",
        "commit_sha": revision,
        "content_hash": "",  # back-filled below (sha256 of the artifact)
        "extractor_version": "",
        "embedding_version": "",
        "authority": authority,
        "valid_from": ts,
        "valid_to": None,
        "observed_at": ts,
        "indexed_at": ts,
        "acl_scope": "public",
        "contains_sensitive_data": False,
        "text": text,
        "token_count": max(1, len(text.split())),
        "language": "",
        "symbols": [],
        "outcome_id": "",
        "test_executed_success": None,
        "evidence_class": evidence_class,
        "confidence": None,
        "perturbation_strength": None,
        "causes": None,
        "supersedes": None,
    }
    fields.update(extra)
    extractor_version = fields["extractor_version"]

    record = KnowledgeRecord(**fields)
    content_hash = _sha256_bytes(record_to_artifact(record))
    knowledge_id = compute_knowledge_id(
        entity_id, revision, content_hash, extractor_version
    )
    return replace(record, content_hash=content_hash, knowledge_id=knowledge_id)
