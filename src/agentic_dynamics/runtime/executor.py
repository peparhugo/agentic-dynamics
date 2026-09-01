"""The step-executor seam (P0-2, control-plane stabilization): one semantic workflow engine.

The pre-P0-2 shape had TWO phase loops — the in-process runner inside
``runtime.workflow_runner.run_workflow`` and a separately-coded Docker loop
(``scripts/run_workflow.py:_run_orchestrator``) that reimplemented phase iteration,
failure propagation, and test handling differently. That is how the container path
developed its own (broken) workflow language: a second loop could skip ``kind: test``
phases, could classify a failed sibling as success (``returncode == 0``), and had no
shared notion of checkpoint/awaiting.

The unification: the ENGINE (``run_workflow``) owns everything — dependency ordering,
stop-on-failure, approval pauses, retry policy, test semantics, gate evaluation, parent
run state, the aggregate ledger, promotion eligibility. Docker answers exactly one
question: *"execute this one step inside this exact isolation envelope and return a
structured result."* It never reimplements workflow semantics.

Mirrors the Debt-2 pattern (``runtime/routing.py``, ``runtime/telemetry.py``,
``runtime/admission.py``): runtime owns the protocol; the composition root
(``scripts/run_workflow.py``) supplies the implementation — the local agent call by
default, the sibling-container executor under ``--orchestrator``. The dependency arrow
never points from a plane into ``scripts/``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class StepRequest:
    """Everything the engine knows about ONE step, handed to the executor.

    The executor runs the step and returns a :class:`StepResult`. The request is
    deliberately flat and concrete — an executor must not reach back into the spec,
    the worktree, or the ledger; it gets the resolved values.
    """

    phase_name: str
    phase_kind: str
    prompt: str
    model: str
    goal: str
    spec_name: str
    workdir: str
    backend: str | None = None
    thinking_effort: str = "high"
    thinking_budget_tokens: int = 0
    output_token_limit: int = 0
    timeout: int = 1800
    silent_mode: bool = False
    enforce_pytest: bool = False
    phase_def: dict[str, Any] = field(default_factory=dict)


@dataclass
class StepResult:
    """The executor's structured answer for one step.

    Carries the same attribute surface the engine reads off an ``AgenticResult``
    (tokens, cost, session id, files, confidence), so the engine's post-phase logic —
    commit gate, deploy gate, checkpoint, ledger — is unchanged whether the step ran
    in-process or in a sibling container. Unknown fields are ``None``/empty, never
    fabricated.
    """

    ok: bool = False
    state: str = "failed"  # ok | failed | awaiting | cancelled | refused
    error: str = ""
    exit_code: int = -1
    session_id: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    answer_tokens: int = 0
    explanation_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    cost_source: str = ""
    estimation_method: str = ""
    reported_cost_usd: float | None = None
    confidence: float | None = None
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cache_hit_rate: float = 0.0
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    final_response: str = ""


class StepExecutor(Protocol):
    """Execute ONE step inside ONE isolation envelope; return a structured result.

    The engine owns ordering, stop-on-failure, checkpoints, retries, gates, the
    aggregate ledger, and promotion eligibility. An executor never writes a workflow
    ledger, never refreshes an index, never emits run facts, never makes a promotion
    decision.
    """

    def execute(self, request: StepRequest) -> StepResult:
        """Run ``request``'s step and return its structured result."""
        ...


class LocalAgentExecutor:
    """The default executor: run the agent in-process through the injected callable.

    Wraps the historical ``run_agentic``-shaped call (``run_agent(prompt, **kwargs)``)
    so the engine's default path is byte-identical to the pre-P0-2 runner. The callable
    may be a real adapter (``run_agentic``) or a test fake.
    """

    def __init__(self, run_agent: Any):
        self._run_agent = run_agent

    def execute(self, request: StepRequest) -> StepResult:
        kwargs: dict[str, Any] = {
            "model": request.model,
            "backend": request.backend,
            "workdir": request.workdir,
            "thinking_effort": request.thinking_effort,
            "thinking_budget_tokens": request.thinking_budget_tokens,
            "output_token_limit": request.output_token_limit,
            "timeout": request.timeout,
            "silent_mode": request.silent_mode,
            "enforce_pytest": request.enforce_pytest,
        }
        # The engine's phase-loop may hand watchdog-specific kwargs (watchdog seam,
        # transcript path) for the LOCAL path only — the Docker executor has its own
        # in-container watchdog, so those never appear in a Docker StepRequest. They are
        # forwarded here so the local watchdog keeps working through the executor seam.
        if request.phase_def.get("run_model"):
            kwargs["model"] = str(request.phase_def["run_model"])
        kwargs.update(request.phase_def.get("_agent_kwargs", {}) or {})
        ar = self._run_agent(request.prompt, **kwargs)
        return _result_from_agentic(ar)


def _result_from_agentic(ar: Any) -> StepResult:
    """Adapt an ``AgenticResult``-shaped object onto :class:`StepResult`.

    ``getattr``-tolerant (composition-root tests substitute minimal result namespaces).
    """
    tokens = getattr(ar, "tokens", None) or {}
    if not isinstance(tokens, dict):
        tokens = {}
    cost_source = getattr(ar, "cost_source", None)
    return StepResult(
        ok=bool(getattr(ar, "ok", False)),
        state="ok" if getattr(ar, "ok", False) else "failed",
        error=getattr(ar, "error", "") or "",
        exit_code=int(getattr(ar, "exit_code", -1) or -1),
        session_id=getattr(ar, "session_id", "") or "",
        prompt_tokens=int(tokens.get("in", 0)),
        completion_tokens=int(tokens.get("out", 0)),
        reasoning_tokens=int(tokens.get("reasoning", 0)),
        answer_tokens=int(tokens.get("answer", 0)),
        explanation_tokens=int(tokens.get("explanation", 0)),
        total_tokens=int(tokens.get("total", getattr(ar, "total_tokens", 0) or 0)),
        estimated_cost_usd=float(getattr(ar, "estimated_cost_usd", 0.0) or 0.0),
        cost_source=getattr(cost_source, "value", None) or (
            str(cost_source) if cost_source else ""
        ),
        estimation_method=getattr(ar, "estimation_method", None),
        reported_cost_usd=getattr(ar, "reported_cost_usd", None),
        confidence=getattr(ar, "confidence", None),
        cache_read_tokens=int(getattr(ar, "cache_read_tokens", 0) or 0),
        cache_write_tokens=int(getattr(ar, "cache_write_tokens", 0) or 0),
        cache_hit_rate=float(getattr(ar, "cache_hit_rate", 0.0) or 0.0),
        files_created=list(getattr(ar, "files_created", []) or []),
        files_modified=list(getattr(ar, "files_modified", []) or []),
        final_response=getattr(ar, "final_response", "") or "",
    )
