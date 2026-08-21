"""ONE-TIME migration — tombstone the ten payload-less story rows.

``docs/review/public_truth_review.md`` P1: the ten cost-0 Claude stubs (dropped in commit
994454f79 — "Complete the re-run: drop 13 un-runnable Claude stubs") have no measurement
payload, yet their registry rows were left ``lifecycle_state=current`` and were only papered
over by broad ``(table, locator)`` waivers. A canonical tombstone (``lifecycle_state=
tombstoned`` + a non-empty reason) is the honest state: the cell never ran and has no
usable measurement, so it must be *retracted*, not silently exempted forever.

Appends one tombstone line per row to the append-only ``experiments/results/
registry_index.jsonl`` — the exact shape ``scripts/kb_worker.py``'s kb-registry-v1 consumer
writes for a ``delete`` event (see that handler's ``line = {…}``). ``scripts/
generate_manifest.py`` then compacts each entity's history down to ``tombstoned`` (its
``_compact_registry_index`` already treats a tombstone as terminal for an entity).

Idempotent: a row whose entity already carries a tombstone line is skipped, so a re-run
after the first pass appends nothing. Never invoked by a cron or steady-state code path.

Run once, by an operator::

    python scripts/archive/retract_payloadless_stories.py [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# scripts/archive/ → repo root → src, so the local instrument package wins over any
# installed one (this script lives one level deeper than scripts/, so it cannot `import
# _bootstrap` the way the top-level scripts/ do — it inserts src/ itself).
_SRC = Path(__file__).resolve().parent.parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from agentic_dynamics.core.paths import REGISTRY_INDEX_PATH  # noqa: E402
from agentic_dynamics.knowledge.knowledge import (  # noqa: E402
    compute_content_hash,
    compute_knowledge_id,
)

#: The ten invalid rows — ``(entity_id, logical_locator)`` — copied verbatim from the
#: canonical registry (they are the exact rows the pre-p4 ``waivers/unresolved_payloads.json``
#: covered). Hardcoded because this is a one-time retraction of a specific, audited set.
RETRACTED_ROWS = (
    ("4fcea64d301b7094e2ed6f48c9e6bb9858b2437201dbd9e40413fae107ffd670", "4e7abddc43f1"),
    ("57b397cf8a61996066ded79743f15f2d56b8ee7b3797bddb1fc7ab73aa8219b0", "4f80a9ea38aa"),
    ("5a1734eacc30df76c52c1871d553db125f49a7d552b98f74ce97ba13bab75335", "5196e779c1ca"),
    ("0db496afe0bb29fca6090a43385a3e98e83209c387205fea3cb2144d96bb6f82", "5b87673f0d7a"),
    ("1685dafdadfc5b8c577eac34c2497976c9bfff8e109d495276faecc6330b43be", "5be412dd5b87"),
    ("35230d9da6d444f48dd963ef8306bd5532298022c07fc977092f22e02c14130f", "5d7640124ed4"),
    ("37679fe003cab12e4e9a4ded2bae75a218577770ae87d7558748f2a7445a581e", "6bc71fa28f35"),
    ("61e6e3cc61958913e77ba73961096aa4d3128d566019111dc2047370e2975010", "7005f70e2fd6"),
    ("647f3536a7bb16e17da1aa818f9389172fe762e70086be5fce35af4061d89193", "890584be7186"),
    ("aa5b8de3eb51f9c8bddb4ae2d7b0dc874588d29898b5b078d3e363d197cbb408", "98507441e613"),
)

#: The retraction reason attached to every tombstone (public-truth review P1).
RETRACTION_REASON = (
    "no usable measurement payload: cost-0 Claude stub dropped in commit 994454f79 "
    "('Complete the re-run: drop 13 un-runnable Claude stubs'); the claude CLI was "
    "unavailable on this host, so the cell never ran and the story file was deleted"
)

#: The ``extractor_version`` folded into each tombstone's ``knowledge_id`` — a stable marker
#: for "this is a retraction event", distinct from any payload-derived version.
RETRACTION_EXTRACTOR = "retraction/v1"


def _already_tombstoned(existing: list[dict], entity_id: str) -> bool:
    """True when the index already carries a tombstone line for ``entity_id``."""
    return any(
        r.get("entity_id") == entity_id and r.get("lifecycle_state") == "tombstoned"
        for r in existing
    )


def _tombstone_line(entity_id: str, locator: str, *, now: str) -> dict:
    """Build one tombstone registry-index line (the kb_worker ``delete`` shape).

    ``knowledge_id`` is a fresh, deterministic id — the tombstone is its own immutable
    record (a delete event), never a rewrite of the original "current" registration line.
    """
    reason_hash = compute_content_hash(RETRACTION_REASON)
    knowledge_id = compute_knowledge_id(entity_id, "retraction", reason_hash, RETRACTION_EXTRACTOR)
    return {
        "knowledge_id": knowledge_id,
        "entity_id": entity_id,
        "source_type": "story",
        "logical_locator": locator,
        "source_uri": f"story:{locator}",
        "lifecycle_state": "tombstoned",
        "observed_at": now,
        "indexed_at": now,
        "supersedes": None,
        "causes": None,
        "reason": RETRACTION_REASON,
    }


def _load_existing_lines() -> list[dict]:
    """Read every currently-durable registry-index line (missing file → [])."""
    if not REGISTRY_INDEX_PATH.exists():
        return []
    lines: list[dict] = []
    for line in REGISTRY_INDEX_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            lines.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return lines


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="preview, touch nothing")
    args = parser.parse_args(argv)

    existing = _load_existing_lines()
    now = datetime.now(timezone.utc).isoformat()

    new_lines: list[dict] = []
    skipped = 0
    for entity_id, locator in RETRACTED_ROWS:
        if _already_tombstoned(existing, entity_id):
            skipped += 1
            continue
        new_lines.append(_tombstone_line(entity_id, locator, now=now))

    print(f"retract-payloadless-stories: {len(new_lines)} to append, {skipped} already tombstoned")
    for line in new_lines:
        print(
            f"  tombstone {line['logical_locator']}  entity={line['entity_id'][:12]}… "
            f"kid={line['knowledge_id'][:12]}…"
        )

    if args.dry_run:
        return

    if not new_lines:
        return
    with open(REGISTRY_INDEX_PATH, "a", encoding="utf-8") as f:
        for line in new_lines:
            f.write(json.dumps(line) + "\n")
    print(f"appended {len(new_lines)} tombstone line(s) to {REGISTRY_INDEX_PATH}")


if __name__ == "__main__":
    main()
