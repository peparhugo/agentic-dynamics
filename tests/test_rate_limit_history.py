"""Tests for rate limiting, message history, and TTL cleanup."""

import asyncio
import json
import urllib.request
from datetime import datetime, timedelta, timezone

import pytest
import websockets
from fakeredis import FakeServer
from fakeredis.aioredis import FakeRedis

from notification_server import (
    NotificationServer,
    RateLimiter,
    decode_message,
    encode_message,
    now_iso,
)


async def connect_client(port):
    """Connect a client and consume its initial system 'connected' message."""
    ws = await websockets.connect(f"ws://127.0.0.1:{port}")
    raw = await asyncio.wait_for(ws.recv(), timeout=5)
    msg = decode_message(raw)
    assert msg["type"] == "system"
    assert msg["payload"]["event"] == "connected"
    return ws, msg["payload"]["client_id"]


async def get_json(port, path):
    url = f"http://127.0.0.1:{port}{path}"
    resp = await asyncio.to_thread(urllib.request.urlopen, url)
    return json.loads(resp.read().decode("utf-8"))


# ── Rate limiting ─────────────────────────────────────────────


async def test_rate_limit_exceeded_returns_error(tmp_path):
    fake_server = FakeServer()
    redis = FakeRedis(server=fake_server, decode_responses=True)
    ns = NotificationServer(
        redis_client=redis,
        database_url=str(tmp_path / "rl.db"),
        rate_limit=3,
    )
    await ns.start()
    try:
        async with websockets.serve(
            ns.handler, "127.0.0.1", 0, process_request=ns.process_request
        ) as s:
            port = s.sockets[0].getsockname()[1]
            ws, client_id = await connect_client(port)

            for i in range(3):
                await ws.send(
                    encode_message({"type": "broadcast", "payload": {"n": i}})
                )
                got = decode_message(await asyncio.wait_for(ws.recv(), timeout=5))
                assert got["type"] == "broadcast"
                assert got["payload"]["n"] == i

            await ws.send(
                encode_message({"type": "broadcast", "payload": {"n": 99}})
            )
            err = decode_message(await asyncio.wait_for(ws.recv(), timeout=5))
            assert err["type"] == "error"
            assert err["payload"]["error"] == "rate limit exceeded"

            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(ws.recv(), timeout=0.3)

            await ws.close()

        messages, has_more = ns.store.query_history(limit=50)
        assert len(messages) == 3
        assert has_more is False
    finally:
        await ns.stop()


async def test_rate_limit_uses_redis_counter(tmp_path):
    fake_server = FakeServer()
    redis = FakeRedis(server=fake_server, decode_responses=True)
    ns = NotificationServer(redis_client=redis, rate_limit=100)
    await ns.start()
    try:
        assert await ns.rate_limiter.allow("client-1", redis) is True
        assert await redis.get(RateLimiter.KEY_PREFIX + "client-1") == "1"
    finally:
        await ns.stop()


async def test_rate_limit_local_fallback(tmp_path):
    ns = NotificationServer(database_url=str(tmp_path / "local.db"), rate_limit=2)
    async with websockets.serve(
        ns.handler, "127.0.0.1", 0, process_request=ns.process_request
    ) as s:
        port = s.sockets[0].getsockname()[1]
        ws, _ = await connect_client(port)

        for i in range(2):
            await ws.send(encode_message({"type": "broadcast", "payload": {"n": i}}))
            got = decode_message(await asyncio.wait_for(ws.recv(), timeout=5))
            assert got["type"] == "broadcast"

        await ws.send(encode_message({"type": "broadcast", "payload": {"n": 2}}))
        err = decode_message(await asyncio.wait_for(ws.recv(), timeout=5))
        assert err["type"] == "error"
        assert err["payload"]["error"] == "rate limit exceeded"

        await ws.close()


# ── Message history ───────────────────────────────────────────


