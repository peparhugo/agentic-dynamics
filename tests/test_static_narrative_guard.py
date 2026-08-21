"""Static-narrative guard (public-truth closure P0).

``docs/review/public_truth_review.md`` P0: the site's *static* narrative still carries the
retired corpus figures — 156 stories / 772 sessions / $219.51 in page metadata, Open Graph
tags, headlines, prose, and footers — plus a stale "88.7% across 1572/1772 tests" claim and
``bad_seed`` presented as a live treatment arm. Client-side ``data.js`` replacement cannot
repair metadata, OG tags, snippets, or prose that carries no ``data-stat`` placeholder, so
the only fix is to sweep the static text to the canonical ``public_statistics`` figures and
to describe retired treatment arms historically (or not at all).

This module makes the correction permanent. It scans every ``apps/website/*.html`` for the
retired figure set and the retired live-treatment term, and fails on any occurrence outside
the narrow allowlist below. The allowlist has exactly two legitimate shapes:

* **Historical framing** — a sentence that quotes a retired figure to explain a past drift
  (not to report a current number).
* **Coincidental digit match** — a number that equals a retired figure but denotes something
  else entirely (an SVG coordinate, a decimal range, an unrelated metric).

A new static claim, or a new retired-figure mention in an already-allowlisted line, fails here.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEBSITE_DIR = ROOT / "apps" / "website"
DATA_JS = WEBSITE_DIR / "data.js"

#: The retired figure set (docs/review/public_truth_review.md P0 + the README staleness the
#: same review flagged as "smaller"). Each regex matches the figure as it appeared in static
#: text; ``772`` uses a lookbehind so an SVG ``y="772"`` coordinate and the decimal range
#: ``0.772–0.815`` are not treated as the retired session count.
RETIRED_FIGURES: dict[str, str] = {
    "156": r"\b156\b",  # retired story count (now 215)
    "772": r"(?<![\d.\"])772\b",  # retired session count (now 1,067)
    "219.51": r"219\.51",  # retired corpus cost (now $309.17; also covers 219.5112)
    "1,097": r"\b1,097\b",  # retired README session count (now 1,067)
    "1097": r"\b1097\b",
    "288.69": r"288\.69",  # retired README spend (now $309.17)
    "1572": r"\b1572\b",  # retired test-pass numerator
    "1772": r"\b1772\b",  # retired test-pass denominator
    "88.7%": r"88\.7\s*%",  # retired overall test-pass rate
}

#: The retired live-treatment term. ``bad_seed`` is no longer an active arm — the canonical
#: condition split is ``clean 135 / early_degrade 80`` (no-op ``bad_seed`` cells relabeled
#: ``clean``, docs/data_integrity_findings.md treatment rule 1).
RETIRED_TREATMENT_TERMS: dict[str, str] = {
    "bad_seed": r"(?i)bad[_ ]seed",
}

#: Narrow allowlist. A key is ``(repo-relative path, line substring)``; the value is the set
#: of retired figures/terms that line may mention. The substring identifies the line WITHOUT
#: naming the retired token itself, so the resolve test below detects a dead entry the moment
#: the historical framing is edited away. Every entry is a deliberate historical framing or a
#: coincidental non-figure match, justified by its comment — never a current claim.
ALLOWLIST: dict[tuple[str, str], frozenset[str]] = {
    # Historical framing: the code comment explains WHY the story-arc table was repointed to
    # read D.labs.story_arc — it quotes the retired figure it drifted from.
    (
        "apps/website/evidence.html",
        "it drifted: the transcribed figures were from",
    ): frozenset({"156"}),
    # Coincidental digit match, not the retired test-pass rate: the semantic-drift table's
    # "Correctness (all shapes)" column for GPT-5.6-fast (a trajectory-shape metric, not a
    # test-pass percentage).
    (
        "apps/website/evidence.html",
        "Most strongly convergent (75%)",
    ): frozenset({"88.7%"}),
    # Corrective framing, not an active arm: the "Note on arms" explains that no-op
    # bad_seed/early_degrade cells are relabeled clean. It names the retired label only to
    # say it is NOT a real arm.
    (
        "apps/website/index.html",
        "the arms above are the corrected ones",
    ): frozenset({"bad_seed"}),
    (
        "apps/website/evidence.html",
        "the arms above are the corrected ones, not the raw labels",
    ): frozenset({"bad_seed"}),
}

#: The public figures the static pages cite. The public_statistics block (the single source
#: of truth per the review) must carry every one, so a page figure can never drift from it.
CITED_PUBLIC_FIGURES = (
    "story_sessions",
    "stories_total",
    "story_total_cost",
    "model_variants",
)


def _is_allowed(rel: str, line: str, name: str) -> bool:
    """True when this line's occurrence is covered by an explicit allowlist entry."""
    for (path, substring), allowed in ALLOWLIST.items():
        if path == rel and substring in line and name in allowed:
            return True
    return False


def test_static_html_contains_no_retired_figures():
    """No ``*.html`` carries a retired figure or a live ``bad_seed`` arm outside the allowlist."""
    patterns = {**RETIRED_FIGURES, **RETIRED_TREATMENT_TERMS}
    violations: list[str] = []
    for path in sorted(WEBSITE_DIR.glob("*.html")):
        rel = str(path.relative_to(ROOT))
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for name, pattern in patterns.items():
                for match in re.finditer(pattern, line):
                    if _is_allowed(rel, line, name):
                        continue
                    violations.append(
                        f"{rel}:{line_no}: {name!r} ({match.group(0)!r}) — retired; "
                        f"repoint to the canonical public_statistics figure or add an "
                        f"allowlist entry"
                    )
    assert not violations, "static pages referencing retired figures/terms:\n" + "\n".join(
        sorted(violations)
    )


def test_allowlist_entries_all_resolve():
    """Every allowlist entry still matches a line in its file (no dead historical framing)."""
    for (rel, substring), allowed in ALLOWLIST.items():
        path = ROOT / rel
        assert path.is_file(), f"allowlist path does not exist: {rel}"
        assert substring in path.read_text(encoding="utf-8"), (
            f"allowlist entry no longer matches {rel}: {substring!r} — the historical "
            f"framing was edited away; drop the entry"
        )
        assert allowed, f"allowlist entry for {rel}:{substring!r} allows nothing"


def test_public_statistics_covers_cited_figures():
    """The public_statistics block carries every figure the static pages cite.

    This is the "regenerate data.js only if public_statistics needs extension" gate: the pages
    cite story count, session count, and total cost, so all three must live in the one
    generated statistics artifact — not only in the ``summary`` block.
    """
    if not DATA_JS.exists():  # pragma: no cover - generated file, present in CI
        return
    text = DATA_JS.read_text(encoding="utf-8")
    payload = json.loads(text[text.index("{") : text.rindex("}") + 1])
    ps = payload.get("public_statistics", {})
    missing = [name for name in CITED_PUBLIC_FIGURES if name not in ps]
    assert not missing, (
        f"public_statistics is missing figures the pages cite: {missing} — extend "
        f"build_data.py's public_statistics block and regenerate data.js"
    )
