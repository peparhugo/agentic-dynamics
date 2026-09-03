"""Render a workflow-v1 definition as an executable plan (Wave-3 authoring, a3).

``workflow plan`` turns a workflow-v1 definition into the plan a human or the AIO
Control Agent reads BEFORE the workflow runs: the step DAG (its ``needs`` and
``candidateFrom`` edges), the gates and what each gate binds, and the promotion
contract. ``build_plan`` is the machine render (the ``--json`` surface, schema
``workflow-plan/v1``); ``render_plan_text`` is the human glance.

The plan is a RENDER of the declared shape plus the structure the workflow engine
will execute — it never invents run state (status is derived from run evidence,
never planned) and it carries the a1 lint report inline, so a reader sees at a
glance whether the declared plan is clean:

* ``validation.ok`` is True only when the definition passes the workflow-v1 schema
  AND every a1 semantic rule with zero findings; the findings are embedded verbatim
  (code/message/path), so a plan for a violating workflow shows exactly why.
* Step mutation is derived the same way the linter derives it (a step under a
  write-capable scope produces a candidate); gates resolve their bound candidate
  from a declared ``candidateFrom`` or from a single mutating upstream — the same
  resolution the linter's ``unbound-gate`` rule checks.

The sibling lint surface is ``workflows/lint_workflow.py``; the scaffold surface is
``workflows/scaffold_workflow.py``.
"""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any

import yaml

from workflows import lint_workflow as lw

PLAN_SCHEMA_ID = "workflow-plan/v1"

WORKFLOW_V1_KIND = "workflow-v1"


# --------------------------------------------------------------------------- #
# Public render entry points
# --------------------------------------------------------------------------- #
def build_plan(document: Any, *, source: str | None = None) -> dict[str, Any]:
    """Render a parsed workflow-v1 document into the ``workflow-plan/v1`` dict.

    Raises ``ValueError`` when ``document`` is not a workflow-v1 definition — a plan
    can only be rendered for the document kind the authoring contract describes.
    """
    if not lw.is_workflow_v1_document(document):
        raise ValueError(
            "not a workflow-v1 definition (missing apiVersion/kind/metadata/spec): "
            "a plan renders a workflow-v1 document, not an ExperimentSpec or a config"
        )

    report = lw.lint(document)
    spec = document.get("spec")
    spec = spec if isinstance(spec, dict) else {}
    raw_steps = spec.get("steps")
    steps = [s for s in raw_steps if isinstance(s, dict)] if isinstance(raw_steps, list) else []

    workspace_mode = _workspace_mode(spec)
    by_id = {s.get("id"): s for s in steps if isinstance(s.get("id"), str)}
    deps = _dependency_map(steps, by_id)
    mutating_ids = {sid for sid, step in by_id.items() if _produces_candidate(step, workspace_mode)}

    return {
        "schema": PLAN_SCHEMA_ID,
        "source": source,
        "document_kind": WORKFLOW_V1_KIND,
        "metadata": _metadata_row(document.get("metadata")),
        "spec": _spec_row(spec),
        "steps": _step_rows(steps, workspace_mode),
        "edges": _edge_rows(steps, by_id),
        "topological_order": _topological_order(steps, by_id, deps),
        "gates": _gate_rows(steps, spec, by_id, deps, mutating_ids, workspace_mode),
        "promotion": _promotion_row(spec),
        "validation": _validation_row(report),
    }


