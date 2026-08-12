"""Resource efficiency measurement — the thermodynamic cost of reasoning.

Captures token breakdown, cost, and estimated energy consumption.
Uses a bounded-range approach: lower bound = observables (tokens),
upper bound = disclosed architecture × known hardware specs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .solution import SolutionMetrics


# Architecture constants — publicly disclosed where available.
# DeepSeek: 49B active parameters (MoE V4 Pro, publicly disclosed).
# Claude: undisclosed — placeholder for energy model estimation only.
# GPT: undisclosed.
# Energy estimates are modeled scenarios, not measured quantities.
DEEPSEEK_ACTIVE_PARAMS = 49e9    # 49B active (MoE V4 Pro, publicly disclosed)
DEEPSEEK_GPU_TDP = 350           # H800 TDP (W)
CLAUDE_EST_ACTIVE_PARAMS = None  # Not independently verifiable — do not use for claims
CLAUDE_EST_GPU_TDP = None        # Not independently verifiable
_ENERGY_MODEL_AVAILABLE = False  # Energy model uses undisclosed architecture estimates

# Energy constants — per-token Joules
# Based on TokenPowerBench (Niu et al., AAAI 2026): 0.1-2.0 J/tok range
# Conservative lower-bound estimates for modern hardware
ENERGY_PER_PROMPT_TOKEN = 0.08    # Joules per input token
ENERGY_PER_OUTPUT_TOKEN = 0.23   # Joules per output token
ENERGY_PER_REASONING_TOKEN = 0.47  # Joules per reasoning token (RL models)

# Provider pricing — historical snapshot from experiment billing date.
# Actual DB costs were billed at these rates. Don't retroactively change.
# For current pricing, see CURRENT_REFERENCE_PRICING below.
#
# Pricing snapshot: experiment billing dates (2026-Q2 through 2026-Q3 depending on model release).
# Actual DB costs were billed at these rates. Don't retroactively change.
# These rates reflect what was actually charged during the v0.5 experiment corpus.
PROVIDER_PRICING: dict[str, dict[str, float]] = {
    "deepseek": {
        "input": 0.435, "output": 0.87, "reasoning": 0.87,
        "cache_read": 0.003625, "cache_write": 0.435,
        "source": "api-docs.deepseek.com — DeepSeek V4 Pro pricing (Aug 2026)",
    },
    "anthropic": {
        "input": 3.00, "output": 15.00, "reasoning": 15.00,
        "cache_read": 0.30, "cache_write": 3.75,
    },
    "openai": {
        "input": 1.25, "output": 10.00, "reasoning": 10.00,
        "cache_read": 0.625, "cache_write": 2.50,
    },
    # v0.9 models — added Aug 2026
    "anthropic-sonnet5": {
        "input": 2.00, "output": 10.00, "reasoning": 10.00,
        "cache_read": 0.20, "cache_write": 2.50,
        "note": "Claude Sonnet 5 intro pricing through Aug 31, 2026. Sep 1: $3/$15.",
    },
    "openai-luna": {
        "input": 0.20, "output": 1.20, "reasoning": 1.20,
        "cache_read": 0.02, "cache_write": 0.25,
    },
}

# Current reference pricing (2026-08-11) — for comparison only. Experiment billing
# uses PROVIDER_PRICING above. These are provider-disclosed rates and may not
# reflect actual billed amounts (cache, batch discounts, tier pricing apply).
# Sources: api-docs.deepseek.com, docs.anthropic.com, platform.openai.com
CURRENT_REFERENCE_PRICING: dict[str, dict[str, float]] = {
    "deepseek": {
        "input": 0.435, "output": 0.87, "reasoning": 0.87,
        "cache_read": 0.003625, "cache_write": 0.435,
    },
    "anthropic": {
        "input": 10.00, "output": 50.00, "reasoning": 50.00,
        "cache_read": 1.00, "cache_write": 12.50,
    },
    "openai": {
        "input": 5.00, "output": 30.00, "reasoning": 30.00,
        "cache_read": 2.50, "cache_write": 10.00,
    },
    # v0.9 reference pricing
    "anthropic-sonnet5": {
        "input": 2.00, "output": 10.00, "reasoning": 10.00,
        "cache_read": 0.20, "cache_write": 2.50,
        "note_snapshot": "2026-08-11. Intro $2/$10 through Aug 31. Sep 1: $3/$15.",
    },
    "openai-luna": {
        "input": 0.20, "output": 1.20, "reasoning": 1.20,
        "cache_read": 0.02, "cache_write": 0.25,
        "note_snapshot": "2026-08-11. GPT-5.6 Luna standard pricing.",
    },
}

def get_pricing(provider_id: str, model_id: str = "") -> dict[str, float]:
    """Get approximate pricing for a provider/model.
    
    Returns per-million-token rates. Falls back to generic provider rates
    if model-specific pricing is unavailable. Returns historical billing
    rates for pre-v0.9 models, current rates for v0.9+ models.
    """
    combined = f"{provider_id} {model_id}".lower()
    if "deepseek" in combined:
        return PROVIDER_PRICING["deepseek"]
    if "sonnet" in combined:
        return PROVIDER_PRICING["anthropic-sonnet5"]
    if "luna" in combined:
        return PROVIDER_PRICING["openai-luna"]
    if any(k in combined for k in ("anthropic", "claude")):
        return PROVIDER_PRICING["anthropic"]
    if any(k in combined for k in ("openai", "gpt")):
        return PROVIDER_PRICING["openai"]
    raise ValueError(f"Unknown provider: provider={provider_id!r}, model={model_id!r}")


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
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    # Thinking overhead
    thinking_ratio: float = 0.0      # reasoning_tokens / total_tokens
    output_efficiency: float = 0.0   # completion_tokens / total_tokens

    # Cost (USD)
    cost_input_usd: float = 0.0
    cost_output_usd: float = 0.0
    cost_reasoning_usd: float = 0.0
    cost_cache_usd: float = 0.0
    total_cost_usd: float = 0.0
    cost_is_estimated: bool = True  # True = computed from pricing; False = from API/DB

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
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "thinking_ratio": round(self.thinking_ratio, 4),
            "output_efficiency": round(self.output_efficiency, 4),
            "cost_input_usd": round(self.cost_input_usd, 6),
            "cost_output_usd": round(self.cost_output_usd, 6),
            "cost_reasoning_usd": round(self.cost_reasoning_usd, 6),
            "cost_cache_usd": round(self.cost_cache_usd, 6),
            "total_cost_usd": round(self.total_cost_usd, 6),
            "cost_is_estimated": self.cost_is_estimated,
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
    *,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    provider: str = "",
    model: str = "",
    solution: SolutionMetrics | None = None,
) -> EfficiencyMetrics:
    """Compute complete resource efficiency metrics.

    Args:
        prompt_tokens: Input tokens consumed.
        completion_tokens: Output tokens produced.
        reasoning_tokens: Hidden reasoning tokens.
        total_tokens: Grand total (can exceed sum due to cache).
        cache_read_tokens: Tokens read from provider cache.
        cache_write_tokens: Tokens written to provider cache.
        provider: Provider ID (e.g. 'deepseek', 'anthropic', 'openai').
        model: Model ID for future per-model pricing.
        solution: Optional solution quality metrics for density.

    Returns:
        EfficiencyMetrics with full breakdown.
    """
    m = EfficiencyMetrics()
    pricing = get_pricing(provider, model)

    m.prompt_tokens = prompt_tokens
    m.completion_tokens = completion_tokens
    m.reasoning_tokens = reasoning_tokens
    m.cache_read_tokens = cache_read_tokens
    m.cache_write_tokens = cache_write_tokens
    m.total_tokens = total_tokens or (prompt_tokens + completion_tokens + reasoning_tokens)

    # Thinking overhead
    m.thinking_ratio = reasoning_tokens / max(m.total_tokens, 1)
    m.output_efficiency = completion_tokens / max(m.total_tokens, 1)

    # Cost — estimated from token counts × approximate provider pricing
    m.cost_input_usd = prompt_tokens * pricing["input"] / 1_000_000
    m.cost_output_usd = completion_tokens * pricing["output"] / 1_000_000
    m.cost_reasoning_usd = reasoning_tokens * pricing["reasoning"] / 1_000_000
    m.cost_cache_usd = (cache_read_tokens * pricing["cache_read"] + cache_write_tokens * pricing["cache_write"]) / 1_000_000
    m.total_cost_usd = m.cost_input_usd + m.cost_output_usd + m.cost_reasoning_usd + m.cost_cache_usd
    m.cost_is_estimated = True

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


def estimate_bounded_energy(
    provider: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    reasoning_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> dict[str, Any]:
    """Compute bounded energy range using physicist's approach.

    Lower bound: observables (token counts). Assumes equal architecture.
    Upper bound: disclosed architecture × known hardware specs.

    Returns a dict with lower, mid, and upper energy estimates (Joules)
    and the corresponding ratios.

    Args:
        provider: "deepseek" or "claude" (or "anthropic")
        prompt_tokens: Non-cached input tokens
        completion_tokens: Output tokens
        reasoning_tokens: Reasoning tokens (DeepSeek only)
        cache_read_tokens: Tokens read from cache (Claude)
        cache_write_tokens: Tokens written to cache (Claude)
    """
    # All-provider baseline: token-count-based energy
    # Assume ~0.1 J/token as a conservative per-token energy floor
    # (TokenPowerBench finds 0.1-2 J/tok depending on hardware)
    J_PER_TOKEN_FLOOR = 0.1

    total_observable = prompt_tokens + completion_tokens + reasoning_tokens
    total_with_cache = total_observable + cache_read_tokens + cache_write_tokens

    if provider in ("deepseek",):
        arch_mult = 1.0
        hw_mult = 1.0
    else:
        arch_mult = 1.0   # architecture multiplier not independently verifiable for closed models
        hw_mult = 1.0     # hardware multiplier not independently verifiable for closed models

    lower_bound_j = total_observable * J_PER_TOKEN_FLOOR
    mid_bound_j = total_with_cache * J_PER_TOKEN_FLOOR * arch_mult
    upper_bound_j = total_with_cache * J_PER_TOKEN_FLOOR * arch_mult * hw_mult

    return {
        "provider": provider,
        "total_observable_tokens": total_observable,
        "total_with_cache_tokens": total_with_cache,
        "active_params_ratio": round(arch_mult, 1),
        "hardware_tdp_ratio": round(hw_mult, 1),
        "energy_lower_bound_j": round(lower_bound_j, 0),
        "energy_mid_bound_j": round(mid_bound_j, 0),
        "energy_upper_bound_j": round(upper_bound_j, 0),
        "energy_ratio_range": f"{arch_mult:.0f}x (energy model uses undisclosed architecture estimates)",
        "joules_per_token": J_PER_TOKEN_FLOOR,
        "energy_model_note": "Energy estimates are modeled scenarios, not measured quantities. Architecture constants for closed models are not verifiable.",
    }
