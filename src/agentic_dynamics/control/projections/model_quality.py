"""P3 ``model_quality`` — Grit + first-pass + narration + coverage (d3 §5 P3).

The room's quality read model. Every metric reuses a canonical definition rather than
re-deriving one:

* **Grit** — ``G(s) = P(test_executed_success | perturbation_strength = s)`` via the ONE
  implementation in ``reporting.grit_metric`` (shared with ``scripts/lab_grit.py``), including
  its Wilson intervals and its ``MIN_CELLS_FOR_RATE`` small-sample rule.
* **first-pass** — the Rule 5 definition from the attempt ledger: first attempts
  (``attempt_number == 1``) that were accepted, over the eligible first attempts, plus the
  accepted rate over all eligible attempts. The runner writes ``attempt_number`` /
  ``accepted`` on the workflow-run ledger (``runtime/workflow_runner.py:AttemptRecord``).
* **narration** — the answer/explanation token split: ``explanation_ratio =
  explanation_tokens / (answer_tokens + explanation_tokens)``. Absent tokens stay ``None``,
  never 0.

The coverage discipline (d3 §9, "coverage before ratio") is structural: every metric carries
its ``n_total`` / ``n_eligible`` / ``coverage`` before any ratio, a zero denominator yields
``None`` with a named reason (never ``0.0``), and a field with no writer is rendered as an
explicit unknown (``flail``, G-05) rather than inferred.

Builders are pure over injected inputs; ``load_workflow_attempts`` is the module's only IO.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from agentic_dynamics.reporting.grit_metric import (
    MIN_CELLS_FOR_RATE,
    collect_cells,
    rate_row,
)

SCHEMA = "model-quality/v1"

#: The definitions each metric block is computed from — carried in the payload so a reader
#: never has to look them up and a reviewer can diff the definition against the lab's.
DEFINITIONS: dict[str, str] = {
    "grit": "G(s) = P(test_executed_success | perturbation_strength = s)",
    "first_pass": (
        "first_pass_rate = first attempts (attempt_number == 1) that were accepted / eligible "
        "first attempts; accepted_rate = accepted / eligible attempts"
    ),
    "narration": (
        "explanation_ratio = explanation_tokens / (answer_tokens + explanation_tokens)"
    ),
    "flail": "no named field exists (G-05) — reported as an explicit unknown, never inferred",
}

#: Per-metric evidence classes: grit is measured ([M], the cells are measured verdicts),
#: the ratios are computed over measured fields ([C]).
EVIDENCE = {"grit": "[M]", "first_pass": "[M]", "narration": "[C]", "flail": "[M]"}


def load_workflow_attempts(results_dir: Path) -> tuple[list[dict[str, Any]], int]:
    """Load per-attempt rows from the workflow run ledgers (the ``attempts`` arrays).

    Returns ``(rows, n_ledgers)``. Each row carries ``model``, ``attempt_number``,
    ``accepted``, ``status``, ``job_id``/``phase``, and the owning ``spec_name``. A missing
    directory is an honest empty population (the room renders it as such), never an error.
    """
    if not results_dir.is_dir():
        return [], 0
    rows: list[dict[str, Any]] = []
    n_ledgers = 0
    for path in sorted(results_dir.rglob("*.json")):
        try:
            import json

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
                    "phase": str(attempt.get("phase") or ""),
                    "model": str(attempt.get("model") or ""),
                    "attempt_number": attempt.get("attempt_number"),
                    "accepted": attempt.get("accepted"),
                    "status": str(attempt.get("status") or ""),
                }
            )
    return rows, n_ledgers


def _model_short(model: str) -> str:
    return model.split("/")[-1] if model else "unknown"


def _first_pass_block(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Rule 5 over one model's attempt rows, coverage first.

    Eligible = the attempt carries an integer ``attempt_number`` AND a boolean ``accepted``
    (the fields the definition consumes). A row missing either is counted in ``n_total`` but
    not in ``n_eligible`` — the difference is the coverage, reported before the rate.
    """
    total = len(rows)
    eligible = [
        r
        for r in rows
        if isinstance(r.get("attempt_number"), int) and isinstance(r.get("accepted"), bool)
    ]
    first_attempts = [r for r in eligible if r["attempt_number"] == 1]
    first_pass_ok = sum(1 for r in first_attempts if r["accepted"])
    accepted_ok = sum(1 for r in eligible if r["accepted"])
    rate = round(first_pass_ok / len(first_attempts), 4) if first_attempts else None
    accepted_rate = round(accepted_ok / len(eligible), 4) if eligible else None
    block: dict[str, Any] = {
        "definition": DEFINITIONS["first_pass"],
        "evidence_class": EVIDENCE["first_pass"],
        "n_total": total,
        "n_eligible": len(eligible),
        "coverage": round(len(eligible) / total, 4) if total else 0.0,
        "first_attempts": len(first_attempts),
        "first_pass_rate": rate,
        "accepted_rate": accepted_rate,
        "insufficient_support": len(first_attempts) < MIN_CELLS_FOR_RATE,
    }
    if rate is None:
        block["reason"] = (
            "no eligible first attempts (attempt_number == 1 with a boolean accepted)"
            if not first_attempts
            else "zero denominator"
        )
    return block


