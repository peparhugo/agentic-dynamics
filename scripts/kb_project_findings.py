"""Deterministic finding-layer leg projection (kb_finding_layer k6 — the witness).

The finding layer's durable artifacts (``experiments/results/kb/<id>.json``,
``source_type == "finding"``) are the RECORD — but a record is only retrievable once it
reaches a leg the retrieval pipeline reads (the dense Chroma ``knowledge_chunks_v1``
collection and the lexical Neo4j ``Knowledge`` nodes). Those legs are a SEPARATE projection,
and in the deployed state they can silently lag or miss a producer's checkout entirely:
``kb-chroma-v1`` has never consumed the change stream, and the ``kb-neo4j-v1`` /
``kb-registry-v1`` consumers run from a corpus overlay that does not see every checkout's
durable artifacts. Measured consequence at k6: the k2 backfill's 164 wave findings existed as
durable artifacts + registry rows but ZERO of them were retrievable — a findings query
returned flat code, the 'flat, not rich' verdict. This script closes that gap
deterministically, with NO LLM and rerun-safe idempotent upserts:

* it scans a checkout's ``kb/`` directory for ``source_type == "finding"`` artifacts,
* rebuilds each full :class:`KnowledgeRecord` from the durable bytes (the artifact blanks
  only the derived ids + volatile timestamps; ``knowledge_id`` is the filename and
  ``content_hash`` re-derives as sha256 of the artifact, exactly as the consumers verify),
* and projects each record into the requested legs using the SAME handler bodies the change
  stream's consumers run (``scripts/kb_worker.py``'s ``build_handler``), keyed by
  ``knowledge_id`` — a Chroma upsert / a Neo4j ``MERGE`` / an append-only registry row are
  all idempotent, so a re-run is a no-op.

Scope: finding artifacts only (the distilled layer). ``--only <id-prefix>`` targets a single
record (e.g. a freshly emitted witness finding); ``--extractor`` filters by
``extractor_version`` (e.g. ``wave-backfill/v1`` for the k2 layer). The registry leg skips
ids already present in the checkout's ``registry_index.jsonl`` (k2 already materialized rows
at emit time — appending consumer rows would only duplicate). A dry-run writes nothing.

Invocation:
    python3 scripts/kb_project_findings.py [--leg chroma|neo4j|registry|all] [--dry-run]
        [--extractor wave-backfill/v1] [--only <id-prefix>] [--limit N]

This is the "no live-consumer dependency" materialization pattern the emit-side scripts
already use (kb_produce_campaign_evidence materializes its registry row at emit time); here
the legs themselves are materialized because the live consumers are pointed at a different
corpus root.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from agentic_dynamics.knowledge.knowledge import KnowledgeRecord  # noqa: E402

LEGS = ("chroma", "neo4j", "registry")
#: Leg -> kb_worker consumer-group name: the projection runs the group's REAL handler body.
LEG_GROUP = {
    "chroma": "kb-chroma-v1",
    "neo4j": "kb-neo4j-v1",
    "registry": "kb-registry-v1",
}
FINDING_SOURCE_TYPE = "finding"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_kb_worker():
    """Load ``scripts/kb_worker.py`` as a module (scripts/ is not an import package).

    The projection must run the SAME handler bodies the stream consumers run — importing
    ``build_handler`` from the real worker keeps the leg writes honest (no duplicated
    projection logic to drift).
    """
    path = REPO / "scripts" / "kb_worker.py"
    spec = importlib.util.spec_from_file_location("kb_worker", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def discover_finding_artifacts(root: Path) -> list[Path]:
    """All ``kb/*.json`` artifacts in ``root`` whose stable content says ``finding``."""
    kb_dir = Path(root) / "experiments" / "results" / "kb"
    if not kb_dir.is_dir():
        return []
    out: list[Path] = []
    for path in sorted(kb_dir.glob("*.json")):
        try:
            data = json.loads(path.read_bytes())
        except Exception:  # noqa: BLE001 — a corrupt artifact is skipped, never fatal
            continue
        if str(data.get("source_type") or "").strip() == FINDING_SOURCE_TYPE:
            out.append(path)
    return out


def load_record(path: Path) -> KnowledgeRecord:
    """Rebuild the full :class:`KnowledgeRecord` from a durable artifact's bytes.

    ``record_to_artifact`` blanks the two derived identities (``knowledge_id``,
    ``content_hash``) and the three volatile timestamps; every STABLE field survives. The
    consumer-side reconstruction (``knowledge_ingestion.extract_record``) reattaches the ids
    from the pointer event; here the artifact IS the pointer's source, so ``knowledge_id`` is
    the filename and ``content_hash`` re-derives as sha256 of the exact artifact bytes the
    event would cover.
    """
    raw = path.read_bytes()
    record = KnowledgeRecord.from_dict(json.loads(raw))
    now = _now_iso()
    return replace(
        record,
        knowledge_id=path.stem,
        content_hash=_sha256_bytes(raw),
        valid_from=record.valid_from or now,
        observed_at=record.observed_at or now,
        indexed_at=now,
    )


def select_records(
    root: Path,
    *,
    extractors: set[str] | None = None,
    only: set[str] | None = None,
    limit: int = 0,
) -> list[KnowledgeRecord]:
    """Discover + load the finding records, filtered by extractor and/or id prefix."""
    records: list[KnowledgeRecord] = []
    for path in discover_finding_artifacts(root):
        if only and not any(path.stem.startswith(p) for p in only):
            continue
        record = load_record(path)
        if extractors and (record.extractor_version or "") not in extractors:
            continue
        records.append(record)
        if limit and len(records) >= limit:
            break
    return records


def _load_existing_registry_ids(root: Path) -> set[str]:
    reg = Path(root) / "experiments" / "results" / "registry_index.jsonl"
    ids: set[str] = set()
    if not reg.exists():
        return ids
    with reg.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            kid = row.get("knowledge_id")
            if kid:
                ids.add(kid)
    return ids


def project(
    records: list[KnowledgeRecord],
    *,
    legs: tuple[str, ...],
    root: Path,
    handler_factory=None,
) -> dict[str, int]:
    """Project ``records`` into the requested legs via the kb_worker handler bodies.

    Returns ``{leg: projected_count}``. A leg failure on one record is counted and logged,
    never fatal — a partial projection is better than none, and the idempotent upserts make
    the re-run the repair.
    """
    if handler_factory is None:
        handler_factory = _load_kb_worker().build_handler
    counts: dict[str, int] = {leg: 0 for leg in legs}
    errors: dict[str, int] = {leg: 0 for leg in legs}

    if "registry" in legs:
        existing = _load_existing_registry_ids(root)

    for record in records:
        for leg in legs:
            try:
                group = LEG_GROUP[leg]
                if leg == "registry":
                    if record.knowledge_id in existing:
                        continue  # already registered (emit-time row) — a re-run is a no-op
                    handler = handler_factory(group, None)
                    handler(record, operation="upsert", reason="")
                    existing.add(record.knowledge_id)
                else:
                    handler = handler_factory(group, None)
                    handler(record)
                counts[leg] += 1
            except Exception as exc:  # noqa: BLE001 — one bad record never stops the batch
                errors[leg] += 1
                print(f"  [warn] {leg} projection failed for {record.knowledge_id[:12]}: {exc}")
    for leg in legs:
        if errors[leg]:
            print(f"  {leg}: {counts[leg]} projected, {errors[leg]} failed")
    return counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--root", type=Path, default=REPO,
        help="checkout whose experiments/results/kb to scan (default: this checkout)",
    )
    ap.add_argument("--leg", action="append", default=[], choices=list(LEGS) + ["all"])
    ap.add_argument(
        "--extractor", default="",
        help="comma-separated extractor_version filter (default: all finding artifacts)",
    )
    ap.add_argument("--only", default="", help="comma-separated knowledge_id prefixes")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    legs_raw = [leg for leg in args.leg] or ["all"]
    legs_list: list[str] = []
    for leg in legs_raw:
        if leg == "all":
            legs_list.extend(LEGS)
        else:
            legs_list.append(leg)
    legs: tuple[str, ...] = tuple(legs_list)

    extractors = {e.strip() for e in args.extractor.split(",") if e.strip()} or None
    only = {o.strip() for o in args.only.split(",") if o.strip()} or None

    records = select_records(
        args.root, extractors=extractors, only=only, limit=args.limit
    )
    if not records:
        print("no finding artifacts matched")
        return 0

    if args.dry_run:
        for record in records:
            print(
                f"  [dry] {record.knowledge_id[:12]}  extractor={record.extractor_version}  "
                f"scope={record.repository_id}  {record.text.split(' :: ')[0][:110]}"
            )
        print(f"dry-run: {len(records)} finding record(s) -> legs {legs}")
        return 0

    counts = project(records, legs=legs, root=args.root)
    print(f"projected legs={dict(counts)} records={len(records)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
