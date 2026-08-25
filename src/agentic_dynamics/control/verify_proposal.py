"""The ``verify_code_change/v1`` shadow-proposal seam (cap_2a p1).

A *proposal* is the adaptive verifier's prediction for ONE analyzed code change — its
``{verify, rework, continue}`` action, a proposed verification ``depth``, and the bounded
symbol ``scope`` the action would apply to — recorded BEFORE the baseline's outcome is known so
campaign 2a can later score the proposal against the outcome the baseline actually produced
(design §6: ``cap_evidence_integrity_design.md``; spec ``workflows/repository/cap_2a_shadow_calibration.yaml``).

This module is deliberately **shadow-only and artifact-only**. It has ZERO call sites that arm
actuation, publish a control event, flip ``control_route``, or trigger rework:

* ``record_verify_proposal`` writes ONE durable JSON artifact (``<proposal_id>.json``) to a
  dedicated proposals directory and returns the path — it never calls
  ``knowledge_stream.publish_event``, never builds an ``actuation`` record, never touches the
  registry/stream. A proposal is *measurement*, not actuation: it is distinguishable from a real
  actuation by its own schema (``schema_version``) and by the ``applied: false`` stamp — NOT by
  where it lives.
* ``validate_verify_proposal`` enforces ``applied is False`` as a hard schema invariant: a
  proposal that claims to have been applied is REFUSED. There is no code path here that can
  stamp ``applied=True``.

The "refuse to run" contract (spec hard-rule 2 + the p3 prompt): :func:`record_verify_proposal`
and :func:`emit_verify_proposal` RAISE ``ValueError`` on any validation failure — they do NOT
degrade to a silent no-op like the best-effort shadow *decision* recorder
(``rules.record_shadow_decision``) does. A later campaign cell MUST catch that refusal and stop,
never hand-author a proposal past a failing seam. This is deliberate: the whole point of the seam
is that proposals are machine-derived + machine-validated; a cell that cannot emit+validate a
proposal is a broken cell, and proceeding with a hand-written proposal would corrupt the
calibration dataset.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentic_dynamics.control.decisions import ExpectedEffect
from agentic_dynamics.core.paths import PROJECT_ROOT

#: The proposal record's own schema version. Distinct from ``CONTRACT_VERSION`` (the
#: ``verify_code_change`` decision contract this proposal is made FOR): a record carries both, so
#: a reader can tell "what shape is this JSON" apart from "which contract was it validated
#: against" — the same two-level versioning ``decisions.ControlDecision`` uses
#: (``decision_type`` + ``contract_version``).
PROPOSAL_SCHEMA_VERSION = "verify_code_change_proposal/v1"

#: The decision contract this proposal is validated against (``experiments/contexts/verify_code_change.yaml``).
CONTRACT_VERSION = "verify_code_change/v1"

#: The shadow proposal action vocabulary (mirrors the contract's ``allowed_actions``). Never a
#: superset of ``decisions.AUTOMATABLE_ACTIONS`` — every action here is proposal-only.
PROPOSAL_ACTIONS: frozenset[str] = frozenset({"verify", "rework", "continue"})

#: ``code_change_risk`` at or above this value (with no measured critical issues) proposes
#: ``verify`` rather than ``continue`` — the v1 calibration knee, deliberately simple and
#: documented as a ``[H]`` policy constant, not a measured threshold (measure-before-policy).
VERIFY_RISK_THRESHOLD = 0.2

#: The default durable-artifact directory. Proposals are NOT knowledge records, so they do not
#: live in ``KB_ARTIFACT_DIR`` (which is reserved for the registry-addressed knowledge plane);
#: they are campaign artifacts the p3/p4 cells cite by path + SHA256.
PROPOSAL_ARTIFACT_DIR = PROJECT_ROOT / "experiments" / "results" / "proposals"

#: Legal ``ExpectedEffect.direction`` values — the falsifiable prediction vocabulary
#: ``decisions.ExpectedEffect`` already declares.
_EFFECT_DIRECTIONS = frozenset({"increase", "decrease", "unchanged"})


@dataclass(frozen=True)
class VerifyProposal:
    """A typed, versioned, validated shadow proposal for ONE analyzed change (cap_2a p1).

    The field order mirrors the spec's own required field list (p1 SHAPE, verbatim):
    ``proposal_id, cell_id, baseline_revision, analyzed_revision, facts_used, action, depth,
    scope, expected_effect, applied, recorded_at`` — plus the two version fields (schema +
    contract). ``applied`` is ALWAYS ``False`` in shadow mode and the validator refuses anything
    else. Pure data — no live handles, no I/O.
    """

    proposal_id: str
    cell_id: str
    baseline_revision: str
    analyzed_revision: str
    facts_used: tuple[str, ...]
    action: str
    depth: int
    scope: tuple[str, ...]
    expected_effect: tuple[ExpectedEffect, ...]
    applied: bool = False
    recorded_at: str = ""
    schema_version: str = PROPOSAL_SCHEMA_VERSION
    contract_version: str = CONTRACT_VERSION
    proposed_by: str = "policy_rule:verify_code_change"


@dataclass(frozen=True)
class ProposalValidation:
    """The validator's verdict: ``valid`` plus every refusal reason (empty when admitted)."""

    valid: bool
    errors: tuple[str, ...]


