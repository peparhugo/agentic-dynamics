"""Doc-lifecycle lint (consolidation Stage 0, phase `lifecycle`).

Enforces critique rec 4 (``docs/review/semantic_monolith_review.md``): every
top-level markdown document carries a structured lifecycle status, and the
``docs/archive/`` / ``docs/designs/`` trees carry the specific statuses the
migration table (``docs/consolidation/design.md`` §3) requires.

The status vocabulary (rec 4) is::

    proposed | accepted | implementing | implemented | superseded | abandoned

with optional ``supersedes:``, ``superseded_by:`` and ``implemented_by:`` fields.
The convention is a YAML front-matter block at the very top of each document::

    ---
    status: accepted
    superseded_by: ARCHITECTURE.md
    ---

This test walks ``docs/**`` + root ``*.md`` and asserts every file carries a
``status`` field, and that the archive/designs trees are correctly classified.
It is deliberately cheap and has no external dependencies.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

STATUS_VOCABULARY = frozenset({
    "proposed", "accepted", "implementing", "implemented", "superseded", "abandoned",
})


def _front_matter(path: Path) -> dict:
    """Parse the YAML front-matter block, if any, from a markdown file.

    A front-matter block is the first two ``---`` lines: everything between
    them is key-value (``key: value``) lines. Returns an empty dict when the
    file does not start with ``---``.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        return {}
    meta: dict[str, str] = {}
    for line in lines[1:]:
        if line == "---":
            break
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return meta


def _markdown_files() -> list[Path]:
    """All root ``*.md`` files plus every ``*.md`` under ``docs/`` (recursive)."""
    files = sorted(ROOT.glob("*.md"))
    files += sorted((ROOT / "docs").rglob("*.md"))
    return files


def test_every_document_has_status_field():
    """Every root + docs markdown file carries a status field in the vocabulary."""
    missing = []
    for path in _markdown_files():
        meta = _front_matter(path)
        status = meta.get("status")
        if status is None:
            missing.append(f"{path.relative_to(ROOT)}: missing status field")
        elif status not in STATUS_VOCABULARY:
            missing.append(f"{path.relative_to(ROOT)}: unknown status {status!r}")
    assert not missing, "documents lacking a valid status field:\n" + "\n".join(missing)


def test_archive_entries_are_superseded():
    """Every ``docs/archive/`` entry is ``status: superseded`` with a successor."""
    problems = []
    for path in sorted((ROOT / "docs" / "archive").glob("*.md")):
        meta = _front_matter(path)
        if meta.get("status") != "superseded":
            problems.append(f"{path.relative_to(ROOT)}: status={meta.get('status')!r}, want superseded")
        if not meta.get("superseded_by"):
            problems.append(f"{path.relative_to(ROOT)}: missing superseded_by")
    assert not problems, "archive entries must be superseded + superseded_by:\n" + "\n".join(problems)


def test_current_designs_are_accepted():
    """Every ``docs/designs/current/`` entry is ``status: accepted``."""
    problems = []
    for path in sorted((ROOT / "docs" / "designs" / "current").glob("*.md")):
        meta = _front_matter(path)
        if meta.get("status") != "accepted":
            problems.append(f"{path.relative_to(ROOT)}: status={meta.get('status')!r}, want accepted")
    assert not problems, "current designs must be accepted:\n" + "\n".join(problems)


def test_implemented_designs_name_their_branch():
    """Every ``docs/designs/implemented/`` entry is implemented + implemented_by."""
    problems = []
    for path in sorted((ROOT / "docs" / "designs" / "implemented").glob("*.md")):
        meta = _front_matter(path)
        if meta.get("status") != "implemented":
            problems.append(f"{path.relative_to(ROOT)}: status={meta.get('status')!r}, want implemented")
        if not meta.get("implemented_by"):
            problems.append(f"{path.relative_to(ROOT)}: missing implemented_by")
    assert not problems, "implemented designs must be implemented + implemented_by:\n" + "\n".join(problems)


def test_no_blueprint_at_root():
    """No BLUEPRINT*.md may remain at the repo root (they moved to docs/archive/)."""
    blueprints = sorted(ROOT.glob("BLUEPRINT*.md"))
    assert not blueprints, f"BLUEPRINT*.md still at root: {[p.name for p in blueprints]}"
