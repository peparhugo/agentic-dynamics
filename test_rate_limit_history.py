"""Tests for rate limiting, the /history endpoint and message expiry."""

import asyncio
import json
import time
from datetime import datetime, timedelta, timezone

import aiohttp
import fakeredis
import fakeredis.aioredis
import pytest
from websockets.asyncio.client import connect

from broker import MessageStore
from ratelimit import (
    DEFAULT_RATE_LIMIT,
    KEY_PREFIX,
    RateLimiter,
    default_rate_limit,
)
from server import NotificationServer, make_message


async def recv_json(ws, timeout=5.0):
    return json.loads(await asyncio.wait_for(ws.recv(), timeout))


async def recv_nothing(ws, timeout=0.2):
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(ws.recv(), timeout)


@pytest.fixture
def fakeredis_server():
    return fakeredis.FakeServer()


async def start(srv):
    await srv.start(host="localhost", port=0)
    return srv._server.sockets[0].getsockname()[1]


def stored_message(text, channel="news"):
    msg = make_message("broadcast", {"text": text})
    return msg, channel


# ── Rate limiting: limiter unit tests ──────────────────────────


async def test_memory_limiter_allows_up_to_limit_and_rejects_beyond():
    limiter = RateLimiter(limit=3, window=60)
    cid = "client-1"
    for _ in range(3):
        assert await limiter.allow(cid) is True
    assert await limiter.allow(cid) is False
    # Other clients are unaffected.
    assert await limiter.allow("client-2") is True


async def test_redis_limiter_uses_per_client_redis_counters(fakeredis_server):
    redis = fakeredis.aioredis.FakeRedis(
        server=fakeredis_server, decode_responses=True
    )
    limiter = RateLimiter(limit=3, window=60, redis=redis)
    cid = "client-1"
    for _ in range(3):
        assert await limiter.allow(cid) is True
    assert await limiter.allow(cid) is False
    assert await limiter.allow("client-2") is True

    keys = [key async for key in redis.scan_iter(match=f"{KEY_PREFIX}rl:*")]
    assert len(keys) == 2
    assert any(key.startswith(f"{KEY_PREFIX}rl:client-1:") for key in keys)
    assert any(key.startswith(f"{KEY_PREFIX}rl:client-2:") for key in keys)

    await limiter.reset("client-1")
    assert await limiter.allow(cid) is True
    await limiter.close()


async def test_limiter_window_resets(fakeredis_server):
    limiter = RateLimiter(limit=1, window=0.3)
    assert await limiter.allow("client-1") is True
    assert await limiter.allow("client-1") is False
    await asyncio.sleep(0.4)
    assert await limiter.allow("client-1") is True


def test_rate_limit_env_var(monkeypatch):
    monkeypatch.delenv("RATE_LIMIT", raising=False)
    assert default_rate_limit() == DEFAULT_RATE_LIMIT
    monkeypatch.setenv("RATE_LIMIT", "5")
    assert default_rate_limit() == 5
    monkeypatch.setenv("RATE_LIMIT", "not-a-number")
    assert default_rate_limit() == DEFAULT_RATE_LIMIT


# ── Rate limiting: server integration ──────────────────────────


async def test_server_returns_error_when_client_exceeds_limit(tmp_path):
    limiter = RateLimiter(limit=3, window=60)
    srv = NotificationServer(
        store=MessageStore(str(tmp_path / "rl.db")), rate_limiter=limiter
    )
    port = await start(srv)
    try:
        async with connect(f"ws://localhost:{port}") as ws:
            await recv_json(ws)  # welcome
            for i in range(3):
                await ws.send(
                    json.dumps({"type": "broadcast", "payload": {"text": f"m{i}"}})
                )
            for i in range(3):
                msg = await recv_json(ws)
                assert msg["type"] == "broadcast"
                assert msg["payload"]["text"] == f"m{i}"

            await ws.send(json.dumps({"type": "broadcast", "payload": {"text": "over"}}))
            err = await recv_json(ws)
            assert err["type"] == "system"
            assert err["payload"]["event"] == "error"
            assert "rate limit" in err["payload"]["error"].lower()

            # The client is NOT dropped: it stays connected and can still be
            # reached by the server.
            assert srv.client_count == 1
            await srv.broadcast({"text": "still-here"})
            msg = await recv_json(ws)
            assert msg["payload"] == {"text": "still-here"}
    finally:
        await srv.stop()


