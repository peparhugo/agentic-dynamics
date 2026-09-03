"""Producer-side session-record derivation for the self-knowledge layer (loop 2).

The session spine's record TYPE (phase ``s1a_session_record_type`` of the
``self_knowledge_layer`` workflow, design ``docs/designs/proposed/self_knowledge_layer.md``).
A session record is the machine's own posterior about a session of itself operating: what
waves ran, what merged, what got parked, the open threads, and the AIO's self-notes on what it
got wrong. Open retrieves the LAST close (s1c); close writes its own (s1b); this module is the
record type both ride on.

``source_type`` is ``"meta_session"`` — the SAME type the ledger's embryonic per-attempt lines
carry (27 rows, all 2026-08-19, verified at the s0 pin). This is deliberate, not a collision:
the source-type vocabulary is one table (``knowledge.SOURCE_TYPES``), and the two families are
disambiguated exactly the way the schema disambiguates every other reuse — by
``extractor_version`` (``session/v1`` here vs ``ledger/v1`` on the legacy lines) and by the URI
family (``session:<slug>`` here vs ``meta_session:<attempt_id>`` there), so no spine record can
ever collide with a legacy attempt on ``entity_id`` or ``knowledge_id`` even for an identical
slug. The legacy shape (inspected at the s0 pin: ``attempt <id> [meta_session]: tokens=…
cost=… confidence=…``, carried in ``text`` with ``confidence=None``) carries NONE of the spine
content; this record carries the structured session body instead.

The record's body (``text``) is a canonical JSON payload of the session's content fields —
``{session_date, slug, waves_run[], merged[], parked[], open_threads[], self_notes}`` plus the
record's ``actor`` and ``scope``, serialized with sorted keys so the same input always yields the
same bytes. A deterministic body is what makes the producer rerun-safe: the shared factory's
``content_hash = sha256(record_to_artifact(record))`` and therefore ``knowledge_id`` are pure
functions of that body plus the stable identity, never of the wall-clock.

Actor + scope follow the context abstraction (design §actor-layering): the producer is the AIO
and the record lives in the AIO's org-root scope. The KB record schema has no ``actor`` field, so
the actor travels in the payload (matching the ``aio_emission`` precedent of an emitter marker in
the body), and the scope is carried twice for determinism: structurally on the record
(``repository_id`` = the org id, ``acl_scope`` = ``org:<repository_id>``) AND in the payload's
``scope`` key. The scope value is chosen so the record is structurally invisible to every other
reader: a cell/workload retrieval filters on its OWN ``repository_id`` (``retrieval.scope_excluded``
hard pre-filter) and ``agentic-dynamics`` never equals a ``self-*`` cell scope; the graph
traversal ACL requires ``repository_id`` AND ``acl_scope`` equality, and the corpus's ``public``
acl rows never match ``org:agentic-dynamics``. Only a reader that explicitly asks for the AIO
org-root scope resolves these records.

Contract reuse: identical to the other producers — :func:`record_factory.build_record`
(identity + content-hash back-fill) + ``record_to_artifact``/``record_to_event`` from
:mod:`knowledge_ingestion`. The record carries the standard identity + artifact + event and
round-trips through ``extract_record`` like every other producer's.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field as _dataclass_field
from datetime import datetime
from pathlib import Path
from typing import Any

from agentic_dynamics.knowledge.knowledge import (
    Authority,
    KnowledgeRecord,
)
from agentic_dynamics.knowledge.knowledge_ingestion import REPOSITORY_ID
from agentic_dynamics.knowledge.record_factory import build_record as build_record_from_parts

# ── Extractor contract constants ────────────────────────────────

#: ``source_type`` recorded on every session record — the SAME type the embryonic ledger
#: ``meta_session`` lines carry (knowledge.SOURCE_TYPES registers it as an observation-family
#: ADVISORY/[H] type). The spine family is disambiguated from the legacy lines by
#: ``extractor_version`` + the URI family, never by a fork in the type vocabulary.
SOURCE_TYPE = "meta_session"

#: The extractor generation. ``knowledge_id`` folds this in, so this family is identity-distinct
#: from the ledger's ``ledger/v1`` meta_session lines even for byte-identical bodies. It is a
#: literal, not a version probe — stability is the point.
EXTRACTOR_VERSION = "session/v1"

#: The producer/actor of every session record. The AIO is the only actor that closes a session;
#: the value travels in the payload so the record is self-describing (the KB schema has no
#: ``actor`` field — see the module docstring).
ACTOR = "aio"

#: Fallback ``source_revision`` for a session record. The record is the AIO's org-root posterior,
#: NOT bound to any one commit — folding the checkout HEAD in as ``revision`` would re-key a
#: close every time HEAD moves, breaking rerun-safety across a session boundary. Mirrors
#: ``observation_ingestion.REVISION_FALLBACK`` for the same reason.
REVISION_FALLBACK = "session/unrevisioned"

#: The seven session content fields the design names (design §record types 1, and the wave's
#: s1a deliverable). The record's body is exactly this content plus ``actor``/``scope``.
CONTENT_FIELDS = (
    "session_date",
    "slug",
    "waves_run",
    "merged",
    "parked",
    "open_threads",
    "self_notes",
)

#: The four list-valued content fields (``waves_run``/``merged``/``parked``/``open_threads``).
#: Missing/empty inputs normalize to ``[]`` — a session that ran nothing and parked nothing is
#: still a session — and non-str elements are coerced so the body is always JSON-serializable.
LIST_FIELDS = frozenset({"waves_run", "merged", "parked", "open_threads"})


# ── Scope helpers (the AIO org-root scope) ──────────────────────


def aio_acl_scope(repository_id: str = REPOSITORY_ID) -> str:
    """Return the AIO org-root acl scope a session record lives in.

    ``org:<repository_id>`` names the org root (the repository) with its scope type, so a reader
    sees at a glance where the record lives and no corpus row — whose ``acl_scope`` is
    ``"public"`` — can ever collide with it under the graph traversal ACL (which requires
    ``repository_id`` AND ``acl_scope`` equality). Cell/workload retrievals filter on their own
    ``repository_id`` and are excluded by ``retrieval.scope_excluded`` (``agentic-dynamics`` never
    equals a ``self-*`` cell scope). Only an explicit AIO org-root read resolves the record.
    """
    return f"org:{repository_id}"


# ── Small deterministic helpers ─────────────────────────────────


def _content_value(session: dict[str, Any], field: str) -> str:
    """Return a required string content field, stripping whitespace.

    Raises ``ValueError`` when the field is missing or empty — a session record with no ``slug``
    (its logical identity) or no ``session_date`` (its place on the spine) cannot be registered.
    """
    value = str(session.get(field) or "").strip()
    if not value:
        raise ValueError(f"session has no {field!r} — cannot derive a stable session record")
    return value


def _list_value(session: dict[str, Any], field: str) -> list[str]:
    """Normalize a list-valued content field to a deterministic ``list[str]``.

    ``None``/missing → ``[]`` (an empty list is the honest rendering of "nothing ran/merged");
    a ``list``/``tuple`` is kept in CALLER order (``waves_run`` is chronological — re-sorting it
    would silently corrupt the story the session is telling) with each element coerced to ``str``
    so a JSON body is guaranteed. A bare string is treated as one item, not split.
    """
    value = session.get(field)
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


# ── The canonical content payload ───────────────────────────────


def session_payload(
    session: dict[str, Any], *, repository_id: str = REPOSITORY_ID
) -> dict[str, Any]:
    """Return the canonical content payload for ONE session record.

    Exactly the seven content fields (normalized) plus ``actor`` and ``scope`` — the record's
    context-abstraction dimensions (design §actor-layering). ``scope`` mirrors the record's own
    ``acl_scope`` (``aio_acl_scope(repository_id)``) so the payload and the record field can never
    drift apart, and ``actor`` is the module's ``ACTOR`` literal. This dict is what ``text``
    serializes (sorted keys), so it is the entire hashed body: two derivations of the same session
    dict yield byte-identical bodies and therefore identical ids (rerun-safe), while a changed
    wave list yields a new body and a new ``knowledge_id`` for the same ``entity_id``.
    """
    payload: dict[str, Any] = {
        "session_date": _content_value(session, "session_date"),
        "slug": _content_value(session, "slug"),
    }
    for field in sorted(LIST_FIELDS):
        payload[field] = _list_value(session, field)
    payload["self_notes"] = str(session.get("self_notes") or "")
    payload["actor"] = ACTOR
    payload["scope"] = aio_acl_scope(repository_id)
    return payload


# ── Record construction ─────────────────────────────────────────


def build_session_record(
    session: dict[str, Any],
    *,
    repository_id: str = REPOSITORY_ID,
    now: datetime | None = None,
) -> KnowledgeRecord:
    """Derive ONE ``source_type=meta_session`` session-spine record from a session dict.

    ``session`` is the synthetic/real close payload: ``{session_date, slug, waves_run[],
    merged[], parked[], open_threads[], self_notes}`` (the list fields optional). The record's
    ``text`` is the canonical JSON body from :func:`session_payload` — deterministic, so the
    factory's ``content_hash``/``knowledge_id`` are rerun-safe for identical input.

    Identity follows the canonical contract in :mod:`knowledge`:

    * ``logical_locator`` is the ``slug`` and ``source_uri`` is ``session:<slug>`` — a family
      distinct from the legacy ``meta_session:<attempt_id>`` lines, so the spine never collides
      with an embryonic attempt on ``entity_id`` even for a matching string.
    * ``revision`` is :data:`REVISION_FALLBACK` (the record is not bound to one commit; folding
      HEAD in would break rerun-safety across session boundaries).
    * ``entity_id = sha256(repository_id | source_uri | logical_locator)``; ``content_hash`` is
      the sha256 of the durable artifact; ``knowledge_id`` folds them with the revision + the
      ``session/v1`` extractor. Re-closing the same session with the same body is a no-op; a
      changed body re-keys ``knowledge_id`` while ``entity_id`` holds (a new version of the same
      session slot, exactly what a ``supersede``-capable spine needs).

    ``authority`` is ``ADVISORY`` / ``[H]`` — the registered nominal for ``meta_session``: a
    session close is the AIO's own account of its session (self-reported), never an independent
    measurement, so it can inform the next session but never override a MEASURED ledger row.
    ``repository_id`` defaults to the org id and ``acl_scope`` to the AIO org-root scope (see
    :func:`aio_acl_scope`). ``observed_at`` is the session's own date — the real "when this
    happened" — while ``valid_from``/``indexed_at`` stay the derivation/consumer clocks.

    Raises ``ValueError`` when the session carries no ``slug`` or no ``session_date``.
    """
    payload = session_payload(session, repository_id=repository_id)
    slug = payload["slug"]
    scope = aio_acl_scope(repository_id)

    return build_record_from_parts(
        source_type=SOURCE_TYPE,
        source_uri=f"session:{slug}",
        logical_locator=slug,
        repository_id=repository_id,
        revision=REVISION_FALLBACK,
        authority=Authority.ADVISORY,
        evidence_class="[H]",
        text=json.dumps(payload, sort_keys=True),
        extra_fields={
            # The session record is not tied to a commit of its own — mirror the observation
            # producer, which passes commit_sha="" while folding its revision marker through the
            # `revision` input (record_factory's contract).
            "commit_sha": "",
            "extractor_version": EXTRACTOR_VERSION,
            "acl_scope": scope,
            # observed_at is the session's own date (when the session HAPPENED), not the close
            # wall-clock; the artifact blanks it, so it never perturbs the rerun-safe content hash.
            "observed_at": payload["session_date"],
        },
        now=now,
    )


def derive_session_record(
    session: dict[str, Any],
    *,
    repository_id: str = REPOSITORY_ID,
    now: datetime | None = None,
) -> KnowledgeRecord:
    """Public derivation entry point — delegates to :func:`build_session_record`.

    Deliberately singular (like ``observation_ingestion.derive_observation_record``): one session
    close always yields exactly one session record, with no batch pre-filter case. A session
    missing its ``slug``/``session_date`` is a genuine caller error, not a skip case.
    """
    return build_session_record(session, repository_id=repository_id, now=now)


# ── Close emission (s1b — the ``session close`` command's write seam) ─────────


@dataclass
class SessionCloseResult:
    """What one :func:`close_session` call did — the ``session close`` command's outcome.

    ``record`` is the derived session record (always present — derivation happens before any
    store access, so a call site can cite its ``knowledge_id`` even when every publish path
    failed). ``artifact_path`` is the durable per-record artifact the call wrote (or confirmed
    already present). ``entry_id`` is the stream entry the pointer event landed on, or ``""``
    when nothing was published by this call.

    ``status`` is one of:

    * ``"closed"`` — the record now fully lands in the KB: its durable artifact is written and
      its pointer event was published this call (including the repair of a prior partial close,
      where the artifact existed but the event had never landed).
    * ``"no-op"`` — re-running close for an already-closed session: the exact record (identical
      bytes) was already durable AND its event was already checkpointed, so this call changed
      nothing (rerun-safe).
    * ``"degraded"`` — the durable artifact is written but the event could not be published or
      its prior publication could not be confirmed (a downed or rejecting knowledge stream).
      This is a WARNING, never a crash: ``warnings`` carries the reason, and re-running close
      once the stream is back completes the publication.

    ``warnings`` lists every producer failure this call swallowed (empty on a clean path).
    """

    record: KnowledgeRecord
    status: str
    artifact_path: Path
    entry_id: str = ""
    warnings: list[str] = _dataclass_field(default_factory=list)


def close_session(
    session: dict[str, Any],
    *,
    repository_id: str = REPOSITORY_ID,
    artifact_dir: Path | None = None,
    connect_fn: Callable[..., Any] | None = None,
    now: datetime | None = None,
) -> SessionCloseResult:
    """Close ONE session: derive its record, land artifact + event in the KB, best-effort.

    This is the write seam of the ``agentic-dynamics session close`` command (phase
    ``s1b_close_writer`` of the ``self_knowledge_layer`` wave, design
    ``docs/designs/proposed/self_knowledge_layer.md``). It follows the producers' canonical
    pointer contract exactly as ``scripts/kb_produce.py`` does — write the durable per-record
    artifact to ``<artifact_dir>/<knowledge_id>.json`` FIRST (so a consumer can read + verify
    the bytes the event's ``content_hash`` covers the moment the pointer lands), then publish
    the pointer event and checkpoint the ``knowledge_id``.

    **Rerun-safe no-op.** ``knowledge_id`` is a pure function of the session body (s1a), so a
    repeated close of the same session resolves to the same record. The close is a no-op when
    the artifact is already on disk with byte-identical content AND the ``knowledge_id`` is
    already checkpointed (its event was published); a prior partial failure (artifact written,
    event never published) is REPAIRED by re-running close — the event is published and the
    record reaches ``"closed"``. ``checkpoint`` reuse matches ``kb_produce``: the
    ``CHECKPOINT_KEY`` hash is the producers' shared idempotence ledger, and session records
    keyed by a globally-unique ``knowledge_id`` cannot collide with any other family's rows.

    **A producer failure is a warning, never a crash.** A downed or rejecting knowledge stream
    is caught, logged into ``warnings``, and reported as ``status="degraded"`` — the durable
    artifact still lands (the record is never lost), and re-running the close when the stream
    is back completes the publication. This is the one deliberate divergence from
    ``kb_produce``'s fail-fast connect: closing a session sits at the end of the AIO's
    operating cadence, where a loud crash would discard the very reflection the close exists
    to persist.

    ``artifact_dir`` defaults to the repo's durable KB artifact directory
    (``core.paths.KB_ARTIFACT_DIR``); ``connect_fn`` defaults to ``knowledge_stream.connect``.
    Both are injectable so tests can point at a tmp dir + a fake stream and so the command is
    import-safe without Redis.
    """
    from agentic_dynamics.core.paths import KB_ARTIFACT_DIR
    from agentic_dynamics.knowledge import knowledge_stream as ks
    from agentic_dynamics.knowledge.knowledge_ingestion import (
        record_to_artifact,
        record_to_event,
    )

    record = derive_session_record(session, repository_id=repository_id, now=now)
    artifact_dir = artifact_dir or KB_ARTIFACT_DIR
    artifact_path = artifact_dir / f"{record.knowledge_id}.json"
    artifact_bytes = record_to_artifact(record)
    warnings: list[str] = []
    already_durable = artifact_path.is_file() and artifact_path.read_bytes() == artifact_bytes

    # 1 ── durable artifact first: a consumer can verify the bytes the pointer names as soon as
    # the event lands. Rewriting byte-identical bytes is harmless, but skip it to keep the
    # no-op path truly side-effect-free.
    if not already_durable:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_path.write_bytes(artifact_bytes)

    # 2 ── pointer event, best-effort. The write guard is satisfied with authorized=True (this
    # seam IS the AIO's authorized close writer); the checkpoint hash makes the publish
    # idempotent so a re-close never double-emits.
    connect = connect_fn or ks.connect
    entry_id = ""
    already_published = False
    try:
        r = connect()
    except Exception as exc:  # noqa: BLE001 - a producer failure is a warning by contract
        warnings.append(
            f"knowledge stream unreachable ({type(exc).__name__}: {exc}); the durable record "
            "is written but the pointer event was not published — re-run `session close` once "
            "the stream is back to complete it"
        )
        r = None
    if r is not None:
        try:
            if r.hget(ks.CHECKPOINT_KEY, record.knowledge_id) is None:
                entry_id = ks.publish_event(
                    r,
                    record_to_event(record),
                    authorized=True,
                    source_type=record.source_type,
                )
                r.hset(ks.CHECKPOINT_KEY, record.knowledge_id, record.indexed_at)
            else:
                already_published = True
        except Exception as exc:  # noqa: BLE001 - a producer failure is a warning by contract
            warnings.append(
                f"publish failed for {record.knowledge_id} ({type(exc).__name__}: {exc}); "
                "re-run `session close` once the stream is healthy to complete it"
            )

    if already_durable and already_published and not warnings:
        status = "no-op"
    elif warnings:
        status = "degraded"
    else:
        status = "closed"
    return SessionCloseResult(
        record=record,
        status=status,
        artifact_path=artifact_path,
        entry_id=entry_id,
        warnings=warnings,
    )
