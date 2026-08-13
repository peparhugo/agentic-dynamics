"""
Integration tests for the Redis pub/sub backbone and SQLite message
persistence layered on top of NotificationServer.

Redis is simulated with fakeredis so these tests run without a real
Redis server; multiple NotificationServer "instances" share one
fakeredis.aioredis.FakeServer, which is what lets a broadcast published
by one instance fan out to clients connected to a different instance —
exactly like separate server processes sharing a real Redis broker.
"""

import asyncio
import json
import urllib.request

import pytest
from fakeredis import aioredis as fake_aioredis
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from notification_server import NotificationServer
from persistence import MessageStore
from redis_backbone import RedisBackbone


async def _recv_json(ws):
    return json.loads(await ws.recv())


def make_backbone(shared_server, server_id):
    client = fake_aioredis.FakeRedis(server=shared_server)
    return RedisBackbone(client, server_id=server_id)


@pytest.fixture
async def redis_pair(tmp_path):
    """Two NotificationServer instances, each with its own websocket
    listener and its own Redis connection, sharing one fake Redis broker."""
    shared_server = fake_aioredis.FakeServer()

    db_a = MessageStore(str(tmp_path / "a.db"))
    db_b = MessageStore(str(tmp_path / "b.db"))

    app_a = NotificationServer(
        redis_backbone=make_backbone(shared_server, "server-a"),
        message_store=db_a,
        server_id="server-a",
    )
    app_b = NotificationServer(
        redis_backbone=make_backbone(shared_server, "server-b"),
        message_store=db_b,
        server_id="server-b",
    )
    await app_a.start()
    await app_b.start()

    async with serve(app_a.handler, "localhost", 0, process_request=app_a.process_request) as srv_a, \
            serve(app_b.handler, "localhost", 0, process_request=app_b.process_request) as srv_b:
        port_a = srv_a.sockets[0].getsockname()[1]
        port_b = srv_b.sockets[0].getsockname()[1]
        try:
            yield app_a, f"ws://localhost:{port_a}", app_b, f"ws://localhost:{port_b}"
        finally:
            await app_a.stop()
            await app_b.stop()


@pytest.fixture
async def redis_single(tmp_path):
    """A single NotificationServer instance wired to a fake Redis broker."""
    shared_server = fake_aioredis.FakeServer()
    db = MessageStore(str(tmp_path / "single.db"))
    app = NotificationServer(
        redis_backbone=make_backbone(shared_server, "server-solo"),
        message_store=db,
        server_id="server-solo",
    )
    await app.start()
    async with serve(app.handler, "localhost", 0, process_request=app.process_request) as server:
        port = server.sockets[0].getsockname()[1]
        try:
            yield app, f"ws://localhost:{port}"
        finally:
            await app.stop()


# ── pub/sub fan-out across instances ─────────────────────────────────


@pytest.mark.asyncio
async def test_broadcast_fans_out_across_server_instances(redis_pair):
    app_a, uri_a, app_b, uri_b = redis_pair

    async with connect(uri_a) as ws_a, connect(uri_b) as ws_b:
        await _recv_json(ws_a)  # welcome
        await _recv_json(ws_b)  # welcome

        await ws_a.send(json.dumps({"type": "broadcast", "payload": {"text": "hi everyone"}}))

        msg_a = await asyncio.wait_for(_recv_json(ws_a), timeout=2)
        msg_b = await asyncio.wait_for(_recv_json(ws_b), timeout=2)

        assert msg_a["payload"] == {"text": "hi everyone"}
        assert msg_b == msg_a


@pytest.mark.asyncio
async def test_channel_broadcast_fans_out_to_subscriber_on_other_instance(redis_pair):
    app_a, uri_a, app_b, uri_b = redis_pair

    async with connect(uri_a) as ws_a, connect(uri_b) as ws_b:
        await _recv_json(ws_a)
        await _recv_json(ws_b)

        await ws_b.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        await _recv_json(ws_b)  # ack

        await ws_a.send(
            json.dumps({"type": "broadcast", "channel": "alerts", "payload": {"text": "fire"}})
        )

        msg_b = await asyncio.wait_for(_recv_json(ws_b), timeout=2)
        assert msg_b["payload"] == {"text": "fire"}
        assert msg_b["channel"] == "alerts"


@pytest.mark.asyncio
async def test_no_duplicate_delivery_on_originating_instance(redis_pair):
    app_a, uri_a, app_b, uri_b = redis_pair

    async with connect(uri_a) as ws1, connect(uri_a) as ws2:
        await _recv_json(ws1)
        await _recv_json(ws2)

        await ws1.send(json.dumps({"type": "broadcast", "payload": {"text": "once"}}))

        got1 = await asyncio.wait_for(_recv_json(ws1), timeout=2)
        got2 = await asyncio.wait_for(_recv_json(ws2), timeout=2)
        assert got1["payload"] == {"text": "once"}
        assert got2 == got1

        # no extra copy should arrive via the redis fan-out loopback
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws1.recv(), timeout=0.3)


@pytest.mark.asyncio
async def test_direct_message_routes_to_client_on_other_instance(redis_pair):
    app_a, uri_a, app_b, uri_b = redis_pair

    async with connect(uri_a) as ws_a, connect(uri_b) as ws_b:
        welcome_b = await _recv_json(ws_b)
        await _recv_json(ws_a)
        target_id = welcome_b["payload"]["client_id"]

        await ws_a.send(
            json.dumps(
                {
                    "type": "direct",
                    "payload": {"client_id": target_id, "payload": {"text": "just for you"}},
                }
            )
        )

        got = await asyncio.wait_for(_recv_json(ws_b), timeout=2)
        assert got["type"] == "direct"
        assert got["payload"] == {"text": "just for you"}


