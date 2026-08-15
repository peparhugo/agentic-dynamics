"""Tests for rate limiting, message history, and message expiry."""

import json
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import pytest
import pytest_asyncio
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve as ws_serve

from conftest import http_get, parse_http, recv_message, send_message
from notification_server import NotificationServer


@pytest_asyncio.fixture
async def limited_server(tmp_path):
    """Start a server with a tiny rate limit so tests can trigger it easily."""
    app = NotificationServer(
        database_url=str(tmp_path / "limit.db"), rate_limit=3
    )
    async with ws_serve(
        app.handler, "127.0.0.1", 0, process_request=app.process_request
    ) as server:
        port = server.sockets[0].getsockname()[1]
        yield app, port


# ── Rate limiting ─────────────────────────────────────────────


async def test_rate_limit_exceeded_returns_error(limited_server):
    _, port = limited_server
    ws = await connect(f"ws://127.0.0.1:{port}")
    try:
        await recv_message(ws)  # connection handshake

        for i in range(3):
            await send_message(ws, {"type": "broadcast", "payload": {"n": i}})
            msg = await recv_message(ws)
            assert msg["type"] == "broadcast"

        await send_message(ws, {"type": "broadcast", "payload": {"n": 99}})
        msg = await recv_message(ws)
        assert msg["type"] == "system"
        assert "error" in msg["payload"]
    finally:
        await ws.close()


async def test_rate_limit_is_per_client(limited_server):
    _, port = limited_server
    ws1 = await connect(f"ws://127.0.0.1:{port}")
    ws2 = await connect(f"ws://127.0.0.1:{port}")
    try:
        await recv_message(ws1)
        await recv_message(ws2)

        for _ in range(3):
            await send_message(ws1, {"type": "broadcast", "payload": {"n": 0}})
            await recv_message(ws1)

        await send_message(ws1, {"type": "broadcast", "payload": {"n": 1}})
        msg = await recv_message(ws1)
        assert msg["type"] == "system"
        assert "error" in msg["payload"]

        # A different client is still within its own budget.
        await send_message(ws2, {"type": "broadcast", "payload": {"n": 2}})
        msg = await recv_message(ws2)
        assert msg["type"] == "broadcast"
    finally:
        await ws1.close()
        await ws2.close()


async def test_rate_limit_uses_redis_counters(redis_backbone, tmp_path):
    import fakeredis.aioredis as fakeredis_aioredis

    client = fakeredis_aioredis.FakeRedis(server=redis_backbone, decode_responses=True)
    app = NotificationServer(
        redis_client=client,
        database_url=str(tmp_path / "rl.db"),
        rate_limit=5,
    )
    await app.start()
    try:
        for _ in range(5):
            assert await app._check_rate_limit("client-a") is True
        assert await app._check_rate_limit("client-a") is False
        assert await app._check_rate_limit("client-b") is True
    finally:
        await app.stop()
        await client.aclose()


# ── Message history ───────────────────────────────────────────


async def test_history_endpoint_filters_channel_and_since(server):
    app, port = server
    base = datetime.now(timezone.utc) - timedelta(minutes=10)
    app.store.save("room", "broadcast", {"n": 1}, (base + timedelta(seconds=1)).isoformat())
    app.store.save("room", "broadcast", {"n": 2}, (base + timedelta(seconds=2)).isoformat())
    app.store.save("other", "broadcast", {"n": 3}, (base + timedelta(seconds=3)).isoformat())
    app.store.save("room", "broadcast", {"n": 4}, (base + timedelta(seconds=4)).isoformat())

    since = (base + timedelta(seconds=2)).isoformat()
    path = "/history?channel=room&since=" + quote(since) + "&limit=50"
    status, body = parse_http(await http_get(port, path))
    assert status == 200
    data = json.loads(body)
    assert data["has_more"] is False
    assert [m["payload"]["n"] for m in data["messages"]] == [2, 4]


async def test_history_returns_chronological_order_and_has_more(server):
    app, port = server
    base = datetime.now(timezone.utc) - timedelta(minutes=10)
    for i in range(3):
        app.store.save(
            "room", "broadcast", {"n": i},
            (base + timedelta(seconds=i)).isoformat(),
        )

    status, body = parse_http(await http_get(port, "/history?channel=room&limit=2"))
    assert status == 200
    data = json.loads(body)
    assert data["has_more"] is True
    assert [m["payload"]["n"] for m in data["messages"]] == [0, 1]

    for m in data["messages"]:
        assert set(m.keys()) >= {"id", "channel", "type", "payload", "timestamp"}


async def test_history_default_limit_is_50(server):
    app, port = server
    app.store.save("room", "broadcast", {"n": 0}, datetime.now(timezone.utc).isoformat())

    status, body = parse_http(await http_get(port, "/history?channel=room"))
    assert status == 200
    data = json.loads(body)
    assert data["has_more"] is False
    assert len(data["messages"]) == 1


# ── Message expiry ────────────────────────────────────────────


async def test_cleanup_removes_expired_messages(tmp_path):
    app = NotificationServer(
        database_url=str(tmp_path / "clean.db"), message_ttl_days=7
    )
    old = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    recent = datetime.now(timezone.utc).isoformat()
    app.store.save("room", "broadcast", {"n": 1}, old)
    app.store.save("room", "broadcast", {"n": 2}, recent)

    deleted = app.cleanup_expired()
    assert deleted == 1
    assert [m["payload"]["n"] for m in app.store.list()] == [2]


async def test_cleanup_runs_on_startup(tmp_path):
    app = NotificationServer(
        database_url=str(tmp_path / "startup.db"), message_ttl_days=7
    )
    old = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    recent = datetime.now(timezone.utc).isoformat()
    app.store.save("room", "broadcast", {"n": 1}, old)
    app.store.save("room", "broadcast", {"n": 2}, recent)

    await app.start()
    try:
        assert app._cleanup_task is not None
        assert [m["payload"]["n"] for m in app.store.list()] == [2]
    finally:
        await app.stop()
