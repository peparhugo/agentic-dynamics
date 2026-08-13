import asyncio
import json
import urllib.parse

import fakeredis
import pytest
import pytest_asyncio
from websockets.asyncio.client import connect

from notification_server import (
    BROADCAST,
    ERROR,
    MessageStore,
    NotificationServer,
    REDIS_RATE_LIMIT_PREFIX,
    utc_now_iso,
)

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def redis_client():
    client = fakeredis.FakeAsyncRedis(decode_responses=True)
    yield client
    await client.aclose()


async def make_server(redis_client=None, database_url=None, **kwargs):
    srv = NotificationServer(
        host="127.0.0.1",
        port=0,
        redis_client=redis_client,
        database_url=database_url,
        **kwargs,
    )
    await srv.start()
    return srv


async def open_client(server):
    ws = await connect(f"ws://127.0.0.1:{server.port}")
    welcome = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
    return ws, welcome


async def http_get(port, path="/health"):
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(
        f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n".encode()
    )
    await writer.drain()
    data = await reader.read()
    writer.close()
    await writer.wait_closed()
    return data


async def recv_all(ws, timeout=0.4):
    messages = []
    while True:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
            messages.append(json.loads(raw))
        except asyncio.TimeoutError:
            return messages


# -- rate limiting: defaults & configuration -------------------------------


async def test_rate_limit_default_is_100():
    srv = NotificationServer(host="127.0.0.1", port=0)
    try:
        assert srv.rate_limiter.limit == 100
        assert srv.rate_limiter.enabled
    finally:
        await srv.close()


async def test_rate_limit_env(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "5")
    srv = NotificationServer(host="127.0.0.1", port=0)
    try:
        assert srv.rate_limiter.limit == 5
    finally:
        await srv.close()


async def test_rate_limit_zero_disables():
    srv = NotificationServer(host="127.0.0.1", port=0, rate_limit=0)
    await srv.start()
    try:
        assert srv.rate_limiter.enabled is False
        ws, _ = await open_client(srv)
        for i in range(5):
            await ws.send(json.dumps({
                "type": BROADCAST,
                "payload": {"text": f"m{i}"},
            }))
        received = await recv_all(ws, timeout=0.5)
        assert len(received) == 5
        assert all(m["type"] == BROADCAST for m in received)
        await ws.close()
    finally:
        await srv.close()


# -- rate limiting: enforcement (in-memory counters) -----------------------


async def test_rate_limit_exceeded_returns_error_no_drop():
    srv = await make_server(rate_limit=3)
    try:
        ws_a, _ = await open_client(srv)
        ws_b, _ = await open_client(srv)

        for i in range(4):
            await ws_a.send(json.dumps({
                "type": BROADCAST,
                "payload": {"text": f"m{i}"},
            }))

        b_received = await recv_all(ws_b, timeout=0.6)
        b_broadcasts = [m for m in b_received if m["type"] == BROADCAST]
        assert [m["payload"]["text"] for m in b_broadcasts] == ["m0", "m1", "m2"]

        a_received = await recv_all(ws_a, timeout=0.6)
        a_broadcasts = [m for m in a_received if m["type"] == BROADCAST]
        a_errors = [m for m in a_received if m["type"] == ERROR]
        assert [m["payload"]["text"] for m in a_broadcasts] == ["m0", "m1", "m2"]
        assert len(a_errors) == 1
        assert a_errors[0]["payload"]["message"] == "rate limit exceeded"
        assert a_errors[0]["payload"]["limit"] == 3

        await ws_a.close()
        await ws_b.close()
    finally:
        await srv.close()


async def test_rate_limit_is_per_client():
    srv = await make_server(rate_limit=2)
    try:
        ws_a, _ = await open_client(srv)
        ws_b, _ = await open_client(srv)

        for i in range(3):
            await ws_a.send(json.dumps({
                "type": BROADCAST,
                "payload": {"text": f"a{i}"},
            }))
        await ws_b.send(json.dumps({
            "type": BROADCAST,
            "payload": {"text": "b0"},
        }))

        b_received = await recv_all(ws_b, timeout=0.6)
        assert all(m["type"] == BROADCAST for m in b_received)
        assert len(b_received) == 3

        a_received = await recv_all(ws_a, timeout=0.6)
        assert any(m["type"] == ERROR for m in a_received)
        a_broadcasts = [m for m in a_received if m["type"] == BROADCAST]
        assert len(a_broadcasts) == 3

        await ws_a.close()
        await ws_b.close()
    finally:
        await srv.close()


# -- rate limiting: Redis counters -----------------------------------------


