"""Streaming subprocess runner — incremental stdout capture for live telemetry.

Replaces ``subprocess.run(capture_output=True)`` with a line-by-line reader so
callers can publish events as they happen (live dashboards, Redis pub/sub) and
recover partial output on timeout instead of discarding it.
"""

from __future__ import annotations

import contextlib
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
) -> StreamResult:
    """Run ``cmd`` in ``workdir``, streaming stdout line-by-line.

    Args:
        cmd: Command line (list form).
        workdir: Working directory for the process.
        timeout: Max seconds before the process is killed.
        on_line: Optional callback invoked per stdout line (trailing newline
            stripped). Exceptions raised by the callback are swallowed so a
            telemetry failure never kills the experiment run.

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
        )
    except OSError as e:
        return StreamResult(exit_code=-2, stdout="", stderr="", error=str(e))

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
        proc.kill()
        proc.wait()

    out_thread.join(timeout=5)
    err_thread.join(timeout=5)

    with out_lock:
        stdout = "".join(out_chunks)
    with err_lock:
        stderr = "".join(err_chunks)

    exit_code = -1 if timed_out else (proc.returncode if proc.returncode is not None else -1)
    return StreamResult(exit_code=exit_code, stdout=stdout, stderr=stderr, timed_out=timed_out)
