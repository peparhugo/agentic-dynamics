"""Opencode agentic invoke — spawn automode sessions and capture full traces.

Replaces raw API calls with real agentic execution: opencode thinks,
writes files, runs tests, iterates on failures. Captures the complete
tool-call trace, token usage, and test results.

This is the measurement layer the instrument was designed for.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Resolve opencode binary: env override or default ~/.opencode/bin/opencode
_OPENSCODE_BIN = os.environ.get("OPENSCODE_BIN", "")
if _OPENSCODE_BIN:
    OPENSCODE_BIN = _OPENSCODE_BIN
elif Path.home().exists():
    OPENSCODE_BIN = str(Path.home() / ".opencode/bin/opencode")
else:
    OPENSCODE_BIN = "opencode"  # fall back to $PATH



@dataclass
class AgenticResult:
    """Complete result of an agentic opencode session."""

    # Session
    run_id: str = ""
    task: str = ""
    model: str = ""
    workdir: str = ""
    exit_code: int = 0
    duration_s: float = 0.0
    error: str = ""

    # Output
    final_response: str = ""
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)

    # Tool call trace
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    total_tool_calls: int = 0
    thinking_steps: int = 0

    # Compounding effects
    retry_loops: int = 0           # how many times did it retry?
    iteration_depth: int = 0       # max depth of tool call chains
    error_count: int = 0           # tool call errors encountered

    # Test results
    tests_passed: int = 0
    tests_total: int = 0
    test_output: str = ""

    # Token usage
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0

    # Cost
    estimated_cost_usd: float = 0.0

    # Raw session transcript (JSONL from opencode stdout)
    raw_transcript: str = ""

    @property
    def correctness(self) -> float:
        if self.tests_total == 0:
            return 0.0
        return self.tests_passed / self.tests_total

    @property
    def text(self) -> str:
        return self.final_response

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and len(self.error) == 0

    # Experiment metadata
    thinking_effort: str = ""
    thinking_budget_tokens: int = 0


def _build_standardized_prompt(
    prompt: str,
    thinking_budget_tokens: int = 0,
    output_token_limit: int = 0,
    enforce_pytest: bool = True,
    silent_mode: bool | None = None,
) -> str:
    """Inject standardized constraints into the prompt for apples-to-apples comparison.

    This ensures every model gets the same formatting constraints regardless of
    training regime. The model can still choose how to allocate tokens — but the
    output format and reporting requirements are standardized.

    Args:
        prompt: Original task prompt.
        thinking_budget_tokens: Maximum thinking/reasoning tokens. 0 = no limit.
        output_token_limit: Maximum output tokens. 0 = no limit.
        enforce_pytest: Require pytest execution and pass/fail report.
        silent_mode: If True, suppress docstrings/comments/explanation.
                     If False, explicitly allow verbosity.
                     If None (default), model uses natural style — we measure the gap.
    """
    header = "[STANDARDIZED CONSTRAINTS — APPLY TO ALL MODELS]\n"
    if thinking_budget_tokens > 0:
        header += f"- Reasoning budget: {thinking_budget_tokens} tokens maximum for thinking/planning\n"
    if output_token_limit > 0:
        header += f"- Output limit: {output_token_limit} tokens maximum total output\n"
    if silent_mode is not None:
        if silent_mode:
            header += (
                "- IMPLEMENTATION-ONLY MODE: do NOT generate docstrings, comments, or "
                "explanatory prose. Output ONLY the working code. Optimize for token efficiency.\n"
            )
        else:
            header += (
                "- VERBOSE MODE: include docstrings, inline comments, and brief reasoning "
                "for every design decision. Optimize for readability and maintainability.\n"
            )
    if enforce_pytest:
        header += (
            "- Write ALL code files. Run pytest. Fix failures until all tests pass.\n"
            "- At the END of your response, state EXACTLY on one line: "
            '"TESTS: N passed, M failed"\n'
        )
    return header + "\n" + prompt


# Thinking effort → opencode --variant mapping
THINKING_VARIANTS = {
    "minimal": "minimal",
    "low": "low",
    "medium": "medium",
    "high": "high",
    "max": "max",
    "default": "default",
}


def run_opencode_agentic(
    prompt: str,
    *,
    model: str = "deepseek/deepseek-v4-pro",
    thinking_effort: str | None = None,
    thinking_budget_tokens: int = 0,
    output_token_limit: int = 0,
    silent_mode: bool | None = None,
    standardize: bool = True,
    enforce_pytest: bool = True,
    workdir: str | None = None,
    timeout: int = 300,
    session_name: str = "",
    init_git: bool = True,
) -> AgenticResult:
    """Spawn an opencode agentic session in an isolated worktree.

    Each run gets its own temp directory with git initialized so the
    model can use version control, branches, and commits. This
    provides full isolation between experiment runs and enables
    measurement of file changes, commits, and branching behavior.

    Args:
        prompt: The task prompt (with or without perturbation).
        model: Model identifier (opencode format: provider/model).
        thinking_effort: Override reasoning effort via --variant (minimal/low/medium/high/max).
        thinking_budget_tokens: Max thinking tokens injected into prompt. 0 = no limit.
        output_token_limit: Max output tokens injected into prompt. 0 = no limit.
        silent_mode: If True, suppress docstrings/comments. If False, require verbosity.
                     If None (default), model uses natural style — we measure the gap.
        standardize: Inject STANDARDIZED CONSTRAINTS header into prompt.
        enforce_pytest: Require pytest execution in standardized header.
        workdir: Working directory. Created if None.
        timeout: Maximum session duration in seconds.
        session_name: Name for the session (logging).
        init_git: Whether to initialize a git repo in the workdir.

    Returns:
        AgenticResult with complete execution trace.
    """
    import tempfile

    t0 = time.monotonic()
    result = AgenticResult(run_id=session_name or f"opencode_{int(t0)}",
                            task=prompt, model=model, workdir=workdir)
    result.thinking_effort = thinking_effort or "default"
    result.thinking_budget_tokens = thinking_budget_tokens

    # Inject standardized constraints for apples-to-apples comparison
    if standardize and not prompt.startswith("[STANDARDIZED CONSTRAINTS"):
        prompt = _build_standardized_prompt(
            prompt,
            thinking_budget_tokens=thinking_budget_tokens,
            output_token_limit=output_token_limit,
            enforce_pytest=enforce_pytest,
            silent_mode=silent_mode,
        )

    # Create an isolated worktree per run
    if workdir is None:
        workdir = tempfile.mkdtemp(prefix="exp_")
        result.workdir = workdir

    # Initialize git for version control tracking
    if init_git:
        subprocess.run(["git", "init"], cwd=workdir, capture_output=True)
        subprocess.run(["git", "config", "user.email", "experiment@instrument.local"], cwd=workdir, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Experiment Runner"], cwd=workdir, capture_output=True)
        subprocess.run(["git", "add", "-A"], cwd=workdir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial"], cwd=workdir, capture_output=True)

    # Store files before for change detection
    files_before = _list_files(workdir)

    cmd = [
        OPENSCODE_BIN, "run",
        "--model", model,
        "--format", "json",
        "--auto",
        "--dir", workdir,
    ]
    if thinking_effort and thinking_effort in THINKING_VARIANTS:
        cmd.extend(["--variant", THINKING_VARIANTS[thinking_effort]])
    if session_name:
        cmd.extend(["--title", session_name])
    if prompt:
        cmd.append(prompt)

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=workdir,
            stdin=subprocess.DEVNULL,
        )
        result.exit_code = proc.returncode
        result.error = proc.stderr.strip() if proc.returncode != 0 else ""

        # Store raw transcript for artifact bundling
        result.raw_transcript = proc.stdout

        # Parse JSONL output even on non-zero exit (partial output)
        if proc.stdout:
            _parse_session_output(proc.stdout, result)

    except subprocess.TimeoutExpired as e:
        result.error = f"Timeout after {timeout}s"
        result.exit_code = -1
        # Try to parse any partial output
        if e.stdout:
            _parse_session_output(e.stdout.decode() if isinstance(e.stdout, bytes) else str(e.stdout), result)
    except Exception as e:
        result.error = str(e)
        result.exit_code = -2

    result.duration_s = time.monotonic() - t0

    # Detect file changes (filter out venv, pip, pytest cache)
    files_after = _list_files(workdir)
    def _is_artifact(p):
        parts = p.split('/')
        for skip in ['.venv', 'venv', '__pycache__', '.pytest_cache', 'node_modules', '.git']:
            if skip in parts: return True
        return False
    result.files_created = sorted(f for f in (files_after - files_before) if not _is_artifact(f))
    result.files_modified = sorted(f for f in (files_after & files_before) if not _is_artifact(f))

    # Persist session transcript for post-hoc artifact bundling
    if result.raw_transcript:
        inst_dir = Path(workdir) / ".instrument"
        inst_dir.mkdir(parents=True, exist_ok=True)
        (inst_dir / "session.jsonl").write_text(result.raw_transcript)

    # Extract final response from the last assistant message
    # (already set during parsing)

    return result


def _list_files(dirpath: str) -> set[str]:
    """List files in a directory, relative to dirpath."""
    try:
        root = Path(dirpath)
        return {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}
    except Exception:
        return set()


def _parse_session_output(stdout: str, result: AgenticResult) -> None:
    """Parse opencode JSONL output to extract structured trace data.

    Opencode output format (v2):
    - {"type":"step_start", "sessionID":..., "part":{"type":"step-start"}}
    - {"type":"tool_use", "part":{"type":"tool","tool":"write|bash|read|edit|grep...",
        "state":{"status":"completed","input":{...},"output":"..."}}}
    - {"type":"text", "part":{"type":"text","text":"..."}}
    - {"type":"step_finish", "part":{"tokens":{"total":...,"input":...,"output":...,"reasoning":...}}}
    """
    tool_calls = []
    final_texts = []
    iteration_depth = 0
    current_depth = 0
    retry_count = 0
    last_was_error = False

    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue

        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        if not isinstance(obj, dict):
            continue

        etype = obj.get("type", "")
        part = obj.get("part", {})
        if not isinstance(part, dict):
            part = {}

        # Tool calls
        if etype == "tool_use":
            tool_name = part.get("tool", "")
            state = part.get("state", {})
            if not isinstance(state, dict):
                state = {}
            status = state.get("status", "?")
            tool_input = state.get("input", "")
            tool_output = state.get("output", "")
            is_error = status not in ("completed", "success") or ("error" in str(tool_output).lower() if tool_output else False)

            tool_calls.append({
                "type": "tool_use",
                "tool": tool_name,
                "input": str(tool_input)[:300],
                "output": str(tool_output)[:300],
                "status": status,
                "is_error": is_error,
            })
            current_depth += 1
            iteration_depth = max(iteration_depth, current_depth)
            result.total_tool_calls += 1

            if is_error:
                result.error_count += 1
                if last_was_error:
                    retry_count += 1
                last_was_error = True
            else:
                last_was_error = False

        # Tool result (step_follow variant)
        elif etype in ("tool_result", "step_follow"):
            current_depth = max(0, current_depth - 1)

        # Model text response
        elif etype == "text":
            text_content = part.get("text", "")
            if text_content:
                final_texts.append(str(text_content))

        # Step finish — extract cumulative token usage and cost
        elif etype == "step_finish":
            current_depth = max(0, current_depth - 1)
            tokens = part.get("tokens", {})
            if isinstance(tokens, dict):
                # Use cumulative session totals (each step_finish is cumulative, not incremental)
                result.prompt_tokens = tokens.get("input", 0) or 0
                result.completion_tokens = tokens.get("output", 0) or 0
                result.reasoning_tokens = tokens.get("reasoning", 0) or 0
                result.total_tokens = tokens.get("total", 0) or 0
            # Cost is the cumulative session cost from opencode's own accounting
            cost_val = part.get("cost", 0)
            if isinstance(cost_val, (int, float)):
                result.estimated_cost_usd = float(cost_val)

        # Parse test output from bash tool results
        if etype == "tool_use" and part.get("tool") == "bash":
            state = part.get("state", {})
            output = state.get("output", "") if isinstance(state, dict) else ""
            if output and ("test" in str(output).lower() or "pass" in str(output).lower() or "fail" in str(output).lower()):
                import re
                if "passed" in str(output).lower():
                    # pytest output: X passed, Y failed
                    m = re.search(r'(\d+)\s+passed', str(output))
                    if m:
                        result.tests_passed = int(m.group(1))
                    mf = re.search(r'(\d+)\s+failed', str(output))
                    if mf:
                        result.tests_total += int(mf.group(1))
                    result.tests_total += result.tests_passed
                result.test_output = str(output)[-500:]

    result.tool_calls = tool_calls
    result.retry_loops = retry_count
    result.iteration_depth = iteration_depth
    result.final_response = "\n".join(final_texts[-3:]) if final_texts else ""

    # Estimate correctness from test results if not directly parsed
    if result.tests_total == 0:
        if "passed" in str(result.test_output).lower():
            result.tests_total = max(result.tests_total, 1)
            result.tests_passed = max(result.tests_passed, 1)
