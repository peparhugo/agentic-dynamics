"""Lint workflow-v1 operational-workflow definitions against the authoring contract.

The authoring contract behind the Wave-3 ``workflow`` surface (``workflow new`` /
``workflow lint``): a NEW operational workflow is validated against
``workflows/schema/workflow-v1.schema.json`` (JSON Schema draft 2020-12) AND the
semantic rules below — rules no JSON Schema alone can express:

* **authored-status** — operational status (``status: running/completed/...``) is
  derived from run evidence ("completion follows the revision"), never authored.
  Any ``status`` key anywhere in the definition is rejected.
* **unknown-step-kind** — a step kind outside the closed vocabulary.
* **missing-concurrency** — a spec with no concurrency block, or a concurrency
  block with no policy.
* **mutating-without-verification** — a mutating step (an agent/task step under a
  write-capable scope) with no downstream gate/approval bound to it (its own
  candidate or a later candidate that builds on it).
* **promotion-without-gates** — a promotion whose requiredGates reference no real
  gate/approval step.
* **unbound-gate** — a gate/approval that resolves no candidate sha (no
  candidateFrom and no single mutating upstream), a candidateFrom that names a
  non-producing step, or an inline ``gate`` on a step that produces no candidate.
* **prompt-as-evidence** — a gate that gates a candidate (bound, or listed in
  requiredGates) whose only "evidence" is prompt text / an LLM executor rather
  than a machine executor (test|command). The gate evidence is the kind:test or
  verifier executor; prompt text is scaffolded instructions, never evidence.

The linter targets NEW and touched workflow-v1 documents only. The historical
ExperimentSpec corpus under ``workflows/repository|operations|research`` is a
different document kind (``is_workflow_v1_document`` is False for it) and is
never expected to pass — a corpus YAML is not a workflow-v1 definition.

Error codes are stable names a caller (CI, ``workflow lint``) can assert on.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

SCHEMA_PATH = Path(__file__).resolve().parent / "schema" / "workflow-v1.schema.json"

WORKFLOW_V1_KEYS = ("apiVersion", "kind", "metadata", "spec")

STEP_KINDS = ("agent", "task", "gate", "approval")
EXECUTORS = ("agent", "test", "command", "human")
SCOPES = (
    "research_readonly",
    "implementation",
    "review_readonly",
    "proposal_write",
    "adversarial_readonly",
)
CONCURRENCY_POLICIES = ("serial", "bounded", "parallel")
WORKSPACE_MODES = ("isolated", "shared", "readonly")
PROMOTION_STRATEGIES = ("squash-merge", "merge-commit", "fast-forward")
LIFECYCLES = ("development", "stable", "deprecated")

MUTATING_KINDS = frozenset({"agent", "task"})
VERIFIER_KINDS = frozenset({"gate", "approval"})
READONLY_SCOPES = frozenset({"research_readonly", "adversarial_readonly"})
WRITE_SCOPES = frozenset({"implementation", "review_readonly", "proposal_write"})
MACHINE_GATE_EXECUTORS = frozenset({"test", "command"})

# Named error codes (the contract's stable vocabulary).
AUTHORED_STATUS = "authored-status"
UNKNOWN_STEP_KIND = "unknown-step-kind"
MISSING_CONCURRENCY = "missing-concurrency"
MUTATING_WITHOUT_VERIFICATION = "mutating-without-verification"
PROMOTION_WITHOUT_GATES = "promotion-without-gates"
UNBOUND_GATE = "unbound-gate"
PROMPT_AS_EVIDENCE = "prompt-as-evidence"
DUPLICATE_STEP_ID = "duplicate-step-id"
UNKNOWN_STEP_REFERENCE = "unknown-step-reference"
STEP_DEPENDENCY_CYCLE = "step-dependency-cycle"
PROMOTION_CANDIDATE_NOT_PRODUCING = "promotion-candidate-not-producing"
SCHEMA_INVALID = "schema-invalid"

_SEMANTIC_CODES = {
    AUTHORED_STATUS,
    UNKNOWN_STEP_KIND,
    MISSING_CONCURRENCY,
    MUTATING_WITHOUT_VERIFICATION,
    PROMOTION_WITHOUT_GATES,
    UNBOUND_GATE,
    PROMPT_AS_EVIDENCE,
    DUPLICATE_STEP_ID,
    UNKNOWN_STEP_REFERENCE,
    STEP_DEPENDENCY_CYCLE,
    PROMOTION_CANDIDATE_NOT_PRODUCING,
}


@dataclass(frozen=True)
class Finding:
    """A single linter finding — a named error code plus its location."""

    code: str
    message: str
    path: str
    source: str = "semantic"

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message, "path": self.path}


@dataclass
class LintReport:
    """The outcome of linting one workflow-v1 document."""

    document: dict[str, Any]
    findings: list[Finding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.findings

    @property
    def codes(self) -> list[str]:
        return [f.code for f in self.findings]

    def has(self, code: str) -> bool:
        return any(f.code == code for f in self.findings)


def _validator() -> Draft202012Validator:
    with SCHEMA_PATH.open("r", encoding="utf-8") as fh:
        return Draft202012Validator(json.load(fh))


_VALIDATOR = _validator()


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def load_schema() -> dict[str, Any]:
    """Load the workflow-v1 schema as a dict (the authoring contract)."""
    with SCHEMA_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def is_workflow_v1_document(document: Any) -> bool:
    """True when the parsed document is shaped like a workflow-v1 definition.

    An ExperimentSpec (the historical corpus shape: ``name/question/workflow/
    phases`` with no apiVersion/kind/metadata/spec) is NOT a workflow-v1 document
    and is never linted as one.
    """
    return isinstance(document, dict) and all(k in document for k in WORKFLOW_V1_KEYS)


def load_document(text: str) -> Any:
    """Parse a workflow definition from YAML (or JSON) text."""
    return yaml.safe_load(text)


def lint_text(text: str) -> LintReport:
    """Lint a workflow-v1 definition given as YAML/JSON text."""
    return lint(load_document(text))


def lint_path(path: str | Path) -> LintReport:
    """Lint a workflow-v1 definition file (.yaml/.yml/.json)."""
    text = Path(path).read_text(encoding="utf-8")
    return lint_text(text)


# --------------------------------------------------------------------------- #
# Lint entry point
# --------------------------------------------------------------------------- #
def lint(document: Any) -> LintReport:
    """Validate a parsed workflow-v1 document: schema fields AND semantic rules.

    Returns a report; ``report.ok`` is True only when the document passes both the
    JSON-Schema structural contract and every semantic rule with zero findings.
    """
    if not isinstance(document, dict):
        return LintReport(document=document, findings=[])

    findings: list[Finding] = []
    findings.extend(_schema_findings(document))
    findings.extend(_semantic_findings(document))
    return LintReport(document=document, findings=_dedupe(findings))


# --------------------------------------------------------------------------- #
# Schema-field validation (draft 2020-12)
# --------------------------------------------------------------------------- #
def _schema_findings(document: dict[str, Any]) -> list[Finding]:
    errors = sorted(_VALIDATOR.iter_errors(document), key=lambda e: list(e.path))
    out: list[Finding] = []
    for err in errors:
        path = _pointer(err.absolute_path)
        code = _classify_schema_error(err)
        out.append(Finding(code=code, message=err.message, path=path, source="schema"))
    return out


def _classify_schema_error(err: Any) -> str:
    parts = [str(p) for p in err.absolute_path]
    message = err.message
    if "status" in parts:
        return AUTHORED_STATUS
    if "concurrency" in parts or ("required" in parts and "concurrency" in message):
        return MISSING_CONCURRENCY
    if parts and parts[-1] == "kind" and "steps" in parts:
        return UNKNOWN_STEP_KIND
    if "requiredGates" in parts or (err.validator == "required" and "requiredGates" in message):
        return PROMOTION_WITHOUT_GATES
    return SCHEMA_INVALID


# --------------------------------------------------------------------------- #
# Semantic rules
# --------------------------------------------------------------------------- #
def _semantic_findings(document: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(_find_authored_status(document))
    spec = document.get("spec")
    if not isinstance(spec, dict):
        return findings

    raw_steps = spec.get("steps")
    if not isinstance(raw_steps, list):
        return findings
    steps = [s for s in raw_steps if isinstance(s, dict)]

    workspace_mode = _workspace_mode(spec)
    by_id, duplicate = _steps_by_id(steps)
    findings.extend(_unknown_step_kind_findings(steps))
    findings.extend(_duplicate_step_id_findings(duplicate))
    findings.extend(_missing_concurrency_findings(spec))

    edges = _dependency_edges(steps, by_id)
    findings.extend(_unknown_step_reference_findings(steps, by_id))
    findings.extend(_cycle_findings(edges, by_id))

    verifier_bindings = _resolve_verifier_bindings(steps, by_id, edges, workspace_mode)
    findings.extend(verifier_bindings.findings)
    findings.extend(_unbound_inline_gate_findings(steps, workspace_mode))
    findings.extend(_prompt_as_evidence_findings(steps, by_id, spec, verifier_bindings.bound))
    findings.extend(
        _mutating_without_verification_findings(
            steps, by_id, edges, workspace_mode, verifier_bindings
        )
    )
    promotion = spec.get("promotion")
    if isinstance(promotion, dict):
        findings.extend(_promotion_findings(promotion, steps, by_id, workspace_mode))
    return findings


def _find_authored_status(document: Any, prefix: str = "$") -> list[Finding]:
    """Operational status is derived from run evidence — any authored ``status``
    key anywhere in the definition is rejected."""
    out: list[Finding] = []
    if isinstance(document, dict):
        for key, value in document.items():
            path = f"{prefix}.{key}"
            if key == "status":
                out.append(
                    Finding(
                        code=AUTHORED_STATUS,
                        message=(
                            "authored operational status is rejected: status is "
                            "derived from run evidence (completion follows the "
                            "revision), never written into a workflow definition"
                        ),
                        path=path,
                    )
                )
            out.extend(_find_authored_status(value, path))
    elif isinstance(document, list):
        for index, item in enumerate(document):
            out.extend(_find_authored_status(item, f"{prefix}[{index}]"))
    return out


def _workspace_mode(spec: dict[str, Any]) -> str:
    workspace = spec.get("workspace")
    if isinstance(workspace, dict):
        mode = workspace.get("mode")
        if mode in WORKSPACE_MODES:
            return mode
    return "isolated"


def _resolved_scope(step: dict[str, Any], workspace_mode: str) -> str:
    scope = step.get("scope")
    if scope in SCOPES:
        return scope
    return "research_readonly" if workspace_mode == "readonly" else "implementation"


def _is_mutating(step: dict[str, Any], workspace_mode: str) -> bool:
    """A step mutates (produces a candidate) iff it is an agent/task step whose
    effective scope is write-capable."""
    if step.get("kind") not in MUTATING_KINDS:
        return False
    return _resolved_scope(step, workspace_mode) in WRITE_SCOPES


def _unknown_step_kind_findings(steps: list[dict[str, Any]]) -> list[Finding]:
    out: list[Finding] = []
    for index, step in enumerate(steps):
        kind = step.get("kind")
        if kind not in STEP_KINDS:
            out.append(
                Finding(
                    code=UNKNOWN_STEP_KIND,
                    message=(
                        f"unknown step kind {kind!r}: valid kinds are {', '.join(STEP_KINDS)}"
                    ),
                    path=f"$.spec.steps[{index}].kind",
                )
            )
    return out


def _missing_concurrency_findings(spec: dict[str, Any]) -> list[Finding]:
    concurrency = spec.get("concurrency")
    if not isinstance(concurrency, dict):
        return [
            Finding(
                code=MISSING_CONCURRENCY,
                message="spec.concurrency is required: every workflow declares a "
                "concurrency group and policy",
                path="$.spec.concurrency",
            )
        ]
    policy = concurrency.get("policy")
    if not isinstance(policy, str) or policy not in CONCURRENCY_POLICIES:
        return [
            Finding(
                code=MISSING_CONCURRENCY,
                message=(
                    f"concurrency policy missing or invalid {policy!r}: valid "
                    f"policies are {', '.join(CONCURRENCY_POLICIES)}"
                ),
                path="$.spec.concurrency.policy",
            )
        ]
    return []


def _steps_by_id(
    steps: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    by_id: dict[str, dict[str, Any]] = {}
    duplicates: list[str] = []
    for step in steps:
        step_id = step.get("id")
        if not isinstance(step_id, str):
            continue
        if step_id in by_id:
            duplicates.append(step_id)
        else:
            by_id[step_id] = step
    return by_id, duplicates


def _duplicate_step_id_findings(duplicates: list[str]) -> list[Finding]:
    return [
        Finding(
            code=DUPLICATE_STEP_ID,
            message=f"duplicate step id {step_id!r}: step ids must be unique",
            path=f"$.spec.steps[*].id[{step_id}]",
        )
        for step_id in sorted(set(duplicates))
    ]


def _dependency_edges(
    steps: list[dict[str, Any]], by_id: dict[str, dict[str, Any]]
) -> dict[str, set[str]]:
    """Edges step_id -> {dependency ids}. Both ``needs`` and ``candidateFrom``
    express that the step depends on the named step's output."""
    edges: dict[str, set[str]] = {step.get("id"): set() for step in steps}
    for step in steps:
        step_id = step.get("id")
        if not isinstance(step_id, str) or step_id not in edges:
            continue
        for dep in step.get("needs", []) if isinstance(step.get("needs"), list) else []:
            if isinstance(dep, str):
                edges[step_id].add(dep)
        candidate_from = step.get("candidateFrom")
        if isinstance(candidate_from, str):
            edges[step_id].add(candidate_from)
    return edges


