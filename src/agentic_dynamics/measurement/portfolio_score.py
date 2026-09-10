"""Portfolio scoring from persisted run results — the ladder's production measurement path.

The g5 round-2 findings F2/F4: ``portfolio_diversity`` existed but no non-test caller computed
it from result JSON, and a null ``solution_code`` had no downstream enforcement. This module is
that caller. It loads ``run.py`` result files, groups attempts by condition, **excludes**
attempts with no collectable source (``solution_code is None``) while **reporting the excluded
count**, and returns a portfolio score with its coverage, threshold, input hashes, and code sha.

Null-not-zero applies at two levels: an excluded attempt is never scored as empty source, and
a group with fewer than two scored attempts reports unmeasured aggregates (``None``) through
:class:`~agentic_dynamics.measurement.diversity.PortfolioDiversity` — never a fabricated zero.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentic_dynamics.measurement.diversity import (
    DEFAULT_DISTINCT_THRESHOLD,
    PortfolioDiversity,
    portfolio_diversity,
)

__all__ = [
    "ConditionScore",
    "InputFile",
    "PortfolioScore",
    "load_result_file",
    "score_result_files",
]


@dataclass(frozen=True)
class InputFile:
    """One consumed result file with its content hash (provenance for the score artifact)."""

    path: str
    sha256: str


@dataclass(frozen=True)
class ConditionScore:
    """One condition's portfolio: how many attempts existed, how many were scorable, and what
    the scorable ones measured. ``excluded_null_source`` is the count of attempts dropped for
    ``solution_code is None`` — the coverage denominator the F4 finding requires to be explicit.
    """

    condition: str
    n_attempts: int
    n_scored: int
    excluded_null_source: int
    diversity: PortfolioDiversity


@dataclass(frozen=True)
class PortfolioScore:
    """The scored portfolio of one result set: inputs, grouping, and per-condition scores."""

    generated_at: str
    code_sha: str
    threshold: float
    group_by: tuple[str, ...]
    inputs: tuple[InputFile, ...]
    conditions: tuple[ConditionScore, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "code_sha": self.code_sha,
            "threshold": self.threshold,
            "group_by": list(self.group_by),
            "inputs": [{"path": i.path, "sha256": i.sha256} for i in self.inputs],
            "conditions": [
                {
                    "condition": c.condition,
                    "n_attempts": c.n_attempts,
                    "n_scored": c.n_scored,
                    "excluded_null_source": c.excluded_null_source,
                    "diversity": c.diversity.to_dict(),
                }
                for c in self.conditions
            ],
        }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _code_sha(repo_root: Path | None) -> str:
    """The scored code's commit sha (best-effort; empty when git is unavailable)."""
    root = repo_root or Path(__file__).resolve().parents[3]
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, timeout=30
        )
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def load_result_file(path: Path | str) -> list[dict[str, Any]]:
    """Load one ``run.py`` result file — ``{"runs": [...]}`` or a bare list — as attempts."""
    payload = json.loads(Path(path).read_text())
    if isinstance(payload, dict):
        runs = payload.get("runs", [])
    elif isinstance(payload, list):
        runs = payload
    else:  # pragma: no cover - defensive: a malformed result file is loud, never silent
        raise ValueError(f"{path}: expected a result object with 'runs' or a bare list")
    return [r for r in runs if isinstance(r, dict)]


def _condition_key(run: dict[str, Any], group_by: Sequence[str]) -> str:
    """The condition label for one attempt: the declared grouping fields that are present."""
    parts = [f"{field}={run[field]}" for field in group_by if run.get(field) is not None]
    return "|".join(parts) if parts else "all"


def score_result_files(
    paths: Sequence[Path | str],
    *,
    group_by: Sequence[str] = ("operator", "strength"),
    threshold: float = DEFAULT_DISTINCT_THRESHOLD,
    repo_root: Path | str | None = None,
) -> PortfolioScore:
    """Score the portfolios in ``paths``: group by condition, exclude null-source attempts.

    Args:
        paths: ``run.py`` result JSON files to consume.
        group_by: The attempt fields that define a condition (default ``operator``/``strength``;
            fields absent from a run are omitted from its label).
        threshold: The distinctness threshold passed to :func:`portfolio_diversity`.
        repo_root: Repo root for the code-sha provenance (defaults to the package's repo).

    Returns:
        A :class:`PortfolioScore` whose per-condition entries carry the scored samples, the
        explicit null-source exclusion count, and the (possibly unmeasured) portfolio metrics.
    """
    resolved = [Path(p) for p in paths]
    inputs = tuple(InputFile(path=str(p), sha256=_sha256(p)) for p in resolved)

    grouped: dict[str, list[dict[str, Any]]] = {}
    for path in resolved:
        for run in load_result_file(path):
            grouped.setdefault(_condition_key(run, group_by), []).append(run)

    conditions: list[ConditionScore] = []
    for condition in sorted(grouped):
        runs = grouped[condition]
        samples = [r["solution_code"] for r in runs if isinstance(r.get("solution_code"), str)]
        excluded = sum(1 for r in runs if r.get("solution_code") is None)
        conditions.append(
            ConditionScore(
                condition=condition,
                n_attempts=len(runs),
                n_scored=len(samples),
                excluded_null_source=excluded,
                diversity=portfolio_diversity(samples, threshold=threshold),
            )
        )

    return PortfolioScore(
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        code_sha=_code_sha(Path(repo_root) if repo_root is not None else None),
        threshold=threshold,
        group_by=tuple(group_by),
        inputs=inputs,
        conditions=tuple(conditions),
    )
