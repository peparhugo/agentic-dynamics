"""Producer-side measured-finding derivation for the runtime-RAG knowledge base.

This module is the *richer* extractor that supersedes ``knowledge_stream.default_extract``
for the measured-result path. ``default_extract`` is the minimal, transport-facing v1
extractor: it carries an identity + arbitrary text through, with no notion of what that
text means. This module knows what a ``_results_summary.json`` entry *is* — a measured
experiment cell — and turns it into a :class:`~instrument.knowledge.KnowledgeRecord`
whose ``text`` is the derived one-line *finding* (the ``build_evidence_cards`` unit), not
raw retrieved steps and not synthesized prose.

Design: ``code_reviews/2026-08-15_rag-knowledge-base-proposal-review.md`` §7 (the
"evidence card" — *retrieve conclusions, not verbatim reasoning*) and the identity +
authority contract in :mod:`instrument.knowledge`.

Relationship to the other KB modules (one line each):

* :mod:`instrument.retrieval` — ``build_evidence_cards`` *renders* the one-line finding
  from a run's measured vector; this module *keys* that finding into a durable record.
* :mod:`instrument.knowledge_stream` — the Redis Streams *transport*. Its
  ``default_extract`` stays in place as the fallback for pointer events whose producer
  has no domain-specific extractor; ``knowledge_ingestion`` is the measured-result path,
  wired in as the ``extractor`` arg of ``process_entry``.
* :mod:`instrument.signal_store` — ``load_results`` supplies the same ``entries`` this
  module derives from, so the finding text and the routing signals describe the *same*
  measured row.
"""

from __future__ import annotations

import contextlib
import json
import math
import os
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

from .knowledge import (
    SCHEMA_VERSION,
    Authority,
    KnowledgeEvent,
    KnowledgeRecord,
)
from .record_factory import (
    _now_iso,
    _sha256_bytes,
    record_to_artifact,
)
from .record_factory import (
    build_record as build_record_from_parts,
)
from .paths import KB_ARTIFACT_DIR_REL
from .retrieval import build_evidence_cards

# ── Extractor contract constants ────────────────────────────────

#: The extractor generation. ``knowledge_id`` folds this in, so bumping it yields a new
#: ``knowledge_id`` for the *same* finding (a new extractor generation must never silently
#: overwrite the previous one's identity). It is deliberately a literal, not a module or
#: version probe — stability is the point: the same string must be reproducible forever.
EXTRACTOR_VERSION = "measured-finding/v1"

#: Durable locator of the source artifact these records derive from. A ``file://`` URI so a
#: consumer can ``knowledge_stream.read_artifact`` it directly (that helper strips the
#: ``file://`` prefix and resolves relative to the checkout root).
SOURCE_URI = "file://experiments/results/_results_summary.json"

#: Directory holding the per-record durable artifacts (repo-root-relative — the ``file://``
#: URI contract). Sourced from :mod:`instrument.paths` (canonical-state R6) so the producer
#: and every consumer's ``read_artifact`` stay on one path. ``record_to_event`` points at
#: ``file://<ARTIFACT_DIR>/<knowledge_id>.json`` — one JSON artifact per derived record — so a
#: consumer's ``read_artifact`` + ``verify_content_hash`` can verify the *exact* bytes the
#: event hashes (unlike the aggregate ``_results_summary.json``, whose bytes can never match a
#: per-finding hash).
ARTIFACT_DIR = KB_ARTIFACT_DIR_REL


def artifact_uri(knowledge_id: str) -> str:
    """Return the durable per-record ``file://`` URI for a record id.

    The producer (``scripts/kb_produce.py``) writes the artifact to this path before
    publishing the pointer event; the consumer (``knowledge_stream.process_entry``) reads it
    back via ``read_artifact`` and verifies ``content_hash`` against its bytes.
    """
    return f"file://{ARTIFACT_DIR}/{knowledge_id}.json"

