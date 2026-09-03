"""Producer-side decision-record derivation for the self-knowledge layer (loop 2).

The decision record is phase ``s2a_decision_command``'s substrate (``self_knowledge_layer``
wave, design ``docs/designs/proposed/self_knowledge_layer.md``): "we chose X because Y" —
the rationale-carrying record the next session must not re-litigate. A decision IS an
observation with intent: it is produced with the observation producer's contract
(ADVISORY ``[H]``, single-record derive, ``record_factory`` tail, best-effort pointer
publication) and registered as an observation-family ``source_type`` (``message_family
("decision") == "observation"``), so a permanence actuation may later cite a decision as its
justifying ``causes``. It is minted BESIDE the a5 ``aio-decision`` observations (prereg D-1's
second option), not by extending them: the a5 verdict shape (``cell_id``/``subject_status``)
carries none of the s2 fields and is not retrievable by category, while this family carries a
structured body — ``{what, why, alternatives[], category, decided_at, actor}`` plus
``run_id``/``candidate_sha`` when bound — and is retrievable by ``category``.

``source_type`` is ``"decision"`` — the SAME row the a5 permanence observations could have
carried, minted here as its own family (registered in ``knowledge.SOURCE_TYPES`` as
observation-family ADVISORY/``[H]``) so the registry census can separate decision rows from
supervisor verdicts and session closes. Disambiguation from every other observation-family
record is by ``extractor_version`` (``decision/v1``) + URI family (``decision:<id>``), exactly
the schema's one-table convention (session/``meta_session`` vs the legacy ledger lines).

The record's body (``text``) is a canonical JSON payload of the decision's content fields plus
the record's ``actor`` and ``scope``, serialized with sorted keys so the same input always
yields the same bytes — deterministic, so the shared factory's ``content_hash``/``knowledge_id``
are rerun-safe pure functions of the decision dict (identical re-record -> no-op).

Actor + scope follow the context abstraction (design §actor-layering): the command's producer
is the AIO and the record lives in the AIO org-root scope (``org:agentic-dynamics``) — carried
structurally on the record (``repository_id`` = the org id, ``acl_scope`` = ``org:<repository_id>``)
AND in the payload's ``scope`` key, exactly as the session spine does. A cell/workload retrieval
filters on its OWN ``repository_id`` (``retrieval.scope_excluded``), which never equals the org
id, so a cell agent cannot resolve these records; only an explicit org-root read sees them.
``actor`` travels in the payload as a first-class, self-describing field (the KB schema has no
``actor`` column): the s2a command records ``aio``; the s2b verified-command emissions record
``verified_command`` at the same org root.

Contract reuse: identical to the other producers — :func:`record_factory.build_record`
(identity + content-hash back-fill) + ``record_to_artifact``/``record_to_event`` from
:mod:`knowledge_ingestion`, published via ``knowledge_stream.publish_event``. The identity
mirrors the observation/actuation producers (per-event fact, never a same-entity supersession
chain): ``decision_id = hash(category | what | decided_at)`` — two decisions about the same
subject at different moments are independent facts, never colliding versions.
"""

from __future__ import annotations

import hashlib
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

#: ``source_type`` recorded on every decision record — registered in ``knowledge.SOURCE_TYPES``
#: as an observation-family ADVISORY ``[H]`` type (see the module docstring for why it is minted
#: beside, not inside, the a5 observation family).
SOURCE_TYPE = "decision"

#: The extractor generation. ``knowledge_id`` folds this in, so the decision family is
#: identity-distinct from every other observation-family producer (session/``meta_session``,
#: ``observation``, ``flag``) even for byte-identical bodies. A literal — stability is the point.
EXTRACTOR_VERSION = "decision/v1"

#: The producer/actor of the s2a command. The AIO is the command's operator; the value travels in
#: the payload (self-describing — the KB schema has no ``actor`` field). The s2b verified-command
#: emissions record ``verified_command`` instead, at the same org root.
ACTOR = "aio"

