"""Instrumented adapter — wraps any LLM invoke callable to capture trajectories.

Each invoke becomes a TrajectoryStep. A sequence of invocations forms
a full ReasoningTrajectory that the basin/recovery modules can analyze.

Uses thread-level timeout so stuck LLM calls don't block experiments.
"""

from __future__ import annotations

import concurrent.futures
import time
import warnings
from dataclasses import dataclass, field
from typing import Any

from .trajectory import ReasoningTrajectory, TrajectoryStep

warnings.warn(
    "instrument.adapter is deprecated. The current pipeline uses "
    "scripts/run.py with instrument.opencode.run_opencode_agentic directly.",
    DeprecationWarning, stacklevel=2,
)


class InvokeTimeoutError(Exception):
    """Raised when an LLM invoke exceeds its time budget."""
    pass


@dataclass
class InstrumentedAdapter:
    """Wraps an LLM invoke callable, logging every invoke as a trajectory step.

    The invoke callable must have signature:
        (prompt: str, *, model: str = "", timeout: int = 180) -> Any
    where the return value has ``.text``, ``.completion_tokens``, ``.estimated_cost_usd``
    attributes (or equivalent dict keys).

    Usage:
        def my_llm(prompt, model="", timeout=180):
            ... # call your LLM
            return result  # must have .text, .completion_tokens, .estimated_cost_usd

        adapter = InstrumentedAdapter(my_llm, model="gpt-5")

        adapter.invoke("Analyze the problem...", thought="analyze")
        adapter.invoke("Design a solution...", thought="design")
        adapter.invoke("Implement the design...", thought="implement")

        traj = adapter.get_trajectory()
    """

    _adapter: Any  # Callable[[str, ...], Any] — an LLM invoke function
    model: str = ""
    task: str = ""
    perturbation_applied: str = ""
    perturbation_strength: float = 0.0

    _steps: list[TrajectoryStep] = field(default_factory=list)
    _total_input_tokens: int = 0
    _total_output_tokens: int = 0
    _total_cost: float = 0.0
    _total_duration: float = 0.0

    def invoke(
        self,
        prompt: str,
        *,
        thought: str = "",
        tool_name: str = "llm_invoke",
        model: str = "",
        timeout: int = 180,
    ) -> tuple[str, int, float]:
        """Invoke the wrapped callable with thread-level timeout.

        Returns:
            (response_text, tokens_used, cost_usd)

        Raises:
            InvokeTimeoutError: If the invoke exceeds timeout seconds.
        """
        effective_model = model or self.model

        def _call():
            result = self._adapter(prompt, model=effective_model, timeout=timeout)
            # Support both object attributes and dict keys
            if isinstance(result, dict):
                text = result.get("text", "")
                tokens = result.get("completion_tokens", 0) or result.get("total_tokens", 0) or 0
                cost = result.get("estimated_cost_usd", 0) or result.get("cost", 0.0)
                prompt_tokens = result.get("prompt_tokens", 0) or 0
                return text, tokens, cost, prompt_tokens
            text = getattr(result, "text", "")
            tokens = getattr(result, "completion_tokens", 0) or getattr(result, "total_tokens", 0) or 0
            cost = getattr(result, "estimated_cost_usd", 0.0)
            prompt_tokens = getattr(result, "prompt_tokens", 0) or 0
            return text, tokens, cost, prompt_tokens

        t0 = time.monotonic()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_call)
            try:
                text, tokens, cost, prompt_tokens = future.result(timeout=timeout + 10)
            except concurrent.futures.TimeoutError:
                raise InvokeTimeoutError(
                    f"LLM invoke exceeded {timeout}s timeout for turn '{thought}' "
                    f"(operator={self.perturbation_applied}, strength={self.perturbation_strength})"
                ) from None

        duration = time.monotonic() - t0

        step = TrajectoryStep(
            step_index=len(self._steps),
            thought=thought or f"turn_{len(self._steps)}",
            action=text,
            tool_name=tool_name,
            tokens_used=tokens,
        )
        self._steps.append(step)
        self._total_input_tokens += prompt_tokens
        self._total_output_tokens += tokens
        self._total_cost += cost
        self._total_duration += duration

        return text, tokens, cost

    def get_trajectory(self, run_id: str = "") -> ReasoningTrajectory:
        """Build a ReasoningTrajectory from all captured steps."""
        return ReasoningTrajectory(
            run_id=run_id or f"instrumented_{int(time.time())}",
            model=self.model,
            task=self.task,
            perturbation_applied=self.perturbation_applied,
            perturbation_strength=self.perturbation_strength,
            steps=list(self._steps),
            total_input_tokens=self._total_input_tokens,
            total_output_tokens=self._total_output_tokens,
            total_tokens=self._total_input_tokens + self._total_output_tokens,
            cost_usd=self._total_cost,
            duration_s=self._total_duration,
        )

    def reset(self) -> None:
        self._steps.clear()
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_cost = 0.0
        self._total_duration = 0.0
