"""Agent review system — use LLMs to evaluate AI-generated commits.

Review agents run post-hoc and are deterministic for a given artifact.
They produce durable JSON output committed as experimental evidence.

Pool:
  - Commit Reviewer (GPT-5.6): Reviews individual commits
  - Story Reviewer (Claude): Reviews full story coherence
  - Cross-Model Comparator (Claude): Compares architectural choices across models
  - Test Generator (Flash V4): Creates held-out tests before experiment runs
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ── Data Structures ────────────────────────────────────────────

@dataclass
class CommitReview:
    """Structured review of a single commit."""

    commit_hash: str
    reviewer_model: str
    architectural_fit: float  # 0.0-1.0
    convention_adherence: float  # 0.0-1.0
    introduces_technical_debt: bool
    respects_existing_patterns: bool
    better_or_worse: str  # "better", "worse", "neutral", "unclear"
    problems: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "commit_hash": self.commit_hash,
            "reviewer_model": self.reviewer_model,
            "architectural_fit": self.architectural_fit,
            "convention_adherence": self.convention_adherence,
            "introduces_technical_debt": self.introduces_technical_debt,
            "respects_existing_patterns": self.respects_existing_patterns,
            "better_or_worse": self.better_or_worse,
            "problems": self.problems,
            "strengths": self.strengths,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CommitReview":
        return cls(
            commit_hash=d.get("commit_hash", ""),
            reviewer_model=d.get("reviewer_model", ""),
            architectural_fit=d.get("architectural_fit", 0.0),
            convention_adherence=d.get("convention_adherence", 0.0),
            introduces_technical_debt=d.get("introduces_technical_debt", False),
            respects_existing_patterns=d.get("respects_existing_patterns", True),
            better_or_worse=d.get("better_or_worse", "unclear"),
            problems=d.get("problems", []),
            strengths=d.get("strengths", []),
            summary=d.get("summary", ""),
        )


@dataclass
class StoryReview:
    """Structured review of an entire multi-session story."""

    story_name: str
    reviewer_model: str
    overall_coherence: float  # 0.0-1.0
    compounding_issues: list[str] = field(default_factory=list)
    key_decisions: list[str] = field(default_factory=list)
    trajectory_description: str = ""
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "story_name": self.story_name,
            "reviewer_model": self.reviewer_model,
            "overall_coherence": self.overall_coherence,
            "compounding_issues": self.compounding_issues,
            "key_decisions": self.key_decisions,
            "trajectory_description": self.trajectory_description,
            "summary": self.summary,
        }


# ── Review Prompts ─────────────────────────────────────────────

_COMMIT_REVIEW_PROMPT = """Rate this git commit made by an AI coding agent on architectural fit and convention adherence.

COMMIT: {commit_message}

DIFF:
{diff}

Output EXACTLY this format with no other text:
arch_fit: <0.0-1.0>
convention: <0.0-1.0>
debt: <true/false>
respects_patterns: <true/false>
better_or_worse: <better|worse|neutral>
summary: <one sentence>
problems: <comma-separated list or none>"""

_STORY_REVIEW_PROMPT = """You are reviewing a complete multi-session AI coding story.
Across {session_count} sessions, an AI agent built a software project incrementally.
Each session produced one git commit building on the prior commit.

REVIEW THE FOLLOWING COMMIT SEQUENCE FOR THE STORY: {story_name}

COMMIT LOG:
{commit_log}

Evaluate:
1. COHERENCE (0.0-1.0): Do the 5 sessions form a logical progression?
   Does session 5 build naturally on sessions 1-4?
2. COMPOUNDING ISSUES: Did any early decisions constrain or harm later sessions?
3. KEY DECISIONS: What were the most consequential architectural choices?
4. TRAJECTORY: Did the quality improve, degrade, or stay flat across sessions?

