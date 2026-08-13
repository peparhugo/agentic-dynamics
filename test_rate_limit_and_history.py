"""Tests for per-client rate limiting, channel history queries, and
background expiry of old persisted messages.
"""

import asyncio
import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import pytest
from fakeredis import aioredis as fake_aioredis
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from notification_server import NotificationServer, create_app
from persistence import MessageStore
from rate_limiter import RateLimiter, default_rate_limiter


async def _recv_json(ws):
    return json.loads(await ws.recv())


def _fetch(url):
    with urllib.request.urlopen(url) as resp:
        return resp.status, json.loads(resp.read())


def _iso(delta: timedelta) -> str:
    return (datetime.now(timezone.utc) + delta).isoformat()


# ── unit tests: RateLimiter ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_rate_limiter_allows_up_to_limit():
    limiter = RateLimiter(fake_aioredis.FakeRedis(), limit=3)
    assert await limiter.check("client-a") is True
    assert await limiter.check("client-a") is True
    assert await limiter.check("client-a") is True


@pytest.mark.asyncio
async def test_rate_limiter_blocks_after_limit():
    limiter = RateLimiter(fake_aioredis.FakeRedis(), limit=2)
    assert await limiter.check("client-a") is True
    assert await limiter.check("client-a") is True
    assert await limiter.check("client-a") is False
    # stays blocked for further calls within the same window
    assert await limiter.check("client-a") is False


@pytest.mark.asyncio
async def test_rate_limiter_isolates_by_client_id():
    limiter = RateLimiter(fake_aioredis.FakeRedis(), limit=1)
    assert await limiter.check("client-a") is True
    assert await limiter.check("client-a") is False
    # a different client id has its own, unaffected quota
    assert await limiter.check("client-b") is True


def test_rate_limiter_default_limit_from_env(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "42")
    limiter = RateLimiter(fake_aioredis.FakeRedis())
    assert limiter.limit == 42


def test_rate_limiter_default_limit_is_100_without_env(monkeypatch):
    monkeypatch.delenv("RATE_LIMIT", raising=False)
    limiter = RateLimiter(fake_aioredis.FakeRedis())
    assert limiter.limit == 100


def test_default_rate_limiter_respects_explicit_limit():
    limiter = default_rate_limiter(limit=7)
    assert limiter.limit == 7


def test_create_app_rate_limit_configurable_via_env(monkeypatch, tmp_path):
    monkeypatch.setenv("RATE_LIMIT", "17")
    monkeypatch.delenv("REDIS_URL", raising=False)
    app = create_app(database_url=str(tmp_path / "messages.db"))
    assert app.rate_limiter.limit == 17


# ── integration tests: rate limiting over a real websocket ──────────────


@pytest.fixture
async def rate_limited_server():
    """A NotificationServer whose rate limiter trips after 2 messages/minute."""
    app = NotificationServer(rate_limiter=RateLimiter(fake_aioredis.FakeRedis(), limit=2))
    async with serve(app.handler, "localhost", 0, process_request=app.process_request) as server:
        port = server.sockets[0].getsockname()[1]
        yield app, f"ws://localhost:{port}"


@pytest.mark.asyncio
async def test_messages_within_limit_are_processed_normally(rate_limited_server):
    app, uri = rate_limited_server
    async with connect(uri) as ws:
        await _recv_json(ws)  # welcome

        await ws.send(json.dumps({"type": "broadcast", "payload": {"text": "one"}}))
        msg1 = await _recv_json(ws)
        assert msg1["type"] == "broadcast"

        await ws.send(json.dumps({"type": "broadcast", "payload": {"text": "two"}}))
        msg2 = await _recv_json(ws)
        assert msg2["payload"] == {"text": "two"}


@pytest.mark.asyncio
async def test_exceeding_rate_limit_returns_error_without_dropping_connection(rate_limited_server):
    app, uri = rate_limited_server
    async with connect(uri) as ws:
        await _recv_json(ws)  # welcome

        await ws.send(json.dumps({"type": "broadcast", "payload": {"text": "one"}}))
        await _recv_json(ws)
        await ws.send(json.dumps({"type": "broadcast", "payload": {"text": "two"}}))
        await _recv_json(ws)

        # third message this minute exceeds the limit of 2
        await ws.send(json.dumps({"type": "broadcast", "payload": {"text": "three"}}))
        err = await _recv_json(ws)
        assert err["type"] == "system"
        assert err["payload"]["event"] == "error"
        assert "rate limit" in err["payload"]["message"]

        # the connection itself is still alive — not dropped
        assert await app.registry.count() == 1


