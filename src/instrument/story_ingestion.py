"""Producer-side story derivation for the runtime-RAG knowledge base.

This is the canonical-state round 2 registry's ``story`` producer — plan step 2 of
``docs/canonical_state_r2_plan.md``. It turns one :class:`~instrument.story.StoryResult`
(serialized to a plain dict, exactly the shape ``story.save_story_result`` writes via
``result.to_dict()``) into ONE ``source_type=story`` :class:`~instrument.knowledge.KnowledgeRecord`
— a cell-level "this story happened, here is its outcome" fact.

Contract reuse (matches the convention every other producer in this package already
follows — ``code_ingestion.py``, ``quality_ingestion.py``, ``policy_ingestion.py`` — see
each module's docstring): the fixed artifact/event contract from
:mod:`instrument.knowledge_ingestion` is reused verbatim. ``record_to_artifact`` serializes
this record to its durable per-record JSON (``content_hash = sha256(artifact)``);
``record_to_event`` / ``extract_record`` (unchanged) round-trip it on the consumer side. No
second artifact/event contract is invented here.

Identity (``docs/canonical_state_r2_design.md`` §3's table, ``story`` row):

* ``entity_id = sha256(repository_id | source_uri | logical_locator)`` where
  ``source_uri = f"story:{story_id}"`` — a **logical** marker, never a filesystem path, so
  a story replayed from two different worktrees (finding 1's stranding scenario) converges
  on the same ``entity_id`` regardless of which worktree currently holds the file.
  ``logical_locator = story_id``.
* ``knowledge_id`` folds in the story's last commit sha (or a stable fallback when no
  session ever committed) plus :data:`EXTRACTOR_VERSION`, so a re-derivation of the same
  story yields the same id (idempotent) while a genuinely different outcome does not.

Scope note (read before wiring a call site): this module builds *records* only —
:func:`derive_story_records` / :func:`build_story_record` have no I/O and no Redis
dependency, matching plan step 2's "built, unit-tested, zero callers" framing. The
"point at the existing story JSON file, never write a copy" behavior
(``docs/canonical_state_r2_design.md`` §9's store-split table) is a property of the
*event* a future caller constructs from this record's ``source_uri`` inside
:func:`instrument.knowledge_stream.publish_event` — that inline call site
(``story.py:945 save_story_result()``) is plan step 10 (steady-state wiring), explicitly
out of scope here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .knowledge import (
    Authority,
    KnowledgeRecord,
)
from .knowledge_ingestion import REPOSITORY_ID
from .record_factory import build_record as build_record_from_parts

# ── Extractor contract constants ────────────────────────────────

#: The extractor generation for story records. Folded into ``knowledge_id`` so a future
#: extractor rewrite never silently collides with this generation's identity — mirrors
#: every other producer's ``EXTRACTOR_VERSION`` convention exactly.
EXTRACTOR_VERSION = "story/v1"

#: ``source_type`` recorded on every story record (design §2's 9-value table).
SOURCE_TYPE = "story"

#: Default ACL scope — story results are public corpus data, same convention as every
#: other producer (code/quality/policy/finding).
ACL_SCOPE = "public"

#: ``source_revision`` fallback for a story that never committed anything (e.g. every
#: session errored before its first commit). Never a fabricated sha — an honest marker,
#: mirroring ``knowledge_ingestion.RESULT_VERSION``'s fallback-not-fabrication convention.
REVISION_FALLBACK = "story-result/no-commit"


# ── Small deterministic helpers (mirror knowledge_ingestion / code_ingestion) ───


def _last_commit_sha(story_result: dict[str, Any]) -> str:
    """Return the last session's commit hash, else :data:`REVISION_FALLBACK`.

    The final commit is the exact code state the story concluded at — the natural
    ``source_revision`` for a story-level record (mirroring how ``code_ingestion``
    anchors a code record to the exact checkout it was derived from). Walking sessions
    in reverse and taking the first non-empty ``commit_hash`` tolerates a trailing
    session that errored before committing.
    """
    for session in reversed(story_result.get("sessions") or []):
        sha = session.get("commit_hash")
        if sha:
            return str(sha)
    return REVISION_FALLBACK


def _render_text(story_result: dict[str, Any]) -> str:
    """Render a one-line human-readable summary of the story's outcome.

    Not a substitute for the structured fields (``test_executed_success``,
    ``perturbation_strength``) — those are carried on dedicated typed fields, per
    ``AGENTS.md``'s measure-before-policy convention that a signal must be structurally
    present, not only prose-rendered. This text is the retrieval-facing evidence line.
    """
    story_name = str(story_result.get("story_name") or "")
    model = str(story_result.get("model") or "")
    condition = str(story_result.get("perturbation_condition") or "")
    summary = story_result.get("summary") or {}
    sessions = story_result.get("sessions") or []
    session_count = summary.get("session_count", len(sessions))
    all_successful = summary.get("all_successful")
    total_cost = summary.get("total_cost")

    if all_successful is True:
        status = "all sessions passed"
    elif all_successful is False:
        status = "some sessions failed"
    else:
        status = "success unmeasured"

    cost_part = f"${total_cost:.2f}" if isinstance(total_cost, (int, float)) else "cost unmeasured"
    return (
        f"{story_name} [{model}, {condition}]: {session_count} sessions, "
        f"{status}, {cost_part}"
    )


# ── Record construction ─────────────────────────────────────────


def build_story_record(
    story_result: dict[str, Any],
    *,
    repository_id: str = REPOSITORY_ID,
    now: datetime | None = None,
) -> KnowledgeRecord:
    """Derive ONE ``source_type=story`` :class:`KnowledgeRecord` from a story result dict.

    ``story_result`` is the plain dict shape ``StoryResult.to_dict()`` produces (the exact
    bytes ``story.save_story_result`` writes). Raises ``ValueError`` when the entry has no
    ``story_id`` — a story with no stable identity cannot be registered; callers that need
    batch behavior use :func:`derive_story_records`, which pre-filters this case instead of
    propagating the exception.

    ``authority`` is ``MEASURED`` and ``evidence_class`` is ``"[M]"`` (design §2: a story
    result is a genuinely measured outcome, not a derived/advisory conclusion).
    ``test_executed_success`` and ``perturbation_strength`` are carried through
    **structurally** (measured-or-``None``, never a fabricated default) from the story's own
    instrumented ledger fields (``story.py``'s ``StoryResult.test_executed_success`` /
    ``.perturbation_strength``) — ``confidence`` stays ``None`` at the story level (it is a
    *per-attempt* signal; see ``ledger_ingestion.py``'s per-session attempt records for the
    structured per-session confidence values).
    """
    story_id = str(story_result.get("story_id") or "")
    if not story_id:
        raise ValueError("story_result has no story_id — cannot derive a stable identity")

    source_uri = f"story:{story_id}"
    text = _render_text(story_result)
    revision = _last_commit_sha(story_result)

    # observed_at prefers the story's own completion/start timestamp; when the result carries
    # neither, the factory's producer-now default is used (leaving the key out of extra_fields).
    observed_at = str(story_result.get("completed_at") or story_result.get("started_at") or "")
    extra_fields = {
        "worktree_id": str(story_result.get("worktree") or ""),
        "extractor_version": EXTRACTOR_VERSION,
        "language": str(story_result.get("language") or ""),
        "test_executed_success": story_result.get("test_executed_success"),
        "perturbation_strength": story_result.get("perturbation_strength"),
    }
    if observed_at:
        extra_fields["observed_at"] = observed_at

    # Identity + the content-hash back-fill are the shared factory's job (record_factory).
    return build_record_from_parts(
        source_type=SOURCE_TYPE,
        source_uri=source_uri,
        logical_locator=story_id,
        repository_id=repository_id,
        revision=revision,
        authority=Authority.MEASURED,
        evidence_class="[M]",
        text=text,
        extra_fields=extra_fields,
        now=now,
    )


def derive_story_records(
    story_result: dict[str, Any],
    *,
    repository_id: str = REPOSITORY_ID,
    now: datetime | None = None,
) -> list[KnowledgeRecord]:
    """Derive the list of story records for one story result (today: zero-or-one).

    A list-returning wrapper around :func:`build_story_record`, for signature symmetry with
    ``derive_records`` / ``derive_code_records`` / ``derive_quality_records`` /
    ``derive_policy_records`` (every other producer in this package returns a list, even
    when one input yields at most one record). Returns ``[]`` — rather than raising — when
    ``story_result`` has no ``story_id``, so a batch caller (the one-time migration driver,
    plan step 9) can pre-filter cheaply without relying on an exception path, matching
    ``knowledge_ingestion.derive_records``'s ``_yields_finding`` pre-filter convention.
    """
    if not story_result.get("story_id"):
        return []
    return [build_story_record(story_result, repository_id=repository_id, now=now)]


def adapt_to_story_result(source: dict[str, Any], *, kind: str) -> dict[str, Any]:
    """Reshape a non-``StoryResult`` artifact into a ``StoryResult``-shaped dict.

    canonical-state R8: the ONE place that owns "what is the canonical story_id for a
    non-story artifact". The two historical adapters (the run-output adapter below and
    ``scripts/kb_produce_registry.py``'s summary-entry adapter) each hand-rolled this
    reshape with their own identity rationale; they are now two ``kind`` branches of this
    single helper, so each upstream shape's identity formula lives in exactly one place and
    cannot drift out of sync with the call site that derives its own artifact filename from
    it (``run.py``'s ``_save_results``).

    ``kind`` selects the upstream shape:

    * ``"run"`` — ``scripts/run.py``'s ``_save_results`` output
      (``{"experiment", "model", "runs": [...]}``). ``story_id`` reuses the EXACT string
      ``_save_results`` derives its own output filename from (``f"{name}_{model_slug}"``),
      so the synthetic identity matches the on-disk cell identity rather than inventing a
      second scheme. Raises ``ValueError`` when ``experiment`` is empty — mirrors
      ``build_story_record``'s "no story_id, no stable identity" contract.
    * ``"summary"`` — a recovered ``_results_summary.json`` entry. ``story_id`` is the
      entry's own durable cell locator (``worktree_name``, else ``run_id``); a missing
      locator yields an empty ``story_id`` (which ``derive_story_records`` pre-filters) —
      the "no stable identity" case is skipped, not raised, matching the summary-recovery
      migration's batch posture.

    Returns a dict ``build_story_record`` / ``derive_story_records`` accept directly. Any
    other ``kind`` raises ``ValueError``.
    """
    if kind == "run":
        name = str(source.get("experiment") or "")
        if not name:
            raise ValueError("run output has no 'experiment' — cannot derive a stable identity")
        model = str(source.get("model") or "")
        model_slug = model.replace(" ", "_").lower()
        run_output_id = f"{name}_{model_slug}"

        runs = source.get("runs") or []
        # A lightweight rollup computed here (run.py's own runs are flat per-run dicts, not
        # a pre-computed "summary" sub-block the way StoryResult.to_dict() already has one) —
        # deliberately minimal: this adapter's whole job is identity + a text-rendering input,
        # not a second analytics layer duplicating what run.py's own reporting already does.
        total_cost = sum(
            float(r.get("cost_usd") or 0.0) for r in runs if isinstance(r, dict)
        )

        return {
            "story_id": run_output_id,
            "story_name": name,
            "language": "",
            "model": model,
            "perturbation_condition": "",
            "worktree": "",
            "perturbation_strength": None,
            "test_executed_success": None,
            "summary": {"total_cost": total_cost, "session_count": len(runs)},
            "sessions": [],
        }

    if kind == "summary":
        story_id = str(source.get("worktree_name") or source.get("run_id") or "")
        return {
            "story_id": story_id,
            "story_name": str(source.get("experiment") or story_id),
            "language": str(source.get("language") or ""),
            "model": str(source.get("model") or ""),
            "perturbation_condition": str(source.get("condition") or ""),
            "worktree": "",  # recovered from git history — no live worktree to point at
            "perturbation_strength": source.get("perturbation_strength"),
            "test_executed_success": source.get("test_executed_success"),
            "sessions": [],
            "summary": {},
        }

    raise ValueError(f"unknown adapt kind {kind!r} — expected 'run' or 'summary'")


def derive_story_records_from_run_output(
    out: dict[str, Any],
    *,
    repository_id: str = REPOSITORY_ID,
    now: datetime | None = None,
) -> list[KnowledgeRecord]:
    """Adapt ``scripts/run.py``'s ``_save_results`` single-task output shape into the
    ``StoryResult``-shaped dict :func:`derive_story_records` expects, then delegate to it.

    The reshape itself is :func:`adapt_to_story_result` (``kind="run"``) — no second
    identity formula lives here (canonical-state R8). See that helper's docstring for the
    synthetic ``story_id`` formula and the "no ``experiment`` key" ``ValueError`` contract.
    """
    adapted_story_result = adapt_to_story_result(out, kind="run")
    return derive_story_records(adapted_story_result, repository_id=repository_id, now=now)
