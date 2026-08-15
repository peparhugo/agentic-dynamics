import pytest

from instrument.efficiency import compute_cost_estimate, get_pricing


def test_get_pricing_deepseek():
    pricing = get_pricing("deepseek", "deepseek-v4-pro")
    assert pricing["input"] == 0.435
    assert pricing["output"] == 0.87
    assert pricing["cache_read"] == 0.003625
    assert pricing["cache_write"] == 0.435


def test_get_pricing_anthropic():
    pricing = get_pricing("anthropic", "claude-fable-5")
    assert pricing["input"] == 3.00
    assert pricing["output"] == 15.00
    assert pricing["cache_read"] == 0.30
    assert pricing["cache_write"] == 3.75


def test_get_pricing_openai():
    pricing = get_pricing("openai", "gpt-5")
    assert pricing["input"] == 1.25
    assert pricing["output"] == 10.00
    assert pricing["cache_read"] == 0.625
    assert pricing["cache_write"] == 2.50


def test_get_pricing_detect_by_model_id():
    pricing = get_pricing("unknown", "deepseek-something")
    assert pricing["input"] == 0.435


def test_get_pricing_raises_on_unknown():
    with pytest.raises(ValueError):
        get_pricing("completely_unknown", "also_unknown")


def test_get_pricing_anthropic_via_claude():
    pricing = get_pricing("anthropic", "claude-fable-5")
    assert pricing["output"] == 15.00


def test_get_pricing_sonnet5():
    pricing = get_pricing("anthropic", "claude-sonnet-5")
    assert pricing["output"] == 10.00


def test_get_pricing_luna():
    pricing = get_pricing("openai", "gpt-5.6-luna")
    assert pricing["output"] == 1.20
    assert pricing["input"] == 0.20


def test_get_pricing_openai_via_gpt():
    pricing = get_pricing("", "gpt-5-mini")
    assert pricing["output"] == 10.00


def test_get_pricing_deepseek_flash():
    pricing = get_pricing("deepseek", "deepseek-v4-flash")
    assert pricing["input"] == 0.14
    assert pricing["output"] == 0.28
    assert pricing["cache_read"] == 0.0028


def test_get_pricing_haiku():
    pricing = get_pricing("anthropic", "claude-haiku-4-5")
    assert pricing["input"] == 1.00
    assert pricing["output"] == 5.00
    assert pricing["cache_read"] == 0.10
    assert pricing["cache_write"] == 1.25


def test_get_pricing_sol():
    pricing = get_pricing("openai", "gpt-5.6-sol")
    assert pricing["input"] == 5.00
    assert pricing["output"] == 30.00
    assert pricing["cache_read"] == 0.50
    assert pricing["cache_write"] == 6.25


def test_get_pricing_terra():
    pricing = get_pricing("openai", "gpt-5.6-terra")
    assert pricing["input"] == 2.50
    assert pricing["output"] == 15.00
    assert pricing["reasoning"] == 15.00
    assert pricing["cache_read"] == 0.25
    assert pricing["cache_write"] == 3.125


def test_get_pricing_sol_does_not_fall_through_to_generic_openai():
    assert get_pricing("", "gpt-5.6-sol")["output"] == 30.00
    assert get_pricing("", "gpt-5")["output"] == 10.00


def test_compute_cost_estimate_terra_base():
    est = compute_cost_estimate(
        prompt_tokens=100_000, completion_tokens=10_000, reasoning_tokens=5_000,
        cache_read_tokens=50_000, cache_write_tokens=0,
        context_tokens=150_000, provider="openai", model="gpt-5.6-terra",
    )
    assert est["pricing_key"] == "openai-terra"
    assert est["long_context_tier"] is False
    assert est["total_cost_usd"] == pytest.approx(
        (100_000 * 2.50 + 10_000 * 15.00 + 5_000 * 15.00 + 50_000 * 0.25) / 1_000_000
    )


def test_compute_cost_estimate_applies_long_context_tier():
    base = compute_cost_estimate(
        prompt_tokens=100_000, completion_tokens=0, reasoning_tokens=0,
        cache_read_tokens=100_000, context_tokens=200_000,
        provider="openai", model="gpt-5.6-terra",
    )
    tiered = compute_cost_estimate(
        prompt_tokens=200_000, completion_tokens=0, reasoning_tokens=0,
        cache_read_tokens=200_000, context_tokens=400_000,
        provider="openai", model="gpt-5.6-terra",
    )
    assert base["long_context_tier"] is False
    assert tiered["long_context_tier"] is True
    # 400k context: 50% of input+cache tokens billed at base, 50% at tier
    expected_input = 200_000 * (2.50 * 0.5 + 5.00 * 0.5)
    expected_cache = 200_000 * (0.25 * 0.5 + 0.50 * 0.5)
    assert tiered["total_cost_usd"] == pytest.approx(
        (expected_input + expected_cache) / 1_000_000
    )


def test_compute_cost_estimate_no_tier_for_non_openai():
    est = compute_cost_estimate(
        prompt_tokens=300_000, completion_tokens=0, reasoning_tokens=0,
        cache_read_tokens=0, context_tokens=300_000,
        provider="deepseek", model="deepseek-v4-pro",
    )
    assert est["long_context_tier"] is False


def test_compute_cost_estimate_luna_is_flat_over_200k():
    est = compute_cost_estimate(
        prompt_tokens=200_000, completion_tokens=10_000, reasoning_tokens=0,
        cache_read_tokens=300_000, context_tokens=500_000,
        provider="openai", model="gpt-5.6-luna",
    )
    assert est["long_context_tier"] is False
    assert est["total_cost_usd"] == pytest.approx(
        (200_000 * 0.20 + 10_000 * 1.20 + 300_000 * 0.02) / 1_000_000
    )
