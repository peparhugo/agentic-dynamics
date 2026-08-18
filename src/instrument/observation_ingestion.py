"""Producer-side observation derivation for the runtime-RAG knowledge base.

Canonical-state round 2 registry's ``observation``/``flag`` producer — plan step 5 of
``docs/canonical_state_r2_plan.md``. Closes round 1's OQ6a audit gap: today
``scripts/supervise.py:supervise_once`` only durably records a session's activity when its
verdict is *not* ``"healthy"``/``"unknown"`` (it calls ``emit_flag`` only in that branch —
confirmed ``supervise.py:342-344``). That means a ``healthy`` verdict leaves no durable
trace at all. This module makes **every** verdict (healthy or not) a registrable
``observation`` record; ``flag`` stays the narrower, session-scoped "newest wins"
derivative that ``emit_flag`` already writes to ``flags.jsonl`` today.

Two record kinds, two producer functions:

* :func:`derive_observation_record` — one record per supervisor assessment pass, for
  **every** verdict. Input shape: ``{"cell_id": str, "status": str, "why": str, "model":
  str, "at": str (optional)}`` — the exact dict the design's future call site
  (``docs/canonical_state_r2_design.md`` §8's table, plan step 13, out of scope here)
  passes to this function.
* :func:`derive_flag_record` — one record per ``flags.jsonl`` line, i.e. per call to
  ``scripts/supervise.py:emit_flag`` (confirmed shape at ``supervise.py:221-230``:
  ``{"at", "session_id", "title", "model", "status", "why", "review"?}``).

Both are ``authority=ADVISORY`` / ``evidence_class="[H]"`` (design §2's table: a
supervisor verdict is a heuristic judgment, not an independently measured fact — it can
inform triage but never override a ``MEASURED`` ledger record).

Contract reuse: identical to :mod:`instrument.story_ingestion` / :mod:`instrument.review_ingestion`
— the fixed artifact/event contract from :mod:`instrument.knowledge_ingestion` is reused
verbatim.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from .knowledge import (
    Authority,
    KnowledgeRecord,
    compute_entity_id,
    compute_knowledge_id,
)
from .knowledge_ingestion import REPOSITORY_ID, record_to_artifact

# ── Extractor contract constants ────────────────────────────────

EXTRACTOR_VERSION = "observation/v1"
SOURCE_TYPE_OBSERVATION = "observation"
SOURCE_TYPE_FLAG = "flag"
ACL_SCOPE = "public"
REVISION_FALLBACK = "observation/unrevisioned"


# ── Small deterministic helpers (mirror story_ingestion / knowledge_ingestion) ──


def _now_iso(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).isoformat()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _assessment_id(cell_id: str, at: str) -> str:
    """Return a stable, short identity for one (cell, timestamp) assessment.

    Design §3: ``logical_locator`` for an ``observation`` record is "assessment_id (hash of
    cell_id+at)" — every verdict against the same cell is an independent fact (unlike a
    same-entity supersession chain), so the timestamp is folded in deliberately: two
    verdicts against the same cell at different times must never collide on identity.
    """
    return hashlib.sha256(f"{cell_id}|{at}".encode("utf-8")).hexdigest()[:16]


# ── Record construction: observation (every verdict) ────────────


def build_observation_record(
    verdict: dict[str, Any],
    *,
    repository_id: str = REPOSITORY_ID,
    now: datetime | None = None,
) -> KnowledgeRecord:
    """Derive ONE ``source_type=observation`` record from a supervisor verdict.

    ``verdict`` is ``{"cell_id", "status", "why", "model", "at"? }`` — ``at`` is the
    verdict's own observation timestamp when the caller has one; when absent, the producer
    ``now`` is used (this describes *when the assessment happened*, which the producer
    genuinely knows in that case — not a fabricated measurement). Raises ``ValueError``
    when ``cell_id`` is missing — a verdict with no subject cannot be registered.
    """
    cell_id = str(verdict.get("cell_id") or "")
    if not cell_id:
        raise ValueError("verdict has no cell_id — cannot derive a stable identity")

    ts = _now_iso(now)
    at = str(verdict.get("at") or ts)
    status = str(verdict.get("status") or "unknown")
    why = str(verdict.get("why") or "")
    model = str(verdict.get("model") or "")

    assessment_id = _assessment_id(cell_id, at)
    source_uri = f"observation:{assessment_id}"
    entity_id = compute_entity_id(repository_id, source_uri, assessment_id)
    text = f"{cell_id} [{model}]: {status}" + (f" — {why}" if why else "")

    record = KnowledgeRecord(
        knowledge_id="",
        entity_id=entity_id,
        source_uri=source_uri,
        source_type=SOURCE_TYPE_OBSERVATION,
        logical_locator=assessment_id,
        repository_id=repository_id,
        branch="",
        worktree_id="",
        commit_sha="",
        content_hash="",
        extractor_version=EXTRACTOR_VERSION,
        embedding_version="",
        authority=Authority.ADVISORY,
        valid_from=ts,
        valid_to=None,
        observed_at=at,
        indexed_at=ts,
        acl_scope=ACL_SCOPE,
        contains_sensitive_data=False,
        text=text,
        token_count=max(1, len(text.split())),
        language="",
        symbols=[],
        outcome_id="",
        test_executed_success=None,
        evidence_class="[H]",
        confidence=None,
        perturbation_strength=None,
        causes=None,
        subject_id=cell_id,
        subject_status=status,
    )
    content_hash = _sha256_bytes(record_to_artifact(record))
    knowledge_id = compute_knowledge_id(entity_id, REVISION_FALLBACK, content_hash, EXTRACTOR_VERSION)
    return replace(record, content_hash=content_hash, knowledge_id=knowledge_id)


def derive_observation_record(
    verdict: dict[str, Any],
    *,
    repository_id: str = REPOSITORY_ID,
    now: datetime | None = None,
) -> KnowledgeRecord:
    """Public entry point matching the plan's stub signature — delegates to :func:`build_observation_record`.

    Deliberately singular (unlike the other producers' ``derive_*_records`` plural form):
    the plan's own step 5 stub declares this returning one ``KnowledgeRecord``, not a list
    — one verdict always yields exactly one observation, with no batch pre-filtering case
    (unlike story/review, a verdict missing its ``cell_id`` is a genuine caller error, not
    a "this entry doesn't qualify" skip case).
    """
    return build_observation_record(verdict, repository_id=repository_id, now=now)


# ── Record construction: flag (session-scoped, "newest wins") ───


def build_flag_record(
    flag_jsonl_line: dict[str, Any],
    *,
    repository_id: str = REPOSITORY_ID,
    now: datetime | None = None,
) -> KnowledgeRecord:
    """Derive ONE ``source_type=flag`` record from one ``flags.jsonl`` line.

    ``flag_jsonl_line`` is the exact dict ``scripts/supervise.py:emit_flag`` appends
    (``{"at", "session_id", "title", "model", "status", "why", "review"?}``). Raises
    ``ValueError`` when ``session_id`` is missing.
    """
    session_id = str(flag_jsonl_line.get("session_id") or "")
    if not session_id:
        raise ValueError("flag has no session_id — cannot derive a stable identity")

    ts = _now_iso(now)
    at = str(flag_jsonl_line.get("at") or ts)
    status = str(flag_jsonl_line.get("status") or "unknown")
    why = str(flag_jsonl_line.get("why") or "")
    model = str(flag_jsonl_line.get("model") or "")
    title = str(flag_jsonl_line.get("title") or "")

    source_uri = f"flag_stream:{session_id}"
    entity_id = compute_entity_id(repository_id, source_uri, session_id)
    text = f"{title or session_id} [{model}]: {status}" + (f" — {why}" if why else "")

    record = KnowledgeRecord(
        knowledge_id="",
        entity_id=entity_id,
        source_uri=source_uri,
        source_type=SOURCE_TYPE_FLAG,
        logical_locator=session_id,
        repository_id=repository_id,
        branch="",
        worktree_id="",
        commit_sha="",
        content_hash="",
        extractor_version=EXTRACTOR_VERSION,
        embedding_version="",
        authority=Authority.ADVISORY,
        valid_from=ts,
        valid_to=None,
        observed_at=at,
        indexed_at=ts,
        acl_scope=ACL_SCOPE,
        contains_sensitive_data=False,
        text=text,
        token_count=max(1, len(text.split())),
        language="",
        symbols=[],
        outcome_id="",
        test_executed_success=None,
        evidence_class="[H]",
        confidence=None,
        perturbation_strength=None,
        causes=None,
        subject_id=session_id,
        subject_status=status,
    )
    content_hash = _sha256_bytes(record_to_artifact(record))
    knowledge_id = compute_knowledge_id(entity_id, REVISION_FALLBACK, content_hash, EXTRACTOR_VERSION)
    return replace(record, content_hash=content_hash, knowledge_id=knowledge_id)


def derive_flag_record(
    flag_jsonl_line: dict[str, Any],
    *,
    repository_id: str = REPOSITORY_ID,
    now: datetime | None = None,
) -> KnowledgeRecord:
    """Public entry point matching the plan's stub signature — delegates to :func:`build_flag_record`."""
    return build_flag_record(flag_jsonl_line, repository_id=repository_id, now=now)
