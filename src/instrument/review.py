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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ── Data Structures ────────────────────────────────────────────

@dataclass
class ReviewProblem:
    """A single code quality issue with category and severity."""

    category: str  # architecture, convention, testing, security, performance, etc.
    severity: str  # critical, major, minor, info
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category, "severity": self.severity,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ReviewProblem:
        return cls(
            category=d.get("category", "other"),
            severity=d.get("severity", "info"),
            description=d.get("description", ""),
        )


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
    problems: list[ReviewProblem] = field(default_factory=list)
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
            "problems": [p.to_dict() for p in self.problems],
            "strengths": self.strengths,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CommitReview:
        return cls(
            commit_hash=d.get("commit_hash", ""),
            reviewer_model=d.get("reviewer_model", ""),
            architectural_fit=d.get("architectural_fit", 0.0),
            convention_adherence=d.get("convention_adherence", 0.0),
            introduces_technical_debt=d.get("introduces_technical_debt", False),
            respects_existing_patterns=d.get("respects_existing_patterns", True),
            better_or_worse=d.get("better_or_worse", "unclear"),
            problems=_parse_problems(d.get("problems", [])),
            strengths=d.get("strengths", []),
            summary=d.get("summary", ""),
        )


def _parse_problems(raw: list) -> list[ReviewProblem]:
    """Parse problems list, handling both old (strings) and new (dict) formats."""
    problems = []
    for p in raw:
        if isinstance(p, dict):
            problems.append(ReviewProblem.from_dict(p))
        elif isinstance(p, str):
            problems.append(ReviewProblem(category="other", severity="info", description=p))
    return problems


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

MECHANICAL MEASUREMENTS (computed by static analysis — use these as ground truth):
{mechanics}

Ground your scores in the mechanical measurements above. If your qualitative judgment
disagrees with a measurement, flag the discrepancy in the summary. Do NOT invent issues
that contradict the measurements.

Output ONLY valid JSON, no other text:
{{
  "architectural_fit": <0.0-1.0>,
  "convention_adherence": <0.0-1.0>,
  "introduces_technical_debt": <true/false>,
  "respects_existing_patterns": <true/false>,
  "better_or_worse": "<better|worse|neutral>",
  "problems": [
    {{"category": "<architecture|convention|testing|security|performance|maintainability|dependency|other>",
      "severity": "<critical|major|minor|info>",
      "description": "<specific issue>"}},
    ...
  ],
  "strengths": ["<strength>", ...],
  "summary": "<one sentence>"
}}"""

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


# ── Review Schemas (for SDK structured output) ──────────────────

COMMIT_SCHEMA = {
    "type": "object",
    "properties": {
        "architectural_fit": {"type": "number", "minimum": 0, "maximum": 1},
        "convention_adherence": {"type": "number", "minimum": 0, "maximum": 1},
        "introduces_technical_debt": {"type": "boolean"},
        "respects_existing_patterns": {"type": "boolean"},
        "better_or_worse": {"type": "string", "enum": ["better", "worse", "neutral"]},
        "problems": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": [
                        "architecture", "convention", "testing", "security",
                        "performance", "maintainability", "dependency", "other"
                    ]},
                    "severity": {"type": "string", "enum": [
                        "critical", "major", "minor", "info"
                    ]},
                    "description": {"type": "string"},
                },
                "required": ["category", "severity", "description"],
            },
        },
        "strengths": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
    },
    "required": ["architectural_fit", "convention_adherence", "better_or_worse"],
}

STORY_SCHEMA = {
    "type": "object",
    "properties": {
        "overall_coherence": {"type": "number", "minimum": 0, "maximum": 1},
        "overall_quality": {"type": "number", "minimum": 0, "maximum": 1},
        "compounding_issues": {"type": "array", "items": {"type": "string"}},
        "key_decisions": {"type": "array", "items": {"type": "string"}},
        "trajectory_description": {"type": "string"},
        "summary": {"type": "string"},
    },
    "required": ["overall_coherence"],
}

# ── Review Functions ───────────────────────────────────────────

def _load_commit_mechanics(story_id: str, commit_hash: str) -> dict:
    """Load pre-computed AST + Sonar + convention metrics for a commit.

    Reads experiments/results/analysis/analysis_{story_id}.json and finds
    the matching commit entry. Returns a dict of mechanical measurements,
    or empty strings if the analysis file is missing.
    """
    from pathlib import Path as _Path
    analysis_dir = _Path(__file__).resolve().parent.parent.parent / "experiments" / "results" / "analysis"
    if not story_id:
        return {}
    path = analysis_dir / f"analysis_{story_id}.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}

    for c in data.get("commits", []):
        if c.get("commit_hash") == commit_hash or c.get("commit_hash", "").startswith(commit_hash[:12]):
            ast = c.get("ast", {})
            sonar = c.get("sonar", {})
            convention = c.get("convention", {})
            return {
                "ast": ast,
                "sonar": sonar,
                "convention": convention,
            }
    return {}


def _format_mechanics(mechanics: dict) -> str:
    """Format mechanical measurements for the review prompt."""
    if not mechanics:
        return "(none available)"
    lines = []
    ast = mechanics.get("ast", {})
    if ast:
        lines.append(
            f"  AST diff: +{ast.get('files_added', 0)} files, "
            f"+{ast.get('lines_added', 0)}/-{ast.get('lines_removed', 0)} lines, "
            f"+{ast.get('functions_added', 0)} functions, "
            f"+{ast.get('classes_added', 0)} classes, "
            f"+{ast.get('imports_added', 0)} imports"
        )
    sonar = mechanics.get("sonar", {})
    if sonar.get("available"):
        lines.append(
            f"  SonarQube delta: bugs {sonar.get('bugs_delta', 0):+d}, "
            f"smells {sonar.get('smells_delta', 0):+d}, "
            f"cognitive complexity {sonar.get('complexity_delta', 0):+d}, "
            f"duplications {sonar.get('duplications_delta', 0):+.1f}%"
        )
    else:
        lines.append("  SonarQube delta: (unavailable)")
    convention = mechanics.get("convention", {})
    if convention:
        score = convention.get("score")
        viols = convention.get("violations", [])
        if score is not None:
            lines.append(f"  Convention score: {score:.2f}")
        if viols:
            lines.append(f"  Convention violations ({len(viols)}): " + "; ".join(viols[:8]))
    return "\n".join(lines) if lines else "(none available)"


def review_commit(
    worktree: Path,
    commit_hash: str,
    *,
    story_name: str = "",
    session_number: int = 0,
    model: str = "deepseek/deepseek-v4-flash",
    timeout: int = 300,
    story_id: str = "",
) -> CommitReview:
    """Review a single commit using an LLM agent.

    Args:
        worktree: Path to the git worktree.
        commit_hash: Commit to review.
        story_name: Name of the story for context.
        session_number: Session number for context.
        model: Model to use for review.
        timeout: Timeout in seconds.
        story_id: Story id used to load pre-computed AST + Sonar metrics.

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
        mechanics=_format_mechanics(_load_commit_mechanics(story_id, commit_hash)),
    )

    # Try SDK bridge for guaranteed structured output
    data = _call_agent_structured(prompt, model, COMMIT_SCHEMA, timeout)
    if data:
        return CommitReview(
            commit_hash=commit_hash, reviewer_model=model,
            architectural_fit=float(data.get("architectural_fit", 0.5)),
            convention_adherence=float(data.get("convention_adherence", 0.5)),
            introduces_technical_debt=bool(data.get("introduces_technical_debt", False)),
            respects_existing_patterns=bool(data.get("respects_existing_patterns", True)),
            better_or_worse=str(data.get("better_or_worse", "unclear")),
            problems=_parse_problems(data.get("problems", [])),
            strengths=list(data.get("strengths", [])),
            summary=str(data.get("summary", "")),
        )

    # Fall back to CLI subprocess
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

    # Try SDK bridge for guaranteed structured output
    data = _call_agent_structured(prompt, model, STORY_SCHEMA, timeout)
    if data:
        return StoryReview(
            story_name=story_name, reviewer_model=model,
            overall_coherence=float(data.get("overall_coherence", 0.5)),
            compounding_issues=list(data.get("compounding_issues", [])),
            key_decisions=list(data.get("key_decisions", [])),
            trajectory_description=str(data.get("trajectory_description", "")),
            summary=str(data.get("summary", "")),
        )

    # Fall back to CLI subprocess
    response = _call_agent(prompt, model=model, timeout=timeout)
    return _parse_story_review(response, story_name, model)


