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
    for model in (SUBSCRIPTION_DEFAULT, "anthropic/claude-haiku-4-5", "openai/gpt-5.6-sol"):
        ensure_model_allowed(model)


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