def build_plan_path(path: str | Path) -> dict[str, Any]:
    """Read a workflow-v1 definition file and render its plan (``workflow plan``)."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    document = yaml.safe_load(text)
    return build_plan(document, source=str(path))


def render_plan_text(plan: dict[str, Any]) -> str:
    """Render a plan dict as the human-readable text the default ``workflow plan`` prints."""
    lines: list[str] = []
    metadata = plan.get("metadata") or {}
    spec = plan.get("spec") or {}
    workspace = spec.get("workspace") or {}
    concurrency = spec.get("concurrency") or {}
    lines.append(
        f"workflow: {metadata.get('name') or '?'}  "
        f"(revision {metadata.get('revision') or '?'} · "
        f"lifecycle {metadata.get('lifecycle') or '?'})"
    )
    parts = [f"baseRef: {spec.get('baseRef') or '?'}"]
    if workspace.get("mode"):
        parts.append(f"workspace: {workspace['mode']}")
    if concurrency.get("group"):
        parts.append(
            f"concurrency: group={concurrency['group']}, policy={concurrency.get('policy')}"
        )
    lines.append(" · ".join(parts))
    lines.append("")

    steps = plan.get("steps") or []
    lines.append(f"steps ({len(steps)}):")
    for step in steps:
        marker = "mutating" if step.get("mutating") else "readonly"
        lines.append(
            f"  {step['id']:<16} {step.get('kind'):<9} {marker:<9} "
            f"needs={_fmt_list(step.get('needs'))} "
            f"candidateFrom={step.get('candidateFrom') or '-'}"
        )
    lines.append("")

    edges = plan.get("edges") or []
    lines.append(f"edges ({len(edges)}):")
    for edge in sorted(edges, key=lambda e: (e.get("via") or "", e.get("from") or "", e.get("to") or "")):
        lines.append(
            f"  {edge.get('via'):<14} {edge['to']} <- {edge['from']}"
        )
    lines.append("")

    gates = plan.get("gates") or []
    lines.append(f"gates ({len(gates)}):")
    for gate in gates:
        required = "required" if gate.get("required_by_promotion") else "optional"
        lines.append(
            f"  {gate['id']:<16} {gate.get('kind')}/{gate.get('executor') or '?'} "
            f"binds {gate.get('binds') or '—'} ({gate.get('binding')}, {required})"
        )
    lines.append("")

    promotion = plan.get("promotion")
    if promotion:
        lines.append(
            "promotion: candidateFrom {candidateFrom} · strategy {strategy} · "
            "requiredGates [{gates}]".format(
                candidateFrom=promotion.get("candidateFrom"),
                strategy=promotion.get("strategy"),
                gates=", ".join(promotion.get("requiredGates") or []),
            )
        )
    else:
        lines.append("promotion: none (no candidate advances toward baseRef)")
    lines.append("")

    validation = plan.get("validation") or {}
    status = "OK" if validation.get("ok") else "FINDINGS"
    lines.append(f"validation: {status} ({len(validation.get('findings') or [])} findings)")
    return "\n".join(lines)


def dump_plan_json(plan: dict[str, Any]) -> str:
    """Serialize a plan dict as indented JSON (the ``--json`` machine surface)."""
    return json.dumps(plan, indent=2, sort_keys=False)


# --------------------------------------------------------------------------- #
# Row derivations
# --------------------------------------------------------------------------- #
def _workspace_mode(spec: dict[str, Any]) -> str:
    workspace = spec.get("workspace")
    if isinstance(workspace, dict):
        mode = workspace.get("mode")
        if mode in lw.WORKSPACE_MODES:
            return mode
    return "isolated"


def _effective_scope(step: dict[str, Any], workspace_mode: str) -> str:
    scope = step.get("scope")
    if scope in lw.SCOPES:
        return scope
    return "research_readonly" if workspace_mode == "readonly" else "implementation"


def _produces_candidate(step: dict[str, Any], workspace_mode: str) -> bool:
    """A step produces a candidate iff it is a mutating agent/task step."""
    if step.get("kind") not in lw.MUTATING_KINDS:
        return False
    return _effective_scope(step, workspace_mode) in lw.WRITE_SCOPES


def _metadata_row(metadata: Any) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    keys = ("name", "revision", "lifecycle", "title")
    return {key: metadata.get(key) for key in keys if metadata.get(key) is not None}


def _spec_row(spec: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {}
    if spec.get("baseRef") is not None:
        row["baseRef"] = spec["baseRef"]
    workspace = spec.get("workspace")
    if isinstance(workspace, dict):
        row["workspace"] = {
            key: workspace[key] for key in ("mode", "image") if workspace.get(key) is not None
        }
    concurrency = spec.get("concurrency")
    if isinstance(concurrency, dict):
        row["concurrency"] = {
            key: concurrency[key]
            for key in ("group", "policy", "maxRuns")
            if concurrency.get(key) is not None
        }
    return row


def _step_rows(steps: list[dict[str, Any]], workspace_mode: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for step in steps:
        step_id = step.get("id")
        if not isinstance(step_id, str):
            continue
        gate = step.get("gate")
        rows.append(
            {
                "id": step_id,
                "kind": step.get("kind"),
                "executor": step.get("executor"),
                "scope": _effective_scope(step, workspace_mode),
                "mutating": _produces_candidate(step, workspace_mode),
                "needs": [n for n in step.get("needs", []) if isinstance(n, str)]
                if isinstance(step.get("needs"), list)
                else [],
                "candidateFrom": step.get("candidateFrom")
                if isinstance(step.get("candidateFrom"), str)
                else None,
                "inline_gate": _inline_gate_row(gate),
            }
        )
    return rows


def _inline_gate_row(gate: Any) -> dict[str, Any] | None:
    if not isinstance(gate, dict):
        return None
    return {
        key: gate[key]
        for key in ("executor", "blocking")
        if gate.get(key) is not None
    }


def _dependency_map(
    steps: list[dict[str, Any]], by_id: dict[str, dict[str, Any]]
) -> dict[str, set[str]]:
    """step_id -> {dependency ids} across needs + candidateFrom (the DAG edges)."""
    deps: dict[str, set[str]] = {step.get("id"): set() for step in steps}
    for step in steps:
        step_id = step.get("id")
        if not isinstance(step_id, str) or step_id not in deps:
            continue
        for dep in step.get("needs", []) if isinstance(step.get("needs"), list) else []:
            if isinstance(dep, str):
                deps[step_id].add(dep)
        candidate_from = step.get("candidateFrom")
        if isinstance(candidate_from, str):
            deps[step_id].add(candidate_from)
    return deps


def _edge_rows(steps: list[dict[str, Any]], by_id: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for step in steps:
        step_id = step.get("id")
        if not isinstance(step_id, str) or step_id not in by_id:
            continue
        for dep in step.get("needs", []) if isinstance(step.get("needs"), list) else []:
            if isinstance(dep, str):
                rows.append({"from": dep, "to": step_id, "via": "needs"})
        candidate_from = step.get("candidateFrom")
        if isinstance(candidate_from, str):
            rows.append({"from": candidate_from, "to": step_id, "via": "candidateFrom"})
    return rows


def _topological_order(
    steps: list[dict[str, Any]], by_id: dict[str, dict[str, Any]], deps: dict[str, set[str]]
) -> list[str]:
    """A declared-order-stable topological order, or [] when a dependency cycle exists.

    A cycle is reported through the embedded lint findings (``step-dependency-cycle``);
    an empty order is the render's way of saying "no valid execution order" — never a
    fabricated one.
    """
    known = set(by_id)
    remaining = {sid: set(d for d in deps.get(sid, ()) if d in known) for sid in known}
    children: dict[str, set[str]] = {sid: set() for sid in known}
    for sid, depset in deps.items():
        for dep in depset:
            if dep in children:
                children[dep].add(sid)

    enqueued: set[str] = set()
    queue: deque[str] = deque()
    for sid in by_id:
        if not remaining[sid]:
            enqueued.add(sid)
            queue.append(sid)

    order: list[str] = []
    while queue:
        sid = queue.popleft()
        order.append(sid)
        for child in sorted(children.get(sid, ())):
            remaining[child].discard(sid)
            if not remaining[child] and child not in enqueued:
                enqueued.add(child)
                queue.append(child)

    return order if len(order) == len(known) else []


def _reachable(start: str, deps: dict[str, set[str]]) -> set[str]:
    seen: set[str] = set()
    stack = list(deps.get(start, ()))
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(deps.get(node, ()))
    return seen


def _gate_rows(
    steps: list[dict[str, Any]],
    spec: dict[str, Any],
    by_id: dict[str, dict[str, Any]],
    deps: dict[str, set[str]],
    mutating_ids: set[str],
    workspace_mode: str,
) -> list[dict[str, Any]]:
    promotion = spec.get("promotion")
    required = (
        {gid for gid in promotion.get("requiredGates", []) if isinstance(gid, str)}
        if isinstance(promotion, dict)
        else set()
    )
    rows: list[dict[str, Any]] = []
    for step in steps:
        step_id = step.get("id")
        if step.get("kind") not in lw.VERIFIER_KINDS or not isinstance(step_id, str):
            continue
        candidate_from = step.get("candidateFrom")
        if isinstance(candidate_from, str):
            binds = candidate_from if candidate_from in mutating_ids else None
            binding = "declared"
        else:
            ancestors = sorted(mutating_ids.intersection(_reachable(step_id, deps)))
            if len(ancestors) == 1:
                binds = ancestors[0]
                binding = "single-mutating-upstream"
            else:
                binds = None
                binding = "unbound"
        rows.append(
            {
                "id": step_id,
                "kind": step.get("kind"),
                "executor": step.get("executor"),
                "scope": _effective_scope(step, workspace_mode),
                "candidateFrom": candidate_from if isinstance(candidate_from, str) else None,
                "binds": binds,
                "binding": binding,
                "required_by_promotion": step_id in required,
            }
        )
    return rows


def _promotion_row(spec: dict[str, Any]) -> dict[str, Any] | None:
    promotion = spec.get("promotion")
    if not isinstance(promotion, dict):
        return None
    row: dict[str, Any] = {}
    for key in ("candidateFrom", "strategy"):
        if promotion.get(key) is not None:
            row[key] = promotion[key]
    if isinstance(promotion.get("requiredGates"), list):
        row["requiredGates"] = [
            gid for gid in promotion["requiredGates"] if isinstance(gid, str)
        ]
    return row


def _validation_row(report: lw.LintReport) -> dict[str, Any]:
    return {
        "ok": report.ok,
        "findings": [f.as_dict() for f in report.findings],
    }


def _fmt_list(values: Any) -> str:
    if not values:
        return "-"
    return ", ".join(str(v) for v in values)
