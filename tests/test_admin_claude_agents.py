"""Contract tests for the Claude background-session Control Room endpoints."""

from __future__ import annotations

import json

import pytest

from admin import server
from admin.claude_agents_client import OWNED_SESSIONS_KEY, ROSTER_KEY, ClaudeAgentsError


class FakeRedis:
    """In-memory subset of Redis used by the claude-agent routes."""

    def __init__(self, *, owned=None, roster=None):
        self.values: dict[str, str] = {}
        self.owned: set[str] = set(owned or [])
        self.sadd_calls: list[str] = []
        self.srem_calls: list[str] = []
        self.delete_calls: list[str] = []
        if roster is not None:
            self.values[ROSTER_KEY] = json.dumps(roster)

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, *, nx=False, ex=None):
        assert ex is not None
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    def sismember(self, key, member):
        assert key == OWNED_SESSIONS_KEY
        return member in self.owned

    def sadd(self, key, member):
        assert key == OWNED_SESSIONS_KEY
        self.owned.add(member)
        self.sadd_calls.append(member)

    def srem(self, key, member):
        assert key == OWNED_SESSIONS_KEY
        self.owned.discard(member)
        self.srem_calls.append(member)

    def delete(self, key):
        self.delete_calls.append(key)
        self.values.pop(key, None)


class FakeClient:
    """Record every subprocess-wrapper call the routes make."""

    def __init__(self):
        self.start_calls: list[dict] = []
        self.stop_calls: list[str] = []
        self.respawn_calls: list[str] = []
        self.rm_calls: list[str] = []
        self.daemon_status_calls = 0
        self.daemon_stop_calls: list[bool] = []
        self.get_logs_calls: list[str] = []
        self.steer_calls: list[dict] = []
        self.start_result = {"id": "sess_started01"}
        self.steer_result = {"id": "sess_steered02", "resumed_from": None}
        self.daemon_status_result = {"running": True, "pid": 4242}
        self.get_logs_result = "log text\n"
        self.error: ClaudeAgentsError | None = None

    def _maybe_raise(self):
        if self.error is not None:
            raise self.error

    def start_agent(self, task, *, cwd, model=None, advisor=None, skip_permissions=True, timeout=15.0):
        self.start_calls.append(
            {"task": task, "cwd": cwd, "model": model, "advisor": advisor, "skip_permissions": skip_permissions}
        )
        self._maybe_raise()
        return self.start_result

    def stop_agent(self, session_id, *, timeout=10.0):
        self.stop_calls.append(session_id)
        self._maybe_raise()
        return {"ok": True}

    def respawn_agent(self, session_id, *, timeout=10.0):
        self.respawn_calls.append(session_id)
        self._maybe_raise()
        return {"ok": True}

    def rm_agent(self, session_id, *, timeout=10.0):
        self.rm_calls.append(session_id)
        self._maybe_raise()
        return {"ok": True}

    def daemon_status(self, *, timeout=5.0):
        self.daemon_status_calls += 1
        self._maybe_raise()
        return self.daemon_status_result

    def daemon_stop(self, *, keep_workers=True, timeout=10.0):
        self.daemon_stop_calls.append(keep_workers)
        self._maybe_raise()
        return {"ok": True}

    def get_logs(self, session_id, *, timeout=10.0):
        self.get_logs_calls.append(session_id)
        self._maybe_raise()
        return self.get_logs_result

    def steer_agent(self, session_id, prompt, *, cwd=None, model=None, advisor=None, skip_permissions=True, timeout=15.0):
        self.steer_calls.append(
            {"session_id": session_id, "prompt": prompt, "model": model, "advisor": advisor}
        )
        self._maybe_raise()
        return self.steer_result