#: Fallback ``source_revision`` for a decision record. The record is the AIO's org-root posterior,
#: NOT bound to one commit — folding the checkout HEAD in as ``revision`` would re-key every record
#: as HEAD moves. Mirrors ``session_ingestion.REVISION_FALLBACK``.
REVISION_FALLBACK = "decision/unrevisioned"

#: The canonical decision categories the wave names (design §record types 2; the s2a command's
#: ``--category`` help): park (parked fleet/effort), model (flash-over-sonnet), name (the AIO
#: name), scope (a boundary). The set is DOCUMENTATION, not a validator — the categories are open
#: by design (the ``--category`` ellipsis); retrieval is exact-string on the recorded value.
DECISION_CATEGORIES = ("park", "model", "name", "scope")


# ── Small deterministic helpers ─────────────────────────────────


def _required_value(decision: dict[str, Any], field: str, label: str) -> str:
    """Return a required content field, stripping whitespace.

    Raises ``ValueError`` when the field is missing or empty — a decision with no ``what`` (its
    subject) or no ``category`` (its retrieval axis) cannot be registered.
    """
    value = str(decision.get(field) or "").strip()
    if not value:
        raise ValueError(f"decision has no {label!r} — cannot derive a decision record")
    return value


def _list_value(decision: dict[str, Any], field: str) -> list[str]:
    """Normalize a list-valued content field to a deterministic ``list[str]``.

    ``None``/missing → ``[]``; a ``list``/``tuple`` is kept in CALLER order (the alternatives
    weighed are the caller's ordering, never re-sorted) with each element coerced to ``str``.
    """
    value = decision.get(field)
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


def _optional_value(decision: dict[str, Any], field: str) -> str:
    """Return an optional binding field (``run_id``/``candidate_sha``), stripped, or ``""``."""
    return str(decision.get(field) or "").strip()


def _decision_id(category: str, what: str, decided_at: str) -> str:
    """Return a stable identity for ONE decision event.

    Folds ``decided_at`` deliberately, mirroring the observation/actuation producers' per-event
    identity: "one identity per candidate, not per subject" — two decisions about the same subject
    at different moments are independent facts (a later re-decision is a NEW decision, never a
    silently-overwritten duplicate of the earlier one).
    """
    return hashlib.sha256(f"{category}|{what}|{decided_at}".encode()).hexdigest()[:16]


# ── The canonical content payload ───────────────────────────────


def decision_payload(
    decision: dict[str, Any], *, repository_id: str = REPOSITORY_ID
) -> dict[str, Any]:
    """Return the canonical content payload for ONE decision record.

    Exactly the s2 content fields (normalized) plus ``actor`` and ``scope`` — the record's
    context-abstraction dimensions. ``scope`` mirrors the record's own ``acl_scope``
    (``aio_acl_scope(repository_id)``); ``actor`` defaults to the module's ``ACTOR`` literal but a
    caller may override it (the s2b verified-command emissions pass ``verified_command``).
    ``run_id``/``candidate_sha`` appear ONLY when bound — an unbound decision is cleanly a
    decision, not a decision-plus-empty-hooks. This dict is what ``text`` serializes (sorted
    keys), so it is the entire hashed body: two derivations of the same decision dict yield
    byte-identical bodies and therefore identical ids (rerun-safe), while a changed rationale or
    a new binding yields a new body and a new ``knowledge_id`` for the same decision event.
    """
    payload: dict[str, Any] = {
        "what": _required_value(decision, "what", "what"),
        "why": str(decision.get("why") or "").strip(),
        "alternatives": _list_value(decision, "alternatives"),
        "category": _required_value(decision, "category", "category"),
        "decided_at": _required_value(decision, "decided_at", "decided_at"),
        "actor": str(decision.get("actor") or ACTOR).strip(),
        "scope": aio_acl_scope(repository_id),
    }
    for field in ("run_id", "candidate_sha"):
        value = _optional_value(decision, field)
        if value:
            payload[field] = value
    return payload


# ── Record construction ─────────────────────────────────────────