def proposal_id_of(
    *,
    cell_id: str,
    baseline_revision: str,
    analyzed_revision: str,
    action: str,
    recorded_at: str,
) -> str:
    """Deterministic identity for one proposal candidate.

    One identity per candidate (folding the proposal time), mirroring
    ``rules._decision_id`` / ``actuation_ingestion._actuation_id``: two proposals for the same
    cell+revision with different actions or times are independent records, never versions of
    each other. Content (facts/scope/depth) is deliberately NOT folded in — the id identifies the
    *candidate*, and the artifact body carries the content.
    """
    return hashlib.sha256(
        f"{cell_id}|{baseline_revision}|{analyzed_revision}|{action}|{recorded_at}".encode()
    ).hexdigest()[:16]


def _int_value(fact: Mapping[str, Any] | None) -> int | None:
    if fact is None:
        return None
    raw = fact.get("value")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _float_value(fact: Mapping[str, Any]) -> float:
    return float(fact.get("value"))


def _risk_depth(risk: float) -> int:
    """The proposed verification depth for a ``verify`` action — a simple monotone mapping of
    ``code_change_risk`` to ``{1, 2, 3}`` (v1, deliberately not fitted to any data)."""
    if risk < 0.15:
        return 1
    if risk < 0.3:
        return 2
    return 3


def _effects(action: str) -> tuple[ExpectedEffect, ...]:
    """The falsifiable prediction each action makes, recorded BEFORE the outcome is known.

    ``rework`` predicts the measured critical-issue counts fall; ``verify`` predicts the LSP
    error count falls; ``continue`` predicts the risk stays put (the null proposal).
    """
    if action == "rework":
        return (
            ExpectedEffect("new_sonar_critical_count", "decrease", None, "next_phase"),
            ExpectedEffect("new_lsp_error_count", "decrease", None, "next_phase"),
        )
    if action == "verify":
        return (ExpectedEffect("new_lsp_error_count", "decrease", None, "next_phase"),)
    return (ExpectedEffect("code_change_risk", "unchanged", None, "next_phase"),)


