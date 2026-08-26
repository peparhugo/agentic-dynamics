"""Batch producer for the runtime-RAG knowledge base — derive findings and emit pointers.

This is the *producer* side of the knowledge pipeline: it reads the measured results
summary, derives one measured-finding ``KnowledgeRecord`` per valid cell (via
``knowledge_ingestion.derive_records``), and appends a pointer-only ``KnowledgeEvent`` to the
Redis change stream (via ``knowledge_stream.publish_event``). It is structurally parallel to
``scripts/kb_worker.py`` (the consumer), which reads those pointers back off the stream.

    python scripts/kb_produce.py --dry-run
    python scripts/kb_produce.py --limit 50
    python scripts/kb_produce.py --results experiments/results/_results_summary.json

Idempotence contract: ``knowledge_id`` is the idempotence key. Before emitting, the producer
checks the checkpoint hash (``CHECKPOINT_KEY`` on DB 2) with ``HGET`` and also dedupes
in-process; only a ``knowledge_id`` that has never been seen is published, then ``HSET`` into
the checkpoint. Re-running the producer emits nothing new.

Isolation (load-bearing): the producer touches **only** ``127.0.0.1:FINOPS_REDIS_PORT``
(default **6380**) **DB 2** — the knowledge-stream DB reserved by ``knowledge_stream``. It
never touches 6379 (the story-agent test sandbox that ``flushall()``s) nor DB 1 (the
framework queue). A connection failure raises immediately (matching ``knowledge_stream.connect``)
rather than silently dropping or retrying forever — the producer is a bounded one-shot, not a
long-running service.
"""

import argparse
import os
from datetime import datetime
from pathlib import Path

# scripts/ → repo root → src, so the local instrument package wins over any installed one
# (matches the bootstrap in worker.py / kb_worker.py).
try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401


from agentic_dynamics.control.signal_store import load_results  # noqa: E402
from agentic_dynamics.core.paths import KB_ARTIFACT_DIR  # noqa: E402
from agentic_dynamics.knowledge import knowledge_ingestion as ki  # noqa: E402
from agentic_dynamics.knowledge import knowledge_stream as ks  # noqa: E402

REDIS_HOST = os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6380"))

#: Default results path, anchored to the repo root so ``--results`` may be omitted regardless
#: of the caller's working directory (mirrors ``signal_store._DEFAULT_RESULTS_PATH``).
DEFAULT_RESULTS_PATH = (
    Path(__file__).resolve().parent.parent / "experiments" / "results" / "_results_summary.json"
)

# How many sample records ``--dry-run`` prints (a preview, not the whole batch).
SAMPLE_COUNT = 5

# Durable per-record artifact directory, anchored to the repo root so the producer writes to
# the same path the consumer's ``read_artifact`` resolves (``file://experiments/results/kb/…``).
# Sourced from ``instrument.paths`` (canonical-state R6) — the single owner of the path.


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}][kb-produce] {msg}", flush=True)


def plan_emissions(
    records: list[ki.KnowledgeRecord],
    *,
    limit: int = 0,
    known_ids: set[str] | frozenset[str] | None = None,
) -> list[ki.KnowledgeRecord]:
    """Cap by ``limit`` then drop already-emitted ids (pure, no Redis).

    ``limit`` <= 0 means "no cap". ``known_ids`` seeds the in-process dedupe with ids already
    emitted this run or in a prior run; every record's ``knowledge_id`` is the idempotence key,
    so the first occurrence wins and later duplicates are dropped. The function is pure so the
    dry-run count and the live emit order are computed by the *same* code path.
    """
    if limit and limit > 0:
        records = records[:limit]
    seen: set[str] = set(known_ids or ())
    plan: list[ki.KnowledgeRecord] = []
    for record in records:
        if record.knowledge_id in seen:
            continue
        seen.add(record.knowledge_id)
        plan.append(record)
    return plan


