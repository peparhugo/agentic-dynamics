"""Shared constants for the FinOps framework pipeline scripts."""

from instrument.session_types import EXPERIMENT_SESSION_PATTERNS as EXPERIMENT_SESSION_PATTERNS
from instrument.session_types import normalize_task as normalize_task

MODEL_LABELS = {
    "deepseek/deepseek-v4-pro": "DeepSeek v4 Pro",
    "openai/gpt-5.6-luna": "GPT-5.6 Luna",
    "anthropic/claude-sonnet-5": "Claude Sonnet 5",
    "deepseek/deepseek-v4-flash": "DeepSeek v4 Flash",
    # "claude-fable-5" was a historical alias: the Claude CLI adapter silently mapped
    # fable-5 -> sonnet-5 until the fix, so EVERY historical "claude-fable-5" result
    # actually ran sonnet-5. Its label is normalized to "Claude Sonnet 5" (see
    # docs/HANDOFF_2026-08-19.md); the corpus model id is normalized separately in the
    # process_perturbation_resample payload.
    "anthropic/claude-fable-5": "Claude Sonnet 5",
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

# EXPERIMENT_SESSION_PATTERNS and normalize_task are imported from
# instrument.session_types (the single task-type / session-pattern vocabulary) —
# the dependency direction here is scripts -> src, not the reverse. Keep this
# re-export for the scripts that already do `from _constants import ...`.


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


import os as _os

WORKTREE_ROOT = _os.environ.get("FINOPS_WORKTREE_ROOT", "/tmp")
WORKTREE_GLOB = _os.path.join(WORKTREE_ROOT, "exp_*")


def probe_session_schema(db_path: str, required_columns: tuple[str, ...]) -> None:
    """Fail loudly if the opencode `session` table lacks the expected columns.

    Downstream queries depend on ``json_extract(model,'$...')`` and specific
    column names; a schema change otherwise yields zero sessions/tokens
    silently (P1-3).
    """
    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(session)")}
    except sqlite3.Error as exc:
        raise RuntimeError(f"opencode session table probe failed: {exc}") from exc
    finally:
        conn.close()
    missing = [c for c in required_columns if c not in cols]
    if missing:
        raise RuntimeError(
            f"opencode session table missing columns {missing!r} — schema drift? "
            f"Expected columns: {list(required_columns)!r}"
        )


def model_slug(model: str) -> str:
    """Derive a short, queue-safe slug from a ``provider/model`` id.

    Canonical slug shared by run_story.py and enqueue.py so result filenames
    and cell ids never collide (P1-5).
    """
    base = model.split("/", 1)[-1]
    slug = base.replace("-", "_").replace(".", "_").replace(" ", "_")
    return slug or "model"


# Single source of truth for per-session timeout (P1-5). worker.py derives its
# per-cell kill timeout from these so they can't drift apart.
SESSION_TIMEOUT = 1200
STORY_SESSIONS = 5