#: Canonical repository identity (the rebranded ``agentic-dynamics`` id, per
#: ``docs/agentic_dynamics_rebrand_plan.md``). It is a stable component of ``entity_id`` so the
#: same logical cell converges on one identity across call sites. Overridable per derivation
#: via ``build_record``/``derive_records`` (the ``--repository-id`` producer flag) — the
#: default matches the producer CLI's default so the two stay in lockstep.
REPOSITORY_ID = "agentic-dynamics"

#: ``source_type`` recorded on every measured-finding record — a *finding* is a derived
#: conclusion over a measured vector, distinct from ``code``/``test``/``review``.
SOURCE_TYPE = "finding"

#: Default ACL scope. Experiment results are public corpus data; the workflow seam can pass
#: a narrower scope, but the summary path has no per-entry scoping.
ACL_SCOPE = "public"

#: Fallback ``source_revision`` when an entry carries no commit id. The current
#: ``_results_summary.json`` has no per-entry revision (its only version marker is
#: ``_meta.generated_at``), so the revision is pinned to the *result schema* version instead
#: of fabricating a commit. A future producer that stamps ``git_sha``/``commit``/``commit_sha``
#: on each entry will replace this wholesale (see :func:`_git_sha`).
RESULT_VERSION = "results/v1"

#: Repo root, resolved from this module's location (``src/instrument/`` → repo root). The
#: self-build emit path needs an absolute filesystem path to write the per-record artifact
#: regardless of the process cwd (``artifact_uri`` is repo-root-*relative*).
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

#: Extractor generation for the self-build ("progressive") phase-finding path. Distinct from
#: :data:`EXTRACTOR_VERSION` so a workflow-phase finding and a summary-derived finding never
#: collide on identity even for identical text (each folds its own extractor into
#: ``knowledge_id``).
PHASE_EXTRACTOR_VERSION = "phase-finding/v1"

#: Logical ``source_uri`` for phase findings. A workflow phase has no aggregate source file —
#: the durable per-record artifact *is* the source — so this is a stable namespace constant
#: folded into ``entity_id``; the real bytes are pointed at by ``artifact_uri`` on the event.
PHASE_SOURCE_URI = "file://workflow/phase"


# ── Entry-field derivation (pure, testable) ─────────────────────


def _git_sha(entry: dict[str, Any]) -> str:
    """Return the entry's commit id, or ``""`` when absent.

    A measured row may carry its producing commit under any of three names depending on
    which pipeline wrote it; the first non-empty one wins. When none is present the caller
    falls back to :data:`RESULT_VERSION` — never a fabricated SHA.
    """
    for key in ("git_sha", "commit", "commit_sha"):
        value = entry.get(key)
        if value:
            return str(value)
    return ""


def _run_id(entry: dict[str, Any]) -> str:
    """Return the entry's durable cell locator (``worktree_name``, else ``run_id``).

    This is the ``logical_locator`` of the record and therefore a component of ``entity_id``:
    it identifies *which* cell the finding belongs to, independent of which extractor or
    revision indexed it.
    """
    return str(entry.get("worktree_name") or entry.get("run_id") or "")


def _source_revision(entry: dict[str, Any]) -> str:
    """Return the source revision: the entry's commit id, else :data:`RESULT_VERSION`.

    The commit id (when present) ties the finding to the exact checkout it was measured on;
    when the summary carries none, the result-schema version is the honest revision marker.
    """
    return _git_sha(entry) or RESULT_VERSION


#: Field names probed on a results entry for a per-run *observation* timestamp. The current
#: ``_results_summary.json`` schema has **none** of these — its only timestamp is the batch
#: ``_meta.generated_at`` — so :func:`_observed_at` falls back to the producer ``now`` in
#: practice. The probe is kept explicit (rather than assuming a field exists) so a future
#: producer that stamps a per-entry timestamp is honored without fabricating one today.
_TIMESTAMP_FIELDS = (
    "ended_at",
    "observed_at",
    "timestamp",
    "run_at",
    "finished_at",
    "created_at",
    "started_at",
)


