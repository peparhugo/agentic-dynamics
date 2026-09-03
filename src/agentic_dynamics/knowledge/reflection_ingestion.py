"""Producer-side reflection-record derivation for the self-knowledge layer (loop 2).

The reflection record is phase ``s6a_reflection_type_append``'s substrate
(``self_knowledge_layer`` wave, design ``docs/designs/proposed/self_knowledge_layer.md``):
the machine's standing reflection series. Where the session spine (s1a) is the
chronological skeleton of what ran and what merged, the reflection series is the
REFLEXIVE layer — "what I got wrong, what surprised me, what I'd change about my own
process" (design §memory-layers: "a standing reflection series each session appends to;
multi-session contemplation is their accumulation"). Every session close (s1b) appends its
self-notes into this session-keyed series: a record family with ONE entry per session, never
overwriting a prior session's — a second session's close appends a SECOND entry, so the
series grows and the next session can contemplate across its predecessors instead of
re-learning its own mistakes by grep (the s1b close's ``self_notes`` is "the reflection
seed" — this type is where that seed lands).

``source_type`` is ``"reflection"`` — minted as its own observation-family row (registered
in ``knowledge.SOURCE_TYPES`` as ADVISORY/``[H]``) so the registry census can distinguish a
reflection entry from the session close that seeded it, a decision, or a belief. The
disambiguation from every other observation-family record is by ``extractor_version``
(``reflection/v1``) + URI family (``reflection:<slug>``), exactly the schema's one-table
convention.

The record's body (``text``) is a canonical JSON payload of the reflection's content fields
— ``{session_date, slug, self_notes}`` plus the record's ``actor`` and ``scope`` —
serialized with sorted keys so the same input always yields the same bytes. Deterministic,
so the shared factory's ``content_hash``/``knowledge_id`` are rerun-safe pure functions of
the session dict (an identical re-append is a no-op). The ``self_notes`` field is the s1a
session type's own field fed straight through — a reflection entry is NOT a new free-text
input; it is the session's own self-notes re-homed under a type that marks them as
contemplative material, keyed by the session they came from.

Actor + scope follow the context abstraction (design §actor-layering): the producer is the
AIO and the record lives in the AIO's org-root scope (``org:agentic-dynamics``), carried
structurally on the record (``repository_id`` = the org id, ``acl_scope`` =
``org:<repository_id>``) AND in the payload's ``scope`` key — private to the
controller–AIO pair, never resolved by cell agents (a cell/workload retrieval filters on its
OWN ``repository_id`` via ``retrieval.scope_excluded``, which never equals the org id) and
never read by the supervisor rail (which observes its own flags/assessments, not the AIO's
org-root private records). ``actor`` travels in the payload as the AIO's ``aio`` marker (the
KB schema has no ``actor`` column), exactly as the session/decision/belief siblings do.

Identity: ONE logical entity per session. The family is SESSION-KEYED — ``logical_locator``
is the session's ``slug`` and ``source_uri`` is ``reflection:<slug>`` (distinct from the
spine's ``session:<slug>`` family, so a reflection never collides with the very close that
seeded it). ``entity_id`` is therefore stable per session slot, and a re-close of the SAME
session with amended self-notes re-keys ``knowledge_id`` while ``entity_id`` holds — a new
version of that session's ONE entry, never a second entry for the same session. Two
DIFFERENT sessions (two slugs) are two entities: appending the second never overwrites the
first. ``revision`` is :data:`REVISION_FALLBACK` (the record is the AIO's org-root
posterior, not bound to one commit — folding HEAD in would re-key every entry as the
checkout advances).

Contract reuse: identical to the other producers — :func:`record_factory.build_record`
(identity + content-hash back-fill) + ``record_to_artifact``/``record_to_event`` from
:mod:`knowledge_ingestion`, published via ``knowledge_stream.publish_event`` under the
authorized-writer seam, rerun-safe against the shared ``CHECKPOINT_KEY`` hash.

Scope fence: the TYPE + the APPEND path ONLY — the read command (rendering the accumulated
series) is s6b (``reflection_ingestion`` exposes only the family scan/resolution a read must
build on, mirroring how s2a exposed ``scan_decision_records`` before its read command
existed). Nothing here registers a CLI leaf or writes outside the append seam.
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
from agentic_dynamics.knowledge.session_ingestion import aio_acl_scope

# ── Extractor contract constants ────────────────────────────────

#: ``source_type`` recorded on every reflection record — registered in
#: ``knowledge.SOURCE_TYPES`` as an observation-family ADVISORY ``[H]`` type (see the module
#: docstring for why it is minted as its own family, beside the session spine that seeds it).
SOURCE_TYPE = "reflection"

#: The extractor generation. ``knowledge_id`` folds this in, so the reflection family is
#: identity-distinct from every other observation-family producer (session/``meta_session``,
#: ``decision``, ``belief``, ``observation``) even for byte-identical bodies. A literal —
#: stability is the point.
EXTRACTOR_VERSION = "reflection/v1"

#: The producer/actor of every reflection record. The AIO is the only actor that reflects on
#: its own session at close; the value travels in the payload (self-describing — the KB
#: schema has no ``actor`` field).
ACTOR = "aio"

#: Fallback ``source_revision`` for a reflection record. The record is the AIO's org-root
#: posterior, NOT bound to one commit — folding the checkout HEAD in as ``revision`` would
#: re-key every entry as HEAD moves. Mirrors ``session_ingestion.REVISION_FALLBACK``.
REVISION_FALLBACK = "reflection/unrevisioned"

#: The content fields of one reflection entry — the session's identity on the spine
#: (``slug`` + ``session_date``) plus the self-notes the entry carries. The list is
#: documentation — the derivation below builds exactly these keys plus ``actor``/``scope``.
CONTENT_FIELDS = (
    "session_date",
    "slug",
    "self_notes",
)


# ── Small deterministic helpers ─────────────────────────────────


def _content_value(session: dict[str, Any], field: str) -> str:
    """Return a required string content field, stripping whitespace.

    Raises ``ValueError`` when the field is missing or empty — a reflection entry with no
    ``slug`` (the session it belongs to) or no ``session_date`` (its place on the series)
    cannot be registered.
    """
    value = str(session.get(field) or "").strip()
    if not value:
        raise ValueError(f"session has no {field!r} — cannot derive a reflection record")
    return value


def _notes_value(session: dict[str, Any]) -> str:
    """Return the session's self-notes, trimmed of surrounding whitespace.

    The notes are the reflection's whole content — the s1a self-notes field fed straight
    through. Surrounding whitespace is trimmed so an all-whitespace close reads as the empty
    notes it is (and the append seam can say "nothing to reflect" honestly).
    """
    return str(session.get("self_notes") or "").strip()


# ── The canonical content payload ───────────────────────────────


def reflection_payload(
    session: dict[str, Any], *, repository_id: str = REPOSITORY_ID
) -> dict[str, Any]:
    """Return the canonical content payload for ONE reflection entry.

    Exactly the three content fields (normalized) plus ``actor`` and ``scope`` — the record's
    context-abstraction dimensions (design §actor-layering). ``scope`` mirrors the record's
    own ``acl_scope`` (``aio_acl_scope(repository_id)``), and ``actor`` is the module's
    ``ACTOR`` literal. This dict is what ``text`` serializes (sorted keys), so it is the
    entire hashed body: two derivations of the same session dict yield byte-identical bodies
    and therefore identical ids (rerun-safe), while amended self-notes yield a new body and a
    new ``knowledge_id`` for the same session's entry.
    """
    return {
        "session_date": _content_value(session, "session_date"),
        "slug": _content_value(session, "slug"),
        "self_notes": _notes_value(session),
        "actor": ACTOR,
        "scope": aio_acl_scope(repository_id),
    }


# ── Record construction ─────────────────────────────────────────


def build_reflection_record(
    session: dict[str, Any],
    *,
    repository_id: str = REPOSITORY_ID,
    now: datetime | None = None,
) -> KnowledgeRecord:
    """Derive ONE ``source_type=reflection`` record from a session dict.

    ``session`` is the session close payload the s1a type defines: ``{session_date, slug,
    waves_run[], merged[], parked[], open_threads[], self_notes}`` — of which the reflection
    reads ``session_date`` (required), ``slug`` (required), and ``self_notes`` (the entry's
    content). The record's ``text`` is the canonical JSON body from :func:`reflection_payload`
    — deterministic, so ``content_hash``/``knowledge_id`` are rerun-safe for identical input.

    Identity follows the canonical contract in :mod:`knowledge`:

    * ``logical_locator`` is the session's ``slug`` and ``source_uri`` is
      ``reflection:<slug>`` — a family distinct from the spine's ``session:<slug>``, so the
      reflection never collides with the very close that seeded it.
    * ``revision`` is :data:`REVISION_FALLBACK` (not bound to one commit).
    * ``entity_id = sha256(repository_id | source_uri | logical_locator)``; ``content_hash``
      is the sha256 of the durable artifact; ``knowledge_id`` folds them with the revision +
      the ``reflection/v1`` extractor. Re-appending the SAME session dict is a no-op; a
      re-close with amended self-notes re-keys ``knowledge_id`` while ``entity_id`` holds — a
      new version of the SAME session's one entry (the "never overwriting a prior session's"
      rule is about OTHER sessions, which are other entities and never collide).

    ``authority`` is ``ADVISORY`` / ``[H]`` — the registered nominal for ``reflection`` (a
    reflection entry is the AIO's own account of what it got wrong, self-reported like a
    session close or a decision, never an independent measurement). ``repository_id``
    defaults to the org id and ``acl_scope`` to the AIO org-root scope (see
    :func:`aio_acl_scope`). ``observed_at`` is the session's own date — the real "when this
    reflection happened" — while ``valid_from``/``indexed_at`` stay the derivation/consumer
    clocks.

    Raises ``ValueError`` when the session carries no ``slug`` or no ``session_date``.
    """
    payload = reflection_payload(session, repository_id=repository_id)
    slug = payload["slug"]
    scope = aio_acl_scope(repository_id)

    return build_record_from_parts(
        source_type=SOURCE_TYPE,
        source_uri=f"reflection:{slug}",
        logical_locator=slug,
        repository_id=repository_id,
        revision=REVISION_FALLBACK,
        authority=Authority.ADVISORY,
        evidence_class="[H]",
        text=json.dumps(payload, sort_keys=True),
        extra_fields={
            # The reflection record is not tied to a commit of its own — mirror the session/
            # decision producers, which pass commit_sha="" while folding their revision marker
            # through the `revision` input (record_factory's contract).
            "commit_sha": "",
            "extractor_version": EXTRACTOR_VERSION,
            "acl_scope": scope,
            # observed_at is the session's own date (when the session HAPPENED), not the
            # append wall-clock; the artifact blanks it, so it never perturbs the rerun-safe
            # content hash.
            "observed_at": payload["session_date"],
        },
        now=now,
    )


def derive_reflection_record(
    session: dict[str, Any],
    *,
    repository_id: str = REPOSITORY_ID,
    now: datetime | None = None,
) -> KnowledgeRecord:
    """Public derivation entry point — delegates to :func:`build_reflection_record`.

    Deliberately singular (like the session/decision producers): one session close always
    yields exactly one reflection record, with no batch pre-filter case. A session missing
    its ``slug``/``session_date`` is a genuine caller error, not a skip case.
    """
    return build_reflection_record(session, repository_id=repository_id, now=now)


# ── The append path (s6a — the session close appends its entry) ─


@dataclass
class ReflectionAppendResult:
    """What one :func:`append_reflection` call did — the session close's reflection half.

    ``record`` is the derived reflection record — always present EXCEPT on a ``"no-notes"``
    skip (there was nothing to reflect, so nothing was derived), where it is ``None``.
    ``artifact_path`` is the durable per-record artifact the call wrote (or confirmed already
    present), or ``None`` on the skip. ``entry_id`` is the stream entry the pointer event
    landed on, or ``""`` when nothing was published by this call.

    ``status`` is one of:

    * ``"appended"`` — the entry now fully lands in the KB: its durable artifact is written
      and its pointer event was published this call (including the repair of a prior partial
      append, where the artifact existed but the event had never landed).
    * ``"no-op"`` — re-appending an already-appended session: the exact record (identical
      bytes) was already durable AND its event was already checkpointed, so this call changed
      nothing (rerun-safe).
    * ``"degraded"`` — the durable artifact is written but the event could not be published
      or its prior publication could not be confirmed (a downed or rejecting knowledge
      stream). This is a WARNING, never a crash: ``warnings`` carries the reason, and
      re-running the append once the stream is back completes the publication.
    * ``"no-notes"`` — the session carried empty self-notes: there is nothing to reflect, so
      no entry was derived or written. Not an error — an honest skip, reported so a caller
      can distinguish "reflected nothing" from "not appended".

    ``warnings`` lists every producer failure this call swallowed (empty on a clean path).
    """

    record: KnowledgeRecord | None
    status: str
    artifact_path: Path | None = None
    entry_id: str = ""
    warnings: list[str] = _dataclass_field(default_factory=list)


def append_reflection(
    session: dict[str, Any],
    *,
    repository_id: str = REPOSITORY_ID,
    artifact_dir: Path | None = None,
    connect_fn: Callable[..., Any] | None = None,
    now: datetime | None = None,
) -> ReflectionAppendResult:
    """Append ONE session's reflection entry: derive, land artifact + event, best-effort.

    This is the append path of phase ``s6a_reflection_type_append`` (``self_knowledge_layer``
    wave): the session close (s1b) calls it so its self-notes land in the session-keyed
    reflection series. It follows the producers' canonical pointer contract exactly as the
    session close does — write the durable per-record artifact to
    ``<artifact_dir>/<knowledge_id>.json`` FIRST (so a consumer can read + verify the bytes
    the event's ``content_hash`` covers the moment the pointer lands), then publish the
    pointer event and checkpoint the ``knowledge_id``.

    **Session-keyed, never overwriting.** ``entity_id`` is a pure function of the session's
    ``slug`` (s6a identity), so a SECOND session's append is a SECOND entity: the first
    session's entry is untouched — the series grows, nothing is overwritten. Re-appending the
    SAME session (an identical re-close) is a rerun-safe no-op; re-closing the same session
    with AMENDED self-notes writes a new version of that session's ONE entry (``entity_id``
    holds, ``knowledge_id`` re-keys).

    **A producer failure is a warning, never a crash.** A downed or rejecting knowledge
    stream is caught, logged into ``warnings``, and reported as ``status="degraded"`` — the
    durable artifact still lands (the reflection is never lost), and re-running when the
    stream is back completes the publication (the checkpoint hash makes the repair exact).

    **A session with empty self-notes reflects nothing.** ``status="no-notes"`` is returned
    and nothing is written — a session that found nothing to note adds no empty entry to the
    series (an empty entry would read as a reflection that happened, which is a fabrication).

    ``artifact_dir`` defaults to the repo's durable KB artifact directory
    (``core.paths.KB_ARTIFACT_DIR``); ``connect_fn`` defaults to ``knowledge_stream.connect``.
    Both are injectable so tests can point at a tmp dir + a fake stream and so the seam is
    import-safe without Redis. Raises ``ValueError`` when the session carries no ``slug`` or
    no ``session_date``.
    """
    from agentic_dynamics.core.paths import KB_ARTIFACT_DIR
    from agentic_dynamics.knowledge import knowledge_stream as ks
    from agentic_dynamics.knowledge.knowledge_ingestion import (
        record_to_artifact,
        record_to_event,
    )

    payload = reflection_payload(session, repository_id=repository_id)
    if not payload["self_notes"]:
        return ReflectionAppendResult(record=None, status="no-notes")

    record = build_reflection_record(session, repository_id=repository_id, now=now)
    artifact_dir = artifact_dir or KB_ARTIFACT_DIR
    artifact_path = artifact_dir / f"{record.knowledge_id}.json"
    artifact_bytes = record_to_artifact(record)
    warnings: list[str] = []
    already_durable = artifact_path.is_file() and artifact_path.read_bytes() == artifact_bytes

    # 1 ── durable artifact first: a consumer can verify the bytes the pointer names as soon
    # as the event lands. Rewriting byte-identical bytes is harmless, but skip it to keep the
    # no-op path truly side-effect-free.
    if not already_durable:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_path.write_bytes(artifact_bytes)

    # 2 ── pointer event, best-effort. The write guard is satisfied with authorized=True (this
    # seam IS the AIO's authorized reflection append); the checkpoint hash makes the publish
    # idempotent so a re-append never double-emits.
    connect = connect_fn or ks.connect
    entry_id = ""
    already_published = False
    try:
        r = connect()
    except Exception as exc:  # noqa: BLE001 - a producer failure is a warning by contract
        warnings.append(
            f"knowledge stream unreachable ({type(exc).__name__}: {exc}); the durable record "
            "is written but the pointer event was not published — re-run `session close` once "
            "the stream is back to complete the reflection append"
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
        status = "appended"
    return ReflectionAppendResult(
        record=record,
        status=status,
        artifact_path=artifact_path,
        entry_id=entry_id,
        warnings=warnings,
    )


# ── The family scan (s6a's "retrievable as a family"; the read command is s6b) ─


def reflection_artifact_files(artifact_dir: Path) -> list[Path]:
    """Every ``*.json`` file under the durable artifact dir, in filename order.

    The artifact dir is shared by EVERY producer (19k+ records), so this is a *scan*, not a
    read of one known file: the reflection family is found by content, never by guessable
    filename. A missing dir (a fresh checkout with no KB yet) is simply empty — the empty
    series state.
    """
    if not artifact_dir.is_dir():
        return []
    return sorted(artifact_dir.glob("*.json"), key=lambda path: path.name)


_ARTIFACT_RECORD = "record"
_ARTIFACT_FOREIGN = "foreign"
_ARTIFACT_ANOMALY = "anomaly"


def _classify_reflection_artifact(
    path: Path, *, repository_id: str = REPOSITORY_ID
) -> tuple[str, dict[str, Any] | None, dict[str, Any] | None]:
    """Classify ONE durable artifact file into ``(kind, artifact_fields, payload)``.

    The kind is one of:

    * ``"record"`` — an AIO org-root reflection record: ``(artifact, payload)`` is returned.
    * ``"foreign"`` — NOT a reflection record of this org scope: any other producer's
      artifact (the ``extractor_version`` discriminator — a session-spine artifact is
      ``session/v1`` and never matches), a record from another repository (the scope
      pre-filter), or an undecodable file. Skipped silently — the artifact dir holds every
      producer's rows and only the reflection family in THIS org is a candidate for the
      series.
    * ``"anomaly"`` — IS a ``reflection/v1`` artifact of this org but is NOT a readable AIO
      org-root reflection record: a corrupt entry or a record whose body ``actor``/``scope``
      are not the AIO's (the body keys travel in the payload so the record is
      self-describing). Surfaced as a warning — an honest signal, never a silent skip.
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
        # A reflection/v1 record of ANOTHER repository: legitimately not ours, skipped silently.
        return _ARTIFACT_FOREIGN, None, None
    text = artifact.get("text")
    if not isinstance(text, str):
        return _ARTIFACT_ANOMALY, None, None
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


