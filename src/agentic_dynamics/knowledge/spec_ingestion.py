"""Producer-side spec-lifecycle ingestion for the runtime-RAG knowledge base.

This is the *spec* ingestion path — one ``source_type="spec"`` record per experiment spec,
derived from the machine index :mod:`instrument.spec_status` generates
(``experiments/specs/index.json``). It answers, inside the KB and the registry, the question
that motivated the whole spec-lifecycle layer: **what specs exist, what is done, when, and
what supersedes what.**

Relationship to the sibling producers (do NOT conflate them):

* :mod:`agentic_dynamics.knowledge.policy_ingestion` already globs the split spec layout (``experiments/definitions/*.yaml`` + ``workflows/**/*.yaml``) and emits a
  ``source_type="policy"`` record carrying the file's leading *text excerpt*, for citation.
  That is the spec **document**.
* This module emits a ``source_type="spec"`` record carrying the spec's **lifecycle** —
  status, version, supersedes chain, last run, latest outcome, results pointer. Different
  source type, different extractor, different entity key. Both may exist for the same YAML
  and neither invalidates the other.

Identity (the one thing that makes lineage work):

* ``entity_id`` is the readable logical key ``spec:<name>`` — deliberately NOT the canonical
  ``sha256(repository_id|source_uri|logical_locator)``, and threaded through
  :func:`instrument.record_factory.build_record`'s ``entity_id`` seam so the record field and
  the ``knowledge_id`` input can never diverge. A spec's *name* is its identity across every
  version of its lifecycle; keying on it makes the version chain greppable in
  ``registry_index.jsonl`` and directly addressable by ``scripts/registry.py show spec:<name>``.
* ``knowledge_id`` = ``sha256(entity_id | revision | content_hash | extractor_version)``, the
  standard contract, so a re-derivation over unchanged input yields the same id and the
  producer's checkpoint skips it.
* ``operation`` is ``"supersede"`` (and ``supersedes`` is set to the predecessor's
  ``knowledge_id``) whenever the registry already holds a record for the SAME ``entity_id``.
  That is precisely what lets ``scripts/generate_manifest.py``'s compaction derive
  ``lifecycle_state`` ``current`` for the newest version and ``superseded`` for its
  predecessors — the same-entity version chain, not a cross-entity link.

Authority is ``POLICY`` / ``"[P]"`` — a spec is authored, pinned repository policy read from
the checkout, not a measurement. Per :mod:`instrument.policy_ingestion`'s load-bearing note,
POLICY records are indexed for discoverability and citation, never as RRF fusion candidates.

Contract (do NOT invent a second one): ``record_to_artifact`` serializes the record to its
durable per-record JSON (``content_hash = sha256(artifact)``) and ``record_to_event`` emits
the pointer-only event at ``file://experiments/results/kb/<knowledge_id>.json`` — identical
to the finding/code/quality/policy paths.

Determinism: ``revision`` (git HEAD sha) is **injected** and folded into every
``knowledge_id``; ``text`` is a pure function of the index entry (and, importantly, does NOT
depend on ``record.supersedes``, so the same lifecycle content always fingerprints the same
way regardless of where it sits in the chain). ``now`` is injectable for tests. No LLM is
involved.

Design: ``workflows/repository/spec_lifecycle.yaml`` phase ``kb_registry``.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from agentic_dynamics.core.paths import KB_ARTIFACT_DIR, PROJECT_ROOT, REGISTRY_INDEX_PATH
from agentic_dynamics.experiment.spec_status import INDEX_FILENAME, SPECS_DIR_REL, SpecStatusEntry
from agentic_dynamics.knowledge.knowledge import Authority, KnowledgeEvent, KnowledgeRecord
from agentic_dynamics.knowledge.knowledge_ingestion import (
    REPOSITORY_ID,
    record_to_artifact,
    record_to_event,
)
from agentic_dynamics.knowledge.record_factory import build_record as build_record_from_parts

# ── Extractor contract constants ────────────────────────────────

#: The extractor generation for spec-lifecycle records. ``knowledge_id`` folds this in, so
#: bumping it yields a new id for the *same* spec (a new extractor must never silently
#: overwrite the previous one's identity). Literal on purpose, mirroring every sibling path.
EXTRACTOR_VERSION = "spec-lifecycle/v1"

#: ``source_type`` recorded on every record from this path. Registered in
#: :data:`instrument.knowledge.SOURCE_TYPES` as an OBSERVATION with POLICY authority.
SOURCE_TYPE = "spec"

#: Default ACL scope. The spec corpus is public repository content.
ACL_SCOPE = "public"

#: Prefix of the ``reason`` annotation carried on a spec record's pointer event and recorded
#: in ``registry_index.jsonl``. It holds :func:`lifecycle_fingerprint` — a hash of the
#: record's ``text``, which is a pure function of the lifecycle content and independent of
#: the record's position in the supersession chain. Without it the producer could not tell
#: "the lifecycle actually changed" from "I linked a new version last time, so my id moved",
#: and every re-run would append another link to a chain that never converges. See
#: :func:`derive_spec_records`.
REASON_PREFIX = "spec-lifecycle-content="

#: Fallback ``source_revision`` when no git sha is supplied. Pinned to the index's own schema
#: generation rather than fabricating a commit — the same posture as
#: ``knowledge_ingestion.RESULT_VERSION``.
REVISION_FALLBACK = "spec-index/v1"


# ── Entity identity ─────────────────────────────────────────────


def spec_entity_id(name: str) -> str:
    """Return the logical entity key for a spec: ``"spec:<name>"``.

    The spec's *name* is what stays constant across every version of its lifecycle, so it —
    not the file path, not a content hash — is the entity. Readable on purpose: this string
    is what lands in ``registry_index.jsonl`` and what ``scripts/registry.py show`` resolves.
    """
    return f"spec:{name}"


def spec_source_uri(spec_path: str) -> str:
    """Return the record's provenance URI for a spec YAML: ``file://<repo-relative path>``.

    The ``file://`` form is the repo-wide URI contract (``knowledge_stream.read_artifact``
    strips the prefix and resolves the remainder against the checkout root), so a consumer can
    open the authoritative YAML straight from the record.
    """
    return f"file://{spec_path}"


# ── The record body ─────────────────────────────────────────────


def _fmt(value: Any) -> str:
    """Render one lifecycle value for the record body; ``None``/empty become ``"-"``.

    A single explicit placeholder (rather than an empty right-hand side) keeps every line
    parseable by :func:`parse_spec_text` and keeps the fingerprint stable — "absent" must
    serialize one way and one way only.
    """
    if value is None or value == "" or value == []:
        return "-"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value)
    return str(value)


def spec_text(entry: SpecStatusEntry) -> str:
    """Render the record body: a deterministic ``key: value`` block, one line per field.

    This is where the lifecycle fields (``status`` / ``last_run_at`` / ``completed_at`` /
    ``latest_ok`` / ``results_pointer`` and the rest) travel. :class:`KnowledgeRecord` is a
    frozen canonical schema with a hashing contract — adding spec-specific columns to it
    would re-key every producer's artifacts — so the structured surface lives in ``text``, in
    a machine-parseable form (:func:`parse_spec_text` round-trips it) rather than as prose.
    The four fields that DO have exact homes on the schema are additionally mapped onto them
    by :func:`build_spec_record`.

    Two properties this rendering must keep:

    * **Deterministic** — same entry, same bytes, so ``content_hash``/``knowledge_id`` are
      reproducible and the producer is idempotent.
    * **Independent of the supersession chain** — the ``supersedes`` line lists spec *names*
      from the YAML, never the predecessor ``knowledge_id``. That is what lets
      :func:`lifecycle_fingerprint` answer "did the lifecycle change?" without being
      perturbed by the record's own position in the chain.
    """
    lines = [
        f"spec {entry.name}@{entry.version} — {_fmt(entry.status)}",
        f"name: {entry.name}",
        f"version: {_fmt(entry.version)}",
        f"status: {_fmt(entry.status)}",
        f"supersedes: {_fmt(entry.supersedes)}",
        f"superseded_by: {_fmt(entry.superseded_by)}",
        f"completed_at: {_fmt(entry.completed_at)}",
        f"last_run_at: {_fmt(entry.last_run_at)}",
        f"latest_ok: {_fmt(entry.latest_ok)}",
        f"latest_model: {_fmt(entry.latest_model)}",
        f"latest_cost_usd: {_fmt(entry.latest_cost_usd)}",
        f"latest_git_sha: {_fmt(entry.latest_git_sha)}",
        f"n_runs: {entry.n_runs}",
        f"results_pointer: {_fmt(entry.results_pointer)}",
        f"spec_path: {_fmt(entry.spec_path)}",
    ]
    return "\n".join(lines)


def parse_spec_text(text: str) -> dict[str, str]:
    """Parse a :func:`spec_text` body back into its ``{key: value}`` mapping.

    The inverse of the rendering, so a consumer (or a test) can read the structured lifecycle
    off a record without re-deriving it from the index. The leading summary line has no
    ``": "`` separator in key position and is skipped. Values keep the ``"-"`` placeholder
    verbatim — the caller decides what "absent" should become in its own domain.
    """
    parsed: dict[str, str] = {}
    for line in text.splitlines()[1:]:  # skip the human-readable summary line
        key, sep, value = line.partition(": ")
        if sep:
            parsed[key.strip()] = value.strip()
    return parsed


def lifecycle_fingerprint(record: KnowledgeRecord) -> str:
    """Return the sha256 of a spec record's body — the "has the lifecycle changed?" key.

    Computable from the record alone (at derive time and again at emit time), and — because
    :func:`spec_text` never mentions the predecessor ``knowledge_id`` — invariant to the
    record's position in the supersession chain. :func:`derive_spec_records` compares this
    against the fingerprint the registry recorded for the entity's current head; equal means
    nothing about the spec's lifecycle moved, so no new version is emitted.
    """
    return hashlib.sha256(record.text.encode("utf-8")).hexdigest()


def spec_reason(record: KnowledgeRecord) -> str:
    """Return the ``reason`` annotation to carry on a spec record's pointer event.

    ``KnowledgeEvent.reason`` is documented as the supersession/tombstone reason and "also
    reused as a caveat annotation"; ``kb_worker.py``'s registry handler writes it verbatim
    into ``registry_index.jsonl``. That makes it the one field on the registry line able to
    carry the lifecycle fingerprint forward to the next producer run.
    """
    return f"{REASON_PREFIX}{lifecycle_fingerprint(record)}"


def spec_operation(record: KnowledgeRecord) -> str:
    """Return the pointer event's ``operation`` for a spec record.

    A record that names a predecessor IS a new version of an existing entity, which is
    exactly what ``supersede`` means (``knowledge.py``: "``supersede`` links a new version to
    its predecessor"). Everything else is a plain ``upsert``. Deriving the operation from the
    record rather than passing it alongside means the two can never disagree.
    """
    return "supersede" if record.supersedes else "upsert"


# ── Record construction ─────────────────────────────────────────


def build_spec_record(
    entry: SpecStatusEntry | dict[str, Any],
    *,
    repository_id: str = REPOSITORY_ID,
    revision: str = REVISION_FALLBACK,
    supersedes: str | None = None,
    now: datetime | None = None,
) -> KnowledgeRecord:
    """Derive ONE ``source_type="spec"`` record from a single ``index.json`` entry.

    ``entry`` may be a :class:`~instrument.spec_status.SpecStatusEntry` or the plain dict
    straight out of ``index.json`` (coerced here), so a caller never has to pre-convert.

    Field mapping — the lifecycle travels in ``text`` (see :func:`spec_text`), plus the four
    values that have an exact home on the canonical schema:

    * ``subject_status`` ← the derived lifecycle status. ``subject_status`` is defined as "the
      structured subject this record describes"'s state; for a spec that is its status, and
      putting it here means a consumer never has to text-split for it.
    * ``subject_id`` ← ``results_pointer``, the concrete run ledger this status was derived
      from (empty when the spec has never run).
    * ``observed_at`` ← ``last_run_at``, the record's OWN observation time — the moment the
      evidence behind this status was produced, not the producer's wall clock. Falls back to
      ``now`` for a spec with no runs. ``record_to_event`` carries it onto the pointer.
    * ``symbols`` ← the spec names this spec supersedes, so lineage is queryable without
      parsing the body.
    * ``outcome_id`` ← ``"<name>@<version>"``, the ledger's ``spec_id`` — the join key back to
      the job/attempt records ``workflow_runner`` now stamps.

    ``test_executed_success`` is deliberately left ``None``. ``latest_ok`` means "every phase
    of the last run succeeded", which is not the same claim as "a test suite was
    independently executed and passed"; fabricating one from the other is exactly the
    conflation the ledger's measured-or-``None`` discipline exists to prevent. ``latest_ok``
    is reported in the body instead.

    ``supersedes`` (the predecessor ``knowledge_id``) is normally supplied by
    :func:`derive_spec_records` after it consults the registry; pass it directly only when
    you are constructing a chain explicitly (as the tests do).
    """
    if not isinstance(entry, SpecStatusEntry):
        entry = SpecStatusEntry.from_dict(entry)

    text = spec_text(entry)

    # `observed_at` is the record's OWN observation time — the moment the evidence behind this
    # status was produced. For a spec that is its last run; a never-run spec has no such
    # moment, so the field is simply omitted and the factory's producer clock stands in
    # (fabricating a run time would be worse than admitting there wasn't one).
    extra: dict[str, Any] = {
        "extractor_version": EXTRACTOR_VERSION,
        "acl_scope": ACL_SCOPE,
        "language": "yaml",
        "symbols": list(entry.supersedes),
        "outcome_id": f"{entry.name}@{entry.version}",
        "subject_id": entry.results_pointer or "",
        "subject_status": entry.status,
        "supersedes": supersedes,
    }
    if entry.last_run_at:
        extra["observed_at"] = entry.last_run_at

    return build_record_from_parts(
        source_type=SOURCE_TYPE,
        source_uri=spec_source_uri(entry.spec_path),
        logical_locator=entry.name,  # the spec name — the human-resolvable locator
        repository_id=repository_id,
        revision=revision,
        authority=Authority.POLICY,
        evidence_class="[P]",
        text=text,
        entity_id=spec_entity_id(entry.name),
        extra_fields=extra,
        now=now,
    )


# ── Registry lookup (the supersede decision) ────────────────────


class RegistryHead:
    """The current head of one entity's version chain, as recorded in the registry index.

    A tiny value object rather than a tuple so the two fields are named at every call site —
    mixing up "the predecessor id" and "the predecessor's content fingerprint" would produce
    a chain that silently never converges.
    """

    __slots__ = ("knowledge_id", "fingerprint")

    def __init__(self, knowledge_id: str, fingerprint: str = "") -> None:
        self.knowledge_id = knowledge_id
        #: The lifecycle fingerprint recorded on that head's registry line (parsed out of its
        #: ``reason``), or ``""`` when the line predates the annotation.
        self.fingerprint = fingerprint

    def __repr__(self) -> str:  # pragma: no cover — debugging aid
        return f"RegistryHead({self.knowledge_id!r}, fingerprint={self.fingerprint!r})"

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, RegistryHead)
            and other.knowledge_id == self.knowledge_id
            and other.fingerprint == self.fingerprint
        )


def _fingerprint_from_reason(reason: str, prefix: str = REASON_PREFIX) -> str:
    """Extract a lifecycle/content fingerprint from a registry line's ``reason``, or ``""``.

    The ``prefix`` is parameterised so the fact plane (``control.fact_ingestion``) can reuse
    ``registry_head`` with its own ``fact-content=`` annotation instead of duplicating the
    two-pass head resolution.
    """
    text = str(reason or "")
    return text[len(prefix):] if text.startswith(prefix) else ""


def registry_head(
    entity_id: str,
    *,
    registry_path: Path | str = REGISTRY_INDEX_PATH,
    reason_prefix: str = REASON_PREFIX,
) -> RegistryHead | None:
    """Return the current (non-superseded) head of ``entity_id``'s chain, or ``None``.

    ``registry_index.jsonl`` is flat and append-only: one line per registered record, plus a
    "predecessor superseded" marker line that ``kb_worker.py`` appends at supersede time.
    Finding the head therefore means the same two-pass reasoning ``generate_manifest.py``
    applies at compaction:

    1. a ``knowledge_id`` named by some other line's ``supersedes`` has been replaced;
    2. so has one whose own line says ``lifecycle_state == "superseded"`` (the marker).

    Whatever survives, latest-in-file-order wins. A missing file, an unreadable one, or a
    truncated JSON line all degrade to "no head" / skip-the-line — a producer must never be
    blocked by a damaged index, and treating a damaged index as "no predecessor" fails toward
    a plain ``upsert`` rather than toward a bogus lineage link.

    ``reason_prefix`` selects which annotation prefix carries the fingerprint (the spec
    lifecycle's ``spec-lifecycle-content=`` by default; the fact plane passes
    ``fact-content=``) — it is how one shared head-resolution serves both producers.
    """
    path = Path(registry_path)
    order: list[str] = []
    lines: dict[str, dict[str, Any]] = {}
    superseded: set[str] = set()

    try:
        raw_lines = path.read_text().splitlines()
    except (OSError, UnicodeDecodeError):
        return None

    for raw in raw_lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue  # a truncated line must not hide the rest of the history
        if not isinstance(row, dict) or row.get("entity_id") != entity_id:
            continue
        kid = row.get("knowledge_id")
        if not kid:
            continue
        if row.get("supersedes"):
            superseded.add(str(row["supersedes"]))
        if row.get("lifecycle_state") == "superseded":
            superseded.add(str(kid))
        if kid not in lines:
            order.append(str(kid))
        # Latest line for an id wins: a record's own registration line carries the reason.
        lines[str(kid)] = row

    for kid in reversed(order):
        if kid not in superseded:
            return RegistryHead(
                kid, _fingerprint_from_reason(lines[kid].get("reason", ""), reason_prefix)
            )
    return None


# ── The public derivation entry point ───────────────────────────


def derive_spec_records(
    entries: Iterable[SpecStatusEntry | dict[str, Any]],
    *,
    repository_id: str = REPOSITORY_ID,
    revision: str = REVISION_FALLBACK,
    registry_path: Path | str = REGISTRY_INDEX_PATH,
    now: datetime | None = None,
) -> list[KnowledgeRecord]:
    """Derive one ``source_type="spec"`` record per spec whose lifecycle needs registering.

    For each index entry, in input order:

    1. Build the record with no predecessor link.
    2. Look up the entity's current head in ``registry_index.jsonl``.
    3. **No head** → this is a first version. Emit it as-is (``operation="upsert"``).
    4. **Head whose fingerprint matches** → the spec's lifecycle has not moved since it was
       last registered. Emit **nothing** for it. This is the convergence guard: because
       linking a predecessor changes ``supersedes`` and therefore ``content_hash`` and
       therefore ``knowledge_id``, an id-only comparison would make every re-run look like a
       change and grow the chain forever. The fingerprint is content-only, so a re-run over
       unchanged specs is a genuine no-op.
    5. **Head whose fingerprint differs** (or a head from before the annotation existed) →
       rebuild with ``supersedes=<head knowledge_id>``, which makes
       :func:`spec_operation` report ``"supersede"`` and gives
       ``generate_manifest.py`` the link it needs to derive ``current`` vs ``superseded``.

    ``revision``, ``registry_path`` and ``now`` are injected for determinism and testability.
    No LLM is involved and nothing here writes: emission is the producer's job
    (``scripts/kb_produce_sources.py --source spec``, or :func:`emit_spec_record`).
    """
    records: list[KnowledgeRecord] = []
    for raw in entries:
        candidate = build_spec_record(
            raw, repository_id=repository_id, revision=revision, now=now
        )
        head = registry_head(candidate.entity_id, registry_path=registry_path)

        if head is None:
            records.append(candidate)  # first version of this entity
            continue
        if head.fingerprint and head.fingerprint == lifecycle_fingerprint(candidate):
            continue  # lifecycle unchanged since the last registration — nothing to say
        if head.knowledge_id == candidate.knowledge_id:
            continue  # byte-identical first version already registered

        records.append(
            build_spec_record(
                raw,
                repository_id=repository_id,
                revision=revision,
                supersedes=head.knowledge_id,
                now=now,
            )
        )
    return records


def spec_event(record: KnowledgeRecord, *, now: datetime | None = None) -> KnowledgeEvent:
    """Build the pointer-only event for a spec record, with operation + reason filled in.

    A thin, intention-revealing wrapper over ``knowledge_ingestion.record_to_event``: the
    ``operation`` comes from :func:`spec_operation` (derived from the record's own
    ``supersedes``) and the ``reason`` from :func:`spec_reason` (the lifecycle fingerprint the
    next producer run reads back off the registry line). Every emitter — the batch producer
    and the end-of-run hook — goes through this, so the two annotations can never drift.
    """
    return record_to_event(
        record, operation=spec_operation(record), reason=spec_reason(record), now=now
    )


# ── Index loading + the best-effort run-time emit ───────────────


def load_index_entries(*, root: Path | str = PROJECT_ROOT) -> list[SpecStatusEntry]:
    """Read the spec_catalog (``experiments/specs/index.json``) and return its entries.

    ``spec_catalog`` is this artifact's name in the control-plane vocabulary
    (``docs/architecture/current/control_plane_vocabulary.md``) — the derived index of what
    specs exist and which are done. It is NOT the knowledge_registry_log this module's records
    eventually land in, and not the run_state control database; all three are catalogs of
    records, which is exactly why the bare word "index" is avoided here.

    Returns ``[]`` when the spec_catalog is missing or unreadable — it is a *generated* artifact
    (``python scripts/spec_status.py``), so "not generated yet" is an ordinary state a producer
    must survive, not an error.
    """
    path = Path(root) / SPECS_DIR_REL / INDEX_FILENAME
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        return []
    entries: list[SpecStatusEntry] = []
    for raw in payload.get("specs", []) or []:
        if isinstance(raw, dict) and raw.get("name"):
            entries.append(SpecStatusEntry.from_dict(raw))
    return entries


@contextmanager
def _authorized_kb_write():
    """Authorize a knowledge-stream write for the duration of the context (env flag only).

    Verbatim in spirit from ``knowledge_ingestion._authorized_kb_write``:
    ``knowledge_stream.publish_event`` raises unless ``FINOPS_KB_WRITE=1``, and this emit
    path sets the flag for *just* the emit (then restores it) so the authorization never
    leaks to another writer in the same process.
    """
    prev = os.environ.get("FINOPS_KB_WRITE")
    os.environ["FINOPS_KB_WRITE"] = "1"
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop("FINOPS_KB_WRITE", None)
        else:
            os.environ["FINOPS_KB_WRITE"] = prev


def emit_spec_record(
    spec_name: str,
    *,
    root: Path | str = PROJECT_ROOT,
    repository_id: str = REPOSITORY_ID,
    revision: str = REVISION_FALLBACK,
    registry_path: Path | str = REGISTRY_INDEX_PATH,
    now: datetime | None = None,
) -> KnowledgeRecord | None:
    """Derive, durably write, and publish ONE spec's lifecycle record. Best-effort.

    The run-time half of this path, called by ``scripts/run_workflow.py`` after the index
    refresh. It follows ``workflow_runner._emit_self_finding``'s pattern exactly: the run has
    already finished and its ledger is already on disk, so a KB problem — Redis down, the
    write guard, a missing index — must degrade to ``None`` and never propagate. The caller
    logs; the run is untouched either way.

    Returns the emitted record, or ``None`` when there was nothing to emit (the spec is not in
    the index, or :func:`derive_spec_records` found its lifecycle unchanged) or when the emit
    failed. Ordering matches every sibling producer: the durable artifact lands *before* the
    pointer event, so a consumer can always read and verify the bytes the event hashes.
    """
    try:
        from . import knowledge_stream as _ks

        entries = [e for e in load_index_entries(root=root) if e.name == spec_name]
        if not entries:
            return None
        records = derive_spec_records(
            entries,
            repository_id=repository_id,
            revision=revision,
            registry_path=registry_path,
            now=now,
        )
        if not records:
            return None  # lifecycle unchanged — a genuine no-op, not a failure
        record = records[0]

        artifact = record_to_artifact(record)
        path = Path(KB_ARTIFACT_DIR) / f"{record.knowledge_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(artifact)

        with _authorized_kb_write():
            r = _ks.connect()
            _ks.publish_event(r, spec_event(record, now=now), source_type=record.source_type)
        return record
    except Exception:
        # Progressive path — never block or fail the run on a KB emission problem.
        return None
