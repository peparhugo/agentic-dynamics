"""Model cost-policy guard tests — per-token pro tier is denied without explicit opt-in."""

import os
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
    for model in (SUBSCRIPTION_DEFAULT, "openai/gpt-5.6-sol"):
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


@pytest.mark.parametrize("model", [PRO_MODEL, "deepseek/deepseek-v4-pro", "provider/deepseek-v4-pro"])
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