def _unknown_step_reference_findings(
    steps: list[dict[str, Any]], by_id: dict[str, dict[str, Any]]
) -> list[Finding]:
    out: list[Finding] = []
    for step in steps:
        step_id = step.get("id")
        if not isinstance(step_id, str):
            continue
        for field_name, path in (("candidateFrom", "$.candidateFrom"), ("needs", "$.needs")):
            value = step.get(field_name)
            if field_name == "needs":
                refs = value if isinstance(value, list) else []
            else:
                refs = [value] if isinstance(value, str) else []
            for ref in refs:
                if isinstance(ref, str) and ref not in by_id:
                    out.append(
                        Finding(
                            code=UNKNOWN_STEP_REFERENCE,
                            message=(
                                f"step {step_id!r} {field_name} references unknown step {ref!r}"
                            ),
                            path=f"$.spec.steps[@{step_id}]{path}",
                        )
                    )
    return out


def _cycle_findings(edges: dict[str, set[str]], by_id: dict[str, dict[str, Any]]) -> list[Finding]:
    """Detect dependency cycles among steps (needs + candidateFrom edges)."""
    visited: set[str] = set()
    stack: list[str] = []
    on_stack: set[str] = set()
    out: list[Finding] = []

    def visit(node: str) -> None:
        if node in visited or node not in edges:
            return
        visited.add(node)
        on_stack.add(node)
        stack.append(node)
        for dep in sorted(edges[node]):
            if dep in on_stack:
                cycle_start = stack.index(dep) if dep in stack else 0
                cycle = stack[cycle_start:] + [dep]
                out.append(
                    Finding(
                        code=STEP_DEPENDENCY_CYCLE,
                        message="step dependency cycle: " + " -> ".join(cycle),
                        path=f"$.spec.steps[@{node}]",
                    )
                )
            elif dep not in visited:
                visit(dep)
        stack.pop()
        on_stack.discard(node)

    for step_id in edges:
        visit(step_id)
    return out