def _observed_at(entry: dict[str, Any], *, now: datetime | None = None) -> str:
    """Return the entry's run timestamp when present, else the producer ``now``.

    Only a non-empty *string* value is accepted (a per-entry ISO timestamp); anything else
    (missing, numeric epoch, empty) falls back to ``now`` — we never fabricate a timestamp
    the summary does not actually carry. ``valid_from``/``indexed_at`` stay the producer
    ``now`` regardless (they describe *this* derivation/indexing pass, not the measurement).
    """
    for key in _TIMESTAMP_FIELDS:
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return _now_iso(now)


def _yields_finding(entry: dict[str, Any]) -> bool:
    """Return True when the entry should become a trusted finding.

    Mirrors ``build_evidence_cards``' skip rules exactly (its docstring documents them): a
    row is skipped when ``narration_failure`` is truthy or ``correctness`` is unmeasured
    (``None``/NaN) or negative. Keeping the gate here — rather than only inside
    ``build_evidence_cards`` — lets :func:`derive_records` filter cheaply without relying on
    an exception path.
    """
    if entry.get("narration_failure"):
        return False
    correctness = entry.get("correctness")
    if correctness is None:
        return False
    try:
        c = float(correctness)
    except (TypeError, ValueError):
        return False
    return math.isfinite(c) and c >= 0.0


# ── Record / event construction ─────────────────────────────────


def build_record(
    entry: dict[str, Any],
    *,
    repository_id: str = REPOSITORY_ID,
    source_uri: str = SOURCE_URI,
    now: datetime | None = None,
) -> KnowledgeRecord:
    """Derive ONE measured-finding :class:`KnowledgeRecord` from a results entry.

    ``source_uri`` defaults to the aggregate :data:`SOURCE_URI` (the summary corpus); a
    producer deriving findings from a *different* source artifact (e.g. the single-task
    ``task_manager_*.json`` run files) passes its own ``file://`` locator so the record's
    provenance and ``entity_id`` namespace reflect the real source, not the summary.

    The record's ``text`` is the evidence-card one-liner produced by
    ``build_evidence_cards([entry])`` — a pure function of the measured vector
    (model/operator/correctness/cost/flail) plus the ledger signals ``confidence`` [H] and
    ``perturbation_strength`` [M] when measured (rendered as ``"confidence —"`` when absent)
    and ``test_executed_success`` [M] (``"tests FAIL (unverified)"`` when ``False``). The
    identity fields are derived from the canonical contract in :mod:`instrument.knowledge`:

    * ``entity_id`` — ``sha256(repository_id | source_uri | logical_locator)``; stable across
      extractor generations and call sites. ``repository_id`` defaults to
      :data:`REPOSITORY_ID` but is overridable (the producer's ``--repository-id`` flag).
    * ``content_hash`` — ``sha256(record_to_artifact(record))``, the sha256 of the durable
      per-record JSON artifact (not the finding text alone). This is what the consumer's
      ``verify_content_hash`` compares against the bytes it reads back from ``source_uri``.
    * ``knowledge_id`` — ``sha256(entity_id | source_revision | content_hash | extractor_version)``;
      a new extractor version, revision, or artifact content yields a new id while
      ``entity_id`` holds.

    ``authority`` is ``MEASURED`` (a raw attempt measurement supports an outcome claim) and
    ``evidence_class`` is ``"[M]"``. The three ledger signals are carried **structurally** on the
    record — ``confidence`` [H] and ``perturbation_strength`` [M] as ``float | None`` (measured or
    ``None``, never a fabricated ``0.0``) and ``test_executed_success`` [M] as ``bool | None`` —
    *and* through the rendered ``text`` (which stays the human-readable rendering with its
    ``"confidence —"`` placeholder when absent). ``outcome_id`` also maps to an explicit field.

    Raises ``ValueError`` when the entry would be skipped by ``build_evidence_cards`` (a
    flailed or unmeasured run must not become a trusted finding) — callers that need the
    batch behavior use :func:`derive_records`, which pre-filters with the same gate.
    """
    # Reuse build_evidence_cards' rendering (its text is the one-line finding). Deriving
    # from a single-entry list also re-applies the documented skip rules; an empty result
    # means this entry is not a valid finding.
    cards = build_evidence_cards([entry])
    if not cards:
        raise ValueError(
            "entry does not yield a measured finding "
            "(narration_failure or unmeasured/negative correctness)"
        )
    card = cards[0]

    run_id = _run_id(entry)
    source_revision = _source_revision(entry)

    # Delegate identity + the content-hash back-fill to the shared factory. This module keeps
    # only its *derivation* (the evidence-card text + the structured ledger signals), while the
    # ordering-sensitive mechanics (blank ids/timestamps → serialize → hash → back-fill) live in
    # record_factory.build_record exactly once.
    return build_record_from_parts(
        source_type=SOURCE_TYPE,
        source_uri=source_uri,
        logical_locator=run_id,
        repository_id=repository_id,
        revision=source_revision,
        authority=Authority.MEASURED,
        evidence_class="[M]",
        text=card.text,
        extra_fields={
            "worktree_id": run_id,  # the summary has no branch dimension; scoping via repo + locator
            "extractor_version": EXTRACTOR_VERSION,
            # observed_at prefers the entry's own run timestamp; valid_from/indexed_at stay the
            # producer now (they describe *this* pass, not the run).
            "observed_at": _observed_at(entry, now=now),
            "outcome_id": str(entry.get("outcome_id") or ""),
            "test_executed_success": card.test_executed_success,
            # Structured ledger signals — measured-or-None, in lockstep with the rendered text
            # (build_evidence_cards already derived them via _finite_float, so absent stays None).
            "confidence": card.confidence,
            "perturbation_strength": card.perturbation_strength,
        },
        now=now,
    )


