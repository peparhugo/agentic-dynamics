"""Resource efficiency measurement — the thermodynamic cost of reasoning.

Captures the complete token and energy breakdown: prompt tokens,
completion tokens, reasoning tokens (hidden thinking budget), cost,
and estimated energy consumption.

The key metric: Joules per correct constrained solution.
Everything else is derivative.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .solution import SolutionMetrics


# Energy estimates per token type (Joules/token on H100-class hardware)
# Source: NVIDIA H100 spec (~700W TDP, ~3000 tok/s output, ~1500 tok/s reasoning)
ENERGY_PER_OUTPUT_TOKEN = 0.23   # J/tok — 700W / 3000 tok/s
ENERGY_PER_REASONING_TOKEN = 0.47  # J/tok — reasoning uses more compute (higher batch, deeper layers)
ENERGY_PER_PROMPT_TOKEN = 0.08   # J/tok — prefill is heavily optimized


@dataclass
class EfficiencyMetrics:
    """Complete resource efficiency breakdown for one model run.

    Tracks four dimensions:
    1. Token breakdown — prompt, completion, reasoning
    2. Cost — USD at provider pricing
    3. Energy — estimated joules consumed
    4. Solution density — useful output per unit of resource
    """

    # Token breakdown
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0

    # Thinking overhead
    thinking_ratio: float = 0.0      # reasoning_tokens / total_tokens
    output_efficiency: float = 0.0   # completion_tokens / total_tokens

    # Cost (USD)
    cost_input_usd: float = 0.0
    cost_output_usd: float = 0.0
    cost_reasoning_usd: float = 0.0
    total_cost_usd: float = 0.0

    # Energy (estimated Joules)
    energy_input_j: float = 0.0
    energy_output_j: float = 0.0
    energy_reasoning_j: float = 0.0
    total_energy_j: float = 0.0

    # Solution density
    lines_of_code: int = 0
    solution_density: float = 0.0      # LOC / total_tokens
    correctness_per_dollar: float = 0.0  # correctness / cost
    quality_per_joule: float = 0.0       # composite quality / energy

    # Composite
    efficiency_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "total_tokens": self.total_tokens,
            "thinking_ratio": round(self.thinking_ratio, 4),
            "output_efficiency": round(self.output_efficiency, 4),
            "cost_input_usd": round(self.cost_input_usd, 6),
            "cost_output_usd": round(self.cost_output_usd, 6),
            "cost_reasoning_usd": round(self.cost_reasoning_usd, 6),
            "total_cost_usd": round(self.total_cost_usd, 6),
            "energy_input_j": round(self.energy_input_j, 2),
            "energy_output_j": round(self.energy_output_j, 2),
            "energy_reasoning_j": round(self.energy_reasoning_j, 2),
            "total_energy_j": round(self.total_energy_j, 2),
            "solution_density": round(self.solution_density, 6),
            "correctness_per_dollar": round(self.correctness_per_dollar, 2),
            "quality_per_joule": round(self.quality_per_joule, 6),
            "efficiency_score": round(self.efficiency_score, 4),
        }


def compute_efficiency(
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    reasoning_tokens: int = 0,
    total_tokens: int = 0,
    cost_input_per_m: float = 0.27,
    cost_output_per_m: float = 1.10,
    cost_reasoning_per_m: float = 0.14,
    solution: SolutionMetrics | None = None,
) -> EfficiencyMetrics:
    """Compute complete resource efficiency metrics.

    Args:
        prompt_tokens: Input tokens consumed.
        completion_tokens: Output tokens produced.
        reasoning_tokens: Hidden reasoning tokens (DeepSeek R1 thinking budget).
        total_tokens: Grand total (can exceed sum due to cache).
        cost_input_per_m: Provider pricing per 1M input tokens.
        cost_output_per_m: Provider pricing per 1M output tokens.
        cost_reasoning_per_m: Provider pricing per 1M reasoning tokens.
        solution: Optional solution quality metrics for density.

    Returns:
        EfficiencyMetrics with full breakdown.
    """
    m = EfficiencyMetrics()

    m.prompt_tokens = prompt_tokens
    m.completion_tokens = completion_tokens
    m.reasoning_tokens = reasoning_tokens
    m.total_tokens = total_tokens or (prompt_tokens + completion_tokens + reasoning_tokens)

    # Thinking overhead
    m.thinking_ratio = reasoning_tokens / max(m.total_tokens, 1)
    m.output_efficiency = completion_tokens / max(m.total_tokens, 1)

    # Cost
    m.cost_input_usd = prompt_tokens * cost_input_per_m / 1_000_000
    m.cost_output_usd = completion_tokens * cost_output_per_m / 1_000_000
    m.cost_reasoning_usd = reasoning_tokens * cost_reasoning_per_m / 1_000_000
    m.total_cost_usd = m.cost_input_usd + m.cost_output_usd + m.cost_reasoning_usd

    # Energy
    m.energy_input_j = prompt_tokens * ENERGY_PER_PROMPT_TOKEN
    m.energy_output_j = completion_tokens * ENERGY_PER_OUTPUT_TOKEN
    m.energy_reasoning_j = reasoning_tokens * ENERGY_PER_REASONING_TOKEN
    m.total_energy_j = m.energy_input_j + m.energy_output_j + m.energy_reasoning_j

    # Solution density
    if solution:
        m.lines_of_code = solution.lines_of_code
        m.solution_density = solution.lines_of_code / max(m.total_tokens, 1)
        m.correctness_per_dollar = solution.correctness_score / max(m.total_cost_usd, 0.000001)
        m.quality_per_joule = solution.composite_score / max(m.total_energy_j, 0.01)
        m.efficiency_score = solution.composite_score / max(m.total_cost_usd, 0.000001)

    return m
