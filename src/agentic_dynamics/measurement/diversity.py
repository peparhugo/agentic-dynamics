"""Portfolio-diversity measurement — how varied is a *set* of attempts?

``measure_basin_escape`` (``basin.py``) answers "did *this* run diverge from its baseline?".
The flash-exploration ladder asks a different question: across N independent attempts at the
same task, how different are they from *one another*? This module is the pairwise
generalization of the basin primitives.

It deliberately defines **no new divergence math**. Architecture, structure, and novelty are
imported from ``basin`` so a fix to the basin metric can never leave a second, stale copy
behind — there is exactly one implementation of each axis.

**The normalization contract (frozen after four adversarial-review rounds).** Only
PARSER-BACKED Python is scored. Parseable Python is canonicalized through ``ast`` (comments,
whitespace, and formatting vanish); the ``run.py`` multi-file ``solution_code`` blob
(``# === <relpath> ===`` headers) is split and each file parsed. Any source that cannot be
parsed is **UNSCORED**: :func:`pairwise_divergence` returns null axes with ``scored: False``
and ``reason: "unsupported_source"`` — never a number that could be wrong in either direction
(a cosmetically-changed pair reading as divergence, or a semantically-changed pair reading as
zero). Heuristic normalization of arbitrary languages was tried and abandoned: every layer
created the next bypass. The ladder's subject is Python, which this contract covers;
:func:`portfolio_diversity` reports ``unsupported_pairs`` / ``unsupported_fraction`` so an
unscored sample is visible, never silently averaged.

Null-not-zero: every mean/max is ``None`` when there is no SCORED pair to average over.
``coverage`` describes the portfolio size (``empty``/``single``/``full``); when every pair is
unsupported the aggregates are ``None`` and ``unsupported_fraction`` is ``1.0``.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from agentic_dynamics.measurement.basin import (
    _architecture_divergence,
    _compute_novelty,
    _structure_divergence,
)

# Public aliases — the basin primitives are the single source of the divergence math. The
# portfolio functions below call through these names, so there is exactly one copy of each axis.
architecture_divergence = _architecture_divergence
structure_divergence = _structure_divergence
compute_novelty = _compute_novelty

# Composite weights, named so the preregistration's `D_c = 0.4·arch + 0.3·struct + 0.3·novelty`
# and this code cannot drift apart silently. These are the basin escape weights (``basin.py``).
ARCHITECTURE_WEIGHT = 0.4
STRUCTURE_WEIGHT = 0.3
NOVELTY_WEIGHT = 0.3

#: A pair counts as "distinct" once its composite divergence reaches this value. The
#: preregistration registers this threshold (flash_exploration_preregistration.md §4).
DEFAULT_DISTINCT_THRESHOLD = 0.5

#: The stable per-file header ``run.py`` writes into the concatenated ``solution_code`` blob.
_BLOB_HEADER = re.compile(r"^# === .+ ===$", re.MULTILINE)

__all__ = [
    "PortfolioDiversity",
    "architecture_divergence",
    "compute_novelty",
    "pairwise_divergence",
    "portfolio_diversity",
    "structure_divergence",
]


def _count_loc(code: str) -> int:
    """Count executable lines the way ``solution.evaluate_solution`` does."""
    return len(
        [line for line in code.split("\n") if line.strip() and not line.strip().startswith("#")]
    )


def _split_source_blob(code: str) -> list[str] | None:
    """Split a ``run.py`` multi-file ``solution_code`` blob into its file bodies.

    Returns ``None`` when the text carries no ``# === <relpath> ===`` headers (not a blob).
    """
    headers = list(_BLOB_HEADER.finditer(code))
    if not headers:
        return None
    bodies: list[str] = []
    for index, header in enumerate(headers):
        start = header.end()
        end = headers[index + 1].start() if index + 1 < len(headers) else len(code)
        bodies.append(code[start:end].strip("\n"))
    return bodies


def _python_canonical(code: str) -> str | None:
    """The AST-canonical form of parseable Python, or ``None`` when the source is unsupported.

    Every file of a multi-file blob must parse; one unparseable file makes the whole sample
    unsupported. An empty/whitespace-only string parses (to nothing) and is supported.
    """
    try:
        return ast.unparse(ast.parse(code))
    except (SyntaxError, ValueError, TypeError):
        pass
    parts = _split_source_blob(code)
    if parts is None:
        return None
    canonical_parts: list[str] = []
    for part in parts:
        try:
            canonical_parts.append(ast.unparse(ast.parse(part)))
        except (SyntaxError, ValueError, TypeError):
            return None
    return "\n".join(canonical_parts)


def _normalize_source(code: str) -> str | None:
    """The canonical form of one sample, or ``None`` when the source is unsupported."""
    return _python_canonical(code)


def pairwise_divergence(a: str, b: str) -> dict[str, Any]:
    """Divergence between two solutions across the three basin axes plus their composite.

    Two parseable-Python samples are canonicalized (comments/whitespace/formatting removed) and
    scored; identical canonicals are a hard zero. If either sample is not parseable Python the
    pair is UNSUPPORTED — every axis is ``None`` and ``scored`` is ``False``; no number is
    invented (the review-4 A1 / review-5 F1-F2 false-zero and inflation classes are impossible
    by construction).
    """
    canonical_a = _python_canonical(a)
    canonical_b = _python_canonical(b)
    if canonical_a is None or canonical_b is None:
        return {
            "novelty": None,
            "architecture_divergence": None,
            "structure_divergence": None,
            "composite": None,
            "scored": False,
            "reason": "unsupported_source",
        }
    if canonical_a == canonical_b:
        return {
            "novelty": 0.0,
            "architecture_divergence": 0.0,
            "structure_divergence": 0.0,
            "composite": 0.0,
            "scored": True,
            "reason": "",
        }

    arch = architecture_divergence(canonical_a, canonical_b)
    struct = structure_divergence(
        _count_loc(canonical_a), _count_loc(canonical_b), canonical_a, canonical_b
    )
    novelty = compute_novelty(canonical_a, canonical_b)
    composite = ARCHITECTURE_WEIGHT * arch + STRUCTURE_WEIGHT * struct + NOVELTY_WEIGHT * novelty
    return {
        "novelty": novelty,
        "architecture_divergence": arch,
        "structure_divergence": struct,
        "composite": composite,
        "scored": True,
        "reason": "",
    }


@dataclass(frozen=True)
class PortfolioDiversity:
    """The aggregate diversity of a portfolio of attempts.

    Attributes:
        n: Number of samples.
        n_pairs: Number of unordered pairs compared (``n·(n−1)/2``).
        n_scored_pairs: Pairs scored (both samples parseable Python).
        unsupported_pairs: Pairs whose samples could not be parsed — reported, never averaged.
        coverage: ``"empty"`` (n=0), ``"single"`` (n=1), or ``"full"`` (n≥2) — the size case.
        unsupported_fraction: ``unsupported_pairs / n_pairs``, or ``None`` when there are no
            pairs.
        mean_novelty: Mean pairwise novelty over SCORED pairs, or ``None``.
        mean_architecture_divergence: As above, over scored pairs.
        mean_structure_divergence: As above, over scored pairs.
        mean_composite: The preregistration's ``D_c`` — over scored pairs, or ``None``.
        max_composite: Largest scored-pair composite, or ``None``.
        distinct_fraction: Fraction of SCORED pairs at/above ``threshold``, or ``None``.
    """

    n: int
    n_pairs: int
    n_scored_pairs: int
    unsupported_pairs: int
    coverage: str
    unsupported_fraction: float | None
    mean_novelty: float | None
    mean_architecture_divergence: float | None
    mean_structure_divergence: float | None
    mean_composite: float | None
    max_composite: float | None
    distinct_fraction: float | None

    def to_dict(self) -> dict[str, Any]:
        """Serialize with the same 4-decimal rounding basin uses (``None`` passes through)."""
        return {
            "n": self.n,
            "n_pairs": self.n_pairs,
            "n_scored_pairs": self.n_scored_pairs,
            "unsupported_pairs": self.unsupported_pairs,
            "coverage": self.coverage,
            "unsupported_fraction": _round_or_none(self.unsupported_fraction),
            "mean_novelty": _round_or_none(self.mean_novelty),
            "mean_architecture_divergence": _round_or_none(self.mean_architecture_divergence),
            "mean_structure_divergence": _round_or_none(self.mean_structure_divergence),
            "mean_composite": _round_or_none(self.mean_composite),
            "max_composite": _round_or_none(self.max_composite),
            "distinct_fraction": _round_or_none(self.distinct_fraction),
        }


def _round_or_none(value: float | None) -> float | None:
    """Round a measured value to 4 decimals; pass ``None`` through untouched."""
    return None if value is None else round(value, 4)


def _mean(values: list[float]) -> float:
    """Arithmetic mean of a non-empty list (callers guarantee non-emptiness)."""
    return sum(values) / len(values)


def portfolio_diversity(
    samples: Sequence[str],
    *,
    threshold: float = DEFAULT_DISTINCT_THRESHOLD,
) -> PortfolioDiversity:
    """Aggregate pairwise divergence across a portfolio of solution samples.

    Args:
        samples: The solutions (typically concatenated ``solution_code``) to compare.
        threshold: A SCORED pair is "distinct" once its composite reaches this value; the
            fraction of such pairs (over scored pairs) is reported as ``distinct_fraction``.

    Returns:
        A frozen :class:`PortfolioDiversity`. Aggregates are ``None`` when there is no scored
        pair to aggregate over; unsupported pairs are counted, never averaged.
    """
    n = len(samples)
    n_pairs = n * (n - 1) // 2
    coverage = "empty" if n == 0 else "single" if n == 1 else "full"

    if n < 2:
        return PortfolioDiversity(
            n=n,
            n_pairs=n_pairs,
            n_scored_pairs=0,
            unsupported_pairs=0,
            coverage=coverage,
            unsupported_fraction=None,
            mean_novelty=None,
            mean_architecture_divergence=None,
            mean_structure_divergence=None,
            mean_composite=None,
            max_composite=None,
            distinct_fraction=None,
        )

    pairs = [pairwise_divergence(samples[i], samples[j]) for i in range(n) for j in range(i + 1, n)]
    scored = [p for p in pairs if p["scored"]]
    unsupported = len(pairs) - len(scored)

    if not scored:
        # Every pair unmeasured — report the coverage, fabricate nothing (null-not-zero).
        return PortfolioDiversity(
            n=n,
            n_pairs=n_pairs,
            n_scored_pairs=0,
            unsupported_pairs=unsupported,
            coverage=coverage,
            unsupported_fraction=unsupported / n_pairs,
            mean_novelty=None,
            mean_architecture_divergence=None,
            mean_structure_divergence=None,
            mean_composite=None,
            max_composite=None,
            distinct_fraction=None,
        )

    composites = [p["composite"] for p in scored]
    distinct_pairs = sum(1 for c in composites if c >= threshold)
    return PortfolioDiversity(
        n=n,
        n_pairs=n_pairs,
        n_scored_pairs=len(scored),
        unsupported_pairs=unsupported,
        coverage=coverage,
        unsupported_fraction=unsupported / n_pairs,
        mean_novelty=_mean([p["novelty"] for p in scored]),
        mean_architecture_divergence=_mean([p["architecture_divergence"] for p in scored]),
        mean_structure_divergence=_mean([p["structure_divergence"] for p in scored]),
        mean_composite=_mean(composites),
        max_composite=max(composites),
        distinct_fraction=distinct_pairs / len(scored),
    )
