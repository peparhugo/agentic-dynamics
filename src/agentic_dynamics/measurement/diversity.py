"""Portfolio-diversity measurement — how varied is a *set* of attempts?

``measure_basin_escape`` (``basin.py``) answers "did *this* run diverge from its baseline?".
The flash-exploration ladder asks a different question: across N independent attempts at the
same task, how different are they from *one another*? This module is the pairwise
generalization of the basin primitives.

It deliberately defines **no new divergence math**. Architecture, structure, and novelty are
imported from ``basin`` so a fix to the basin metric can never leave a second, stale copy
behind — there is exactly one implementation of each axis. Public aliases are exposed for
callers that do not want to reach into private names.

Two entry points:

* :func:`pairwise_divergence` — the three basin axes plus their registered composite
  (``0.4·arch + 0.3·struct + 0.3·novelty``, the basin escape weights and the preregistration's
  ``D_c`` definition) for one pair.
* :func:`portfolio_diversity` — the aggregate over every unordered pair of a sequence:
  means, max, a threshold-based ``distinct_fraction``, and a ``coverage`` verdict.

Null-not-zero: every mean/max is ``None`` when there is no pair to average over (``n < 2``).
An unmeasured portfolio statistic is not a measured zero. ``coverage`` says which case applies:
``empty`` (n=0), ``single`` (n=1), ``full`` (n≥2).
"""

from __future__ import annotations

import ast
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

__all__ = [
    "PortfolioDiversity",
    "architecture_divergence",
    "compute_novelty",
    "pairwise_divergence",
    "portfolio_diversity",
    "structure_divergence",
]


def _count_loc(code: str) -> int:
    """Count executable lines the way ``solution.evaluate_solution`` does.

    ``basin._structure_divergence`` takes two line counts rather than deriving them, so the
    caller must supply them. We mirror ``solution.py``'s definition (non-blank, non-comment
    lines) so a portfolio assembled from persisted ``solution_code`` counts lines identically
    to the run-time evaluation that produced it.
    """
    return len(
        [line for line in code.split("\n") if line.strip() and not line.strip().startswith("#")]
    )


