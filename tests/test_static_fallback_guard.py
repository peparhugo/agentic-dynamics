"""Static-fallback guard (measurement-contribution closure, m4).

The website's static HTML carries two kinds of claim that ``data.js`` cannot repair at
runtime: ``data-stat`` fallback text (the value shown before JS runs) and ``meta``/Open
Graph descriptions (which never run JS). Both must equal the generated
``public_statistics``/``summary`` figures, or a page with JS disabled — or a search
snippet — reports the *retired* corpus.

This module parses every ``data-stat`` fallback and the headline ``meta``/OG text and
asserts exact equality with the generated statistics. Any drift (a stale fallback, a
retired figure in a snippet) fails here, so "the static text agrees with data.js" is a
checkable fact rather than a claim.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WEBSITE_DIR = ROOT / "apps" / "website"
DATA_JS = WEBSITE_DIR / "data.js"

#: data-stat key -> (block, field, kind) for every key the site's ``app.js`` statMap
#: resolves from a *scalar* statistics block (``summary`` / ``public_statistics``).
#: ``kind`` is ``"int"`` (a count, rendered as the raw integer), or ``"usd"`` (a dollar
#: figure rendered via ``toFixed(2)``). Dynamic keys that read ``D.derived`` /
#: ``D.models`` / ``D.calculator`` are out of scope here — they are runtime comparisons,
#: not static corpus claims.
STAT_FIELDS: dict[str, tuple[str, str, str]] = {
    "sessions": ("summary", "sessions_total", "int"),
    "worktrees": ("summary", "worktrees_total", "int"),
    "reports": ("summary", "game_reports", "int"),
    "cost": ("summary", "total_cost", "usd"),
    "architectures": ("summary", "architectures", "int"),
    "variants": ("summary", "variants", "int"),
    "story_sessions": ("summary", "story_sessions", "int"),
    "stories_total": ("summary", "stories_total", "int"),
    "story_total_cost": ("summary", "story_total_cost", "usd"),
    "registry_current_records": ("summary", "registry_current_records", "int"),
    "resolved_measurement_payloads": ("summary", "resolved_measurement_payloads", "int"),
    "eligible_records": ("summary", "eligible_records", "int"),
    "records_used": ("summary", "records_used", "int"),
    "unresolved_waivered": ("summary", "unresolved_waivered", "int"),
    "canonical_findings": ("summary", "canonical_findings", "int"),
    "contaminated_tombstones": ("summary", "contaminated_tombstones", "int"),
    "no_measurement_tombstones": ("summary", "no_measurement_tombstones", "int"),
    "tombstones_total": ("summary", "tombstones_total", "int"),
    "model_variants": ("public_statistics", "model_variants", "int"),
}

#: ``data-stat="KEY">FALLBACK</tag>`` — the fallback text the page shows before JS runs.
_DATA_STAT_RE = re.compile(r'data-stat="([A-Za-z0-9_]+)"[^>]*>([^<]*)<')


def _data_js_payload() -> dict | None:
    if not DATA_JS.exists():  # pragma: no cover - generated file, present in CI
        return None
    text = DATA_JS.read_text(encoding="utf-8")
    return json.loads(text[text.index("{") : text.rindex("}") + 1])


def _expected(payload: dict, key: str) -> str:
    """The value the site's statMap would render for ``key``, as a string."""
    block, field, kind = STAT_FIELDS[key]
    value = payload[block][field]
    if kind == "usd":
        return f"{value:.2f}" if value is not None else ""
    if kind == "int":
        return str(int(value))
    return str(value)


def _norm(s: str) -> str:
    """Normalize a rendered figure for comparison (commas are presentation only)."""
    return s.strip().replace(",", "").replace("$", "")


def test_data_stat_fallbacks_equal_generated_statistics():
    """Every scalar ``data-stat`` fallback equals the generated statistics figure.

    A stale fallback (e.g. a retired session count) fails here even though the live JS
    would overwrite it — the static text must already agree.
    """
    payload = _data_js_payload()
    if payload is None:  # pragma: no cover
        pytest.skip("apps/website/data.js not generated")

    violations: list[str] = []
    for path in sorted(WEBSITE_DIR.glob("*.html")):
        rel = str(path.relative_to(ROOT))
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for match in _DATA_STAT_RE.finditer(line):
                key, fallback = match.group(1), match.group(2)
                if key not in STAT_FIELDS:
                    continue
                expected = _expected(payload, key)
                if _norm(fallback) != _norm(expected):
                    violations.append(
                        f"{rel}:{line_no}: data-stat={key!r} fallback={fallback!r} "
                        f"but data.js says {expected!r}"
                    )
    assert not violations, "static data-stat fallbacks drifted from data.js:\n" + "\n".join(
        sorted(violations)
    )


def _headline_figures(payload: dict) -> dict[str, str]:
    ps = payload["public_statistics"]
    return {
        "stories": str(ps["stories_total"]),
        "sessions": f"{ps['story_sessions']:,}",
        "models": str(ps["model_variants"]),
        "cost": f"{ps['story_total_cost']:.2f}",
    }


def test_meta_and_og_text_agree_with_generated_statistics():
    """The evidence + index meta/OG descriptions carry the current headline figures."""
    payload = _data_js_payload()
    if payload is None:  # pragma: no cover
        pytest.skip("apps/website/data.js not generated")

    figs = _headline_figures(payload)
    # evidence.html's meta description enumerates the four headline figures.
    evidence = (WEBSITE_DIR / "evidence.html").read_text(encoding="utf-8")
    m = re.search(r'<meta name="description" content="([^"]+)"', evidence)
    assert m, "evidence.html has no meta description"
    meta = m.group(1)
    assert figs["stories"] in meta, f"stories figure {figs['stories']!r} missing from evidence meta"
    assert figs["sessions"] in meta, (
        f"sessions figure {figs['sessions']!r} missing from evidence meta"
    )
    assert figs["models"] in meta, f"models figure {figs['models']!r} missing from evidence meta"
    assert figs["cost"] in meta, f"cost figure {figs['cost']!r} missing from evidence meta"
