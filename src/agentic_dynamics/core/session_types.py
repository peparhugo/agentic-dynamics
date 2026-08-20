"""The single task-type / session-pattern vocabulary.

This module is the one source of truth for the two vocabularies that were
previously split (or worse, reverse-imported) across the package and the scripts
tree. It is a *leaf* module — it imports only the standard library — so importing
it never drags the Redis/Chroma/Neo4j machinery of the wider package along (see
``docs/review/restructure.md`` R3/R6/R9).

What lives here, and why:

* ``EXPERIMENT_SESSION_PATTERNS`` — the substring list that classifies an opencode
  session *title* as an "experiment" title (vs. a meta-analysis or stray session).
  It used to be declared in ``scripts/_constants.py`` and then reverse-imported,
  at module import time and by file path, back into ``ledger_ingestion.py`` — the
  only ``src/instrument -> scripts`` edge in the package. The list now lives next to
  its consumers and ``scripts/_constants.py`` imports *from* here (scripts -> src,
  the correct dependency direction).

* ``normalize_task`` — strips perturbation-strength / repetition suffixes from a
  task name (``"url_shortener_s0.8" -> "url_shortener"``). It was duplicated
  verbatim in ``routing.py`` and ``scripts/_constants.py``; both now re-export this
  single definition.

* ``TASK_TYPES`` / ``DEFAULT_TASK_TYPE`` — the story-session phase vocabulary that
  ``story.SessionSpec.task_type`` annotates (greenfield, feature_addition,
  integration, refactor, cross_cutting). Declared once so a stray free-form string
  can't silently fork the vocabulary.
"""

from __future__ import annotations

import re

# ── Task-type vocabulary (story sessions) ───────────────────────
#
# The phase labels a ``story.SessionSpec`` carries. ``DEFAULT_TASK_TYPE`` is what
# ``SessionSpec.from_dict`` falls back to when a session dict omits the field (the
# historical default was the bare string "feature_addition"; now it is named).

TASK_TYPES: frozenset[str] = frozenset(
    {"greenfield", "feature_addition", "integration", "refactor", "cross_cutting"}
)

DEFAULT_TASK_TYPE: str = "feature_addition"


# ── Session-pattern vocabulary (experiment title classification) ──
#
# Substrings that mark an opencode session title as an experiment session. Shared
# by ``scripts/analyze_worktrees.py`` (worktree discovery) and
# ``scripts/inventory.py`` (session classification). Kept as a ``list`` (not a set)
# because the historical consumers iterated it as an ordered list; the order has no
# semantic meaning, but preserving it keeps the diff reviewable and drop-in safe.

EXPERIMENT_SESSION_PATTERNS: list[str] = [
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


def normalize_task(name: str) -> str:
    """Strip perturbation-strength / repetition suffixes from a task name.

    ``"url_shortener_s0.8" -> "url_shortener"`` and
    ``"task_manager_r2" -> "task_manager"``; a plain name passes through unchanged.
    """
    return re.sub(r"_(s\d+\.\d+|r\d+)$", "", name)
