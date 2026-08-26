"""Tests for the streaming subprocess runner."""

import sys
import threading
import time

from agentic_dynamics.core.streaming import stream_subprocess


def test_captures_stdout_and_stderr():
    code = "import sys; print('one'); print('two'); print('boom', file=sys.stderr)"
    res = stream_subprocess([sys.executable, "-c", code], workdir="/tmp", timeout=30)
    assert res.exit_code == 0
    assert res.stdout.splitlines() == ["one", "two"]
    assert "boom" in res.stderr
    assert not res.timed_out


def test_on_line_called_per_line():
    code = "print('a'); print('b'); print('c')"
    seen = []
    res = stream_subprocess(
        [sys.executable, "-c", code], workdir="/tmp", timeout=30, on_line=seen.append
    )
    assert res.exit_code == 0
    assert seen == ["a", "b", "c"]


def test_on_line_exception_is_swallowed():
    code = "print('a')"

    def bad(line):
        raise RuntimeError("telemetry down")

    res = stream_subprocess([sys.executable, "-c", code], workdir="/tmp", timeout=30, on_line=bad)
    assert res.exit_code == 0
    assert res.stdout.splitlines() == ["a"]


def test_timeout_returns_partial_output():
    code = "import sys,time; print('start'); sys.stdout.flush(); time.sleep(60)"
    res = stream_subprocess([sys.executable, "-c", code], workdir="/tmp", timeout=1)
    assert res.timed_out
    assert res.exit_code == -1
    assert "start" in res.stdout


def test_missing_binary_returns_spawn_error():
    res = stream_subprocess(["/nonexistent/binary/xyz"], workdir="/tmp", timeout=5)
    assert res.exit_code == -2
    assert res.error


def test_watchdog_kill_seam_registered_and_sigterms_the_process(tmp_path):
    """The watchdog seam (cap_runner_hardening p1) registers a kill handle at spawn that SIGTERMs
    the process group — the exit code records -15, the measured stall signature."""
    marker = tmp_path / "ready.txt"
    code = (
        "import sys,time,pathlib; "
        f"print('up'); sys.stdout.flush(); pathlib.Path(r'{marker}').write_text('ready'); "
        "time.sleep(30)"
    )
    watchdog: dict = {}
    box = {}

    def run():
        box["res"] = stream_subprocess(
            [sys.executable, "-c", code], workdir="/tmp", timeout=60, watchdog=watchdog
        )

    t = threading.Thread(target=run, daemon=True)
    t.start()
    deadline = time.time() + 5
    while (not watchdog.get("kill") or not marker.exists()) and time.time() < deadline:
        time.sleep(0.02)
    assert watchdog.get("kill"), "the seam must register a kill handle once the process spawns"
    assert marker.exists(), "the child should be alive and past its first output"
    time.sleep(0.1)  # let the reader thread consume the buffered 'up' line

    watchdog["kill"]()  # the phase watchdog's action: SIGTERM the stalled agent
    t.join(timeout=10)

    res = box["res"]
    assert res.exit_code == -15, f"expected SIGTERM (exit -15), got {res.exit_code}"
    assert "up" in res.stdout
    assert not res.timed_out
