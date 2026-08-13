"""Tests for rate limiting, message-history queries and message expiry."""

import asyncio
import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import pytest
import websockets

import app

WS_URL = "ws://127.0.0.1"


@pytest.fixture
async def server():
    srv = await app.make_server()
    try:
        yield srv
    finally:
        await app.close_server(srv)


async def connect(port):
    return await websockets.connect(f"{WS_URL}:{port}")


async def recv_json(ws, timeout=5):
    raw = await asyncio.wait_for(ws.recv(), timeout)
    return json.loads(raw)


async def get_client_id(ws):
    msg = await recv_json(ws)
    assert msg["type"] == "system"
    return msg["payload"]["client_id"]


def http_get(port, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as resp:
        return resp.status, json.loads(resp.read().decode())


async def subscribe(ws, channel):
    await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": channel}}))
    await recv_json(ws)


# ── RATE_LIMIT configuration ─────────────────────────────────────

def test_resolve_rate_limit_default():
    assert app.resolve_rate_limit() == app.RATE_LIMIT_DEFAULT == 100


def test_resolve_rate_limit_from_env(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "50")
    assert app.resolve_rate_limit() == 50
    monkeypatch.setenv("RATE_LIMIT", "not-a-number")
    assert app.resolve_rate_limit() == 100
    monkeypatch.delenv("RATE_LIMIT")
    assert app.resolve_rate_limit() == 100
    assert app.resolve_rate_limit(25) == 25
    assert app.resolve_rate_limit("junk") == 100


# ── RateLimiter unit behaviour ───────────────────────────────────

def test_rate_limiter_allows_up_to_limit():
    limiter = app.RateLimiter(limit=3)
    try:
        assert limiter.enabled is True
        assert limiter.limit == 3
        assert limiter.allow("client-a") == (True, 2)
        assert limiter.allow("client-a") == (True, 1)
        assert limiter.allow("client-a") == (True, 0)
        assert limiter.allow("client-a") == (False, 0)
        assert limiter.allow("client-a") == (False, 0)
    finally:
        limiter.close()


def test_rate_limiter_counters_are_per_client():
    limiter = app.RateLimiter(limit=2)
    try:
        assert limiter.allow("client-a") == (True, 1)
        assert limiter.allow("client-a") == (True, 0)
        assert limiter.allow("client-a") == (False, 0)
        # a different client has its own budget
        assert limiter.allow("client-b") == (True, 1)
        assert limiter.allow("client-b") == (True, 0)
    finally:
        limiter.close()


def test_rate_limiter_reset_clears_counters():
    limiter = app.RateLimiter(limit=2)
    try:
        limiter.allow("c1")
        limiter.allow("c1")
        assert limiter.allow("c1") == (False, 0)
        limiter.reset("c1")
        assert limiter.allow("c1") == (True, 1)
    finally:
        limiter.close()


def test_rate_limiter_disabled_when_non_positive():
    limiter = app.RateLimiter(limit=0)
    try:
        assert limiter.enabled is False
        assert limiter.allow("c1") == (True, None)
    finally:
        limiter.close()
    limiter2 = app.RateLimiter(limit=-5)
    try:
        assert limiter2.enabled is False
        assert limiter2.allow("c2") == (True, None)
    finally:
        limiter2.close()


# ── Rate limiting over the wire ──────────────────────────────────

async def test_rate_limit_exceeded_returns_error_without_drop(tmp_path):
    srv = await app.make_server(rate_limit=3, db_path=str(tmp_path / "rl.db"))
    try:
        ws = await connect(srv["ws_port"])
        await get_client_id(ws)

        for n in range(3):
            await ws.send(json.dumps({"type": "broadcast", "payload": {"n": n}}))
            msg = await recv_json(ws)
            assert msg["type"] == "broadcast"

        await ws.send(json.dumps({"type": "broadcast", "payload": {"n": 3}}))
        msg = await recv_json(ws)
        assert msg["type"] == "system"
        assert "rate limit exceeded" in msg["payload"]["error"]
        assert msg["payload"]["limit"] == 3

        # Connection is not dropped: the next message also gets an error
        # instead of being delivered.
        await ws.send(json.dumps({"type": "broadcast", "payload": {"n": 4}}))
        msg = await recv_json(ws)
        assert msg["type"] == "system"
        assert "rate limit exceeded" in msg["payload"]["error"]
        assert srv["registry"].count == 1

        await ws.close()
    finally:
        await app.close_server(srv)


async def test_rate_limit_is_per_client_over_wire(tmp_path):
    srv = await app.make_server(rate_limit=2, db_path=str(tmp_path / "rl2.db"))
    try:
        ws_a = await connect(srv["ws_port"])
        ws_b = await connect(srv["ws_port"])
        await get_client_id(ws_a)
        await get_client_id(ws_b)

        for _ in range(2):
            await ws_a.send(json.dumps({"type": "broadcast", "payload": {}}))
            await recv_json(ws_a)

        await ws_a.send(json.dumps({"type": "broadcast", "payload": {}}))
        assert "rate limit exceeded" in (await recv_json(ws_a))["payload"]["error"]

        # Client b is unaffected by client a's budget.
        await ws_b.send(json.dumps({"type": "broadcast", "payload": {"n": 1}}))
        assert (await recv_json(ws_b))["type"] == "broadcast"

        await ws_a.close()
        await ws_b.close()
    finally:
        await app.close_server(srv)


def test_rate_limiter_available_on_server():
    limiter = app.RateLimiter(limit=5)
    limiter.connect()
    try:
        # Degrades gracefully to an in-process counter when Redis is down,
        # and uses Redis counters when it is up.
        allowed, _ = limiter.allow("probe")
        assert allowed is True
    finally:
        limiter.close()


# ── MESSAGE_TTL_DAYS configuration ───────────────────────────────

def test_resolve_ttl_days_default():
    assert app.resolve_ttl_days() == app.MESSAGE_TTL_DAYS_DEFAULT == 7


def test_resolve_ttl_days_from_env(monkeypatch):
    monkeypatch.setenv("MESSAGE_TTL_DAYS", "3")
    assert app.resolve_ttl_days() == 3
    monkeypatch.setenv("MESSAGE_TTL_DAYS", "junk")
    assert app.resolve_ttl_days() == 7
    monkeypatch.delenv("MESSAGE_TTL_DAYS")
    assert app.resolve_ttl_days() == 7
    assert app.resolve_ttl_days(14) == 14
    assert app.resolve_ttl_days(0) == 0


# ── Message expiry ───────────────────────────────────────────────

def test_delete_older_than_removes_expired_messages(tmp_path):
    store = app.MessageStore(str(tmp_path / "ttl.db"))
    try:
        now = datetime.now(timezone.utc)
        old = (now - timedelta(days=10)).isoformat()
        recent = (now - timedelta(days=1)).isoformat()
        store.record({"type": "broadcast", "payload": {"n": 1}, "timestamp": old})
        store.record({"type": "broadcast", "payload": {"n": 2}, "timestamp": recent})
        assert store.count() == 2

        deleted = store.delete_older_than(7)
        assert deleted == 1
        remaining = store.list_messages()
        assert len(remaining) == 1
        assert remaining[0]["payload"] == {"n": 2}
    finally:
        store.close()


def test_delete_older_than_disabled_for_non_positive(tmp_path):
    store = app.MessageStore(str(tmp_path / "ttl_disabled.db"))
    try:
        old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        store.record({"type": "broadcast", "payload": {"n": 1}, "timestamp": old})
        assert store.delete_older_than(0) == 0
        assert store.count() == 1
        assert store.delete_older_than(-1) == 0
        assert store.count() == 1
    finally:
        store.close()


async def test_ttl_cleanup_runs_at_startup(tmp_path):
    db = str(tmp_path / "ttl_startup.db")
    store = app.MessageStore(db)
    now = datetime.now(timezone.utc)
    store.record(
        {"type": "broadcast", "payload": {"n": 1}, "timestamp": (now - timedelta(days=10)).isoformat()}
    )
    store.record(
        {"type": "broadcast", "payload": {"n": 2}, "timestamp": (now - timedelta(days=1)).isoformat()}
    )
    store.close()

    srv = await app.make_server(db_path=db, message_ttl_days=7)
    try:
        assert srv["ttl_task"] is not None
        assert srv["store"].count() == 1
        remaining = srv["store"].list_messages()
        assert remaining[0]["payload"] == {"n": 2}
    finally:
        await app.close_server(srv)


async def test_ttl_cleanup_skipped_when_disabled(tmp_path):
    db = str(tmp_path / "ttl_off.db")
    store = app.MessageStore(db)
    store.record(
        {
            "type": "broadcast",
            "payload": {"n": 1},
            "timestamp": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
        }
    )
    store.close()

    srv = await app.make_server(db_path=db, message_ttl_days=0)
    try:
        assert srv["ttl_task"] is None
        assert srv["store"].count() == 1
    finally:
        await app.close_server(srv)


# ── Message history queries ──────────────────────────────────────

def test_history_chronological_and_filtered(tmp_path):
    store = app.MessageStore(str(tmp_path / "history.db"))
    try:
        now = datetime.now(timezone.utc)
        t0 = (now - timedelta(days=2)).isoformat()
        t1 = (now - timedelta(days=1)).isoformat()
        t2 = now.isoformat()
        store.record({"type": "broadcast", "payload": {"n": 1}, "timestamp": t0}, channel="alerts")
        store.record({"type": "broadcast", "payload": {"n": 2}, "timestamp": t1}, channel="alerts")
        store.record({"type": "broadcast", "payload": {"n": 3}, "timestamp": t2}, channel="chat")
        store.record({"type": "broadcast", "payload": {"n": 4}, "timestamp": t2}, channel="alerts")

        messages, has_more = store.list_history(channel="alerts")
        assert [m["payload"]["n"] for m in messages] == [1, 2, 4]
        assert has_more is False

        messages, has_more = store.list_history(since=t1)
        assert [m["payload"]["n"] for m in messages] == [2, 3, 4]
        assert has_more is False

        messages, has_more = store.list_history(channel="alerts", since=t1)
        assert [m["payload"]["n"] for m in messages] == [2, 4]
        assert has_more is False
    finally:
        store.close()


def test_history_since_accepts_z_suffix_and_offsets(tmp_path):
    store = app.MessageStore(str(tmp_path / "history_z.db"))
    try:
        t0 = "2026-01-01T00:00:00.000000+00:00"
        t1 = "2026-01-02T00:00:00.000000+00:00"
        t2 = "2026-01-03T00:00:00.000000+00:00"
        store.record({"type": "broadcast", "payload": {"n": 1}, "timestamp": t0})
        store.record({"type": "broadcast", "payload": {"n": 2}, "timestamp": t1})
        store.record({"type": "broadcast", "payload": {"n": 3}, "timestamp": t2})

        messages, _ = store.list_history(since="2026-01-02T00:00:00Z")
        assert [m["payload"]["n"] for m in messages] == [2, 3]

        messages, _ = store.list_history(since="2026-01-02T00:00:00+00:00")
        assert [m["payload"]["n"] for m in messages] == [2, 3]
    finally:
        store.close()


def test_history_pagination_has_more(tmp_path):
    store = app.MessageStore(str(tmp_path / "history_pages.db"))
    try:
        now = datetime.now(timezone.utc)
        for n in range(1, 6):
            store.record(
                {"type": "broadcast", "payload": {"n": n}, "timestamp": now.isoformat()},
                channel="alerts",
            )

        messages, has_more = store.list_history(channel="alerts", limit=2, offset=0)
        assert [m["payload"]["n"] for m in messages] == [1, 2]
        assert has_more is True

        messages, has_more = store.list_history(channel="alerts", limit=2, offset=2)
        assert [m["payload"]["n"] for m in messages] == [3, 4]
        assert has_more is True

        messages, has_more = store.list_history(channel="alerts", limit=2, offset=4)
        assert [m["payload"]["n"] for m in messages] == [5]
        assert has_more is False

        messages, has_more = store.list_history(channel="nope")
        assert messages == []
        assert has_more is False
    finally:
        store.close()


async def test_history_endpoint_channel_since_and_pagination(tmp_path):
    srv = await app.make_server(db_path=str(tmp_path / "history_http.db"))
    try:
        now = datetime.now(timezone.utc)
        t0 = (now - timedelta(days=2)).isoformat()
        t1 = (now - timedelta(days=1)).isoformat()
        t2 = now.isoformat()
        store = srv["store"]
        store.record({"type": "broadcast", "payload": {"n": 1}, "timestamp": t0}, channel="alerts")
        store.record({"type": "broadcast", "payload": {"n": 2}, "timestamp": t1}, channel="alerts")
        store.record({"type": "broadcast", "payload": {"n": 3}, "timestamp": t2}, channel="chat")

        status, body = http_get(
            srv["http_port"], "/history?channel=alerts&limit=10"
        )
        assert status == 200
        assert body["channel"] == "alerts"
        assert body["has_more"] is False
        assert [m["payload"]["n"] for m in body["messages"]] == [1, 2]

        status, body = http_get(
            srv["http_port"],
            "/history?channel=alerts&since=" + urllib.parse.quote(t1),
        )
        assert status == 200
        assert body["has_more"] is False
        assert [m["payload"]["n"] for m in body["messages"]] == [2]

        status, body = http_get(
            srv["http_port"], "/history?channel=alerts&limit=1&offset=0"
        )
        assert status == 200
        assert [m["payload"]["n"] for m in body["messages"]] == [1]
        assert body["has_more"] is True

        status, body = http_get(
            srv["http_port"], "/history?channel=alerts&limit=1&offset=1"
        )
        assert status == 200
        assert [m["payload"]["n"] for m in body["messages"]] == [2]
        assert body["has_more"] is False
    finally:
        await app.close_server(srv)


async def test_history_endpoint_messages_chronological_over_wire(tmp_path):
    srv = await app.make_server(db_path=str(tmp_path / "history_wire.db"))
    try:
        ws = await connect(srv["ws_port"])
        await get_client_id(ws)
        await subscribe(ws, "alerts")

        for n in range(1, 4):
            await ws.send(
                json.dumps({"type": "broadcast", "payload": {"n": n}, "channel": "alerts"})
            )
            await recv_json(ws)

        status, body = http_get(srv["http_port"], "/history?channel=alerts&limit=10")
        assert status == 200
        payloads = [m["payload"]["n"] for m in body["messages"]]
        assert payloads == [1, 2, 3]
        timestamps = [m["timestamp"] for m in body["messages"]]
        assert timestamps == sorted(timestamps)

        await ws.close()
    finally:
        await app.close_server(srv)
