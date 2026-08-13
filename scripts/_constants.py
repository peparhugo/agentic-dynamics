"""Shared constants for the FinOps framework pipeline scripts."""

import re as _re

MODEL_LABELS = {
    "deepseek/deepseek-v4-pro": "DeepSeek v4 Pro",
    "openai/gpt-5.6-luna": "GPT-5.6 Luna",
    "anthropic/claude-sonnet-5": "Claude Sonnet 5",
    "deepseek/deepseek-v4-flash": "DeepSeek v4 Flash",
    "anthropic/claude-fable-5": "Claude Fable 5",
    "openai/gpt-5": "GPT-5",
    "openai/gpt-5-mini": "GPT-5-mini",
    "openai/gpt-5-nano": "GPT-5-nano",
    "openai/gpt-5.5": "GPT-5.5",
    "openai/gpt-5.6": "GPT-5.6",
    "openai/gpt-5.6-fast": "GPT-5.6-fast",
}

# Pricing lives in src/instrument/efficiency.py (single source of truth).
# Do not re-add provider pricing here — import `get_pricing` from
# instrument.efficiency instead.

EXPERIMENT_SESSION_PATTERNS = [
    "flask", "api", "rest", "task", "url", "probe", "std_", "sweep", "batch", "config",
    "silent", "constraint", "recovery", "baseline", "perturb", "inject", "phantom",
    "remove_critical", "invert", "shift_framing", "alien", "false_premise", "competing",
    "force_abandonment", "reverse_causality", "contradiction", "data_table",
    "collaborat", "url_shortener", "iterative", "cross-domain", "standardized",
    "silent_mode", "factorial", "architecture_redesign", "search_kv", "web_crawler",
    "notification", "autocomplete", "twitter", "form_wizard", "social_graph",
    "mint_financial", "fastapi_maintenance", "flask_maintenance", "comparative",
    "r1]", "r2]", "r3]", "s0.5", "s0.8", "s1.0", "2rep",
]


def bootstrap_ci(values, n_resamples=1000, ci=95, seed=42):
    """Compute bootstrap confidence interval for a list of values."""
    import random
    random.seed(seed)
    n = len(values)
    if n < 3:
        return None
    means = []
    for _ in range(n_resamples):
        sample = [values[random.randint(0, n - 1)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo_idx = int((100 - ci) / 2 / 100 * n_resamples)
    hi_idx = int((100 + ci) / 2 / 100 * n_resamples) - 1
    return [round(means[lo_idx], 4), round(means[hi_idx], 4)]


def normalize_task(experiment: str) -> str:
    """Strip perturbation strength and repetition suffixes from task names."""
    return _re.sub(r'_(s\d+\.\d+|r\d+)$', '', experiment)


import os as _os
WORKTREE_ROOT = _os.environ.get("FINOPS_WORKTREE_ROOT", "/tmp")
WORKTREE_GLOB = _os.path.join(WORKTREE_ROOT, "exp_*")
