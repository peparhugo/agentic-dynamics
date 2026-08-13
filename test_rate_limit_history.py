"""Tests for rate limiting, history queries and message expiry."""

import asyncio
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import pytest
from websockets.asyncio.client import connect

from message_store import MessageStore
from notification_server import NotificationApp
from redis_backend import RedisBackend

REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6399/0")


@pytest.fixture
async def backend():
    instance = RedisBackend(REDIS_URL, namespace=f"notify_rl_{uuid.uuid4().hex}")
    await instance.connect()
    try:
        yield instance
    finally:
        await instance.flush()
        await instance.close()


@pytest.fixture
async def store(tmp_path):
    instance = MessageStore(str(tmp_path / "history.db"))
    await instance.connect()
    try:
        yield instance
    finally:
        await instance.close()


@pytest.fixture
async def hist_app(store):
    app = NotificationApp(store=store)
    await app.start()
    try:
        yield app
    finally:
        await app.stop()


async def connect_client(app):
    """Open a websocket client and consume its connect notice."""
    ws = await connect(app.url)
    notice = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
    assert notice["type"] == "system"
    assert notice["payload"]["event"] == "connect"
    return ws, notice["payload"]["client_id"]


async def http_get(app, path="/health"):
    """Issue a plain HTTP GET request to the server."""
    reader, writer = await asyncio.open_connection(app.host, app.port)
    writer.write(
        f"GET {path} HTTP/1.1\r\nHost: {app.host}\r\nConnection: close\r\n\r\n".encode()
    )
    await writer.drain()
    data = await reader.read()
    writer.close()
    await writer.wait_closed()
    raw = data.decode("utf-8", "replace")
    head, _, body = raw.partition("\r\n\r\n")
    status = int(head.split(" ")[1])
    return status, body


async def wait_until(cond, timeout=3.0):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        result = cond()
        if asyncio.iscoroutine(result):
            result = await result
        if result:
            return True
        await asyncio.sleep(0.02)
    return False


def iso_at(offset_seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)).isoformat()


# ── Rate limiting ─────────────────────────────────────────────────────────


async def test_rate_limit_exceeded_returns_error(backend):
    app = NotificationApp(backend=backend, rate_limit=3)
    await app.start()
    ws, _ = await connect_client(app)
    try:
        for i in range(3):
            await ws.send(json.dumps({"type": "broadcast", "payload": {"i": i}}))
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            assert msg["type"] == "broadcast"
            assert msg["payload"] == {"i": i}

        await ws.send(json.dumps({"type": "broadcast", "payload": {"over": True}}))
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        assert msg["type"] == "system"
        assert msg["payload"]["event"] == "error"
        assert "rate limit" in msg["payload"]["message"]

        # Connection is NOT dropped: the client still receives later broadcasts.
        ws_other, _ = await connect_client(app)
        try:
            await ws_other.send(
                json.dumps({"type": "broadcast", "payload": {"from": "other"}})
            )
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            assert msg["type"] == "broadcast"
            assert msg["payload"] == {"from": "other"}
        finally:
            await ws_other.close()
    finally:
        await ws.close()
        await app.stop()


async def test_rate_limit_is_per_client(backend):
    app = NotificationApp(backend=backend, rate_limit=3)
    await app.start()
    ws_a, _ = await connect_client(app)
    ws_b, _ = await connect_client(app)
    try:
        # A subscribe counts as a client message; exhaust client A's quota.
        await ws_a.send(json.dumps({"type": "subscribe", "channel": "ca"}))
        await ws_b.send(json.dumps({"type": "subscribe", "channel": "cb"}))
        await asyncio.sleep(0.1)
        for i in (1, 2):
            await ws_a.send(
                json.dumps({"type": "broadcast", "channel": "ca", "payload": {"a": i}})
            )
            await asyncio.wait_for(ws_a.recv(), timeout=5)

        await ws_a.send(
            json.dumps({"type": "broadcast", "channel": "ca", "payload": {"a": 3}})
        )
        msg = json.loads(await asyncio.wait_for(ws_a.recv(), timeout=5))
        assert msg["payload"]["event"] == "error"

        # Client B is unaffected.
        await ws_b.send(
            json.dumps({"type": "broadcast", "channel": "cb", "payload": {"b": 1}})
        )
        msg = json.loads(await asyncio.wait_for(ws_b.recv(), timeout=5))
        assert msg["type"] == "broadcast"
        assert msg["payload"] == {"b": 1}
    finally:
        await ws_a.close()
        await ws_b.close()
        await app.stop()


async def test_rate_limit_configurable_via_env(monkeypatch, backend):
    monkeypatch.setenv("RATE_LIMIT", "3")
    app = NotificationApp(backend=backend)
    await app.start()
    ws, _ = await connect_client(app)
    try:
        for i in range(3):
            await ws.send(json.dumps({"type": "broadcast", "payload": {"i": i}}))
            await asyncio.wait_for(ws.recv(), timeout=5)
        await ws.send(json.dumps({"type": "broadcast", "payload": {"over": True}}))
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        assert msg["type"] == "system"
        assert msg["payload"]["event"] == "error"
    finally:
        await ws.close()
        await app.stop()


async def test_rate_limit_resets_after_window(backend):
    app = NotificationApp(backend=backend, rate_limit=1, rate_limit_window=1)
    await app.start()
    ws, _ = await connect_client(app)
    try:
        await ws.send(json.dumps({"type": "broadcast", "payload": {"n": 1}}))
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        assert msg["type"] == "broadcast"

        await ws.send(json.dumps({"type": "broadcast", "payload": {"n": 2}}))
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        assert msg["payload"]["event"] == "error"

        await asyncio.sleep(1.2)
        await ws.send(json.dumps({"type": "broadcast", "payload": {"n": 3}}))
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        assert msg["type"] == "broadcast"
        assert msg["payload"] == {"n": 3}
    finally:
        await ws.close()
        await app.stop()


