"""Producer-side ledger derivation for the runtime-RAG knowledge base.

Canonical-state round 2 registry's ``ledger_job`` / ``ledger_attempt`` / ``meta_session``
producer — plan step 4 of ``docs/canonical_state_r2_plan.md``. Closes two base-inventory
gaps (``docs/canonical_state_base_verify.md``):

* **Gap (a), Finding 4 — no-session fallback.** A ``claude_cli``-backend story has no
  matching row in the opencode sqlite DB (that table is opencode-specific), so the
  DB-join path round 1 assumed is simply absent for those cells. This module's fallback
  reads tokens/cost/confidence directly from each session's own ``agentic`` block
  (``StoryResult.sessions[i]["agentic"]``, the exact shape ``story.py:261-279`` writes —
  backend-agnostic, per ``story.py``'s own ``SessionResult.to_dict()``), so a claude_cli
  cell is never silently unmeasured just because it has no DB row.
* **Gap (b), Finding 5 — ``meta_*`` pollution.** ``scripts/analyze_worktrees.py``'s
  ``EXPERIMENT_SESSION_PATTERNS`` substring match (``analyze_worktrees.py:1099-1102``)
  false-matches meta-analysis session titles like ``meta_batch_042`` (the substring
  ``"batch"`` is itself a pattern) and would fold them into "experiment worktree" cost
  rollups. :func:`classify_session` runs *before* emission and routes any ``meta_``-titled
  session to ``source_type="meta_session"`` instead of ``"ledger_attempt"`` — it never
  enters the attempt rollup family in the first place, closing the gap at registration
  time rather than requiring every downstream consumer to re-apply a title-substring
  workaround.

Contract reuse: identical to :mod:`instrument.story_ingestion` et al. — the fixed
artifact/event contract from :mod:`instrument.knowledge_ingestion` is reused verbatim.

Two record kinds per cell (one call to :func:`derive_ledger_records` returns both):

* ``ledger_job`` — one per story/cell (design §2: ``authority=MEASURED``,
  ``evidence_class="[M]"``). Source-of-truth for the whole story's aggregate cost/tokens:
  the single opencode DB ``session`` row (keyed by worktree directory, confirmed query
  shape ``scripts/analyze_worktrees.py:226-236``) when available, else the story's own
  ``summary`` block (backend-agnostic, gap-a fallback).
* ``ledger_attempt`` (or ``meta_session`` — see :func:`classify_session`) — one per
  session within the story. Tokens/cost/confidence are **always** read from that session's
  own ``agentic`` block: this is the one genuinely backend-agnostic per-session source
  ``story_result`` carries (the DB row has no per-session breakdown at all — it is a
  single aggregate row per worktree), so both the primary and fallback paths read the
  same field; only ``extractor_version`` differs (``EXTRACTOR_VERSION`` when a DB row
  exists for this story at all, else :data:`FALLBACK_EXTRACTOR_VERSION`), matching the
  design's own table (§7a) where the *provenance label* — not the *field source* — is
  what the DB-join-vs-fallback branch changes at attempt granularity.
"""

from __future__ import annotations

import hashlib
import importlib.util
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from .knowledge import (
    Authority,
    KnowledgeRecord,
    compute_entity_id,
    compute_knowledge_id,
)
from .knowledge_ingestion import PROJECT_ROOT, REPOSITORY_ID, record_to_artifact

# ── Extractor contract constants ────────────────────────────────

EXTRACTOR_VERSION = "ledger/v1"
#: Gap (a): set on every record derived from this call when no opencode DB row exists for
#: the story (claude_cli-backend cells) — distinguishes join-sourced from self-reported
#: attempts downstream without a new field, per design §7a's table.
FALLBACK_EXTRACTOR_VERSION = "ledger/v1-storyfallback"

SOURCE_TYPE_JOB = "ledger_job"
SOURCE_TYPE_ATTEMPT = "ledger_attempt"
SOURCE_TYPE_META = "meta_session"
ACL_SCOPE = "public"
REVISION_FALLBACK = "ledger/unrevisioned"


# ── EXPERIMENT_SESSION_PATTERNS — loaded from scripts/_constants.py, not re-declared ──


