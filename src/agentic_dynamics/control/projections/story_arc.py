"""P4 ``story_arc`` — the session arc of a story family (Snowball / velocity / β) (d3 §5 P4).

The read model answers "what did this story cost, session by session?" — the Snowball Rule
measured directly. Two lookup modes against the canonical story corpus:

* ``<name>`` matching a ``story_id`` -> that ONE build's arc;
* ``<name>`` matching a ``story_name`` (``task_manager_api`` …) -> the family's arc, each
  session number aggregated across every build of that story (the same population
  ``scripts/lab_story_arc.py`` reads).

Costs are nullable exactly like the lab's: an absent/zero session cost is *not captured* and
never inserted as 0 (measurement_contribution m2). ``snowball_factor`` = last-session cost /
first-session cost over the captured means (None when either is un-captured — a ratio with a
missing denominator is unknown, never a fabricated number).

β is a declared design parameter, not a measurement of this arc: it is carried with its
policy class and its source, per the d5 acceptance (``β is labeled [P]``).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from agentic_dynamics.control.lease_registry import BETA_TOKENS
from agentic_dynamics.reporting.measurement_coverage import cost_captured, cost_coverage

SCHEMA = "story-arc/v1"

#: How β is presented: a policy prior used for admission sizing, never a live reading.
BETA_SOURCE = (
    "control.lease_registry.BETA_TOKENS — the preregistered coordination-tax estimate "
    "(lab_beta_from_corpus, decision: moderate_tax)"
)

#: The session-number vocabulary the story designs use (presentation only).
SESSION_TASK_TYPES = {
    1: "greenfield",
    2: "feature",
    3: "integration",
    4: "refactor",
    5: "cross_cutting",
}


def match_stories(stories: list[dict[str, Any]], name: str) -> tuple[list[dict[str, Any]], str]:
    """Resolve ``name`` against the corpus: exact ``story_id`` first, then ``story_name``.

    Returns ``(matched, matched_by)`` with ``matched_by`` in ``{"story_id", "story_name",
    "none"}`` — the caller renders "none" as a 404 rather than guessing a story.
    """
    by_id = [s for s in stories if str(s.get("story_id") or "") == name]
    if by_id:
        return by_id, "story_id"
    by_name = [s for s in stories if str(s.get("story_name") or "") == name]
    if by_name:
        return by_name, "story_name"
    return [], "none"


def build_story_arc(
    stories: list[dict[str, Any]],
    name: str,
    *,
    beta: float | None = None,
    now: str | None = None,
    source: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Build the arc payload for ``name``, or ``None`` when no story matches.

    Pure given its inputs; ``now`` and ``source`` are injected, β may be overridden for tests.
    """
    matched, matched_by = match_stories(stories, name)
    if not matched:
        return None

    per_session: dict[int, dict[str, list[Any]]] = defaultdict(
        lambda: {"costs": [], "code_lines": [], "n": 0}
    )
    for story in matched:
        for session in story.get("sessions") or []:
            if not isinstance(session, dict):
                continue
            sn = session.get("session_number")
            if not isinstance(sn, int) or sn <= 0:
                continue
            row = per_session[sn]
            row["n"] += 1
            cost = session.get("cost_usd")
            if cost_captured(cost):
                row["costs"].append(cost)
            code_lines = session.get("code_lines")
            if isinstance(code_lines, (int, float)) and not isinstance(code_lines, bool):
                row["code_lines"].append(code_lines)

    sessions: list[dict[str, Any]] = []
    for sn in sorted(per_session):
        row = per_session[sn]
        coverage = cost_coverage(row["costs"], n_total=row["n"])
        lines = row["code_lines"]
        sessions.append(
            {
                "session_number": sn,
                "task_type": SESSION_TASK_TYPES.get(sn, "?"),
                "n": row["n"],
                "cost_usd": coverage["avg_captured_cost"],
                "cost_captured_records": coverage["cost_captured_records"],
                "cost_coverage": coverage["cost_coverage"],
                "code_lines": round(sum(lines) / len(lines), 2) if lines else None,
                "code_lines_records": len(lines),
            }
        )

    first_cost = sessions[0]["cost_usd"] if sessions else None
    last_cost = sessions[-1]["cost_usd"] if sessions else None
    snowball = round(last_cost / first_cost, 2) if (first_cost and last_cost) else None

    all_lines = [v for row in per_session.values() for v in row["code_lines"]]
    velocity = round(sum(all_lines) / len(all_lines), 2) if all_lines else None

    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at": now,
        "source": dict(source or {}),
        "story": name,
        "matched_by": matched_by,
        "stories_matched": len(matched),
        "sessions": sessions,
        "snowball_factor": snowball,
        "velocity": velocity,
        "beta": {
            "value": beta if beta is not None else BETA_TOKENS,
            "class": "[P]",
            "source": BETA_SOURCE,
        },
        "degraded": [],
    }
    if snowball is None:
        payload["snowball_reason"] = (
            "first/last session cost un-captured" if sessions else "no sessions recorded"
        )
    return payload
