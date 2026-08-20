"""Backend dispatch — route a model id to opencode or the Claude CLI adapter.

Both backends return an ``AgenticResult``, so the rest of the pipeline is
backend-agnostic. ``anthropic/*`` models route to the Claude CLI (Claude
subscription); everything else routes to the opencode binary.
"""

from __future__ import annotations

import os
from typing import Any


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

    Args:
        prompt: The task prompt.
        model: Model identifier (``provider/model`` format).
        backend: Optional explicit backend (``opencode`` or ``claude_cli``).
        **kwargs: Forwarded to ``run_opencode_agentic`` / ``run_claude_agentic``.

    Returns:
        AgenticResult from whichever backend executed.
    """
    from agentic_dynamics.adapters.claude_adapter import run_claude_agentic
    from agentic_dynamics.adapters.opencode import run_opencode_agentic

    if resolve_backend(model, backend) == "claude_cli":
        return run_claude_agentic(prompt, model=model, **kwargs)
    return run_opencode_agentic(prompt, model=model, **kwargs)
