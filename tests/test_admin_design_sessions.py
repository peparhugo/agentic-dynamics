"""Backend contracts for portal-owned live design sessions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from admin import design_sessions, opencode_client, server
from admin.design_sessions import DESIGN_SESSIONS_KEY, DesignSessionManager
from admin.opencode_client import OpenCodeClient


class FakeRedis:
    """In-memory subset of Redis used by design metadata and event publishing."""

    def __init__(self) -> None:
        self.hashes: dict[str, dict[str, str]] = {}
        self.lists: dict[str, list[str]] = {}
        self.values: dict[str, str] = {}
        self.published: list[tuple[str, str]] = []

    def hgetall(self, name):
        return dict(self.hashes.get(name, {}))

    def hget(self, name, key):
        return self.hashes.get(name, {}).get(key)

    def hset(self, name, key, value):
        self.hashes.setdefault(name, {})[key] = value

    def lpush(self, name, value):
        self.lists.setdefault(name, []).insert(0, value)

    def ltrim(self, name, start, end):
        self.lists[name] = self.lists.get(name, [])[start:end + 1]

    def publish(self, channel, value):
        self.published.append((channel, value))

    def get(self, name):
        return self.values.get(name)

    def set(self, name, value, *, nx=False, ex=None):
        assert ex is not None
        if nx and name in self.values:
            return False
        self.values[name] = value
        return True


class FakeOpenCode:
    """Record native session calls and provide deterministic relay events."""

    def __init__(self) -> None:
        self.created: list[dict] = []
        self.inputs: list[dict] = []
        self.interrupts: list[str] = []
        self.event_requests: list[tuple[str, str | None]] = []
        self.events: list[dict] = []

    def create_session(self, *, location, model):
        self.created.append({"location": location, "model": model})
        return {"data": {"id": "ses_native_1"}}

    def send_input(self, session_id, prompt, *, delivery):
        self.inputs.append({"session_id": session_id, "prompt": prompt, "delivery": delivery})
        return {"admitted": True}

    def interrupt(self, session_id):
        self.interrupts.append(session_id)
        return {"interrupted": True}

    def iter_events(self, session_id, *, after=None):
        self.event_requests.append((session_id, after))
        yield from self.events


def _manager(tmp_path: Path):
    """Create an isolated manager with no daemon threads."""
    redis = FakeRedis()
    opencode = FakeOpenCode()
    manager = DesignSessionManager(
        root=tmp_path,
        redis_factory=lambda: redis,
        opencode=opencode,
        workdirs={"repository": tmp_path},
        start_relays=False,
    )
    return manager, redis, opencode


def _valid_spec(kind="agent_task", levels="[sol, terra]"):
    """Return a compact spec accepted by the repository's real validator."""
    return f"""name: live-design
question: Does this design work?
version: '1'
workflow:
  kind: {kind}
  params:
    phases:
      - {{name: implement, kind: agent, prompt: Build it}}
factors:
  - name: model
    levels: {levels}
  - name: condition
    levels: [clean, degraded]
design: factorial
rules:
  - {{name: quality_measure, plane: measurement, evidence_class: '[M]', produces: [quality]}}
metrics:
  - {{name: quality, agg: mean, over: cell}}
comparison: {{kind: effect_size, arm_factor: model, loss: {{quality: -1.0}}}}
adapt: {{strategy: manual, selection: highest_regret}}
"""


def _created(manager, kind="workflow"):
    """Create one persisted portal-owned fixture and return its summary."""
    return manager.create(
        kind=kind,
        intent="Design a controlled workflow",
        model="openai/gpt-5.6-sol",
        workdir_key="repository",
    )


def test_create_and_list_bind_native_session_to_assigned_draft(tmp_path):
    """Creation uses native v2 semantics and persists only portal ownership."""
    manager, redis, opencode = _manager(tmp_path)

    created = _created(manager)
    listed = manager.list_sessions()

    assert created["portal_id"].startswith("ds_")
    assert created["opencode_session_id"] == "ses_native_1"
    assert opencode.created == [{"location": str(tmp_path), "model": "openai/gpt-5.6-sol"}]
    initial = opencode.inputs[0]
    assert initial["delivery"] == "queue"
    assert "workflow.kind: agent_task" in initial["prompt"]
    private = json.loads(redis.hashes[DESIGN_SESSIONS_KEY][created["portal_id"]])
    assert private["draft_path"] in initial["prompt"]
    assert private["draft_path"].endswith(f"{created['portal_id']}.yaml")
    assert listed["sessions"] == [created]
    assert "draft_path" not in listed["sessions"][0]
    assert listed["workdirs"] == [{"key": "repository", "label": tmp_path.name}]


