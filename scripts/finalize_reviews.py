"""finalize_reviews.py — Merge per-session review files into aggregate JSONs.

The review runner writes one file per session (review_{story_id}_S{n}.json)
plus review_{story_id}_story.json. This merges them into the aggregate
review_{story_id}.json that build_data.py and the website consume.

Idempotent — safe to run anytime, including mid-batch.

Usage:
  python3 scripts/finalize_reviews.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401


REVIEWS_DIR = ROOT / "experiments" / "results" / "reviews"
MODEL = "deepseek/deepseek-v4-flash"


def _finalize_story(story_id: str) -> bool:
    """Merge per-session files for one story. Returns True if written."""
    story_review = None
    commit_reviews = []

    # Story-level review
    story_path = REVIEWS_DIR / f"review_{story_id}_story.json"
    if story_path.exists():
        try:
            story_review = json.loads(story_path.read_text())
        except (json.JSONDecodeError, OSError):
            story_review = None

    # Per-session commit reviews
    for f in sorted(REVIEWS_DIR.glob(f"review_{story_id}_S*.json")):
        try:
            cr = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        cr["session_number"] = cr.get("session_number", 0)
        commit_reviews.append(cr)

    if not commit_reviews and not story_review:
        return False

    commit_reviews.sort(key=lambda c: c.get("session_number", 0))

    # Derive story_name from any commit review or story review
    story_name = ""
    if commit_reviews:
        story_name = commit_reviews[0].get("story_name", "")
    if not story_name and story_review:
        story_name = story_review.get("story_name", "")

    data = {
        "story_name": story_name,
        "story_id": story_id,
        "model": MODEL,
        "commit_reviews": commit_reviews,
        "story_review": story_review,
    }
    (REVIEWS_DIR / f"review_{story_id}.json").write_text(json.dumps(data, indent=2))

    # canonical-state round 2, plan step 12: write-time registration (Delta 1) — inline
    # after the merged review write succeeds. Gated on FINOPS_KB_WRITE (opt-in, same
    # convention as every other KB writer) and deliberately left unwrapped (no
    # try/except) once the flag is set — see story.py:save_story_result's docstring for
    # why this class of call site intentionally lets a downed knowledge stream raise.
    if os.environ.get("FINOPS_KB_WRITE") == "1":
        from agentic_dynamics.knowledge.knowledge_ingestion import REPOSITORY_ID
        from agentic_dynamics.knowledge.knowledge_stream import register_records
        from agentic_dynamics.knowledge.review_ingestion import derive_review_records

        register_records(
            derive_review_records(data, repository_id=REPOSITORY_ID),
            fail_loud=True,
        )

    return True


def main() -> None:
    story_ids = set()
    for f in REVIEWS_DIR.glob("review_*_S*.json"):
        m = re.match(r"review_(.+)_S\d+\.json", f.name)
        if m:
            story_ids.add(m.group(1))
    for f in REVIEWS_DIR.glob("review_*_story.json"):
        m = re.match(r"review_(.+)_story\.json", f.name)
        if m:
            story_ids.add(m.group(1))

    written = 0
    for sid in sorted(story_ids):
        if _finalize_story(sid):
            written += 1

    print(f"Finalized {written} story aggregates from per-session files")


if __name__ == "__main__":
    main()
