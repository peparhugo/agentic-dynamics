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

Test semantics (w1, engine_gaps_verifier_revision): the engine owns the VERDICT too.
A ``kind: test`` phase is executed either in-process by ``test_runner.run_suite``
(LocalVerifier — the default) or, under ``--orchestrator``, dispatched through an
injected verifier executor (``scripts/fleet/docker_verifier_executor.py`` — the
DockerVerifierExecutor) which runs the suite in a READ-ONLY verifier container bound to
the candidate. The verdict lands on the SAME :class:`StepResult` fields
(``test_executed_success`` / ``tests_passed`` / ``tests_total``) in both shapes, from the
SAME source semantics — the suite run by the independent runner, never the agent's
self-report. ``StepResult`` therefore carries those three test-verdict fields (additive —
an agent executor never fills them).

Mirrors the Debt-2 pattern (``runtime/routing.py``, ``runtime/telemetry.py``,
``runtime/admission.py``): runtime owns the protocol; the composition root
(``scripts/run_workflow.py``) supplies the implementation — the local agent call by
default, the sibling-container executor under ``--orchestrator``. The dependency arrow
never points from a plane into ``scripts/``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
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
    language: str = ""
    backend: str | None = None
    thinking_effort: str = "high"
    thinking_budget_tokens: int = 0
    output_token_limit: int = 0
    timeout: int = 1800
    silent_mode: bool = False
    enforce_pytest: bool = False
    phase_def: dict[str, Any] = field(default_factory=dict)
    #: Step 3: the attempt ordinal within the phase (1-based) — the engine's retry counter, so
    #: executor state is keyed by run/ATTEMPT, never shared across retries of one phase.
    attempt: int = 1

    @property
    def prompt_sha256(self) -> str:
        """The immutable identity of the prepared instruction (sha256 of ``prompt``)."""
        return hashlib.sha256(self.prompt.encode("utf-8")).hexdigest()

    def to_prepared_dict(self) -> dict[str, Any]:
        """The transport form of this step (``prepared-step/v1``) for a sibling executor.

        The child consumes THIS — never a re-derivation from the spec — so the prompt the
        parent readied (and may have augmented) is exactly the prompt that executes, and its
        hash is carried for verification.
        """
        return {
            "schema": "prepared-step/v1",
            "phase_name": self.phase_name,
            "phase_kind": self.phase_kind,
            "prompt": self.prompt,
            "prompt_sha256": self.prompt_sha256,
            "model": self.model,
            "backend": self.backend,
            "goal": self.goal,
            "spec_name": self.spec_name,
            "workdir": self.workdir,
            "language": self.language,
            "thinking_effort": self.thinking_effort,
            "thinking_budget_tokens": self.thinking_budget_tokens,
            "output_token_limit": self.output_token_limit,
            "timeout": self.timeout,
            "silent_mode": self.silent_mode,
            "enforce_pytest": self.enforce_pytest,
            "attempt": self.attempt,
        }


def load_prepared_step(path: Path | str) -> dict[str, Any]:
    """Load and VERIFY a ``prepared-step/v1`` transport file (the child side of step 3).

    Refuses — never repairs — when the file is absent, not a prepared step, missing its
    prompt/hash, or when the prompt does not hash to the carried ``prompt_sha256``. A
    mismatch means the instruction was changed in transit; executing it would let the
    recorded parent decision and the actual run disagree, which is the defect this transport
    exists to close.
    """
    prepared_path = Path(path)
    try:
        payload = json.loads(prepared_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"prepared step not found: {prepared_path}") from None
    except json.JSONDecodeError as exc:
        raise ValueError(f"prepared step is not valid JSON: {prepared_path}: {exc}") from None
    if not isinstance(payload, dict) or payload.get("schema") != "prepared-step/v1":
        raise ValueError(f"not a prepared-step/v1 document: {prepared_path}")
    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError(f"prepared step carries no prompt: {prepared_path}")
    if not payload.get("phase_name"):
        raise ValueError(f"prepared step carries no phase_name: {prepared_path}")
    carried = str(payload.get("prompt_sha256") or "")
    actual = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    if carried != actual:
        raise ValueError(
            f"prepared step prompt hash mismatch ({carried[:12] or '<empty>'} != {actual[:12]}): "
            f"the instruction was changed in transit — refusing to execute"
        )
    return payload


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
    # test-verdict fields (w1, engine_gaps_verifier_revision): filled ONLY by a verifier
    # executor — the object a ``kind: test`` phase's dispatch returns. The engine reads the
    # SAME fields whether the suite ran in-process (LocalVerifier) or in a verifier container
    # (DockerVerifierExecutor), and the source is always the independent runner's suite
    # (exit + report), never the agent's self-report. An agent executor never fills them —
    # they stay ``None``/``0`` (null-not-zero, never a fabricated verdict).
    test_executed_success: bool | None = None
    tests_passed: int = 0
    tests_total: int = 0


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
        # Test-verdict fields ride through when the adapted object carries them (an agentic
        # result normally does not — an agent executor produces no test verdict); absent
        # fields stay None/0, never fabricated.
        test_executed_success=getattr(ar, "test_executed_success", None),
        tests_passed=int(getattr(ar, "tests_passed", 0) or 0),
        tests_total=int(getattr(ar, "tests_total", 0) or 0),
    )