def test_relay_resumes_after_sequence_and_bounds_retained_log(tmp_path):
    """A reconnect suppresses its boundary event and advances durable sequence."""
    manager, redis, opencode = _manager(tmp_path)
    created = _created(manager)
    private = json.loads(redis.hashes[DESIGN_SESSIONS_KEY][created["portal_id"]])
    private["last_sequence"] = "4"
    redis.hset(DESIGN_SESSIONS_KEY, created["portal_id"], json.dumps(private))
    opencode.events = [
        {"sequence": 4, "type": "message.part.updated", "properties": {"part": {"type": "text", "text": "duplicate"}}},
        {"sequence": 5, "type": "message.part.updated", "properties": {"part": {"type": "reasoning", "text": "new"}}},
    ]

    assert manager._relay_once(created["portal_id"]) == 1

    assert opencode.event_requests == [("ses_native_1", "4")]
    event = json.loads(redis.lists[f"events_log:{created['portal_id']}"][0])
    assert event == {"type": "reasoning", "part": {"type": "reasoning", "text": "new"}, "sessionID": "ses_native_1"}
    stored = json.loads(redis.hashes[DESIGN_SESSIONS_KEY][created["portal_id"]])
    assert stored["last_sequence"] == "5"
    for index in range(600):
        manager._publish(stored, {"type": "text", "part": {"text": str(index)}})
    assert len(redis.lists[f"events_log:{created['portal_id']}"]) == 500


@pytest.mark.parametrize(
    ("content", "expected_state"),
    [
        ("name: [unterminated", "invalid_yaml"),
        ("name: incomplete", "construction_error"),
        (_valid_spec(levels="[]"), "validation_errors"),
    ],
)
def test_draft_state_distinguishes_parser_construction_and_validator_errors(tmp_path, content, expected_state):
    """Distinct artifact failures remain actionable and never enable Save."""
    manager, redis, _opencode = _manager(tmp_path)
    created = _created(manager)
    private = json.loads(redis.hashes[DESIGN_SESSIONS_KEY][created["portal_id"]])
    Path(private["draft_path"]).write_text(content)

    state = manager.draft_state(created["portal_id"])

    assert state["draft_state"] == expected_state
    assert state["validation"]["valid"] is False
    assert state["validation"]["errors"]
    assert state["capabilities"]["save"] is False


def test_experiment_draft_calls_validator_before_matrix_preview(monkeypatch, tmp_path):
    """The real validator gate runs before the compiler's matrix expansion."""
    manager, redis, _opencode = _manager(tmp_path)
    created = _created(manager, kind="experiment")
    private = json.loads(redis.hashes[DESIGN_SESSIONS_KEY][created["portal_id"]])
    Path(private["draft_path"]).write_text(_valid_spec(kind="task"))
    calls: list[str] = []
    real_validate = design_sessions.validate_spec
    real_matrix = design_sessions.experiment_matrix

    def tracked_validate(spec):
        calls.append("validate")
        return real_validate(spec)

    def tracked_matrix(spec):
        calls.append("matrix")
        return real_matrix(spec)

    monkeypatch.setattr(design_sessions, "validate_spec", tracked_validate)
    monkeypatch.setattr(design_sessions, "experiment_matrix", tracked_matrix)

    state = manager.draft_state(created["portal_id"])

    assert calls == ["validate", "matrix"]
    assert state["draft_state"] == "valid"
    assert state["matrix"]["count"] == 4
    assert [cell["cell_id"] for cell in state["matrix"]["preview"]] == [
        "live_design_model_sol_condition_clean",
        "live_design_model_sol_condition_degraded",
        "live_design_model_terra_condition_clean",
        "live_design_model_terra_condition_degraded",
    ]
    assert state["capabilities"] == {
        "save": True,
        "run": False,
        "enqueue": False,
        "reason": "Validated; enqueue unavailable (no generic dispatcher)",
    }


