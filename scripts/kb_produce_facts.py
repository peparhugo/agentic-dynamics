"""Batch producer for the fact plane — derive canonical facts and emit pointer events.

This is the *facts* producer (CAP I1, design §4.3 / §9): it runs a registered reducer over the
spec-lifecycle index and persists the resulting :class:`~agentic_dynamics.control.facts.CanonicalFact`
objects through the EXISTING knowledge pipe — ``build_fact_record`` → ``record_to_artifact`` →
``record_to_event`` → ``publish_event`` — onto ``kb:v1:changes`` (DB 2 on 6380). It is the sibling
of ``scripts/kb_produce_sources.py`` (which emits code/quality/policy/spec records) and shares its
idempotence + isolation contracts verbatim.

    python scripts/kb_produce_facts.py --reducer spec_status/v1 --dry-run
    python scripts/kb_produce_facts.py --reducer spec_status/v1 --limit 5   # smoke
    python scripts/kb_produce_facts.py --reducer spec_status/v1             # full emit

Like the ``spec`` source, a fact record can emit a ``supersede`` (rather than ``upsert``) event:
when ``registry_index.jsonl`` already holds a fact for the same ``fact_entity_id`` (the stable
slot ``<scope>/<subject>/<predicate>``) with a *different* value, the new record links its
predecessor via ``supersedes``, which is what lets ``scripts/generate_manifest.py`` derive
``lifecycle_state`` ``current`` vs ``superseded`` (design §9 I1's gate). Operation and ``reason``
are derived from the record (``fact_ingestion.fact_event``), never passed alongside it.

Idempotence (identical to ``kb_produce_sources.py``): ``knowledge_id`` is the idempotence key.
The producer checks the checkpoint hash (``CHECKPOINT_KEY`` on DB 2) and dedupes in-process; only
a never-seen ``knowledge_id`` is published, then checkpointed. The durable per-record artifact is
written to ``experiments/results/kb/<knowledge_id>.json`` BEFORE the pointer event lands.

Isolation (load-bearing): this producer touches only ``127.0.0.1:FINOPS_REDIS_PORT`` (default
6380) DB 2 — never 6379 (the story sandbox) nor DB 1 (the framework queue).
"""

import argparse
import os
import subprocess
from datetime import datetime
from pathlib import Path

# scripts/ → repo root → src, so the local package wins over any installed one (matches the
# bootstrap in worker.py / kb_worker.py / kb_produce.py).
try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401


from agentic_dynamics.control import fact_ingestion as fi  # noqa: E402
from agentic_dynamics.control.facts import EvidenceItem, ReducerInput  # noqa: E402
from agentic_dynamics.control.reducers import REDUCERS, get_reducer  # noqa: E402
from agentic_dynamics.core.paths import KB_ARTIFACT_DIR, REGISTRY_INDEX_PATH  # noqa: E402
from agentic_dynamics.knowledge import knowledge_stream as ks  # noqa: E402
from agentic_dynamics.knowledge import spec_ingestion as si  # noqa: E402
from agentic_dynamics.knowledge.record_factory import _now_iso  # noqa: E402

REDIS_HOST = os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6380"))

#: Repo root, anchored to the script location so flags may be omitted regardless of cwd.
REPO_ROOT = Path(__file__).resolve().parent.parent

#: How many sample records ``--dry-run`` prints (a preview, not the whole batch).
SAMPLE_COUNT = 5


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}][kb-produce-facts] {msg}", flush=True)


def git_head_sha() -> str:
    """Return the repo's HEAD sha (the injected ``revision``), or ``""`` when unavailable."""
    r = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    )
    return r.stdout.strip() if r.returncode == 0 else ""


# ── Derivation: run one registered reducer → facts → records ────