def _load_experiment_session_patterns() -> list[str]:
    """Load ``EXPERIMENT_SESSION_PATTERNS`` from ``scripts/_constants.py`` by file path.

    ``classify_session`` must use the IDENTICAL list ``analyze_worktrees.py:32`` imports —
    a re-declared copy would drift from the exact thing gap (b) is meant to match (plan
    step 4's explicit warning). ``scripts/`` is not an importable package (no
    ``__init__.py``), and the dependency direction throughout this repo runs
    ``scripts -> src/instrument``, never the reverse (``scripts/analyze_worktrees.py``
    imports ``instrument``, not vice versa) — adding ``scripts/`` to ``sys.path`` from a
    core library module would invert that graph for every future import in the process.
    Loading the file by its exact path avoids both problems: it reads the same source list
    without becoming a normal Python package dependency in either direction.
    """
    path = PROJECT_ROOT / "scripts" / "_constants.py"
    spec = importlib.util.spec_from_file_location("_finops_scripts_constants", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return list(module.EXPERIMENT_SESSION_PATTERNS)


#: The identical list analyze_worktrees.py:32 imports — loaded once at import time (not
#: re-derived per call), so classify_session() never drifts from the pattern list it must
#: match against.
EXPERIMENT_SESSION_PATTERNS = _load_experiment_session_patterns()


def classify_session(session_title: str) -> str:
    """Return the ``source_type`` a session's ledger record should be emitted as.

    Runs BEFORE emission (not after) so a ``meta_*`` title is routed to
    ``"meta_session"`` at registration time — it never enters ``"ledger_attempt"`` in the
    first place. This is what prevents this design from merely *relocating*
    ``analyze_worktrees.py``'s title-substring pollution into the registry's own cost
    rollups instead of eliminating it (design §7b).

    The ``meta_`` prefix check runs first and short-circuits — a title starting with
    ``meta_`` (e.g. ``"meta_batch_042"``) is never given the chance to also match an
    ``EXPERIMENT_SESSION_PATTERNS`` substring (``"batch"`` is itself one of those
    patterns, which is exactly how gap (b) happened upstream). An unclassified title
    (matches neither check) still registers as ``"ledger_attempt"`` — round 1's OQ1,
    unchanged: an ambiguous title is not silently dropped.
    """
    if session_title.startswith("meta_"):
        return SOURCE_TYPE_META
    if any(p in session_title.lower() for p in EXPERIMENT_SESSION_PATTERNS):
        return SOURCE_TYPE_ATTEMPT
    return SOURCE_TYPE_ATTEMPT


# ── Small deterministic helpers (mirror the other *_ingestion modules) ──────


def _now_iso(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).isoformat()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _job_id(story_result: dict[str, Any]) -> str:
    return str(story_result.get("story_id") or "")


def _attempt_id(job_id: str, session_number: Any) -> str:
    return f"{job_id}_{session_number}"


def _source_revision(summary_entry: dict[str, Any] | None) -> str:
    """Return the summary entry's commit id, else :data:`REVISION_FALLBACK`.

    Mirrors ``knowledge_ingestion._git_sha``'s "first non-empty of three possible key
    names, never a fabricated sha" convention — this is the "join with summary_entry"
    piece of the design's job/attempt identity (design §7a's table names all three
    inputs: ``story_result`` + ``opencode_session_row`` + ``summary_entry``).
    """
    for key in ("git_sha", "commit", "commit_sha"):
        value = (summary_entry or {}).get(key)
        if value:
            return str(value)
    return REVISION_FALLBACK


# ── Record construction: ledger_job (one per cell) ───────────────


def build_job_record(
    story_result: dict[str, Any],
    opencode_session_row: dict[str, Any] | None,
    summary_entry: dict[str, Any] | None,
    *,
    repository_id: str = REPOSITORY_ID,
    now: datetime | None = None,
) -> KnowledgeRecord:
    """Derive ONE ``source_type=ledger_job`` record for a whole story/cell.

    Primary path (``opencode_session_row is not None``): the DB row is authoritative for
    the job-level aggregate (round 1, unchanged) — it is the single sqlite ``session`` row
    keyed by worktree directory, carrying the whole story's total cost/tokens/model.

    Fallback (gap a, ``opencode_session_row is None``): no DB row exists for a
    claude_cli-backend story. Every field the DB join would have supplied is already on
    the story's own ``summary`` block (backend-agnostic — ``story.py``'s
    ``StoryResult.to_dict()``'s ``summary`` sub-dict), so the job is still fully
    registrable, just labeled with :data:`FALLBACK_EXTRACTOR_VERSION` instead of
    :data:`EXTRACTOR_VERSION`.

    Raises ``ValueError`` when ``story_result`` has no ``story_id``.
    """
    job_id = _job_id(story_result)
    if not job_id:
        raise ValueError("story_result has no story_id — cannot derive a stable job identity")

    ts = _now_iso(now)
    source_uri = f"ledger_job:{job_id}"
    entity_id = compute_entity_id(repository_id, source_uri, job_id)
    extractor_version = EXTRACTOR_VERSION if opencode_session_row is not None else FALLBACK_EXTRACTOR_VERSION
    revision = _source_revision(summary_entry)

    if opencode_session_row is not None:
        cost = opencode_session_row.get("cost")
        total_tokens = (opencode_session_row.get("tokens_input") or 0) + (
            opencode_session_row.get("tokens_output") or 0
        )
        provider = str(opencode_session_row.get("provider") or "")
        model_id = str(opencode_session_row.get("model_id") or "")
        model = f"{provider}/{model_id}".strip("/")
    else:
        summary = story_result.get("summary") or {}
        cost = summary.get("total_cost")
        total_tokens = summary.get("total_tokens")
        model = str(story_result.get("model") or "")

    text = f"job {job_id} [{model}]: cost={cost!r} total_tokens={total_tokens!r}"

    record = KnowledgeRecord(
        knowledge_id="",
        entity_id=entity_id,
        source_uri=source_uri,
        source_type=SOURCE_TYPE_JOB,
        logical_locator=job_id,
        repository_id=repository_id,
        branch="",
        worktree_id=str(story_result.get("worktree") or ""),
        commit_sha=revision,
        content_hash="",
        extractor_version=extractor_version,
        embedding_version="",
        authority=Authority.MEASURED,
        valid_from=ts,
        valid_to=None,
        observed_at=str(story_result.get("completed_at") or story_result.get("started_at") or ts),
        indexed_at=ts,
        acl_scope=ACL_SCOPE,
        contains_sensitive_data=False,
        text=text,
        token_count=max(1, len(text.split())),
        language=str(story_result.get("language") or ""),
        symbols=[],
        outcome_id="",
        test_executed_success=story_result.get("test_executed_success"),
        evidence_class="[M]",
        confidence=None,  # job-level confidence is not a thing; see attempt records
        perturbation_strength=story_result.get("perturbation_strength"),
        causes=None,
    )
    content_hash = _sha256_bytes(record_to_artifact(record))
    knowledge_id = compute_knowledge_id(entity_id, revision, content_hash, extractor_version)
    return replace(record, content_hash=content_hash, knowledge_id=knowledge_id)


# ── Record construction: ledger_attempt / meta_session (one per session) ────


def build_attempt_record(
    story_result: dict[str, Any],
    session: dict[str, Any],
    opencode_session_row: dict[str, Any] | None,
    summary_entry: dict[str, Any] | None,
    *,
    repository_id: str = REPOSITORY_ID,
    now: datetime | None = None,
) -> KnowledgeRecord:
    """Derive ONE ``ledger_attempt`` (or ``meta_session`` — see :func:`classify_session`)
    record for one session within a story.

    Tokens/cost/confidence are always read from ``session["agentic"]`` — the one
    genuinely per-session, backend-agnostic source ``story_result`` carries (gap a: this
    is the exact fallback the design calls for when ``opencode_session_row is None``, and
    it is also the *only* per-session source available even when a DB row exists, since
    that row is a single aggregate per worktree with no per-session breakdown). Only
    ``extractor_version`` differs between the two branches — see this module's docstring.
    """
    job_id = _job_id(story_result)
    session_number = session.get("session_number")
    attempt_id = _attempt_id(job_id, session_number)

    # gap (b): classify BEFORE emission. Best-available title — the opencode DB row's own
    # title when this story has one, else the story name (StoryConfig/StoryResult carries
    # no per-session title of its own; the DB row is the only place a raw session title,
    # the thing gap (b)'s pollution is about, actually lives).
    title = str((opencode_session_row or {}).get("title") or story_result.get("story_name") or "")
    source_type = classify_session(title)

    ts = _now_iso(now)
    agentic = session.get("agentic") or {}
    extractor_version = EXTRACTOR_VERSION if opencode_session_row is not None else FALLBACK_EXTRACTOR_VERSION
    revision = _source_revision(summary_entry)

    source_uri = f"{source_type}:{attempt_id}"
    entity_id = compute_entity_id(repository_id, source_uri, attempt_id)

    confidence = agentic.get("confidence")
    total_tokens = agentic.get("total_tokens", session.get("total_tokens"))
    cost = agentic.get("estimated_cost_usd", session.get("cost_usd"))
    text = f"attempt {attempt_id} [{source_type}]: tokens={total_tokens!r} cost={cost!r} confidence={confidence!r}"

    is_meta = source_type == SOURCE_TYPE_META
    authority = Authority.ADVISORY if is_meta else Authority.MEASURED
    evidence_class = "[H]" if is_meta else "[M]"

    record = KnowledgeRecord(
        knowledge_id="",
        entity_id=entity_id,
        source_uri=source_uri,
        source_type=source_type,
        logical_locator=attempt_id,
        repository_id=repository_id,
        branch="",
        worktree_id=str(story_result.get("worktree") or ""),
        commit_sha=str(session.get("commit_hash") or ""),
        content_hash="",
        extractor_version=extractor_version,
        embedding_version="",
        authority=authority,
        valid_from=ts,
        valid_to=None,
        observed_at=ts,
        indexed_at=ts,
        acl_scope=ACL_SCOPE,
        contains_sensitive_data=False,
        text=text,
        token_count=max(1, len(text.split())),
        language=str(story_result.get("language") or ""),
        symbols=[],
        outcome_id="",
        test_executed_success=story_result.get("test_executed_success"),
        evidence_class=evidence_class,
        confidence=confidence,
        perturbation_strength=story_result.get("perturbation_strength"),
        causes=None,
    )
    content_hash = _sha256_bytes(record_to_artifact(record))
    knowledge_id = compute_knowledge_id(entity_id, revision, content_hash, extractor_version)
    return replace(record, content_hash=content_hash, knowledge_id=knowledge_id)


# ── The public derivation entry point ───────────────────────────


def derive_ledger_records(
    story_result: dict[str, Any],
    opencode_session_row: dict[str, Any] | None,
    summary_entry: dict[str, Any] | None,
    *,
    repository_id: str = REPOSITORY_ID,
    now: datetime | None = None,
) -> list[KnowledgeRecord]:
    """Derive one ``ledger_job`` + one-or-more ``ledger_attempt``/``meta_session`` records.

    ``opencode_session_row`` is ``None`` on claude_cli-backend runs (gap a's real branch —
    no matching sqlite row exists for that backend at all) or when no DB lookup was
    performed by the caller. ``summary_entry`` is the corresponding
    ``_results_summary.json`` row when one exists (may also be ``None``/``{}``); it
    contributes only the job/attempt ``source_revision`` when the story's own sessions
    never committed. Returns ``[]`` when ``story_result`` has no ``story_id`` — mirrors
    every other producer's pre-filter convention (batch callers skip cheaply rather than
    catching an exception per entry).
    """
    if not story_result.get("story_id"):
        return []
    records = [
        build_job_record(
            story_result, opencode_session_row, summary_entry,
            repository_id=repository_id, now=now,
        )
    ]
    for session in story_result.get("sessions") or []:
        records.append(
            build_attempt_record(
                story_result, session, opencode_session_row, summary_entry,
                repository_id=repository_id, now=now,
            )
        )
    return records
