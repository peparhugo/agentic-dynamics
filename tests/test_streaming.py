"""Tests for the streaming subprocess runner."""

import sys

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
