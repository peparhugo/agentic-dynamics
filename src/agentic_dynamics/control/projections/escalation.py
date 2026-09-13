"""P9 ``escalation_cascade`` — the Cascade Rule surface (d3 §5 P9, rule 8).

The escalation mechanism does not exist yet: ``escalation_from``/``escalation_to`` are DECLARED
on the attempt schema, and the runner writes ``None`` only (it never retries a phase and never
escalates a model mid-phase). The projection therefore says so explicitly:

* **events** — served only from non-empty recorded ``escalation_from``/``escalation_to`` values;
  with none recorded the list is empty and the missing mechanism is named (G-27);
* **rate_by_tier / human_rate** — computed over the attempts supplied (events per model tier);
  the human counter is MEASURED when recorded human-attributed escalation events exist
  (``human_events``: decision records filed under ``category=escalate`` by a human actor), and a
  named unknown otherwise — never a fabricated rate (G-29);
* **armed** — true only when events actually exist; otherwise false with the reason;
* **E_x** — the measured cascade cost multiplier, served from the published website data
  (``verdicts.escalation``, the cap-escalation measurement) and labeled ``[C]/[X]``; when the
  published data is unreadable it is a named unknown, never a guessed ratio.

No event is ever invented; an empty cascade is reported as empty, not as zero-risk.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

SCHEMA = "escalation-cascade/v1"

#: The decision-record category a human escalation is filed under (the decision-record mechanism
#: is the recorded human-attribution surface; categories are open by design). A recorded event
#: under this category whose actor is human IS the G-29 counter's numerator.
HUMAN_ESCALATION_CATEGORY = "escalate"

#: The machine actors the repo records decisions under: the AIO's own s2a recordings
#: (``decision_ingestion.ACTOR``) and the verified commands' s2b permanence emissions
#: (``scripts/promote.py``/``publish_release.py``). A decision attributed to one of these is NOT
#: a human escalation — attribution to a human is what the counter measures.
MACHINE_ACTORS = frozenset({"aio", "verified_command"})


def _unknown(reason: str, *, gap: str = "", cls: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {"state": "unknown", "reason": reason}
    if gap:
        out["gap"] = gap
    if cls:
        out["class"] = cls
    return out


def load_escalation_attempts(results_dir: Path) -> tuple[list[dict[str, Any]], int]:
    """Attempt rows (with escalation fields) from every workflow run ledger.

    ``escalation_*`` are carried through untouched — including ``None``, which is "not written",
    never "no escalation happened". Returns ``(rows, n_ledgers)``.
    """
    if not results_dir.is_dir():
        return [], 0
    rows: list[dict[str, Any]] = []
    n_ledgers = 0
    for path in sorted(results_dir.rglob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(payload, dict) or not isinstance(payload.get("attempts"), list):
            continue
        n_ledgers += 1
        spec_name = str(payload.get("spec_name") or "")
        for attempt in payload["attempts"]:
            if not isinstance(attempt, dict):
                continue
            rows.append(
                {
                    "spec_name": spec_name,
                    "job_id": str(attempt.get("job_id") or ""),
                    "model": str(attempt.get("model") or ""),
                    "escalation_from": attempt.get("escalation_from"),
                    "escalation_to": attempt.get("escalation_to"),
                    # The reason vocabulary the runner actually writes: the schema declares
                    # only ``escalation_from``/``escalation_to`` on the attempt; the WHY rides
                    # ``retry_reason`` ("escalation"). ``escalation_reason`` is read first as
                    # the forward-compatible name if a future writer adds it.
                    "escalation_reason": attempt.get("escalation_reason")
                    or attempt.get("retry_reason"),
                    "cost_usd": attempt.get("cost_usd"),
                }
            )
    return rows, n_ledgers


def load_human_escalation_events(artifact_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Recorded human-attributed escalation events, from the decision-record read seam.

    A human escalation IS a decision ("hand this to a human"), recorded at the moment of the act
    through the decision-record mechanism with the human actor in the payload. Returns
    ``(events, warnings)``; the events are the org-root ``category=escalate`` records whose actor
    is NOT a machine actor (:data:`MACHINE_ACTORS`) — a machine-recorded escalation is not a
    human escalation, and an actor-less record proves nothing, so neither enters the counter.
    A missing artifact directory is simply empty (no recorded events).
    """
    from agentic_dynamics.knowledge import decision_ingestion as di

    triples, warnings = di.scan_decision_records(
        category=HUMAN_ESCALATION_CATEGORY, artifact_dir=artifact_dir
    )
    events: list[dict[str, Any]] = []
    for _path, _artifact, payload in triples:
        actor = str(payload.get("actor") or "").strip()
        if not actor or actor in MACHINE_ACTORS:
            continue
        events.append(
            {
                "decided_at": str(payload.get("decided_at") or ""),
                "actor": actor,
                "what": str(payload.get("what") or ""),
                "run_id": str(payload.get("run_id") or ""),
                "candidate_sha": str(payload.get("candidate_sha") or ""),
            }
        )
    return events, warnings


