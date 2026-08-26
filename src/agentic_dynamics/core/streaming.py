"""Streaming subprocess runner — incremental stdout capture for live telemetry.

Replaces ``subprocess.run(capture_output=True)`` with a line-by-line reader so
callers can publish events as they happen (live dashboards, Redis pub/sub) and
recover partial output on timeout instead of discarding it.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class StreamResult:
    """Outcome of a streamed subprocess run."""

    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    error: str = ""


def stream_subprocess(
    cmd: list[str],
    *,
    workdir: str,
    timeout: int = 300,
    on_line: Callable[[str], None] | None = None,
    watchdog: dict | None = None,
) -> StreamResult:
    """Run ``cmd`` in ``workdir``, streaming stdout line-by-line.

    Args:
        cmd: Command line (list form).
        workdir: Working directory for the process.
        timeout: Max seconds before the process is killed.
        on_line: Optional callback invoked per stdout line (trailing newline
            stripped). Exceptions raised by the callback are swallowed so a
            telemetry failure never kills the experiment run.
        watchdog: Optional kill seam (cap_runner_hardening p1). When given, it is
            populated with a ``watchdog["kill"]`` callable the moment the process
            spawns, so an external monitor (the workflow runner's phase watchdog)
            can SIGTERM a stalled agent from another thread — the runner never sees
            the ``Popen`` handle otherwise.

    Returns:
        StreamResult with the exit code (-1 on timeout, -2 on spawn failure),
        full stdout, and full stderr.
    """
    out_chunks: list[str] = []
    err_chunks: list[str] = []
    out_lock = threading.Lock()
    err_lock = threading.Lock()

    def _read(pipe: Any, chunks: list[str], lock: threading.Lock, is_stdout: bool) -> None:
        for line in iter(pipe.readline, ""):
            with lock:
                chunks.append(line)
            if is_stdout and on_line is not None:
                with contextlib.suppress(Exception):
                    on_line(line.rstrip("\n"))
        pipe.close()

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=workdir,
            stdin=subprocess.DEVNULL,
            start_new_session=True,  # own process group so descendants can be killed
        )
    except OSError as e:
        return StreamResult(exit_code=-2, stdout="", stderr="", error=str(e))

    if watchdog is not None:
        watchdog["kill"] = lambda: _terminate_process_group_sigterm(proc)

    out_thread = threading.Thread(
        target=_read, args=(proc.stdout, out_chunks, out_lock, True), daemon=True
    )
    err_thread = threading.Thread(
        target=_read, args=(proc.stderr, err_chunks, err_lock, False), daemon=True
    )
    out_thread.start()
    err_thread.start()

    timed_out = False
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _terminate_process_group(proc)

    # Reader threads end when the pipes close (all writers killed), so join
    # without a fixed deadline rather than leaving dangling readers.
    out_thread.join()
    err_thread.join()

    with out_lock:
        stdout = "".join(out_chunks)
    with err_lock:
        stderr = "".join(err_chunks)

    exit_code = -1 if timed_out else (proc.returncode if proc.returncode is not None else -1)
    return StreamResult(exit_code=exit_code, stdout=stdout, stderr=stderr, timed_out=timed_out)


def _terminate_process_group(proc: subprocess.Popen) -> None:
    """Kill the process and all descendants (opencode spawns test runners).

    A bare ``proc.kill()`` leaves spawned build/test tools orphaned; killing the
    whole session group ensures the pipes close so reader threads can finish.
    """
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def _terminate_process_group_sigterm(proc: subprocess.Popen) -> None:
    """SIGTERM the process group, escalating to SIGKILL after a short grace.

    The phase watchdog's action (cap_runner_hardening p1): a stalled agent is
    deterministically SIGTERM'd — its exit code records ``-15``, the exact measured
    stall signature — rather than left to hang for another hour. A process that
    ignores SIGTERM is escalated to SIGKILL so the session group dies and the
    reader threads' pipes close.
    """
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        proc.wait()
