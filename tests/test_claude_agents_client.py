"""Contract tests for the ``claude`` CLI subprocess wrapper."""

from __future__ import annotations

import json
import subprocess

import pytest

from admin import claude_agents_client
from admin.claude_agents_client import ClaudeAgentsClient, ClaudeAgentsError


class FakeCompletedProcess:
    def __init__(self, *, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _client(monkeypatch, fake_run):
    """Return a client whose subprocess.run calls are intercepted by ``fake_run``."""
    monkeypatch.setattr(claude_agents_client.subprocess, "run", fake_run)
    return ClaudeAgentsClient(binary="claude")


def test_list_agents_filters_unsafe_or_missing_ids(monkeypatch):
    """Only id-shaped entries survive; everything else is dropped with a warning."""
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        payload = json.dumps([
            {"id": "abc123", "status": "running"},
            {"id": "../etc/passwd", "status": "running"},
            {"id": "", "status": "running"},
            {"status": "running"},
            "not-a-dict",
        ])
        return FakeCompletedProcess(stdout=payload)

    client = _client(monkeypatch, fake_run)
    result = client.list_agents("/tmp/work", all=True, timeout=5)

    assert result == [{"id": "abc123", "status": "running"}]
    assert calls[0] == ["claude", "agents", "--json", "--all", "--cwd", "/tmp/work"]


def test_list_agents_without_all_flag(monkeypatch):
    captured = []

    def fake_run(cmd, **kwargs):
        captured.append(cmd)
        return FakeCompletedProcess(stdout="[]")

    client = _client(monkeypatch, fake_run)
    client.list_agents("/tmp/work", all=False)
    assert "--all" not in captured[0]


def test_list_agents_rejects_non_list_non_agents_shape(monkeypatch):
    def fake_run(cmd, **kwargs):
        return FakeCompletedProcess(stdout=json.dumps({"unexpected": "shape"}))

    client = _client(monkeypatch, fake_run)
    with pytest.raises(ClaudeAgentsError) as excinfo:
        client.list_agents("/tmp/work")
    assert excinfo.value.code == "malformed_json"


def test_missing_binary_raises_distinguishable_error(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise FileNotFoundError()

    client = _client(monkeypatch, fake_run)
    with pytest.raises(ClaudeAgentsError) as excinfo:
        client.list_agents("/tmp/work")
    assert excinfo.value.code == "binary_not_found"


def test_timeout_raises_distinguishable_error(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout", 1))

    client = _client(monkeypatch, fake_run)
    with pytest.raises(ClaudeAgentsError) as excinfo:
        client.get_logs("abc123", timeout=1)
    assert excinfo.value.code == "timeout"


def test_non_zero_exit_raises_distinguishable_error_with_stderr_detail(monkeypatch):
    def fake_run(cmd, **kwargs):
        return FakeCompletedProcess(returncode=2, stderr="boom")

    client = _client(monkeypatch, fake_run)
    with pytest.raises(ClaudeAgentsError) as excinfo:
        client.stop_agent("abc123")
    assert excinfo.value.code == "non_zero_exit"
    assert "boom" in str(excinfo.value)


def test_malformed_json_raises_distinguishable_error(monkeypatch):
    def fake_run(cmd, **kwargs):
        return FakeCompletedProcess(stdout="{not json")

    client = _client(monkeypatch, fake_run)
    with pytest.raises(ClaudeAgentsError) as excinfo:
        client.stop_agent("abc123")
    assert excinfo.value.code == "malformed_json"


def test_start_agent_extracts_session_id_from_labeled_output(monkeypatch):
    captured = []

    def fake_run(cmd, **kwargs):
        captured.append(cmd)
        return FakeCompletedProcess(stdout="Started.\nSession ID: sess_abc123\nRun `claude logs sess_abc123`.\n")

    client = _client(monkeypatch, fake_run)
    result = client.start_agent(
        "do the thing", cwd="/tmp/work", model="claude-sonnet-4-5", advisor="opus", skip_permissions=True
    )

    assert result["id"] == "sess_abc123"
    assert captured[0] == [
        "claude",
        "--bg",
        "do the thing",
        "--cwd",
        "/tmp/work",
        "--model",
        "claude-sonnet-4-5",
        "--advisor",
        "opus",
        "--dangerously-skip-permissions",
    ]


def test_start_agent_falls_back_to_bare_token(monkeypatch):
    def fake_run(cmd, **kwargs):
        return FakeCompletedProcess(stdout="sess_bare_token_1\n")

    client = _client(monkeypatch, fake_run)
    result = client.start_agent("task", cwd="/tmp/work")
    assert result["id"] == "sess_bare_token_1"


def test_start_agent_without_usable_id_raises_malformed_json(monkeypatch):
    def fake_run(cmd, **kwargs):
        return FakeCompletedProcess(stdout="no id here, just prose without token shapes.")

    client = _client(monkeypatch, fake_run)
    with pytest.raises(ClaudeAgentsError) as excinfo:
        client.start_agent("task", cwd="/tmp/work")
    assert excinfo.value.code == "malformed_json"


def test_start_agent_never_touches_stdin(monkeypatch):
    captured_kwargs = {}

    def fake_run(cmd, **kwargs):
        captured_kwargs.update(kwargs)
        return FakeCompletedProcess(stdout="Session ID: sess_1\n")

    client = _client(monkeypatch, fake_run)
    client.start_agent("task", cwd="/tmp/work")
    assert captured_kwargs["stdin"] == subprocess.DEVNULL


def test_get_logs_returns_raw_text_not_json(monkeypatch):
    def fake_run(cmd, **kwargs):
        return FakeCompletedProcess(stdout="line one\nline two\n")

    client = _client(monkeypatch, fake_run)
    assert client.get_logs("sess_1") == "line one\nline two\n"


def test_stop_respawn_rm_require_json_object_result(monkeypatch):
    def fake_run(cmd, **kwargs):
        return FakeCompletedProcess(stdout=json.dumps({"ok": True}))

    client = _client(monkeypatch, fake_run)
    assert client.stop_agent("sess_1") == {"ok": True}
    assert client.respawn_agent("sess_1") == {"ok": True}
    assert client.rm_agent("sess_1") == {"ok": True}


def test_daemon_status_exit_code_one_means_not_running_without_raising(monkeypatch):
    def fake_run(cmd, **kwargs):
        return FakeCompletedProcess(returncode=1, stdout="")

    client = _client(monkeypatch, fake_run)
    assert client.daemon_status() == {"running": False}


def test_daemon_status_other_nonzero_exit_still_raises(monkeypatch):
    def fake_run(cmd, **kwargs):
        return FakeCompletedProcess(returncode=17, stdout="")

    client = _client(monkeypatch, fake_run)
    with pytest.raises(ClaudeAgentsError) as excinfo:
        client.daemon_status()
    assert excinfo.value.code == "non_zero_exit"


def test_daemon_status_running_returns_parsed_json(monkeypatch):
    def fake_run(cmd, **kwargs):
        return FakeCompletedProcess(stdout=json.dumps({"running": True, "pid": 4242}))

    client = _client(monkeypatch, fake_run)
    assert client.daemon_status() == {"running": True, "pid": 4242}


def test_daemon_stop_passes_keep_workers_flag(monkeypatch):
    captured = []

    def fake_run(cmd, **kwargs):
        captured.append(cmd)
        return FakeCompletedProcess(stdout=json.dumps({"ok": True}))

    client = _client(monkeypatch, fake_run)
    client.daemon_stop(keep_workers=True)
    client.daemon_stop(keep_workers=False)
    assert captured[0] == ["claude", "daemon", "stop", "--any", "--keep-workers"]
    assert captured[1] == ["claude", "daemon", "stop", "--any"]


def test_every_call_closes_stdin(monkeypatch):
    """No subprocess call in this module ever leaves stdin open to a background session."""
    captured_kwargs = []

    def fake_run(cmd, **kwargs):
        captured_kwargs.append(kwargs)
        if cmd[1:3] == ["daemon", "status"]:
            return FakeCompletedProcess(returncode=1)
        if "--json" in cmd:
            return FakeCompletedProcess(stdout="[]")
        if cmd[1] == "logs":
            return FakeCompletedProcess(stdout="hello\n")
        return FakeCompletedProcess(stdout=json.dumps({"ok": True}))

    client = _client(monkeypatch, fake_run)
    client.list_agents("/tmp/work")
    client.get_logs("sess_1")
    client.stop_agent("sess_1")
    client.respawn_agent("sess_1")
    client.rm_agent("sess_1")
    client.daemon_status()
    client.daemon_stop()

    assert captured_kwargs
    assert all(kwargs["stdin"] == subprocess.DEVNULL for kwargs in captured_kwargs)
