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
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentic_dynamics.measurement.efficiency import compute_cost_estimate
from agentic_dynamics.control.live import make_publisher
from agentic_dynamics.core.streaming import stream_subprocess

# Resolve opencode binary: env override or default ~/.opencode/bin/opencode
_OPENCODE_BIN = os.environ.get("OPENCODE_BIN", "")
if _OPENCODE_BIN:
    OPENCODE_BIN = _OPENCODE_BIN
elif Path.home().exists():
    OPENCODE_BIN = str(Path.home() / ".opencode/bin/opencode")
else:
    OPENCODE_BIN = "opencode"  # fall back to $PATH


@dataclass
class AgenticResult:
    """Complete result of an agentic opencode session."""

    # Session
    run_id: str = ""
    task: str = ""
    model: str = ""
    workdir: str = ""
    session_id: str = ""
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
    retry_loops: int = 0  # how many times did it retry?
    iteration_depth: int = 0  # max depth of tool call chains
    error_count: int = 0  # tool call errors encountered

    # Test results
    tests_passed: int = 0
    tests_total: int = 0
    test_output: str = ""

    # Token usage
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0

    # Whether the backend reported per-step token usage in the transcript. Set by the JSONL
    # parser when it sees a step_finish/usage event carrying a tokens dict — the signal that
    # ``prompt_tokens``/``completion_tokens`` are measured (possibly 0) rather than absent.
    # ``False`` means the session never reached a model call (or the backend reported no
    # usage): the in/out split is coverage-not-available, distinct from a measured zero.
    usage_reported: bool = False

    # Token split — the completion/output stream is partitioned into the "answer"
    # (tokens spent writing the deliverable via tool calls) and "explanation"
    # (tokens spent on prose narration). This is the decomposition the
    # Explanation Tax (silent vs verbose mode) needs. Invariant:
    # answer_tokens + explanation_tokens == completion_tokens.
    answer_tokens: int = 0
    explanation_tokens: int = 0

    # Cache (context tokens not re-sent to provider — "free" reads)
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    # Effective context throughput (billable + cached = total context footprint)
    context_tokens: int = 0

    @property
    def cache_hit_rate(self) -> float:
        """Fraction of context served from cache (0.0–1.0)."""
        total_context = self.total_tokens + self.cache_read_tokens
        if total_context == 0:
            return 0.0
        return self.cache_read_tokens / total_context

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
    def confidence(self) -> float | None:
        """Per-attempt execution-confidence signal, tagged [H].

        Derivation (documented heuristic — NOT the model's self-reported pass/fail):
          1. If the session errored (non-empty ``error``), confidence is 0.0.
          2. Else if any tests ran, confidence is measured correctness
             (``tests_passed / tests_total``) — an outcome-grounded signal.
          3. Else confidence is the tool-call success fraction
             (``1 - error_count / total_tool_calls``) — did the agent's actions
             succeed without retry/error churn?
          4. With no signal at all (no error, no tests, no tool calls), ``None``.

        This is the ``confidence`` the ``model_cascade``/``dynamics`` control arms
        consume. It tracks *outcome* (correctness / action success), not narration:
        a model that narrates "I'm confident" while failing tests gets 0.0. A
        property (not a stored field) so it always reflects the final run state —
        ``error`` is assigned after the transcript is parsed.
        """
        if self.error:
            return 0.0
        if self.tests_total > 0:
            return round(self.tests_passed / self.tests_total, 4)
        if self.total_tool_calls > 0:
            ok_calls = max(self.total_tool_calls - self.error_count, 0)
            return round(ok_calls / self.total_tool_calls, 4)
        return None

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
        header += (
            f"- Reasoning budget: {thinking_budget_tokens} tokens maximum for thinking/planning\n"
        )
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
    on_event: Callable[[dict[str, Any]], None] | None = None,
    transcript_path: str | None = None,
    session_id: str | None = None,
    fork: bool = False,
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
        on_event: Optional callback invoked per parsed opencode event. Falls
            back to Redis live publishing (``FINOPS_CELL_ID``) when omitted.
        transcript_path: Optional path for the session JSONL transcript.
            Defaults to ``<workdir>/.instrument/session.jsonl``.
        session_id: When set together with ``fork=True``, resume the workflow by
            forking the given session (``--session <id> --fork``), so the shared
            context prefix is served as provider cache reads.
        fork: Fork from ``session_id`` to reuse its context prefix (cache reads).

    Returns:
        AgenticResult with complete execution trace.
    """

    t0 = time.monotonic()
    result = AgenticResult(
        run_id=session_name or f"opencode_{int(t0)}", task=prompt, model=model, workdir=workdir
    )
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
        _init_git_workdir(workdir)

    # Store files before for change detection
    files_before = _list_files(workdir)

    cmd = [
        OPENCODE_BIN,
        "run",
        "--model",
        model,
        "--format",
        "json",
        "--auto",
        "--dir",
        workdir,
    ]
    if thinking_effort and thinking_effort in THINKING_VARIANTS:
        cmd.extend(["--variant", THINKING_VARIANTS[thinking_effort]])
    if session_name:
        cmd.extend(["--title", session_name])
    if fork and session_id:
        cmd.extend(["--session", session_id, "--fork"])
    if prompt:
        cmd.append(prompt)

    publisher = make_publisher() if on_event is None else None

    def _on_line(line: str) -> None:
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            return
        if not isinstance(obj, dict):
            return
        if on_event is not None:
            on_event(obj)
        elif publisher is not None:
            publisher.publish_event(obj)

    on_line = _on_line if (on_event is not None or publisher is not None) else None
    stream = stream_subprocess(cmd, workdir=workdir, timeout=timeout, on_line=on_line)
    if stream.timed_out:
        result.error = f"Timeout after {timeout}s"
        result.exit_code = -1
    else:
        result.exit_code = stream.exit_code
        result.error = stream.stderr.strip() if stream.exit_code != 0 else ""

    # Store raw transcript for artifact bundling
    result.raw_transcript = stream.stdout

    # Parse JSONL output even on non-zero exit (partial output)
    if stream.stdout:
        _parse_session_output(stream.stdout, result)

    result.session_id = _extract_session_id(stream.stdout)

    # Fall back to token × provider pricing when the events report no per-step cost
    # (e.g. openai models, whose step_finish carries cost=0). Keeps live cost honest
    # instead of silently reading $0.00.
    if result.estimated_cost_usd == 0.0 and result.total_tokens > 0:
        provider, _, model_id = model.partition("/")
        try:
            est = compute_cost_estimate(
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                reasoning_tokens=result.reasoning_tokens,
                cache_read_tokens=result.cache_read_tokens,
                cache_write_tokens=result.cache_write_tokens,
                provider=provider,
                model=model_id,
            )
            result.estimated_cost_usd = est["total_cost_usd"]
        except (ValueError, KeyError):
            pass

    result.duration_s = time.monotonic() - t0

    # Detect file changes (filter out venv, pip, pytest cache)
    result.files_created, result.files_modified = _diff_workdir(workdir, files_before)

    # Persist session transcript for post-hoc artifact bundling
    if result.raw_transcript:
        out_path = (
            Path(transcript_path)
            if transcript_path
            else Path(workdir) / ".instrument" / "session.jsonl"
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(result.raw_transcript)

    # Extract final response from the last assistant message
    # (already set during parsing)

    return result


def _init_git_workdir(workdir: str) -> None:
    """Initialize a git repo in the workdir for version-control tracking.

    Idempotent (docs/routing_next_steps.md item 5.2): when the worktree already has history
    (``git rev-parse HEAD`` succeeds), this is a no-op — a killed run's leftover work must not
    be swept into a misnamed "Initial" commit, and resume's ``[workflow] <phase>`` commit
    detection must not be confused. The genuinely-new-repo path initializes, sets the runner
    identity, and only commits when something is actually staged (an empty "Initial" commit is
    skipped).
    """
    has_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=workdir, capture_output=True
    ).returncode == 0
    if has_head:
        return

    subprocess.run(["git", "init"], cwd=workdir, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "experiment@instrument.local"],
        cwd=workdir,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Experiment Runner"], cwd=workdir, capture_output=True
    )
    subprocess.run(["git", "add", "-A"], cwd=workdir, capture_output=True)
    staged = subprocess.run(
        ["git", "status", "--porcelain"], cwd=workdir, capture_output=True, text=True
    )
    if not staged.stdout.strip():
        return
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=workdir, capture_output=True)


def _diff_workdir(workdir: str, files_before: set[str]) -> tuple[list[str], list[str]]:
    """Compute files created/modified relative to a prior snapshot."""
    files_after = _list_files(workdir)

    def _is_artifact(p: str) -> bool:
        return any(
            skip in p.split("/")
            for skip in (".venv", "venv", "__pycache__", ".pytest_cache", "node_modules", ".git")
        )

    files_created = sorted(f for f in (files_after - files_before) if not _is_artifact(f))
    files_modified = sorted(f for f in (files_after & files_before) if not _is_artifact(f))
    return files_created, files_modified


def _list_files(dirpath: str) -> set[str]:
    """List files in a directory, relative to dirpath."""
    try:
        root = Path(dirpath)
        return {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}
    except Exception:
        return set()


def _extract_session_id(stdout: str) -> str:
    """Extract the sessionID from the first JSONL event that carries one."""
    if not stdout:
        return ""
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        sid = obj.get("sessionID", "")
        if sid:
            return sid
    return ""


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
    _step_costs: list[float] = []
    # Whether the current step produced tool calls (wrote/edited the deliverable)
    # vs was prose-only. Drives the answer/explanation token split at step_finish.
    step_has_tool = False

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
            step_has_tool = True
            tool_name = part.get("tool", "")
            state = part.get("state", {})
            if not isinstance(state, dict):
                state = {}
            status = state.get("status", "?")
            tool_input = state.get("input", "")
            tool_output = state.get("output", "")
            is_error = status not in ("completed", "success") or (
                "error" in str(tool_output).lower() if tool_output else False
            )

            tool_calls.append(
                {
                    "type": "tool_use",
                    "tool": tool_name,
                    "input": str(tool_input)[:300],
                    "output": str(tool_output)[:300],
                    "status": status,
                    "is_error": is_error,
                }
            )
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

        # Step boundary — reset the answer/explanation attribution flag. A fresh
        # step starts with no tool activity; the next tool_use (if any) re-marks it.
        elif etype == "step_start":
            step_has_tool = False

        # Model text response
        elif etype == "text":
            text_content = part.get("text", "")
            if text_content:
                final_texts.append(str(text_content))

        # Step finish — accumulate token usage and cost
        elif etype == "step_finish":
            current_depth = max(0, current_depth - 1)
            tokens = part.get("tokens", {})
            # Capture and reset the step's answer/explanation flag before the token
            # dict is read, so a missing tokens dict can't leak the flag into the
            # next step's attribution.
            was_tool_step = step_has_tool
            step_has_tool = False
            if isinstance(tokens, dict):
                # The backend reported usage for this step — the split is measured (even a
                # legitimately zero token count is a real measurement), not absent.
                result.usage_reported = True
                # Token counts are per-step deltas, sum across steps
                result.prompt_tokens += tokens.get("input", 0) or 0
                result.completion_tokens += tokens.get("output", 0) or 0
                result.reasoning_tokens += tokens.get("reasoning", 0) or 0
                # Answer/explanation split [H]: a step that wrote code (tool calls)
                # is counted as "answer"; a prose-only step is "explanation". This
                # is a step-granularity heuristic, not a per-token attribution.
                out_tokens = tokens.get("output", 0) or 0
                if was_tool_step:
                    result.answer_tokens += out_tokens
                else:
                    result.explanation_tokens += out_tokens
                cache = tokens.get("cache", {})
                if isinstance(cache, dict):
                    result.cache_read_tokens += cache.get("read", 0) or 0
                    result.cache_write_tokens += cache.get("write", 0) or 0
                # Total = actionable tokens only (cache is context reuse, not billed)
                result.total_tokens = (
                    result.prompt_tokens + result.completion_tokens + result.reasoning_tokens
                )
                result.context_tokens = result.total_tokens + result.cache_read_tokens
            # Collect cost — format depends on provider
            cost_val = part.get("cost", 0)
            if isinstance(cost_val, (int, float)) and cost_val > 0:
                _step_costs.append(float(cost_val))

        # Parse test output from bash tool results
        if etype == "tool_use" and part.get("tool") == "bash":
            state = part.get("state", {})
            output = state.get("output", "") if isinstance(state, dict) else ""
            if output and (
                "test" in str(output).lower()
                or "pass" in str(output).lower()
                or "fail" in str(output).lower()
            ):
                import re

                if "passed" in str(output).lower():
                    # pytest output: X passed, Y failed
                    m = re.search(r"(\d+)\s+passed", str(output))
                    if m:
                        p = int(m.group(1))
                        mf = re.search(r"(\d+)\s+failed", str(output))
                        f = int(mf.group(1)) if mf else 0
                        result.tests_passed = p
                        result.tests_total = p + f
                result.test_output = str(output)[-500:]

    result.tool_calls = tool_calls
    result.retry_loops = retry_count
    result.iteration_depth = iteration_depth
    result.final_response = "\n".join(final_texts[-3:]) if final_texts else ""

    # Provider cost format detection:
    # - DeepSeek: cost is cumulative per step (always increasing)
    # - OpenAI/Anthropic: cost is a per-step delta (may decrease)
    # If costs never decrease → cumulative, use last value.
    # If any cost is lower than a prior cost → per-step, sum all.
    if _step_costs:
        if all(_step_costs[i] >= _step_costs[i - 1] for i in range(1, len(_step_costs))):
            result.estimated_cost_usd = _step_costs[-1]  # cumulative
        else:
            result.estimated_cost_usd = sum(_step_costs)  # per-step delta

    # Estimate correctness from test results if not directly parsed
    if result.tests_total == 0 and "passed" in str(result.test_output).lower():
        result.tests_total = max(result.tests_total, 1)
        result.tests_passed = max(result.tests_passed, 1)


def normalize_opencode_event(event: dict, schema_version: int | None = None) -> dict:
    """Normalize an opencode JSONL event to a canonical v1-compatible format.

    Handles two schema versions:
      v1 (historical): flat structure — {"type":"tool","tool":"write","state":{...}},
          {"type":"reasoning","text":"..."}, {"type":"step-finish","tokens":{...}}
      v2 (current): nested structure — {"type":"tool_use","part":{"tool":"write",...}},
          {"type":"step_finish","part":{"tokens":{...}}}, {"type":"text","part":{"text":"..."}}

    Detection: v2 events have a ``part`` key containing nested fields.
    v1 events have top-level ``tool``, ``tokens``, ``text`` fields directly.

    Returns a canonical dict with:
      - ``type``: "reasoning" | "tool" | "text" | "step-finish" | "step-start" |
        "tool_result" | "step_follow"
      - ``_schema``: detected schema version (1 or 2)
      - Top-level fields: ``tool``, ``text``, ``tokens``, ``state`` (flattened from part if v2)
      - ``_raw_part``: original part dict preserved for v2 events (None for v1)
    """
    if not isinstance(event, dict):
        return {"type": "unknown", "_schema": 0, "_error": "not a dict"}

    # Detect schema if not provided
    if schema_version is None:
        etype = event.get("type", "")
        part = event.get("part")
        has_part = isinstance(part, dict)

        # v2 detection: type matches v2 naming convention (tool_use, step_start, etc.)
        # or has a non-empty part dict
        v2_types = {"tool_use", "tool_result", "step_follow", "step_start", "step_finish"}
        if etype in v2_types or (has_part and etype in ("text", "reasoning")):
            schema_version = 2
        else:
            schema_version = 1

    canonical = {"_schema": schema_version, "_raw_part": event.get("part")}

    if schema_version == 2:
        part = event.get("part", {})
        if not isinstance(part, dict):
            part = {}
        etype = event.get("type", "")

        if etype == "tool_use":
            canonical["type"] = "tool"
            canonical["tool"] = part.get("tool", "")
            state = part.get("state", {})
            canonical["state"] = state if isinstance(state, dict) else {}
            canonical["callID"] = part.get("callID", "")

        elif etype == "step_finish":
            canonical["type"] = "step-finish"
            tokens = part.get("tokens", {})
            canonical["tokens"] = tokens if isinstance(tokens, dict) else {}
            cost = part.get("cost", 0)
            canonical["cost"] = float(cost) if isinstance(cost, (int, float)) else 0.0

        elif etype == "text":
            canonical["type"] = "text"
            canonical["text"] = str(part.get("text", ""))

        elif etype == "reasoning":
            canonical["type"] = "reasoning"
            canonical["text"] = str(part.get("text", ""))

        elif etype == "step_start":
            canonical["type"] = "step-start"

        elif etype in ("tool_result", "step_follow"):
            canonical["type"] = etype

        else:
            canonical["type"] = etype

    else:
        # v1 — already flat, keep as-is
        etype = event.get("type", "")

        # Normalize type names for consistency
        type_map = {
            "tool": "tool",
            "reasoning": "reasoning",
            "text": "text",
            "step-finish": "step-finish",
            "step-start": "step-start",
            "tool_result": "tool_result",
            "step_follow": "step_follow",
        }
        canonical["type"] = type_map.get(etype, etype)

        if etype in ("reasoning", "text"):
            canonical["text"] = str(event.get("text", ""))
        if etype == "tool":
            canonical["tool"] = event.get("tool", "")
            state = event.get("state", {})
            canonical["state"] = state if isinstance(state, dict) else {}
        if etype == "step-finish":
            tokens = event.get("tokens", {})
            canonical["tokens"] = tokens if isinstance(tokens, dict) else {}

        # Preserve original event metadata
        for k in ("timestamp", "sessionID"):
            if k in event:
                canonical[k] = event[k]

    return canonical
