"""Producer-side session-record derivation for the self-knowledge layer (loop 2).

The session spine's record TYPE (phase ``s1a_session_record_type`` of the
``self_knowledge_layer`` workflow, design ``docs/designs/proposed/self_knowledge_layer.md``).
A session record is the machine's own posterior about a session of itself operating: what
waves ran, what merged, what got parked, the open threads, and the AIO's self-notes on what it
got wrong. Open retrieves the LAST close (s1c); close writes its own (s1b); this module is the
record type both ride on — the write seam (:func:`close_session`) and the read seam
(:func:`open_session`, the ``session open`` command's retrieval).

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

import contextlib
import hashlib
import json
import os
import tempfile
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
    if session.get("close_seq") is not None:
        payload["close_seq"] = int(session["close_seq"])
    payload["actor"] = ACTOR
    payload["scope"] = aio_acl_scope(repository_id)
    return payload


# ── Record construction ─────────────────────────────────────────


def _session_prose_summary(session: dict[str, Any], payload: dict[str, Any]) -> str:
    """A retrieval-facing prose summary of a session close (F3, deep review 2026-09-04).

    The AIO's continuity queries are prose ("what did the last session decide, what merged,
    what was parked") — a pure JSON blob embeds poorly against them. The summary leads with
    the human meaning and appends the canonical JSON for structured consumers.
    """
    slug = str(session.get("slug") or payload.get("slug") or "")
    date = str(session.get("session_date") or payload.get("session_date") or "")
    merged = payload.get("merged") or []
    parked = payload.get("parked") or []
    threads = payload.get("open_threads") or []
    notes = str(payload.get("self_notes") or "")
    parts = [f"session close {date} ({slug}):"]
    if merged:
        parts.append(f"merged {len(merged)}: " + "; ".join(str(m) for m in merged[:5]))
    if parked:
        parts.append("parked: " + "; ".join(str(p) for p in parked[:5]))
    if threads:
        parts.append("open threads: " + "; ".join(str(t) for t in threads[:5]))
    if notes:
        parts.append(f"self-notes: {notes[:300]}")
    summary = " ".join(parts)
    return summary + " || json: " + json.dumps(payload, sort_keys=True)


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
        # F3 fix (deep review 2026-09-04): a pure JSON blob embeds poorly against prose
        # queries ("session continuity AIO" returned zero session records). Prepend a
        # retrieval-facing prose summary so the record is findable BY MEANING, not only by
        # id — the AIO's continuity queries are prose, and the spine must answer them.
        text=_session_prose_summary(session, payload),
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

    artifact_dir = artifact_dir or KB_ARTIFACT_DIR
    session = dict(session)
    session["close_seq"] = _close_sequence_number(
        session.get("session_date") or "", session.get("slug") or "", artifact_dir
    )
    record = derive_session_record(session, repository_id=repository_id, now=now)
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


# ── Open retrieval (s1c — the ``session open`` command's read seam) ─────────


def session_artifact_files(artifact_dir: Path) -> list[Path]:
    """Every ``*.json`` file under the durable artifact dir, in filename order.

    The artifact dir is shared by EVERY producer (19k+ records), so this is a *scan*, not a
    read of one known file: the session spine family is found by content, never by guessable
    filename. The filename order is the deterministic base scan; the resolver re-orders below.
    A missing dir (a fresh checkout with no KB yet) is simply empty — the first-session state.
    """
    if not artifact_dir.is_dir():
        return []
    return sorted(artifact_dir.glob("*.json"), key=lambda path: path.name)


_ARTIFACT_RECORD = "record"
_ARTIFACT_FOREIGN = "foreign"
_ARTIFACT_ANOMALY = "anomaly"


def _classify_session_artifact(
    path: Path, *, repository_id: str = REPOSITORY_ID
) -> tuple[str, dict[str, Any] | None, dict[str, Any] | None]:
    """Classify ONE durable artifact file into ``(kind, artifact_fields, payload)``.

    The kind is one of:

    * ``"record"`` — an AIO org-root session-spine record: ``(artifact, payload)`` is returned.
    * ``"foreign"`` — NOT a session-spine record of this org scope: any other producer's
      artifact (the ``extractor_version`` discriminator — the legacy ledger ``meta_session``
      lines are ``ledger/v1`` and never match), a record from another repository (the scope
      pre-filter), or an undecodable file. Skipped silently — the artifact dir holds every
      producer's rows and only the spine family in THIS org is a candidate for ``session open``.
    * ``"anomaly"`` — IS a ``session/v1`` artifact of this org but is NOT a readable AIO
      org-root record: a corrupt spine artifact (a truncated close) or a record whose body
      ``actor``/``scope`` are not the AIO's (the body keys travel in the payload so the record
      is self-describing). Surfaced as a warning — an honest signal, never a silent skip.
    """
    try:
        raw = path.read_bytes()
    except OSError:
        return _ARTIFACT_FOREIGN, None, None
    try:
        artifact = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return _ARTIFACT_FOREIGN, None, None
    if not isinstance(artifact, dict):
        return _ARTIFACT_FOREIGN, None, None
    if artifact.get("extractor_version") != EXTRACTOR_VERSION:
        return _ARTIFACT_FOREIGN, None, None
    if artifact.get("repository_id") != repository_id:
        # A session/v1 record of ANOTHER repository: legitimately not ours, skipped silently
        # (a cell/workload repository never equals the org id — a shared-dir neighbor is not
        # this read's business and warning on it would be noise at every scan).
        return _ARTIFACT_FOREIGN, None, None
    text = artifact.get("text")
    if not isinstance(text, str):
        return _ARTIFACT_ANOMALY, None, None
    # F3 fix (deep review 2026-09-04): the record text is now a prose+JSON hybrid — the
    # prose leads (retrieval embeds it) and the canonical JSON follows the separator.
    # Parse the JSON suffix; tolerate a pure-JSON text (pre-fix records) unchanged.
    if " || json: " in text:
        text = text.split(" || json: ", 1)[1]
    try:
        payload = json.loads(text)
    except ValueError:
        return _ARTIFACT_ANOMALY, None, None
    if not isinstance(payload, dict):
        return _ARTIFACT_ANOMALY, None, None
    if payload.get("actor") != ACTOR:
        return _ARTIFACT_ANOMALY, None, None
    if payload.get("scope") != aio_acl_scope(repository_id):
        return _ARTIFACT_ANOMALY, None, None
    return _ARTIFACT_RECORD, artifact, payload


def parse_session_artifact(
    path: Path, *, repository_id: str = REPOSITORY_ID
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Parse ONE durable artifact file into ``(artifact_fields, payload)``.

    ``artifact_fields`` is the parsed durable record (the on-disk rows blank
    ``knowledge_id``/``content_hash``/volatile clocks — see :func:`close_session`), with
    ``payload`` the decoded content body (``text``) that carries the seven session fields plus
    ``actor``/``scope``.

    Returns ``None`` — the file is SKIPPED, never an error — when it is not a readable AIO
    org-root session-spine record (:func:`_classify_session_artifact`'s ``foreign`` and
    ``anomaly`` kinds; callers who need the distinction use the classifier directly).

    The read is a DIRECT read of the durable artifact — the same store ``close_session``
    writes and every consumer verifies — never the registry projection, which requires a live
    consumer: the round-trip (close then open) must be exact the moment the close lands, with
    no kb-registry-v1 dependency.
    """
    kind, artifact, payload = _classify_session_artifact(path, repository_id=repository_id)
    if kind != _ARTIFACT_RECORD:
        return None
    return artifact, payload