Output ONLY valid JSON, no other text:
{{
  "overall_coherence": <0.0-1.0>,
  "compounding_issues": ["<issue>", ...],
  "key_decisions": ["<decision>", ...],
  "trajectory_description": "<one paragraph describing the quality arc>",
  "summary": "<one-sentence overall evaluation>"
}}"""


# ── Review Functions ───────────────────────────────────────────

def review_commit(
    worktree: Path,
    commit_hash: str,
    *,
    story_name: str = "",
    session_number: int = 0,
    model: str = "deepseek/deepseek-v4-flash",
    timeout: int = 300,
) -> CommitReview:
    """Review a single commit using an LLM agent.

    Args:
        worktree: Path to the git worktree.
        commit_hash: Commit to review.
        story_name: Name of the story for context.
        session_number: Session number for context.
        model: Model to use for review.
        timeout: Timeout in seconds.

    Returns:
        CommitReview with scores and findings.
    """
    # Get commit metadata and diff (source files only)
    commit_msg = _run_git(worktree, "log", "-1", "--format=%s", commit_hash).strip()
    raw_diff = _run_git(worktree, "diff", f"{commit_hash}~1..{commit_hash}")

    # Filter diff to source files only (skip pycache, .instrument, node_modules)
    lines = []
    keep = False
    for line in raw_diff.splitlines():
        if line.startswith("diff --git"):
            keep = (
                any(ext in line for ext in (".py", ".ts", ".tsx", ".js", ".json", ".yaml", ".yml", ".go", ".rs"))
                and "__pycache__" not in line
                and ".instrument" not in line
                and "node_modules" not in line
                and "dist/" not in line
            )
        if keep:
            lines.append(line)
    diff = "\n".join(lines)

    if not diff.strip():
        return CommitReview(
            commit_hash=commit_hash,
            reviewer_model=model,
            architectural_fit=1.0,
            convention_adherence=1.0,
            introduces_technical_debt=False,
            respects_existing_patterns=True,
            better_or_worse="neutral",
            summary="No changes in this commit.",
        )

    # Truncate diff if too large
    if len(diff) > 8000:
        diff = diff[:8000] + "\n... (diff truncated)"

    prompt = _COMMIT_REVIEW_PROMPT.format(
        session_number=session_number,
        story_name=story_name,
        commit_message=commit_msg,
        diff=diff,
    )

    response = _call_agent(prompt, model=model, timeout=timeout)
    return _parse_commit_review(response, commit_hash, model)


def review_story(
    worktree: Path,
    story_name: str,
    *,
    model: str = "deepseek/deepseek-v4-flash",
    timeout: int = 300,
) -> StoryReview:
    """Review a complete multi-session story.

    Args:
        worktree: Path to the git worktree with full history.
        story_name: Name of the story.
        model: Model to use for review.
        timeout: Timeout in seconds.

    Returns:
        StoryReview with coherence and trajectory analysis.
    """
    log = _run_git(worktree, "log", "--reverse", "--format=%h %s")
    session_count = log.count("[story]") if "[story]" in log else len(log.splitlines())

    prompt = _STORY_REVIEW_PROMPT.format(
        story_name=story_name,
        session_count=session_count,
        commit_log=log,
    )

    response = _call_agent(prompt, model=model, timeout=timeout)
    return _parse_story_review(response, story_name, model)


def _call_agent(prompt: str, model: str, timeout: int) -> str | None:
    """Call an LLM agent via opencode CLI."""
    import os
    import re

    opencode_bin = os.environ.get(
        "OPENCODE_BIN",
        str(Path.home() / ".opencode/bin/opencode"),
    )

    try:
        result = subprocess.run(
            [opencode_bin, "run", prompt, "--model", model, "--auto"],
            capture_output=True,
            text=True,
            timeout=timeout + 30,
        )
        output = result.stdout or ""
        output = re.sub(r'\x1b\[[0-9;]*m', '', output)
        lines = [l for l in output.splitlines()
                 if l.strip() and not l.strip().startswith(">")]
        return "\n".join(lines).strip() or None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def _parse_commit_review(response: str | None, commit_hash: str, model: str) -> CommitReview:
    """Parse LLM response into CommitReview. Handles both JSON and key:value formats."""
    defaults = CommitReview(
        commit_hash=commit_hash,
        reviewer_model=model,
        architectural_fit=0.5,
        convention_adherence=0.5,
        introduces_technical_debt=False,
        respects_existing_patterns=True,
        better_or_worse="unclear",
        summary="Review unavailable.",
    )

    if not response:
        return defaults

    # Try JSON first
    try:
        start = response.find("{")
        end = response.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(response[start:end])
            return CommitReview(
                commit_hash=commit_hash,
                reviewer_model=model,
                architectural_fit=float(data.get("architectural_fit", 0.5)),
                convention_adherence=float(data.get("convention_adherence", 0.5)),
                introduces_technical_debt=bool(data.get("introduces_technical_debt", False)),
                respects_existing_patterns=bool(data.get("respects_existing_patterns", True)),
                better_or_worse=str(data.get("better_or_worse", "unclear")),
                problems=list(data.get("problems", [])),
                strengths=list(data.get("strengths", [])),
                summary=str(data.get("summary", "")),
            )
    except (json.JSONDecodeError, KeyError, ValueError):
        pass

    # Try key:value format
    try:
        import re
        arch_fit = _extract_float(response, r"arch_fit:\s*([\d.]+)")
        convention = _extract_float(response, r"convention:\s*([\d.]+)")
        debt = _extract_bool(response, r"debt:\s*(true|false)")
        respects = _extract_bool(response, r"respects_patterns:\s*(true|false)")
        bow = _extract_str(response, r"better_or_worse:\s*(\w+)")
        summary = _extract_str(response, r"summary:\s*(.+?)(?:\n|$)")
        problems = _extract_list(response, r"problems:\s*(.+)")

        if arch_fit is not None:
            return CommitReview(
                commit_hash=commit_hash, reviewer_model=model,
                architectural_fit=max(0.0, min(1.0, arch_fit)),
                convention_adherence=max(0.0, min(1.0, convention or arch_fit or 0.5)),
                introduces_technical_debt=debt or False,
                respects_existing_patterns=respects or True,
                better_or_worse=bow or "unclear",
                problems=[p.strip() for p in (problems or "").split(",") if p.strip() and p.strip() != "none"],
                strengths=[],
                summary=summary or "Review parsed from text output.",
            )
    except Exception:
        pass

    # Try single-number response (model returned just a score)
    try:
        text = response.strip()
        if text.replace(".", "").replace("-", "").isdigit():
            score = float(text)
            return CommitReview(
                commit_hash=commit_hash, reviewer_model=model,
                architectural_fit=max(0.0, min(1.0, score)),
                convention_adherence=max(0.0, min(1.0, score)),
                better_or_worse="better" if score >= 0.5 else "worse",
                summary=f"Score: {score}",
            )
    except (ValueError, AttributeError):
        pass

    return defaults


def _extract_float(text: str, pattern: str) -> float | None:
    import re
    m = re.search(pattern, text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return None


def _extract_bool(text: str, pattern: str) -> bool | None:
    import re
    m = re.search(pattern, text)
    if m:
        return m.group(1).lower() == "true"
    return None


def _extract_str(text: str, pattern: str) -> str | None:
    import re
    m = re.search(pattern, text)
    if m:
        return m.group(1).strip()
    return None


def _extract_list(text: str, pattern: str) -> str | None:
    import re
    m = re.search(pattern, text)
    if m:
        val = m.group(1).strip()
        return val if val != "none" else ""
    return None


def _parse_story_review(response: str | None, story_name: str, model: str) -> StoryReview:
    """Parse LLM response into StoryReview."""
    defaults = StoryReview(
        story_name=story_name,
        reviewer_model=model,
        overall_coherence=0.5,
        summary="Review unavailable.",
    )

    if not response:
        return defaults

    try:
        start = response.find("{")
        end = response.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(response[start:end])
            return StoryReview(
                story_name=story_name,
                reviewer_model=model,
                overall_coherence=float(data.get("overall_coherence", 0.5)),
                compounding_issues=list(data.get("compounding_issues", [])),
                key_decisions=list(data.get("key_decisions", [])),
                trajectory_description=str(data.get("trajectory_description", "")),
                summary=str(data.get("summary", "")),
            )
    except (json.JSONDecodeError, KeyError, ValueError):
        pass

    return defaults


def _run_git(worktree: Path, *args: str) -> str:
    try:
        proc = subprocess.run(
            ["git"] + list(args),
            capture_output=True,
            text=True,
            cwd=str(worktree),
            timeout=30,
        )
        return proc.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


# ── Test Generator ─────────────────────────────────────────────

_TEST_GEN_PROMPT = """You are a test generator for an experimental measurement instrument.
Write a comprehensive test suite for the following specification.

