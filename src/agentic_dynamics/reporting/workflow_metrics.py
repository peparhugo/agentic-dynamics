"""Shared workflow-metric primitives (step 7 extraction: script + Control Room P8).

The pinned ``sla_behavior`` metric — "SLA = the timeouts/deadline breaches / total" — was
computed only inside ``scripts/aggregate_workflow_metrics.py`` (the website pipeline). Step 7's
P8 ``sla_queue`` projection computes the SAME metric on demand for the Control Room, so the
computation moves here: one definition, two consumers (the same pattern as ``grit_metric``).

The breach semantics are the runner's structured per-phase fields (``BREACH_FIELDS``): a
non-empty evidence dict is a measured breach; ``None`` is "no breach recorded". The metric is
measurable ONLY over phases whose ledger actually recorded the fields — a pre-hardening ledger
omits them entirely, and "absent key" must not be read as "zero breaches". That is why
:func:`breach_view` exists: the recorded/absent distinction survives normalization.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

#: The runner's structured per-phase breach fields. ``stall_evidence`` is the phase-watchdog
#: timeout; the three gates are the mechanical commit/deploy/relabel refusals.
BREACH_FIELDS = ("stall_evidence", "deploy_gate", "commit_gate", "relabel_gate")

#: The pinned metric definition, verbatim (workflow_metrics.yaml §3).
SLA_BEHAVIOR_DEFINITION = "SLA = the timeouts/deadline breaches / total"


def breach_view(raw_phase: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw phase dict into the breach view the SLA computation consumes.

    ``breach_fields_recorded`` is True only when the ledger carried at least one of the four
    fields; the four values are passed through untouched (the caller may coerce non-dicts).
    """
    return {
        "breach_fields_recorded": any(k in raw_phase for k in BREACH_FIELDS),
        "stall_evidence": raw_phase.get("stall_evidence"),
        "deploy_gate": raw_phase.get("deploy_gate"),
        "commit_gate": raw_phase.get("commit_gate"),
        "relabel_gate": raw_phase.get("relabel_gate"),
    }


def _is_breach(evidence: Any) -> bool:
    """A breach is a non-empty evidence dict (the runner writes ``None`` for no breach)."""
    return isinstance(evidence, dict) and bool(evidence)


def sla_behavior(views: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    """The pinned SLA value dict, or ``None`` when no view recorded the breach fields.

    ``None`` is the not-measurable signal (the caller reports the missing fields); it is NOT
    a zero-breach reading. Rates are over the phases that recorded the fields only.
    """
    recorded = [v for v in views if v.get("breach_fields_recorded")]
    if not recorded:
        return None
    stall = sum(1 for v in recorded if _is_breach(v.get("stall_evidence")))
    deploy = sum(1 for v in recorded if _is_breach(v.get("deploy_gate")))
    commit = sum(1 for v in recorded if _is_breach(v.get("commit_gate")))
    relabel = sum(1 for v in recorded if _is_breach(v.get("relabel_gate")))
    total = len(recorded)
    return {
        "total_phases_with_breach_fields": total,
        "timeout_breaches": stall,
        "gate_breaches": deploy + commit + relabel,
        "breakdown": {
            "stall": stall,
            "deploy_gate": deploy,
            "commit_gate": commit,
            "relabel_gate": relabel,
        },
        "timeout_breach_rate": round(stall / total, 6) if total else None,
    }
