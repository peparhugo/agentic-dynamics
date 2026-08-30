"""The β coordination-tax instrument — the snowball tax's coordination face.

Design: ``docs/designs/proposed/beta_snowball_measurement_design.md`` §2.

The framework's β is decomposed into two measured faces; this module is the SECOND face —
the coordination tax: the overhead of breaking work into concurrent units and
re-integrating them. The instrument is a measurement rule (``[C]`` — derived from measured
fields):

    coordination_overhead(campaign) = (wrapper + merge + chain + review) / (cell)

reported per campaign and aggregated over the corpus.

**Measured-never-blended (design §6).** Only the ``wrapper`` and ``cell`` terms carry a
measured USD cost (the campaign phase ledgers' ``total_measured_cost_breakdown``). The
``merge``/``chain``/``review`` terms are EVENT COUNTS — git merge/conflict events, the
sync/build/manifest data-chain runs, and the review rounds — each from its own record
source. They are deliberately NOT blended into the cost ratio: the cost-based β uses only
the measured cost terms, and the event counts are reported as a parallel, per-campaign
coordination-event vector (a different unit, a different signal). A term with no measured
source is ``None``, never a fabricated zero.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CoordinationComponents:
    """One campaign's measured coordination inputs, per term with its source.

    ``cell_cost`` and ``wrapper_cost`` are USD (measured). ``merge_events``,
    ``chain_events`` and ``review_rounds`` are counts (measured where a record exists,
    else ``None``). Each carries a provenance ``*_source`` string naming the artifact it
    was derived from, so a reader can re-derive every number.
    """

    campaign: str
    cell_cost: float | None = None
    wrapper_cost: float | None = None
    merge_events: int | None = None
    chain_events: int | None = None
    review_rounds: int | None = None
    cell_source: str = ""
    wrapper_source: str = ""
    merge_source: str = ""
    chain_source: str = ""
    review_source: str = ""
    breakdown: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign": self.campaign,
            "cell_cost": self.cell_cost,
            "wrapper_cost": self.wrapper_cost,
            "merge_events": self.merge_events,
            "chain_events": self.chain_events,
            "review_rounds": self.review_rounds,
            "cell_source": self.cell_source,
            "wrapper_source": self.wrapper_source,
            "merge_source": self.merge_source,
            "chain_source": self.chain_source,
            "review_source": self.review_source,
            "breakdown": self.breakdown,
        }


#: The phase-ledger keys that are CELL work (the agent doing the task), vs everything else
#: (the wrapper/verification overhead). ``rework`` is agent work on a failed first attempt —
#: it is cell work, not coordination. ``[P]`` policy: which phase kinds count as "cell" vs
#: "wrapper" is the instrument's declared choice, recorded here so it is auditable.
CELL_PHASE_KEYS = ("implement", "rework")


def coordination_overhead(
    cell_cost: float | None,
    wrapper_cost: float | None,
    *,
    merge_cost: float = 0.0,
    chain_cost: float = 0.0,
    review_cost: float = 0.0,
) -> float | None:
    """The β arithmetic — ``(wrapper + merge + chain + review) / cell``.

    All terms are in a caller-chosen common unit (USD for the cost-based β; the
    ``merge_cost``/``chain_cost``/``review_cost`` keyword terms default to 0.0 so the
    cost-based β is ``wrapper / cell`` unless a caller supplies event costs). Returns
    ``None`` when ``cell_cost`` is absent or non-positive — a cell denominator that cannot
    be measured yields an unmeasured result, never a division by zero or a fabricated 0.
    """
    if cell_cost is None or wrapper_cost is None:
        return None
    if cell_cost <= 0:
        return None
    return (wrapper_cost + merge_cost + chain_cost + review_cost) / cell_cost


def wrapper_share(cell_cost: float | None, wrapper_cost: float | None) -> float | None:
    """The wrapper-phase share of a campaign's spend — ``wrapper / (wrapper + cell)``.

    This is the number the 2b prior quotes at 63% ($0.17 of $0.27). ``None`` when the
    denominator is absent or non-positive.
    """
    if cell_cost is None or wrapper_cost is None:
        return None
    total = wrapper_cost + cell_cost
    if total <= 0:
        return None
    return wrapper_cost / total


def split_breakdown(breakdown: dict[str, float]) -> tuple[float, float]:
    """Split a phase-ledger cost breakdown into ``(cell_cost, wrapper_cost)``.

    ``cell`` = the sum over :data:`CELL_PHASE_KEYS` (``implement`` + ``rework``); ``wrapper``
    = the sum over every other key (``test`` + ``verify`` + any orchestrator phases present).
    A ``None`` phase value (a phase that did not run) contributes 0.0 — the phase-ledger
    contract writes ``null`` for unrun phases, never a fabricated cost.
    """
    cell = 0.0
    wrapper = 0.0
    for key, value in breakdown.items():
        if value is None:
            continue
        if key in CELL_PHASE_KEYS:
            cell += float(value)
        else:
            wrapper += float(value)
    return cell, wrapper
