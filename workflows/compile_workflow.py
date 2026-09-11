"""Compile a workflow-v1 definition into the executable ExperimentSpec plan (step 1).

Wave 3's authoring surface (``workflow new`` / ``workflow lint`` / ``workflow plan``)
produces and validates ``workflow-v1`` documents, while the runner executes
ExperimentSpecs — two document kinds with no bridge (the AIO-workflow review's finding:
authored workflows could not execute end-to-end). This module IS the bridge, and it is
deliberately strict:

* The a1 linter's findings are REFUSALS, never warnings — a definition that violates the
  authoring contract never reaches a run.
* Only semantics the engine can execute 1:1 are mapped. Everything else refuses with a
  stable ``refused-*`` code: an ``approval`` node is a human checkpoint the runner cannot
  bind (its order/needs are unrepresentable); a ``command`` executor has no engine seam;
  ``merge-commit``/``fast-forward`` promotion is declared-but-unimplemented; a readonly
  workspace's repeatability contract has no runner form. Translating these silently would
  let the recorded plan and the executed run disagree — the exact failure this bridge
  removes.
* A workflow-v1 ``gate`` (executor ``test``) compiles to the engine's native
  ``test_gate: true`` on the producing agent phase: the independent test_runner verdict
  runs after the agent commits and fails the phase if the suite fails. The gate's evidence
  is that verdict — never prompt text — and it is never a standalone ``kind: test`` phase
  (whose empty ``commit_hash`` promote.py refuses).

The supported subset is the minimal example's shape: a LINEAR chain of ``agent`` steps
plus ``test`` gates, an isolated workspace, and ``squash-merge`` promotion whose
``requiredGates`` are exactly the declared gate steps (the engine has no optional gates).

``load_spec_any`` is the execution seam: a caller that accepts either document kind
(``scripts/run_workflow.py``, ``scripts/fleet/spawn_wrapper.py``) routes workflow-v1
through the compiler and everything else through the ordinary ExperimentSpec loader.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from agentic_dynamics.experiment import experiment_spec as es
from agentic_dynamics.experiment.experiment_spec import ExperimentSpec, SideEffects, Workflow
from workflows import lint_workflow as lw

#: The one workspace mode the runner implements: a disposable run clone off the base.
SUPPORTED_WORKSPACE_MODE = "isolated"

#: The one promotion strategy ``scripts/promote.py`` implements.
SUPPORTED_PROMOTION_STRATEGY = "squash-merge"

#: step kind -> the executor it must declare (agent: absent means "agent").
SUPPORTED_STEP_EXECUTORS: dict[str, str] = {"agent": "agent", "gate": "test"}

#: Stable refusal codes (a caller — CI, a tool — can assert on the vocabulary).
REFUSED_LINT = "refused-lint"
REFUSED_WORKSPACE_MODE = "refused-workspace-mode"
REFUSED_WORKSPACE_IMAGE = "refused-workspace-image"
REFUSED_CONCURRENCY_BOUNDED = "refused-concurrency-bounded"
REFUSED_STEP_KIND = "refused-step-kind"
REFUSED_STEP_EXECUTOR = "refused-step-executor"
REFUSED_STEP_IMAGE = "refused-step-image"
REFUSED_NEEDS_JOIN = "refused-needs-join"
REFUSED_NEEDS_ORDER = "refused-needs-order"
REFUSED_INLINE_GATE = "refused-inline-gate"
REFUSED_MISSING_PROMPT = "refused-missing-prompt"
REFUSED_CANDIDATE_FROM = "refused-candidate-from"
REFUSED_GATE_BINDING = "refused-gate-binding"
REFUSED_DUPLICATE_TEST_GATE = "refused-duplicate-test-gate"
REFUSED_PROMOTION_STRATEGY = "refused-promotion-strategy"
REFUSED_PROMOTION_GATES = "refused-promotion-gates"
REFUSED_PROMOTION_CANDIDATE = "refused-promotion-candidate"
REFUSED_SPEC_INVALID = "refused-spec-invalid"


class CompilationRefusedError(ValueError):
    """A workflow-v1 definition the engine cannot execute 1:1 — with named reasons.

    ``errors`` is the ordered list of ``[refused-<feature>] detail`` strings; nothing is
    ever "fixed up" silently.
    """

    def __init__(self, errors: list[str]):
        self.errors = list(errors)
        super().__init__("workflow-v1 compilation refused: " + "; ".join(self.errors))


@dataclass(frozen=True)
class CompiledWorkflow:
    """The compiled plan: the executable spec, the authored plan render, and identity.

    ``step_map`` maps every workflow-v1 step id to the compiled phase it executes on
    (a gate step maps to the producing phase whose ``test_gate`` enforces it).
    """

    spec: ExperimentSpec
    plan: dict[str, Any]
    source_digest: str
    source: str | None = None
    step_map: dict[str, str] = field(default_factory=dict)


def _document_digest(document: Any) -> str:
    """sha256 over the canonical JSON encoding of the parsed definition."""
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _is_mutating(step: dict[str, Any]) -> bool:
    """An agent step is mutating under a write-capable scope (the linter's own rule).

    In an isolated (write-capable) workspace an agent step with no declared scope defaults
    to ``implementation`` — the same default ``lint_workflow`` derives.
    """
    scope = step.get("scope") or "implementation"
    return scope in lw.WRITE_SCOPES


def compile_workflow(document: Any, *, source: str | None = None) -> CompiledWorkflow:
    """Compile a parsed workflow-v1 document into the executable spec + plan.

    Raises ``ValueError`` when ``document`` is not a workflow-v1 definition (the wrong
    document kind is a caller error, not a refusal), and :class:`CompilationRefusedError` with
    every named reason when the definition cannot execute 1:1.
    """
    if not lw.is_workflow_v1_document(document):
        raise ValueError(
            "not a workflow-v1 definition (missing apiVersion/kind/metadata/spec): "
            "a compilation consumes a workflow-v1 document, not an ExperimentSpec or a config"
        )

    errors: list[str] = []
    report = lw.lint(document)
    for finding in report.findings:
        errors.append(f"[{REFUSED_LINT}:{finding.code}] {finding.path}: {finding.message}")
    if errors:
        raise CompilationRefusedError(errors)

    metadata = document.get("metadata") or {}
    spec_doc = document.get("spec") or {}
    raw_steps = spec_doc.get("steps") or []
    steps = [s for s in raw_steps if isinstance(s, dict)]

    _check_workspace(spec_doc, errors)
    _check_concurrency(spec_doc, errors)

    phases, step_map, gate_ids = _compile_steps(steps, errors)
    promotion_row = _check_promotion(spec_doc, step_map, gate_ids, errors)
    if errors:
        raise CompilationRefusedError(errors)

    digest = _document_digest(document)
    mutating = any(s.get("kind") == "agent" and _is_mutating(s) for s in steps)
    compiled = ExperimentSpec(
        name=str(metadata.get("name") or ""),
        question=str(
            metadata.get("description") or metadata.get("title") or metadata.get("name") or ""
        ),
        version=str(metadata.get("revision") or ""),
        workflow=Workflow(
            kind="agent_task",
            params={
                "phases": phases,
                "workflow_v1": {
                    "schema": "workflow-v1",
                    "source": source,
                    "digest": digest,
                    "name": metadata.get("name"),
                    "revision": metadata.get("revision"),
                    "lifecycle": metadata.get("lifecycle"),
                    "baseRef": spec_doc.get("baseRef"),
                    "concurrency": spec_doc.get("concurrency") or {},
                    "promotion": promotion_row,
                    "step_map": step_map,
                },
            },
        ),
        factors=[],
        design="factorial",
        artifact_kind="workflow",
        intent="mutate" if mutating else "measure",
        side_effects=SideEffects(repository=mutating, external_services=False),
        # an operational workflow is a one-shot procedure (matching the committed
        # agent_task corpus); it runs in a disposable run clone.
        repeatable=False,
        sandboxed=True,
    )
    validation = es.validate_spec(compiled)
    if validation:
        raise CompilationRefusedError([f"[{REFUSED_SPEC_INVALID}] {e}" for e in validation])

    return CompiledWorkflow(
        spec=compiled,
        plan=_plan(document, source),
        source_digest=digest,
        source=source,
        step_map=step_map,
    )


def compile_path(path: str | Path) -> CompiledWorkflow:
    """Read a workflow-v1 definition file and compile it."""
    path = Path(path)
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    return compile_workflow(document, source=str(path))


def load_spec_any(path: Path) -> ExperimentSpec:
    """Load EITHER document kind: workflow-v1 compiles; everything else is a spec.

    This is the one seam that connects authoring to execution — ``run_workflow.py`` and
    the spawn wrapper call it instead of deciding the dialect by hand.
    """
    path = Path(path)
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if lw.is_workflow_v1_document(document):
        return compile_workflow(document, source=str(path)).spec
    return es.load_spec(path)


# --------------------------------------------------------------------------- #
# Section checks (each appends named refusals; nothing raises early so a caller
# sees EVERY reason at once)
# --------------------------------------------------------------------------- #
def _check_workspace(spec_doc: dict[str, Any], errors: list[str]) -> None:
    workspace = spec_doc.get("workspace") or {}
    if workspace.get("mode") != SUPPORTED_WORKSPACE_MODE:
        errors.append(
            f"[{REFUSED_WORKSPACE_MODE}] workspace.mode={workspace.get('mode')!r} — the engine "
            f"runs isolated run clones only; shared/readonly have no runner form"
        )
    if workspace.get("image"):
        errors.append(
            f"[{REFUSED_WORKSPACE_IMAGE}] workspace.image is not wired to the engine "
            f"(only the global --cell-image exists)"
        )


def _check_concurrency(spec_doc: dict[str, Any], errors: list[str]) -> None:
    concurrency = spec_doc.get("concurrency") or {}
    if concurrency.get("policy") == "bounded":
        errors.append(
            f"[{REFUSED_CONCURRENCY_BOUNDED}] concurrency.policy 'bounded' has no engine cap "
            f"— refuse rather than ignore maxRuns"
        )


def _compile_steps(
    steps: list[dict[str, Any]], errors: list[str]
) -> tuple[list[dict[str, Any]], dict[str, str], set[str]]:
    """Map the declared steps to engine phases (the gate merges into its producer)."""
    phases: list[dict[str, Any]] = []
    step_map: dict[str, str] = {}
    gate_ids: set[str] = set()
    test_gated: set[str] = set()  # producers already carrying the test_gate seam
    earlier_ids: list[str] = []

    for step in steps:
        sid = step.get("id")
        kind = step.get("kind")
        executor = step.get("executor")

        if kind not in SUPPORTED_STEP_EXECUTORS:
            errors.append(
                f"[{REFUSED_STEP_KIND}] step {sid!r} kind={kind!r} — the engine executes "
                f"agent steps and test gates only (task/approval refuse)"
            )
            continue
        expected = SUPPORTED_STEP_EXECUTORS[kind]
        if kind == "agent" and executor not in (None, expected):
            errors.append(
                f"[{REFUSED_STEP_EXECUTOR}] step {sid!r} executor={executor!r} — agent steps "
                f"run the agent executor only"
            )
            continue
        if kind == "gate" and executor != expected:
            errors.append(
                f"[{REFUSED_STEP_EXECUTOR}] step {sid!r} executor={executor!r} — a compiled "
                f"gate must declare executor 'test' (the independent test_runner verdict)"
            )
            continue
        if step.get("image"):
            errors.append(
                f"[{REFUSED_STEP_IMAGE}] step {sid!r} declares an image — per-step images are "
                f"not wired to the engine"
            )
            continue

        needs = step.get("needs") or []
        if len(needs) > 1:
            errors.append(
                f"[{REFUSED_NEEDS_JOIN}] step {sid!r} needs {needs} — non-linear joins have "
                f"no engine semantics (the engine executes a declared order)"
            )
            continue
        if needs and needs[0] not in earlier_ids:
            errors.append(
                f"[{REFUSED_NEEDS_ORDER}] step {sid!r} needs {needs[0]!r}, which is not an "
                f"earlier step — declared order is the execution order"
            )
            continue

        inline = step.get("gate")
        if inline is not None:
            if kind == "agent" and inline.get("executor") == "test" and inline.get("blocking") is not False:
                pass
            else:
                errors.append(
                    f"[{REFUSED_INLINE_GATE}] step {sid!r}: an inline gate supports "
                    f"executor 'test' and blocking (not false) on an agent step only"
                )
                continue

        if kind == "agent":
            prompt = step.get("prompt")
            if not isinstance(prompt, str) or not prompt.strip():
                errors.append(
                    f"[{REFUSED_MISSING_PROMPT}] agent step {sid!r} carries no prompt — "
                    f"a phase needs one"
                )
                continue
            if step.get("candidateFrom"):
                errors.append(
                    f"[{REFUSED_CANDIDATE_FROM}] agent step {sid!r} declares candidateFrom — "
                    f"only gates bind candidates"
                )
                continue
            phase: dict[str, Any] = {"name": sid, "kind": "agent", "prompt": prompt}
            if step.get("scope"):
                phase["scope"] = step["scope"]
            if inline is not None:
                phase["test_gate"] = True
                test_gated.add(sid)
            phases.append(phase)
            step_map[sid] = sid
        else:
            binding = step.get("candidateFrom")
            if not binding or binding not in earlier_ids:
                errors.append(
                    f"[{REFUSED_GATE_BINDING}] gate {sid!r} must bind candidateFrom an earlier "
                    f"step (got {binding!r})"
                )
                continue
            if phases[-1].get("name") != binding:
                errors.append(
                    f"[{REFUSED_GATE_BINDING}] gate {sid!r} binds {binding!r}, which is not the "
                    f"immediately preceding agent phase — the engine's test_gate runs after "
                    f"the producing phase only"
                )
                continue
            if binding in test_gated:
                errors.append(
                    f"[{REFUSED_DUPLICATE_TEST_GATE}] step {binding!r} already carries a test "
                    f"gate; gate {sid!r} would double-bind it (the engine runs one verdict)"
                )
                continue
            phases[-1]["test_gate"] = True
            test_gated.add(binding)
            gate_ids.add(sid)
            step_map[sid] = binding

        earlier_ids.append(sid)

    return phases, step_map, gate_ids


def _check_promotion(
    spec_doc: dict[str, Any],
    step_map: dict[str, str],
    gate_ids: set[str],
    errors: list[str],
) -> dict[str, Any] | None:
    promotion = spec_doc.get("promotion")
    if promotion is None:
        return None
    strategy = promotion.get("strategy")
    if strategy != SUPPORTED_PROMOTION_STRATEGY:
        errors.append(
            f"[{REFUSED_PROMOTION_STRATEGY}] promotion.strategy={strategy!r} — promote.py "
            f"implements {SUPPORTED_PROMOTION_STRATEGY!r} only"
        )
    required = list(promotion.get("requiredGates") or [])
    if set(required) != gate_ids:
        errors.append(
            f"[{REFUSED_PROMOTION_GATES}] promotion.requiredGates={required} != the declared "
            f"gate steps {sorted(gate_ids)} — optional gates have no engine form"
        )
    candidate = promotion.get("candidateFrom")
    if not isinstance(candidate, str) or step_map.get(candidate) != candidate:
        errors.append(
            f"[{REFUSED_PROMOTION_CANDIDATE}] promotion.candidateFrom={candidate!r} is not a "
            f"compiled agent step"
        )
    return {
        "strategy": strategy,
        "candidateFrom": candidate,
        "requiredGates": required,
    }


def _plan(document: Any, source: str | None) -> dict[str, Any]:
    """The authored plan render (``workflow-plan/v1``) — imported lazily to keep compile light."""
    from workflows import plan_workflow as pw

    return pw.build_plan(document, source=source)