def load_checkpoint_ids(r) -> set[str]:
    """Return the set of already-checkpointed ``knowledge_id``s (the idempotence keys).

    The checkpoint hash's field names ARE the ``knowledge_id``s the producer has already
    emitted (every emit does ``HSET knowledge_id -> indexed_at``). Reading them lets the
    dry-run preview report the *honest* would-emit count — derived minus already-seen —
    instead of the raw derived count, so a second ``--dry-run`` after a live run reports 0.
    """
    return set(r.hkeys(ks.CHECKPOINT_KEY))


def emit_records(r, records: list[ki.KnowledgeRecord]) -> tuple[int, int]:
    """Publish one pointer event per record, skipping ids already checkpointed.

    Returns ``(emitted, skipped)``. For each record: skip when the checkpoint hash already
    carries the ``knowledge_id`` (``HGET``), else write the durable per-record artifact to
    ``experiments/results/kb/<knowledge_id>.json`` **before** publishing the pointer event,
    then ``HSET`` the checkpoint — the destination-confirm-then-ack ordering mirrors the
    consumer's, so a crash between publish and checkpoint leaves the stream the single source
    of truth. Writing the artifact first guarantees the consumer can read + verify the bytes
    the event's ``content_hash`` covers as soon as the pointer lands.
    """
    emitted = 0
    skipped = 0
    for record in records:
        if r.hget(ks.CHECKPOINT_KEY, record.knowledge_id) is not None:
            skipped += 1
            continue
        artifact = ki.record_to_artifact(record)
        KB_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        (KB_ARTIFACT_DIR / f"{record.knowledge_id}.json").write_bytes(artifact)
        ks.publish_event(r, ki.record_to_event(record), source_type=record.source_type)
        r.hset(ks.CHECKPOINT_KEY, record.knowledge_id, record.indexed_at)
        emitted += 1
    return emitted, skipped


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Derive measured findings and emit pointer events to the knowledge stream"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report the would-emit count and a few sample records, touching nothing",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="cap the number of records emitted (0 = no cap)",
    )
    parser.add_argument(
        "--results",
        default=str(DEFAULT_RESULTS_PATH),
        help=f"path to a _results_summary.json (default: {DEFAULT_RESULTS_PATH})",
    )
    parser.add_argument(
        "--repository-id",
        default=ki.REPOSITORY_ID,
        help=f"repository identity folded into entity_id (default: {ki.REPOSITORY_ID!r})",
    )
    args = parser.parse_args(argv)

    # 1. Derive — load_results feeds the same entries the signal store and evidence cards
    #    describe, so each finding describes the *same* measured row.
    entries = load_results(Path(args.results))
    records = ki.derive_records(entries, repository_id=args.repository_id)

    # 2. Preview — dry-run reports the honest would-emit count: derived minus already
    #    checkpointed. The checkpoint read is best-effort so a preview never *requires* the
    #    stream — a downed Redis degrades to the raw derived count rather than failing.
    known_ids: set[str] = set()
    if args.dry_run:
        try:
            known_ids = load_checkpoint_ids(ks.connect(host=REDIS_HOST, port=REDIS_PORT))
        except Exception:
            known_ids = set()

    plan = plan_emissions(records, limit=args.limit, known_ids=known_ids)

    if args.dry_run:
        log(
            f"dry-run: would emit {len(plan)} record(s) "
            f"(from {len(entries)} entries, {len(known_ids)} already checkpointed, "
            f"repository-id={args.repository_id!r}, limit={args.limit or 'none'})"
        )
        for record in plan[:SAMPLE_COUNT]:
            log(f"  {record.knowledge_id[:12]}  {record.logical_locator:16}  {record.text}")
        return

    # 3. Emit — fail fast on connection (knowledge_stream.connect raises on a downed stream);
    #    the checkpoint + in-process dedupe make this idempotent.
    # The producer is an authorized writer: satisfy publish_event's write guard (FINOPS_KB_WRITE)
    # for the whole run — this script exists solely to emit pointers.
    os.environ["FINOPS_KB_WRITE"] = "1"
    r = ks.connect(host=REDIS_HOST, port=REDIS_PORT)
    emitted, skipped = emit_records(r, plan)
    log(f"emitted={emitted} skipped={skipped} (already checkpointed) total={len(plan)}")


if __name__ == "__main__":
    main()
