"""Multi-session story orchestrator — sequential agentic sessions with git history.

Each experiment cell is a *story* — N sequential coding sessions, each building
on the prior session's git commit. This captures compounding effects
(architectural drift, convention erosion, decision cascading) that single-session
experiments cannot observe.

Architecture:
    Session 1 → git commit A → Session 2 (starts from A) → git commit B → ...

Split into a package (refactor-repair Debt-1, second): the data model (``models``), the
perturbation conditions (``conditions``), the run loop (``orchestration``), the persistence/IO
helpers (``persistence``), and the built-in story catalog (``builtins``). This module re-exports
the whole surface so existing consumers (``scripts/run_story.py``, the analyzers, the lab books,
the tests) import from ``agentic_dynamics.runtime.story`` exactly as before — including
``compile_mutation``, which the story test suite monkeypatches.
"""

from __future__ import annotations

from agentic_dynamics.measurement.mutation import (  # noqa: F401  # re-exported (monkeypatched in tests)
    MutationArtifact,
    apply_mutation,
    compile_mutation,
)
from agentic_dynamics.runtime.story.builtins import (  # noqa: F401
    BUILTIN_STORIES,
    notification_service_story,
    static_site_gen_story,
    task_manager_story,
)
from agentic_dynamics.runtime.story.conditions import (  # noqa: F401
    CONDITION_STRENGTH,
    PerturbationCondition,
    condition_to_mutations,
)
from agentic_dynamics.runtime.story.models import (  # noqa: F401
    SessionResult,
    SessionSpec,
    StoryConfig,
    StoryResult,
)
from agentic_dynamics.runtime.story.orchestration import (  # noqa: F401
    _count_tests,
    _prepare_worktree,
    run_story,
)
from agentic_dynamics.runtime.story.persistence import (  # noqa: F401
    _detect_or_use,
    _estimate_session_cost,
    _estimate_subagent_cost,
    _extract_session_id_from_stdout,
    _git,
    _list_tracked_files,
    _opencode_db,
    _read_session_id,
    _sum_billed_tokens_from_jsonl,
    load_story_result,
    save_story_result,
)

__all__ = [
    "MutationArtifact",
    "apply_mutation",
    "compile_mutation",
    "BUILTIN_STORIES",
    "notification_service_story",
    "static_site_gen_story",
    "task_manager_story",
    "CONDITION_STRENGTH",
    "PerturbationCondition",
    "condition_to_mutations",
    "SessionResult",
    "SessionSpec",
    "StoryConfig",
    "StoryResult",
    "_count_tests",
    "_prepare_worktree",
    "run_story",
    "load_story_result",
    "save_story_result",
]
