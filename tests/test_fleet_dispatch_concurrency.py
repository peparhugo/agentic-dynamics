"""Step 4: bounded concurrent dispatch in the fleet command consumer.

The pre-step-4 consumer called the broker INLINE: the broker waits for the whole container run,
so the BRPOP loop could not read the next command — submit OR scale/drain/restart — until the
run ended. These tests pin the two properties that fix it:

* a control action lands WHILE a submit is still in flight (the loop is not serialised);
* saturation QUEUES (busy => queued, never dropped): with one dispatch worker, a second submit
  is recorded ``queued`` at acceptance and runs when the worker frees.
"""

from __future__ import annotations

import json
import sys
import threading
import time

from agentic_dynamics.core.paths import PROJECT_ROOT

# scripts/fleet is a dir, not a package — the consumer's own import path.
_FLEET_DIR = str(PROJECT_ROOT / "scripts" / "fleet")
if _FLEET_DIR not in sys.path:
    sys.path.insert(0, _FLEET_DIR)

import fleet_manager  # noqa: E402
import spawn_wrapper  # noqa: E402


class _FakeCommandsRedis:
    """Minimal redis stand-in covering the calls the loop + board make."""

    def __init__(self) -> None:
        self._hashes: dict[str, dict[str, str]] = {}
        self._lists: dict[str, list[str]] = {}

    def lpush(self, key: str, value: str) -> int:
        self._lists.setdefault(key, []).insert(0, value)
        return len(self._lists[key])

    def rpush(self, key: str, *values: str) -> int:
        self._lists.setdefault(key, []).extend(values)
        return len(self._lists[key])

    def llen(self, key: str) -> int:
        return len(self._lists.get(key, []))

    def brpop(self, key: str, timeout: int | None = None):
        lst = self._lists.get(key)
        if not lst:
            return None
        return key, lst.pop()

    # Wave B2 claim lane: BLMOVE (claim), LREM (release), LRANGE (recovery scan).
    def blmove(self, first: str, second: str, timeout: int | None = None,
               src: str = "LEFT", dest: str = "RIGHT"):
        lst = self._lists.get(first)
        if not lst:
            return None
        value = lst.pop(0) if src == "LEFT" else lst.pop()
        dst = self._lists.setdefault(second, [])
        if dest == "LEFT":
            dst.insert(0, value)
        else:
            dst.append(value)
        return value

    def lrem(self, key: str, count: int, value: str) -> int:
        lst = self._lists.get(key, [])
        removed = 0
        while value in lst and (count == 0 or removed < count):
            lst.remove(value)
            removed += 1
        return removed

    def lrange(self, key: str, start: int, end: int) -> list[str]:
        lst = self._lists.get(key, [])
        if end == -1:
            return list(lst[start:])
        return list(lst[start : end + 1])

    def hset(self, key: str, mapping: dict | None = None, **_kw) -> None:
        self._hashes.setdefault(key, {}).update({k: str(v) for k, v in (mapping or {}).items()})

    def hget(self, key: str, field: str) -> str | None:
        return self._hashes.get(key, {}).get(field)

    def hvals(self, key: str) -> list[str]:
        return list(self._hashes.get(key, {}).values())

    def hgetall(self, key: str) -> dict[str, str]:
        return dict(self._hashes.get(key, {}))

    def scan_iter(self, match: str | None = None, count: int | None = None):
        return iter([])


class _FakeBroker:
    """A broker whose submits BLOCK until released — the long container run, simulated."""

    def __init__(self) -> None:
        self.started: list[str] = []
        self.control: list[str] = []
        self._release: dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    def gate(self, job_id: str) -> threading.Event:
        with self._lock:
            return self._release.setdefault(job_id, threading.Event())

    def fleet_command(self, command, dry_run=False):
        action = command.get("action")
        if action == "submit":
            job_id = str(command.get("job_id"))
            with self._lock:
                self.started.append(job_id)
            self.gate(job_id).wait(timeout=10)
            return {
                "state": "OK",
                "argv": ["docker", "compose", "run", "--rm", "workflow-runner"],
                "returncode": 0,
            }
        with self._lock:
            self.control.append(str(action))
        return {"state": "OK", "argv": ["docker", "compose", action], "returncode": 0}