@dataclass
class _VerifierBindings:
    """Resolved candidate bindings for every gate/approval step."""

    bound: dict[str, str] = field(default_factory=dict)  # verifier id -> gated mutating step id
    findings: list[Finding] = field(default_factory=list)


def _reachable_deps(start: str, edges: dict[str, set[str]]) -> set[str]:
    """Every step ``start`` transitively depends on (its needs-closure)."""
    seen: set[str] = set()
    frontier = list(edges.get(start, set()))
    while frontier:
        node = frontier.pop()
        if node in seen:
            continue
        seen.add(node)
        frontier.extend(edges.get(node, set()))
    return seen


def _resolve_verifier_bindings(
    steps: list[dict[str, Any]],
    by_id: dict[str, dict[str, Any]],
    edges: dict[str, set[str]],
    workspace_mode: str,
) -> _VerifierBindings:
    bindings = _VerifierBindings()
    mutating_ids = {
        step.get("id")
        for step in steps
        if isinstance(step.get("id"), str) and _is_mutating(step, workspace_mode)
    }
    for step in steps:
        step_id = step.get("id")
        if step.get("kind") not in VERIFIER_KINDS or not isinstance(step_id, str):
            continue
        candidate_from = step.get("candidateFrom")
        if isinstance(candidate_from, str):
            if candidate_from in by_id:
                if candidate_from in mutating_ids:
                    bindings.bound[step_id] = candidate_from
                else:
                    bindings.findings.append(
                        Finding(
                            code=UNBOUND_GATE,
                            message=(
                                f"gate step {step_id!r} candidateFrom names "
                                f"{candidate_from!r}, which produces no candidate "
                                "(only mutating agent/task steps under a write "
                                "scope produce candidate shas)"
                            ),
                            path=f"$.spec.steps[@{step_id}].candidateFrom",
                        )
                    )
            continue  # unknown candidateFrom is reported as unknown-step-reference
        mutating_ancestors = sorted(mutating_ids.intersection(_reachable_deps(step_id, edges)))
        if len(mutating_ancestors) == 1:
            bindings.bound[step_id] = mutating_ancestors[0]
        else:
            reason = (
                "it has no mutating upstream to gate"
                if not mutating_ancestors
                else f"its needs-closure reaches {len(mutating_ancestors)} mutating "
                f"steps ({', '.join(mutating_ancestors)}) — set candidateFrom to "
                "bind it to one candidate sha"
            )
            bindings.findings.append(
                Finding(
                    code=UNBOUND_GATE,
                    message=(f"gate step {step_id!r} is not bound to a candidate sha: {reason}"),
                    path=f"$.spec.steps[@{step_id}]",
                )
            )
    return bindings


