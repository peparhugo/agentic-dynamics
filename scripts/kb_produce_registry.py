"""ONE-TIME migration driver — backfills the pre-Delta-1 corpus into the canonical-state
registry (``docs/canonical_state_r2_plan.md`` step 9 / ``docs/canonical_state_r2_design.md``
§12's Migration plan, steps 3-6).

Mirrors ``scripts/kb_produce_sources.py``'s exact shape (a ``_SOURCES`` dict of
``{key: (source_type_label, derive_fn)}``, an ``argparse`` CLI selecting one-or-all keys, a
``--dry-run`` flag) rather than inventing a new CLI pattern. Every ``derive_*_pass``
function below is a THIN WRAPPER that reads existing files and calls the step-2/3/4
producer functions (``story_ingestion``, ``review_ingestion``, ``ledger_ingestion``) — no
new derivation/identity logic lives in this file, matching the plan's explicit "purely an
orchestration/CLI layer" framing.

Run order (the "ONE-TIME MIGRATION" sequence — executed once, by an operator, never by a
cron or a steady-state code path; the design's §12 step numbers are noted per source)::

    python scripts/kb_produce_registry.py --source story             # pass 1
    python scripts/kb_produce_registry.py --source review            # pass 1
    python scripts/kb_produce_registry.py --source story-worktree    # pass 3 (finding 1)
    python scripts/kb_produce_registry.py --source summary-recovery --since-sha <sha>
                                                                       # pass 3 (gap c)
    python scripts/kb_produce_registry.py --source contaminated      # pass 6 (77 cells)
    python scripts/kb_produce_registry.py --source meta-audit        # pass 6 (gap b)

Each invocation (when not ``--dry-run``) sets ``FINOPS_KB_WRITE=1`` for its own process
only, matching ``kb_produce_sources.py``'s existing convention. **None of these six
sources ever emits an ``actuation`` record** — this file imports only
``story_ingestion``/``review_ingestion``/``ledger_ingestion`` (never
``actuation_ingestion``), so ``knowledge_stream.publish_event``'s actuation gate
(``FINOPS_ACTUATION_ARMED``) is never exercised by migration at all; that is a structural
fact of this file's imports, not a runtime check this script needs to perform.

Isolation (load-bearing, identical to every other KB producer in this package): touches
only ``127.0.0.1:FINOPS_REDIS_PORT`` (default **6380**) **DB 2** — never port 6379 (the
story-agent sandbox that ``flushall()``s) nor DB 1 (the framework queue).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# scripts/ → repo root → src, so the local instrument package wins over any installed one
# (matches the bootstrap in worker.py / kb_worker.py / kb_produce.py / kb_produce_sources.py).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from instrument import knowledge_stream as ks  # noqa: E402
from instrument import ledger_ingestion as li  # noqa: E402
from instrument import review_ingestion as ri  # noqa: E402
from instrument import story_ingestion as si  # noqa: E402

REDIS_HOST = os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6380"))

#: Repo root, anchored to the script location so flags may be omitted regardless of cwd
#: (matches ``kb_produce_sources.REPO_ROOT``'s convention exactly).
REPO_ROOT = Path(__file__).resolve().parent.parent

#: Durable per-record artifact directory (mirrors ``kb_produce_sources.KB_ARTIFACT_DIR``).
KB_ARTIFACT_DIR = REPO_ROOT / "experiments" / "results" / "kb"

#: The ~156 main-repo story JSONs (pass 1). ``_remediation_contaminated/`` is a
#: subdirectory of this same directory but is its OWN pass ("contaminated") — the
#: "story" pass must not silently sweep it in, or a contaminated cell would register
#: twice under two different provenance labels.
STORIES_DIR = REPO_ROOT / "experiments" / "results" / "stories"
CONTAMINATED_DIR = STORIES_DIR / "_remediation_contaminated"

#: The merged (not per-session-shard) review JSONs finalize_reviews.py writes (pass 1).
REVIEWS_DIR = REPO_ROOT / "experiments" / "results" / "reviews"

#: The current, post-shrink summary — used only to determine which of the historical
#: entries at ``--since-sha`` are genuinely missing (gap c's diff step).
RESULTS_SUMMARY_PATH = REPO_ROOT / "experiments" / "results" / "_results_summary.json"

#: The corpus of raw session titles (incl. non-experiment ones) — used by the
#: "meta-audit" pass to find any ``meta_*`` title that a naive substring match would
#: have folded into "ledger_attempt" cost rollups (gap b).
INVENTORY_PATH = REPO_ROOT / "experiments" / "inventory.json"

#: The two stranded worktrees named in the design (finding 1) — hardcoded, one-time-only
#: paths. This script is a migration driver, never re-run as a steady-state mechanism, so
#: these do not need to be configurable via a flag; a future stranded worktree would be a
#: NEW one-time invocation with its own path, not a reason to generalize this constant.
STRANDED_WORKTREES = (
    Path("/tmp/pipeline/feature_remediation-integrity"),
    Path("/tmp/pipeline/feature_queue-steer-2"),
)

DEFAULT_REPOSITORY_ID = "agentic-dynamics"

#: How many sample records ``--dry-run`` prints per source (a preview, not the whole batch).
SAMPLE_COUNT = 5


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}][kb-produce-registry] {msg}", flush=True)


def _load_json(path: Path) -> Any | None:
    """Read and parse one JSON file; return ``None`` (not raise) on any read/parse error.

    A migration walking hundreds of historical files must tolerate an occasional
    truncated/corrupt one without aborting the whole pass — the caller logs and skips.
    """
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _iter_json_files(directory: Path):
    """Yield every ``*.json`` file directly under ``directory`` (non-recursive), sorted
    for determinism. Missing directories yield nothing rather than raising — several
    passes below probe directories that may not exist in every checkout (e.g. a
    stranded worktree that has since been cleaned up)."""
    if not directory.is_dir():
        return
    yield from sorted(directory.glob("*.json"))


# ── Pass 1: main-repo stories + reviews ─────────────────────────


def derive_story_pass1(repository_id: str, revision: str | None = None) -> list:
    """Pass 1: the ~156 main-repo story JSONs under ``experiments/results/stories/``."""
    records = []
    for f in _iter_json_files(STORIES_DIR):
        data = _load_json(f)
        if data is None:
            log(f"story: skipping unreadable file {f}")
            continue
        records.extend(si.derive_story_records(data, repository_id=repository_id))
    return records


#: A merged review file is named ``review_{story_id}.json``. The per-session shards
#: ``finalize_reviews.py`` merges FROM (not the merged file it writes TO) are named
#: ``review_{story_id}_S{n}.json`` / ``review_{story_id}_story.json`` — these carry a
#: different, incomplete shape (a single ``CommitReview``/``StoryReview``, not the merged
#: ``{"commit_reviews": [...], "story_review": {...}}`` body ``review_ingestion``
#: expects) and must be excluded, or this pass would derive malformed/duplicate records.
_REVIEW_SHARD_SUFFIX = re.compile(r"_S\d+$|_story$")


def _is_merged_review_file(path: Path) -> bool:
    stem = path.stem
    if not stem.startswith("review_"):
        return False
    rest = stem[len("review_"):]
    return not _REVIEW_SHARD_SUFFIX.search(rest)


def derive_review_pass1(repository_id: str, revision: str | None = None) -> list:
    """Pass 1: the merged ``review_{story_id}.json`` files under ``experiments/results/reviews/``."""
    records = []
    for f in _iter_json_files(REVIEWS_DIR):
        if not _is_merged_review_file(f):
            continue
        data = _load_json(f)
        if data is None:
            log(f"review: skipping unreadable file {f}")
            continue
        records.extend(ri.derive_review_records(data, repository_id=repository_id))
    return records


# ── Pass 3: stranded worktrees (finding 1) + lost-83 recovery (gap c) ────────


def derive_story_pass3(repository_id: str, revision: str | None = None) -> list:
    """Pass 3: story JSONs stranded in the two named worktrees (finding 1).

    Worktree-independent identity (``story_ingestion``'s ``entity_id`` hashes
    ``story_id``, never a filesystem path — see that module's docstring) makes
    re-deriving a story that ALSO exists in the main repo a free no-op: it yields the
    SAME ``knowledge_id``, so a downstream checkpoint dedupe (``emit_records`` below)
    silently skips it. Only genuinely stranded stories (absent from ``STORIES_DIR``)
    actually add anything new.
    """
    records = []
    for worktree in STRANDED_WORKTREES:
        stories_dir = worktree / "experiments" / "results" / "stories"
        found = list(_iter_json_files(stories_dir))
        if not found:
            log(f"story-worktree: no stories found under {stories_dir} (worktree may be gone)")
        for f in found:
            data = _load_json(f)
            if data is None:
                log(f"story-worktree: skipping unreadable file {f}")
                continue
            records.extend(si.derive_story_records(data, repository_id=repository_id))
    return records


def _historical_results_summary(since_sha: str) -> dict[str, Any]:
    """Return the parsed ``_results_summary.json`` as it existed at ``since_sha``.

    Uses ``git show`` rather than checking out the commit — read-only, does not disturb
    the working tree. Raises ``RuntimeError`` when the sha or the path at that revision
    is invalid (a migration pass must not silently treat "no such commit" as "no entries").
    """
    proc = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "show", f"{since_sha}:experiments/results/_results_summary.json"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"git show {since_sha}:experiments/results/_results_summary.json failed: "
            f"{proc.stderr.strip()}"
        )
    return json.loads(proc.stdout)


def _summary_entry_to_story_result(entry: dict[str, Any]) -> dict[str, Any]:
    """Adapt one recovered ``_results_summary.json`` entry into the minimal
    ``StoryResult``-shaped dict ``story_ingestion.build_story_record`` expects.

    A field-renaming adapter only — not a second identity formula. ``story_id`` below
    becomes ``entity_id``'s ``logical_locator`` exactly the way a live ``StoryResult``'s
    own ``story_id`` would; the historical entry has no per-session breakdown to recover
    (that granularity was never in ``_results_summary.json`` to begin with), so
    ``sessions`` stays empty — a caveated-but-canonical historical fact (design §7c), not
    a fabricated reconstruction of session-level detail nobody measured.
    """
    story_id = str(entry.get("worktree_name") or entry.get("run_id") or "")
    return {
        "story_id": story_id,
        "story_name": str(entry.get("experiment") or story_id),
        "language": str(entry.get("language") or ""),
        "model": str(entry.get("model") or ""),
        "perturbation_condition": str(entry.get("condition") or ""),
        "worktree": "",  # recovered from git history — no live worktree to point at
        "perturbation_strength": entry.get("perturbation_strength", 0.0),
        "test_executed_success": entry.get("test_executed_success"),
        "sessions": [],
        "summary": {},
    }


def derive_summary_recovery_pass(
    repository_id: str, revision: str | None = None, *, since_sha: str | None = None
) -> list:
    """Pass 3, gap (c): recover entries present in ``_results_summary.json`` at
    ``since_sha`` but absent from the CURRENT file (design §7c's ~83-entry remediation).

    ``since_sha`` (the pre-shrink commit) is a genuine one-time operator decision, not
    something this script can safely default or guess — design §7c's own procedure
    begins "``git show <pre-shrink-commit>:...``", naming a specific historical commit
    the operator identifies by inspecting ``git log`` themselves. Raising here (rather
    than silently no-op-ing) keeps that requirement visible instead of letting
    ``--source summary-recovery`` silently emit nothing.
    """
    if not since_sha:
        raise ValueError(
            "summary-recovery requires --since-sha <commit> (the pre-shrink commit "
            "documented in docs/canonical_state_r2_design.md §7c) — this is a one-time "
            "operator decision, never a default this script can safely guess"
        )
    historical = _historical_results_summary(since_sha)
    historical_entries = historical.get("entries") or []

    current = _load_json(RESULTS_SUMMARY_PATH) or {}
    current_keys = {
        str(e.get("experiment") or e.get("worktree_name") or e.get("run_id") or "")
        for e in (current.get("entries") or [])
    }

    records = []
    for entry in historical_entries:
        key = str(entry.get("experiment") or entry.get("worktree_name") or entry.get("run_id") or "")
        if not key or key in current_keys:
            continue  # not missing — already present in the post-shrink file
        story_result = _summary_entry_to_story_result(entry)
        records.extend(si.derive_story_records(story_result, repository_id=repository_id))
    return records


# ── Pass 6: contaminated tombstones + meta_* retro-tagging ───────


def derive_contaminated_tombstone_pass(repository_id: str, revision: str | None = None) -> list:
    """Pass 6: the 77 contaminated cells under ``stories/_remediation_contaminated/``.

    Registers each as a story record so its outcome is durably indexed and citable. The
    ``delete``-with-``reason`` TOMBSTONE semantics design §7c/§12 step 6 calls for are a
    property of the ``KnowledgeEvent.operation`` a caller PUBLISHES this record under —
    not something ``KnowledgeRecord``/``story_ingestion.build_story_record`` itself
    carries (mirrors every other producer in this package: the record describes the
    fact, the event describes the change operation). This function stays a thin wrapper
    over the step-2 producer per this file's "no new derivation logic" rule; it is the
    caller's job (a future publish step) to construct the ``delete`` event with a
    forensic ``reason`` when actually emitting these records to the stream.
    """
    records = []
    for f in _iter_json_files(CONTAMINATED_DIR):
        data = _load_json(f)
        if data is None:
            log(f"contaminated: skipping unreadable file {f}")
            continue
        records.extend(si.derive_story_records(data, repository_id=repository_id))
    return records


def _meta_session_id(title: str) -> str:
    """Return a stable id for a bare inventory title with no story_id of its own."""
    return hashlib.sha256(title.encode("utf-8")).hexdigest()[:16]


def derive_meta_audit_pass(repository_id: str, revision: str | None = None) -> list:
    """Pass 6, gap (b): retro-tag any ``meta_*``-titled session in the inventory that a
    naive title-substring match would have folded into ``ledger_attempt`` cost rollups.

    Reuses ``ledger_ingestion.classify_session``/``build_attempt_record`` directly —
    deliberately NOT ``derive_ledger_records`` (which also builds a ``ledger_job``
    record): a bare inventory title has no ``story_id`` and no ``sessions`` structure of
    its own and is not itself an experiment cell, so emitting a ``ledger_job`` record for
    it would pollute the very rollup this pass exists to protect against. Only titles
    ``classify_session()`` actually routes to ``"meta_session"`` are emitted — a genuine
    experiment title already has its own job/attempt records from the ``story`` pass and
    is silently skipped here (not double-registered under a second provenance label).
    """
    data = _load_json(INVENTORY_PATH)
    if data is None:
        log(f"meta-audit: {INVENTORY_PATH} not found or unreadable")
        return []

    records = []
    for entry in data.get("experiment_session_titles") or []:
        title = str(entry.get("title") or "")
        if not title or li.classify_session(title) != li.SOURCE_TYPE_META:
            continue

        session_id = _meta_session_id(title)
        # A minimal synthetic single-session story_result — solely to give
        # build_attempt_record the shape it expects (story_id -> attempt_id; the
        # session's agentic block -> tokens/cost). No new identity formula: attempt_id
        # is still job_id + session_number, exactly ledger_ingestion's own convention.
        synthetic_story_result = {
            "story_id": session_id,
            "story_name": title,
            "language": "",
            "worktree": "",
            "perturbation_strength": None,
            "test_executed_success": None,
        }
        synthetic_session = {
            "session_number": 1,
            "commit_hash": "",
            "agentic": {
                "total_tokens": entry.get("tokens_output"),
                "estimated_cost_usd": entry.get("cost"),
                "confidence": None,
            },
        }
        opencode_session_row = {"title": title}
        records.append(
            li.build_attempt_record(
                synthetic_story_result, synthetic_session, opencode_session_row, {},
                repository_id=repository_id,
            )
        )
    return records


# ── Emission (identical logic to kb_produce_sources.py) ──────────


def load_checkpoint_ids(r) -> set[str]:
    """Return the already-checkpointed ``knowledge_id``s (the idempotence keys)."""
    return set(r.hkeys(ks.CHECKPOINT_KEY))


def emit_records(r, records: list) -> tuple[int, int]:
    """Write each durable artifact then publish its pointer event; skip already-checkpointed ids.

    Returns ``(emitted, skipped)``. Ordering mirrors ``kb_produce_sources.emit_records``:
    the artifact lands *before* the event, so a consumer can always read + verify the
    exact bytes the event's ``content_hash`` covers.
    """
    from instrument.knowledge_ingestion import record_to_artifact, record_to_event

    emitted = 0
    skipped = 0
    for record in records:
        if r.hget(ks.CHECKPOINT_KEY, record.knowledge_id) is not None:
            skipped += 1
            continue
        artifact = record_to_artifact(record)
        KB_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        (KB_ARTIFACT_DIR / f"{record.knowledge_id}.json").write_bytes(artifact)
        ks.publish_event(r, record_to_event(record), source_type=record.source_type)
        r.hset(ks.CHECKPOINT_KEY, record.knowledge_id, record.indexed_at)
        emitted += 1
    return emitted, skipped


# ── Source table ────────────────────────────────────────────────

#: Each source: a key -> (source_type label, derive callable). The derive callables all
#: share the signature ``(repository_id, revision=None, **kwargs) -> list[KnowledgeRecord]``
#: — ``summary_recovery`` additionally accepts ``since_sha`` via a small wrapper below
#: (``main()`` passes it as a keyword only when that source is selected).
_SOURCES = {
    "story": ("story", derive_story_pass1),
    "story-worktree": ("story", derive_story_pass3),
    "review": ("review", derive_review_pass1),
    "summary-recovery": ("story", derive_summary_recovery_pass),
    "contaminated": ("story", derive_contaminated_tombstone_pass),
    "meta-audit": ("meta_session", derive_meta_audit_pass),
}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "ONE-TIME migration driver — backfill the pre-Delta-1 corpus "
            "(stories/reviews/stranded worktrees/lost-83/contaminated/meta_*) into the "
            "canonical-state registry. Never invoked by a cron or steady-state code path."
        )
    )
    parser.add_argument(
        "--source",
        default="all",
        choices=[*_SOURCES.keys(), "all"],
        help="which migration source to run (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report the would-emit counts and samples, touching neither Redis nor the filesystem",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="cap the number of records emitted across selected sources (0 = no cap)",
    )
    parser.add_argument(
        "--repository-id",
        default=DEFAULT_REPOSITORY_ID,
        help="repository identity folded into entity_id",
    )
    parser.add_argument(
        "--since-sha",
        default=None,
        help="pre-shrink commit for --source summary-recovery (design §7c) — required only by that source",
    )
    args = parser.parse_args(argv)

    source_keys = list(_SOURCES.keys()) if args.source == "all" else [args.source]

    # 1. Derive every requested source. Purely local/filesystem/git reads — no Redis
    #    connection is attempted here, in --dry-run or otherwise, which is what makes
    #    --dry-run genuinely side-effect-free rather than merely "doesn't write".
    derived: dict[str, list] = {}
    for key in source_keys:
        label, derive_fn = _SOURCES[key]
        if key == "summary-recovery":
            records = derive_fn(args.repository_id, since_sha=args.since_sha)
        else:
            records = derive_fn(args.repository_id)
        derived[key] = records
        log(f"{key} ({label}): derived {len(records)} record(s)")

    all_records = [rec for key in source_keys for rec in derived[key]]
    if args.limit and args.limit > 0:
        all_records = all_records[: args.limit]

    if args.dry_run:
        per_source: dict[str, int] = {}
        for key in source_keys:
            per_source[key] = len(derived[key][: args.limit] if args.limit else derived[key])
        log(
            f"dry-run: would emit {len(all_records)} record(s) "
            f"(repository-id={args.repository_id!r}, limit={args.limit or 'none'}) "
            f"— by source: {per_source}"
        )
        for rec in all_records[:SAMPLE_COUNT]:
            log(f"  {rec.knowledge_id[:12]}  [{rec.source_type}]  {rec.text[:80]}")
        return

    # 2. Emit — fail fast on connection (knowledge_stream.connect raises on a downed
    #    stream). The producer is an authorized writer for the duration of this run only
    #    (matches kb_produce_sources.py's convention exactly).
    os.environ["FINOPS_KB_WRITE"] = "1"
    r = ks.connect(host=REDIS_HOST, port=REDIS_PORT)
    emitted, skipped = emit_records(r, all_records)
    log(f"emitted={emitted} skipped={skipped} (already checkpointed) total={len(all_records)}")


if __name__ == "__main__":
    main()
