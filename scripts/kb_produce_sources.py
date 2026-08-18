"""Batch producer for the code / quality / policy sources of the runtime-RAG KB.

This is the *sources* producer — the sibling of ``scripts/kb_produce.py`` (which emits
measured *findings*). Where ``kb_produce.py`` derives ``MEASURED`` findings from a
``_results_summary.json``, this script derives three other source types through the SAME
pointer contract:

* ``code``    — ``derive_code_records`` over ``src/`` and ``scripts/`` (``SOURCE`` / ``[C]``),
* ``quality`` — ``derive_quality_records`` over the repo root (SonarQube/LSP → ``MEASURED``/``[M]``,
  entropy → ``DERIVED``/``[C]``, absent tools skipped-with-note),
* ``policy``  — ``derive_policy_records`` over the pinned policy surface (``POLICY`` / ``[P]``).

    python scripts/kb_produce_sources.py --source code --dry-run
    python scripts/kb_produce_sources.py --source code --limit 20     # smoke
    python scripts/kb_produce_sources.py --source all                # full emit

Idempotence contract (identical to ``kb_produce.py``): ``knowledge_id`` is the idempotence key.
Before emitting, the producer checks the checkpoint hash (``CHECKPOINT_KEY`` on DB 2) with
``HGET`` and dedupes in-process; only a never-seen ``knowledge_id`` is published, then ``HSET``
into the checkpoint. Re-running emits nothing new. The durable per-record artifact is written to
``experiments/results/kb/<knowledge_id>.json`` *before* the pointer event lands, so the consumer
can read + verify the exact bytes the event's ``content_hash`` covers.

Isolation (load-bearing): the producer touches **only** ``127.0.0.1:FINOPS_REDIS_PORT``
(default **6380**) **DB 2** — the knowledge-stream DB reserved by ``knowledge_stream``. It never
touches 6379 (the story-agent test sandbox that ``flushall()``s) nor DB 1 (the framework queue).
A connection failure raises immediately rather than silently dropping or retrying forever.
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# scripts/ → repo root → src, so the local instrument package wins over any installed one
# (matches the bootstrap in worker.py / kb_worker.py / kb_produce.py).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from instrument import code_ingestion as ci  # noqa: E402
from instrument import knowledge_stream as ks  # noqa: E402
from instrument import policy_ingestion as pi  # noqa: E402
from instrument import quality_ingestion as qi  # noqa: E402

REDIS_HOST = os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6380"))

#: Repo root, anchored to the script location so flags may be omitted regardless of cwd.
REPO_ROOT = Path(__file__).resolve().parent.parent

#: Durable per-record artifact directory (mirrors ``kb_produce.KB_ARTIFACT_DIR``).
KB_ARTIFACT_DIR = REPO_ROOT / "experiments" / "results" / "kb"

#: Subdirectories the ``code`` source derives over (the spec scopes code records to these).
CODE_ROOTS = ("src", "scripts")

#: How many sample records ``--dry-run`` prints per source (a preview, not the whole batch).
SAMPLE_COUNT = 5


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}][kb-produce-sources] {msg}", flush=True)


def git_head_sha() -> str:
    """Return the repo's HEAD sha (the injected ``revision``), or ``""`` when unavailable.

    Deterministic and injectable via ``--revision``; the default reads the live checkout so the
    producer stamps the actual revision the records describe.
    """
    r = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    )
    return r.stdout.strip() if r.returncode == 0 else ""


# ── Derivation (each source → records, plus a notes side-channel for quality) ──


def derive_code(repository_id: str, revision: str) -> list:
    """Derive ``source_type=code`` records over ``src/`` and ``scripts/``."""
    records = []
    for rel in CODE_ROOTS:
        records.extend(
            ci.derive_code_records(
                None,
                repository_id=repository_id,
                revision=revision,
                repo_root=REPO_ROOT / rel,
            )
        )
    return records


def derive_quality(repository_id: str, revision: str) -> tuple[list, list[str]]:
    """Derive ``source_type=report`` records over ``src/``; returns (records, notes).

    Scoped to ``src/`` (the instrument package, 51 modules) rather than the repo root on
    purpose: the repo root sweeps in ``experiments/results/`` (~200 MB of backfilled generated
    code across 2600+ files), which makes the SonarQube scan impractically slow (it times out
    at 300 s). ``src/`` is the actual codebase whose quality we measure; ``scripts/`` is
    operational glue. The scope is a fixed, documented decision — not a tunable.
    """
    notes: list[str] = []
    records = qi.derive_quality_records(
        REPO_ROOT / "src",
        repository_id=repository_id,
        revision=revision,
        notes=notes,
    )
    return records, notes


def derive_policy(repository_id: str, revision: str) -> list:
    """Derive ``authority=POLICY`` records over the pinned policy surface."""
    paths = pi.discover_policy_paths(REPO_ROOT)
    return pi.derive_policy_records(
        paths, repository_id=repository_id, revision=revision, repo_root=REPO_ROOT
    )


# ── Emission (identical logic to kb_produce.py) ────────────────


def plan_emissions(
    records: list,
    *,
    limit: int = 0,
    known_ids: set[str] | frozenset[str] | None = None,
) -> list:
    """Cap by ``limit`` then drop already-emitted ids (pure, no Redis)."""
    if limit and limit > 0:
        records = records[:limit]
    seen: set[str] = set(known_ids or ())
    plan: list = []
    for record in records:
        if record.knowledge_id in seen:
            continue
        seen.add(record.knowledge_id)
        plan.append(record)
    return plan


def load_checkpoint_ids(r) -> set[str]:
    """Return the already-checkpointed ``knowledge_id``s (the idempotence keys)."""
    return set(r.hkeys(ks.CHECKPOINT_KEY))


def emit_records(r, records: list) -> tuple[int, int]:
    """Write each durable artifact then publish its pointer event; skip already-checkpointed ids.

    Returns ``(emitted, skipped)``. Ordering mirrors ``kb_produce.emit_records``: the artifact is
    written *before* the event lands (so the consumer can always read + verify the bytes the
    event hashes), then ``HSET`` into the checkpoint.
    """
    emitted = 0
    skipped = 0
    for record in records:
        if r.hget(ks.CHECKPOINT_KEY, record.knowledge_id) is not None:
            skipped += 1
            continue
        # The fixed producer contract (knowledge_ingestion): serialize to the per-record JSON
        # artifact, then emit a pointer-only event whose content_hash covers those exact bytes.
        from instrument.knowledge_ingestion import record_to_artifact, record_to_event

        artifact = record_to_artifact(record)
        KB_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        (KB_ARTIFACT_DIR / f"{record.knowledge_id}.json").write_bytes(artifact)
        ks.publish_event(r, record_to_event(record), source_type=record.source_type)
        r.hset(ks.CHECKPOINT_KEY, record.knowledge_id, record.indexed_at)
        emitted += 1
    return emitted, skipped


# ── Source table ────────────────────────────────────────────────

#: Each source: a key, a human label, and a derivation callable returning (records, notes).
_SOURCES = {
    "code": ("code", derive_code),
    "quality": ("report", derive_quality),
    "policy": ("policy", derive_policy),
}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Derive code/quality/policy records and emit pointer events to the KB stream"
    )
    parser.add_argument(
        "--source",
        default="all",
        choices=["code", "quality", "policy", "all"],
        help="which source to emit (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report the would-emit counts and samples, touching nothing",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="cap the number of records emitted across selected sources (0 = no cap)",
    )
    parser.add_argument(
        "--repository-id",
        default="agentic-dynamics",
        help="repository identity folded into entity_id",
    )
    parser.add_argument(
        "--revision",
        default=None,
        help="git HEAD sha stamped as source_revision (default: rev-parse HEAD)",
    )
    args = parser.parse_args(argv)

    revision = args.revision or git_head_sha()

    # Resolve the requested source keys (order is fixed and deterministic).
    source_keys = ["code", "quality", "policy"] if args.source == "all" else [args.source]

    # 1. Derive every requested source, capturing records + quality skip notes.
    derived: dict[str, tuple[list, list[str]]] = {}
    for key in source_keys:
        label, derive_fn = _SOURCES[key]
        if key == "quality":
            records, notes = derive_fn(args.repository_id, revision)
        else:
            records, notes = derive_fn(args.repository_id, revision), []
        derived[key] = (records, notes)

    # 2. Preview / emit. Dry-run reports the honest would-emit count (derived minus already
    #    checkpointed) per source; a downed Redis degrades to the raw derived count.
    known_ids: set[str] = set()
    if args.dry_run:
        try:
            known_ids = load_checkpoint_ids(ks.connect(host=REDIS_HOST, port=REDIS_PORT))
        except Exception:
            known_ids = set()

    # Apply the limit across the concatenated plan (source order preserved).
    all_records = [rec for key in source_keys for rec in derived[key][0]]
    plan = plan_emissions(all_records, limit=args.limit, known_ids=known_ids)

    for key in source_keys:
        label, _ = _SOURCES[key]
        records, notes = derived[key]
        log(f"{label}: derived {len(records)} record(s)")
        for note in notes:
            log(f"  {label}: {note}")

    if args.dry_run:
        per_source = {key: 0 for key in source_keys}
        for rec in plan:
            # Map each planned record back to its source by source_type.
            stype = rec.source_type
            per_source[stype] = per_source.get(stype, 0) + 1
        log(
            f"dry-run: would emit {len(plan)} record(s) "
            f"(revision={revision[:12]}, repository-id={args.repository_id!r}, "
            f"limit={args.limit or 'none'}) — by source_type: {per_source}"
        )
        for rec in plan[:SAMPLE_COUNT]:
            log(f"  {rec.knowledge_id[:12]}  [{rec.source_type}]  {rec.text[:80]}")
        return

    # 3. Emit — fail fast on connection (knowledge_stream.connect raises on a downed stream).
    # The producer is an authorized writer: satisfy publish_event's write guard (FINOPS_KB_WRITE)
    # for the whole run — this script exists solely to emit pointers.
    os.environ["FINOPS_KB_WRITE"] = "1"
    r = ks.connect(host=REDIS_HOST, port=REDIS_PORT)
    emitted, skipped = emit_records(r, plan)
    log(f"emitted={emitted} skipped={skipped} (already checkpointed) total={len(plan)}")


if __name__ == "__main__":
    main()
