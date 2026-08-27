"""Repository-hygiene guards (the missing CI gates, as guard tests).

Three deterministic guards, all local (git + filesystem, no external services):

1. No merge-conflict markers may remain in tracked files. The detector uses
   the precise marker shape (``<<<<<<< <ref>``, ``=======``, ``>>>>>>> <ref>``
   at line start) so ASCII-art table borders like ``=====...=====`` (present in
   ``tests/test_stale_path_guard.py``'s docstring) are not false positives.
   ``experiments/results/**`` and ``docs/archive/**`` are excluded — they are
   versioned experiment artifacts / frozen history where marker-like text is
   legitimate, and re-running the grep there is pure noise.
2. No tracked junk: ``__pycache__/``, ``*.pyc``, ``firebase-debug.log``, and no
   zero-byte files at the repo root (the zero-byte allowlist is empty — nothing
   legitimate lives there today).
3. The README "By the Numbers" table is reconciled against the canonical
   ``apps/website/data.js`` ``public_statistics`` block — numbers are derived
   from ``data.js``, never hardcoded, so the guard stays alive as the corpus
   grows. Both the table cells and the explanatory note must agree with it.
"""

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: git grep pathspec excludes — versioned experiment artifacts + frozen archive
#: history are exempt from the conflict-marker scan.
GIT_GREP_EXCLUDES = (
    ":!experiments/results/**",
    ":!docs/archive/**",
)

#: Exact conflict-marker shapes (git writes exactly 7 chars + optional ref).
#: Longer ``=====`` runs (ASCII table borders) are not markers.
CONFLICT_MARKER_RE = re.compile(r"^(<<<<<<< |>>>>>>> |=======$)")

#: The README "By the Numbers" rows whose numbers must equal data.js.
README_STAT_ROWS = (
    "Story sessions",
    "Game reports",
    "Model variants",
    "Experiment configs",
    "Experiment + workflow specs",
    "Perturbation operators",
    "Lab books",
    "Story-corpus measured spend",
)


def _git(args, check=True):
    """Run a git command in the repo root; return the subprocess result."""
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=check
    )


def _numbers(cell: str) -> list[float]:
    """Every number in a table cell, normalized (``1,067`` -> ``1067.0``)."""
    return [float(n.replace(",", "")) for n in re.findall(r"\d[\d,]*\.?\d*", cell)]


def _public_statistics() -> dict:
    """Parse the ``public_statistics`` object out of the data.js JS literal.

    ``data.js`` is ``window.DYNAMICS_DATA = { ... };`` — a JS object literal,
    not JSON. Brace-match the ``public_statistics`` value, strip trailing
    commas, then parse with :mod:`json`.
    """
    text = (ROOT / "apps" / "website" / "data.js").read_text(encoding="utf-8")
    start = text.index('"public_statistics"')
    brace = text.index("{", start)
    depth = 0
    for i in range(brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    literal = re.sub(r",\s*([}\]])", r"\1", text[brace:end])
    return json.loads(literal)


def _readme_by_the_numbers() -> dict[str, str]:
    """``metric -> value-cell`` for every data row of the 'By the Numbers' table."""
    rows = {}
    in_table = False
    for line in (ROOT / "README.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("## By the Numbers"):
            in_table = True
            continue
        if not in_table:
            continue
        if line.startswith("## "):
            break
        if not line.startswith("| "):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 2 and not cells[0].startswith("-"):
            rows[cells[0]] = cells[1]
    return rows


def test_no_conflict_markers_in_tracked_files():
    """No git merge-conflict markers in tracked files (outside the exclusions)."""
    result = _git(
        ["grep", "-nE", CONFLICT_MARKER_RE.pattern, "--", ".", *GIT_GREP_EXCLUDES],
        check=False,
    )
    if result.returncode == 1:
        return  # no matches
    assert result.returncode == 0, result.stderr
    hits = result.stdout.splitlines()
    assert not hits, "conflict markers in tracked files:\n" + "\n".join(hits)


def test_no_tracked_junk():
    """No tracked ``__pycache__/``, ``*.pyc``, or ``firebase-debug.log``."""
    offenders = []
    for path in _git(["ls-files"]).stdout.splitlines():
        if "__pycache__/" in path or path.endswith(".pyc") or path == "firebase-debug.log":
            offenders.append(path)
    assert not offenders, "tracked junk (remove with `git rm`):\n" + "\n".join(offenders)


def test_no_zero_byte_files_at_repo_root():
    """No zero-byte tracked files at the repo root (allowlist: none)."""
    offenders = []
    for path in _git(["ls-files"]).stdout.splitlines():
        if "/" in path:
            continue  # not a root-level file
        p = ROOT / path
        if p.exists() and p.stat().st_size == 0:
            offenders.append(path)
    assert not offenders, "zero-byte tracked files at repo root:\n" + "\n".join(offenders)


def test_readme_by_the_numbers_matches_public_statistics():
    """Every README 'By the Numbers' value equals apps/website/data.js exactly."""
    stats = _public_statistics()
    rows = _readme_by_the_numbers()

    expected = {
        "Story sessions": [stats["story_sessions"], stats["db_sessions_total"]],
        "Game reports": [stats["game_reports"]],
        "Model variants": [stats["model_variants"], stats["providers"]],
        "Experiment configs": [stats["experiment_configs"]],
        "Experiment + workflow specs": [
            stats["experiment_specs"] + stats["workflow_specs"],
            stats["experiment_specs"],
            stats["workflow_specs"],
        ],
        "Perturbation operators": [stats["perturbation_operators"]],
        "Lab books": [
            stats["lab_books"],
            stats["lab_books_canonical"],
            stats["lab_books_quarantined"],
        ],
        "Story-corpus measured spend": [stats["measured_spend_usd"]],
    }

    problems = []
    for metric, wanted in expected.items():
        if metric not in rows:
            problems.append(f"missing row {metric!r} in the 'By the Numbers' table")
            continue
        got = _numbers(rows[metric])
        if got != wanted:
            problems.append(f"{metric!r}: README {got} != data.js {wanted}")
    assert not problems, "README 'By the Numbers' drifted from data.js public_statistics:\n" + (
        "\n".join(problems)
    )


def test_readme_note_does_not_contradict_table():
    """The explanatory note's DB session total matches the table, never a stale count."""
    stats = _public_statistics()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "3,370" not in readme, (
        "README explanatory note still cites the stale DB session total 3,370; "
        f"public_statistics.db_sessions_total is {stats['db_sessions_total']:,}"
    )
    assert f"{stats['db_sessions_total']:,}" in readme, (
        f"README no longer mentions the DB session total {stats['db_sessions_total']:,} "
        "reported by public_statistics"
    )
