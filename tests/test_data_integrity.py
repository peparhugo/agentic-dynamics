"""Regression guards for the Phase-1 data-integrity remediation.

These assert, at the source level, that the fabrication/duplication
anti-patterns the architecture review flagged (P0-1, P0-2, P0-3) do not
return. They are cheap and run with no external dependencies.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(rel: str) -> str:
    return (ROOT / rel).read_text()


def test_no_duplicate_pricing_in_constants():
    # P0-2: _constants.py must not carry a second PROVIDER_PRICING.
    assert "PROVIDER_PRICING" not in _read("scripts/_constants.py")


def test_no_fabricated_pass_rate_in_build_data():
    # P0-1: compute_story_models must never set tests_passed == tests_total
    # or hardcode a 100% pass rate.
    src = _read("scripts/build_data.py")
    assert "all stories passed" not in src
    assert 'pass_rate": f"100%' not in src


def test_basin_cost_fallback_uses_get_pricing():
    # P0-2: basin.py must not hardcode a literal per-token rate.
    src = _read("src/instrument/basin.py")
    assert "0.27" not in src
    assert "get_pricing" in src


def test_no_resurrected_arch_constants_in_build_data():
    # P0-3: build_data.py must not emit the debunked 500B/37B active-param claims.
    src = _read("scripts/build_data.py")
    assert '"claude_active_params"' not in src
    assert '"37B"' not in src
