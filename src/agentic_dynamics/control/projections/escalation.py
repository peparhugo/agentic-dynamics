"""P9 ``escalation_cascade`` — the Cascade Rule surface (d3 §5 P9, rule 8).

The escalation mechanism does not exist yet: ``escalation_from``/``escalation_to`` are DECLARED
on the attempt schema, and the runner writes ``None`` only (it never retries a phase and never
escalates a model mid-phase). The projection therefore says so explicitly:

* **events** — served only from non-empty recorded ``escalation_from``/``escalation_to`` values;
  with none recorded the list is empty and the missing mechanism is named (G-27);
* **rate_by_tier / human_rate** — computed over the attempts supplied (events per model tier),
  with the human-escalation count an explicit unknown (no counter exists, G-29);
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
                    "escalation_reason": attempt.get("escalation_reason"),
                    "cost_usd": attempt.get("cost_usd"),
                }
            )
    return rows, n_ledgers


def build_escalation_cascade(
    attempts: list[dict[str, Any]],
    *,
    spec: str | None = None,
    published: dict[str, Any] | None = None,
    now: str | None = None,
    source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the escalation payload. Pure given its inputs; ``published`` is the website data."""
    selected = [a for a in attempts if not spec or str(a.get("spec_name") or "") == spec]

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

    return {
        "schema": SCHEMA,
        "generated_at": now,
        "source": dict(source or {}),
        "spec": spec or None,
        "events": events,
        "rate_by_tier": {tier: dict(counts) for tier, counts in sorted(by_tier.items())},
        "human_rate": _unknown("no human-escalation counter (G-29)", gap="G-29", cls="[M]"),
        "armed": bool(events),
        "armed_note": (
            ""
            if events
            else "no cascade mechanism (G-27) — escalation fields are declared and "
            "currently never written; the projection never invents events"
        ),
        "e_x": e_x,
        "degraded": [],
    }