def scan_reflection_records(
    *,
    slug: str | None = None,
    repository_id: str = REPOSITORY_ID,
    artifact_dir: Path | None = None,
) -> tuple[list[tuple[Path, dict[str, Any], dict[str, Any]]], list[str]]:
    """Scan the durable artifact dir for every AIO org-root reflection record.

    Returns ``(triples, warnings)`` where each triple is ``(path, artifact_fields, payload)``
    for one reflection record in the requested org scope, and ``warnings`` names the
    ``reflection/v1`` artifacts of this org that are NOT readable AIO org-root records (the
    classifier's ``anomaly`` kind). When ``slug`` is given, only records whose payload
    ``slug`` equals it (exact string) are returned — the session-keyed retrieval: "what did
    THIS session reflect?". A session's re-close versions all share the slug, so this is the
    per-session version pool the series resolution collapses.

    The read is a DIRECT read of the durable artifacts the append seam produces — never the
    registry projection, which requires a live consumer: the round-trip (append then read)
    must be exact the moment the entry lands. ``artifact_dir`` defaults to the repo's durable
    KB artifact directory (``core.paths.KB_ARTIFACT_DIR``).
    """
    from agentic_dynamics.core.paths import KB_ARTIFACT_DIR

    artifact_dir = artifact_dir or KB_ARTIFACT_DIR
    warnings: list[str] = []
    triples: list[tuple[Path, dict[str, Any], dict[str, Any]]] = []
    for path in reflection_artifact_files(artifact_dir):
        kind, artifact, payload = _classify_reflection_artifact(path, repository_id=repository_id)
        if kind == _ARTIFACT_RECORD:
            if slug is not None and payload.get("slug") != slug:
                continue
            triples.append((path, artifact, payload))
        elif kind == _ARTIFACT_ANOMALY:
            warnings.append(
                f"{path.name}: a reflection/v1 artifact that is not a readable AIO org-root "
                "reflection record — excluded from the series read"
            )
    return triples, warnings