def scan_session_records(
    *, repository_id: str = REPOSITORY_ID, artifact_dir: Path | None = None
) -> tuple[list[tuple[Path, dict[str, Any], dict[str, Any]]], list[str]]:
    """Scan the durable artifact dir for every AIO org-root session record.

    Returns ``(triples, warnings)`` where each triple is ``(path, artifact_fields, payload)``
    for one session-spine record in the requested org scope, and ``warnings`` names the
    ``session/v1`` artifacts of this org that are NOT readable AIO org-root records (the
    classifier's ``anomaly`` kind — a corrupt spine artifact or a foreign-actor record).
    ``artifact_dir`` defaults to the repo's durable KB artifact directory
    (``core.paths.KB_ARTIFACT_DIR``).
    """
    from agentic_dynamics.core.paths import KB_ARTIFACT_DIR

    artifact_dir = artifact_dir or KB_ARTIFACT_DIR
    warnings: list[str] = []
    triples: list[tuple[Path, dict[str, Any], dict[str, Any]]] = []
    for path in session_artifact_files(artifact_dir):
        kind, artifact, payload = _classify_session_artifact(path, repository_id=repository_id)
        if kind == _ARTIFACT_RECORD:
            triples.append((path, artifact, payload))
        elif kind == _ARTIFACT_ANOMALY:
            warnings.append(
                f"{path.name}: a session/v1 artifact that is not a readable AIO org-root "
                "session record — excluded from the spine read"
            )
    return triples, warnings


def _close_sequence_number(session_date: str, slug: str, artifact_dir: Path) -> int:
    """Content-stable ordering within one session-date: how many OTHER session slots have
    closed that day already.

    The spine's content blanks wall clocks, so two DISTINCT sessions closing the same day
    cannot be ordered by content (the 2026-09-08 open_session regression: the lexicographic
    slug tiebreak picked the morning session over the afternoon's). ``close_seq`` = 1 + the
    number of same-date records with a DIFFERENT slug stamps close-order into the content:
    distinct sessions increase it, while a re-close of the SAME slug keeps its own sequence
    (preserving the rerun-safe no-op — the body is unchanged, so the id is unchanged).
    """
    if not session_date or not slug:
        return 1
    from agentic_dynamics.core.paths import KB_ARTIFACT_DIR

    artifact_dir = artifact_dir or KB_ARTIFACT_DIR
    try:
        peers = 0
        for path in session_artifact_files(artifact_dir):
            try:
                _kind, _artifact, payload = _classify_session_artifact(
                    path, repository_id=REPOSITORY_ID
                )
            except Exception:
                continue
            # The 2026-09-13 repair: the KB dir is a MIXED artifact dir, and a non-session
            # artifact classifies to a payload that is not a dict. The unguarded ``payload.get``
            # below raised here — caught by the OUTER try — so every same-day close got
            # ``close_seq = 1`` and ordering fell back to the lexicographic slug. The guard
            # must live INSIDE the per-artifact try, where the classifier's own failure is
            # already the skip signal.
            if not isinstance(payload, dict):
                continue
            if (
                str(payload.get("session_date") or "") == session_date
                and str(payload.get("slug") or "") != slug
            ):
                peers += 1
        return peers + 1
    except Exception:
        return 1


def _selection_key(
    triple: tuple[Path, dict[str, Any], dict[str, Any]],
) -> tuple[str, str, float, str]:
    """Deterministic "most recent close" ordering over one session-spine artifact triple.

    The spine's time axis is the SESSION's own date (the record deliberately stamps
    ``session_date``, and the artifact blanks volatile clocks so its bytes are rerun-safe), so
    content — never the filesystem wall-clock alone — orders the candidates: greatest
    ``session_date`` first. Within a date the ``slug`` tie-breaks deterministically (two
    sessions closed the same day cannot be ordered by content — lexicographic slug order is
    the documented, checkout-stable resolution), and within the same session slot (re-close of
    a changed body) the newer write — file mtime, then the content-addressed filename — is the
    newer version. This ordering survives a fresh checkout, where git resets every artifact's
    mtime and only content survives.
    """
    _path, artifact, payload = triple
    try:
        mtime = _path.stat().st_mtime
    except OSError:
        mtime = 0.0
    return (
        str(payload.get("session_date") or ""),
        int(payload.get("close_seq") or 0),
        str(payload.get("slug") or ""),
        mtime,
        _path.name,
    )


@dataclass
class SessionOpenResult:
    """What one :func:`open_session` call resolved — the ``session open`` command's outcome.

    ``status`` is one of:

    * ``"opened"`` — a prior close was found and resolved: ``slug`` names the session,
      ``payload`` carries its seven content fields (the opening context), and ``artifact`` /
      ``artifact_path`` / ``knowledge_id`` / ``entity_id`` identify the durable record.
    * ``"bootstrap"`` — NO prior close exists (or none for the requested ``slug``): the
      first-session state. ``payload`` is ``None`` and ``slug`` repeats the requested slug when
      one was given (so a caller can see which session slot came up empty).

    ``requested_slug`` records the optional slug filter the caller asked for (``None`` = the
    default "last session" read). ``candidates`` counts every AIO org-root session record the
    scan found before the slug filter / selection — a "last of N" context for the report.
    ``warnings`` lists the scan's anomalies (see :func:`scan_session_records`).
    """

    status: str
    slug: str | None = None
    payload: dict[str, Any] | None = None
    artifact: dict[str, Any] | None = None
    artifact_path: Path | None = None
    knowledge_id: str | None = None
    entity_id: str | None = None
    requested_slug: str | None = None
    candidates: int = 0
    warnings: list[str] = _dataclass_field(default_factory=list)