async def test_rate_limit_uses_redis_counter(redis_client):
    srv = await make_server(redis_client=redis_client, rate_limit=2)
    try:
        ws, welcome = await open_client(srv)
        client_id = welcome["payload"]["client_id"]

        for i in range(3):
            await ws.send(json.dumps({
                "type": BROADCAST,
                "payload": {"text": f"m{i}"},
            }))

        received = await recv_all(ws, timeout=0.6)
        assert len([m for m in received if m["type"] == BROADCAST]) == 2
        assert len([m for m in received if m["type"] == ERROR]) == 1

        keys = await redis_client.keys(f"{REDIS_RATE_LIMIT_PREFIX}{client_id}:*")
        assert len(keys) == 1
        count = int(await redis_client.get(keys[0]))
        assert count == 3

        await ws.close()
    finally:
        await srv.close()


async def test_rate_limit_counters_reset_between_windows(monkeypatch):
    srv = await make_server(rate_limit=2)
    try:
        ws, welcome = await open_client(srv)
        client_id = welcome["payload"]["client_id"]

        for i in range(3):
            await ws.send(json.dumps({
                "type": BROADCAST,
                "payload": {"text": f"m{i}"},
            }))
        received = await recv_all(ws, timeout=0.5)
        assert len([m for m in received if m["type"] == ERROR]) == 1

        future_window = int(
            __import__("time").time() + 61
        ) // 60
        srv.rate_limiter._local[client_id] = (0, future_window)

        await ws.send(json.dumps({
            "type": BROADCAST,
            "payload": {"text": "m3"},
        }))
        received = await recv_all(ws, timeout=0.5)
        assert all(m["type"] == BROADCAST for m in received)
        assert len(received) == 1

        await ws.close()
    finally:
        await srv.close()


# -- history: store-level queries ------------------------------------------


async def test_history_returns_chronological_and_filters(tmp_path):
    db = tmp_path / "history.db"
    srv = await make_server(database_url=db)
    try:
        store = srv.message_store
        store.store(BROADCAST, "alerts", {"text": "a0"}, "2026-08-13T00:00:00.000+00:00")
        store.store(BROADCAST, None, {"text": "g"}, "2026-08-13T00:00:01.000+00:00")
        store.store(BROADCAST, "alerts", {"text": "a1"}, "2026-08-13T00:00:02.000+00:00")
        store.store(BROADCAST, "alerts", {"text": "a2"}, "2026-08-13T00:00:03.000+00:00")

        result = store.history(channel="alerts")
        assert [m["payload"]["text"] for m in result["messages"]] == ["a0", "a1", "a2"]
        assert result["has_more"] is False

        result = store.history(channel="alerts", since="2026-08-13T00:00:02.000+00:00")
        assert [m["payload"]["text"] for m in result["messages"]] == ["a1", "a2"]

        result = store.history()
        assert [m["payload"]["text"] for m in result["messages"]] == ["a0", "g", "a1", "a2"]
    finally:
        await srv.close()


async def test_history_pagination_has_more(tmp_path):
    db = tmp_path / "history.db"
    srv = await make_server(database_url=db)
    try:
        store = srv.message_store
        for i in range(5):
            store.store(
                BROADCAST, "alerts", {"text": f"m{i}"},
                f"2026-08-13T00:00:0{i}.000+00:00",
            )

        page = store.history(channel="alerts", limit=2, offset=0)
        assert [m["payload"]["text"] for m in page["messages"]] == ["m0", "m1"]
        assert page["has_more"] is True

        page = store.history(channel="alerts", limit=2, offset=2)
        assert [m["payload"]["text"] for m in page["messages"]] == ["m2", "m3"]
        assert page["has_more"] is True

        page = store.history(channel="alerts", limit=2, offset=4)
        assert [m["payload"]["text"] for m in page["messages"]] == ["m4"]
        assert page["has_more"] is False
    finally:
        await srv.close()


async def test_history_without_store_returns_empty():
    srv = await make_server(database_url=None)
    try:
        result = srv.message_store.history(channel="alerts")
        assert result == {"messages": [], "has_more": False}
    finally:
        await srv.close()


# -- history: REST endpoint -------------------------------------------------


