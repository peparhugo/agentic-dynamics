"""Tests for per-client rate limiting, history queries and message expiry."""

import asyncio
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import pytest
import pytest_asyncio
import redis
from websockets.asyncio.client import connect

from broker import MessageStore, RateLimiter
from server import NotificationServer


BROKER_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


def _redis() -> redis.Redis:
    return redis.Redis.from_url(BROKER_URL)


def ws_uri(srv: NotificationServer) -> str:
    return f"ws://127.0.0.1:{srv.port}"


def http_uri(srv: NotificationServer) -> str:
    return f"http://127.0.0.1:{srv.port}"


async def recv_msg(ws) -> dict:
    return json.loads(await ws.recv())


@pytest_asyncio.fixture
async def channel_name():
    return f"rltest:{uuid.uuid4().hex}"


async def _server(channel_name, tmp_path, name="m.db", rate_limiter=None):
    srv = NotificationServer(
        port=0,
        channel=channel_name,
        store=MessageStore(path=str(tmp_path / name)),
        rate_limiter=rate_limiter,
    )
    await srv.start()
    return srv


# ── rate limiter unit tests ─────────────────────────────────────────────


def test_rate_limiter_allows_limit_messages():
    limiter = RateLimiter(limit=3, namespace=f"test:{uuid.uuid4().hex}")
    results = [limiter.check("client-a") for _ in range(4)]
    assert results == [True, True, True, False]


def test_rate_limiter_isolates_clients():
    limiter = RateLimiter(limit=2, namespace=f"test:{uuid.uuid4().hex}")
    assert limiter.check("a") is True
    assert limiter.check("a") is True
    assert limiter.check("a") is False
    assert limiter.check("b") is True
    assert limiter.check("b") is True


def test_rate_limiter_reads_env_limit(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "5")
    limiter = RateLimiter(namespace=f"test:{uuid.uuid4().hex}")
    assert limiter.limit == 5
    assert all(limiter.check("c") for _ in range(5))
    assert limiter.check("c") is False


def test_rate_limiter_sets_redis_expiry():
    limiter = RateLimiter(limit=10, namespace=f"test:{uuid.uuid4().hex}")
    key = limiter._key("client-x")
    limiter.check("client-x")
    ttl = _redis().ttl(key)
    assert 0 < ttl <= 60
    _redis().delete(key)


def test_server_default_limiter_reads_env(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "42")
    srv = NotificationServer()
    try:
        assert srv.rate_limiter.limit == 42
    finally:
        srv.rate_limiter.reset("unused")


# ── rate limiting over the wire ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_rate_limited_client_receives_error(channel_name, tmp_path):
    limiter = RateLimiter(limit=2, namespace=f"test:{channel_name}:rl")
    srv = await _server(channel_name, tmp_path, rate_limiter=limiter)
    try:
        async with connect(ws_uri(srv)) as a:
            await recv_msg(a)
            for n in (1, 2):
                await a.send(
                    json.dumps({"type": "broadcast", "payload": {"n": n}})
                )
                msg = await recv_msg(a)
                assert msg["type"] == "broadcast"
                assert msg["payload"] == {"n": n}

            await a.send(json.dumps({"type": "broadcast", "payload": {"n": 3}}))
            err = await recv_msg(a)
            assert err["type"] == "error"
            assert err["payload"]["error"] == "rate_limit_exceeded"
            assert err["payload"]["limit"] == 2
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_rate_limited_message_not_broadcast(channel_name, tmp_path):
    limiter = RateLimiter(limit=1, namespace=f"test:{channel_name}:rl2")
    srv = await _server(channel_name, tmp_path, rate_limiter=limiter)
    try:
        async with connect(ws_uri(srv)) as a:
            await recv_msg(a)
            async with connect(ws_uri(srv)) as b:
                await recv_msg(b)

                await a.send(json.dumps({"type": "broadcast", "payload": {"n": 1}}))
                assert (await recv_msg(a))["payload"] == {"n": 1}
                assert (await recv_msg(b))["payload"] == {"n": 1}

                await a.send(json.dumps({"type": "broadcast", "payload": {"n": 2}}))
                err = await recv_msg(a)
                assert err["type"] == "error"
                with pytest.raises(asyncio.TimeoutError):
                    await asyncio.wait_for(b.recv(), timeout=0.3)
    finally:
        await srv.stop()


# ── history store unit tests ────────────────────────────────────────────


def test_query_history_chronological_order(tmp_path):
    store = MessageStore(path=str(tmp_path / "h.db"))
    store.store_message("alerts", "broadcast", {"n": 1}, "2026-01-01T00:00:01+00:00")
    store.store_message("alerts", "broadcast", {"n": 2}, "2026-01-01T00:00:02+00:00")
    store.store_message("alerts", "broadcast", {"n": 3}, "2026-01-01T00:00:03+00:00")
    messages, has_more = store.query_history(channel="alerts", limit=50)
    assert has_more is False
    assert [m["payload"]["n"] for m in messages] == [1, 2, 3]
    assert all(m["channel"] == "alerts" for m in messages)


def test_query_history_channel_filter(tmp_path):
    store = MessageStore(path=str(tmp_path / "h.db"))
    store.store_message("alerts", "broadcast", {"n": 1}, "2026-01-01T00:00:01+00:00")
    store.store_message("system", "broadcast", {"n": 2}, "2026-01-01T00:00:02+00:00")
    store.store_message("alerts", "broadcast", {"n": 3}, "2026-01-01T00:00:03+00:00")
    messages, _ = store.query_history(channel="alerts")
    assert [m["payload"]["n"] for m in messages] == [1, 3]


