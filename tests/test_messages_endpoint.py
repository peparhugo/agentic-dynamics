import pytest
from aiohttp.test_utils import TestClient, TestServer

from notification_server.registry import ClientRegistry
from notification_server.soap import create_soap_app
from notification_server.store import MessageStore


@pytest.fixture
async def rest_client(tmp_path):
    registry = ClientRegistry()
    store = MessageStore(str(tmp_path / "messages.db"))
    app = create_soap_app(registry, store=store)
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    yield client, store
    await client.close()


async def test_get_messages_empty(rest_client):
    client, _store = rest_client
    resp = await client.get("/messages")
    assert resp.status == 200
    body = await resp.json()
    assert body == {"messages": []}


async def test_get_messages_returns_recorded_messages(rest_client):
    client, store = rest_client
    store.record("broadcast", {"text": "hi"}, "2026-01-01T00:00:00Z", channel="alerts")
    store.record("direct", {"text": "psst"}, "2026-01-01T00:00:01Z")

    resp = await client.get("/messages")
    assert resp.status == 200
    body = await resp.json()
    assert len(body["messages"]) == 2
    # most recent first
    assert body["messages"][0]["payload"]["text"] == "psst"
    assert body["messages"][1]["channel"] == "alerts"


async def test_get_messages_respects_limit_and_offset(rest_client):
    client, store = rest_client
    for i in range(5):
        store.record("broadcast", {"n": i}, f"2026-01-01T00:00:0{i}Z")

    resp = await client.get("/messages", params={"limit": "2", "offset": "1"})
    body = await resp.json()
    assert [m["payload"]["n"] for m in body["messages"]] == [3, 2]


async def test_get_messages_default_limit_is_50(rest_client):
    client, store = rest_client
    for i in range(60):
        store.record("broadcast", {"n": i}, "2026-01-01T00:00:00Z")

    resp = await client.get("/messages")
    body = await resp.json()
    assert len(body["messages"]) == 50


async def test_get_messages_rejects_non_integer_params(rest_client):
    client, _store = rest_client
    resp = await client.get("/messages", params={"limit": "abc"})
    assert resp.status == 400


async def test_get_messages_rejects_negative_params(rest_client):
    client, _store = rest_client
    resp = await client.get("/messages", params={"limit": "-1"})
    assert resp.status == 400


async def test_get_messages_without_store_returns_empty():
    registry = ClientRegistry()
    app = create_soap_app(registry)  # no store passed
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    try:
        resp = await client.get("/messages")
        assert resp.status == 200
        assert await resp.json() == {"messages": []}
    finally:
        await client.close()


# ── GET /history ─────────────────────────────────────────────────────


async def test_get_history_empty(rest_client):
    client, _store = rest_client
    resp = await client.get("/history", params={"channel": "alerts"})
    assert resp.status == 200
    body = await resp.json()
    assert body == {"messages": [], "has_more": False}


async def test_get_history_filters_by_channel_and_orders_chronologically(rest_client):
    client, store = rest_client
    store.record("broadcast", {"n": 1}, "2026-01-01T00:00:00Z", channel="alerts")
    store.record("broadcast", {"n": 2}, "2026-01-01T00:00:01Z", channel="other")
    store.record("broadcast", {"n": 3}, "2026-01-01T00:00:02Z", channel="alerts")

    resp = await client.get("/history", params={"channel": "alerts"})
    body = await resp.json()
    assert [m["payload"]["n"] for m in body["messages"]] == [1, 3]
    assert body["has_more"] is False


async def test_get_history_since_excludes_earlier_messages(rest_client):
    client, store = rest_client
    store.record("broadcast", {"n": 1}, "2026-01-01T00:00:00Z", channel="alerts")
    store.record("broadcast", {"n": 2}, "2026-01-01T00:00:01Z", channel="alerts")

    resp = await client.get(
        "/history", params={"channel": "alerts", "since": "2026-01-01T00:00:00Z"}
    )
    body = await resp.json()
    assert [m["payload"]["n"] for m in body["messages"]] == [2]


async def test_get_history_paginates_with_has_more(rest_client):
    client, store = rest_client
    for i in range(3):
        store.record("broadcast", {"n": i}, f"2026-01-01T00:00:0{i}Z", channel="alerts")

    resp = await client.get("/history", params={"channel": "alerts", "limit": "2"})
    body = await resp.json()
    assert [m["payload"]["n"] for m in body["messages"]] == [0, 1]
    assert body["has_more"] is True


async def test_get_history_default_limit_is_50(rest_client):
    client, store = rest_client
    for i in range(60):
        store.record("broadcast", {"n": i}, f"2026-01-01T00:{i:02d}:00Z", channel="alerts")

    resp = await client.get("/history", params={"channel": "alerts"})
    body = await resp.json()
    assert len(body["messages"]) == 50
    assert body["has_more"] is True


async def test_get_history_without_channel_returns_all_channels(rest_client):
    client, store = rest_client
    store.record("broadcast", {"text": "a"}, "2026-01-01T00:00:00Z", channel="alerts")
    store.record("direct", {"text": "b"}, "2026-01-01T00:00:01Z")

    resp = await client.get("/history")
    body = await resp.json()
    assert len(body["messages"]) == 2


async def test_get_history_rejects_non_integer_limit(rest_client):
    client, _store = rest_client
    resp = await client.get("/history", params={"limit": "abc"})
    assert resp.status == 400


async def test_get_history_rejects_negative_limit(rest_client):
    client, _store = rest_client
    resp = await client.get("/history", params={"limit": "-1"})
    assert resp.status == 400


async def test_get_history_rejects_malformed_since(rest_client):
    client, _store = rest_client
    resp = await client.get("/history", params={"since": "not-a-timestamp"})
    assert resp.status == 400


async def test_get_history_accepts_since_with_z_suffix(rest_client):
    client, store = rest_client
    store.record("broadcast", {"text": "hi"}, "2026-01-01T00:00:00Z", channel="alerts")
    resp = await client.get(
        "/history", params={"channel": "alerts", "since": "2025-12-31T00:00:00Z"}
    )
    assert resp.status == 200
    body = await resp.json()
    assert len(body["messages"]) == 1


async def test_get_history_without_store_returns_empty():
    registry = ClientRegistry()
    app = create_soap_app(registry)  # no store passed
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    try:
        resp = await client.get("/history", params={"channel": "alerts"})
        assert resp.status == 200
        assert await resp.json() == {"messages": [], "has_more": False}
    finally:
        await client.close()