def open_session(
    *,
    slug: str | None = None,
    repository_id: str = REPOSITORY_ID,
    artifact_dir: Path | None = None,
) -> SessionOpenResult:
    """Open a session: retrieve the LAST session's close record (or one named session's).

    This is the read seam of the ``agentic-dynamics session open`` command (phase
    ``s1c_open_reader`` of the ``self_knowledge_layer`` wave). The AIO's operating cadence
    closes every session it ends, so opening the next session retrieves its predecessor's
    posterior — decisions, open threads, parked items, self-notes — instead of starting from a
    fresh prior.

    **Direct read, org-scoped.** Candidates are the durable artifacts the s1b close writes
    (``core.paths.KB_ARTIFACT_DIR``), filtered to the AIO org-root spine family
    (``extractor_version`` ``session/v1``, ``repository_id`` the org id, body ``actor``/``scope``
    the AIO's). A cell/workload repository never equals the org id, so this read is exactly the
    explicit org-root read the scope fence reserves to the AIO — it resolves none of a cell's
    records. The registry projection is deliberately NOT consulted: it needs a live consumer,
    and the round-trip (close then open) must be exact the moment the close lands.

    **Resolution.** ``slug=None`` (default) resolves the LAST session — the candidate that
    maximizes ``(session_date, slug, mtime, filename)`` (see :func:`_selection_key`); with a
    ``slug``, the most recent close OF THAT session slot. No candidates (or none matching the
    slug) resolves ``status="bootstrap"`` — the clear first-session state, never an error.
    ``artifact_dir`` defaults to the repo's durable KB artifact directory and is injectable so
    tests can point at a tmp dir.
    """
    from agentic_dynamics.core.paths import KB_ARTIFACT_DIR

    artifact_dir = artifact_dir or KB_ARTIFACT_DIR
    requested = (slug or "").strip() or None
    triples, warnings = scan_session_records(repository_id=repository_id, artifact_dir=artifact_dir)
    candidates = len(triples)
    if requested is not None:
        triples = [triple for triple in triples if str(triple[2].get("slug") or "") == requested]
    if not triples:
        return SessionOpenResult(
            status="bootstrap",
            slug=requested,
            requested_slug=requested,
            candidates=candidates,
            warnings=warnings,
        )
    path, artifact, payload = max(triples, key=_selection_key)
    return SessionOpenResult(
        status="opened",
        slug=str(payload.get("slug") or ""),
        payload=payload,
        artifact=artifact,
        artifact_path=path,
        knowledge_id=path.stem,
        entity_id=artifact.get("entity_id") or "",
        requested_slug=requested,
        candidates=candidates,
        warnings=warnings,
    )


def _bullet_lines(title: str, items: list[str] | None) -> list[str]:
    """Render one list-valued content field as a single indented line (or an explicit none)."""
    items = items or []
    if not items:
        return [f"{title}: — none —"]
    return [f"{title}: {', '.join(items)}"]


def render_opening_context(result: SessionOpenResult) -> str:
    """Render an :class:`SessionOpenResult` as the session's opening context.

    The human rendering the ``session open`` command prints (and the AIO embeds at session
    start): the resolved record's seven content fields — the opening context's decisions
    (merged), open threads, parked items, and self-notes. ``bootstrap`` renders the clear
    first-session message naming the ``session close`` command that makes the next open
    meaningful.
    """
    if result.status != "opened" or result.payload is None:
        if result.slug:
            head = f"No prior close found for session {result.slug!r} — first-session bootstrap."
        else:
            head = "First session — no prior close record in the knowledge base."
        return (
            f"[session-open] {head}\n"
            "  There is no last session to inherit: this session opens from a fresh prior\n"
            "  (no decisions, open threads, parked items, or self-notes yet). When it ends,\n"
            "  run `agentic-dynamics session close` so the next session opens with its context."
        )
    payload = result.payload
    lines = [
        f"[session-open] Last session close: {payload['slug']} ({payload['session_date']})",
        f"  knowledge_id: {(result.knowledge_id or '')[:12]} (artifact {result.artifact_path.name})",
    ]
    for title, key in (
        ("  waves run", "waves_run"),
        ("  merged", "merged"),
        ("  parked", "parked"),
        ("  open threads", "open_threads"),
    ):
        lines.extend(_bullet_lines(title, payload.get(key)))
    notes = str(payload.get("self_notes") or "").strip()
    lines.append(f"  self-notes: {notes if notes else '(none)'}")
    return "\n".join(lines)


# ── Session bindings (aio-session-binding/v1 — Unit C native binding) ──────────
#
# The binding is the durable answer to "which task is THIS native opencode session running,
# from which origin, under which acceptance" — written once, on the session's first substantive
# message, and read by every later capsule request (including after a coordinator restart and
# after compaction). It is NOT a session close: the spine's ``session/v1`` family stays the
# AIO's posterior, and this family is identity/binding state, deliberately distinct — a
# different ``extractor_version``, a different URI family, and a dedicated slot directory so a
# binding can never be mistaken for a close by any reader (``session open`` scans the top-level
# artifact dir and filters on ``session/v1``; bindings live under ``<kb>/aio-bindings/``).
#
# Durability model (the "a process-local map is a cache, not the durable source" rule):
#   * the SLOT file (``<kb>/aio-bindings/<slot_id>.json``) is the operational pointer — its
#     name is a pure function of (family, repository, native session id), so lookup is one
#     deterministic read, never a 19k-artifact scan and never "the newest binding";
#   * the FULL record is the content-addressed KB artifact (``<kb>/<knowledge_id>.json``) built
#     through the shared factory, so the binding carries the standard identity/authority
#     surface and can be cited by ``knowledge_id`` like every other record. A pointer event is
#     published best-effort (same contract as :func:`close_session`: a downed stream is a
#     warning, never a lost binding).
#
# Hardening (reviewer repairs 2026-09-15):
#   * the durable root MUST already exist — the writer never fabricates a store. Missing store
#     is returned to the caller (:data:`BINDING_STATUS_STORE_MISSING`); initialization is the
#     EXPLICIT :func:`init_binding_store` operation. A wrong worktree path therefore cannot
#     silently become "another store";
#   * slot creation is atomic across processes (``O_CREAT|O_EXCL``): exactly one concurrent
#     first write wins ``created``; the loser re-reads and returns the winner's binding. The
#     slot's identity is its NAME — a copied/foreign pointer is refused;
#   * reads verify the full identity chain: slot name ↔ claimed session id, artifact filename
#     ↔ recomputed ``knowledge_id`` (entity_id + artifact sha256 + extractor), payload request
#     hash ↔ original request, and the payload's native session id ↔ the slot's. A modified
#     request or a swapped artifact is ``corrupt``, never ``found``;
#   * the record ``text`` is PURE canonical JSON — no ``" || json: "`` framing — so a request
#     text that happens to contain the legacy separator round-trips byte-exactly;
#   * task context (acceptance / predecessor / work unit / next action / blocker / project /
#     source revision) is versioned: :func:`update_binding_context` requires the caller's
#     expected version, preserves the ORIGINAL request fields, appends a bounded history, and
#     replaces the slot atomically.

