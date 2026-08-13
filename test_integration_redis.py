"""Integration tests for the Redis pub/sub backbone and SQLite persistence."""

import asyncio
import json
import os
import uuid

import pytest
from websockets.asyncio.client import connect

from message_store import MessageStore
from notification_server import NotificationApp, now_iso
from redis_backend import RedisBackend

REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6399/0")


@pytest.fixture
async def backend():
    instance = RedisBackend(REDIS_URL, namespace=f"notify_it_{uuid.uuid4().hex}")
    await instance.connect()
    try:
        yield instance
    finally:
        await instance.close()


@pytest.fixture
async def store(tmp_path):
    instance = MessageStore(str(tmp_path / "messages.db"))
    await instance.connect()
    try:
        yield instance
    finally:
        await instance.close()


@pytest.fixture
async def app_pair(backend, store):
    app1 = NotificationApp(backend=backend, store=store)
    app2 = NotificationApp(backend=backend, store=store)
    await app1.start()
    await app2.start()
    try:
        yield app1, app2
    finally:
        await app1.stop()
        await app2.stop()


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


async def wait_for_pubsub_message(pubsub, timeout=5.0):
    """Block until a pub/sub 'message' arrives; return the parsed envelope."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        msg = await pubsub.get_message(ignore_subscribe_messages=True)
        if msg is not None and msg.get("type") == "message":
            return json.loads(msg["data"])
        await asyncio.sleep(0.02)
    raise AssertionError("no pub/sub message received")


# ── Redis pub/sub backbone ──────────────────────────────────────────────


async def test_broadcast_cross_instance_via_redis(app_pair):
    app1, app2 = app_pair
    ws_a, _ = await connect_client(app1)
    ws_b, _ = await connect_client(app2)
    try:
        payload = {"text": "hello from a", "via": "redis"}
        await ws_a.send(json.dumps({"type": "broadcast", "payload": payload}))
        for ws in (ws_a, ws_b):
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            assert msg["type"] == "broadcast"
            assert msg["payload"] == payload
    finally:
        await ws_a.close()
        await ws_b.close()


async def test_channel_routing_across_instances(app_pair):
    app1, app2 = app_pair
    ws_a, _ = await connect_client(app1)
    ws_b, _ = await connect_client(app2)
    ws_c, _ = await connect_client(app2)
    try:
        await ws_a.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        await ws_b.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        await ws_c.send(json.dumps({"type": "subscribe", "channel": "chat"}))
        await asyncio.sleep(0.3)

        payload = {"text": "alert across"}
        await ws_a.send(
            json.dumps({"type": "broadcast", "channel": "alerts", "payload": payload})
        )
        for ws in (ws_a, ws_b):
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            assert msg["type"] == "broadcast"
            assert msg["payload"] == payload
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws_c.recv(), timeout=0.3)
    finally:
        await ws_a.close()
        await ws_b.close()
        await ws_c.close()


async def test_direct_message_across_instances(app_pair):
    app1, app2 = app_pair
    ws_a, _ = await connect_client(app1)
    ws_b, id_b = await connect_client(app2)
    try:
        payload = {"text": "private across"}
        await ws_a.send(
            json.dumps({"type": "direct", "target_id": id_b, "payload": payload})
        )
        msg = json.loads(await asyncio.wait_for(ws_b.recv(), timeout=5))
        assert msg["type"] == "direct"
        assert msg["payload"] == payload
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws_a.recv(), timeout=0.3)
    finally:
        await ws_a.close()
        await ws_b.close()


async def test_server_publishes_to_redis_channel(backend, store):
    app = NotificationApp(backend=backend, store=store)
    await app.start()
    pubsub = backend.pubsub()
    await pubsub.subscribe(backend.messages_channel)
    try:
        ws, _ = await connect_client(app)
        try:
            await ws.send(
                json.dumps({"type": "broadcast", "payload": {"via": "pubsub"}})
            )
            envelope = await wait_for_pubsub_message(pubsub)
            assert envelope["kind"] == "broadcast"
            assert envelope["message"]["type"] == "broadcast"
            assert envelope["message"]["payload"] == {"via": "pubsub"}
        finally:
            await ws.close()
    finally:
        await pubsub.unsubscribe()
        await pubsub.close()
        await app.stop()


async def test_channel_message_envelope_carries_channel(backend, store):
    app = NotificationApp(backend=backend, store=store)
    await app.start()
    pubsub = backend.pubsub()
    await pubsub.subscribe(backend.messages_channel)
    try:
        ws, _ = await connect_client(app)
        try:
            await ws.send(
                json.dumps({"type": "broadcast", "channel": "ops", "payload": {"x": 1}})
            )
            envelope = await wait_for_pubsub_message(pubsub)
            assert envelope["kind"] == "channel"
            assert envelope["channel"] == "ops"
        finally:
            await ws.close()
    finally:
        await pubsub.unsubscribe()
        await pubsub.close()
        await app.stop()


# ── Client connection state in Redis ────────────────────────────────────


async def test_client_connection_state_stored_in_redis(app_pair, backend):
    app1, _ = app_pair
    ws, client_id = await connect_client(app1)
    try:
        await ws.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        await asyncio.sleep(0.2)

        assert client_id in await backend.global_clients()
        assert client_id in await backend.global_channel_members("alerts")
        assert "alerts" in await backend.global_channels()

        info = await backend.client_info(client_id)
        assert info is not None
        assert info["server_id"] == app1.notifier.server_id
        assert info["connected_at"]
    finally:
        await ws.close()


async def test_client_state_removed_on_disconnect(app_pair, backend):
    app1, _ = app_pair
    ws, client_id = await connect_client(app1)
    await ws.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
    await asyncio.sleep(0.2)
    await ws.close()

    async def state_gone():
        exists = await backend.client_exists(client_id)
        members = await backend.global_channel_members("alerts")
        return not exists and client_id not in members

    ok = await wait_until(lambda: state_gone())
    assert ok


async def test_channel_state_shared_across_instances(app_pair, backend):
    app1, app2 = app_pair
    ws_a, id_a = await connect_client(app1)
    try:
        await ws_a.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        await asyncio.sleep(0.2)

        # The other instance observes the same persisted membership.
        assert id_a in await backend.global_channel_members("alerts")
        assert await app2.notifier.registry.global_contains(id_a)
    finally:
        await ws_a.close()


async def test_client_state_survives_server_restart(backend, store):
    # Simulate a server process that crashed: it wrote connection state to
    # Redis and never got to run its disconnect cleanup.
    await backend.register_client("42", "server-a")
    await backend.add_channel_member("42", "alerts")

    # A fresh server instance (restart) reads the surviving state.
    app2 = NotificationApp(backend=backend, store=store)
    await app2.start()
    try:
        assert "42" in await backend.global_clients()
        assert "42" in await backend.global_channel_members("alerts")
        assert "alerts" in await backend.global_channels()
        assert await app2.notifier.registry.global_contains("42")
    finally:
        await app2.stop()


# ── SQLite persistence ──────────────────────────────────────────────────


async def test_message_store_roundtrip(store):
    ts = now_iso()
    await store.record("alerts", "broadcast", {"x": 1}, ts)
    await store.record("", "direct", {"y": 2}, ts)
    messages = await store.list_messages(limit=10, offset=0)
    assert len(messages) == 2
    assert messages[0]["type"] == "direct"
    assert messages[0]["payload"] == {"y": 2}
    assert messages[1]["channel"] == "alerts"
    assert messages[1]["payload"] == {"x": 1}
    assert messages[1]["timestamp"] == ts
    assert await store.count() == 2


async def test_messages_endpoint_returns_persisted_messages(app_pair):
    app1, app2 = app_pair
    ws_a, _ = await connect_client(app1)
    ws_b, id_b = await connect_client(app2)
    try:
        await ws_a.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        await asyncio.sleep(0.2)

        await ws_a.send(json.dumps({"type": "broadcast", "payload": {"text": "global"}}))
        await asyncio.wait_for(ws_a.recv(), timeout=5)

        await ws_a.send(
            json.dumps({"type": "broadcast", "channel": "alerts", "payload": {"text": "channeled"}})
        )
        await asyncio.wait_for(ws_a.recv(), timeout=5)

        await ws_a.send(
            json.dumps({"type": "direct", "target_id": id_b, "payload": {"text": "directed"}})
        )
        await asyncio.wait_for(ws_b.recv(), timeout=5)

        status, body = await http_get(app1, "/messages")
        assert status == 200
        data = json.loads(body)
        assert data["total"] == 3
        msgs = data["messages"]
        assert len(msgs) == 3
        assert msgs[0]["type"] == "direct"
        assert msgs[0]["payload"] == {"text": "directed"}
        assert msgs[0]["channel"] == ""
        assert msgs[1]["type"] == "broadcast"
        assert msgs[1]["channel"] == "alerts"
        assert msgs[1]["payload"] == {"text": "channeled"}
        assert msgs[2]["type"] == "broadcast"
        assert msgs[2]["channel"] == ""
        assert msgs[2]["payload"] == {"text": "global"}
        for msg in msgs:
            assert set(msg.keys()) == {"id", "channel", "type", "payload", "timestamp"}
            assert isinstance(msg["id"], int)
    finally:
        await ws_a.close()
        await ws_b.close()


async def test_messages_endpoint_pagination(app_pair):
    app1, _ = app_pair
    ws, _ = await connect_client(app1)
    try:
        for i in range(5):
            await ws.send(json.dumps({"type": "broadcast", "payload": {"i": i}}))
            await asyncio.wait_for(ws.recv(), timeout=5)

        status, body = await http_get(app1, "/messages?limit=2&offset=0")
        data = json.loads(body)
        assert data["total"] == 5
        assert [m["payload"] for m in data["messages"]] == [{"i": 4}, {"i": 3}]

        status, body = await http_get(app1, "/messages?limit=2&offset=2")
        data = json.loads(body)
        assert data["total"] == 5
        assert [m["payload"] for m in data["messages"]] == [{"i": 2}, {"i": 1}]
    finally:
        await ws.close()


async def test_messages_default_limit_50(app_pair):
    app1, _ = app_pair
    ws, _ = await connect_client(app1)
    try:
        for i in range(3):
            await ws.send(json.dumps({"type": "broadcast", "payload": {"i": i}}))
            await asyncio.wait_for(ws.recv(), timeout=5)

        status, body = await http_get(app1, "/messages")
        data = json.loads(body)
        assert data["total"] == 3
        assert len(data["messages"]) == 3
    finally:
        await ws.close()


async def test_messages_persist_across_server_restart(backend, tmp_path):
    db = tmp_path / "history.db"
    store1 = MessageStore(str(db))
    await store1.connect()
    app1 = NotificationApp(backend=backend, store=store1)
    await app1.start()
    ws, _ = await connect_client(app1)
    await ws.send(json.dumps({"type": "broadcast", "payload": {"keep": True}}))
    await asyncio.wait_for(ws.recv(), timeout=5)
    await ws.close()
    await app1.stop()
    await store1.close()

    store2 = MessageStore(str(db))
    await store2.connect()
    app2 = NotificationApp(backend=backend, store=store2)
    await app2.start()
    try:
        status, body = await http_get(app2, "/messages")
        data = json.loads(body)
        assert data["total"] == 1
        assert data["messages"][0]["payload"] == {"keep": True}
    finally:
        await app2.stop()
        await store2.close()