def record_to_event(
    record: KnowledgeRecord,
    *,
    operation: str = "upsert",
    reason: str = "",
    now: datetime | None = None,
) -> KnowledgeEvent:
    """Build the POINTER-only event for a record.

    ``operation`` is one of ``upsert`` | ``supersede`` | ``delete`` (the ``OPERATIONS``
    frozenset). ``reason`` is required non-empty for ``delete`` (a tombstone must say why) and
    for a ``supersede`` that resolves a content conflict; it is also reused as a caveat
    annotation on a recovered-from-git ``upsert``. Both are additive keyword-only defaults so
    every existing caller (which passes neither) still emits a plain ``upsert``.

    Deliberately carries **no** ``text``/``body`` — mirroring ``KnowledgeEvent``'s docstring,
    a consumer must read the source artifact, verify ``content_hash``, and re-run the
    versioned extractor. The pointer's ``source_uri`` is the **per-record durable artifact**
    (``file://experiments/results/kb/<knowledge_id>.json``), not the aggregate summary, so the
    consumer reads the *exact* bytes that ``content_hash`` covers. ``content_hash`` is
    ``sha256(record_to_artifact(record))``. The ``source_revision`` is recovered from
    ``record.commit_sha`` (which stores the revision folded into ``knowledge_id``), so a replay
    reproduces the exact id. ``occurred_at`` is the producer timestamp used to measure
    end-to-end lag. ``observed_at`` carries the record's OWN observation timestamp (the cell's
    run time when stamped, else the producer now) so a consumer can round-trip the real
    measurement time rather than mistaking the producer clock for it. ``event_id`` is set to
    ``record.knowledge_id`` as a deterministic tracing id — it is **not** the idempotence key
    (``knowledge_id`` is; ``event_id`` is only a correlation handle, so a re-emitted event
    traces back to the same logical record).
    """
    return KnowledgeEvent(
        knowledge_id=record.knowledge_id,
        entity_id=record.entity_id,
        operation=operation,
        source_uri=artifact_uri(record.knowledge_id),
        source_revision=record.commit_sha,
        content_hash=_sha256_bytes(record_to_artifact(record)),
        occurred_at=_now_iso(now),
        schema_version=SCHEMA_VERSION,
        event_id=record.knowledge_id,
        causes=record.causes or "",
        reason=reason,
        observed_at=record.observed_at,
    )