#: The binding family's extractor generation. Distinct from ``session/v1`` so no reader —
#: including :func:`open_session`'s scanner — can confuse a binding with a session close.
BINDING_EXTRACTOR_VERSION = "aio-session-binding/v1"

#: Subdirectory of the durable KB artifact dir that holds the binding slots.
BINDING_DIR_NAME = "aio-bindings"

#: The slot-pointer schema id.
BINDING_SLOT_SCHEMA = "aio-session-binding-slot/v1"

#: The binding statuses :class:`BindingResult` may carry.
BINDING_STATUS_FOUND = "found"
BINDING_STATUS_MISSING = "missing"          # the store is present; no binding for this session
BINDING_STATUS_STORE_MISSING = "store_missing"  # the durable root itself is absent
BINDING_STATUS_CREATED = "created"
BINDING_STATUS_EXISTING = "existing"
BINDING_STATUS_UPDATED = "updated"          # an explicit, versioned task-context update
BINDING_STATUS_CORRUPT = "corrupt"          # a slot exists but does not resolve to a binding

#: Acceptance sources. A model-extracted acceptance is ``interpretation`` and MUST carry
#: provenance — it is never promoted to the raw request's standing.
BINDING_ACCEPTANCE_SOURCES = ("raw", "interpretation")

#: The task-context fields a versioned update may change. The ORIGINAL request fields are
#: deliberately absent: no update can replace the request, only the context around it.
BINDING_CONTEXT_FIELDS = (
    "acceptance",
    "predecessor",
    "work_unit",
    "next_action",
    "blocker",
    "project",
    "source_revision",
)

#: Bound on the retained context history (provenance is auditable, not unbounded).
BINDING_CONTEXT_HISTORY = 10

#: The AUTHORIZATION-relevant task fields: changing one of these changes WHAT the AIO is
#: authorized to do, so a pending command minted against the old definition is stale and
#: must be refused. The remaining context fields (``next_action`` / ``blocker``) are
#: OPERATIONAL PROGRESS: routine recording must never invalidate pending work (round-9
#: review — one version represented both, so recording a submission's own ``next_action``
#: invalidated the submission's queued command at its binding-id and revision checks).
AUTHORIZATION_FIELDS = ("acceptance", "predecessor", "work_unit", "project", "source_revision")


