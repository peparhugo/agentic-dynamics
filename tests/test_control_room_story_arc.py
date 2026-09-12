"""Tests for the P4 ``story_arc`` projection (step 6, d3 §5 P4).

Pins: session ordering; snowball = last/first captured cost; family lookup aggregates builds;
an uncaptured cost never becomes 0; an unknown story is None (the route's 404); β carries its
policy class and source.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _path in (_ROOT, _ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from agentic_dynamics.control.projections.story_arc import (  # noqa: E402
    SCHEMA,
    build_story_arc,
    match_stories,
)

_NOW = "2026-09-12T00:00:00+00:00"


def _story(story_id, story_name, sessions):
    return {"story_id": story_id, "story_name": story_name, "sessions": sessions}


_STORY_1 = _story(
    "s1",
    "task_manager_api",
    [
        {"session_number": 1, "cost_usd": 1.0, "code_lines": 100},
        {"session_number": 2, "cost_usd": 2.0, "code_lines": 120},
        {"session_number": 3, "cost_usd": 3.0, "code_lines": 140},
        {"session_number": 4, "cost_usd": 4.0, "code_lines": 160},
        {"session_number": 5, "cost_usd": 5.0, "code_lines": 180},
    ],
)
_STORY_2 = _story(
    "s2",
    "task_manager_api",
    [
        {"session_number": 1, "cost_usd": 3.0, "code_lines": 200},
        {"session_number": 5, "cost_usd": 9.0, "code_lines": 300},
        {"session_number": 5, "cost_usd": None, "code_lines": None},  # not captured
    ],
)


def test_single_build_arc_is_ordered_and_snowball_is_last_over_first():
    payload = build_story_arc([_STORY_1, _STORY_2], "s1", now=_NOW)
    assert payload["schema"] == SCHEMA
    assert payload["matched_by"] == "story_id"
    assert [row["session_number"] for row in payload["sessions"]] == [1, 2, 3, 4, 5]
    assert payload["snowball_factor"] == 5.0
    assert payload["velocity"] == 140.0
    assert payload["sessions"][0]["task_type"] == "greenfield"


def test_family_lookup_aggregates_every_build_of_the_story():
    payload = build_story_arc([_STORY_1, _STORY_2], "task_manager_api", now=_NOW)
    assert payload["matched_by"] == "story_name"
    assert payload["stories_matched"] == 2
    by_number = {row["session_number"]: row for row in payload["sessions"]}
    # session 1: mean(1.0, 3.0) = 2.0; session 5: captured costs [5, 9] (the None is dropped).
    assert by_number[1]["cost_usd"] == 2.0
    assert by_number[5]["cost_usd"] == 7.0
    assert by_number[5]["n"] == 3
    assert by_number[5]["cost_captured_records"] == 2
    assert by_number[5]["cost_coverage"] == 0.6667
    assert payload["snowball_factor"] == 3.5


def test_uncaptured_costs_leave_the_ratio_unknown_not_zero():
    story = _story(
        "s3",
        "static_site_gen",
        [
            {"session_number": 1, "cost_usd": None, "code_lines": 10},
            {"session_number": 5, "cost_usd": 0.0, "code_lines": 20},  # 0.0 is not captured
        ],
    )
    payload = build_story_arc([story], "s3", now=_NOW)
    assert payload["snowball_factor"] is None
    assert payload["snowball_reason"] == "first/last session cost un-captured"
    assert payload["sessions"][0]["cost_usd"] is None
    assert payload["sessions"][1]["cost_usd"] is None
    assert payload["sessions"][1]["cost_coverage"] == 0.0


def test_unknown_story_name_is_none_and_match_reports_none():
    assert build_story_arc([_STORY_1], "nope", now=_NOW) is None
    assert match_stories([_STORY_1], "nope") == ([], "none")


def test_beta_is_labeled_policy_with_its_source():
    payload = build_story_arc([_STORY_1], "s1", now=_NOW)
    assert payload["beta"]["class"] == "[P]"
    assert isinstance(payload["beta"]["value"], float)
    assert "lab_beta_from_corpus" in payload["beta"]["source"]
