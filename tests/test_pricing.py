import pytest
from instrument.efficiency import get_pricing, PROVIDER_PRICING


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