def binding_authorization_id(payload: dict[str, Any]) -> str:
    """The binding's AUTHORIZATION identity: derived from its authorization-relevant fields.

    Stable across progress-only updates (``next_action``/``blocker``); changes when the task
    definition (acceptance / work_unit / project / source_revision / predecessor) or the
    session identity changes. The exec gate compares the claimed binding id against THIS —
    never the content-addressed record id, which every update necessarily changes.
    """
    canonical = json.dumps(
        {
            "native_session_id": str(payload.get("native_session_id") or ""),
            "task_identity": str(payload.get("task_identity") or ""),
            "resolved_agent": str(payload.get("resolved_agent") or ""),
            "repository_id": str(payload.get("repository_id") or ""),
            **{field: str(payload.get(field) or "") for field in AUTHORIZATION_FIELDS},
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def binding_authorization_version(payload: dict[str, Any]) -> int:
    """The binding's authorization epoch (fallback: the context version for older bindings).

    Starts at 1 at creation; :func:`update_binding_context` bumps it ONLY when an
    authorization-relevant field actually changes. A progress-only update leaves it (and
    the derived id) untouched, so commands queued against this task stay authorized.
    """
    raw = payload.get("authorization_version")
    if isinstance(raw, int) and not isinstance(raw, bool) and raw >= 1:
        return raw
    return int(payload.get("context_version") or 1)


def binding_slot_id(native_session_id: str, *, repository_id: str = REPOSITORY_ID) -> str:
    """The deterministic slot id for one native session's binding.

    Pure function of (family, repository, native session id) — never wall-clock, never the
    task text — so the durable lookup is one read and a replayed call resolves the same slot.
    """
    key = f"{BINDING_EXTRACTOR_VERSION}\0{repository_id}\0{str(native_session_id).strip()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def binding_slot_path(
    native_session_id: str, *, artifact_dir: Path | None = None, repository_id: str = REPOSITORY_ID
) -> Path:
    """The slot file path for one native session's binding (does not touch the filesystem)."""
    from agentic_dynamics.core.paths import KB_ARTIFACT_DIR

    artifact_dir = artifact_dir or KB_ARTIFACT_DIR
    return artifact_dir / BINDING_DIR_NAME / f"{binding_slot_id(native_session_id, repository_id=repository_id)}.json"


def init_binding_store(artifact_dir: Path) -> Path:
    """EXPLICITLY initialize the binding store (the durable root + the bindings dir).

    The only operation that creates the root. Native binding calls never do — a missing root
    is reported as such, so a wrong worktree path cannot silently start a private store.
    """
    (artifact_dir / BINDING_DIR_NAME).mkdir(parents=True, exist_ok=True)
    return artifact_dir / BINDING_DIR_NAME


def _binding_text(value: Any, *, default: str = "") -> str:
    return str(value if value is not None else default).strip()


def binding_payload(
    binding: dict[str, Any], *, repository_id: str = REPOSITORY_ID
) -> dict[str, Any]:
    """Return the canonical content payload for ONE session binding.

    Raises ``ValueError`` when the binding carries no ``native_session_id`` (its durable key),
    no ``resolved_agent`` (whose session this is), no ``task_identity`` (what it is doing), or
    no ``original_request`` (the fact later "continue" messages must never replace).
    """
    native_session_id = _content_value(binding, "native_session_id")
    resolved_agent = _content_value(binding, "resolved_agent")
    task_identity = _content_value(binding, "task_identity")
    original_request = _content_value(binding, "original_request")

    raw_acceptance = binding.get("acceptance")
    acceptance: dict[str, Any] | None = None
    if isinstance(raw_acceptance, dict) and _binding_text(raw_acceptance.get("text")):
        source = _binding_text(raw_acceptance.get("source")) or "raw"
        if source not in BINDING_ACCEPTANCE_SOURCES:
            raise ValueError(
                f"acceptance source {source!r} is not one of {BINDING_ACCEPTANCE_SOURCES}"
            )
        provenance = _binding_text(raw_acceptance.get("provenance"))
        if source == "interpretation" and not provenance:
            raise ValueError(
                "an acceptance extracted by a model is an interpretation and must carry "
                "provenance (who extracted it, from what) — never promoted to the raw request"
            )
        acceptance = {
            "text": _binding_text(raw_acceptance["text"]),
            "version": int(raw_acceptance.get("version") or 1),
            "source": source,
            "provenance": provenance,
        }

    raw_predecessor = binding.get("predecessor")
    predecessor: dict[str, Any] | None = None
    if isinstance(raw_predecessor, dict) and _binding_text(raw_predecessor.get("slug")):
        ids = raw_predecessor.get("knowledge_ids") or []
        if isinstance(ids, str):
            ids = [ids]
        predecessor = {
            "slug": _binding_text(raw_predecessor["slug"]),
            "knowledge_ids": [str(i).strip() for i in ids if str(i).strip()],
        }

    history: list[dict[str, Any]] = []
    for entry in (binding.get("context_history") or [])[-BINDING_CONTEXT_HISTORY:]:
        if isinstance(entry, dict):
            history.append({str(k): v for k, v in entry.items()})

    payload: dict[str, Any] = {
        "native_session_id": native_session_id,
        "resolved_agent": resolved_agent,
        "initiating_message_id": _binding_text(binding.get("initiating_message_id")),
        "task_identity": task_identity,
        "task_identity_source": _binding_text(binding.get("task_identity_source")) or "explicit",
        "project": _binding_text(binding.get("project")),
        "original_request": original_request,
        "original_request_sha256": _binding_text(binding.get("original_request_sha256"))
        or hashlib.sha256(original_request.encode("utf-8")).hexdigest(),
        "source_revision": _binding_text(binding.get("source_revision")),
        "acceptance": acceptance,
        "predecessor": predecessor,
        # Capsule inputs (optional): the current work unit and the one next action / known
        # blocker the capsule renders. They ride on the binding so every capsule request reads
        # them from the durable record rather than from whichever message is in flight.
        "work_unit": _binding_text(binding.get("work_unit")),
        "next_action": _binding_text(binding.get("next_action")),
        "blocker": _binding_text(binding.get("blocker")),
        "created_at": _binding_text(binding.get("created_at")),
        # Versioned task context: 1 at creation; :func:`update_binding_context` bumps it with
        # the caller's expected-version check and retains a bounded history.
        "context_version": int(binding.get("context_version") or 1),
        "updated_at": _binding_text(binding.get("updated_at")),
        "context_history": history,
        "actor": ACTOR,
        "scope": aio_acl_scope(repository_id),
    }
    # The AUTHORIZATION identity (round-9): a pure function of the authorization-relevant
    # fields + the session identity, ALWAYS recomputed so payload and checks can never
    # disagree. The epoch defaults to 1 at creation; update_binding_context bumps it only
    # when an authorization-relevant field actually changes.
    payload["authorization_id"] = binding_authorization_id(payload)
    raw_epoch = binding.get("authorization_version")
    payload["authorization_version"] = (
        int(raw_epoch)
        if isinstance(raw_epoch, int) and not isinstance(raw_epoch, bool) and raw_epoch >= 1
        else 1
    )
    return payload


def build_binding_record(
    binding: dict[str, Any],
    *,
    repository_id: str = REPOSITORY_ID,
    now: datetime | None = None,
) -> KnowledgeRecord:
    """Derive ONE ``meta_session``-enveloped binding record (family ``aio-session-binding/v1``).

    Authority is ADVISORY / ``[H]`` — like the spine: identity/binding state is the AIO's own
    account of the session, never an independent measurement. The record is not bound to one
    commit (``REVISION_FALLBACK`` + ``commit_sha=""``), so a close/bind re-run is rerun-safe.
    The record ``text`` is PURE canonical JSON (no prose/JSON separator) — an original request
    containing the legacy ``" || json: "`` sequence must round-trip byte-exactly.
    """
    payload = binding_payload(binding, repository_id=repository_id)
    native_session_id = payload["native_session_id"]
    scope = aio_acl_scope(repository_id)

    return build_record_from_parts(
        source_type=SOURCE_TYPE,
        source_uri=f"session-binding:{native_session_id}",
        logical_locator=native_session_id,
        repository_id=repository_id,
        revision=REVISION_FALLBACK,
        authority=Authority.ADVISORY,
        evidence_class="[H]",
        text=json.dumps(payload, sort_keys=True),
        extra_fields={
            "commit_sha": "",
            "extractor_version": BINDING_EXTRACTOR_VERSION,
            "acl_scope": scope,
            "observed_at": payload.get("created_at") or "",
        },
        now=now,
    )


@dataclass
class BindingResult:
    """What one binding read/write resolved.

    ``status`` is one of the ``BINDING_STATUS_*`` constants. ``binding`` is the canonical
    payload when one resolves (``found``/``existing``/``created``/``updated``); ``path`` is the
    slot file; ``knowledge_id`` the full record's KB identity ("" until built). ``warnings``
    carries every swallowed producer/read failure (a degraded publish, a corrupt slot, a
    missing store) — never silent.
    """

    status: str
    binding: dict[str, Any] | None = None
    path: Path | None = None
    knowledge_id: str = ""
    entry_id: str = ""
    warnings: list[str] = _dataclass_field(default_factory=list)


def _binding_store_status(artifact_dir: Path) -> str:
    """``present`` when the durable root exists, else ``missing`` — the explicit store state.

    This is the distinction the path trap turns on: a read (or a native bind) against an
    ABSENT root is "store missing" (unavailable), never the bootstrap answer "no predecessor
    yet", and never a freshly created private copy.
    """
    return "present" if artifact_dir.is_dir() else "missing"


def _decode_binding_text(text: str) -> dict[str, Any] | None:
    """Decode a binding record's ``text`` into its payload.

    New records are PURE canonical JSON; the legacy ``" || json: "`` hybrid is tolerated only
    as a fallback (and, even then, the FIRST separator — the prose lead never contains one).
    """
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except ValueError:
        pass
    if " || json: " in text:
        try:
            parsed = json.loads(text.split(" || json: ", 1)[1])
            return parsed if isinstance(parsed, dict) else None
        except ValueError:
            return None
    return None


def _read_binding_slot(
    slot_path: Path, *, repository_id: str = REPOSITORY_ID
) -> tuple[dict[str, Any] | None, str, list[str]]:
    """Read + FULLY VERIFY one slot file → its canonical binding payload (or warnings).

    Verification chain (every link must hold; any failure is ``corrupt`` with a named reason):

    1. the slot's schema + the claimed session id must hash to the slot's own FILENAME (a
       copied/foreign pointer is refused);
    2. the pointed-at artifact must exist at ``<kb>/<knowledge_id>.json`` and carry the
       binding family + repository;
    3. the artifact's bytes must recompute to the slot's ``knowledge_id`` (entity_id from
       repository/uri/locator + sha256(artifact) + the family extractor) — a swapped or
       modified artifact is refused;
    4. the payload's native session id must match the slot's, and its original request must
       hash to its recorded ``original_request_sha256`` — a modified request is refused.
    """
    from agentic_dynamics.knowledge.knowledge import compute_entity_id, compute_knowledge_id

    warnings: list[str] = []
    try:
        raw = slot_path.read_bytes()
    except OSError as exc:
        return None, "", [f"binding slot {slot_path.name} is unreadable ({exc})"]
    try:
        slot = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None, "", [f"binding slot {slot_path.name} is unreadable (bad JSON)"]
    if not isinstance(slot, dict) or slot.get("schema") != BINDING_SLOT_SCHEMA:
        return None, "", [f"binding slot {slot_path.name} is not a {BINDING_SLOT_SCHEMA} pointer"]
    knowledge_id = _binding_text(slot.get("knowledge_id"))
    claimed = _binding_text(slot.get("native_session_id"))
    if not knowledge_id or not claimed:
        return None, "", [f"binding slot {slot_path.name} names no record/session"]
    if binding_slot_id(claimed, repository_id=repository_id) != slot_path.stem:
        return None, "", [
            f"binding slot {slot_path.name} claims session {claimed!r} whose slot id does not "
            "match this file's name — a copied or misplaced pointer"
        ]
    artifact = slot_path.parent.parent / f"{knowledge_id}.json"
    if not artifact.is_file():
        return None, "", [
            f"binding slot {slot_path.name} points at {knowledge_id[:12]} whose durable "
            "artifact is absent — the binding cannot be resolved"
        ]
    try:
        artifact_bytes = artifact.read_bytes()
        record = json.loads(artifact_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return None, "", [f"binding artifact {artifact.name} is unreadable ({exc})"]
    if not isinstance(record, dict) or record.get("extractor_version") != BINDING_EXTRACTOR_VERSION:
        return None, "", [f"binding artifact {artifact.name} is not a {BINDING_EXTRACTOR_VERSION} record"]
    if record.get("repository_id") != repository_id:
        return None, "", [
            f"binding artifact {artifact.name} belongs to repository "
            f"{record.get('repository_id')!r}, not {repository_id!r}"
        ]
    entity_id = compute_entity_id(repository_id, f"session-binding:{claimed}", claimed)
    content_hash = hashlib.sha256(artifact_bytes).hexdigest()
    recomputed = compute_knowledge_id(
        entity_id, REVISION_FALLBACK, content_hash, BINDING_EXTRACTOR_VERSION
    )
    if recomputed != knowledge_id or artifact.stem != knowledge_id:
        return None, "", [
            f"binding artifact {artifact.name} does not recompute to the slot's knowledge_id "
            "— the record or the pointer was modified"
        ]
    if record.get("entity_id") != entity_id:
        return None, "", [f"binding artifact {artifact.name} carries a mismatched entity_id"]
    payload = _decode_binding_text(str(record.get("text") or ""))
    if payload is None:
        return None, "", [f"binding artifact {artifact.name} carries an unreadable payload"]
    if str(payload.get("native_session_id") or "") != claimed:
        return None, "", [
            f"binding slot {slot_path.name} and its artifact disagree on the native session id"
        ]
    request = str(payload.get("original_request") or "")
    recorded_hash = str(payload.get("original_request_sha256") or "")
    if not recorded_hash or hashlib.sha256(request.encode("utf-8")).hexdigest() != recorded_hash:
        return None, "", [
            f"binding artifact {artifact.name} carries request text that does not hash to its "
            "recorded original_request_sha256 — the request was modified"
        ]
    return payload, knowledge_id, warnings


def read_binding(
    native_session_id: str,
    *,
    repository_id: str = REPOSITORY_ID,
    artifact_dir: Path | None = None,
) -> BindingResult:
    """Read the binding for ONE native session, from the durable store only.

    Statuses: ``store_missing`` (the durable root itself is absent — unavailable, NOT the
    bootstrap "no predecessor" state), ``missing`` (the store is present but this session has
    no binding), ``found`` (a fully verified payload), ``corrupt`` (a slot exists but fails
    verification — warnings name why). Never creates directories, never guesses a neighbour.
    """
    from agentic_dynamics.core.paths import KB_ARTIFACT_DIR

    artifact_dir = artifact_dir or KB_ARTIFACT_DIR
    if _binding_store_status(artifact_dir) == "missing":
        return BindingResult(
            status=BINDING_STATUS_STORE_MISSING,
            warnings=[
                f"the durable knowledge root {artifact_dir} is absent — the binding store is "
                "unavailable (this is NOT first-session bootstrap)"
            ],
        )
    slot_path = binding_slot_path(
        native_session_id, artifact_dir=artifact_dir, repository_id=repository_id
    )
    if not slot_path.is_file():
        return BindingResult(status=BINDING_STATUS_MISSING, path=slot_path)
    payload, knowledge_id, warnings = _read_binding_slot(slot_path, repository_id=repository_id)
    if payload is None:
        return BindingResult(status=BINDING_STATUS_CORRUPT, path=slot_path, warnings=warnings)
    # The payload and its knowledge_id come from the SAME slot snapshot — a concurrent update
    # cannot pair an old payload with a newer artifact id (reviewer repair 2026-09-15).
    return BindingResult(
        status=BINDING_STATUS_FOUND, binding=payload, path=slot_path,
        knowledge_id=knowledge_id, warnings=warnings,
    )


def _write_slot_temp(slot_path: Path, slot: dict[str, Any]) -> str:
    """Write the slot JSON to a UNIQUE temp file beside the slot; return its path."""
    slot_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=slot_path.parent, prefix=f"{slot_path.name}.tmp.")
    with os.fdopen(fd, "wb") as handle:
        handle.write(json.dumps(slot, sort_keys=True, indent=2).encode("utf-8"))
    return tmp_name


def _create_slot_exclusive(slot_path: Path, slot: dict[str, Any]) -> bool:
    """Create the slot atomically across processes; False when another writer won.

    Content-atomic, not just name-atomic: the full JSON is written to a unique temp file and
    then ``os.link``-ed into place — the link either fails (the slot exists) or publishes the
    COMPLETE slot in one step. ``O_CREAT|O_EXCL`` alone guarantees only that one writer lands
    the NAME; a concurrent reader could observe an empty/partial file mid-write (the CI
    concurrency flake this replaces). The artifact is written before the link, so a reader
    that sees the slot always sees a resolvable binding. ``mkstemp`` keeps the temp name
    unique across THREADS as well as processes.
    """
    tmp_name = _write_slot_temp(slot_path, slot)
    try:
        os.link(tmp_name, slot_path)
        return True
    except FileExistsError:
        return False
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp_name)


