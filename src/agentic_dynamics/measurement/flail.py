"""The Explanation-Tax flail rule (d3 G-05) — measured, never invented.

Rule 2 charges a model for what its resilience costs. The two costs it names are the
**flail rate** (sessions that spend tokens but produce nothing) and the narration penalty
(the answer/explanation token split, surfaced by the ``model_quality`` projection from the
ledger). This module owns the first, computed over the canonical story session rows
(``sessions.parquet`` / the canonical corpus) that :mod:`scripts.sync_data` normalizes.

Definition (``docs/reviews/control_room_rule_map.md`` Rule 2 — *flail rate [C, derived from
``code_lines==0``/``files_changed==0``]*)::

    flail(session) = code_lines == 0 AND files_changed == 0
    flail_rate     = flail sessions / eligible sessions

The conjunction is deliberate, and it is the reading the two signals can actually support:

* ``code_lines`` is the worktree's **cumulative** non-test code count at session end
  (``runtime/story/orchestration.py:_count_tests``), not a per-session delta; a zero means the
  worktree held no non-test code at all.
* ``files_changed`` is the **per-session** symmetric-difference count.

A bare ``code_lines == 0`` therefore fires on ~40% of the committed session rows (a counter
that is often zero when a session only touched tests or the worktree count ran clean), and a
bare OR of the two signals fires on 25–72% per model — neither is plausibly "produced no
code". Requiring BOTH to be zero is the corroborated "changed nothing and left no code"
reading: it under-counts rather than converting a defaulted counter into a fabricated flail.
A session is **eligible** only when BOTH signals are measured (a non-negative integer) — a
session missing either is reported in the coverage gap, never counted as a non-flail.

The small-sample rule (``reporting.grit_metric.MIN_CELLS_FOR_RATE``) is applied by the
projection beside the other metrics; this module reports the raw counts and ratio so the
coverage discipline (*coverage before ratio*) is structural.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

#: The formula, carried in the projection payload so a reader never has to look it up.
FLAIL_DEFINITION = (
    "flail(session) = code_lines == 0 and files_changed == 0; "
    "flail_rate = flail sessions / eligible sessions"
)

#: ``[C]`` — computed from the measured session fields (rule map Rule 2's own class).
EVIDENCE_CLASS = "[C]"


@dataclass(frozen=True)
class FlailMetrics:
    """The flail rule's coverage-first result for one model's session population.

    ``flail_rate`` is the raw ratio (``None`` on a zero denominator); ``coverage`` is
    ``n_eligible / n_total`` — both are always reported so a caller can see the population
    the ratio stands on before reading it.
    """

    n_total: int
    n_eligible: int
    flail_sessions: int
    flail_rate: float | None
    coverage: float
    reason: str | None = None


def _measured_int(value: Any) -> bool:
    """True when ``value`` is a measured non-negative integer (not a bool/float/None).

    The session tables type these counters as integers; a missing/defaulted counter must not
    silently become a measured zero, so only a real ``int`` qualifies.
    """
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def compute_flail(sessions: Iterable[Mapping[str, Any]]) -> FlailMetrics:
    """Compute the flail rule over session rows, coverage before ratio.

    Each row must expose ``code_lines`` and ``files_changed`` (the two signals the rule
    consumes). A row missing either is counted in ``n_total`` but not ``n_eligible``.
    An empty eligible population yields ``flail_rate is None`` with a named reason — never
    ``0.0``.
    """
    rows = list(sessions)
    total = len(rows)
    eligible = [
        row
        for row in rows
        if _measured_int(row.get("code_lines")) and _measured_int(row.get("files_changed"))
    ]
    flail = sum(
        1 for row in eligible if row["code_lines"] == 0 and row["files_changed"] == 0
    )
    rate = round(flail / len(eligible), 4) if eligible else None
    reason: str | None = None
    if not eligible:
        reason = (
            "no session carries both code_lines and files_changed (cannot form a rate)"
            if total
            else "no sessions in the population"
        )
    return FlailMetrics(
        n_total=total,
        n_eligible=len(eligible),
        flail_sessions=flail,
        flail_rate=rate,
        coverage=round(len(eligible) / total, 4) if total else 0.0,
        reason=reason,
    )


def flatten_story_sessions(stories: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Flatten canonical story payloads to one row per session, carrying its model.

    The canonical story payload nests each session's measured counters; this exposes the two
    the flail rule consumes plus the model/story/session identity a caller groups and cites
    by. Only dict sessions are read; a malformed entry is skipped (the projection's
    population count is the corpus's, not a fabricated one).
    """
    rows: list[dict[str, Any]] = []
    for story in stories:
        if not isinstance(story, Mapping):
            continue
        model = str(story.get("model") or "")
        story_name = str(story.get("story_name") or "")
        for session in story.get("sessions") or []:
            if not isinstance(session, Mapping):
                continue
            rows.append(
                {
                    "model": model,
                    "story_name": story_name,
                    "session_number": session.get("session_number"),
                    "code_lines": session.get("code_lines"),
                    "files_changed": session.get("files_changed"),
                }
            )
    return rows
