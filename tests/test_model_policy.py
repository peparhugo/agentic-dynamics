"""Model cost-policy guard tests — per-token pro tier is denied without explicit opt-in."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.fast

from agentic_dynamics.control.model_policy import (
    FLASH_MODEL,
    PRO_MODEL,
    SUBSCRIPTION_DEFAULT,
    ModelPolicyError,
    ensure_model_allowed,
    is_pro_per_token,
)


def test_subscription_models_always_allowed():
    for model in (SUBSCRIPTION_DEFAULT, "openai/gpt-5.6-luna", "openai/gpt-6-astra"):
        ensure_model_allowed(model)


def test_the_default_model_is_the_openai_arm_and_not_claude():
    """De-Claude pin (2026-09-12): the maintained default is the OpenAI subscription arm.

    Claude is decommissioned on this host (the OAuth family was revoked server-side and
    re-logins are brittle), so no maintained default may point at ``anthropic/*`` again.
    """
    assert SUBSCRIPTION_DEFAULT == "openai/gpt-6-astra"
    assert not SUBSCRIPTION_DEFAULT.startswith("anthropic/")


def test_flash_always_allowed():
    ensure_model_allowed(FLASH_MODEL)


@pytest.mark.parametrize(
    "model",
    [
        PRO_MODEL,
        "deepseek/deepseek-v4-pro",
        "provider/deepseek-v4-pro",
        "openai/gpt-5.6-terra",
        "openai/gpt-5.6-sol",
    ],
)
def test_pro_denied_without_opt_in(model):
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("FINOPS_ALLOW_PRO", None)
        with pytest.raises(ModelPolicyError):
            ensure_model_allowed(model)


def test_pro_allowed_with_explicit_opt_in():
    with patch.dict(os.environ, {"FINOPS_ALLOW_PRO": "1"}):
        ensure_model_allowed(PRO_MODEL)


def test_is_pro_per_token():
    assert is_pro_per_token("deepseek/deepseek-v4-pro")
    assert is_pro_per_token("anything/deepseek-v4-pro")
    assert not is_pro_per_token(FLASH_MODEL)
    assert not is_pro_per_token(SUBSCRIPTION_DEFAULT)


def test_cell_visible_config_maps_the_custom_adversary_model():
    """The adversary alias must resolve WITHOUT the operator's user config.

    Fleet cells run opencode with an EMPTY XDG config namespace (their per-attempt
    state dir) and see only the repo's project config. A custom model alias that
    lives solely in ``~/.config/opencode/opencode.jsonc`` is invisible in-cell — the
    2026-09-25 att5-flash failure: the first in-cell ``openai/gpt-6-astra`` call died
    with an opencode "Unexpected server error" (0 tokens, 12.7s) because the alias
    could not resolve (the host resolves it; an empty-config process lists no astra).
    ``opencode.json`` is the versioned, cell-visible home for that mapping — the same
    entry ``model_policy`` names: "containerized fleets need the same entry in their
    config mount".
    """
    config = json.loads(
        (Path(__file__).resolve().parent.parent / "opencode.json").read_text(encoding="utf-8")
    )
    models = config.get("provider", {}).get("openai", {}).get("models", {})
    assert "gpt-6-astra" in models, (
        "opencode.json must map openai/gpt-6-astra for cells (whose XDG config is "
        "empty): a user-level-only entry breaks every in-cell adversarial phase"
    )