def test_matrix_cardinality_is_bounded_before_expansion(monkeypatch, tmp_path):
    """A compact combinatorial draft cannot make Flask materialize every cell."""
    manager, redis, _opencode = _manager(tmp_path)
    created = _created(manager, kind="experiment")
    private = json.loads(redis.hashes[DESIGN_SESSIONS_KEY][created["portal_id"]])
    levels = ", ".join(f"v{index}" for index in range(101))
    content = _valid_spec(kind="task", levels=f"[{levels}]").replace(
        "levels: [clean, degraded]",
        f"levels: [{levels}]",
    )
    Path(private["draft_path"]).write_text(content)
    monkeypatch.setattr(
        design_sessions,
        "experiment_matrix",
        lambda _spec: pytest.fail("unbounded matrix expansion was called"),
    )

    state = manager.draft_state(created["portal_id"])

    assert state["validation"]["valid"] is True
    assert state["matrix"] == {"count": 10201, "preview": [], "truncated": True}
    assert "above the 10000-cell preview cap" in state["capabilities"]["reason"]


def test_draft_reader_rejects_symlinks_and_oversized_files(tmp_path):
    """Agent-controlled paths cannot escape the assigned regular-file boundary."""
    manager, redis, _opencode = _manager(tmp_path)
    created = _created(manager)
    private = json.loads(redis.hashes[DESIGN_SESSIONS_KEY][created["portal_id"]])
    draft = Path(private["draft_path"])
    outside = tmp_path / "outside.yaml"
    outside.write_text(_valid_spec())
    draft.symlink_to(outside)

    linked = manager.draft_state(created["portal_id"])
    assert linked["draft_state"] == "unavailable"
    assert "symlink" in linked["validation"]["errors"][0]

    draft.unlink()
    draft.write_bytes(b"x" * (design_sessions.MAX_DRAFT_BYTES + 1))
    oversized = manager.draft_state(created["portal_id"])
    assert oversized["draft_state"] == "invalid_yaml"
    assert "byte limit" in oversized["validation"]["errors"][0]


def test_safe_atomic_save_requires_overwrite_and_preserves_exact_content(tmp_path):
    """Saving rejects traversal and never silently replaces an existing spec."""
    manager, redis, _opencode = _manager(tmp_path)
    created = _created(manager)
    private = json.loads(redis.hashes[DESIGN_SESSIONS_KEY][created["portal_id"]])
    content = _valid_spec()
    Path(private["draft_path"]).write_text(content)

    with pytest.raises(ValueError, match="safe"):
        manager.save(created["portal_id"], filename="../escape.yaml", overwrite=False)
    first = manager.save(created["portal_id"], filename="workflow.yaml", overwrite=False)
    assert first["ok"] is True
    assert first["content"] == content
    destination = tmp_path / "experiments" / "specs" / "workflow.yaml"
    assert destination.read_text() == content
    destination.write_text("existing")
    conflict = manager.save(created["portal_id"], filename="workflow.yaml", overwrite=False)
    assert conflict["conflict"] is True
    assert destination.read_text() == "existing"
    replaced = manager.save(created["portal_id"], filename="workflow.yaml", overwrite=True)
    assert replaced["ok"] is True
    assert destination.read_text() == content


def test_run_revalidates_saved_bytes_and_builds_explicit_cli(monkeypatch, tmp_path):
    """Workflow launch uses the existing runner and a separate stream identity."""
    manager, redis, _opencode = _manager(tmp_path)
    created = _created(manager)
    private = json.loads(redis.hashes[DESIGN_SESSIONS_KEY][created["portal_id"]])
    Path(private["draft_path"]).write_text(_valid_spec())
    manager.save(created["portal_id"], filename="workflow.yaml", overwrite=False)
    captured = {}

    class FakeThread:
        def __init__(self, *, target, args, daemon, name):
            captured.update(target=target, args=args, daemon=daemon, name=name)

        def start(self):
            captured["started"] = True

    monkeypatch.setattr(design_sessions.threading, "Thread", FakeThread)

    result = manager.run_workflow(
        created["portal_id"],
        goal="Implement export",
        model="openai/gpt-5.6-sol",
        workdir_key="repository",
        timeout=900,
        commit=False,
        backend="opencode",
        thinking_budget_tokens=1200,
        output_token_limit=3000,
    )

    command = captured["args"][1]
    assert captured["started"] is True
    assert result["execution_id"].startswith("workflow_")
    assert command[:2] == [design_sessions.sys.executable, "scripts/run_workflow.py"]
    for pair in (
        ["--spec", "experiments/specs/workflow.yaml"],
        ["--goal", "Implement export"],
        ["--model", "openai/gpt-5.6-sol"],
        ["--timeout", "900"],
        ["--backend", "opencode"],
        ["--thinking-budget-tokens", "1200"],
        ["--output-token-limit", "3000"],
    ):
        position = command.index(pair[0])
        assert command[position:position + 2] == pair
    assert "--no-commit" in command
    assert redis.hashes["story_status"][result["execution_id"]] == "queued"

    (tmp_path / "experiments" / "specs" / "workflow.yaml").write_text(_valid_spec().replace("live-design", "changed"))
    with pytest.raises(ValueError, match="changed after Save"):
        manager.run_workflow(
            created["portal_id"],
            goal="Again",
            model="openai/gpt-5.6-sol",
            workdir_key="repository",
            timeout=900,
            commit=True,
        )


