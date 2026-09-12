"""Model cost-policy guard — the spend-classification seam (per-token vs subscription).

Cost model (operator-declared, 2026-08-31; default re-pointed 2026-09-12):
- ``deepseek/*`` is the ONLY per-token API cost. ``deepseek-v4-pro`` is the expensive
  per-token tier and is DENIED by default — it requires ``FINOPS_ALLOW_PRO=1``.
- ``openai/*`` is a subscription account (5-hour windows + weekly caps) — marginal cost
  is zero within the subscription, so it carries the default for workflow/story/
  spend-heavy execution. ``anthropic/*`` is decommissioned on this host (the OAuth family
  was revoked server-side; logins are brittle — the operator retired it 2026-09-12), so
  NO maintained default points at it.
- ``deepseek-v4-flash`` remains allowed: cheap per-token tier for instrument tasks
  (supervise monitor, mutation authoring, prompt construction, legacy advisory reviews).

The guard is the admission check at every spend entry point: missing cost provenance is
a *denial* condition downstream (``cost_source`` tracking), never a pass.
"""

from __future__ import annotations

import os

PER_TOKEN_PROVIDER = "deepseek"
PRO_MODEL = "deepseek/deepseek-v4-pro"
FLASH_MODEL = "deepseek/deepseek-v4-flash"
#: The default model for spend-capable scripts when none is given (env ``FINOPS_MODEL``
#: overrides at the call sites). De-Claude switch (2026-09-12): the operator runs the
#: OpenAI subscription arm — Claude auth is revoked and logins are brittle. NOTE: the
#: model must be addressable by the host's opencode config (a user-level entry maps
#: ``openai/gpt-6-astra``; containerized fleets need the same entry in their config mount).
SUBSCRIPTION_DEFAULT = "openai/gpt-6-astra"

ALLOW_PRO_ENV = "FINOPS_ALLOW_PRO"


class ModelPolicyError(RuntimeError):
    """A spend-capable model was requested without the required opt-in."""


def is_pro_per_token(model: str) -> bool:
    """True for the expensive per-token tier (deepseek-v4-pro)."""
    return model == PRO_MODEL or model.endswith("/deepseek-v4-pro")


def ensure_model_allowed(model: str) -> None:
    """Refuse the per-token pro tier unless the operator explicitly opts in.

    Raises ModelPolicyError for ``deepseek-v4-pro`` unless FINOPS_ALLOW_PRO is a
    truthy env var. Every other model passes (subscription tiers + flash).
    """
    if is_pro_per_token(model) and not os.environ.get(ALLOW_PRO_ENV):
        raise ModelPolicyError(
            f'model "{model}" is the per-token pro tier — the only direct API spend. '
            f"Refusing unless {ALLOW_PRO_ENV}=1 (the subscription default is "
            f'"{SUBSCRIPTION_DEFAULT}"; other openai/gpt subscription tiers pass; '
            f'"{FLASH_MODEL}" for cheap instrument tasks).'
        )