# ── client connection state in redis ─────────────────────────────────


@pytest.mark.asyncio
async def test_client_state_stored_in_redis_on_connect(redis_single):
    app, uri = redis_single
    async with connect(uri) as ws:
        welcome = await _recv_json(ws)
        client_id = welcome["payload"]["client_id"]

        state = await app.redis_backbone.get_client_state(client_id)
        assert state is not None
        assert state["server_id"] == "server-solo"
        assert await app.redis_backbone.active_client_count() == 1


@pytest.mark.asyncio
async def test_client_state_cleared_from_redis_on_disconnect(redis_single):
    app, uri = redis_single
    ws = await connect(uri)
    welcome = await _recv_json(ws)
    client_id = welcome["payload"]["client_id"]
    await ws.close()

    for _ in range(50):
        state = await app.redis_backbone.get_client_state(client_id)
        if state is None:
            break
        await asyncio.sleep(0.02)

    assert await app.redis_backbone.get_client_state(client_id) is None
    assert await app.redis_backbone.active_client_count() == 0


# ── SQLite message persistence ───────────────────────────────────────


@pytest.mark.asyncio
async def test_broadcast_persists_message_to_sqlite(tmp_path):
    store = MessageStore(str(tmp_path / "messages.db"))
    app = NotificationServer(message_store=store)

    await app.broadcast({"text": "persisted"}, channel="alerts")

    rows = await store.list_messages(limit=10, offset=0)
    assert len(rows) == 1
    assert rows[0]["type"] == "broadcast"
    assert rows[0]["channel"] == "alerts"
    assert rows[0]["payload"] == {"text": "persisted"}
    assert "timestamp" in rows[0]


@pytest.mark.asyncio
async def test_direct_message_persists_to_sqlite(tmp_path):
    store = MessageStore(str(tmp_path / "messages.db"))
    app = NotificationServer(message_store=store)

    await app.send_direct("some-client", {"text": "hello"})

    rows = await store.list_messages(limit=10, offset=0)
    assert len(rows) == 1
    assert rows[0]["type"] == "direct"
    assert rows[0]["payload"] == {"text": "hello"}


@pytest.mark.asyncio
async def test_message_store_respects_limit_and_offset(tmp_path):
    store = MessageStore(str(tmp_path / "messages.db"))
    app = NotificationServer(message_store=store)

    for i in range(5):
        await app.broadcast({"n": i})

    page1 = await store.list_messages(limit=2, offset=0)
    page2 = await store.list_messages(limit=2, offset=2)

    assert [m["payload"]["n"] for m in page1] == [4, 3]
    assert [m["payload"]["n"] for m in page2] == [2, 1]


# ── GET /messages REST endpoint ──────────────────────────────────────


@pytest.mark.asyncio
async def test_messages_endpoint_returns_persisted_history(tmp_path):
    store = MessageStore(str(tmp_path / "messages.db"))
    app = NotificationServer(message_store=store)

    async with serve(app.handler, "localhost", 0, process_request=app.process_request) as server:
        port = server.sockets[0].getsockname()[1]
        uri = f"ws://localhost:{port}"

        async with connect(uri) as ws:
            await _recv_json(ws)  # welcome
            await ws.send(json.dumps({"type": "broadcast", "payload": {"text": "first"}}))
            await _recv_json(ws)
            await ws.send(json.dumps({"type": "broadcast", "payload": {"text": "second"}}))
            await _recv_json(ws)

        http_uri = f"http://localhost:{port}/messages?limit=50&offset=0"

        def fetch():
            with urllib.request.urlopen(http_uri) as resp:
                return resp.status, json.loads(resp.read())

        status, data = await asyncio.to_thread(fetch)
        assert status == 200
        assert data["limit"] == 50
        assert data["offset"] == 0
        assert len(data["messages"]) == 2
        assert data["messages"][0]["payload"] == {"text": "second"}
        assert data["messages"][1]["payload"] == {"text": "first"}


@pytest.mark.asyncio
async def test_messages_endpoint_without_message_store_returns_empty(tmp_path):
    app = NotificationServer()

    async with serve(app.handler, "localhost", 0, process_request=app.process_request) as server:
        port = server.sockets[0].getsockname()[1]
        http_uri = f"http://localhost:{port}/messages"

        def fetch():
            with urllib.request.urlopen(http_uri) as resp:
                return resp.status, json.loads(resp.read())

        status, data = await asyncio.to_thread(fetch)
        assert status == 200
        assert data["messages"] == []


@pytest.mark.asyncio
async def test_messages_endpoint_paginates_with_query_params(tmp_path):
    store = MessageStore(str(tmp_path / "messages.db"))
    app = NotificationServer(message_store=store)
    for i in range(3):
        await app.broadcast({"n": i})

    async with serve(app.handler, "localhost", 0, process_request=app.process_request) as server:
        port = server.sockets[0].getsockname()[1]
        http_uri = f"http://localhost:{port}/messages?limit=1&offset=1"

        def fetch():
            with urllib.request.urlopen(http_uri) as resp:
                return resp.status, json.loads(resp.read())

        status, data = await asyncio.to_thread(fetch)
        assert status == 200
        assert data["limit"] == 1
        assert data["offset"] == 1
        assert len(data["messages"]) == 1
        assert data["messages"][0]["payload"] == {"n": 1}