def _submit_command(job_id: str) -> dict:
    return {
        "action": "submit",
        "job_id": job_id,
        "spec": "workflows/repository/launch_handler_dry_run.yaml",
        "goal": "g",
        "model": "anthropic/claude-sonnet-5",
        "workdir": "/tmp/wt-x",
        "ts": 0.0,
        "nonce": "n",
    }


def _submit(r: _FakeCommandsRedis, job_id: str) -> None:
    r.lpush(spawn_wrapper.COMMANDS_KEY, json.dumps(_submit_command(job_id)))


def _scale(r: _FakeCommandsRedis) -> None:
    r.lpush(
        spawn_wrapper.COMMANDS_KEY,
        json.dumps(
            {"action": "scale", "service": "workflow-runner", "count": 2, "ts": 0.0,
             "nonce": "n2"}
        ),
    )


def _jobs(r: _FakeCommandsRedis) -> dict[str, dict]:
    return {j["job_id"]: j for j in fleet_manager.build_board(r)["jobs"]}


def _wait_until(predicate, *, timeout: float = 5.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def test_control_action_is_answered_while_a_submit_is_in_flight(monkeypatch):
    r = _FakeCommandsRedis()
    broker = _FakeBroker()
    monkeypatch.setattr(spawn_wrapper, "_broker_client", lambda: broker)
    _submit(r, "job-slow")
    _scale(r)

    consumer = threading.Thread(
        target=spawn_wrapper.consume_fleet_commands,
        kwargs={"client": r, "max_commands": 2},
        daemon=True,
    )
    consumer.start()
    try:
        assert _wait_until(lambda: broker.started == ["job-slow"]), "submit never reached broker"
        # the control action must land WHILE the submit is blocked (the loop is not serialised)
        assert _wait_until(lambda: broker.control == ["scale"]), "control blocked behind submit"
    finally:
        broker.gate("job-slow").set()
        consumer.join(timeout=10)

    assert not consumer.is_alive()
    assert _jobs(r)["job-slow"]["status"] == "completed"


def test_saturated_pool_queues_and_never_drops(monkeypatch):
    monkeypatch.setenv("FINOPS_FLEET_DISPATCH_WORKERS", "1")
    r = _FakeCommandsRedis()
    broker = _FakeBroker()
    monkeypatch.setattr(spawn_wrapper, "_broker_client", lambda: broker)
    _submit(r, "job-1")
    _submit(r, "job-2")

    consumer = threading.Thread(
        target=spawn_wrapper.consume_fleet_commands,
        kwargs={"client": r, "max_commands": 2},
        daemon=True,
    )
    consumer.start()
    try:
        assert _wait_until(lambda: broker.started == ["job-1"])
        # job-2 is ACCEPTED (queued on the board) while the single worker is busy with job-1
        assert _wait_until(lambda: _jobs(r).get("job-2", {}).get("status") == "queued"), (
            "the second submit was not accepted as queued"
        )
        assert broker.started == ["job-1"], "job-2 ran despite a saturated pool"
        broker.gate("job-1").set()
        assert _wait_until(lambda: broker.started == ["job-1", "job-2"]), (
            "the queued submit was dropped"
        )
    finally:
        broker.gate("job-1").set()
        broker.gate("job-2").set()
        consumer.join(timeout=10)

    assert not consumer.is_alive()
    jobs = _jobs(r)
    assert jobs["job-1"]["status"] == "completed"
    assert jobs["job-2"]["status"] == "completed"


# ── Wave B2: the durable claim lane + restart recovery ──────────────────────


def _seed_claim(r: _FakeCommandsRedis, command: dict, *, job_status: str) -> str:
    """The exact state a killed wrapper leaves: the raw command in the claim lane plus
    whatever the board had recorded before the death."""
    raw = json.dumps(command)
    r.rpush(spawn_wrapper.PROCESSING_KEY, raw)
    if command.get("action") == "submit":
        r.hset(
            "fleet:jobs",
            mapping={
                command["job_id"]: json.dumps(
                    {"job_id": command["job_id"], "status": job_status}
                )
            },
        )
    return raw


def test_waiting_work_is_claimable_again_after_a_restart(monkeypatch):
    """The core B2 acceptance: a submit a dead wrapper left WAITING (claimed, queued,
    never started — the in-memory pool is gone with the process) is requeued at startup
    and runs to completion."""
    r = _FakeCommandsRedis()
    broker = _FakeBroker()
    monkeypatch.setattr(spawn_wrapper, "_broker_client", lambda: broker)
    _seed_claim(r, _submit_command("job-waiting"), job_status="queued")

    spawn_wrapper.consume_fleet_commands(client=r, once=True)

    assert broker.started == ["job-waiting"]
    assert _jobs(r)["job-waiting"]["status"] == "completed"
    assert r.llen(spawn_wrapper.PROCESSING_KEY) == 0
    assert r.llen(spawn_wrapper.COMMANDS_KEY) == 0


def test_a_submit_caught_mid_dispatch_resolves_failed_not_a_ghost(monkeypatch):
    """A submit whose board row says 'running' when the wrapper died cannot be safely
    re-run (the container may still be alive host-side): it resolves to an honest terminal
    failure on the board + the DLQ — never a forever-running ghost — and its claim is
    released."""
    r = _FakeCommandsRedis()
    broker = _FakeBroker()
    monkeypatch.setattr(spawn_wrapper, "_broker_client", lambda: broker)
    _seed_claim(r, _submit_command("job-caught"), job_status="running")

    spawn_wrapper.consume_fleet_commands(client=r, once=True)

    assert broker.started == []  # never re-dispatched
    job = _jobs(r)["job-caught"]
    assert job["status"] == "failed"
    assert "restarted mid-dispatch" in job["error"]
    assert r.llen(spawn_wrapper.PROCESSING_KEY) == 0
    dead = [json.loads(e) for e in r._lists.get("fleet_jobs:dead_letter", [])]
    assert any("restarted mid-dispatch" in entry.get("reason", "") for entry in dead)


def test_recovery_requeues_a_control_request_for_replay(monkeypatch):
    """Control actions are REQUESTS: a claim interrupted mid-action is replayed, never
    dropped (a shaping scale/drain/restart is safe to repeat)."""
    r = _FakeCommandsRedis()
    broker = _FakeBroker()
    monkeypatch.setattr(spawn_wrapper, "_broker_client", lambda: broker)
    r.rpush(
        spawn_wrapper.PROCESSING_KEY,
        json.dumps({"action": "scale", "service": "workflow-runner", "count": 2,
                    "ts": 0.0, "nonce": "n2"}),
    )

    spawn_wrapper.consume_fleet_commands(client=r, once=True)

    assert broker.control == ["scale"]  # replayed after the restart
    assert r.llen(spawn_wrapper.PROCESSING_KEY) == 0


def test_a_pool_queued_submit_waits_in_the_durable_claim_lane(monkeypatch):
    """Busy means queued — and the queued work is in the CLAIM LANE, not only the in-memory
    pool: while job-2 waits behind a saturated worker it is already durable, so a restart
    at that instant requeues it rather than losing it."""
    monkeypatch.setenv("FINOPS_FLEET_DISPATCH_WORKERS", "1")
    r = _FakeCommandsRedis()
    broker = _FakeBroker()
    monkeypatch.setattr(spawn_wrapper, "_broker_client", lambda: broker)
    _submit(r, "job-1")
    _submit(r, "job-2")

    consumer = threading.Thread(
        target=spawn_wrapper.consume_fleet_commands,
        kwargs={"client": r, "max_commands": 2},
        daemon=True,
    )
    consumer.start()
    try:
        assert _wait_until(lambda: broker.started == ["job-1"])
        assert _wait_until(lambda: _jobs(r).get("job-2", {}).get("status") == "queued")
        # BOTH raw commands are in the durable claim lane: job-1 dispatching, job-2 waiting.
        lane = r._lists.get(spawn_wrapper.PROCESSING_KEY, [])
        ids = sorted(json.loads(raw).get("job_id") for raw in lane)
        assert ids == ["job-1", "job-2"], f"claim lane missing waiting work: {ids}"
        broker.gate("job-1").set()
        assert _wait_until(lambda: broker.started == ["job-1", "job-2"])
    finally:
        broker.gate("job-1").set()
        broker.gate("job-2").set()
        consumer.join(timeout=10)

    assert r.llen(spawn_wrapper.PROCESSING_KEY) == 0  # released on terminal