# ── Message history ───────────────────────────────────────────────────────


async def test_history_returns_chronological_messages(hist_app, store):
    for i in range(5):
        await store.record("alerts", "broadcast", {"i": i}, iso_at(i))

    status, body = await http_get(hist_app, "/history?channel=alerts&limit=10")
    assert status == 200
    data = json.loads(body)
    assert data["channel"] == "alerts"
    assert [m["payload"]["i"] for m in data["messages"]] == [0, 1, 2, 3, 4]
    assert data["has_more"] is False


async def test_history_pagination_with_has_more(hist_app, store):
    for i in range(5):
        await store.record("alerts", "broadcast", {"i": i}, iso_at(i))

    status, body = await http_get(hist_app, "/history?channel=alerts&limit=2")
    data = json.loads(body)
    assert [m["payload"]["i"] for m in data["messages"]] == [0, 1]
    assert data["has_more"] is True

    status, body = await http_get(hist_app, "/history?channel=alerts&limit=2&offset=2")
    data = json.loads(body)
    assert [m["payload"]["i"] for m in data["messages"]] == [2, 3]
    assert data["has_more"] is True

    status, body = await http_get(hist_app, "/history?channel=alerts&limit=2&offset=4")
    data = json.loads(body)
    assert [m["payload"]["i"] for m in data["messages"]] == [4]
    assert data["has_more"] is False


async def test_history_since_filters_by_time(hist_app, store):
    for i in range(4):
        await store.record("alerts", "broadcast", {"i": i}, iso_at(i))
    since = (datetime.now(timezone.utc) + timedelta(seconds=1, microseconds=100)).isoformat()

    status, body = await http_get(
        hist_app, f"/history?channel=alerts&since={quote(since, safe='')}"
    )
    assert status == 200
    data = json.loads(body)
    assert [m["payload"]["i"] for m in data["messages"]] == [2, 3]


async def test_history_filters_by_channel(hist_app, store):
    await store.record("alerts", "broadcast", {"x": 1}, iso_at(0))
    await store.record("chat", "broadcast", {"y": 2}, iso_at(0))
    await store.record("alerts", "broadcast", {"x": 3}, iso_at(1))

    status, body = await http_get(hist_app, "/history?channel=alerts")
    data = json.loads(body)
    assert [m["payload"] for m in data["messages"]] == [{"x": 1}, {"x": 3}]
    assert all(m["channel"] == "alerts" for m in data["messages"])


async def test_history_records_relayed_messages(store):
    app = NotificationApp(store=store)
    await app.start()
    ws, _ = await connect_client(app)
    try:
        await ws.send(json.dumps({"type": "subscribe", "channel": "news"}))
        await asyncio.sleep(0.1)
        for i in range(3):
            await ws.send(
                json.dumps({"type": "broadcast", "channel": "news", "payload": {"i": i}})
            )
            await asyncio.wait_for(ws.recv(), timeout=5)
        await ws.send(json.dumps({"type": "broadcast", "payload": {"i": 99}}))
        await asyncio.wait_for(ws.recv(), timeout=5)

        status, body = await http_get(app, "/history?channel=news")
        assert status == 200
        data = json.loads(body)
        assert [m["payload"]["i"] for m in data["messages"]] == [0, 1, 2]
        assert all(m["channel"] == "news" for m in data["messages"])
        assert data["has_more"] is False
    finally:
        await ws.close()
        await app.stop()


# ── System message expiry ────────────────────────────────────────────────


async def test_delete_older_than_removes_expired(store):
    old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    fresh = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    await store.record("alerts", "broadcast", {"old": True}, old)
    await store.record("alerts", "broadcast", {"fresh": True}, fresh)

    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    deleted = await store.delete_older_than(cutoff)
    assert deleted == 1
    assert await store.count() == 1
    messages = (await store.query_history("alerts", limit=10, offset=0))[0]
    assert [m["payload"] for m in messages] == [{"fresh": True}]


async def test_background_cleanup_removes_expired_messages(tmp_path):
    db = tmp_path / "ttl.db"
    store = MessageStore(str(db))
    await store.connect()
    old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    fresh = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    await store.record("alerts", "broadcast", {"old": True}, old)
    await store.record("alerts", "broadcast", {"fresh": True}, fresh)

    app = NotificationApp(store=store, message_ttl_days=7, cleanup_interval=0.1)
    await app.start()
    try:
        async def count_is_one():
            return await store.count() == 1

        ok = await wait_until(count_is_one, timeout=3.0)
        assert ok
        messages = (await store.query_history("alerts", limit=10, offset=0))[0]
        assert [m["payload"] for m in messages] == [{"fresh": True}]
    finally:
        await app.stop()
        await store.close()


async def test_message_ttl_days_configurable_via_env(monkeypatch, tmp_path):
    monkeypatch.setenv("MESSAGE_TTL_DAYS", "2")
    store = MessageStore(str(tmp_path / "env_ttl.db"))
    await store.connect()
    old = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    fresh = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    await store.record("alerts", "broadcast", {"old": True}, old)
    await store.record("alerts", "broadcast", {"fresh": True}, fresh)

    app = NotificationApp(store=store, cleanup_interval=0.1)
    await app.start()
    try:
        async def count_is_one():
            return await store.count() == 1

        ok = await wait_until(count_is_one, timeout=3.0)
        assert ok
    finally:
        await app.stop()
        await store.close()