SPECIFICATION:
{specification}

REQUIREMENTS:
1. Write tests that verify correct behavior, NOT that the code compiles.
2. Test edge cases: empty inputs, boundary values, error conditions.
3. Test integration: multiple endpoints/features working together.
4. Write {test_count} tests minimum.
5. Use the {test_framework} test framework for {language}.

Output ONLY valid {language} code for the test file. No explanations."""


def generate_tests(
    specification: str,
    language: str = "python",
    test_framework: str = "pytest",
    test_count: int = 20,
    *,
    model: str = "deepseek/deepseek-v4-flash",
    timeout: int = 300,
) -> str | None:
    """Generate held-out tests from a specification BEFORE the experiment runs.

    These tests are created without the agent ever seeing them. They serve
    as an independent correctness evaluator (evaluator_independent=True).

    Args:
        specification: The clean task specification to test.
        language: Target language (python, typescript).
        test_framework: Test framework to use (pytest, jest).
        test_count: Minimum number of tests to generate.
        model: Model for test generation (cheap model since tests are reviewed).
        timeout: Timeout in seconds.

    Returns:
        Test file content as string, or None if generation failed.
    """
    prompt = _TEST_GEN_PROMPT.format(
        specification=specification,
        test_count=test_count,
        test_framework=test_framework,
        language=language,
    )

    response = _call_agent(prompt, model=model, timeout=timeout)
    return response


# ── Cross-Model Comparator ─────────────────────────────────────

_COMPARISON_PROMPT = """You are comparing implementations of the same task produced by different AI coding agents.
Each implementation was built by an agent completing the same {session_count}-session story.