async def test_rate_limit_is_per_client(tmp_path):
    limiter = RateLimiter(limit=2, window=60)
    srv = NotificationServer(
        store=MessageStore(str(tmp_path / "rl.db")), rate_limiter=limiter
    )
    port = await start(srv)
    try:
        async with connect(f"ws://localhost:{port}") as ws_a, connect(
            f"ws://localhost:{port}"
        ) as ws_b:
            welcome_a = await recv_json(ws_a)
            welcome_b = await recv_json(ws_b)
            id_a = welcome_a["payload"]["client_id"]
            id_b = welcome_b["payload"]["client_id"]

            # ws_a uses up its allowance sending direct messages.
            for _ in range(2):
                await ws_a.send(
                    json.dumps(
                        {"type": "direct", "payload": {"target_id": id_b, "text": "x"}}
                    )
                )
            for _ in range(2):
                assert (await recv_json(ws_b))["type"] == "direct"

            # ws_a is over the limit: the next message is rejected with an error.
            await ws_a.send(
                json.dumps(
                    {"type": "direct", "payload": {"target_id": id_b, "text": "x"}}
                )
            )
            err = await recv_json(ws_a)
            assert err["type"] == "system"
            assert err["payload"]["event"] == "error"

            # ws_b still has its full allowance.
            await ws_b.send(
                json.dumps(
                    {"type": "direct", "payload": {"target_id": id_a, "text": "y"}}
                )
            )
            direct = await recv_json(ws_a)
            assert direct["type"] == "direct"
            assert direct["payload"]["text"] == "y"
    finally:
        await srv.stop()


# ── History: store-level ───────────────────────────────────────


async def test_store_history_chronological_and_paginated(tmp_path):
    store = MessageStore(str(tmp_path / "h.db"))
    await store.init()
    for i in range(5):
        msg, channel = stored_message(f"m{i}")
        await store.store(msg, channel)
        await asyncio.sleep(0.001)

    page0 = await store.history("news", limit=2, offset=0)
    assert [m["payload"]["text"] for m in page0["messages"]] == ["m0", "m1"]
    assert page0["has_more"] is True

    page1 = await store.history("news", limit=2, offset=2)
    assert [m["payload"]["text"] for m in page1["messages"]] == ["m2", "m3"]
    assert page1["has_more"] is True

    page2 = await store.history("news", limit=2, offset=4)
    assert [m["payload"]["text"] for m in page2["messages"]] == ["m4"]
    assert page2["has_more"] is False

    await store.close()


async def test_store_history_filters_by_channel_and_since(tmp_path):
    store = MessageStore(str(tmp_path / "h.db"))
    await store.init()
    base = datetime.now(timezone.utc).replace(microsecond=0)
    stored = []
    for i in range(4):
        msg, _ = stored_message(f"m{i}", channel="news")
        msg["timestamp"] = (base + timedelta(seconds=i)).isoformat()
        stored.append(msg)
        await store.store(msg, "news")
    other, _ = stored_message("other", channel="chat")
    other["timestamp"] = (base + timedelta(seconds=10)).isoformat()
    await store.store(other, "chat")

    page = await store.history("news", since=stored[1]["timestamp"])
    assert [m["payload"]["text"] for m in page["messages"]] == ["m1", "m2", "m3"]
    assert page["has_more"] is False

    # Without a channel every channel is returned, still chronological.
    all_msgs = await store.history()
    texts = [m["payload"]["text"] for m in all_msgs["messages"]]
    assert texts == ["m0", "m1", "m2", "m3", "other"]

    await store.close()