def _entry_selection_key(
    triple: tuple[Path, dict[str, Any], dict[str, Any]],
) -> tuple[str, float, str]:
    """Deterministic "newest version of one session's entry" ordering over a triple.

    The series' time axis is the SESSION's own date (the entry deliberately stamps
    ``session_date``, and the artifact blanks volatile clocks so its bytes are rerun-safe), so
    content — never the filesystem wall-clock alone — orders the versions of one session slot:
    greatest ``session_date`` first, then file mtime (the newer write of two same-day
    versions), then the content-addressed filename (the checkout-stable tie-break, since a
    fresh git checkout resets every artifact's mtime). Mirrors
    ``session_ingestion._selection_key``'s ordering.
    """
    _path, _artifact, payload = triple
    try:
        mtime = _path.stat().st_mtime
    except OSError:
        mtime = 0.0
    return str(payload.get("session_date") or ""), mtime, _path.name


def resolve_reflection_series(
    *,
    repository_id: str = REPOSITORY_ID,
    artifact_dir: Path | None = None,
) -> tuple[list[tuple[Path, dict[str, Any], dict[str, Any]]], list[str]]:
    """Resolve the reflection SERIES: ONE current entry per session, chronologically ordered.

    The family a session contemplates across (the s6b read command's input): the durable dir
    accumulates every version an amended re-close writes (each re-keys ``knowledge_id`` while
    ``entity_id`` holds), so the series resolves ONE current entry per session slot — grouped
    by the entry's payload ``slug`` (the SESSION-key, which the payload carries so the group
    is re-derivable from the body alone) and selected by :func:`_entry_selection_key` — then
    orders those entries by ``session_date`` (then ``slug``, deterministic) so the series
    reads in the order the sessions happened. Two different sessions are two entries, never a
    collapse. Returns ``(entries, warnings)``; an empty dir resolves an empty series — the
    honest "no reflections yet" state.
    """
    triples, warnings = scan_reflection_records(
        repository_id=repository_id, artifact_dir=artifact_dir
    )
    current: dict[str, tuple[Path, dict[str, Any], dict[str, Any]]] = {}
    for triple in triples:
        session_key = str(triple[2].get("slug") or "")
        prev = current.get(session_key)
        if prev is None or _entry_selection_key(triple) > _entry_selection_key(prev):
            current[session_key] = triple
    return (
        sorted(
            current.values(),
            key=lambda triple: (
                str(triple[2].get("session_date") or ""),
                str(triple[2].get("slug") or ""),
            ),
        ),
        warnings,
    )