def extract_record(event: KnowledgeEvent, artifact_bytes: bytes) -> KnowledgeRecord:
    """Reconstruct the FULL measured-finding record from a verified pointer + artifact.

    This is the domain-specific extractor for the measured-result path — it supersedes
    ``knowledge_stream.default_extract`` for producer-emitted events and is wired in as the
    ``extractor`` arg of ``process_entry`` (see ``scripts/kb_worker.py``). The artifact is the
    JSON from :func:`record_to_artifact`, which blanked the two derived identities
    (``knowledge_id`` and ``content_hash``) and the three volatile timestamps (``valid_from``,
    ``observed_at``, ``indexed_at``). The ids are reattached from the pointer event; the
    timestamps are reconstructed from the event — ``valid_from`` from ``occurred_at`` (the
    producer derivation clock), ``observed_at`` from the event's ``observed_at`` (the cell's
    real measurement time the producer carried) falling back to ``occurred_at`` only for
    pre-fidelity events that predate that field, and ``indexed_at`` from the consumer clock —
    mirroring ``default_extract``'s convention. Every stable field — including
    ``authority=MEASURED`` and the structured ledger signals
    ``confidence``/``perturbation_strength``/``test_executed_success`` — is restored via
    ``KnowledgeRecord.from_dict`` (those three are measured-or-``None``, never a fabricated 0.0).
    """
    data = json.loads(artifact_bytes.decode("utf-8"))
    record = KnowledgeRecord.from_dict(data)
    return replace(
        record,
        knowledge_id=event.knowledge_id,
        content_hash=event.content_hash,
        valid_from=event.occurred_at,
        observed_at=event.observed_at or event.occurred_at,
        indexed_at=_now_iso(),
    )


def derive_records(
    entries: list[dict[str, Any]],
    *,
    repository_id: str = REPOSITORY_ID,
    source_uri: str = SOURCE_URI,
) -> list[KnowledgeRecord]:
    """Derive one measured-finding record per valid entry, in input order.

    For each entry, ``build_record`` reuses ``build_evidence_cards``' rendering (and its
    skip rules); this function pre-filters with :func:`_yields_finding` so ``narration_failure``
    and unmeasured/negative-``correctness`` rows are skipped without an exception path. The
    result is a list with one record per surviving row, preserving input order. ``repository_id``
    (default :data:`REPOSITORY_ID`) and ``source_uri`` (default :data:`SOURCE_URI`) are threaded
    to each ``build_record`` so a producer can scope the whole batch to a different repository
    and/or source artifact.
    """
    records: list[KnowledgeRecord] = []
    for entry in entries:
        if not _yields_finding(entry):
            continue
        records.append(build_record(entry, repository_id=repository_id, source_uri=source_uri))
    return records


# ── Self-build (progressive) phase findings ─────────────────────


def _artifact_path(knowledge_id: str) -> Path:
    """Absolute filesystem path of a record's durable per-record artifact.

    ``artifact_uri`` / ``record_to_event`` point at the repo-root-relative
    ``file://experiments/results/kb/<knowledge_id>.json``; writing needs the absolute path
    regardless of the process cwd, so it is anchored to :data:`PROJECT_ROOT`.
    """
    return PROJECT_ROOT / ARTIFACT_DIR / f"{knowledge_id}.json"


def _phase_tokens(phase_result: Any) -> int:
    """Return the phase's total token count (input+output fallback when ``total`` is absent).

    ``PhaseResult.tokens`` carries ``in/out/reasoning/answer/explanation/total``; the finding
    reports ``total`` (or the in+out best-effort sum) so the token component of the idempotence
    text stays deterministic.
    """
    tokens = getattr(phase_result, "tokens", None) or {}
    total = tokens.get("total", 0)
    if total:
        return int(total)
    return int(tokens.get("in", 0)) + int(tokens.get("out", 0))


