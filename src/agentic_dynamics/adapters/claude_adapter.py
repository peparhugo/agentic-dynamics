"""Claude CLI adapter — run Claude Code headless and emit opencode-format JSONL.

Anthropic's ToS prohibits using Claude Pro/Max subscriptions inside opencode's
provider layer. This module sidesteps that by driving the official ``claude``
CLI directly (``--output-format stream-json``) and translating its event
stream into opencode's ``run --format json`` event schema, so every downstream
parser (``analyze_trajectories``, ``efficiency``, lab books) works unchanged.

Translation is stateful: Claude splits a tool call into an ``assistant``
``tool_use`` block (running) and a ``user`` ``tool_result`` block (done), while
opencode emits a single completed ``tool_use`` event. ``ClaudeStreamAdapter``
buffers pending calls and flushes one event per completed tool.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

# Import-order-sensitive (DO NOT let isort reorder; pinned with # isort: skip): ``control.live``
# MUST be imported BEFORE ``agentic_dynamics.adapters.opencode`` here. ``opencode`` imports
# ``control.live`` (the pinned execution→control telemetry seam), and ``control`` transitively
# imports ``runtime`` which eagerly imports ``adapters.opencode``. Importing ``control`` first
# fully loads it (and, through that chain, fully loads ``opencode``) before this module touches
# ``opencode`` — if ``opencode`` were imported first it would be PARTIALLY initialized when the
# ``control → runtime → opencode`` chain re-enters it (ImportError). Same contract as the old
# pre-sort ordering; only this line's position matters.
from agentic_dynamics.control.live import make_publisher  # isort: skip
from agentic_dynamics.adapters.opencode import (  # noqa: E402  # isort: skip
    AgenticResult,
    _build_standardized_prompt,
    _diff_workdir,
    _init_git_workdir,
    _list_files,
    _parse_session_output,
)
from agentic_dynamics.core.cost_provenance import (  # noqa: E402
    METHOD_TOKEN_PRICE_TABLE,
    CostSource,
    resolve_cost_observation,
)
from agentic_dynamics.core.streaming import stream_subprocess


def _resolve_claude_bin(
    *,
    configured: str | None = None,
    find_executable: Callable[[str], str | None] = shutil.which,
) -> str:
    """Resolve Claude through the portable environment contract only.

    Deployments either put ``claude`` on ``PATH`` or set ``CLAUDE_BIN``. The framework must not
    know a user's installer-specific directory layout.

    Host fallback (mirrors ``opencode.py``'s binary resolution): when neither is present, fall
    back to the framework's canonical install location ``~/.local/bin/claude`` (the claude
    symlink chain — ``~/.local/share/claude/versions/<v>``) BEFORE giving up and emitting a
    bare ``"claude"`` that cannot spawn. Without this, a shell whose PATH lacks ``~/.local/bin``
    silently fails every anthropic cell with a spawn error whose real cause (``stream.error``)
    the adapter never surfaces — the measured signature was ``exit_code=-2`` at ~5s, $0, empty
    stderr, indistinguishable from a kill.
    """
    if configured:
        return configured
    resolved = find_executable("claude")
    if resolved:
        return resolved
    home_claude = Path.home() / ".local" / "bin" / "claude"
    if home_claude.exists():
        return str(home_claude)
    return "claude"  # last resort: rely on $PATH at spawn time


# Resolve Claude CLI through the environment, never a host-specific installer path.
CLAUDE_BIN = _resolve_claude_bin(configured=os.environ.get("CLAUDE_BIN"))


def adapt_usage(usage: Any, total_cost_usd: float | None = None) -> dict[str, Any]:
    """Map Claude CLI ``result.usage`` to opencode's ``step-finish`` tokens.

    Claude does not break out reasoning tokens in usage (thinking is folded
    into ``output_tokens``), so ``reasoning`` is always 0 — matching the
    framework's honest-token semantics. Cache fields map directly.

    **The zero-coercion is gone.** This function used to default ``total_cost_usd`` to ``0.0``
    and then emit ``float(total_cost_usd or 0.0)`` — two separate coercions, either of which
    turned "Claude CLI reported no cost" into "this run was free". A subscription run legitimately
    reports no ``total_cost_usd`` (there is no per-call charge to report), so the coercion was
    firing on the common path and the resulting $0.00 was indistinguishable from a metered zero.

    Now an absent cost stays ``None`` all the way into the emitted event, and
    ``core.cost_provenance`` decides what it means. ``0.0`` passed in explicitly still emits
    ``0.0`` — a reported zero is a real observation and is preserved as one.
    """
    if not isinstance(usage, dict):
        usage = {}
    input_tokens = int(usage.get("input_tokens", 0) or 0)
    output_tokens = int(usage.get("output_tokens", 0) or 0)
    cache_read = int(usage.get("cache_read_input_tokens", 0) or 0)
    cache_write = int(usage.get("cache_creation_input_tokens", 0) or 0)
    total = input_tokens + output_tokens
    # ``bool`` is an ``int`` in Python; a ``True`` here would otherwise become a $1.00 cost.
    reported = (
        float(total_cost_usd)
        if isinstance(total_cost_usd, (int, float)) and not isinstance(total_cost_usd, bool)
        else None
    )
    return {
        "tokens": {
            "input": input_tokens,
            "output": output_tokens,
            "reasoning": 0,
            "total": total,
            "cache": {"read": cache_read, "write": cache_write},
        },
        "cost": reported,
    }


class ClaudeStreamAdapter:
    """Stateful translator from Claude CLI stream-json events to opencode events."""

    def __init__(self) -> None:
        self._pending_tools: dict[str, dict[str, Any]] = {}
        self._started = False

    def feed(self, event: dict[str, Any]) -> list[dict[str, Any]]:
        """Translate one Claude event; returns zero or more opencode events."""
        etype = event.get("type", "")

        if etype == "system":
            if self._started:
                return []
            self._started = True
            return [{"type": "step_start", "part": {"type": "step-start"}}]

        if etype == "assistant":
            return self._handle_assistant(event.get("message", {}))

        if etype == "user":
            return self._handle_user(event.get("message", {}))

        if etype == "result":
            return self._handle_result(event)

        return []

    def _handle_assistant(self, message: dict[str, Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        content = message.get("content", [])
        if not isinstance(content, list):
            content = []
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "text":
                text = block.get("text", "")
                if text:
                    out.append({"type": "text", "part": {"type": "text", "text": text}})
            elif btype == "thinking":
                text = block.get("thinking", "")
                if text:
                    out.append({"type": "reasoning", "part": {"type": "reasoning", "text": text}})
            elif btype == "tool_use":
                call_id = block.get("id", "")
                self._pending_tools[call_id] = {
                    "tool": block.get("name", ""),
                    "input": block.get("input", {}),
                }
        return out

    def _handle_user(self, message: dict[str, Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        content = message.get("content", [])
        if not isinstance(content, list):
            content = []
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_result":
                continue
            call_id = block.get("tool_use_id", "")
            pending = self._pending_tools.pop(call_id, {"tool": "", "input": {}})
            status = "error" if block.get("is_error") else "completed"
            out.append(
                {
                    "type": "tool_use",
                    "part": {
                        "type": "tool",
                        "tool": pending["tool"],
                        "callID": call_id,
                        "state": {
                            "status": status,
                            "input": pending["input"],
                            "output": block.get("content", ""),
                        },
                    },
                }
            )
        return out

    def _handle_result(self, event: dict[str, Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for call_id, pending in self._pending_tools.items():
            out.append(
                {
                    "type": "tool_use",
                    "part": {
                        "type": "tool",
                        "tool": pending["tool"],
                        "callID": call_id,
                        "state": {"status": "completed", "input": pending["input"], "output": ""},
                    },
                }
            )
        self._pending_tools.clear()

        # ``.get("total_cost_usd")`` with NO default: a missing key yields ``None`` (unknown),
        # a present ``0.0`` yields ``0.0`` (a metered zero). The old ``, 0.0`` default erased
        # that distinction at the source, before any downstream code could see it.
        usage = adapt_usage(event.get("usage", {}), event.get("total_cost_usd"))
        part: dict[str, Any] = {"type": "step-finish", "tokens": usage["tokens"]}
        # Omit the key entirely when unknown, rather than emitting ``"cost": null``. The
        # opencode event schema this stream is translated INTO expresses "no cost reported"
        # by absence, and the parser's ``_reported_any_cost`` flag reads it that way.
        if usage["cost"] is not None:
            part["cost"] = usage["cost"]
        out.append({"type": "step_finish", "part": part})
        return out


# opencode-style anthropic model ids (right of "anthropic/") → Claude Code --model.
# Real Claude Code model ids/aliases pass through unchanged; framework-internal
# ids with no Claude Code equivalent map to a real, subscription-accessible model.
_CLAUDE_MODEL_ALIASES: dict[str, str] = {
    # Claude 5 generation (current — verified via Claude Code 2.1.228):
    "claude-opus-5": "claude-opus-5",
    "claude-sonnet-5": "claude-sonnet-5",
    "claude-haiku-5": "claude-haiku-5",
    # Latest model (Claude Code's current default; alias "fable"):
    "claude-fable-5": "claude-fable-5",
    # Claude 4.5 generation (still available):
    "claude-opus-4-5": "claude-opus-4-5",
    "claude-sonnet-4-5": "claude-sonnet-4-5",
    "claude-haiku-4-5": "claude-haiku-4-5",
    # Aliases:
    "sonnet": "sonnet",
    "opus": "opus",
    "haiku": "haiku",
    "fable": "fable",
}


def _resolve_claude_model(model: str) -> str:
    """Map an opencode-style model id to a Claude Code ``--model`` value."""
    model_id = (model.split("/", 1)[1] if "/" in model else model).strip()
    if not model_id or model_id.lower() == "anthropic":
        return ""
    key = model_id.lower()
    if key in _CLAUDE_MODEL_ALIASES:
        return _CLAUDE_MODEL_ALIASES[key]
    return model_id


def _claude_model_arg(model: str) -> list[str]:
    """Derive a ``--model`` argument from an opencode-style ``provider/model`` id."""
    resolved = _resolve_claude_model(model)
    if not resolved:
        return []
    return ["--model", resolved]


def _estimate_claude_cost(result: AgenticResult, model: str) -> float:
    """Estimate cost from tokens when Claude CLI reports no metered cost."""
    from agentic_dynamics.measurement.efficiency import get_pricing

    pricing = get_pricing("anthropic", model)
    return (
        result.prompt_tokens * pricing["input"]
        + result.completion_tokens * pricing["output"]
        + result.reasoning_tokens * pricing.get("reasoning", pricing["output"])
        + result.cache_read_tokens * pricing["cache_read"]
        + result.cache_write_tokens * pricing["cache_write"]
    ) / 1_000_000


def run_claude_agentic(
    prompt: str,
    *,
    model: str = "anthropic/claude-sonnet-4-5",
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
    watchdog: dict | None = None,
) -> AgenticResult:
    """Run an agentic session through the Claude CLI, emitting opencode JSONL.

    Mirrors ``run_opencode_agentic``: same worktree isolation, standardized
    prompt injection, and ``AgenticResult`` return — but execution happens in
    the official ``claude`` CLI and its stream is translated to opencode's
    event schema.

    Note: Claude CLI exposes no reasoning-effort flag; thinking is constrained
    by the standardized prompt header (``thinking_budget_tokens``), matching
    the opencode path.

    ``session_id`` + ``fork=True`` resume the workflow by forking the given
    session (``--resume <id> --fork-session``), so the shared context prefix is
    served as provider cache reads.
    """
    import tempfile

    t0 = time.monotonic()
    result = AgenticResult(
        run_id=session_name or f"claude_{int(t0)}", task=prompt, model=model, workdir=workdir
    )
    result.thinking_effort = thinking_effort or "default"
    result.thinking_budget_tokens = thinking_budget_tokens

    if standardize and not prompt.startswith("[STANDARDIZED CONSTRAINTS"):
        prompt = _build_standardized_prompt(
            prompt,
            thinking_budget_tokens=thinking_budget_tokens,
            output_token_limit=output_token_limit,
            enforce_pytest=enforce_pytest,
            silent_mode=silent_mode,
        )

    if workdir is None:
        workdir = tempfile.mkdtemp(prefix="exp_")
        result.workdir = workdir

    if init_git:
        _init_git_workdir(workdir)

    files_before = _list_files(workdir)

    cmd = [
        CLAUDE_BIN,
        "-p",
        prompt,
        "--output-format",
        "stream-json",
        "--verbose",
        "--dangerously-skip-permissions",
    ]
    cmd.extend(_claude_model_arg(model))
    if fork and session_id:
        cmd.extend(["--resume", session_id, "--fork-session"])

    adapter = ClaudeStreamAdapter()
    translated_lines: list[str] = []
    publisher = make_publisher() if on_event is None else None
    captured_session_id = ""

    # Live transcript seam (cap_runner_hardening p1): mirror opencode's watchdog path —
    # append each translated event line to the transcript file as it arrives so the runner's
    # stall monitor can read the last-step age from the file's mtime. Only when the seam is
    # present; the default path stays byte-identical (transcript written once at the end).
    live_fh = None
    if watchdog is not None:
        live_path = (
            Path(transcript_path)
            if transcript_path
            else Path(workdir) / ".instrument" / "session.jsonl"
        )
        live_path.parent.mkdir(parents=True, exist_ok=True)
        live_fh = live_path.open("a")

    def on_line(line: str) -> None:
        nonlocal captured_session_id
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return
        sid = event.get("session_id", "")
        if sid:
            captured_session_id = sid
        for out in adapter.feed(event):
            serialized = json.dumps(out)
            translated_lines.append(serialized)
            if live_fh is not None:
                live_fh.write(serialized + "\n")
                live_fh.flush()
            if on_event is not None:
                on_event(out)
            elif publisher is not None:
                publisher.publish_event(out)

    try:
        stream = stream_subprocess(
            cmd, workdir=workdir, timeout=timeout, on_line=on_line, watchdog=watchdog
        )
    finally:
        if live_fh is not None:
            live_fh.close()

    if stream.timed_out:
        result.error = f"Timeout after {timeout}s"
        result.exit_code = -1
    else:
        result.exit_code = stream.exit_code
        # Surface the spawn error (stream.error) when present — a failed spawn with an
        # unresolvable binary previously reported only an empty stderr + exit_code=-2,
        # indistinguishable from a kill (the silent-failure signature the host fallback
        # above removes). stream.stderr is the fallback detail for nonzero exits.
        result.error = (stream.error or stream.stderr).strip() if stream.exit_code != 0 else ""

    result.raw_transcript = "\n".join(translated_lines)
    if result.raw_transcript:
        _parse_session_output(result.raw_transcript, result)

    result.session_id = captured_session_id

    result.duration_s = time.monotonic() - t0
    result.files_created, result.files_modified = _diff_workdir(workdir, files_before)

    # Resolve the cost's PROVENANCE. Anthropic is subscription-class: a Claude Code run has no
    # per-call charge, so the CLI usually reports no ``total_cost_usd`` at all and the price-table
    # figure below is a *counterfactual* — what these tokens would have cost on the metered API.
    # That is a legitimate ESTIMATED figure and the repo already reports it; what was wrong was
    # publishing it (or its absence) as if it were metered truth.
    if result.cost_source is not CostSource.METERED:
        estimate: float | None = None
        if result.total_tokens > 0:
            try:
                estimate = _estimate_claude_cost(result, model)
            except (ValueError, KeyError):
                # No pricing row for this model id — an UNKNOWN cost, recorded as such.
                estimate = None
        result.apply_cost_observation(
            resolve_cost_observation(
                reported_cost_usd=result.reported_cost_usd,
                estimated_cost_usd=estimate,
                estimation_method=METHOD_TOKEN_PRICE_TABLE,
                tokens_observed=result.total_tokens > 0 or result.usage_reported,
            )
        )

    if result.raw_transcript:
        out_path = (
            Path(transcript_path)
            if transcript_path
            else Path(workdir) / ".instrument" / "session.jsonl"
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(result.raw_transcript)

    return result