def build_decision_record(
    decision: dict[str, Any],
    *,
    repository_id: str = REPOSITORY_ID,
    now: datetime | None = None,
) -> KnowledgeRecord:
    """Derive ONE ``source_type=decision`` record from a decision dict.

    ``decision`` is ``{what, why, alternatives[], category, decided_at, actor, run_id?,
    candidate_sha?}`` — ``what`` and ``category`` required, ``decided_at`` required (the command
    defaults it to the decision moment), ``run_id``/``candidate_sha`` optional bindings. The
    record's ``text`` is the canonical JSON body from :func:`decision_payload` — deterministic,
    so ``content_hash``/``knowledge_id`` are rerun-safe for identical input.

    Identity follows the observation/actuation per-event contract:

    * ``logical_locator`` is ``decision_id`` (hash of ``category|what|decided_at``); ``source_uri``
      is ``decision:<decision_id>`` — a family distinct from ``observation:<id>`` /
      ``session:<slug>`` / ``flag_stream:<session>``.
    * ``revision`` is :data:`REVISION_FALLBACK` (not bound to one commit).
    * ``entity_id = sha256(repository_id | source_uri | logical_locator)``; ``content_hash`` is the
      sha256 of the durable artifact; ``knowledge_id`` folds them with the revision + the
      ``decision/v1`` extractor. Re-recording an identical decision is a no-op; recording the same
      subject at a NEW ``decided_at`` is a NEW decision event (new entity), never a collision.

    ``authority`` is ``ADVISORY`` / ``[H]`` — the registered nominal for ``decision`` (a decision
    is the AIO's own account of its choice, self-reported like a session close or an observation,
    never an independent measurement). ``repository_id`` defaults to the org id and ``acl_scope``
    to the AIO org-root scope (see :func:`aio_acl_scope`). ``observed_at`` is the decision's own
    moment — the real "when this happened" — while ``valid_from``/``indexed_at`` stay the
    derivation/consumer clocks.

    Raises ``ValueError`` when the decision carries no ``what``, no ``category``, or no
    ``decided_at``.
    """
    payload = decision_payload(decision, repository_id=repository_id)
    decided_at = payload["decided_at"]
    decision_id = _decision_id(payload["category"], payload["what"], decided_at)
    scope = aio_acl_scope(repository_id)

    return build_record_from_parts(
        source_type=SOURCE_TYPE,
        source_uri=f"decision:{decision_id}",
        logical_locator=decision_id,
        repository_id=repository_id,
        revision=REVISION_FALLBACK,
        authority=Authority.ADVISORY,
        evidence_class="[H]",
        text=json.dumps(payload, sort_keys=True),
        extra_fields={
            # The decision record is not tied to a commit of its own — mirror the observation
            # producer, which passes commit_sha="" while folding its revision marker through the
            # `revision` input (record_factory's contract).
            "commit_sha": "",
            "extractor_version": EXTRACTOR_VERSION,
            "acl_scope": scope,
            # observed_at is the decision's own moment (decided_at), not the command wall-clock;
            # the artifact blanks it, so it never perturbs the rerun-safe content hash.
            "observed_at": decided_at,
        },
        now=now,
    )


def derive_decision_record(
    decision: dict[str, Any],
    *,
    repository_id: str = REPOSITORY_ID,
    now: datetime | None = None,
) -> KnowledgeRecord:
    """Public derivation entry point — delegates to :func:`build_decision_record`.

    Deliberately singular (like the observation producer): one decision dict always yields exactly
    one decision record, with no batch pre-filter case. A decision missing its ``what``/
    ``category``/``decided_at`` is a genuine caller error, not a skip case.
    """
    return build_decision_record(decision, repository_id=repository_id, now=now)


# ── Record emission (the ``decision record`` command's write seam) ─────────


