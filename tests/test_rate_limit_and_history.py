"""Tests for per-client rate limiting, history queries, and TTL expiry."""

import asyncio
import json
import time
import urllib.request
from datetime import datetime, timedelta, timezone

import pytest
import websockets
from fakeredis import FakeRedis

import notification_server as ns
from notification_server import NotificationServer, make_message


def parse(raw) -> dict:
    return json.loads(raw)


def ts(seconds_offset: int = 0) -> str:
    """ISO timestamp offset from now, safe against TTL expiry."""
    base = datetime.now(timezone.utc).replace(microsecond=0)
    return (base + timedelta(seconds=seconds_offset)).isoformat()


async def http_get(url: str):
    def _get():
        with urllib.request.urlopen(url, timeout=5) as resp:
            return json.loads(resp.read())

    return await asyncio.to_thread(_get)


@pytest.fixture(autouse=True)
def patch_redis(monkeypatch):
    fake = FakeRedis(decode_responses=True)
    monkeypatch.setattr(ns, "_get_redis", lambda: fake)
    monkeypatch.setattr(ns, "_redis_failed", False)
    monkeypatch.setattr(ns, "_redis_client", None)
    return fake


# ── Rate limiter unit tests ────────────────────────────────────────

def test_rate_limiter_allows_up_to_limit_then_blocks():
    limiter = ns.RateLimiter(limit=3)
    for _ in range(3):
        assert limiter.allow("client-1") is True
    assert limiter.allow("client-1") is False
    assert limiter.allow("client-2") is True


def test_rate_limiter_uses_redis_counters(patch_redis):
    fake = patch_redis
    limiter = ns.RateLimiter(limit=3)
    for _ in range(3):
        assert limiter.allow("client-1") is True
    assert limiter.allow("client-1") is False
    assert fake.get("chat:ratelimit:client-1") == "4"


def test_rate_limiter_reset(patch_redis):
    fake = patch_redis
    limiter = ns.RateLimiter(limit=3)
    for _ in range(3):
        assert limiter.allow("client-1") is True
    assert limiter.allow("client-1") is False
    limiter.reset("client-1")
    assert fake.get("chat:ratelimit:client-1") is None
    assert limiter.allow("client-1") is True


def test_rate_limiter_window_resets(monkeypatch):
    monkeypatch.setattr(ns, "_get_redis", lambda: None)
    monkeypatch.setattr(ns, "_redis_failed", True)
    now = [1000.0]
    monkeypatch.setattr(ns.time, "monotonic", lambda: now[0])
    limiter = ns.RateLimiter(limit=2, window_seconds=60.0)
    assert limiter.allow("c") is True
    assert limiter.allow("c") is True
    assert limiter.allow("c") is False
    now[0] = 1000.0 + 60.0
    assert limiter.allow("c") is True


# ── Rate limiting over the wire ────────────────────────────────────

async def test_server_returns_error_when_rate_limit_exceeded():
    srv = await NotificationServer(rate_limit=3).start()
    try:
        async with websockets.connect(srv.ws_url) as ws:
            await ws.recv()  # connection hello
            for i in range(3):
                await ws.send(json.dumps(make_message("system", {"i": i})))
                msg = parse(await asyncio.wait_for(ws.recv(), timeout=3))
                assert msg["payload"]["event"] == "ack"

            await ws.send(json.dumps(make_message("system", {"i": 3})))
            msg = parse(await asyncio.wait_for(ws.recv(), timeout=3))
            assert msg["type"] == "system"
            assert msg["payload"]["event"] == "error"
            assert "rate limit" in msg["payload"]["error"].lower()
    finally:
        await srv.stop()


async def test_rate_limit_is_per_client():
    srv = await NotificationServer(rate_limit=2).start()
    try:
        async with websockets.connect(srv.ws_url) as a, \
                   websockets.connect(srv.ws_url) as b:
            await a.recv()
            await b.recv()
            for _ in range(2):
                await a.send(json.dumps(make_message("system", {})))
                await a.recv()

            await b.send(json.dumps(make_message("system", {"b": 1})))
            msg = parse(await asyncio.wait_for(b.recv(), timeout=3))
            assert msg["payload"]["event"] == "ack"

            await a.send(json.dumps(make_message("system", {})))
            msg = parse(await asyncio.wait_for(a.recv(), timeout=3))
            assert msg["payload"]["event"] == "error"
            assert "rate limit" in msg["payload"]["error"].lower()
    finally:
        await srv.stop()


async def test_rate_limited_message_is_not_delivered():
    srv = await NotificationServer(rate_limit=1).start()
    try:
        async with websockets.connect(srv.ws_url) as a, \
                   websockets.connect(srv.ws_url) as b:
            await a.recv()
            await b.recv()
            await a.send(json.dumps(make_message("broadcast", {"text": "one"})))
            assert (await asyncio.wait_for(b.recv(), timeout=3)) is not None
            await asyncio.wait_for(a.recv(), timeout=3)  # sender's own echo
            await asyncio.sleep(0.05)

            await a.send(json.dumps(make_message("broadcast", {"text": "two"})))
            msg = parse(await asyncio.wait_for(a.recv(), timeout=3))
            assert msg["payload"]["event"] == "error"
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(b.recv(), timeout=0.3)
    finally:
        await srv.stop()


