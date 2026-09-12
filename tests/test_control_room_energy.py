"""Tests for the rule-4 ``energy``/EPM projection (step 7, d5 Phase 3).

Pins: the energy model comes from the single writer (``measurement.efficiency``); EPM and the
ranking are served from the published website data with their provenance labels ([X] /
[C]/[X]); the ONE measured quantity — per-session energy — is a named unknown, and absent
published data yields unknowns, never empty values passed off as readings.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _path in (_ROOT, _ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from agentic_dynamics.control.projections.energy import (  # noqa: E402
    SCHEMA,
    build_energy,
)
from agentic_dynamics.measurement.efficiency import (  # noqa: E402
    ENERGY_PER_OUTPUT_TOKEN,
    ENERGY_PER_PROMPT_TOKEN,
    ENERGY_PER_REASONING_TOKEN,
)

_NOW = "2026-09-12T12:00:00+00:00"


def _published():
    return {
        "external_sources": {
            "epm_baseline": {"value": "1.6%/yr", "provenance": "X", "source": "IEA WEO 2024"},
            "epm_aggressive": {"value": "2.5%/yr", "provenance": "X", "source": "Aggressive"},
        },
        "energy_ranking": [
            {"id": "anthropic/claude-haiku-4-5", "avg_energy_j": 18526.7, "avg_energy_j_per_loc": 11.7}
        ],
    }


def test_energy_model_constants_are_imported_not_copied():
    payload = build_energy(_published(), now=_NOW)
    assert payload["schema"] == SCHEMA
    model = payload["energy_model"]
    assert model["per_prompt_token_j"] == ENERGY_PER_PROMPT_TOKEN
    assert model["per_output_token_j"] == ENERGY_PER_OUTPUT_TOKEN
    assert model["per_reasoning_token_j"] == ENERGY_PER_REASONING_TOKEN
    assert model["class"] == "[C]/[X]"
    assert "efficiency.py" in model["source"]


def test_epm_and_ranking_are_published_scenarios_with_labels():
    payload = build_energy(_published(), now=_NOW)
    assert payload["epm"]["state"] == "published"
    assert payload["epm"]["class"] == "[X]"
    assert payload["epm"]["baseline"]["value"] == "1.6%/yr"
    assert payload["energy_ranking"]["state"] == "published"
    assert payload["energy_ranking"]["class"] == "[C]/[X]"
    assert payload["energy_ranking"]["models"][0]["avg_energy_j"] == 18526.7


def test_measured_and_horizon_are_named_unknowns():
    payload = build_energy(_published(), now=_NOW)
    assert payload["measured_session_energy"]["state"] == "unknown"
    assert payload["measured_session_energy"]["class"] == "[M]"
    assert payload["flip_horizon"]["state"] == "unknown"
    assert payload["flip_horizon"]["class"] == "[P]"


def test_absent_published_data_is_a_named_unknown():
    payload = build_energy(None, now=_NOW)
    assert payload["epm"]["state"] == "unknown"
    assert payload["energy_ranking"]["state"] == "unknown"
    assert payload["energy_ranking"]["class"] == "[C]/[X]"