def binding_publish_enabled() -> bool:
    """Whether binding writes may publish their pointer event (default ON).

    ``FINOPS_AIO_BINDING_PUBLISH=0`` is the durable-only switch: the artifact + slot still
    land (the binding is never lost), but no stream event is emitted. Used by sandboxed/
    isolated stores (and the native-path integration tests) so a scratch store cannot
    pollute the live knowledge stream.
    """
    return os.environ.get("FINOPS_AIO_BINDING_PUBLISH", "1") != "0"


def _publish_binding(record: KnowledgeRecord, connect_fn: Any, warnings: list[str]) -> str:
    """Best-effort pointer publish (same warning contract as :func:`close_session`)."""
    from agentic_dynamics.knowledge import knowledge_stream as ks
    from agentic_dynamics.knowledge.knowledge_ingestion import record_to_event

    connect = connect_fn or ks.connect
    try:
        r = connect()
    except Exception as exc:  # noqa: BLE001 — a producer failure is a warning by contract
        warnings.append(
            f"knowledge stream unreachable ({type(exc).__name__}: {exc}); the durable binding "
            "is written but its pointer event was not published"
        )
        return ""
    try:
        if r.hget(ks.CHECKPOINT_KEY, record.knowledge_id) is None:
            entry_id = ks.publish_event(
                r, record_to_event(record), authorized=True, source_type=record.source_type
            )
            r.hset(ks.CHECKPOINT_KEY, record.knowledge_id, record.indexed_at)
            return entry_id
    except Exception as exc:  # noqa: BLE001 — a producer failure is a warning by contract
        warnings.append(
            f"binding pointer publish failed for {record.knowledge_id} "
            f"({type(exc).__name__}: {exc})"
        )
    return ""