@contextlib.contextmanager
def _authorized_kb_write():
    """Authorize a knowledge-stream write for the duration of the context (env flag only).

    ``knowledge_stream.publish_event`` raises unless ``FINOPS_KB_WRITE=1``; the self-build
    emit path sets the flag for *just* the emit (then restores it) so the authorization does
    not leak to any other writer in the process.
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


def derive_phase_record(
    phase_result: Any,
    *,
    goal: str,
    repository_id: str,
    revision: str,
    now: datetime | None = None,
) -> KnowledgeRecord:
    """Derive ONE phase-finding record for a completed workflow phase.

    The self-build ("progressive") producer path: after a phase commits, its outcome becomes a
    scoped finding in the cell's OWN knowledge scope — never the global summary corpus. The
    finding text is the one-liner::

        "<goal[:40]> phase <phase> -> test_executed_success <bool>, cost $<c>, tokens <n>"

    Authority is ``MEASURED`` when ``test_executed_success`` is a real ``bool`` (the independent
    test runner measured it) and ``ADVISORY`` when it is ``None`` (self-report, unverified) — an
    unverified phase must never read as a measured finding.

    ``logical_locator`` is the cell scope (the ``repository_id`` value here — the workflow seam
    passes the cell scope as the repository id, so every scoping field is the cell scope, never
    global). ``commit_sha`` is ``revision`` (the phase's commit), which is also the
    ``source_revision`` folded into ``knowledge_id``. Idempotence follows from the canonical
    identity: ``knowledge_id`` folds goal (text) + phase (text) + commit (revision) + scope
    (repository_id / logical_locator / acl_scope) + extractor version, so re-emitting the same
    phase yields the same id.
    """
    success = getattr(phase_result, "test_executed_success", None)
    # A bool is an independent measurement (test runner); None is self-report → ADVISORY.
    authority = Authority.MEASURED if isinstance(success, bool) else Authority.ADVISORY

    phase = str(getattr(phase_result, "phase", ""))
    cost = float(getattr(phase_result, "cost_usd", 0.0) or 0.0)
    tokens = _phase_tokens(phase_result)
    text = (
        f"{goal[:40]} phase {phase} -> "
        f"test_executed_success {success}, cost ${cost:.4f}, tokens {tokens}"
    )

    # Delegate identity + the content-hash back-fill to the shared factory. Every scoping field
    # is the cell scope (== repository_id on the self-build path), never global.
    return build_record_from_parts(
        source_type=SOURCE_TYPE,  # "finding"
        source_uri=PHASE_SOURCE_URI,
        logical_locator=repository_id,
        repository_id=repository_id,
        revision=revision,
        authority=authority,
        evidence_class="[M]" if authority is Authority.MEASURED else "[H]",
        text=text,
        extra_fields={
            "worktree_id": repository_id,
            "extractor_version": PHASE_EXTRACTOR_VERSION,
            "acl_scope": repository_id,  # scoped to the cell, never global
            "outcome_id": phase,  # the phase name is the outcome unit
            "test_executed_success": success,
        },
        now=now,
    )


def emit_phase_finding(
    phase_result: Any,
    *,
    goal: str,
    repository_id: str,
    revision: str,
    now: datetime | None = None,
) -> KnowledgeRecord:
    """Derive, durably write, and publish a phase finding into the cell's OWN scope.

    The progressive producer: the record is scoped to ``repository_id`` (the cell scope — never
    global), its durable artifact is written to ``experiments/results/kb/<id>.json``, and a
    pointer-only event is published to the change stream. The write guard in
    ``knowledge_stream.publish_event`` is satisfied for the duration of the emit only (the
    ``FINOPS_KB_WRITE`` flag is set and restored here), so the phase emit is an authorized
    writer while the rest of the process stays read-only.

    Returns the derived record; its ``knowledge_id`` is the idempotence key, so re-emitting the
    same phase derives the same id and the consumer's keyed upsert is a no-op.
    """
    from . import knowledge_stream as _ks

    record = derive_phase_record(
        phase_result, goal=goal, repository_id=repository_id, revision=revision, now=now
    )
    # Durable artifact first — the consumer must be able to read + verify the bytes the
    # event's content_hash covers the moment the pointer lands (mirrors kb_produce ordering).
    artifact = record_to_artifact(record)
    path = _artifact_path(record.knowledge_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(artifact)

    with _authorized_kb_write():
        r = _ks.connect()
        _ks.publish_event(r, record_to_event(record, now=now), source_type=record.source_type)
    return record
