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

import math
from datetime import datetime, timezone
from typing import Any

from .knowledge import (
    SCHEMA_VERSION,
    Authority,
    KnowledgeEvent,
    KnowledgeRecord,
    compute_content_hash,
    compute_entity_id,
    compute_knowledge_id,
)
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

#: Canonical repository identity, derived from the git remote
#: (``git@github.com:peparhugo/agentic-dynamics.git``). It is a stable component of
#: ``entity_id`` so the same logical cell converges on one identity across call sites.
REPOSITORY_ID = "github.com/peparhugo/agentic-dynamics"

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


# ── Entry-field derivation (pure, testable) ─────────────────────

def _now_iso(now: datetime | None = None) -> str:
    """Return ``now`` (or the current UTC instant) as an ISO-8601 timestamp.

    Injectable so tests can pin the produced timestamps; production always uses the real
    clock, mirroring ``retrieval.retrieve``'s ``now`` convention.
    """
    return (now or datetime.now(timezone.utc)).isoformat()


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

def build_record(entry: dict[str, Any], *, now: datetime | None = None) -> KnowledgeRecord:
    """Derive ONE measured-finding :class:`KnowledgeRecord` from a results entry.

    The record's ``text`` is the evidence-card one-liner produced by
    ``build_evidence_cards([entry])`` — a pure function of the measured vector
    (model/operator/correctness/cost/flail) plus the ledger signals ``confidence`` [H] and
    ``perturbation_strength`` [M] when measured (rendered as ``"confidence —"`` when absent)
    and ``test_executed_success`` [M] (``"tests FAIL (unverified)"`` when ``False``). The
    identity fields are derived from the canonical contract in :mod:`instrument.knowledge`:

    * ``entity_id`` — ``sha256(repository_id | source_uri | logical_locator)``; stable across
      extractor generations and call sites.
    * ``content_hash`` — ``sha256(text)``, recomputable from the record's own ``text``.
    * ``knowledge_id`` — ``sha256(entity_id | source_revision | content_hash | extractor_version)``;
      a new extractor version, revision, or text yields a new id while ``entity_id`` holds.

    ``authority`` is ``MEASURED`` (a raw attempt measurement supports an outcome claim) and
    ``evidence_class`` is ``"[M]"``. ``confidence`` and ``perturbation_strength`` are carried
    through the rendered ``text`` (the :class:`KnowledgeRecord` schema has no fields for them);
    ``test_executed_success`` and ``outcome_id`` map to the record's explicit fields.

    Raises ``ValueError`` when the entry would be skipped by ``build_evidence_cards`` (a
    flailed or unmeasured run must not become a trusted finding) — callers that need the
    batch behavior use :func:`derive_records`, which pre-filters with the same gate.
    """
    ts = _now_iso(now)

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

    # Identity: the record's text is the authoritative payload, so the content hash is
    # computed from it — a consumer can re-derive text from the entry and compare hashes.
    entity_id = compute_entity_id(REPOSITORY_ID, SOURCE_URI, run_id)
    content_hash = compute_content_hash(card.text)
    knowledge_id = compute_knowledge_id(
        entity_id, source_revision, content_hash, EXTRACTOR_VERSION
    )

    return KnowledgeRecord(
        knowledge_id=knowledge_id,
        entity_id=entity_id,
        source_uri=SOURCE_URI,
        source_type=SOURCE_TYPE,
        logical_locator=run_id,
        repository_id=REPOSITORY_ID,
        branch="",  # the summary has no branch dimension; scoping is via repository_id + locator
        worktree_id=run_id,
        # commit_sha *is* the source_revision for repository-backed units (knowledge.py's
        # docstring); here that is the commit id when stamped, else RESULT_VERSION.
        commit_sha=source_revision,
        content_hash=content_hash,
        extractor_version=EXTRACTOR_VERSION,
        embedding_version="",  # no embedding is computed at extraction time
        authority=Authority.MEASURED,
        valid_from=ts,
        valid_to=None,
        observed_at=ts,
        indexed_at=ts,
        acl_scope=ACL_SCOPE,
        contains_sensitive_data=False,
        text=card.text,
        token_count=max(1, len(card.text.split())),  # whitespace-token estimate, [H]
        language="",  # a finding is prose, not a source-language unit
        symbols=[],  # no symbol table on a one-line finding
        outcome_id=str(entry.get("outcome_id") or ""),
        test_executed_success=card.test_executed_success,
        evidence_class="[M]",
    )


def record_to_event(
    record: KnowledgeRecord, *, now: datetime | None = None
) -> KnowledgeEvent:
    """Build the POINTER-only event for a record (``operation="upsert"``).

    Deliberately carries **no** ``text``/``body`` — mirroring ``KnowledgeEvent``'s docstring,
    a consumer must read the source artifact, verify ``content_hash``, and re-run the
    versioned extractor. The ``source_revision`` is recovered from ``record.commit_sha``
    (which stores the revision folded into ``knowledge_id``), so a replay reproduces the
    exact id. ``occurred_at`` is the producer timestamp used to measure end-to-end lag.
    """
    return KnowledgeEvent(
        knowledge_id=record.knowledge_id,
        entity_id=record.entity_id,
        operation="upsert",
        source_uri=record.source_uri,
        source_revision=record.commit_sha,
        content_hash=record.content_hash,
        occurred_at=_now_iso(now),
        schema_version=SCHEMA_VERSION,
        event_id="",
    )


def derive_records(entries: list[dict[str, Any]]) -> list[KnowledgeRecord]:
    """Derive one measured-finding record per valid entry, in input order.

    For each entry, ``build_record`` reuses ``build_evidence_cards``' rendering (and its
    skip rules); this function pre-filters with :func:`_yields_finding` so ``narration_failure``
    and unmeasured/negative-``correctness`` rows are skipped without an exception path. The
    result is a list with one record per surviving row, preserving input order.
    """
    records: list[KnowledgeRecord] = []
    for entry in entries:
        if not _yields_finding(entry):
            continue
        records.append(build_record(entry))
    return records