def write_binding(
    binding: dict[str, Any],
    *,
    repository_id: str = REPOSITORY_ID,
    artifact_dir: Path | None = None,
    connect_fn: Any = None,
    now: datetime | None = None,
    init_store: bool = False,
    publish: bool | None = None,
) -> BindingResult:
    """Create ONE session binding — durable artifact first, then an ATOMIC slot claim.

    An EXISTING binding is returned unchanged (status ``existing``): the original request is
    immutable. Two concurrent first writes: exactly one wins ``created`` (the slot claim is
    ``O_CREAT|O_EXCL``); the loser re-reads and returns the winner's binding as ``existing``.

    The durable root MUST already exist. ``init_store=False`` (the native path) returns
    :data:`BINDING_STATUS_STORE_MISSING` instead of creating anything; initialization is the
    explicit :func:`init_binding_store` operation. Raises ``ValueError`` for a genuinely
    invalid binding (missing identity/request) or an unresolvable pre-existing slot.
    """
    from agentic_dynamics.core.paths import KB_ARTIFACT_DIR
    from agentic_dynamics.knowledge.knowledge_ingestion import record_to_artifact

    artifact_dir = artifact_dir or KB_ARTIFACT_DIR
    native_session_id = _content_value(binding, "native_session_id")
    slot_path = binding_slot_path(
        native_session_id, artifact_dir=artifact_dir, repository_id=repository_id
    )
    existing = read_binding(
        native_session_id, repository_id=repository_id, artifact_dir=artifact_dir
    )
    if existing.status == BINDING_STATUS_FOUND:
        return BindingResult(
            status=BINDING_STATUS_EXISTING,
            binding=existing.binding,
            path=slot_path,
            knowledge_id=existing.knowledge_id,
            warnings=existing.warnings,
        )
    if existing.status == BINDING_STATUS_CORRUPT:
        raise ValueError(
            f"a binding slot for {native_session_id!r} exists but does not resolve "
            f"({'; '.join(existing.warnings)}) — repair or remove it explicitly, never overwrite"
        )
    if existing.status == BINDING_STATUS_STORE_MISSING:
        if not init_store:
            return BindingResult(
                status=BINDING_STATUS_STORE_MISSING,
                path=slot_path,
                warnings=[
                    f"the durable knowledge root {artifact_dir} is absent — refusing to create "
                    "one implicitly (a wrong worktree path must not become a private store); "
                    "initialize explicitly (session_open.py --init-store / "
                    "session_ingestion.init_binding_store)"
                ],
            )
        init_binding_store(artifact_dir)

    binding = dict(binding)
    binding.setdefault("created_at", (now or datetime.now()).astimezone().isoformat())
    record = build_binding_record(binding, repository_id=repository_id, now=now)
    artifact_path = artifact_dir / f"{record.knowledge_id}.json"
    artifact_bytes = record_to_artifact(record)
    if not artifact_path.is_file() or artifact_path.read_bytes() != artifact_bytes:
        artifact_path.write_bytes(artifact_bytes)
    slot = {
        "schema": BINDING_SLOT_SCHEMA,
        "family": BINDING_EXTRACTOR_VERSION,
        "repository_id": repository_id,
        "native_session_id": native_session_id,
        "knowledge_id": record.knowledge_id,
        "created_at": binding["created_at"],
    }
    if not _create_slot_exclusive(slot_path, slot):
        # Another writer claimed the slot between our read and our create. Its binding wins;
        # our (content-addressed, valid) artifact is left in place — artifacts are immutable
        # and deleting one here could race a reader.
        raced = read_binding(
            native_session_id, repository_id=repository_id, artifact_dir=artifact_dir
        )
        if raced.status == BINDING_STATUS_FOUND:
            return BindingResult(
                status=BINDING_STATUS_EXISTING,
                binding=raced.binding,
                path=slot_path,
                knowledge_id=raced.knowledge_id,
                warnings=raced.warnings,
            )
        raise ValueError(
            f"the binding slot for {native_session_id!r} was claimed concurrently but does "
            f"not resolve ({raced.status}) — refusing to guess the winner"
        )

    warnings: list[str] = []
    entry_id = ""
    if (binding_publish_enabled() if publish is None else publish):
        entry_id = _publish_binding(record, connect_fn, warnings)
    payload = binding_payload(binding, repository_id=repository_id)
    return BindingResult(
        status=BINDING_STATUS_CREATED,
        binding=payload,
        path=slot_path,
        knowledge_id=record.knowledge_id,
        entry_id=entry_id,
        warnings=warnings,
    )


