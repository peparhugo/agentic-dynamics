#!/usr/bin/env python3
"""Bounded DLQ triage for the KB stream (proposal §7 slice 3, D-12, §6).

``kb:v1:dead_letter`` (db2 / 6380) holds stream events that failed processing after
``MAX_RETRIES``. The D-12 slice-3 pass re-drives or tombstones them, **bounded**: each entry
is classified by whether its source artifact still exists (and its ``content_hash`` matches) —
a recoverable entry is re-published to the main stream (re-drive); an entry whose artifact is
gone is recorded as a tombstone (permanently dead, never retried). The disposition is written to
``experiments/results/kb/dlq_triage.json`` so the operator (and the slice-3 verification) can see
the exact re-drive vs tombstone split.

This is the KB stream's DLQ — the *job* queues' DLQ is ``scripts/fleet/dlq.py`` (a different
plane). This script is a one-shot triage, not a daemon; ``--dry-run`` characterizes + records the
disposition without mutating the stream.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import redis

# scripts/fleet/ -> repo root two parents up; put src/ on sys.path for the knowledge plane.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from agentic_dynamics.knowledge import knowledge_stream as ks  # noqa: E402

REDIS_HOST = os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6380"))
REDIS_DB = int(os.environ.get("FINOPS_KB_DB", "2"))

OUT_PATH = _REPO_ROOT / "experiments" / "results" / "kb" / "dlq_triage.json"

# The DLQ entry fields that belong to the POINTER event (re-published verbatim on re-drive);
# everything else (reason/source_entry_id/dead_lettered_at) is DLQ-local, dropped on re-drive.
_EVENT_FIELDS = (
    "schema_version", "knowledge_id", "entity_id", "source_uri", "source_revision",
    "content_hash", "occurred_at", "observed_at", "operation", "reason",
)


def _artifact_ok(fields: dict) -> tuple[bool, str]:
    """Return (recoverable, why) — an entry is recoverable iff its artifact exists AND hashes
    to its recorded ``content_hash`` (the same check ``process_entry`` runs before upsert)."""
    source_uri = fields.get("source_uri", "")
    path = source_uri
    if path.startswith("file://"):
        path = path[len("file://"):]
    try:
        artifact = Path(path).read_bytes()
    except OSError as exc:
        return False, f"artifact missing: {exc}"
    expected = fields.get("content_hash", "")
    if not expected:
        return False, "no content_hash recorded"
    digest = hashlib.sha256(artifact).hexdigest()
    if digest != expected:
        return False, f"content_hash mismatch ({digest[:12]} != {expected[:12]})"
    return True, ""


def _re_publish(r: redis.Redis, fields: dict) -> str:
    """Re-publish a recoverable DLQ entry to the main stream (the D-12 re-drive path)."""
    event = {k: fields[k] for k in _EVENT_FIELDS if k in fields}
    return r.xadd(ks.STREAM_KEY, event)


def triage(*, dry_run: bool, limit: int | None = None) -> dict:
    """Classify + (optionally) re-drive the DLQ; return the disposition summary."""
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
    r.ping()

    entries = r.xrange(ks.DEAD_LETTER_KEY, count=limit or None)
    disposition = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "dlq_stream": ks.DEAD_LETTER_KEY,
        "total": r.xlen(ks.DEAD_LETTER_KEY),
        "inspected": len(entries),
        "re_driven": 0,
        "tombstoned": 0,
        "by_reason": {},
        "dry_run": dry_run,
    }

    for entry_id, fields in entries:
        ok, why = _artifact_ok(fields)
        if ok:
            disposition["re_driven"] += 1
            if not dry_run:
                _re_publish(r, fields)
        else:
            disposition["tombstoned"] += 1
            # Bucket only the TOMBSTONE reasons (recoverable entries have no failure reason).
            bucket = why.split(":")[0]
            disposition["by_reason"][bucket] = disposition["by_reason"].get(bucket, 0) + 1

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(disposition, indent=2))
    return disposition


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bounded KB-stream DLQ triage (D-12, slice 3).")
    parser.add_argument("--dry-run", action="store_true",
                        help="characterize + record the disposition without re-driving")
    parser.add_argument("--limit", type=int, default=None,
                        help="bound the pass to the newest N DLQ entries")
    args = parser.parse_args(argv)

    disposition = triage(dry_run=args.dry_run, limit=args.limit)
    print(json.dumps(disposition, indent=2))
    print(f"disposition -> {OUT_PATH}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