def build_verify_proposal(
    *,
    facts: Iterable[Mapping[str, Any]],
    cell_id: str,
    baseline_revision: str,
    analyzed_revision: str,
    scope: Iterable[str] = (),
    recorded_at: str = "",
    proposed_by: str = "policy_rule:verify_code_change",
) -> VerifyProposal:
    """Derive ONE shadow proposal from a phase's de-typed ``code_change_facts`` (cap_2a p1).

    Pure and deterministic: the same facts + revisions yield a byte-identical proposal. The
    action/depth rule is deliberately simple — a first, measurable baseline, never front-loaded
    sophistication (the ``route_next_job_v1`` discipline):

    * a change whose ``code_change_risk`` is NOT measurable, or whose typed delta / parse
      coverage is absent, is REFUSED here (``ValueError``) — the contract's own
      ``on_missing: halt`` facts (``changed_symbol_count``, ``ast_parse_coverage``,
      ``code_change_risk``) are required for a valid proposal, never guessed.
    * measured critical issues (``new_sonar_critical_count > 0`` or ``new_lsp_error_count > 0``)
      → ``rework``, depth 3, scope = the bounded neighborhood.
    * otherwise ``changed_symbol_count == 0`` → ``continue``, depth 0, empty scope.
    * otherwise ``code_change_risk >= VERIFY_RISK_THRESHOLD`` → ``verify``, depth = the risk
      mapping, scope = the bounded neighborhood.
    * otherwise → ``continue`` (low-risk change), depth 0, empty scope.

    ``facts_used`` records every predicate the proposal saw (the values themselves live in the
    phase's ``change_analysis`` ledger row; this is the audit pointer, mirroring
    ``ControlDecision.facts_used``'s "which facts led here" purpose). ``proposed_by`` is recorded
    for provenance but is NOT folded into ``proposal_id``.
    """
    by: dict[str, Mapping[str, Any]] = {}
    for fact in facts:
        predicate = str(fact.get("predicate") or "")
        if predicate:
            by[predicate] = fact

    for required in ("changed_symbol_count", "ast_parse_coverage", "code_change_risk"):
        if required not in by:
            raise ValueError(
                f"cannot propose verify_code_change: required fact {required!r} not measured "
                "(contract on_missing: halt) — refusing rather than guessing"
            )
    try:
        changed = int(by["changed_symbol_count"].get("value"))
        risk = _float_value(by["code_change_risk"])
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"cannot propose verify_code_change: unparseable fact value ({exc})"
        ) from exc

    criticals = _int_value(by.get("new_sonar_critical_count"))
    errors = _int_value(by.get("new_lsp_error_count"))
    scope_tuple = tuple(scope)

    has_critical = (criticals is not None and criticals > 0) or (errors is not None and errors > 0)
    if has_critical:
        action, depth, out_scope = "rework", 3, scope_tuple
    elif changed == 0:
        action, depth, out_scope = "continue", 0, ()
    elif risk >= VERIFY_RISK_THRESHOLD:
        action, depth, out_scope = "verify", _risk_depth(risk), scope_tuple
    else:
        action, depth, out_scope = "continue", 0, ()

    proposal_id = proposal_id_of(
        cell_id=cell_id,
        baseline_revision=baseline_revision,
        analyzed_revision=analyzed_revision,
        action=action,
        recorded_at=recorded_at,
    )
    return VerifyProposal(
        proposal_id=proposal_id,
        cell_id=cell_id,
        baseline_revision=baseline_revision,
        analyzed_revision=analyzed_revision,
        facts_used=tuple(sorted(by)),
        action=action,
        depth=depth,
        scope=out_scope,
        expected_effect=_effects(action),
        applied=False,
        recorded_at=recorded_at,
        proposed_by=proposed_by,
    )


def proposal_payload(proposal: VerifyProposal) -> dict[str, Any]:
    """The proposal's JSON-safe body — the durable artifact's full content, self-describing."""
    return {
        "schema_version": proposal.schema_version,
        "contract_version": proposal.contract_version,
        "proposal_id": proposal.proposal_id,
        "cell_id": proposal.cell_id,
        "baseline_revision": proposal.baseline_revision,
        "analyzed_revision": proposal.analyzed_revision,
        "facts_used": list(proposal.facts_used),
        "action": proposal.action,
        "depth": proposal.depth,
        "scope": list(proposal.scope),
        "expected_effect": [
            {
                "predicate": e.predicate,
                "direction": e.direction,
                "magnitude": e.magnitude,
                "horizon": e.horizon,
            }
            for e in proposal.expected_effect
        ],
        "applied": proposal.applied,
        "recorded_at": proposal.recorded_at,
        "proposed_by": proposal.proposed_by,
    }