@pytest.fixture
def fake_redis(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(server, "_redis", lambda: redis)
    return redis


@pytest.fixture
def fake_client(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(server, "_claude_agents", lambda: client)
    return client


def _headers(key="idem-1"):
    return {"Idempotency-Key": key}


# ---------------------------------------------------------------------------
# GET /api/claude-agents
# ---------------------------------------------------------------------------


def test_roster_reads_redis_and_never_touches_the_cli(fake_client, monkeypatch):
    roster = [{"id": "sess_a", "status": "running", "owned": True}]
    redis = FakeRedis(roster=roster)
    monkeypatch.setattr(server, "_redis", lambda: redis)

    response = server.app.test_client().get("/api/claude-agents")

    assert response.status_code == 200
    body = response.get_json()
    assert body["agents"] == roster
    assert isinstance(body["workdirs"], list) and body["workdirs"]
    assert fake_client.daemon_status_calls == 0


def test_roster_missing_key_returns_supervisor_unavailable_not_500(fake_redis, fake_client):
    response = server.app.test_client().get("/api/claude-agents")

    assert response.status_code == 200
    assert response.get_json()["error"] == "supervisor_unavailable"
    assert response.get_json()["agents"] == []


def test_roster_malformed_json_returns_supervisor_unavailable(fake_client, monkeypatch):
    redis = FakeRedis()
    redis.values[ROSTER_KEY] = "{not json"
    monkeypatch.setattr(server, "_redis", lambda: redis)

    response = server.app.test_client().get("/api/claude-agents")

    assert response.status_code == 200
    assert response.get_json()["error"] == "supervisor_unavailable"


def test_roster_redis_failure_returns_supervisor_unavailable(fake_client, monkeypatch):
    monkeypatch.setattr(server, "_redis", lambda: (_ for _ in ()).throw(RuntimeError("down")))

    response = server.app.test_client().get("/api/claude-agents")

    assert response.status_code == 200
    assert response.get_json()["error"] == "supervisor_unavailable"


# ---------------------------------------------------------------------------
# GET /api/claude-agents/<id>/logs
# ---------------------------------------------------------------------------


def test_external_log_fetch_returns_plain_text(fake_client):
    fake_client.get_logs_result = "hello from an external session\n"

    response = server.app.test_client().get("/api/claude-agents/sess_ext01/logs")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "hello from an external session\n"
    assert response.headers["X-Claude-Agent-Log-Truncated"] == "false"
    assert fake_client.get_logs_calls == ["sess_ext01"]


def test_external_log_fetch_truncates_at_the_documented_cap(fake_client):
    fake_client.get_logs_result = "x" * (server.MAX_CLAUDE_AGENT_LOG_BYTES + 500)

    response = server.app.test_client().get("/api/claude-agents/sess_big/logs")

    assert response.status_code == 200
    assert len(response.get_data()) == server.MAX_CLAUDE_AGENT_LOG_BYTES
    assert response.headers["X-Claude-Agent-Log-Truncated"] == "true"


def test_log_fetch_rejects_unsafe_id_before_calling_the_cli(fake_client):
    response = server.app.test_client().get("/api/claude-agents/../etc/passwd/logs")

    assert response.status_code in (400, 404)
    assert fake_client.get_logs_calls == []


def test_log_fetch_maps_cli_error_to_502(fake_client):
    fake_client.error = ClaudeAgentsError("claude CLI binary not found", code="binary_not_found")

    response = server.app.test_client().get("/api/claude-agents/sess_1/logs")

    assert response.status_code == 502
    assert response.get_json()["code"] == "binary_not_found"


# ---------------------------------------------------------------------------
# GET /api/claude-agents/daemon
# ---------------------------------------------------------------------------


def test_daemon_status_passthrough_is_read_only(fake_client):
    response = server.app.test_client().get("/api/claude-agents/daemon")

    assert response.status_code == 200
    assert response.get_json() == {"running": True, "pid": 4242}


def test_daemon_status_cli_error_reports_not_running_without_500(fake_client):
    fake_client.error = ClaudeAgentsError("timed out", code="timeout")

    response = server.app.test_client().get("/api/claude-agents/daemon")

    assert response.status_code == 200
    assert response.get_json()["running"] is False


# ---------------------------------------------------------------------------
# POST /api/claude-agents — start
# ---------------------------------------------------------------------------


def test_start_requires_loopback_same_origin_json_and_idempotency(fake_redis, fake_client):
    client = server.app.test_client()
    body = {"task": "do the thing", "workdir": "repository"}

    assert client.post("/api/claude-agents", data="x").status_code == 415
    assert client.post("/api/claude-agents", json=body).status_code == 400
    headers = _headers()
    assert (
        client.post("/api/claude-agents", json=body, headers={**headers, "Origin": "https://evil.example"}).status_code
        == 403
    )
    assert (
        client.post("/api/claude-agents", json=body, headers=headers, environ_base={"REMOTE_ADDR": "10.0.0.4"}).status_code
        == 403
    )


def test_start_rejects_unapproved_workdir_without_calling_the_cli(fake_redis, fake_client):
    response = server.app.test_client().post(
        "/api/claude-agents",
        json={"task": "do it", "workdir": "not-approved"},
        headers=_headers(),
    )

    assert response.status_code == 400
    assert fake_client.start_calls == []


def test_start_rejects_empty_or_oversized_task(fake_redis, fake_client):
    client = server.app.test_client()
    too_long = "x" * (server.MAX_CLAUDE_AGENT_TASK_CHARS + 1)

    assert client.post(
        "/api/claude-agents", json={"task": "  ", "workdir": "repository"}, headers=_headers("k1")
    ).status_code == 400
    assert client.post(
        "/api/claude-agents", json={"task": too_long, "workdir": "repository"}, headers=_headers("k2")
    ).status_code == 400
    assert fake_client.start_calls == []


def test_start_resolves_model_and_validates_advisor(fake_redis, fake_client):
    client = server.app.test_client()

    ok = client.post(
        "/api/claude-agents",
        json={"task": "build it", "workdir": "repository", "model": "anthropic/claude-sonnet-4-5", "advisor": "opus"},
        headers=_headers("k1"),
    )
    assert ok.status_code == 201
    assert fake_client.start_calls[-1]["model"] == "claude-sonnet-4-5"
    assert fake_client.start_calls[-1]["advisor"] == "opus"
    assert fake_client.start_calls[-1]["skip_permissions"] is True

    bad_advisor = client.post(
        "/api/claude-agents",
        json={"task": "build it", "workdir": "repository", "advisor": "!!!not-safe!!!"},
        headers=_headers("k2"),
    )
    assert bad_advisor.status_code == 400
    assert len(fake_client.start_calls) == 1  # the invalid-advisor request never reached the CLI


def test_start_workdir_allowlist_is_independent_of_design_sessions(fake_redis, fake_client, tmp_path, monkeypatch):
    """FINOPS_CLAUDE_AGENT_WORKDIRS is parsed independently of FINOPS_DESIGN_WORKDIRS."""
    monkeypatch.delenv("FINOPS_DESIGN_WORKDIRS", raising=False)
    monkeypatch.setenv("FINOPS_CLAUDE_AGENT_WORKDIRS", str(tmp_path))

    response = server.app.test_client().post(
        "/api/claude-agents",
        json={"task": "build it", "workdir": "repository"},
        headers=_headers(),
    )

    assert response.status_code == 201
    assert fake_client.start_calls[-1]["cwd"] == str(tmp_path)


def test_start_records_ownership_and_returns_new_id(fake_redis, fake_client):
    response = server.app.test_client().post(
        "/api/claude-agents",
        json={"task": "build it", "workdir": "repository"},
        headers=_headers(),
    )

    assert response.status_code == 201
    assert response.get_json() == {"ok": True, "id": "sess_started01"}
    assert "sess_started01" in fake_redis.owned


def test_start_is_idempotent_on_retry(fake_redis, fake_client):
    client = server.app.test_client()
    body = {"task": "build it", "workdir": "repository"}
    headers = _headers("retry-key")

    first = client.post("/api/claude-agents", json=body, headers=headers)
    second = client.post("/api/claude-agents", json=body, headers=headers)

    assert first.get_json() == second.get_json()
    assert len(fake_client.start_calls) == 1


# ---------------------------------------------------------------------------
# POST /api/claude-agents/<id>/stop, /respawn, /rm — ownership boundary
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("action", ["stop", "respawn", "rm"])
def test_lifecycle_actions_reject_non_owned_sessions_before_any_subprocess_call(action, fake_redis, fake_client):
    response = server.app.test_client().post(
        f"/api/claude-agents/sess_external/{action}", json={}, headers=_headers()
    )

    assert response.status_code == 403
    assert fake_client.stop_calls == []
    assert fake_client.respawn_calls == []
    assert fake_client.rm_calls == []


def test_stop_succeeds_for_owned_session_and_notes_it_is_resumable(fake_redis, fake_client):
    fake_redis.owned.add("sess_owned01")

    response = server.app.test_client().post(
        "/api/claude-agents/sess_owned01/stop", json={}, headers=_headers()
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert "Respawn" in body["note"]
    assert fake_client.stop_calls == ["sess_owned01"]


def test_respawn_succeeds_for_owned_session(fake_redis, fake_client):
    fake_redis.owned.add("sess_owned01")

    response = server.app.test_client().post(
        "/api/claude-agents/sess_owned01/respawn", json={}, headers=_headers()
    )

    assert response.status_code == 200
    assert fake_client.respawn_calls == ["sess_owned01"]


def test_rm_succeeds_and_removes_ownership_and_cursor(fake_redis, fake_client):
    fake_redis.owned.add("sess_owned01")
    fake_redis.values["claude_bg:cursor:sess_owned01"] = "5"

    response = server.app.test_client().post(
        "/api/claude-agents/sess_owned01/rm", json={}, headers=_headers()
    )

    assert response.status_code == 200
    body = response.get_json()
    assert "claude --resume sess_owned01" in body["note"]
    assert "sess_owned01" not in fake_redis.owned
    assert fake_client.rm_calls == ["sess_owned01"]


def test_lifecycle_actions_reject_unsafe_id_shape(fake_redis, fake_client):
    response = server.app.test_client().post(
        "/api/claude-agents/../etc/stop", json={}, headers=_headers()
    )

    assert response.status_code in (400, 404)
    assert fake_client.stop_calls == []


# ---------------------------------------------------------------------------
# POST /api/claude-agents/<id>/steer — steering by restart
# ---------------------------------------------------------------------------


def test_steer_rejects_non_owned_before_any_subprocess_call(fake_redis, fake_client):
    response = server.app.test_client().post(
        "/api/claude-agents/sess_external/steer", json={"prompt": "adjust the plan"}, headers=_headers()
    )

    assert response.status_code == 403
    assert fake_client.steer_calls == []


def test_steer_rejects_empty_prompt_without_calling_the_cli(fake_redis, fake_client):
    fake_redis.owned.add("sess_owned01")

    response = server.app.test_client().post(
        "/api/claude-agents/sess_owned01/steer", json={"prompt": "   "}, headers=_headers()
    )

    assert response.status_code == 400
    assert fake_client.steer_calls == []


def test_steer_succeeds_and_remaps_ownership_to_the_new_id(fake_redis, fake_client):
    fake_redis.owned.add("sess_owned01")
    fake_client.steer_result = {"id": "sess_steered02", "resumed_from": "sess_owned01"}

    response = server.app.test_client().post(
        "/api/claude-agents/sess_owned01/steer", json={"prompt": "adjust the plan"}, headers=_headers()
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["id"] == "sess_steered02"
    assert body["resumed_from"] == "sess_owned01"
    assert "sess_steered02" in fake_redis.owned
    assert "sess_owned01" not in fake_redis.owned
    assert fake_client.steer_calls[0]["prompt"] == "adjust the plan"


def test_steer_keeps_ownership_when_the_id_is_unchanged(fake_redis, fake_client):
    fake_redis.owned.add("sess_owned01")
    fake_client.steer_result = {"id": "sess_owned01", "resumed_from": "sess_owned01"}

    response = server.app.test_client().post(
        "/api/claude-agents/sess_owned01/steer", json={"prompt": "again"}, headers=_headers()
    )

    assert response.status_code == 200
    assert "sess_owned01" in fake_redis.owned


def test_steer_is_idempotent_on_retry(fake_redis, fake_client):
    fake_redis.owned.add("sess_owned01")
    client = server.app.test_client()
    body = {"prompt": "keep going"}
    headers = _headers("steer-retry")

    first = client.post("/api/claude-agents/sess_owned01/steer", json=body, headers=headers)
    second = client.post("/api/claude-agents/sess_owned01/steer", json=body, headers=headers)

    assert first.get_json() == second.get_json()
    assert len(fake_client.steer_calls) == 1


# ---------------------------------------------------------------------------
# POST /api/claude-agents/daemon/stop
# ---------------------------------------------------------------------------


def test_daemon_stop_requires_explicit_keep_workers_boolean(fake_redis, fake_client):
    client = server.app.test_client()

    missing = client.post("/api/claude-agents/daemon/stop", json={}, headers=_headers("k1"))
    assert missing.status_code == 400

    not_boolean = client.post(
        "/api/claude-agents/daemon/stop", json={"keep_workers": "yes"}, headers=_headers("k2")
    )
    assert not_boolean.status_code == 400
    assert fake_client.daemon_stop_calls == []


def test_daemon_stop_passes_keep_workers_through(fake_redis, fake_client):
    response = server.app.test_client().post(
        "/api/claude-agents/daemon/stop", json={"keep_workers": False}, headers=_headers()
    )

    assert response.status_code == 200
    assert fake_client.daemon_stop_calls == [False]


# ---------------------------------------------------------------------------
# Existing surfaces are unaffected
# ---------------------------------------------------------------------------


def test_claude_bg_prefixed_ids_ride_the_existing_events_route_unmodified():
    """§1.4: ``claude_bg_<id>`` resolves to the same, unmodified ``/api/events/<cell_id>`` view."""
    adapter = server.app.url_map.bind("localhost")
    endpoint_default, args_default = adapter.match("/api/events/sess_1", method="GET")
    endpoint_claude, args_claude = adapter.match("/api/events/claude_bg_sess_1", method="GET")

    assert endpoint_default == endpoint_claude == "api_events"
    assert args_default == {"cell_id": "sess_1"}
    assert args_claude == {"cell_id": "claude_bg_sess_1"}