def _call_agent_structured(
    prompt: str, model: str, schema: dict, timeout: int = 300
) -> dict | None:
    """Call an LLM agent via opencode SDK bridge with guaranteed structured output.

    Uses the SDK's json_schema format to enforce valid JSON matching the schema.
    Falls back to None if the bridge is unavailable or times out.
    """
    import os
    import shutil

    node_bin = shutil.which("node") or os.environ.get("NODE_BIN", "node")
    bridge_path = Path(__file__).resolve().parent.parent.parent / "scripts" / "sdk_bridge.mjs"

    if not bridge_path.exists():
        return None

    try:
        result = subprocess.run(
            [node_bin, str(bridge_path)],
            input=json.dumps({"prompt": prompt, "model": model, "schema": schema, "timeout": timeout}),
            capture_output=True,
            text=True,
            timeout=timeout + 60,
        )
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout)
        if data.get("ok") and data.get("structured"):
            return data["structured"]
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _call_agent(prompt: str, model: str, timeout: int) -> str | None:
    """Call an LLM agent via opencode CLI with structured JSONL output."""
    import os

    opencode_bin = os.environ.get(
        "OPENCODE_BIN",
        str(Path.home() / ".opencode/bin/opencode"),
    )

    try:
        result = subprocess.run(
            [opencode_bin, "run", prompt, "--model", model, "--format", "json", "--auto"],
            capture_output=True,
            text=True,
            timeout=timeout + 30,
        )

        # Parse JSONL output to extract text responses from the model
        text_parts = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            if obj.get("type") == "text":
                part = obj.get("part", {})
                if isinstance(part, dict) and part.get("text"):
                    text_parts.append(part["text"])

        if text_parts:
            return "\n".join(text_parts).strip() or None

        # Fallback: try raw stdout if JSONL parsing produced nothing
        output = result.stdout
        if output:
            return output.strip() or None
        return None

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
                problems=_parse_problems(data.get("problems", [])),
                strengths=list(data.get("strengths", [])),
                summary=str(data.get("summary", "")),
            )
    except (json.JSONDecodeError, KeyError, ValueError):
        pass

    # Try key:value format or JSON embedded in text
    try:
        # First try to extract JSON from the response
        import re as _re
        json_match = _re.search(r'\{[\s\S]*\}', response)
        if json_match:
            data = json.loads(json_match.group())
            return CommitReview.from_dict({**data, "commit_hash": commit_hash, "reviewer_model": model})
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

    # Try SDK bridge for guaranteed structured output
    data = _call_agent_structured(prompt, model, None, timeout)
    if data:
        return data

    # Fall back to CLI subprocess
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