@pytest.mark.asyncio
async def test_rate_limit_is_per_client(rate_limited_server):
    app, uri = rate_limited_server
    async with connect(uri) as ws1, connect(uri) as ws2:
        await _recv_json(ws1)
        await _recv_json(ws2)

        # exhaust ws1's quota (each broadcast also reaches ws2, since neither
        # client is scoped to a channel here — drain those too)
        await ws1.send(json.dumps({"type": "broadcast", "payload": {"n": 1}}))
        await _recv_json(ws1)
        await _recv_json(ws2)
        await ws1.send(json.dumps({"type": "broadcast", "payload": {"n": 2}}))
        await _recv_json(ws1)
        await _recv_json(ws2)
        await ws1.send(json.dumps({"type": "broadcast", "payload": {"n": 3}}))
        err = await _recv_json(ws1)
        assert err["payload"]["event"] == "error"

        # ws2 still has its own quota untouched
        await ws2.send(json.dumps({"type": "broadcast", "payload": {"n": 4}}))
        got = await _recv_json(ws2)
        assert got["payload"] == {"n": 4}


# ── unit tests: MessageStore.list_by_channel (history) ──────────────────


@pytest.mark.asyncio
async def test_list_by_channel_filters_by_channel(tmp_path):
    store = MessageStore(str(tmp_path / "messages.db"))
    await store.save({"type": "broadcast", "payload": {"n": 1}, "timestamp": _iso(timedelta()), "channel": "alerts"})
    await store.save({"type": "broadcast", "payload": {"n": 2}, "timestamp": _iso(timedelta()), "channel": "chat"})

    messages, has_more = await store.list_by_channel("alerts", limit=50)
    assert len(messages) == 1
    assert messages[0]["payload"] == {"n": 1}
    assert has_more is False


@pytest.mark.asyncio
async def test_list_by_channel_returns_chronological_order(tmp_path):
    store = MessageStore(str(tmp_path / "messages.db"))
    for i in range(3):
        await store.save(
            {
                "type": "broadcast",
                "payload": {"n": i},
                "timestamp": _iso(timedelta(seconds=i)),
                "channel": "alerts",
            }
        )

    messages, _ = await store.list_by_channel("alerts", limit=50)
    assert [m["payload"]["n"] for m in messages] == [0, 1, 2]


@pytest.mark.asyncio
async def test_list_by_channel_since_excludes_older_messages(tmp_path):
    store = MessageStore(str(tmp_path / "messages.db"))
    older = _iso(timedelta(minutes=-10))
    cutoff = _iso(timedelta(minutes=-5))
    newer = _iso(timedelta())

    await store.save({"type": "broadcast", "payload": {"which": "older"}, "timestamp": older, "channel": "alerts"})
    await store.save({"type": "broadcast", "payload": {"which": "newer"}, "timestamp": newer, "channel": "alerts"})

    messages, _ = await store.list_by_channel("alerts", since=cutoff, limit=50)
    assert len(messages) == 1
    assert messages[0]["payload"] == {"which": "newer"}


@pytest.mark.asyncio
async def test_list_by_channel_has_more_true_when_extra_rows_exist(tmp_path):
    store = MessageStore(str(tmp_path / "messages.db"))
    for i in range(5):
        await store.save(
            {
                "type": "broadcast",
                "payload": {"n": i},
                "timestamp": _iso(timedelta(seconds=i)),
                "channel": "alerts",
            }
        )

    page, has_more = await store.list_by_channel("alerts", limit=3)
    assert [m["payload"]["n"] for m in page] == [0, 1, 2]
    assert has_more is True

    rest, has_more2 = await store.list_by_channel("alerts", since=page[-1]["timestamp"], limit=3)
    assert [m["payload"]["n"] for m in rest] == [3, 4]
    assert has_more2 is False


# ── integration tests: GET /history endpoint ─────────────────────────────


@pytest.mark.asyncio
async def test_history_endpoint_returns_channel_messages(tmp_path):
    store = MessageStore(str(tmp_path / "messages.db"))
    app = NotificationServer(message_store=store)

    async with serve(app.handler, "localhost", 0, process_request=app.process_request) as server:
        port = server.sockets[0].getsockname()[1]
        async with connect(f"ws://localhost:{port}") as ws:
            await _recv_json(ws)  # welcome
            # subscribe to both channels so every broadcast below is echoed
            # back, which lets us know the server has finished persisting it
            # before we query /history
            await ws.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
            await _recv_json(ws)  # ack
            await ws.send(json.dumps({"type": "subscribe", "channel": "other"}))
            await _recv_json(ws)  # ack

            await ws.send(json.dumps({"type": "broadcast", "channel": "alerts", "payload": {"text": "first"}}))
            await _recv_json(ws)
            await ws.send(json.dumps({"type": "broadcast", "channel": "alerts", "payload": {"text": "second"}}))
            await _recv_json(ws)
            await ws.send(json.dumps({"type": "broadcast", "channel": "other", "payload": {"text": "elsewhere"}}))
            await _recv_json(ws)

        http_uri = f"http://localhost:{port}/history?channel=alerts&limit=50"
        status, data = await asyncio.to_thread(_fetch, http_uri)

        assert status == 200
        assert data["channel"] == "alerts"
        assert data["has_more"] is False
        assert [m["payload"] for m in data["messages"]] == [{"text": "first"}, {"text": "second"}]


