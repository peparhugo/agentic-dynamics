"""Backend dispatch — route a model id to opencode or the Claude CLI adapter.

Both backends return an ``AgenticResult``, so the rest of the pipeline is
backend-agnostic. ``anthropic/*`` models route to the Claude CLI (Claude
subscription); everything else routes to the opencode binary.

This is also the **admission choke point**. Every paid invocation in the repo funnels through
``run_agentic``, which makes it the one place a "was this run admitted?" question can be asked
of *all* spend — so the bypass guard lives here (``admission_leases`` phase 2). The guard is a
tier-0 call (``core.admission_context.require_admission``), never a ``control`` import: the
dependency lint pins the complete adapters→control edge set to the ``control.live`` telemetry
edge, and widening it for the gate would re-open the hole the lint exists to close. See
``core.admission_context`` for the split and for why arming is the operator's decision.
"""

from __future__ import annotations

import os
from typing import Any

from agentic_dynamics.core.admission_context import require_admission


def get_backend_for_model(model: str) -> str:
    """Return the backend that should execute a given model id.

    ``anthropic/*`` routes to ``claude_cli``, everything else to ``opencode``.
    Override globally via the ``DYNAMIC_CODE_BACKEND`` env var.
    """
    override = os.environ.get("DYNAMIC_CODE_BACKEND", "").strip().lower()
    if override in ("claude", "claude_cli", "anthropic"):
        return "claude_cli"
    if override in ("opencode", "auto"):
        return "opencode"

    provider = model.split("/", 1)[0].lower() if "/" in model else model.lower()
    if provider in ("anthropic", "claude"):
        return "claude_cli"
    return "opencode"


def resolve_backend(model: str, backend: str | None = None) -> str:
    """Resolve the effective backend for a run, honoring an explicit override."""
    if backend and backend not in ("auto", ""):
        return "claude_cli" if backend in ("claude", "claude_cli") else "opencode"
    return get_backend_for_model(model)


def run_agentic(prompt: str, *, model: str, backend: str | None = None, **kwargs: Any):
    """Run an agentic session through the appropriate backend.

    Refuses before dispatching when the admission gate is armed
    (``FINOPS_ADMISSION_REQUIRED=1``) and no live lease context is present — the bypass
    detector. ``require_admission`` is called FIRST, before the adapter modules are even
    imported, so a refusal cannot have started a subprocess, opened a session, or spent a
    token: refusing here means *no invocation happened*, which is the property the entry-point
    tests assert.

    Args:
        prompt: The task prompt.
        model: Model identifier (``provider/model`` format).
        backend: Optional explicit backend (``opencode`` or ``claude_cli``).
        **kwargs: Forwarded to ``run_opencode_agentic`` / ``run_claude_agentic``.

    Returns:
        AgenticResult from whichever backend executed.

    Raises:
        AdmissionContextError: the gate is armed and this call did not come through the
            admission controller (or came through one whose leases have since expired, or
            whose admission was priced for a different model).
    """
    # The gate, before anything else. Disarmed (the default) this is a cheap env read and a
    # ContextVar lookup; armed, it is the refusal.
    require_admission(model)

    from agentic_dynamics.adapters.claude_adapter import run_claude_agentic
    from agentic_dynamics.adapters.opencode import run_opencode_agentic

    if resolve_backend(model, backend) == "claude_cli":
        return run_claude_agentic(prompt, model=model, **kwargs)
    return run_opencode_agentic(prompt, model=model, **kwargs)