def build_escalation_cascade(
    attempts: list[dict[str, Any]],
    *,
    spec: str | None = None,
    published: dict[str, Any] | None = None,
    human_events: list[dict[str, Any]] | None = None,
    now: str | None = None,
    source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the escalation payload. Pure given its inputs; ``published`` is the website data."""
    selected = [a for a in attempts if not spec or str(a.get("spec_name") or "") == spec]
    human = list(human_events or [])

    events: list[dict[str, Any]] = []
    for row in selected:
        frm = str(row.get("escalation_from") or "")
        to = str(row.get("escalation_to") or "")
        if not (frm or to):
            continue  # None/empty = nothing recorded; not an event, and not a fabricated one
        cost = row.get("cost_usd")
        events.append(
            {
                "from": frm,
                "to": to,
                "reason": str(row.get("escalation_reason") or ""),
                "model": str(row.get("model") or ""),
                "cost_usd": float(cost)
                if isinstance(cost, (int, float)) and not isinstance(cost, bool)
                else None,
            }
        )

    by_tier: dict[str, dict[str, int]] = defaultdict(lambda: {"attempts": 0, "events": 0})
    for row in selected:
        tier = str(row.get("model") or "unknown")
        by_tier[tier]["attempts"] += 1
    for event in events:
        # An event is attributed to the tier escalated TO — the cascade's receiving tier (a
        # receiver may have zero attempts recorded yet; the event is still real).
        target = event["to"] or event["model"] or "unknown"
        by_tier[target]["events"] += 1

    verdict = ((published or {}).get("verdicts") or {}).get("escalation")
    if isinstance(verdict, dict):
        e_x: dict[str, Any] = {
            "state": "published",
            "class": "[C]/[X]",
            "source": "apps/website/data.js verdicts.escalation (cap escalation measurement)",
            **verdict,
        }
    else:
        e_x = _unknown(
            "published website data unavailable (apps/website/data.js)",
            cls="[C]/[X]",
        )

    if human and selected:
        # Coverage before ratio: numerator AND denominator travel with any measured rate.
        human_rate: dict[str, Any] = {
            "state": "measured",
            "class": "[M]",
            "events": len(human),
            "attempts": len(selected),
            "rate": round(len(human) / len(selected), 6),
            "source": (
                "decision records category=escalate with a human actor, over the workflow-ledger "
                "attempts in this population (org-scope records — not per-spec attributable)"
            ),
        }
    elif human:
        # Events exist but the denominator is empty: the rate is undeterminable, never 0.0.
        human_rate = _unknown(
            "recorded human-escalation events exist but the attempt population is empty — "
            "rate undeterminable (zero denominator)",
            gap="G-29",
            cls="[M]",
        )
        human_rate["events"] = len(human)
        human_rate["attempts"] = 0
    else:
        human_rate = _unknown(
            "no recorded human-escalation events (G-29)", gap="G-29", cls="[M]"
        )

    return {
        "schema": SCHEMA,
        "generated_at": now,
        "source": dict(source or {}),
        "spec": spec or None,
        "events": events,
        "rate_by_tier": {tier: dict(counts) for tier, counts in sorted(by_tier.items())},
        "human_rate": human_rate,
        "armed": bool(events),
        "armed_note": (
            ""
            if events
            else "no escalation events recorded — the cascade exists (step 9, G-27) but is "
            "opt-in via workflow.params.escalation, and no attempt has escalated in this "
            "corpus; the projection never invents events"
        ),
        "e_x": e_x,
        "degraded": [],
    }