async def test_history_endpoint_filters_channel_and_since(tmp_path):
    db = tmp_path / "history.db"
    srv = await make_server(database_url=db)
    try:
        store = srv.message_store
        store.store(BROADCAST, "alerts", {"text": "a0"}, "2026-08-13T00:00:00.000+00:00")
        store.store(BROADCAST, None, {"text": "g"}, "2026-08-13T00:00:01.000+00:00")
        store.store(BROADCAST, "alerts", {"text": "a1"}, "2026-08-13T00:00:02.000+00:00")

        raw = await http_get(srv.port, "/history?channel=alerts")
        status = raw.split(b" ", 2)[1].decode()
        body = raw.split(b"\r\n\r\n", 1)[1]
        payload = json.loads(body)
        assert status == "200"
        assert payload["has_more"] is False
        assert payload["channel"] == "alerts"
        assert [m["payload"]["text"] for m in payload["messages"]] == ["a0", "a1"]

        since = urllib.parse.quote("2026-08-13T00:00:02.000+00:00", safe="")
        raw = await http_get(srv.port, f"/history?channel=alerts&since={since}")
        body = raw.split(b"\r\n\r\n", 1)[1]
        payload = json.loads(body)
        assert [m["payload"]["text"] for m in payload["messages"]] == ["a1"]
    finally:
        await srv.close()


async def test_history_endpoint_pagination(tmp_path):
    db = tmp_path / "history.db"
    srv = await make_server(database_url=db)
    try:
        store = srv.message_store
        for i in range(5):
            store.store(
                BROADCAST, "alerts", {"text": f"m{i}"},
                f"2026-08-13T00:00:0{i}.000+00:00",
            )

        raw = await http_get(srv.port, "/history?channel=alerts&limit=2")
        payload = json.loads(raw.split(b"\r\n\r\n", 1)[1])
        assert payload["limit"] == 2
        assert payload["offset"] == 0
        assert [m["payload"]["text"] for m in payload["messages"]] == ["m0", "m1"]
        assert payload["has_more"] is True

        raw = await http_get(srv.port, "/history?channel=alerts&limit=2&offset=2")
        payload = json.loads(raw.split(b"\r\n\r\n", 1)[1])
        assert [m["payload"]["text"] for m in payload["messages"]] == ["m2", "m3"]
        assert payload["has_more"] is True

        raw = await http_get(srv.port, "/history?channel=alerts&limit=2&offset=4")
        payload = json.loads(raw.split(b"\r\n\r\n", 1)[1])
        assert [m["payload"]["text"] for m in payload["messages"]] == ["m4"]
        assert payload["has_more"] is False
    finally:
        await srv.close()


async def test_history_default_limit_50(tmp_path):
    db = tmp_path / "history.db"
    srv = await make_server(database_url=db)
    try:
        raw = await http_get(srv.port, "/history?channel=alerts")
        payload = json.loads(raw.split(b"\r\n\r\n", 1)[1])
        assert payload["limit"] == 50
        assert payload["messages"] == []
        assert payload["has_more"] is False
    finally:
        await srv.close()


# -- message expiry ----------------------------------------------------------


async def test_expired_messages_purged_on_startup(tmp_path):
    db = tmp_path / "history.db"
    store = MessageStore(db)
    store.store(BROADCAST, "alerts", {"text": "old"}, "2020-01-01T00:00:00.000+00:00")
    store.store(BROADCAST, "alerts", {"text": "new"}, utc_now_iso())
    assert store.count() == 2

    srv = await make_server(database_url=db)
    try:
        assert store.count() == 1
        rows = store.list(limit=10, offset=0)
        assert rows[0]["payload"]["text"] == "new"
    finally:
        await srv.close()


async def test_purge_honors_ttl(tmp_path):
    db = tmp_path / "history.db"
    store = MessageStore(db)
    store.store(BROADCAST, "alerts", {"text": "old"}, "2026-08-01T00:00:00.000+00:00")
    store.store(BROADCAST, "alerts", {"text": "mid"}, "2026-08-10T00:00:00.000+00:00")
    store.store(BROADCAST, "alerts", {"text": "new"}, utc_now_iso())

    removed = store.purge(ttl_days=7)
    assert removed == 1
    texts = {r["payload"]["text"] for r in store.list(limit=10, offset=0)}
    assert texts == {"mid", "new"}


async def test_message_ttl_env(monkeypatch):
    monkeypatch.setenv("MESSAGE_TTL_DAYS", "3")
    srv = NotificationServer(host="127.0.0.1", port=0)
    try:
        assert srv.message_ttl_days == 3
    finally:
        await srv.close()


async def test_purge_background_task_loops(tmp_path):
    db = tmp_path / "history.db"
    store = MessageStore(db)
    store.store(BROADCAST, "alerts", {"text": "old"}, "2020-01-01T00:00:00.000+00:00")

    srv = await make_server(database_url=db, cleanup_interval=0.05)
    try:
        assert store.count() == 0

        store.store(BROADCAST, "alerts", {"text": "stale"}, "2020-01-01T00:00:00.000+00:00")
        assert store.count() == 1
        for _ in range(50):
            if store.count() == 0:
                break
            await asyncio.sleep(0.05)
        assert store.count() == 0
    finally:
        await srv.close()