def _unbound_inline_gate_findings(
    steps: list[dict[str, Any]], workspace_mode: str
) -> list[Finding]:
    """An inline ``gate`` binds to the step's OWN candidate — a step that produces
    no candidate cannot carry one."""
    out: list[Finding] = []
    for step in steps:
        if "gate" not in step:
            continue
        step_id = step.get("id")
        if not _is_mutating(step, workspace_mode):
            out.append(
                Finding(
                    code=UNBOUND_GATE,
                    message=(
                        f"step {step_id!r} carries an inline gate but produces no "
                        "candidate: an inline gate is bound to its step's own "
                        "candidate sha, which only mutating agent/task steps under "
                        "a write scope produce"
                    ),
                    path=f"$.spec.steps[@{step_id}].gate",
                )
            )
    return out


def _step_has_blocking_self_gate(step: dict[str, Any]) -> bool:
    gate = step.get("gate")
    return isinstance(gate, dict) and bool(gate.get("blocking", True))


def _prompt_as_evidence_findings(
    steps: list[dict[str, Any]],
    by_id: dict[str, dict[str, Any]],
    spec: dict[str, Any],
    bound_verifiers: dict[str, str],
) -> list[Finding]:
    """A gate that gates a candidate (it is bound, or it is a required promotion
    gate) must carry a MACHINE executor (test|command). Prompt text — or an LLM
    executor — is not evidence. A controller approval (kind: approval) is
    legitimate human evidence — but ONLY with a human/controller executor. An
    ``approval`` step carrying an LLM (agent/task) executor is the A1 anti-pattern:
    an author could make an LLM self-approval the candidate's ONLY required gate —
    prompt text and LLM judgment are never independent gate evidence."""
    required_gate_ids: set[str] = set()
    promotion = spec.get("promotion")
    if isinstance(promotion, dict) and isinstance(promotion.get("requiredGates"), list):
        required_gate_ids = set(promotion["requiredGates"])

    out: list[Finding] = []
    for step in steps:
        kind = step.get("kind")
        if kind not in ("gate", "approval"):
            continue
        step_id = step.get("id")
        if not isinstance(step_id, str):
            continue
        is_required = step_id in required_gate_ids or step_id in bound_verifiers
        if not is_required:
            continue
        executor = step.get("executor")
        if kind == "approval":
            # A1 (authoring_product_aio, 2026-09-03): an approval is legitimate ONLY as a
            # human/controller checkpoint. An LLM executor (agent/task) on an approval is
            # not a human gate — it is a model judging its own work, the exact
            # self-approval the rule forbids. The executor must be a human/controller
            # form (or a machine gate executor, which makes it a gate, not an approval).
            if executor in ("human", "controller", "operator"):
                continue
            if executor in MACHINE_GATE_EXECUTORS:
                continue
            out.append(
                Finding(
                    code=PROMPT_AS_EVIDENCE,
                    message=(
                        f"approval {step_id!r} carries an LLM executor "
                        f"(executor={executor!r}): an approval is a human/controller "
                        "checkpoint — a model executor makes it an LLM self-approval, "
                        "which is never independent gate evidence"
                    ),
                    path=f"$.spec.steps[@{step_id}].executor",
                )
            )
            continue
        if executor in MACHINE_GATE_EXECUTORS:
            continue
        out.append(
            Finding(
                code=PROMPT_AS_EVIDENCE,
                message=(
                    f"required gate {step_id!r} has no machine executor "
                    f"(executor={executor!r}): a gate that gates a candidate must "
                    "produce its evidence from a test or command executor — prompt "
                    "text is scaffolded instructions, never gate evidence"
                ),
                path=f"$.spec.steps[@{step_id}].executor",
            )
        )
    return out


