"""ONE-TIME migration driver — backfills the pre-Delta-1 corpus into the canonical-state
registry (``docs/canonical_state_r2_plan.md`` step 9 / ``docs/canonical_state_r2_design.md``
§12's Migration plan, steps 3-6).

Mirrors ``scripts/kb_produce_sources.py``'s exact shape (a ``_SOURCES`` dict of
``{key: (source_type_label, derive_fn)}``, an ``argparse`` CLI selecting one-or-all keys, a
``--dry-run`` flag) rather than inventing a new CLI pattern. Every ``derive_*_pass``
function below is a THIN WRAPPER that reads existing files and calls the step-2/3/4
producer functions (``story_ingestion``, ``review_ingestion``, ``ledger_ingestion``,
``knowledge_ingestion``) — no new derivation/identity logic lives in this file, matching
the plan's explicit "purely an orchestration/CLI layer" framing.

Run order (the "ONE-TIME MIGRATION" sequence — executed once, by an operator, never by a
cron or a steady-state code path; the design's §12 step numbers are noted per source)::

    python scripts/kb_produce_registry.py --source story             # pass 1
    python scripts/kb_produce_registry.py --source review            # pass 1
    python scripts/kb_produce_registry.py --source story-worktree    # pass 3 (finding 1)
    python scripts/kb_produce_registry.py --source single-task       # clean single-task arm
    python scripts/kb_produce_registry.py --source contaminated      # pass 6 (77 cells)
    python scripts/kb_produce_registry.py --source meta-audit        # pass 6 (gap b)

Each invocation (when not ``--dry-run``) sets ``FINOPS_KB_WRITE=1`` for its own process
only, matching ``kb_produce_sources.py``'s existing convention. **None of these six
sources ever emits an ``actuation`` record** — this file imports only
``story_ingestion``/``review_ingestion``/``ledger_ingestion``/``knowledge_ingestion``
(never ``actuation_ingestion``), so ``knowledge_stream.publish_event``'s actuation gate
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
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# scripts/ → repo root → src, so the local instrument package wins over any installed one
# (matches the bootstrap in worker.py / kb_worker.py / kb_produce.py / kb_produce_sources.py).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from instrument import knowledge_ingestion as ki  # noqa: E402
from instrument import knowledge_stream as ks  # noqa: E402
from instrument import ledger_ingestion as li  # noqa: E402
from instrument import review_ingestion as ri  # noqa: E402
from instrument import story_ingestion as si  # noqa: E402
from instrument.paths import KB_ARTIFACT_DIR  # noqa: E402

REDIS_HOST = os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6380"))

#: Repo root, anchored to the script location so flags may be omitted regardless of cwd
#: (matches ``kb_produce_sources.REPO_ROOT``'s convention exactly).
REPO_ROOT = Path(__file__).resolve().parent.parent

# Durable per-record artifact directory — sourced from ``instrument.paths``
# (canonical-state R6), the single owner of the path (``KB_ARTIFACT_DIR`` imported above).

#: The ~156 main-repo story JSONs (pass 1). ``_remediation_contaminated/`` is a
#: subdirectory of this same directory but is its OWN pass ("contaminated") — the
#: "story" pass must not silently sweep it in, or a contaminated cell would register
#: twice under two different provenance labels.
STORIES_DIR = REPO_ROOT / "experiments" / "results" / "stories"
CONTAMINATED_DIR = STORIES_DIR / "_remediation_contaminated"

#: The merged (not per-session-shard) review JSONs finalize_reviews.py writes (pass 1).
REVIEWS_DIR = REPO_ROOT / "experiments" / "results" / "reviews"

#: The results directory holding the clean single-task re-run files
#: (``task_manager_*.json`` + ``process_perturbation_resample_*.json``) that form the
#: canonical clean single-task perturbation arm (docs/data_integrity_findings.md).
SINGLE_TASK_DIR = REPO_ROOT / "experiments" / "results"

#: Filename prefixes that identify a single-task run file (vs. the story/review/lab
#: artifacts that also live in the same results directory).
SINGLE_TASK_PREFIXES = ("task_manager_", "process_perturbation_resample_")

#: The invalid gpt-5.6 model id — the plain ``gpt-5.6`` (NOT the -luna/-sol/-terra
#: variants), whose single-task file is a server error (every run all-zero), skipped
#: wholesale (docs/data_integrity_findings.md).
INVALID_GPT56_MODEL = "gpt-5.6"

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


# ── Pass 3: stranded worktrees (finding 1) ──────────────────────


def _contaminated_story_ids() -> set[str]:
    """The story_ids of the quarantined contaminated cells (pass 6 tombstones them).

    ``feature_queue-steer-2`` was created BEFORE the remediation moved the 77 contaminated
    files into ``_remediation_contaminated/``, so its TOP-LEVEL ``stories/`` still holds
    them. Pass 3 must skip those files — otherwise it registers a contaminated cell as a
    plain ``upsert`` (``current``) before pass 6 can tombstone it, and the tombstone's
    ``delete`` event is deduped away by ``knowledge_id``.
    """
    ids: set[str] = set()
    for f in _iter_json_files(CONTAMINATED_DIR):
        ids.add(f.stem.rsplit("_", 1)[-1])
    return ids


def derive_story_pass3(repository_id: str, revision: str | None = None) -> list:
    """Pass 3: story JSONs stranded in the two named worktrees (finding 1).

    Worktree-independent identity (``story_ingestion``'s ``entity_id`` hashes
    ``story_id``, never a filesystem path — see that module's docstring) makes
    re-deriving a story that ALSO exists in the main repo a free no-op: it yields the
    SAME ``knowledge_id``, so a downstream checkpoint dedupe (``emit_records`` below)
    silently skips it. Only genuinely stranded stories (absent from ``STORIES_DIR``)
    actually add anything new.

    Contaminated cells that happen to still live in a worktree's top-level ``stories/``
    are EXCLUDED here (see :func:`_contaminated_story_ids`): they are pass 6's tombstones,
    not stranded stories.
    """
    contaminated = _contaminated_story_ids()
    records = []
    for worktree in STRANDED_WORKTREES:
        stories_dir = worktree / "experiments" / "results" / "stories"
        found = list(_iter_json_files(stories_dir))
        if not found:
            log(f"story-worktree: no stories found under {stories_dir} (worktree may be gone)")
        for f in found:
            if f.stem.rsplit("_", 1)[-1] in contaminated:
                log(f"story-worktree: skipping contaminated cell {f.name} (pass 6 tombstones it)")
                continue
            data = _load_json(f)
            if data is None:
                log(f"story-worktree: skipping unreadable file {f}")
                continue
            records.extend(si.derive_story_records(data, repository_id=repository_id))
    return records


# ── Single-task: the clean single-task perturbation arm ──────────


def _iter_single_task_files():
    """Yield every single-task run file directly under the results dir, sorted.

    ``task_manager_*.json`` and ``process_perturbation_resample_*.json`` are the clean
    single-task re-runs (docs/data_integrity_findings.md) — the story/review/lab/lab-*
    artifacts that share the same directory are excluded by the prefix filter.
    """
    if not SINGLE_TASK_DIR.is_dir():
        return
    for f in sorted(SINGLE_TASK_DIR.glob("*.json")):
        if f.name.startswith(SINGLE_TASK_PREFIXES):
            yield f


def _is_invalid_gpt56(data: dict[str, Any]) -> bool:
    """Return True for the invalid plain-``gpt-5.6`` single-task file.

    docs/data_integrity_findings.md: the plain ``gpt-5.6`` model (NOT the -luna/-sol/
    -terra variants) errored — every run carries correctness 0.0 / zero tokens / a
    server-error transcript — and must be skipped wholesale, never registered as a
    canonical perturbation finding. The -luna/-sol/-terra variants are valid and kept.
    """
    return str(data.get("model") or "").strip() == INVALID_GPT56_MODEL


def _run_to_entry(run: dict[str, Any], file_model: Any) -> dict[str, Any]:
    """Adapt one single-task run dict into the ``_results_summary.json``-shaped entry
    ``knowledge_ingestion.derive_records`` expects.

    Field renames only (canonical-state R8 posture — no second identity formula):
    ``cost_usd`` → ``cost``, ``escape_score`` → ``escape`` (the basin-escape signal
    ``build_evidence_cards``' ``_derive_flail`` falls back to), and the run's ``workdir``
    basename becomes the durable ``worktree_name``/``run_id`` locator. ``model`` prefers
    the run's own full provider/model id, falling back to the file-level short id.
    """
    worktree_name = Path(str(run.get("workdir") or "")).name
    return {
        "worktree_name": worktree_name,
        "run_id": worktree_name,
        "model": str(run.get("model") or file_model or ""),
        "operator": str(run.get("operator") or ""),
        "perturbation_class": str(run.get("perturbation_class") or ""),
        "strategy": str(run.get("strategy") or ""),
        "correctness": run.get("correctness"),
        "cost": run.get("cost_usd"),
        "escape": run.get("escape_score"),
        "test_executed_success": run.get("test_executed_success"),
        "confidence": run.get("confidence"),
        "perturbation_strength": run.get("perturbation_strength"),
    }


def derive_single_task_pass(repository_id: str, revision: str | None = None) -> list:
    """The clean single-task perturbation arm — ``task_manager_*.json`` +
    ``process_perturbation_resample_*.json`` (docs/data_integrity_findings.md).

    Each run in each file becomes ONE measured-finding record (``source_type=finding``,
    never ``story``) via ``knowledge_ingestion.derive_records`` — the same finding shape
    the summary corpus uses — keyed by the run's worktree basename. The invalid plain
    ``gpt-5.6`` file is skipped wholesale. Each file's ``file://`` locator is its own
    ``source_uri``, so these findings never share the retired aggregate summary's
    namespace.
    """
    records = []
    for f in _iter_single_task_files():
        data = _load_json(f)
        if data is None:
            log(f"single-task: skipping unreadable file {f}")
            continue
        if _is_invalid_gpt56(data):
            log(f"single-task: skipping invalid gpt-5.6 file {f}")
            continue
        source_uri = f"file://experiments/results/{f.name}"
        entries = []
        for run in data.get("runs") or []:
            if not isinstance(run, dict):
                continue
            entry = _run_to_entry(run, data.get("model"))
            if not entry["worktree_name"]:
                continue
            entries.append(entry)
        records.extend(
            ki.derive_records(entries, repository_id=repository_id, source_uri=source_uri)
        )
    return records


# ── Pass 6: contaminated tombstones + meta_* retro-tagging ───────

#: Forensic reason attached to every contaminated-cell tombstone (design §7c / §12 step 6).
CONTAMINATED_REASON = (
    "contaminated: ran as CLEAN due to the P0-7 mutation fallback "
    "(mutated_spec = mutated or specification); labeled early_degrade but never degraded"
)


def derive_contaminated_tombstone_pass(repository_id: str, revision: str | None = None) -> list:
    """Pass 6: the 77 contaminated cells under ``stories/_remediation_contaminated/``.

    Derives one story record per contaminated file (its outcome stays durably citable), but the
    *tombstone* is applied at emit time: ``main()`` publishes these under ``operation="delete"``
    with :data:`CONTAMINATED_REASON`, so the entity registers as tombstoned rather than current.
    The record itself carries the fact; the event carries the change operation — same split as
    every other producer in this package.
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


def emit_records(
    r, records: list, operation: str = "upsert", reason: str = ""
) -> tuple[int, int]:
    """Write each durable artifact then publish its pointer event; skip already-checkpointed ids.

    ``operation`` (one of ``upsert``/``supersede``/``delete``) and ``reason`` (required
    non-empty for ``delete``) are forwarded to ``record_to_event`` so the tombstone pass can
    register a record as ``delete``-with-reason rather than a plain ``upsert``. Returns
    ``(emitted, skipped)``. Ordering mirrors ``kb_produce_sources.emit_records``: the artifact
    lands *before* the event, so a consumer can always read + verify the exact bytes the
    event's ``content_hash`` covers.
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
        ks.publish_event(
            r,
            record_to_event(record, operation=operation, reason=reason),
            source_type=record.source_type,
        )
        r.hset(ks.CHECKPOINT_KEY, record.knowledge_id, record.indexed_at)
        emitted += 1
    return emitted, skipped


# ── Source table ────────────────────────────────────────────────

#: Each source: a key -> (source_type label, derive callable). The derive callables all
#: share the signature ``(repository_id, revision=None) -> list[KnowledgeRecord]``.
_SOURCES = {
    "story": ("story", derive_story_pass1),
    "story-worktree": ("story", derive_story_pass3),
    "review": ("review", derive_review_pass1),
    "single-task": ("finding", derive_single_task_pass),
    "contaminated": ("story", derive_contaminated_tombstone_pass),
    "meta-audit": ("meta_session", derive_meta_audit_pass),
}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "ONE-TIME migration driver — backfill the pre-Delta-1 corpus "
            "(stories/reviews/stranded worktrees/single-task/contaminated/meta_*) into the "
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
    args = parser.parse_args(argv)

    source_keys = list(_SOURCES.keys()) if args.source == "all" else [args.source]

    # 1. Derive every requested source. Purely local/filesystem/git reads — no Redis
    #    connection is attempted here, in --dry-run or otherwise, which is what makes
    #    --dry-run genuinely side-effect-free rather than merely "doesn't write".
    derived: dict[str, list] = {}
    for key in source_keys:
        label, derive_fn = _SOURCES[key]
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
    #    (matches kb_produce_sources.py's convention exactly). The contaminated source is
    #    published under operation="delete" + CONTAMINATED_REASON (a tombstone); every other
    #    source is a plain "upsert".
    os.environ["FINOPS_KB_WRITE"] = "1"
    r = ks.connect(host=REDIS_HOST, port=REDIS_PORT)
    total_emitted = 0
    total_skipped = 0
    for key in source_keys:
        records = derived[key]
        if args.limit and args.limit > 0:
            records = records[: args.limit]
        if key == "contaminated":
            e, s = emit_records(r, records, operation="delete", reason=CONTAMINATED_REASON)
        else:
            e, s = emit_records(r, records)
        total_emitted += e
        total_skipped += s
    log(f"emitted={total_emitted} skipped={total_skipped} (already checkpointed) total={len(all_records)}")


if __name__ == "__main__":
    main()
