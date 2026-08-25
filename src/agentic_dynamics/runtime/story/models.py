"""Story data model — the dataclasses that describe a story and its results.

Extracted from ``runtime/story.py`` (refactor-repair Debt-1). Pure value objects + YAML/JSON
serialization; no orchestration or I/O logic lives here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from agentic_dynamics.adapters.opencode import AgenticResult
from agentic_dynamics.core.session_types import DEFAULT_TASK_TYPE


@dataclass
class SessionSpec:
    """Definition of one session in a story."""

    session_number: int
    task_type: str  # see instrument.session_types.TASK_TYPES (greenfield, feature_addition, ...)
    prompt: str  # the actual task prompt for this session
    description: str = ""  # human-readable description

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_number": self.session_number,
            "task_type": self.task_type,
            "prompt": self.prompt,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SessionSpec:
        missing = [k for k in ("session_number", "prompt") if k not in d]
        if missing:
            raise ValueError(f"SessionSpec missing required fields: {missing}")
        return cls(
            session_number=d["session_number"],
            task_type=d.get("task_type", DEFAULT_TASK_TYPE),
            prompt=d["prompt"],
            description=d.get("description", ""),
        )


@dataclass
class StoryConfig:
    """Complete definition of a multi-session story.

    Can be loaded from YAML or constructed programmatically.
    """

    name: str
    description: str = ""
    language: str = "python"
    sessions: list[SessionSpec] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "language": self.language,
            "constraints": self.constraints,
            "sessions": [s.to_dict() for s in self.sessions],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> StoryConfig:
        return cls(
            name=d["name"],
            description=d.get("description", ""),
            language=d.get("language", "python"),
            constraints=d.get("constraints", []),
            sessions=[SessionSpec.from_dict(s) for s in d.get("sessions", [])],
        )

    @classmethod
    def from_yaml(cls, path: Path) -> StoryConfig:
        with open(path) as f:
            return cls.from_dict(yaml.safe_load(f))

    def to_yaml(self, path: Path) -> None:
        path.write_text(yaml.dump(self.to_dict(), sort_keys=False))


@dataclass
class SessionResult:
    """Results from one session within a story."""

    session_number: int
    task_type: str
    prompt: str
    commit_hash: str = ""
    commit_message: str = ""
    agentic: AgenticResult | None = None
    cost_usd: float = 0.0
    total_tokens: int = 0
    duration_s: float = 0.0
    files_changed: int = 0
    exit_code: int = 0
    error: str = ""
    continuation_used: bool = False
    continuation_cost_usd: float = 0.0
    subagent_cost_usd: float = 0.0
    subagent_sessions: int = 0
    test_count: int = 0
    test_lines: int = 0
    code_lines: int = 0
    # Instrumented ledger fields (attempt-level).
    confidence: float | None = None  # [H] execution-confidence signal (opencode.AgenticResult.confidence)
    answer_tokens: int = 0  # output tokens → deliverable (tool-call steps)
    explanation_tokens: int = 0  # output tokens → prose narration
    # Backend-reported token in/out split (additive to the flat ``total_tokens``), e.g.
    # ``{"in": 300, "out": 200}``. ``None`` = the backend reported no usage — the split is
    # coverage-not-available and the flat ``total_tokens`` remains the valid fallback.
    tokens: dict[str, int] | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "session_number": self.session_number,
            "task_type": self.task_type,
            "prompt": self.prompt[:200],
            "commit_hash": self.commit_hash,
            "commit_message": self.commit_message,
            "cost_usd": self.cost_usd,
            "total_tokens": self.total_tokens,
            "duration_s": self.duration_s,
            "files_changed": self.files_changed,
            "exit_code": self.exit_code,
            "error": self.error,
            "continuation_used": self.continuation_used,
            "continuation_cost_usd": self.continuation_cost_usd,
            "subagent_cost_usd": self.subagent_cost_usd,
            "subagent_sessions": self.subagent_sessions,
            "test_count": self.test_count,
            "test_lines": self.test_lines,
            "code_lines": self.code_lines,
            "confidence": self.confidence,
            "answer_tokens": self.answer_tokens,
            "explanation_tokens": self.explanation_tokens,
        }
        if self.tokens is not None:
            d["tokens"] = self.tokens
        if self.agentic:
            d["agentic"] = {
                "tests_passed": self.agentic.tests_passed,
                "tests_total": self.agentic.tests_total,
                "tool_calls": self.agentic.total_tool_calls,
                "retries": self.agentic.retry_loops,
                "depth": self.agentic.iteration_depth,
                "files_created": self.agentic.files_created,
                "prompt_tokens": self.agentic.prompt_tokens,
                "completion_tokens": self.agentic.completion_tokens,
                "reasoning_tokens": self.agentic.reasoning_tokens,
                "answer_tokens": self.agentic.answer_tokens,
                "explanation_tokens": self.agentic.explanation_tokens,
                "total_tokens": self.agentic.total_tokens,
                "estimated_cost_usd": self.agentic.estimated_cost_usd,
                "cache_read_tokens": self.agentic.cache_read_tokens,
                "cache_write_tokens": self.agentic.cache_write_tokens,
                "context_tokens": self.agentic.context_tokens,
                "cache_hit_rate": round(self.agentic.cache_hit_rate, 3),
                "confidence": self.agentic.confidence,
            }
        return d


def session_token_split(agentic: AgenticResult | None) -> dict[str, int] | None:
    """The backend-reported in/out token split for a session's agentic work.

    Returns ``None`` (coverage-not-available) when no backend reported usage — the flat
    ``total_tokens`` remains the valid fallback. Never fabricates a split: a backend that
    reported a measured zero is recorded as ``{"in": 0, "out": 0}``; a session that never
    reached a model call stays ``None``.
    """
    if agentic is None or not agentic.usage_reported:
        return None
    return {"in": agentic.prompt_tokens, "out": agentic.completion_tokens}


@dataclass
class StoryResult:
    """Aggregate results across all sessions in a story."""

    story_name: str
    story_id: str = ""
    codebase_path: str = ""
    language: str = ""
    model: str = ""
    mutation_id: str = ""
    perturbation_condition: str = ""
    started_at: str = ""
    completed_at: str = ""
    worktree: str = ""
    sessions: list[SessionResult] = field(default_factory=list)
    error: str = ""
    # Instrumented ledger fields (cell-level).
    perturbation_strength: float = 0.0  # the numeric strength axis (0.0 = CLEAN)
    test_executed_success: bool | None = None  # independently verified (test_runner), never self-report

    @property
    def total_cost(self) -> float:
        return sum(s.cost_usd for s in self.sessions)

    @property
    def total_continuation_cost(self) -> float:
        return sum(s.continuation_cost_usd for s in self.sessions)

    @property
    def total_subagent_cost(self) -> float:
        return sum(s.subagent_cost_usd for s in self.sessions)

    @property
    def total_subagent_sessions(self) -> int:
        return sum(s.subagent_sessions for s in self.sessions)

    @property
    def total_tokens(self) -> int:
        return sum(s.total_tokens for s in self.sessions)

    @property
    def total_cache_reads(self) -> int:
        return sum(s.agentic.cache_read_tokens for s in self.sessions if s.agentic)

    @property
    def total_cache_writes(self) -> int:
        return sum(s.agentic.cache_write_tokens for s in self.sessions if s.agentic)

    @property
    def total_context_tokens(self) -> int:
        return self.total_tokens + self.total_cache_reads

    @property
    def cache_hit_rate(self) -> float:
        total_context = self.total_context_tokens
        if total_context == 0:
            return 0.0
        return self.total_cache_reads / total_context

    @property
    def total_duration(self) -> float:
        return sum(s.duration_s for s in self.sessions)

    @property
    def session_count(self) -> int:
        return len(self.sessions)

    @property
    def all_successful(self) -> bool:
        return all(s.exit_code == 0 for s in self.sessions)

    @property
    def cascade_recovery(self) -> bool | None:
        """If session 1 had low correctness, did later sessions recover?

        Returns True if correctness improved from session 1 to last session.
        Returns False if it degraded or stayed the same.
        Returns None if no cascade data available.
        """
        if len(self.sessions) < 2:
            return None
        first = self.sessions[0]
        last = self.sessions[-1]
        if first.agentic is None or last.agentic is None:
            return None
        first_correctness = first.agentic.correctness
        last_correctness = last.agentic.correctness
        if first_correctness >= last_correctness:
            return False
        # Find the session where correctness stabilized
        for _i, s in enumerate(self.sessions):
            if s.agentic and s.agentic.correctness > first_correctness:
                return True
        return None

    @property
    def total_test_count(self) -> int:
        return sum(s.test_count for s in self.sessions)

    @property
    def total_test_lines(self) -> int:
        return sum(s.test_lines for s in self.sessions)

    @property
    def total_code_lines(self) -> int:
        return sum(s.code_lines for s in self.sessions)

    @property
    def test_code_ratio(self) -> float:
        if self.total_code_lines == 0:
            return 0.0
        return self.total_test_lines / self.total_code_lines

    def to_dict(self) -> dict[str, Any]:
        return {
            "story_name": self.story_name,
            "story_id": self.story_id,
            "codebase_path": self.codebase_path,
            "language": self.language,
            "model": self.model,
            "mutation_id": self.mutation_id,
            "perturbation_condition": self.perturbation_condition,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "worktree": self.worktree,
            "error": self.error,
            "perturbation_strength": self.perturbation_strength,
            "test_executed_success": self.test_executed_success,
            "summary": {
                "total_cost": self.total_cost,
                "total_continuation_cost": self.total_continuation_cost,
                "total_subagent_cost": self.total_subagent_cost,
                "total_subagent_sessions": self.total_subagent_sessions,
                "total_tokens": self.total_tokens,
                "total_cache_reads": self.total_cache_reads,
                "total_cache_writes": self.total_cache_writes,
                "total_context_tokens": self.total_context_tokens,
                "cache_hit_rate": round(self.cache_hit_rate, 3),
                "test_count": self.total_test_count,
                "test_lines": self.total_test_lines,
                "code_lines": self.total_code_lines,
                "test_code_ratio": round(self.test_code_ratio, 3),
                "total_duration": self.total_duration,
                "session_count": self.session_count,
                "all_successful": self.all_successful,
                "cascade_recovery": self.cascade_recovery,
            },
            "sessions": [s.to_dict() for s in self.sessions],
        }