def test_native_interrupt_accepts_documented_empty_success(monkeypatch):
    """OpenCode's successful 204 interrupt response does not require JSON."""
    requests = []

    class EmptyResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, *_args):
            return b""

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return EmptyResponse()

    monkeypatch.setattr(opencode_client, "urlopen", fake_urlopen)

    result = OpenCodeClient("http://127.0.0.1:4096").interrupt("ses/native")

    assert result == {}
    assert requests[0][0].full_url.endswith("/api/session/ses%2Fnative/interrupt")
    assert requests[0][0].method == "POST"


def test_native_sse_parser_preserves_id_and_after_sequence(monkeypatch):
    """The native durable stream uses SSE framing rather than WebSockets."""
    requests = []

    class Headers:
        def get_content_type(self):
            return "text/event-stream"

    class StreamResponse:
        headers = Headers()

        def __iter__(self):
            return iter([
                b": heartbeat\n",
                b"id: 9\n",
                b'data: {"type":"text","part":{"text":"hello"}}\n',
                b"\n",
            ])

        def close(self):
            self.closed = True

    response = StreamResponse()

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return response

    monkeypatch.setattr(opencode_client, "urlopen", fake_urlopen)

    events = list(OpenCodeClient("http://127.0.0.1:4096").iter_events("ses/native", after="8"))

    assert events == [{"type": "text", "part": {"text": "hello"}, "_sse_id": "9"}]
    assert requests[0][0].full_url.endswith("/api/session/ses%2Fnative/event?after=8")
    assert requests[0][0].headers["Accept"] == "text/event-stream"
    assert response.closed is True


class StubManager:
    """Route-level manager recording validated request bodies."""

    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return {"portal_id": "ds_route", "kind": kwargs["kind"]}


def test_mutating_routes_require_loopback_same_origin_json_and_idempotency(monkeypatch):
    """Unauthenticated spend and file mutations enforce the documented boundary."""
    manager = StubManager()
    redis = FakeRedis()
    monkeypatch.setattr(server, "_design_sessions", lambda: manager)
    monkeypatch.setattr(server, "_redis", lambda: redis)
    client = server.app.test_client()
    body = {"kind": "workflow", "intent": "Build export", "model": "model/id", "workdir": "repository"}

    assert client.post("/api/design-sessions", data="x").status_code == 415
    assert client.post("/api/design-sessions", json=body).status_code == 400
    headers = {"Idempotency-Key": "route-1"}
    assert client.post("/api/design-sessions", json=body, headers={**headers, "Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/design-sessions", json=body, headers=headers, environ_base={"REMOTE_ADDR": "10.0.0.4"}).status_code == 403

    response = client.post("/api/design-sessions", json=body, headers=headers)

    assert response.status_code == 201
    assert response.get_json()["session"]["portal_id"] == "ds_route"
    assert manager.calls == [{
        "kind": "workflow",
        "intent": "Build export",
        "model": "model/id",
        "workdir_key": "repository",
    }]

    replay = client.post("/api/design-sessions", json=body, headers=headers)
    assert replay.status_code == 201
    assert replay.get_json() == response.get_json()
    assert len(manager.calls) == 1

    changed = {**body, "intent": "Different work"}
    collision = client.post("/api/design-sessions", json=changed, headers=headers)
    assert collision.status_code == 409