def update_binding_context(
    native_session_id: str,
    *,
    context: dict[str, Any],
    expected_version: int,
    repository_id: str = REPOSITORY_ID,
    artifact_dir: Path | None = None,
    connect_fn: Any = None,
    now: datetime | None = None,
    publish: bool | None = None,
) -> BindingResult:
    """Apply an EXPLICIT, VERSIONED task-context update to an existing binding.

    The original request fields are preserved byte-for-byte; only the fields in
    :data:`BINDING_CONTEXT_FIELDS` may change. ``expected_version`` is the caller's optimistic
    concurrency check — a mismatch is a named ``ValueError``, never a silent overwrite. The
    new record is content-addressed; the slot is replaced atomically (temp + ``os.replace``),
    so a reader sees either the old or the new binding, never a torn one.
    """
    import fcntl

    from agentic_dynamics.core.paths import KB_ARTIFACT_DIR

    artifact_dir = artifact_dir or KB_ARTIFACT_DIR
    # The reviewer repair: check the store BEFORE creating anything (the lock directory
    # included). Creating `aio-bindings/` for a rejected update would make the ROOT appear
    # present and let a later ordinary bind succeed without explicit initialization.
    if _binding_store_status(artifact_dir) == "missing":
        raise ValueError(
            f"no binding store at {artifact_dir} to update (store_missing) — refusing to "
            "create it implicitly; initialize explicitly (session_open.py --init-store)"
        )
    slot_path_locked = binding_slot_path(
        native_session_id, artifact_dir=artifact_dir, repository_id=repository_id
    )
    if not slot_path_locked.parent.is_dir():
        raise ValueError(
            f"the binding store at {slot_path_locked.parent} is absent — initialize it "
            "explicitly (session_open.py --init-store)"
        )
    # Serialize the read-check-write across PROCESSES (the reviewer race: two updaters both
    # accepted version 1 and overwrote each other). An exclusive flock on a sidecar lock file
    # makes the version check and the slot replacement one critical section.
    lock_path = slot_path_locked.with_name(f"{slot_path_locked.name}.lock")
    with open(lock_path, "a+", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        try:
            current = read_binding(
                native_session_id, repository_id=repository_id, artifact_dir=artifact_dir
            )
            return _apply_context_update(
                current, native_session_id=native_session_id, context=context,
                expected_version=expected_version, repository_id=repository_id,
                artifact_dir=artifact_dir, connect_fn=connect_fn, now=now, publish=publish,
            )
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


def _apply_context_update(
    current: BindingResult,
    *,
    native_session_id: str,
    context: dict[str, Any],
    expected_version: int,
    repository_id: str,
    artifact_dir: Path,
    connect_fn: Any,
    now: datetime | None,
    publish: bool | None = None,
) -> BindingResult:
    """The critical section of :func:`update_binding_context` (caller holds the slot lock)."""
    from agentic_dynamics.knowledge.knowledge_ingestion import record_to_artifact

    if current.status != BINDING_STATUS_FOUND or current.binding is None:
        raise ValueError(
            f"no binding for {native_session_id!r} to update (status {current.status})"
        )
    payload = dict(current.binding)
    version = int(payload.get("context_version") or 1)
    if int(expected_version) != version:
        raise ValueError(
            f"context version conflict for {native_session_id!r}: expected {expected_version}, "
            f"current {version} — re-read the binding before updating"
        )

    merged = dict(payload)
    merged.update({
        field: context[field] for field in BINDING_CONTEXT_FIELDS if field in context
    })
    # AUTHORIZATION vs PROGRESS (round-9 review): the authorization epoch advances ONLY when
    # an authorization-relevant field actually changes a value — routine progress recording
    # (next_action / blocker) preserves the authorization of commands already queued against
    # this task. The context_version above still advances on EVERY update: it is the
    # optimistic-concurrency guard for writers, never the exec gate's stale-task check.
    previous_epoch = binding_authorization_version(payload)
    authorization_changed = binding_authorization_id(merged) != binding_authorization_id(payload)
    merged["authorization_version"] = previous_epoch + 1 if authorization_changed else previous_epoch
    merged["context_version"] = version + 1
    merged["updated_at"] = (now or datetime.now()).astimezone().isoformat()
    history = list(payload.get("context_history") or [])
    history.append({
        "version": version,
        "updated_at": payload.get("updated_at", ""),
        **{field: payload.get(field) for field in BINDING_CONTEXT_FIELDS},
    })
    merged["context_history"] = history[-BINDING_CONTEXT_HISTORY:]

    record = build_binding_record(merged, repository_id=repository_id, now=now)
    artifact_path = artifact_dir / f"{record.knowledge_id}.json"
    artifact_bytes = record_to_artifact(record)
    if not artifact_path.is_file() or artifact_path.read_bytes() != artifact_bytes:
        artifact_path.write_bytes(artifact_bytes)
    slot_path = current.path or binding_slot_path(
        native_session_id, artifact_dir=artifact_dir, repository_id=repository_id
    )
    slot = {
        "schema": BINDING_SLOT_SCHEMA,
        "family": BINDING_EXTRACTOR_VERSION,
        "repository_id": repository_id,
        "native_session_id": native_session_id,
        "knowledge_id": record.knowledge_id,
        "created_at": payload.get("created_at", ""),
    }
    tmp_name = _write_slot_temp(slot_path, slot)
    os.replace(tmp_name, slot_path)

    warnings: list[str] = []
    entry_id = ""
    if (binding_publish_enabled() if publish is None else publish):
        entry_id = _publish_binding(record, connect_fn, warnings)
    return BindingResult(
        status=BINDING_STATUS_UPDATED,
        binding=binding_payload(merged, repository_id=repository_id),
        path=slot_path,
        knowledge_id=record.knowledge_id,
        entry_id=entry_id,
        warnings=warnings,
    )