def _strip_comments(code: str) -> str:
    """Remove ``#``/``//``/``/* */`` comments that sit OUTSIDE string literals.

    The g5 round-2 F1 finding: the line filter dropped whole comment lines only, so inline
    ``//`` and C block comments still raised the metric. A tiny scanner (not a parser) tracks
    single/double quotes and backslash escapes; everything from a comment marker to its end is
    removed. Contents of strings are preserved, so ``"http://x"`` survives.
    """
    out: list[str] = []
    i = 0
    n = len(code)
    quote: str | None = None
    while i < n:
        ch = code[i]
        if quote is not None:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(code[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
            out.append(ch)
            i += 1
            continue
        if ch == "#":
            while i < n and code[i] != "\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and code[i + 1] == "/":
            while i < n and code[i] != "\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and code[i + 1] == "*":
            i += 2
            while i < n and not (code[i] == "*" and i + 1 < n and code[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _normalize_source(code: str) -> str:
    """Strip formatting-only code so a cosmetic edit cannot read as divergence.

    The adversarial reviews (``g5_adversarial`` findings F3 then F1) measured whitespace-only,
    comment-only, and non-Python inline/block-comment pairs scoring nonzero composite
    divergence — churn a diversity metric must not reward. Python sources that parse are
    normalized through the AST (comments, blank lines, indentation style, and trailing
    whitespace all vanish). Non-Python or unparseable sources take comments out with
    :func:`_strip_comments` (string-aware, for ``#``, ``//``, and ``/* */``), then drop blank
    lines and strip line edges. Concatenated multi-file ``solution_code`` (the
    ``# === <relpath> ===`` headers make it unparseable as one module) takes this fallback.
    """
    try:
        return ast.unparse(ast.parse(code))
    except (SyntaxError, ValueError, TypeError):
        pass
    stripped = _strip_comments(code)
    lines: list[str] = []
    for line in stripped.splitlines():
        trimmed = line.strip()
        if trimmed:
            lines.append(trimmed)
    return "\n".join(lines)


def pairwise_divergence(a: str, b: str) -> dict[str, float]:
    """Divergence between two solutions across the three basin axes plus their composite.

    Args:
        a: One solution's source (typically the concatenated ``solution_code``).
        b: The other solution's source.

    Returns:
        ``{"novelty", "architecture_divergence", "structure_divergence", "composite"}`` with
        ``composite = 0.4·arch + 0.3·struct + 0.3·novelty``.

    Formatting is normalized away BEFORE any axis is scored (:func:`_normalize_source`): a
    whitespace-only or comment-only pair is a hard zero, so cosmetic churn cannot inflate the
    portfolio statistics the ladder's decision rule reads (the g5 F3 finding). Identity is a
    hard zero; the normalization also keeps the empty/whitespace case honest, because basin's
    neutral-prior novelty (0.5 when no 5-grams exist) would otherwise score two empty strings
    as divergent.
    """
    normalized_a = _normalize_source(a)
    normalized_b = _normalize_source(b)
    if normalized_a == normalized_b:
        return {
            "novelty": 0.0,
            "architecture_divergence": 0.0,
            "structure_divergence": 0.0,
            "composite": 0.0,
        }

    arch = architecture_divergence(normalized_a, normalized_b)
    struct = structure_divergence(
        _count_loc(normalized_a), _count_loc(normalized_b), normalized_a, normalized_b
    )
    novelty = compute_novelty(normalized_a, normalized_b)
    composite = ARCHITECTURE_WEIGHT * arch + STRUCTURE_WEIGHT * struct + NOVELTY_WEIGHT * novelty
    return {
        "novelty": novelty,
        "architecture_divergence": arch,
        "structure_divergence": struct,
        "composite": composite,
    }


@dataclass(frozen=True)
class PortfolioDiversity:
    """The aggregate diversity of a portfolio of attempts.

    Frozen so a portfolio statistic is a value, not mutable state passed between analyses.

    Attributes:
        n: Number of samples.
        n_pairs: Number of unordered pairs compared (``n·(n−1)/2``).
        mean_novelty: Mean pairwise novelty, or ``None`` when ``n < 2``.
        mean_architecture_divergence: Mean pairwise architecture divergence, or ``None``.
        mean_structure_divergence: Mean pairwise structure divergence, or ``None``.
        mean_composite: Mean pairwise composite (the preregistration's ``D_c``), or ``None``.
        max_composite: The single largest pairwise composite, or ``None``.
        distinct_fraction: Fraction of pairs whose composite reaches ``threshold``, or
            ``None`` when there are no pairs (``n < 2``).
        coverage: ``"empty"`` (n=0), ``"single"`` (n=1), or ``"full"`` (n≥2) — which case
            the portfolio is in, so a ``None`` mean is read as coverage, never as a zero.
    """

    n: int
    n_pairs: int
    mean_novelty: float | None
    mean_architecture_divergence: float | None
    mean_structure_divergence: float | None
    mean_composite: float | None
    max_composite: float | None
    distinct_fraction: float | None
    coverage: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize with the same 4-decimal rounding basin uses (``None`` passes through)."""
        return {
            "n": self.n,
            "n_pairs": self.n_pairs,
            "mean_novelty": _round_or_none(self.mean_novelty),
            "mean_architecture_divergence": _round_or_none(self.mean_architecture_divergence),
            "mean_structure_divergence": _round_or_none(self.mean_structure_divergence),
            "mean_composite": _round_or_none(self.mean_composite),
            "max_composite": _round_or_none(self.max_composite),
            "distinct_fraction": _round_or_none(self.distinct_fraction),
            "coverage": self.coverage,
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
        samples: The solutions (typically concatenated source strings) to compare.
        threshold: A pair is "distinct" once its composite reaches this value; the fraction of
            such pairs is reported as ``distinct_fraction``.

    Returns:
        A frozen :class:`PortfolioDiversity`. Means, ``max_composite``, and
        ``distinct_fraction`` are ``None`` when ``n < 2`` — there is no pair to aggregate.
    """
    n = len(samples)
    n_pairs = n * (n - 1) // 2
    coverage = "empty" if n == 0 else "single" if n == 1 else "full"

    if n < 2:
        # No pair exists: every aggregate is unmeasured, not zero (null-not-zero).
        return PortfolioDiversity(
            n=n,
            n_pairs=n_pairs,
            mean_novelty=None,
            mean_architecture_divergence=None,
            mean_structure_divergence=None,
            mean_composite=None,
            max_composite=None,
            distinct_fraction=None,
            coverage=coverage,
        )

    pairs = [pairwise_divergence(samples[i], samples[j]) for i in range(n) for j in range(i + 1, n)]
    composites = [p["composite"] for p in pairs]
    distinct_pairs = sum(1 for c in composites if c >= threshold)

    return PortfolioDiversity(
        n=n,
        n_pairs=n_pairs,
        mean_novelty=_mean([p["novelty"] for p in pairs]),
        mean_architecture_divergence=_mean([p["architecture_divergence"] for p in pairs]),
        mean_structure_divergence=_mean([p["structure_divergence"] for p in pairs]),
        mean_composite=_mean(composites),
        max_composite=max(composites),
        distinct_fraction=distinct_pairs / n_pairs,
        coverage=coverage,
    )