def validate_verify_proposal(
    proposal: VerifyProposal,
    *,
    contract: Any = None,
) -> ProposalValidation:
    """Schema + contract validation. ``applied is False`` is a HARD invariant (shadow mode).

    Deterministic and total. The checks are structural (all required fields present and of the
    right type), versioned (both ``schema_version`` and ``contract_version`` must match), and
    contractual (the action must be in the contract's ``allowed_actions`` when a contract is
    supplied). ``applied`` must be exactly ``False`` — there is no shadow proposal whose
    ``applied`` is truthy, and refusing it is the seam's own enforcement of hard-rule 2
    ("APPLY STAYS OFF").
    """
    errors: list[str] = []

    if proposal.schema_version != PROPOSAL_SCHEMA_VERSION:
        errors.append(f"schema_version {proposal.schema_version!r} != {PROPOSAL_SCHEMA_VERSION!r}")
    if proposal.contract_version != CONTRACT_VERSION:
        errors.append(f"contract_version {proposal.contract_version!r} != {CONTRACT_VERSION!r}")
    if not proposal.proposal_id:
        errors.append("proposal_id is empty")
    if not proposal.cell_id:
        errors.append("cell_id is empty")
    if not proposal.baseline_revision:
        errors.append("baseline_revision is empty")
    if not proposal.analyzed_revision:
        errors.append("analyzed_revision is empty")
    if proposal.action not in PROPOSAL_ACTIONS:
        errors.append(
            f"action {proposal.action!r} is not in the shadow proposal vocabulary "
            f"{sorted(PROPOSAL_ACTIONS)}"
        )
    elif contract is not None and proposal.action not in getattr(contract, "allowed_actions", ()):
        errors.append(
            f"action {proposal.action!r} is not in the contract's allowed_actions "
            f"{getattr(contract, 'allowed_actions', ())}"
        )
    if not isinstance(proposal.depth, int) or proposal.depth < 0:
        errors.append(f"depth {proposal.depth!r} is not a non-negative int")
    if not all(isinstance(s, str) and s for s in proposal.scope):
        errors.append("scope must be a sequence of non-empty strings")
    if not all(isinstance(f, str) and f for f in proposal.facts_used):
        errors.append("facts_used must be a sequence of non-empty strings")
    for effect in proposal.expected_effect:
        if effect.direction not in _EFFECT_DIRECTIONS:
            errors.append(f"expected_effect direction {effect.direction!r} is not legal")
        if not effect.predicate or not effect.horizon:
            errors.append("expected_effect must carry predicate and horizon")
    if proposal.applied is not False:
        errors.append("applied must be exactly False — a shadow proposal is never applied")
    if not proposal.recorded_at:
        errors.append("recorded_at is empty")

    return ProposalValidation(valid=not errors, errors=tuple(errors))


def record_verify_proposal(
    proposal: VerifyProposal,
    *,
    artifact_dir: Path = PROPOSAL_ARTIFACT_DIR,
    contract: Any = None,
) -> Path:
    """Validate + durably persist ONE shadow proposal as a plain JSON artifact. Refuses loudly.

    Artifact-only by construction: this writes ``<proposal_id>.json`` and returns its path; it
    NEVER publishes an event, NEVER builds an actuation record, NEVER flips ``control_route``,
    and NEVER triggers rework. On a validation refusal it raises ``ValueError`` (the "refuse to
    run" contract — see the module docstring) rather than swallowing the failure and letting a
    caller proceed with a hand-authored proposal.
    """
    validation = validate_verify_proposal(proposal, contract=contract)
    if not validation.valid:
        raise ValueError(
            "verify_code_change proposal refused: " + "; ".join(validation.errors)
        )
    artifact_dir.mkdir(parents=True, exist_ok=True)
    path = artifact_dir / f"{proposal.proposal_id}.json"
    path.write_text(json.dumps(proposal_payload(proposal), indent=2, sort_keys=True))
    return path


def emit_verify_proposal(
    *,
    facts: Iterable[Mapping[str, Any]],
    cell_id: str,
    baseline_revision: str,
    analyzed_revision: str,
    scope: Iterable[str] = (),
    recorded_at: str = "",
    artifact_dir: Path = PROPOSAL_ARTIFACT_DIR,
    contract: Any = None,
) -> tuple[VerifyProposal, Path]:
    """Build + validate + record ONE shadow proposal in a single call (the seam entry point).

    The convenience for a campaign cell: it either returns ``(proposal, artifact_path)`` — both
    the machine-validated record and its durable artifact — or raises ``ValueError``, which the
    cell MUST treat as "refuse to run" (spec hard-rule 2 + p3 prompt). A proposal that cannot be
    emitted and validated means the seam is broken for this cell; proceeding would corrupt the
    calibration dataset, so there is no silent no-op path.
    """
    proposal = build_verify_proposal(
        facts=facts,
        cell_id=cell_id,
        baseline_revision=baseline_revision,
        analyzed_revision=analyzed_revision,
        scope=scope,
        recorded_at=recorded_at,
    )
    path = record_verify_proposal(proposal, artifact_dir=artifact_dir, contract=contract)
    return proposal, path
