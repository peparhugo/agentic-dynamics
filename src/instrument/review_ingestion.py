"""Producer-side review derivation for the runtime-RAG knowledge base.

Canonical-state round 2 registry's ``review`` producer — plan step 3 of
``docs/canonical_state_r2_plan.md``. Turns one merged review dict (the exact shape
``scripts/finalize_reviews.py:_finalize_story`` writes to
``experiments/results/reviews/review_{story_id}.json`` — ``{"story_name", "story_id",
"model", "commit_reviews": [...], "story_review": {...} | None}``) into ONE
``source_type=review`` :class:`~instrument.knowledge.KnowledgeRecord`.

Contract reuse: identical to :mod:`instrument.story_ingestion` — the fixed
artifact/event contract from :mod:`instrument.knowledge_ingestion` (``record_to_artifact``
/ ``record_to_event`` / ``extract_record``) is reused verbatim; no second contract is
invented for this producer.

Identity (``docs/canonical_state_r2_design.md`` §3, ``review`` row): ``source_uri =
f"review:{story_id}"`` (a logical marker, not a filesystem path — see
``story_ingestion``'s module docstring for the worktree-independence argument, which
applies identically here), ``logical_locator = story_id``.

``authority = ADVISORY`` / ``evidence_class = "[H]"`` (design §2's table): a review is a
model's *judgment* about a story, not an independently measured fact — it can inform but
never override a ``MEASURED`` story record or current ``SOURCE`` code.

Scope note: builds records only, same "point at the existing file, no copy" deferral to
the steady-state call site (``finalize_reviews.py``, plan step 12) as
``story_ingestion.py`` documents — out of scope for this producer module.
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

EXTRACTOR_VERSION = "review/v1"
SOURCE_TYPE = "review"
ACL_SCOPE = "public"

#: ``source_revision`` fallback — reviews carry no commit dimension of their own (they
#: judge a *story*, which already anchors to its own commits via story_ingestion).
REVISION_FALLBACK = "review/unrevisioned"


# ── Small deterministic helpers (mirror story_ingestion / knowledge_ingestion) ──


def _now_iso(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).isoformat()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _render_text(review: dict[str, Any]) -> str:
    """Render a one-line summary: story, model, commit-review tally, story coherence."""
    story_name = str(review.get("story_name") or "")
    model = str(review.get("model") or "")
    commit_reviews = review.get("commit_reviews") or []
    story_review = review.get("story_review") or {}

    better = sum(1 for c in commit_reviews if c.get("better_or_worse") == "better")
    worse = sum(1 for c in commit_reviews if c.get("better_or_worse") == "worse")
    coherence = story_review.get("overall_coherence")
    coherence_part = (
        f"coherence={coherence:.2f}" if isinstance(coherence, (int, float)) else "coherence unmeasured"
    )
    return (
        f"{story_name} [{model}]: {len(commit_reviews)} commit reviews "
        f"({better} better, {worse} worse), {coherence_part}"
    )


# ── Record construction ─────────────────────────────────────────


def build_review_record(
    review: dict[str, Any],
    *,
    repository_id: str = REPOSITORY_ID,
    now: datetime | None = None,
) -> KnowledgeRecord:
    """Derive ONE ``source_type=review`` :class:`KnowledgeRecord` from a merged review dict.

    Raises ``ValueError`` when the entry has no ``story_id`` — mirrors
    ``story_ingestion.build_story_record``'s contract exactly; batch callers use
    :func:`derive_review_records`, which pre-filters this case.
    """
    story_id = str(review.get("story_id") or "")
    if not story_id:
        raise ValueError("review has no story_id — cannot derive a stable identity")

    ts = _now_iso(now)
    source_uri = f"review:{story_id}"
    entity_id = compute_entity_id(repository_id, source_uri, story_id)
    text = _render_text(review)

    record = KnowledgeRecord(
        knowledge_id="",
        entity_id=entity_id,
        source_uri=source_uri,
        source_type=SOURCE_TYPE,
        logical_locator=story_id,
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
        observed_at=ts,
        indexed_at=ts,
        acl_scope=ACL_SCOPE,
        contains_sensitive_data=False,
        text=text,
        token_count=max(1, len(text.split())),
        language="",
        symbols=[],
        outcome_id="",
        test_executed_success=None,  # a review is a judgment, not an independent test run
        evidence_class="[H]",
        confidence=None,
        perturbation_strength=None,
        causes=None,
    )
    content_hash = _sha256_bytes(record_to_artifact(record))
    knowledge_id = compute_knowledge_id(entity_id, REVISION_FALLBACK, content_hash, EXTRACTOR_VERSION)
    return replace(record, content_hash=content_hash, knowledge_id=knowledge_id)


def derive_review_records(
    review: dict[str, Any],
    *,
    repository_id: str = REPOSITORY_ID,
    now: datetime | None = None,
) -> list[KnowledgeRecord]:
    """Derive the list of review records for one merged review dict (today: zero-or-one).

    List-returning wrapper around :func:`build_review_record`, for signature symmetry with
    the other ``derive_*_records`` producers. Returns ``[]`` when ``review`` has no
    ``story_id`` rather than raising, matching ``story_ingestion.derive_story_records``'s
    pre-filter convention.
    """
    if not review.get("story_id"):
        return []
    return [build_review_record(review, repository_id=repository_id, now=now)]