async def test_store_history_since_accepts_naive_timestamp(tmp_path):
    store = MessageStore(str(tmp_path / "h.db"))
    await store.init()
    for i in range(3):
        msg, _ = stored_message(f"m{i}", channel="news")
        await store.store(msg, "news")
        await asyncio.sleep(0.001)
    # A naive (no timezone) ISO timestamp is treated as UTC.
    naive = (datetime.utcnow() - timedelta(seconds=5)).isoformat()
    page = await store.history("news", since=naive)
    assert [m["payload"]["text"] for m in page["messages"]] == ["m0", "m1", "m2"]
    await store.close()


# ── History: REST endpoint ─────────────────────────────────────


async def test_history_endpoint_returns_chronological_pages(tmp_path):
    store = MessageStore(str(tmp_path / "h.db"))
    await store.init()
    for i in range(4):
        msg, _ = stored_message(f"m{i}", channel="news")
        await store.store(msg, "news")
        await asyncio.sleep(0.001)
    msg, _ = stored_message("other", channel="chat")
    await store.store(msg, "chat")

    srv = NotificationServer(store=store)
    port = await start(srv)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://localhost:{port}/history?channel=news&limit=2"
            ) as resp:
                assert resp.status == 200
                body = await resp.json()
        assert [m["payload"]["text"] for m in body["messages"]] == ["m0", "m1"]
        assert body["has_more"] is True
        assert body["channel"] == "news"
        assert body["limit"] == 2
        assert body["offset"] == 0

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://localhost:{port}/history?channel=news&limit=2&offset=2"
            ) as resp:
                body2 = await resp.json()
        assert [m["payload"]["text"] for m in body2["messages"]] == ["m2", "m3"]
        assert body2["has_more"] is False
    finally:
        await srv.stop()


async def test_history_endpoint_since_and_defaults(tmp_path):
    store = MessageStore(str(tmp_path / "h.db"))
    await store.init()
    for i in range(3):
        msg, _ = stored_message(f"m{i}", channel="news")
        await store.store(msg, "news")
        await asyncio.sleep(0.001)

    srv = NotificationServer(store=store)
    port = await start(srv)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://localhost:{port}/history?channel=news&limit=1"
            ) as resp:
                first = await resp.json()
            async with session.get(
                f"http://localhost:{port}/history"
                f"?channel=news&since={first['messages'][0]['timestamp']}"
            ) as resp:
                rest = await resp.json()
        assert [m["payload"]["text"] for m in first["messages"]] == ["m0"]
        assert [m["payload"]["text"] for m in rest["messages"]] == ["m0", "m1", "m2"]
    finally:
        await srv.stop()


# ── Message expiry ─────────────────────────────────────────────


async def test_store_cleanup_removes_only_expired(tmp_path):
    store = MessageStore(str(tmp_path / "clean.db"))
    await store.init()
    await store.store(make_message("system", {"event": "fresh"}))

    old = make_message("system", {"event": "old"})
    old["timestamp"] = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    await store.store(old)

    removed = await store.cleanup(ttl_days=7)
    assert removed == 1

    remaining = await store.list()
    assert len(remaining) == 1
    assert remaining[0]["payload"]["event"] == "fresh"
    await store.close()


async def test_server_cleans_up_expired_messages_on_startup(tmp_path):
    store = MessageStore(str(tmp_path / "clean.db"))
    await store.init()
    old = make_message("system", {"event": "old"})
    old["timestamp"] = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    await store.store(old)
    await store.store(make_message("system", {"event": "fresh"}))

    srv = NotificationServer(store=store, ttl_days=7)
    port = await start(srv)
    try:
        for _ in range(100):
            if len(await store.list()) == 1:
                break
            await asyncio.sleep(0.01)
        remaining = await store.list()
        assert [m["payload"]["event"] for m in remaining] == ["fresh"]
    finally:
        await srv.stop()


def test_ttl_days_env_var(monkeypatch):
    monkeypatch.delenv("MESSAGE_TTL_DAYS", raising=False)
    assert NotificationServer()._ttl_days == 7
    monkeypatch.setenv("MESSAGE_TTL_DAYS", "3")
    assert NotificationServer()._ttl_days == 3
    monkeypatch.setenv("MESSAGE_TTL_DAYS", "bogus")
    assert NotificationServer()._ttl_days == 7