def _narration_block(cells: list[dict[str, Any]]) -> dict[str, Any]:
    """The answer/explanation split over one model's cells, coverage first."""
    total = len(cells)
    with_tokens = [
        c
        for c in cells
        if isinstance(c.get("answer_tokens"), int) and isinstance(c.get("explanation_tokens"), int)
    ]
    answer = sum(c["answer_tokens"] for c in with_tokens)
    explanation = sum(c["explanation_tokens"] for c in with_tokens)
    output_total = answer + explanation
    ratio = round(explanation / output_total, 4) if output_total else None
    block: dict[str, Any] = {
        "definition": DEFINITIONS["narration"],
        "evidence_class": EVIDENCE["narration"],
        "n_total": total,
        "n_eligible": len(with_tokens),
        "coverage": round(len(with_tokens) / total, 4) if total else 0.0,
        "answer_tokens": answer if with_tokens else None,
        "explanation_tokens": explanation if with_tokens else None,
        "explanation_ratio": ratio,
        "insufficient_support": len(with_tokens) < MIN_CELLS_FOR_RATE,
    }
    if ratio is None:
        block["reason"] = (
            "no cells carry the answer/explanation token split"
            if not with_tokens
            else "zero output tokens (cannot form a ratio)"
        )
    return block


def build_model_quality(
    findings: list[dict[str, Any]],
    stories: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    *,
    now: str | None = None,
    source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the model-quality payload. Pure given its inputs (``now`` is injected)."""
    cells, exclusions, _used, _excluded = collect_cells(findings, stories)

    by_model_cells: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for cell in cells:
        by_model_cells[cell["model"]].append(cell)

    by_model_attempts: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in attempts:
        by_model_attempts[_model_short(row.get("model", ""))].append(row)

    models = sorted(set(by_model_cells) | set(by_model_attempts))
    model_blocks: list[dict[str, Any]] = []
    for model in models:
        model_cells = by_model_cells.get(model, [])
        model_attempts = by_model_attempts.get(model, [])

        by_strength: dict[float, list[dict[str, Any]]] = defaultdict(list)
        for cell in model_cells:
            by_strength[cell["strength"]].append(cell)
        grit_rows = [
            rate_row(
                "strength",
                strength,
                sum(1 for c in items if c["success"]),
                len(items),
            )
            for strength, items in sorted(by_strength.items())
        ]
        overall = rate_row(
            "model",
            model,
            sum(1 for c in model_cells if c["success"]),
            len(model_cells),
        )

        model_blocks.append(
            {
                "model": model,
                "grit": {
                    "definition": DEFINITIONS["grit"],
                    "evidence_class": EVIDENCE["grit"],
                    "overall": overall,
                    "by_strength": grit_rows,
                },
                "first_pass": _first_pass_block(model_attempts),
                "narration": _narration_block(model_cells),
                "flail": {
                    "definition": DEFINITIONS["flail"],
                    "evidence_class": EVIDENCE["flail"],
                    "state": "unknown",
                    "reason": "no_writer",
                    "gap": "G-05",
                },
            }
        )

    resolved = len(findings) + len(stories)
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at": now,
        "source": dict(source or {}),
        "definitions": dict(DEFINITIONS),
        "population": {
            "resolved_cells": resolved,
            "eligible_cells": len(cells),
            "excluded_cells": sum(exclusions.values()),
            "exclusions": exclusions,
            "n_attempt_rows": len(attempts),
        },
        "models": model_blocks,
        "degraded": [],
    }
    return payload