def _mutating_without_verification_findings(
    steps: list[dict[str, Any]],
    by_id: dict[str, dict[str, Any]],
    edges: dict[str, set[str]],
    workspace_mode: str,
    bindings: _VerifierBindings,
) -> list[Finding]:
    """Every mutating step must be covered by a downstream gate: a verifier bound
    to its candidate, or to a later candidate that builds on it, or a blocking
    inline self-gate."""
    covered: set[str] = set()
    for candidate_id in bindings.bound.values():
        covered.add(candidate_id)
        covered.update(_reachable_deps(candidate_id, edges))

    out: list[Finding] = []
    for step in steps:
        step_id = step.get("id")
        if not isinstance(step_id, str) or not _is_mutating(step, workspace_mode):
            continue
        if step_id in covered or _step_has_blocking_self_gate(step):
            continue
        out.append(
            Finding(
                code=MUTATING_WITHOUT_VERIFICATION,
                message=(
                    f"mutating step {step_id!r} has no downstream verification: a "
                    "mutating step needs a gate/approval bound to its candidate "
                    "(or to a later candidate that builds on it), or a blocking "
                    "inline gate"
                ),
                path=f"$.spec.steps[@{step_id}]",
            )
        )
    return out


def _promotion_findings(
    promotion: dict[str, Any],
    steps: list[dict[str, Any]],
    by_id: dict[str, dict[str, Any]],
    workspace_mode: str,
) -> list[Finding]:
    out: list[Finding] = []
    candidate_from = promotion.get("candidateFrom")
    if not isinstance(candidate_from, str) or candidate_from not in by_id:
        out.append(
            Finding(
                code=UNKNOWN_STEP_REFERENCE,
                message=(f"promotion.candidateFrom references unknown step {candidate_from!r}"),
                path="$.spec.promotion.candidateFrom",
            )
        )
    elif not _is_mutating(by_id[candidate_from], workspace_mode):
        out.append(
            Finding(
                code=PROMOTION_CANDIDATE_NOT_PRODUCING,
                message=(
                    f"promotion.candidateFrom names {candidate_from!r}, which "
                    "produces no candidate — only mutating agent/task steps under "
                    "a write scope produce a candidate to promote"
                ),
                path="$.spec.promotion.candidateFrom",
            )
        )

    required_gates = promotion.get("requiredGates")
    gate_ids = [
        gid
        for gid in (required_gates if isinstance(required_gates, list) else [])
        if isinstance(gid, str)
    ]
    valid_gates = [
        gid for gid in gate_ids if gid in by_id and by_id[gid].get("kind") in VERIFIER_KINDS
    ]
    if not gate_ids or not valid_gates:
        out.append(
            Finding(
                code=PROMOTION_WITHOUT_GATES,
                message=(
                    "promotion has no required gates: promotion.requiredGates must "
                    "name at least one gate/approval step whose pass is required "
                    "before the candidate is promoted"
                ),
                path="$.spec.promotion.requiredGates",
            )
        )
    for gid in gate_ids:
        if gid not in by_id:
            out.append(
                Finding(
                    code=UNKNOWN_STEP_REFERENCE,
                    message=f"promotion.requiredGates references unknown step {gid!r}",
                    path="$.spec.promotion.requiredGates",
                )
            )
        elif by_id[gid].get("kind") not in VERIFIER_KINDS:
            out.append(
                Finding(
                    code=PROMOTION_WITHOUT_GATES,
                    message=(
                        f"promotion.requiredGates entry {gid!r} is not a gate or "
                        f"approval step (kind={by_id[gid].get('kind')!r})"
                    ),
                    path=f"$.spec.promotion.requiredGates[@{gid}]",
                )
            )
    return out


# --------------------------------------------------------------------------- #
# Reporting helpers
# --------------------------------------------------------------------------- #
def _pointer(absolute_path: Iterable[Any]) -> str:
    out = "$"
    for part in absolute_path:
        out += f"[{part}]" if isinstance(part, int) else f".{part}"
    return out


def _dedupe(findings: list[Finding]) -> list[Finding]:
    seen: set[tuple[str, str]] = set()
    out: list[Finding] = []
    for finding in findings:
        key = (finding.code, finding.path)
        if key in seen:
            continue
        seen.add(key)
        out.append(finding)
    return out


def semantic_error_codes() -> Iterator[str]:
    """The stable named error codes the semantic rules emit."""
    return iter(sorted(_SEMANTIC_CODES))