async def test_history_channel_and_chronological_order(tmp_path):
    db = str(tmp_path / "history.db")
    ns = NotificationServer(database_url=db)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    # Insert out of order to prove ordering is by timestamp.
    for i in [4, 1, 3, 0, 2]:
        ns.store.save("chanA", "broadcast", {"n": i}, (base + timedelta(minutes=i)).isoformat())
    for i in range(3):
        ns.store.save("chanB", "broadcast", {"n": 100 + i}, (base + timedelta(minutes=10 + i)).isoformat())

    async with websockets.serve(
        ns.handler, "127.0.0.1", 0, process_request=ns.process_request
    ) as s:
        port = s.sockets[0].getsockname()[1]
        data = await get_json(port, "/history?channel=chanA&limit=50")
        assert data["has_more"] is False
        msgs = data["messages"]
        assert [m["payload"]["n"] for m in msgs] == [0, 1, 2, 3, 4]
        stamps = [m["timestamp"] for m in msgs]
        assert stamps == sorted(stamps)
        assert all(m["channel"] == "chanA" for m in msgs)


async def test_history_since_filter(tmp_path):
    db = str(tmp_path / "since.db")
    ns = NotificationServer(database_url=db)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(5):
        ns.store.save("chan", "broadcast", {"n": i}, (base + timedelta(minutes=i)).isoformat())

    since = (base + timedelta(minutes=2)).isoformat()
    async with websockets.serve(
        ns.handler, "127.0.0.1", 0, process_request=ns.process_request
    ) as s:
        port = s.sockets[0].getsockname()[1]
        data = await get_json(port, f"/history?channel=chan&since={since}&limit=50")
        msgs = data["messages"]
        assert [m["payload"]["n"] for m in msgs] == [2, 3, 4]
        assert data["has_more"] is False


async def test_history_pagination_has_more(tmp_path):
    db = str(tmp_path / "page.db")
    ns = NotificationServer(database_url=db)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(5):
        ns.store.save("chan", "broadcast", {"n": i}, (base + timedelta(minutes=i)).isoformat())

    async with websockets.serve(
        ns.handler, "127.0.0.1", 0, process_request=ns.process_request
    ) as s:
        port = s.sockets[0].getsockname()[1]
        data = await get_json(port, "/history?channel=chan&limit=3")
        assert data["has_more"] is True
        assert [m["payload"]["n"] for m in data["messages"]] == [0, 1, 2]

        data = await get_json(port, "/history?channel=chan&limit=50")
        assert data["has_more"] is False
        assert len(data["messages"]) == 5


# ── TTL cleanup ───────────────────────────────────────────────


def test_message_cleanup_deletes_expired(tmp_path):
    db = str(tmp_path / "cleanup.db")
    ns = NotificationServer(database_url=db, message_ttl_days=7)
    old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    ns.store.save(None, "broadcast", {"text": "old"}, old)
    ns.store.save(None, "broadcast", {"text": "new"}, now_iso())

    deleted = ns.store.delete_older_than(7)
    assert deleted == 1
    messages, has_more = ns.store.query_history(limit=50)
    assert len(messages) == 1
    assert messages[0]["payload"]["text"] == "new"


async def test_cleanup_runs_on_startup(tmp_path):
    db = str(tmp_path / "startup.db")
    ns = NotificationServer(database_url=db, message_ttl_days=7)
    old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    ns.store.save(None, "broadcast", {"text": "old"}, old)
    ns.store.save(None, "broadcast", {"text": "new"}, now_iso())

    await ns.start()
    try:
        assert ns._cleanup_task is not None
        deadline = asyncio.get_event_loop().time() + 5
        while True:
            messages, _ = ns.store.query_history(limit=50)
            if len(messages) == 1:
                break
            if asyncio.get_event_loop().time() > deadline:
                raise AssertionError("cleanup task did not remove old message")
            await asyncio.sleep(0.05)
        assert messages[0]["payload"]["text"] == "new"
    finally:
        await ns.stop()


def test_env_config_rate_limit_and_ttl(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "25")
    monkeypatch.setenv("MESSAGE_TTL_DAYS", "3")
    ns = NotificationServer()
    assert ns.rate_limit == 25
    assert ns.rate_limiter.limit == 25
    assert ns.message_ttl_days == 3