@pytest.mark.asyncio
async def test_history_endpoint_requires_channel(tmp_path):
    store = MessageStore(str(tmp_path / "messages.db"))
    app = NotificationServer(message_store=store)

    async with serve(app.handler, "localhost", 0, process_request=app.process_request) as server:
        port = server.sockets[0].getsockname()[1]
        http_uri = f"http://localhost:{port}/history?limit=10"

        def fetch():
            try:
                with urllib.request.urlopen(http_uri) as resp:
                    return resp.status, json.loads(resp.read())
            except urllib.error.HTTPError as e:
                return e.code, json.loads(e.read())

        status, data = await asyncio.to_thread(fetch)
        assert status == 400
        assert "error" in data


@pytest.mark.asyncio
async def test_history_endpoint_since_filters_and_paginates(tmp_path):
    store = MessageStore(str(tmp_path / "messages.db"))
    app = NotificationServer(message_store=store)
    for i in range(3):
        await store.save(
            {
                "type": "broadcast",
                "payload": {"n": i},
                "timestamp": _iso(timedelta(seconds=i)),
                "channel": "alerts",
            }
        )

    async with serve(app.handler, "localhost", 0, process_request=app.process_request) as server:
        port = server.sockets[0].getsockname()[1]

        status, page1 = await asyncio.to_thread(
            _fetch, f"http://localhost:{port}/history?channel=alerts&limit=2"
        )
        assert status == 200
        assert [m["payload"]["n"] for m in page1["messages"]] == [0, 1]
        assert page1["has_more"] is True

        since = urllib.parse.quote(page1["messages"][-1]["timestamp"], safe="")
        status, page2 = await asyncio.to_thread(
            _fetch, f"http://localhost:{port}/history?channel=alerts&since={since}&limit=2"
        )
        assert status == 200
        assert [m["payload"]["n"] for m in page2["messages"]] == [2]
        assert page2["has_more"] is False


# ── unit tests: MessageStore.delete_older_than (expiry) ──────────────────


@pytest.mark.asyncio
async def test_delete_older_than_removes_only_old_messages(tmp_path):
    store = MessageStore(str(tmp_path / "messages.db"))
    old_ts = _iso(timedelta(days=-8))
    recent_ts = _iso(timedelta(days=-1))

    await store.save({"type": "broadcast", "payload": {"which": "old"}, "timestamp": old_ts, "channel": "alerts"})
    await store.save(
        {"type": "broadcast", "payload": {"which": "recent"}, "timestamp": recent_ts, "channel": "alerts"}
    )

    cutoff = _iso(timedelta(days=-7))
    deleted = await store.delete_older_than(cutoff)

    assert deleted == 1
    remaining = await store.list_messages(limit=10)
    assert len(remaining) == 1
    assert remaining[0]["payload"] == {"which": "recent"}


# ── integration tests: background expiry on NotificationServer ─────────


@pytest.mark.asyncio
async def test_cleanup_expired_messages_purges_old_rows(tmp_path):
    store = MessageStore(str(tmp_path / "messages.db"))
    app = NotificationServer(message_store=store, message_ttl_days=7)

    old_ts = _iso(timedelta(days=-8))
    recent_ts = _iso(timedelta(minutes=-1))
    await store.save({"type": "broadcast", "payload": {"which": "old"}, "timestamp": old_ts, "channel": "alerts"})
    await store.save(
        {"type": "broadcast", "payload": {"which": "recent"}, "timestamp": recent_ts, "channel": "alerts"}
    )

    deleted = await app._cleanup_expired_messages()

    assert deleted == 1
    remaining = await store.list_messages(limit=10)
    assert [m["payload"]["which"] for m in remaining] == ["recent"]


@pytest.mark.asyncio
async def test_cleanup_runs_automatically_on_start(tmp_path):
    store = MessageStore(str(tmp_path / "messages.db"))
    app = NotificationServer(message_store=store, message_ttl_days=7, cleanup_interval_seconds=10)

    old_ts = _iso(timedelta(days=-30))
    await store.save({"type": "broadcast", "payload": {"which": "old"}, "timestamp": old_ts, "channel": "alerts"})

    await app.start()
    try:
        for _ in range(50):
            remaining = await store.list_messages(limit=10)
            if not remaining:
                break
            await asyncio.sleep(0.02)
        assert remaining == []
    finally:
        await app.stop()


def test_message_ttl_configurable_via_env(monkeypatch):
    monkeypatch.setenv("MESSAGE_TTL_DAYS", "3")
    app = NotificationServer()
    assert app.message_ttl_days == 3