TASK: {task_description}

IMPLEMENTATIONS:
{implementations}

Compare the architectural decisions made by each model. For each key decision area
(authentication approach, data access pattern, error handling, testing strategy, etc.),
describe which model made the most durable choice and why.

Output ONLY valid JSON, no other text:
{{
  "decision_areas": [
    {{
      "area": "<decision area name>",
      "models": {{
        "<model_name>": "<what this model did>",
        ...
      }},
      "best_choice": "<model_name that made the most durable choice>",
      "rationale": "<why this choice is more maintainable, scalable, or less likely to create future cost>"
    }},
    ...
  ],
  "overall_assessment": {{
    "most_maintainable": "<model_name>",
    "most_innovative": "<model_name>",
    "most_cost_effective": "<model_name>",
    "most_architecturally_sound": "<model_name>",
    "summary": "<one paragraph comparing the models>"
  }}
}}"""


def compare_implementations(
    specifications: dict[str, str],  # model_name -> task spec
    code_bases: dict[str, str],      # model_name -> codebase path or summary
    task_description: str = "",
    session_count: int = 5,
    *,
    model: str = "anthropic/claude-fable-5",
    timeout: int = 600,
) -> dict[str, Any] | None:
    """Compare implementations of the same task across multiple models.

    Args:
        specifications: Map of model_name -> original task specification.
        code_bases: Map of model_name -> codebase summary or path.
        task_description: Human-readable task description.
        session_count: Number of sessions in the story.
        model: Model used for comparison (should be high-quality).
        timeout: Timeout in seconds.

    Returns:
        Parsed comparison JSON dict, or None if generation failed.
    """
    # Build implementation descriptions for the prompt
    impl_parts: list[str] = []
    for model_name, spec in specifications.items():
        code_summary = code_bases.get(model_name, "No code available")
        # Truncate code summaries
        if len(code_summary) > 2000:
            code_summary = code_summary[:2000] + "\n... (truncated)"
        impl_parts.append(f"--- MODEL: {model_name} ---\nTASK: {spec}\nCODE SUMMARY:\n{code_summary}\n")

    prompt = _COMPARISON_PROMPT.format(
        task_description=task_description or "Multi-session coding task",
        session_count=session_count,
        implementations="\n\n".join(impl_parts),
    )

    response = _call_agent(prompt, model=model, timeout=timeout)
    if not response:
        return None

    try:
        start = response.find("{")
        end = response.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(response[start:end])
    except (json.JSONDecodeError, KeyError, ValueError):
        pass

    return None