# ── History queries ────────────────────────────────────────────────

def make_store(tmp_path, name="history.db") -> ns.MessageStore:
    return ns.MessageStore(str(tmp_path / name))


async def test_history_returns_chronological_and_has_more(tmp_path):
    store = make_store(tmp_path)
    for i in range(5):
        store.save(
            "room1", "broadcast", {"text": str(i)}, ts(seconds_offset=i)
        )
    srv = await NotificationServer(store=store).start()
    try:
        data = await http_get(f"{srv.http_url}/history?channel=room1&limit=2")
        assert set(data) == {"messages", "has_more"}
        assert [m["payload"]["text"] for m in data["messages"]] == ["0", "1"]
        assert data["has_more"] is True

        page2 = await http_get(
            f"{srv.http_url}/history?channel=room1&limit=2&offset=2"
        )
        assert [m["payload"]["text"] for m in page2["messages"]] == ["2", "3"]
        assert page2["has_more"] is True

        page3 = await http_get(
            f"{srv.http_url}/history?channel=room1&limit=2&offset=4"
        )
        assert [m["payload"]["text"] for m in page3["messages"]] == ["4"]
        assert page3["has_more"] is False

        ids = [m["id"] for m in data["messages"] + page2["messages"]]
        assert len(set(ids)) == 4

        timestamps = [
            m["timestamp"] for m in (data["messages"] + page2["messages"] + page3["messages"])
        ]
        assert timestamps == sorted(timestamps)
    finally:
        await srv.stop()


async def test_history_filters_by_channel_and_since(tmp_path):
    store = make_store(tmp_path)
    store.save("room1", "broadcast", {"text": "a"}, ts(0))
    store.save("room2", "broadcast", {"text": "b"}, ts(60))
    store.save("room1", "broadcast", {"text": "c"}, ts(120))
    store.save("room1", "broadcast", {"text": "d"}, ts(180))
    srv = await NotificationServer(store=store).start()
    try:
        data = await http_get(f"{srv.http_url}/history?channel=room1&limit=50")
        assert [m["payload"]["text"] for m in data["messages"]] == ["a", "c", "d"]
        assert data["has_more"] is False

        data = await http_get(
            f"{srv.http_url}/history?channel=room1&since={ts(60)}&limit=50"
        )
        assert [m["payload"]["text"] for m in data["messages"]] == ["c", "d"]

        data = await http_get(f"{srv.http_url}/history?limit=50")
        assert len(data["messages"]) == 4
    finally:
        await srv.stop()


async def test_history_via_wire_messages(tmp_path):
    store = make_store(tmp_path)
    srv = await NotificationServer(store=store).start()
    try:
        async with websockets.connect(srv.ws_url) as a, \
                   websockets.connect(srv.ws_url) as b:
            await a.recv()
            await b.recv()
            await b.send(json.dumps(make_message("subscribe", {"channel": "chat"})))
            await asyncio.sleep(0.05)
            for text in ("first", "second", "third"):
                await a.send(
                    json.dumps(
                        make_message("broadcast", {"channel": "chat", "text": text})
                    )
                )
                await asyncio.wait_for(b.recv(), timeout=3)
            await asyncio.sleep(0.1)

        data = await http_get(f"{srv.http_url}/history?channel=chat&limit=50")
        texts = [m["payload"]["text"] for m in data["messages"]]
        assert texts == ["first", "second", "third"]
        assert data["has_more"] is False
    finally:
        await srv.stop()


# ── Message expiry ─────────────────────────────────────────────────

def test_store_purge_removes_expired(tmp_path):
    store = make_store(tmp_path)
    store.save("room1", "broadcast", {"text": "old"}, "2020-01-01T00:00:00+00:00")
    store.save("room1", "broadcast", {"text": "new"}, "2026-08-16T00:00:00+00:00")
    purged = store.purge("2026-01-01T00:00:00+00:00")
    assert purged == 1
    remaining = store.list()
    assert len(remaining) == 1
    assert remaining[0]["payload"]["text"] == "new"


async def test_server_startup_cleanup_removes_expired(tmp_path):
    store = make_store(tmp_path)
    store.save("room1", "broadcast", {"text": "old"}, "2020-01-01T00:00:00+00:00")
    store.save(
        "room1", "broadcast", {"text": "recent"},
        datetime.now(timezone.utc).isoformat(),
    )
    srv = await NotificationServer(store=store, ttl_days=7).start()
    try:
        await srv._cleanup_task
        remaining = store.list()
        assert len(remaining) == 1
        assert remaining[0]["payload"]["text"] == "recent"
    finally:
        await srv.stop()