@dataclass
class DecisionRecordResult:
    """What one :func:`record_decision` call did — the command's outcome.

    ``record`` is the derived decision record (always present — derivation happens before any
    store access, so a call site can cite its ``knowledge_id`` even when every publish path
    failed). ``artifact_path`` is the durable per-record artifact the call wrote (or confirmed
    already present). ``entry_id`` is the stream entry the pointer event landed on, or ``""``
    when nothing was published by this call.

    ``status`` is one of:

    * ``"recorded"`` — the record now fully lands in the KB: its durable artifact is written and
      its pointer event was published this call (including the repair of a prior partial record,
      where the artifact existed but the event had never landed).
    * ``"no-op"`` — re-recording an already-recorded decision: the exact record (identical bytes)
      was already durable AND its event was already checkpointed, so this call changed nothing
      (rerun-safe).
    * ``"degraded"`` — the durable artifact is written but the event could not be published or its
      prior publication could not be confirmed (a downed or rejecting knowledge stream). This is a
      WARNING, never a crash: ``warnings`` carries the reason, and re-running the command once the
      stream is back completes the publication.

    ``warnings`` lists every producer failure this call swallowed (empty on a clean path).
    """

    record: KnowledgeRecord
    status: str
    artifact_path: Path
    entry_id: str = ""
    warnings: list[str] = _dataclass_field(default_factory=list)


def record_decision(
    decision: dict[str, Any],
    *,
    repository_id: str = REPOSITORY_ID,
    artifact_dir: Path | None = None,
    connect_fn: Callable[..., Any] | None = None,
    now: datetime | None = None,
) -> DecisionRecordResult:
    """Record ONE decision: derive its record, land artifact + event in the KB, best-effort.

    This is the write seam of the ``agentic-dynamics decision record`` command (phase
    ``s2a_decision_command`` of the ``self_knowledge_layer`` wave). It follows the producers'
    canonical pointer contract exactly as the session close does — write the durable per-record
    artifact to ``<artifact_dir>/<knowledge_id>.json`` FIRST (so a consumer can read + verify the
    bytes the event's ``content_hash`` covers the moment the pointer lands), then publish the
    pointer event and checkpoint the ``knowledge_id``.

    **Rerun-safe no-op.** ``knowledge_id`` is a pure function of the decision dict, so a repeated
    record of the same decision (identical ``decided_at`` included) resolves to the same record.
    The record is a no-op when the artifact is already on disk with byte-identical content AND the
    ``knowledge_id`` is already checkpointed; a prior partial failure (artifact written, event
    never published) is REPAIRED by re-running — the event is published and the record reaches
    ``"recorded"``.

    **A producer failure is a warning, never a crash.** A downed or rejecting knowledge stream is
    caught, logged into ``warnings``, and reported as ``status="degraded"`` — the durable artifact
    still lands (the record is never lost) and re-running when the stream is back completes the
    publication. A decision at the end of the AIO's operating cadence must never be discarded by a
    stream outage.

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

    record = derive_decision_record(decision, repository_id=repository_id, now=now)
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
    # seam IS the AIO's authorized decision recorder); the checkpoint hash makes the publish
    # idempotent so a re-record never double-emits.
    connect = connect_fn or ks.connect
    entry_id = ""
    already_published = False
    try:
        r = connect()
    except Exception as exc:  # noqa: BLE001 - a producer failure is a warning by contract
        warnings.append(
            f"knowledge stream unreachable ({type(exc).__name__}: {exc}); the durable record "
            "is written but the pointer event was not published — re-run `decision record` once "
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
                "re-run `decision record` once the stream is healthy to complete it"
            )

    if already_durable and already_published and not warnings:
        status = "no-op"
    elif warnings:
        status = "degraded"
    else:
        status = "recorded"
    return DecisionRecordResult(
        record=record,
        status=status,
        artifact_path=artifact_path,
        entry_id=entry_id,
        warnings=warnings,
    )


# ── Retrieval-by-category (the read seam the command's DONE_WHEN rests on) ──


def decision_artifact_files(artifact_dir: Path) -> list[Path]:
    """Every ``*.json`` file under the durable artifact dir, in filename order.

    The artifact dir is shared by EVERY producer, so this is a *scan*, not a read of one known
    file: the decision family is found by content, never by guessable filename. A missing dir is
    simply empty.
    """
    if not artifact_dir.is_dir():
        return []
    return sorted(artifact_dir.glob("*.json"), key=lambda path: path.name)


_ARTIFACT_RECORD = "record"
_ARTIFACT_FOREIGN = "foreign"
_ARTIFACT_ANOMALY = "anomaly"


def _classify_decision_artifact(
    path: Path, *, repository_id: str = REPOSITORY_ID
) -> tuple[str, dict[str, Any] | None, dict[str, Any] | None]:
    """Classify ONE durable artifact file into ``(kind, artifact_fields, payload)``.

    The kind is one of:

    * ``"record"`` — an org-root decision record: ``(artifact, payload)`` is returned. Unlike the
      session classifier there is NO actor equality check: decisions are recorded by the AIO
      (s2a, ``actor: aio``) AND by the verified commands (s2b, ``actor: verified_command``) at the
      SAME org root, so every org-scope decision is a legitimate read for the controller + AIO.
    * ``"foreign"`` — NOT a decision record of this org scope: any other producer's artifact (the
      ``extractor_version`` discriminator), a record from another repository, or an undecodable
      file. Skipped silently.
    * ``"anomaly"`` — IS a ``decision/v1`` artifact of this org but is NOT a readable org-root
      decision record: a corrupt decision artifact or a record whose body ``scope`` is not the
      org root's (a layering violation). Surfaced as a warning — an honest signal, never a silent
      skip.
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
        # A decision/v1 record of ANOTHER repository: legitimately not ours, skipped silently.
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
    if payload.get("scope") != aio_acl_scope(repository_id):
        return _ARTIFACT_ANOMALY, None, None
    return _ARTIFACT_RECORD, artifact, payload


