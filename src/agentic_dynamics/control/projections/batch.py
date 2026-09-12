"""P10 ``batch`` — the Batch Discount surface (d3 §5 P10, rule 6).

There is no batch execution mode anywhere in the system: no ``batch_mode`` marker, no batch
accounting, no batch arm. The projection is therefore explicitly not-measurable — it renders the
pin's honest state and the DESIGN scenario it stands for, and it never fabricates a fraction:

* ``measurable: false`` with the missing-record reason while no job carries ``batch_mode``;
* the modeled block (``discount``/``horizon_h``, class ``X/P``) labeled as a scenario;
* if a ``batch_mode`` marker ever appears (a real writer landing), the fraction switches to a
  measured computation over the marked jobs — the door is open, the number is never invented.
"""

from __future__ import annotations

from typing import Any

SCHEMA = "batch/v1"

#: The rule-6 design scenario (pinned): a 50% discount over a 72h batch horizon, class X/P.
MODELED: dict[str, Any] = {
    "discount": 0.5,
    "horizon_h": 72,
    "class": "X/P",
    "source": "rule 6 (Batch Discount) — proposed [C]; no batch executor exists",
}


def build_batch(
    jobs: list[dict[str, Any]],
    *,
    now: str | None = None,
    source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the batch payload over the queue's job dicts. Pure given its inputs."""
    marked = [j for j in jobs if isinstance(j, dict) and isinstance(j.get("batch_mode"), bool)]
    if not marked:
        return {
            "schema": SCHEMA,
            "generated_at": now,
            "source": dict(source or {}),
            "measurable": False,
            "reason": (
                "queue empty — nothing to classify"
                if not jobs
                else "no batch_mode marker"
            ),
            "scanned_jobs": len(jobs),
            "missing_fields": ["batch_mode", "batch vs on-demand accounting", "batch fraction"],
            "modeled": dict(MODELED),
            "degraded": [],
        }

    batch = sum(1 for j in marked if j["batch_mode"])
    fraction = batch / len(marked)
    return {
        "schema": SCHEMA,
        "generated_at": now,
        "source": dict(source or {}),
        "measurable": True,
        "batch_fraction": round(fraction, 6),
        "batch_jobs": batch,
        "on_demand_jobs": len(marked) - batch,
        "marked_jobs": len(marked),
        "scanned_jobs": len(jobs),
        # The DISCOUNT stays a labeled design scenario: no provider batch transport exists, so
        # the split is measured but the 50% economics are not (rule 6's own condition).
        "modeled": dict(MODELED),
        "degraded": [],
    }