def derive_facts(
    reducer_version: str,
    repository_id: str,
    revision: str,
    now: str,
) -> list:
    """Run the named reducer over the spec index; return the persistable fact records.

    Reads the *generated* ``experiments/specs/index.json`` (via ``spec_ingestion.load_index_entries``)
    rather than the YAMLs directly — the index is the single place the spec corpus and the run
    ledgers have already been joined, and re-deriving that join here would give the fact plane a
    second, drift-prone opinion about what "done" means. Regenerate it first with
    ``python scripts/spec_status.py``; a missing index yields zero facts.

    The reducer is a pure function: its ``ReducerInput`` carries the resolved evidence (one
    :class:`~agentic_dynamics.control.facts.EvidenceItem` per index entry), an injected clock, and
    the injected revision — no I/O happens inside the reducer itself (design §4.1).
    """
    reducer_fn = get_reducer(reducer_version)
    if reducer_fn is None:
        raise SystemExit(f"unknown reducer {reducer_version!r} (registered: {sorted(REDUCERS)})")

    entries = si.load_index_entries(root=REPO_ROOT)
    inp = ReducerInput(
        scope_path=f"org:{repository_id}",
        scope_type="workload",
        scope_id="",  # the whole spec corpus — the reducer emits per-spec workload facts
        repository_id=repository_id,
        evidence=tuple(
            EvidenceItem(source_type="spec", evidence_id=f"spec:{e.name}", payload=e)
            for e in entries
        ),
        facts=(),
        now=now,
        source_revision=revision,
    )
    facts = reducer_fn(inp)
    return fi.derive_fact_records(facts, registry_path=REGISTRY_INDEX_PATH)


# ── Emission (identical logic to kb_produce_sources.py) ─────────


def plan_emissions(
    records: list, *, limit: int = 0, known_ids: set[str] | frozenset[str] | None = None
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


def build_event(record):
    """Build the pointer event for one fact record (operation + reason derived inside)."""
    return fi.fact_event(record)


def emit_records(r, records: list) -> tuple[int, int]:
    """Write each durable artifact then publish its pointer event; skip already-checkpointed ids.

    Returns ``(emitted, skipped)``. Ordering mirrors ``kb_produce_sources.emit_records``: the
    artifact is written before the event lands (so the consumer can always read + verify the
    bytes the event hashes), then checkpointed.
    """
    emitted = 0
    skipped = 0
    for record in records:
        if r.hget(ks.CHECKPOINT_KEY, record.knowledge_id) is not None:
            skipped += 1
            continue
        from agentic_dynamics.knowledge.knowledge_ingestion import record_to_artifact

        artifact = record_to_artifact(record)
        KB_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        (KB_ARTIFACT_DIR / f"{record.knowledge_id}.json").write_bytes(artifact)
        ks.publish_event(r, build_event(record), source_type=record.source_type)
        r.hset(ks.CHECKPOINT_KEY, record.knowledge_id, record.indexed_at)
        emitted += 1
    return emitted, skipped


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Derive canonical facts from a registered reducer and emit pointer events"
    )
    parser.add_argument(
        "--reducer",
        default="spec_status/v1",
        choices=tuple(REDUCERS),
        help="reducer version to run (default: spec_status/v1)",
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
        help="cap the number of records emitted (0 = no cap)",
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
    now = _now_iso()

    # 1. Derive fact records (run the reducer, then the registry-driven supersede decision).
    records = derive_facts(args.reducer, args.repository_id, revision, now)
    log(
        f"{args.reducer}: derived {len(records)} fact record(s) "
        f"(revision={revision[:12]}, repository-id={args.repository_id!r})"
    )

    # 2. Preview / emit. Dry-run reports the honest would-emit count (derived minus already
    #    checkpointed); a downed Redis degrades to the raw derived count.
    known_ids: set[str] = set()
    if args.dry_run:
        try:
            known_ids = load_checkpoint_ids(ks.connect(host=REDIS_HOST, port=REDIS_PORT))
        except Exception:
            known_ids = set()

    plan = plan_emissions(records, limit=args.limit, known_ids=known_ids)

    if args.dry_run:
        log(f"dry-run: would emit {len(plan)} fact record(s) (limit={args.limit or 'none'})")
        for record in plan[:SAMPLE_COUNT]:
            op = fi.fact_operation(record)
            log(f"  {record.knowledge_id[:12]}  [fact/{op}]  {record.logical_locator}")
        return

    # 3. Emit — fail fast on connection. The producer is an authorized writer: satisfy
    #    publish_event's write guard (FINOPS_KB_WRITE) for the whole run.
    os.environ["FINOPS_KB_WRITE"] = "1"
    r = ks.connect(host=REDIS_HOST, port=REDIS_PORT)
    emitted, skipped = emit_records(r, plan)
    log(f"emitted={emitted} skipped={skipped} (already checkpointed) total={len(plan)}")


if __name__ == "__main__":
    main()