def test_query_history_since_filter(tmp_path):
    store = MessageStore(path=str(tmp_path / "h.db"))
    store.store_message("alerts", "broadcast", {"n": 1}, "2026-01-01T00:00:01+00:00")
    store.store_message("alerts", "broadcast", {"n": 2}, "2026-01-01T00:00:02+00:00")
    store.store_message("alerts", "broadcast", {"n": 3}, "2026-01-01T00:00:03+00:00")
    messages, _ = store.query_history(
        channel="alerts", since="2026-01-01T00:00:02+00:00"
    )
    assert [m["payload"]["n"] for m in messages] == [2, 3]


def test_query_history_pagination_has_more(tmp_path):
    store = MessageStore(path=str(tmp_path / "h.db"))
    for i in range(5):
        store.store_message(
            "alerts", "broadcast", {"n": i}, f"2026-01-01T00:00:0{i}+00:00"
        )
    messages, has_more = store.query_history(channel="alerts", limit=2, offset=0)
    assert [m["payload"]["n"] for m in messages] == [0, 1]
    assert has_more is True

    messages, has_more = store.query_history(channel="alerts", limit=2, offset=2)
    assert [m["payload"]["n"] for m in messages] == [2, 3]
    assert has_more is True

    messages, has_more = store.query_history(channel="alerts", limit=2, offset=4)
    assert [m["payload"]["n"] for m in messages] == [4]
    assert has_more is False


# ── history REST endpoint ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_history_endpoint_returns_chronological(channel_name, tmp_path):
    srv = await _server(channel_name, tmp_path)
    try:
        srv.broadcast({"channel": "alerts", "n": 1})
        srv.broadcast({"channel": "alerts", "n": 2})
        srv.broadcast({"n": 3})
        async with httpx.AsyncClient() as http:
            r = await http.get(f"{http_uri(srv)}/history?channel=alerts")
            assert r.status_code == 200
            body = r.json()
            assert body["has_more"] is False
            assert [m["payload"]["n"] for m in body["messages"]] == [1, 2]
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_history_endpoint_since(channel_name, tmp_path):
    now = datetime.now(timezone.utc)
    ts = {
        n: (now - timedelta(seconds=4 - n)).isoformat() for n in (1, 2, 3)
    }
    store = MessageStore(path=str(tmp_path / "m.db"))
    srv = NotificationServer(port=0, channel=channel_name, store=store)
    await srv.start()
    try:
        store.store_message("alerts", "broadcast", {"n": 1}, ts[1])
        store.store_message("alerts", "broadcast", {"n": 2}, ts[2])
        store.store_message("alerts", "broadcast", {"n": 3}, ts[3])
        async with httpx.AsyncClient() as http:
            query = urlencode({"channel": "alerts", "since": ts[2]})
            r = await http.get(f"{http_uri(srv)}/history?{query}")
            body = r.json()
            assert [m["payload"]["n"] for m in body["messages"]] == [2, 3]
            assert body["has_more"] is False
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_history_endpoint_pagination_has_more(channel_name, tmp_path):
    srv = await _server(channel_name, tmp_path)
    try:
        for i in range(5):
            srv.broadcast({"channel": "alerts", "n": i})
        async with httpx.AsyncClient() as http:
            r = await http.get(f"{http_uri(srv)}/history?channel=alerts&limit=2")
            body = r.json()
            assert [m["payload"]["n"] for m in body["messages"]] == [0, 1]
            assert body["has_more"] is True

            r = await http.get(
                f"{http_uri(srv)}/history?channel=alerts&limit=2&offset=4"
            )
            body = r.json()
            assert [m["payload"]["n"] for m in body["messages"]] == [4]
            assert body["has_more"] is False
    finally:
        await srv.stop()


# ── message expiry / cleanup ────────────────────────────────────────────


def test_cleanup_expired_removes_old_messages(tmp_path):
    store = MessageStore(path=str(tmp_path / "c.db"))
    store.store_message("alerts", "broadcast", {"n": "old"}, "2020-01-01T00:00:00+00:00")
    store.store_message("alerts", "broadcast", {"n": "fresh"}, "2026-08-13T00:00:00+00:00")
    assert store.count() == 2
    removed = store.cleanup_expired(ttl_days=7)
    assert removed == 1
    remaining = store.list_messages()
    assert [m["payload"]["n"] for m in remaining] == ["fresh"]


def test_cleanup_uses_env_ttl(monkeypatch, tmp_path):
    monkeypatch.setenv("MESSAGE_TTL_DAYS", "1")
    store = MessageStore(path=str(tmp_path / "c.db"))
    store.store_message(None, "broadcast", {"n": 1}, "2020-01-01T00:00:00+00:00")
    store.store_message(None, "broadcast", {"n": 2}, "2026-08-13T00:00:00+00:00")
    assert store.cleanup_expired() == 1


@pytest.mark.asyncio
async def test_cleanup_runs_on_server_startup(channel_name, tmp_path):
    store = MessageStore(path=str(tmp_path / "m.db"))
    store.store_message("alerts", "broadcast", {"n": "old"}, "2020-01-01T00:00:00+00:00")
    store.store_message("alerts", "broadcast", {"n": "fresh"}, "2026-08-13T00:00:00+00:00")
    srv = NotificationServer(port=0, channel=channel_name, store=store)
    await srv.start()
    try:
        await asyncio.sleep(0.1)
        messages, _ = store.query_history(channel="alerts")
        assert [m["payload"]["n"] for m in messages] == ["fresh"]
    finally:
        await srv.stop()