def scan_decision_records(
    *,
    category: str | None = None,
    repository_id: str = REPOSITORY_ID,
    artifact_dir: Path | None = None,
) -> tuple[list[tuple[Path, dict[str, Any], dict[str, Any]]], list[str]]:
    """Scan the durable artifact dir for every org-root decision record, optionally by category.

    Returns ``(triples, warnings)`` where each triple is ``(path, artifact_fields, payload)`` for
    one decision record in the requested org scope, and ``warnings`` names the ``decision/v1``
    artifacts of this org that are NOT readable org-root decision records (the classifier's
    ``anomaly`` kind). When ``category`` is given, only records whose payload ``category`` equals
    it (exact string) are returned — the command's "retrievable-by-category" DONE_WHEN.

    The read is a DIRECT read of the durable artifacts the write seam produces — never the
    registry projection, which requires a live consumer: the round-trip (record then retrieve)
    must be exact the moment the record lands. ``artifact_dir`` defaults to the repo's durable KB
    artifact directory (``core.paths.KB_ARTIFACT_DIR``).
    """
    from agentic_dynamics.core.paths import KB_ARTIFACT_DIR

    artifact_dir = artifact_dir or KB_ARTIFACT_DIR
    warnings: list[str] = []
    triples: list[tuple[Path, dict[str, Any], dict[str, Any]]] = []
    for path in decision_artifact_files(artifact_dir):
        kind, artifact, payload = _classify_decision_artifact(path, repository_id=repository_id)
        if kind == _ARTIFACT_RECORD:
            if category is not None and payload.get("category") != category:
                continue
            triples.append((path, artifact, payload))
        elif kind == _ARTIFACT_ANOMALY:
            warnings.append(
                f"{path.name}: a decision/v1 artifact that is not a readable org-root decision "
                "record — excluded from the decision read"
            )
    return triples, warnings


def render_decision_summary(
    triples: list[tuple[Path, dict[str, Any], dict[str, Any]]],
) -> str:
    """Render decision triples as the human one-line-per-record listing.

    Used by the read-side tooling and tests to show what a category scan resolves: each record's
    ``what``, ``category``, ``decided_at``, and ``actor`` plus its durable artifact name.
    """
    lines = []
    for path, _artifact, payload in triples:
        binding = ""
        if payload.get("run_id") or payload.get("candidate_sha"):
            parts = []
            if payload.get("run_id"):
                parts.append(f"run {payload['run_id']}")
            if payload.get("candidate_sha"):
                parts.append(f"candidate {payload['candidate_sha'][:12]}")
            binding = f" ({', '.join(parts)})"
        lines.append(
            f"[decision] {payload.get('what')} [{payload.get('category')} @ "
            f"{payload.get('decided_at')} by {payload.get('actor')}]{binding} — {path.name}"
        )
    return "\n".join(lines)
