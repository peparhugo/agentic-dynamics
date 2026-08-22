"""The shared optional-measurement primitive (measurement-contribution closure, m2).

Why this module exists
----------------------
``docs/review/measurement_contribution_review.md`` P1/P2 found the *same* defect in
every canonical producer under different names: an unavailable measurement was coerced
to numeric zero, so "not measured" became "measured as 0" and diluted published
averages. Three variants appeared across the eight labs and ``build_data.py``:

* ``cost = summary.get("total_cost", 0) or 0`` then averaging over **all** cells
  (``lab_condition_effects``, ``lab_story_review``);
* ``cost = s.get("cost_usd", 0) or 0`` inserting a zero for an absent session cost
  (``lab_story_arc``);
* ``if cost > 0: append`` excluding zeros but publishing **no coverage**, so a reader
  could not tell "cheap" from "unpriced" (``lab_cache_economics``,
  ``lab_quality_frontier``, ``lab_verification_frontier``);
* ``sol.get("correctness_score", 0) or 0`` / ``basin.get("escape_score", 0) or 0``
  folding an absent deep-metric into the average (``build_data.py``).

The invariant (m2): **an unavailable measurement is ``null`` with zero coverage — never
numeric zero — and a published average never treats missing cost as $0.**

This module is the single place that decides *captured vs not* and *available vs total*,
so every producer applies one denominator policy instead of each re-deriving it. The
dataclass is the generic shape; the cost helpers are its cost-specific specialization.

Design notes
------------
* :class:`MeasurementCoverage` is **frozen** — producers consume and serialize it, they
  never mutate it. ``value`` is ``None`` exactly when ``n_available == 0``, which is what
  the guard test asserts.
* ``coverage`` is rounded to 4 decimals here, uniformly, so two producers reporting the
  same population emit byte-identical coverage; ``value`` is left raw (producers round it
  to their own precision via ``round_value`` or at serialization).
* :func:`cost_captured` is the one place "is this cost real?" is answered. The old code
  answered it three ways (``or 0``, ``> 0``, and nothing at all in ``condition_effects``);
  now there is one answer.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import TypeGuard

#: The precision every producer reports ``coverage`` at (a proportion, 4 decimals).
_COVERAGE_NDIGITS = 4

#: The precision every producer reports a cost average / total at (USD, 6 decimals).
_COST_NDIGITS = 6


@dataclass(frozen=True)
class MeasurementCoverage:
    """One optional measurement and its availability accounting.

    Fields (m2 SHAPE):

    * ``value`` — the mean over the *available* records, or ``None`` when none were
      available (an unmeasured value is null, never zero).
    * ``n_available`` — how many records actually measured the value.
    * ``n_total`` — how many records *could have* measured it.
    * ``coverage`` — ``n_available / n_total`` (``0.0`` when ``n_total`` is zero).
    """

    value: float | None
    n_available: int
    n_total: int
    coverage: float

    @classmethod
    def over(
        cls,
        values: Iterable[float],
        *,
        n_total: int,
        round_value: int | None = None,
    ) -> MeasurementCoverage:
        """Coverage for the *available* ``values`` against ``n_total`` possible records.

        ``value`` is the mean of ``values`` (rounded to ``round_value`` decimals when
        given) and is ``None`` when ``values`` is empty — the null-not-zero rule.
        """
        available = [v for v in values]
        n_available = len(available)
        if n_available:
            value = sum(available) / n_available
            if round_value is not None:
                value = round(value, round_value)
        else:
            value = None
        coverage = round(n_available / n_total, _COVERAGE_NDIGITS) if n_total else 0.0
        return cls(
            value=value,
            n_available=n_available,
            n_total=n_total,
            coverage=coverage,
        )

    @property
    def measured(self) -> bool:
        """True when at least one record measured the value (``value`` is not ``None``)."""
        return self.n_available > 0

    def to_dict(self) -> dict:
        """Plain dict for JSON embedding (the ``{value, n_available, n_total, coverage}`` shape)."""
        return asdict(self)


def cost_captured(cost) -> TypeGuard[float]:
    """A cost is *captured* iff it is a finite, positive real number.

    A ``0.0``/``None``/absent cost means "no billable work priced" (the review's P1 case:
    a story whose sessions never ran, or whose cost the parser never wrote). Such a value
    must not enter a captured-cost average as zero. Centralized so no producer re-invents
    the old ``if cost > 0`` vs ``or 0`` split.
    """
    return (
        isinstance(cost, (int, float))
        and not isinstance(cost, bool)
        and math.isfinite(cost)
        and cost > 0
    )


def captured_costs(costs: Iterable[float | None]) -> list[float]:
    """The subset of ``costs`` that are actually captured (see :func:`cost_captured`).

    ``None`` / ``0.0`` entries are "not captured" and are dropped, never folded into an
    average as zero.
    """
    return [c for c in costs if cost_captured(c)]


def cost_coverage(costs: Iterable[float | None], *, n_total: int) -> dict:
    """The published cost-average shape (m2): captured-only mean + coverage accounting.

    Every published cost average carries the same five fields, so two views of the same
    population can never disagree on its denominator:

    * ``avg_captured_cost`` — mean over captured costs only (``None`` when none captured);
    * ``total_captured_cost`` — sum of captured costs;
    * ``cost_captured_records`` — how many records captured a cost;
    * ``total_records`` — how many records the average is over;
    * ``cost_coverage`` — ``cost_captured_records / total_records``.
    """
    captured = captured_costs(costs)
    mc = MeasurementCoverage.over(captured, n_total=n_total)
    return {
        "avg_captured_cost": (round(mc.value, _COST_NDIGITS) if mc.value is not None else None),
        "total_captured_cost": round(sum(captured), _COST_NDIGITS),
        "cost_captured_records": mc.n_available,
        "total_records": mc.n_total,
        "cost_coverage": mc.coverage,
    }
