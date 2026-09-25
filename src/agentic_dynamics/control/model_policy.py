"""Model cost-policy guard — the spend-classification seam (per-token vs subscription).

Cost model (operator-declared, 2026-08-31; default re-pointed 2026-09-12; pro-tier denied
2026-09-24/25):
- ``deepseek/*`` is the ONLY per-token API cost. ``deepseek-v4-pro`` is the expensive
  per-token tier and is DENIED by default — it requires ``FINOPS_ALLOW_PRO=1``.
- Pro-tier models are DENIED by default (operator directive 2026-09-24: "we have to stop
  using pro — it's way too expensive and not as good as flash"): the per-token
  ``deepseek-v4-pro`` plus the OpenAI mid tiers ``openai/gpt-5.6-terra`` and
  ``openai/gpt-5.6-sol``. All require ``FINOPS_ALLOW_PRO=1``.
- The sanctioned spend split (operator, 2026-09-25): agent/review VOLUME runs on
  ``openai/gpt-5.6-luna`` (subscription-flat, the current cheap default since the
  deepseek-flash retirement); the ADVERSARIAL REVIEW runs on ``openai/gpt-6-astra``
  (the operator's designated adversary — also ``SUBSCRIPTION_DEFAULT``), a different
  model from the authoring cells by design.
- ``anthropic/*`` is decommissioned on this host (the OAuth family was revoked
  server-side; logins are brittle — the operator retired it 2026-09-12), so NO
  maintained default points at it.
- ``deepseek-v4-flash`` remains allowed: cheap per-token tier for instrument tasks
  (supervise monitor, mutation authoring, prompt construction, legacy advisory reviews) —
  retired upstream, successor pending the whitelist (register L39).

The guard is the admission check at every spend entry point: missing cost provenance is
a *denial* condition downstream (``cost_source`` tracking), never a pass.
"""

from __future__ import annotations

import os

PER_TOKEN_PROVIDER = "deepseek"
PRO_MODEL = "deepseek/deepseek-v4-pro"
FLASH_MODEL = "deepseek/deepseek-v4-flash"
#: Pro-tier models DENIED by default (operator directive 2026-09-24/25): the per-token
#: deepseek pro tier + the OpenAI mid tiers terra/sol. ``openai/gpt-6-astra`` (the
#: designated adversarial-review model) and ``openai/gpt-5.6-luna`` stay allowed.
DENIED_MODELS = frozenset({PRO_MODEL, "openai/gpt-5.6-terra", "openai/gpt-5.6-sol"})
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


def is_denied_by_default(model: str) -> bool:
    """True for a pro-tier model (deepseek per-token pro, or the terra/sol mid tiers)."""
    return is_pro_per_token(model) or model in DENIED_MODELS


def ensure_model_allowed(model: str) -> None:
    """Refuse pro-tier models unless the operator explicitly opts in.

    Raises ModelPolicyError for ``deepseek-v4-pro`` / ``openai/gpt-5.6-terra`` /
    ``openai/gpt-5.6-sol`` unless FINOPS_ALLOW_PRO is a truthy env var. Everything else
    passes (``openai/gpt-5.6-luna`` volume, ``openai/gpt-6-astra`` the adversary, flash).
    """
    if is_denied_by_default(model) and not os.environ.get(ALLOW_PRO_ENV):
        raise ModelPolicyError(
            f'model "{model}" is pro-tier — refused by default (operator, 2026-09-24: '
            f'"stop using pro"). Set {ALLOW_PRO_ENV}=1 to override. The sanctioned split: '
            f'volume on "openai/gpt-5.6-luna"; the adversarial review on '
            f'"openai/gpt-6-astra".'
        )
