"""Subprocess wrapper around the ``claude`` CLI for background-session control.

Claude Code exposes no HTTP API for background sessions (unlike OpenCode,
see ``admin/opencode_client.py``) — the ``claude`` CLI itself is the only
documented contract (``claude --bg``, ``claude agents --json --all``,
``claude logs``, ``claude stop``/``respawn``/``rm``, ``claude daemon
status``/``stop``). This module mirrors ``OpenCodeClient``'s shape but calls
the CLI instead of an HTTP API, using the same binary-resolution pattern
``src/instrument/claude_adapter.py`` already uses for headless runs.

No call touches stdin: every subprocess is invoked with ``stdin=DEVNULL`` so a
misbehaving command can never block waiting for terminal input.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Resolve the claude binary the same way src/instrument/claude_adapter.py does:
# env override, then common install paths, then $PATH.
_CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "")
if _CLAUDE_BIN:
    CLAUDE_BIN = _CLAUDE_BIN
elif Path.home().exists():
    _candidates = (
        Path.home() / ".local" / "bin" / "claude",
        Path.home() / ".claude" / "local" / "claude",
    )
    CLAUDE_BIN = next((str(p) for p in _candidates if p.exists()), "claude")
else:
    CLAUDE_BIN = "claude"

# A background session id is expected to be a stable machine identifier.
# Anything that doesn't match this shape is dropped rather than passed
# through, at every point it crosses a trust boundary (CLI output, URL path
# segment, Redis key, LivePublisher cell id).
SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")

# Redis keys shared between admin/server.py (reader) and
# scripts/claude_agents_supervisor.py (writer).
ROSTER_KEY = "claude_bg:roster"
OWNED_SESSIONS_KEY = "claude_bg:owned_sessions"
CURSOR_KEY_PREFIX = "claude_bg:cursor:"
CELL_ID_PREFIX = "claude_bg_"

_SESSION_ID_FIELD_RE = re.compile(r"(?i)\bsession\s*id\b\s*[:=]?\s*([A-Za-z0-9_-]{1,128})")
_BACKGROUNDED_RE = re.compile(r"(?i)backgrounded\s*[·•:]\s*([A-Za-z0-9_-]{1,128})")
_BARE_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{6,128}$")


def _extract_session_id_from_bg_output(text: str) -> str | None:
    """Parse the session id out of ``claude --bg``'s human-readable stdout.

    The CLI reference states the command "prints the session id and
    management commands" without pinning an exact format. Observed output is
    ``backgrounded · <id>``, so this looks for a labeled ``session id`` field
    first, then the ``backgrounded ·`` form, then a standalone id-shaped
    token, then a final id-shaped regex fallback.
    """
    match = _SESSION_ID_FIELD_RE.search(text)
    if match:
        return match.group(1)
    match = _BACKGROUNDED_RE.search(text)
    if match:
        return match.group(1)
    for line in text.splitlines():
        candidate = line.strip()
        if _BARE_TOKEN_RE.fullmatch(candidate):
            return candidate
    # Last resort: an id-shaped token containing a digit/underscore/hyphen,
    # which ordinary prose words in the surrounding CLI banner will not have.
    for token in re.findall(r"(?=[A-Za-z0-9_-]*[0-9_-])[A-Za-z0-9_-]{6,128}", text):
        return token
    return None


@dataclass
class ClaudeAgentsError(RuntimeError):
    """Actionable failure returned by or encountered while calling ``claude``."""

    message: str
    code: str = "claude_agents_error"  # binary_not_found | non_zero_exit | malformed_json | timeout

    def __str__(self) -> str:
        return self.message


class ClaudeAgentsClient:
    """Call the ``claude`` CLI for background-session observe/control actions."""

    def __init__(self, *, binary: str | None = None) -> None:
        self.binary = binary or CLAUDE_BIN

    def _run(
        self,
        args: list[str],
        *,
        timeout: float,
        expect_json: bool,
        raise_on_nonzero: bool = True,
    ) -> tuple[Any, int]:
        """Run one bounded, stdin-closed subprocess call against the CLI."""
        cmd = [self.binary, *args]
        try:
            proc = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError as error:
            raise ClaudeAgentsError(
                f"claude CLI binary not found: {self.binary!r}", code="binary_not_found"
            ) from error
        except subprocess.TimeoutExpired as error:
            raise ClaudeAgentsError(
                f"claude CLI timed out after {timeout}s running: {' '.join(cmd)}", code="timeout"
            ) from error

        if proc.returncode != 0 and raise_on_nonzero:
            detail = (proc.stderr or proc.stdout or "").strip()
            raise ClaudeAgentsError(
                f"claude CLI exited {proc.returncode}: {detail}", code="non_zero_exit"
            )
        if not expect_json:
            return proc.stdout, proc.returncode
        text = (proc.stdout or "").strip()
        if not text:
            return None, proc.returncode
        try:
            return json.loads(text), proc.returncode
        except json.JSONDecodeError as error:
            raise ClaudeAgentsError("claude CLI returned malformed JSON", code="malformed_json") from error

    def list_agents(self, cwd: str, *, all: bool = True, timeout: float = 15.0) -> list[dict]:
        """``claude agents --json [--all] --cwd <cwd>`` — every session under ``cwd``."""
        args = ["agents", "--json"]
        if all:
            args.append("--all")
        args.extend(["--cwd", cwd])
        result, _returncode = self._run(args, timeout=timeout, expect_json=True)
        if isinstance(result, list):
            entries = result
        elif isinstance(result, dict) and isinstance(result.get("agents"), list):
            entries = result["agents"]
        else:
            raise ClaudeAgentsError("claude agents --json returned an unexpected shape", code="malformed_json")

        filtered = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            session_id = entry.get("id")
            if not isinstance(session_id, str) or not SESSION_ID_PATTERN.fullmatch(session_id):
                logger.warning("dropping claude agent roster entry with an unsafe or missing id: %r", session_id)
                continue
            filtered.append(entry)
        return filtered

    def start_agent(
        self,
        task: str,
        *,
        cwd: str,
        model: str | None = None,
        advisor: str | None = None,
        skip_permissions: bool = True,
        timeout: float = 15.0,
    ) -> dict:
        """``claude --bg "<task>" --cwd <cwd> [--model ...] [--advisor ...] [--dangerously-skip-permissions]``."""
        args = ["--bg", task, "--cwd", cwd]
        if model:
            args.extend(["--model", model])
        if advisor:
            args.extend(["--advisor", advisor])
        if skip_permissions:
            args.append("--dangerously-skip-permissions")
        stdout, _returncode = self._run(args, timeout=timeout, expect_json=False)
        session_id = _extract_session_id_from_bg_output(stdout or "")
        if not session_id or not SESSION_ID_PATTERN.fullmatch(session_id):
            raise ClaudeAgentsError("claude --bg did not report a usable session id", code="malformed_json")
        return {"id": session_id, "raw_output": stdout}

    def steer_agent(
        self,
        session_id: str,
        prompt: str,
        *,
        cwd: str | None = None,
        model: str | None = None,
        advisor: str | None = None,
        skip_permissions: bool = True,
        timeout: float = 15.0,
    ) -> dict:
        """``claude stop <id>`` then ``claude --bg --resume <id> "<prompt>"``.

        Steering-by-restart: interrupt the running session (if any), then
        resume its conversation as a new background session carrying the
        adjusted prompt. ``claude`` has no mid-flight send-input for a
        running background session, so this is the closest documented
        equivalent. The resume returns a *new* session id. ``cwd`` is omitted
        when not given — ``--resume`` restores the session's own working
        directory from its saved state.
        """
        # Interrupt first. A stop against an already-stopped session is a
        # non-zero exit, which is expected and tolerated here — resume works
        # from a stopped session's on-disk conversation.
        try:
            self.stop_agent(session_id, timeout=timeout)
        except ClaudeAgentsError:
            pass
        args = ["--bg", "--resume", session_id, prompt]
        if cwd:
            args.extend(["--cwd", cwd])
        if model:
            args.extend(["--model", model])
        if advisor:
            args.extend(["--advisor", advisor])
        if skip_permissions:
            args.append("--dangerously-skip-permissions")
        stdout, _returncode = self._run(args, timeout=timeout, expect_json=False)
        resumed_id = _extract_session_id_from_bg_output(stdout or "")
        if not resumed_id or not SESSION_ID_PATTERN.fullmatch(resumed_id):
            raise ClaudeAgentsError(
                "claude --bg --resume did not report a usable session id", code="malformed_json"
            )
        return {"id": resumed_id, "resumed_from": session_id, "raw_output": stdout}

    def get_logs(self, session_id: str, *, timeout: float = 10.0) -> str:
        """``claude logs <session_id>`` — a bounded, best-effort recent-output tail."""
        stdout, _returncode = self._run(["logs", session_id], timeout=timeout, expect_json=False)
        return stdout or ""

    def stop_agent(self, session_id: str, *, timeout: float = 10.0) -> dict:
        """``claude stop <session_id>``. ``kill`` is the CLI's alias for the same operation."""
        result, _returncode = self._run(["stop", session_id], timeout=timeout, expect_json=True)
        if not isinstance(result, dict):
            raise ClaudeAgentsError("claude stop returned an unexpected JSON shape", code="malformed_json")
        return result

    def respawn_agent(self, session_id: str, *, timeout: float = 10.0) -> dict:
        """``claude respawn <session_id>`` — restart with conversation intact."""
        result, _returncode = self._run(["respawn", session_id], timeout=timeout, expect_json=True)
        if not isinstance(result, dict):
            raise ClaudeAgentsError("claude respawn returned an unexpected JSON shape", code="malformed_json")
        return result

    def rm_agent(self, session_id: str, *, timeout: float = 10.0) -> dict:
        """``claude rm <session_id>`` — remove from the list; transcript stays on disk."""
        result, _returncode = self._run(["rm", session_id], timeout=timeout, expect_json=True)
        if not isinstance(result, dict):
            raise ClaudeAgentsError("claude rm returned an unexpected JSON shape", code="malformed_json")
        return result

    def daemon_status(self, *, timeout: float = 5.0) -> dict:
        """``claude daemon status``; exit code 1 is a documented "not running" signal."""
        result, returncode = self._run(
            ["daemon", "status"], timeout=timeout, expect_json=True, raise_on_nonzero=False
        )
        if returncode == 1:
            return {"running": False}
        if returncode != 0:
            raise ClaudeAgentsError(f"claude daemon status exited {returncode}", code="non_zero_exit")
        if not isinstance(result, dict):
            raise ClaudeAgentsError("claude daemon status returned an unexpected JSON shape", code="malformed_json")
        return result

    def daemon_stop(self, *, keep_workers: bool = True, timeout: float = 10.0) -> dict:
        """``claude daemon stop --any [--keep-workers]`` — affects every hosted session."""
        args = ["daemon", "stop", "--any"]
        if keep_workers:
            args.append("--keep-workers")
        result, _returncode = self._run(args, timeout=timeout, expect_json=True)
        if not isinstance(result, dict):
            raise ClaudeAgentsError("claude daemon stop returned an unexpected JSON shape", code="malformed_json")
        return result
