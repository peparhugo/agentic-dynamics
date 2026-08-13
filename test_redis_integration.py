import asyncio
import json

import fakeredis
import pytest
import pytest_asyncio
from websockets.asyncio.client import connect

from notification_server import (
    BROADCAST,
    DIRECT,
    SUBSCRIBE,
    NotificationServer,
    REDIS_BACKBONE_CHANNEL,
)

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def redis_client():
    client = fakeredis.FakeAsyncRedis(decode_responses=True)
    yield client
    await client.aclose()


async def make_server(redis_client=None, database_url=None):
    srv = NotificationServer(
        host="127.0.0.1",
        port=0,
        log_path=None,
        redis_client=redis_client,
        database_url=database_url,
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


async def wait_until(coro, timeout=2.0):
    """Poll an async predicate until it returns a truthy value."""
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if await coro():
            return True
        await asyncio.sleep(0.02)
    return await coro()


def is_not_member(client, key, member):
    async def _check():
        return not await client.sismember(key, member)
    return _check


# -- Redis pub/sub backbone ------------------------------------------------


async def test_redis_broadcast_delivered_via_backbone(redis_client):
    srv = await make_server(redis_client=redis_client)
    try:
        ws, _ = await open_client(srv)
        assert srv.backbone is not None

        await ws.send(json.dumps({
            "type": BROADCAST,
            "payload": {"text": "via redis backbone"},
        }))
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        assert msg["type"] == BROADCAST
        assert msg["payload"]["text"] == "via redis backbone"
        await ws.close()
    finally:
        await srv.close()


async def test_redis_server_publishes_to_backbone_channel(redis_client):
    srv = await make_server(redis_client=redis_client)
    spy = redis_client.pubsub()
    await spy.subscribe(REDIS_BACKBONE_CHANNEL)
    try:
        ws, _ = await open_client(srv)
        await ws.send(json.dumps({
            "type": BROADCAST,
            "payload": {"text": "published envelope"},
        }))

        envelope = None
        async for raw in spy.listen():
            if raw.get("type") == "message":
                envelope = json.loads(raw["data"])
                break
        assert envelope is not None
        assert envelope["type"] == BROADCAST
        assert envelope["message"]["payload"]["text"] == "published envelope"
        await ws.close()
    finally:
        await spy.unsubscribe(REDIS_BACKBONE_CHANNEL)
        await spy.aclose()
        await srv.close()


async def test_multiple_servers_share_redis_backbone(redis_client):
    srv_a = await make_server(redis_client=redis_client)
    srv_b = await make_server(redis_client=redis_client)
    try:
        ws_a, _ = await open_client(srv_a)
        ws_b, _ = await open_client(srv_b)

        await ws_a.send(json.dumps({
            "type": BROADCAST,
            "payload": {"text": "cluster broadcast"},
        }))

        received_a = json.loads(await asyncio.wait_for(ws_a.recv(), timeout=5))
        received_b = json.loads(await asyncio.wait_for(ws_b.recv(), timeout=5))
        assert received_a["payload"]["text"] == "cluster broadcast"
        assert received_b["payload"]["text"] == "cluster broadcast"

        await ws_a.close()
        await ws_b.close()
    finally:
        await srv_a.close()
        await srv_b.close()


async def test_redis_channel_routing_via_backbone(redis_client):
    srv = await make_server(redis_client=redis_client)
    try:
        ws_alerts, _ = await open_client(srv)
        ws_other, _ = await open_client(srv)

        await ws_alerts.send(json.dumps({
            "type": SUBSCRIBE,
            "payload": {"channel": "alerts"},
        }))
        await asyncio.sleep(0.05)
        await ws_other.send(json.dumps({
            "type": BROADCAST,
            "channel": "alerts",
            "payload": {"text": "alerts only"},
        }))

        msg = json.loads(await asyncio.wait_for(ws_alerts.recv(), timeout=5))
        assert msg["payload"]["text"] == "alerts only"
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws_other.recv(), timeout=0.3)

        await ws_alerts.close()
        await ws_other.close()
    finally:
        await srv.close()


async def test_redis_direct_message_via_backbone(redis_client):
    srv = await make_server(redis_client=redis_client)
    try:
        ws_a, welcome_a = await open_client(srv)
        ws_b, welcome_b = await open_client(srv)
        target_b = welcome_b["payload"]["client_id"]

        await ws_a.send(json.dumps({
            "type": DIRECT,
            "payload": {"target": target_b, "text": "only b"},
        }))

        msg = json.loads(await asyncio.wait_for(ws_b.recv(), timeout=5))
        assert msg["type"] == DIRECT
        assert msg["payload"]["text"] == "only b"
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws_a.recv(), timeout=0.3)

        await ws_a.close()
        await ws_b.close()
    finally:
        await srv.close()


# -- client connection state in Redis ----------------------------------------


async def test_client_state_stored_in_redis(redis_client):
    srv = await make_server(redis_client=redis_client)
    try:
        ws, welcome = await open_client(srv)
        client_id = welcome["payload"]["client_id"]

        assert await wait_until(
            lambda: redis_client.sismember("notification:clients", client_id)
        )

        await ws.send(json.dumps({
            "type": SUBSCRIBE,
            "payload": {"channel": "alerts"},
        }))
        assert await wait_until(
            lambda: redis_client.sismember("notification:channel:alerts", client_id)
        )

        await ws.close()
        assert await wait_until(
            is_not_member(redis_client, "notification:clients", client_id)
        )
        assert await wait_until(
            is_not_member(redis_client, "notification:channel:alerts", client_id)
        )
    finally:
        await srv.close()


async def test_redis_snapshot_reflects_state(redis_client):
    srv = await make_server(redis_client=redis_client)
    try:
        ws, welcome = await open_client(srv)
        client_id = welcome["payload"]["client_id"]

        await ws.send(json.dumps({
            "type": SUBSCRIBE,
            "payload": {"channels": ["alerts", "system"]},
        }))
        await wait_until(
            lambda: redis_client.sismember("notification:channel:alerts", client_id)
        )

        snapshot = await srv.redis_snapshot()
        assert client_id in snapshot["clients"]
        assert client_id in snapshot["channels"]["alerts"]
        assert client_id in snapshot["channels"]["system"]

        await ws.close()
        assert await wait_until(
            is_not_member(redis_client, "notification:clients", client_id)
        )
        snapshot = await srv.redis_snapshot()
        assert client_id not in snapshot["clients"]
        assert snapshot["channels"] == {}
    finally:
        await srv.close()


async def test_client_state_restored_after_restart(redis_client):
    srv_a = await make_server(redis_client=redis_client)
    try:
        ws, welcome = await open_client(srv_a)
        client_id = welcome["payload"]["client_id"]

        await ws.send(json.dumps({
            "type": SUBSCRIBE,
            "payload": {"channel": "alerts"},
        }))
        assert await wait_until(
            lambda: redis_client.sismember("notification:channel:alerts", client_id)
        )

        # Simulate a crash: the old server never runs its disconnect
        # cleanup, but its connection state lives on in Redis. A new
        # server instance can restore it.
        srv_b = await make_server(redis_client=redis_client)
        try:
            restored = await srv_b.restore_state()
            assert restored > 0
            assert client_id in srv_b.channel_subscribers("alerts")
            assert client_id in srv_b.registry.snapshot()
        finally:
            await srv_b.close()

        await ws.close()
        await wait_until(
            is_not_member(redis_client, "notification:clients", client_id)
        )
    finally:
        await srv_a.close()


# -- SQLite persistence -------------------------------------------------------


async def test_messages_persisted_to_sqlite(tmp_path):
    db = tmp_path / "history.db"
    srv = await make_server(database_url=db)
    try:
        ws, _ = await open_client(srv)
        await ws.send(json.dumps({
            "type": BROADCAST,
            "payload": {"text": "remember me"},
        }))
        await asyncio.sleep(0.05)

        assert srv.message_store.count() == 1
        rows = srv.message_store.list(limit=10, offset=0)
        assert rows[0]["type"] == BROADCAST
        assert rows[0]["payload"]["text"] == "remember me"
        assert rows[0]["channel"] is None
        assert set(rows[0]) >= {"id", "channel", "type", "payload", "timestamp"}

        await ws.close()
    finally:
        await srv.close()


async def test_direct_and_channel_messages_persisted(tmp_path):
    db = tmp_path / "history.db"
    srv = await make_server(database_url=db)
    try:
        ws, welcome = await open_client(srv)
        client_id = welcome["payload"]["client_id"]

        await ws.send(json.dumps({
            "type": BROADCAST,
            "channel": "alerts",
            "payload": {"text": "channel msg"},
        }))
        await ws.send(json.dumps({
            "type": DIRECT,
            "payload": {"target": client_id, "text": "direct msg"},
        }))
        await asyncio.sleep(0.05)

        rows = srv.message_store.list(limit=10, offset=0)
        by_type = {r["type"] for r in rows}
        assert by_type == {BROADCAST, DIRECT}
        channel_rows = [r for r in rows if r["type"] == BROADCAST]
        assert channel_rows[0]["channel"] == "alerts"
        direct_rows = [r for r in rows if r["type"] == DIRECT]
        assert direct_rows[0]["channel"] is None
        assert direct_rows[0]["payload"]["target"] == client_id

        await ws.close()
    finally:
        await srv.close()


async def test_get_messages_endpoint(tmp_path):
    db = tmp_path / "history.db"
    srv = await make_server(database_url=db)
    try:
        ws, _ = await open_client(srv)
        for i in range(3):
            await ws.send(json.dumps({
                "type": BROADCAST,
                "payload": {"text": f"msg-{i}"},
            }))
        await asyncio.sleep(0.05)

        raw = await http_get(srv.port, "/messages")
        status = raw.split(b" ", 2)[1].decode()
        body = raw.split(b"\r\n\r\n", 1)[1]
        payload = json.loads(body)
        assert status == "200"
        assert payload["count"] == 3
        assert payload["limit"] == 50
        assert payload["offset"] == 0
        texts = [m["payload"]["text"] for m in payload["messages"]]
        assert set(texts) == {"msg-0", "msg-1", "msg-2"}

        await ws.close()
    finally:
        await srv.close()


async def test_get_messages_limit_offset(tmp_path):
    db = tmp_path / "history.db"
    srv = await make_server(database_url=db)
    try:
        ws, _ = await open_client(srv)
        for i in range(5):
            await ws.send(json.dumps({
                "type": BROADCAST,
                "payload": {"text": f"m{i}"},
            }))
        await asyncio.sleep(0.05)

        raw = await http_get(srv.port, "/messages?limit=2&offset=1")
        body = raw.split(b"\r\n\r\n", 1)[1]
        payload = json.loads(body)
        assert payload["count"] == 5
        assert payload["limit"] == 2
        assert payload["offset"] == 1
        assert len(payload["messages"]) == 2
        ids = [m["id"] for m in payload["messages"]]
        assert ids == [4, 3]

        await ws.close()
    finally:
        await srv.close()


# -- configuration -------------------------------------------------------------


async def test_env_config(monkeypatch, tmp_path):
    import notification_server as ns

    fake = fakeredis.FakeAsyncRedis(decode_responses=True)
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/env.db")
    monkeypatch.setattr(
        ns.NotificationServer,
        "_create_redis_client",
        staticmethod(lambda url: fake),
    )

    srv = ns.NotificationServer(host="127.0.0.1", port=0)
    try:
        assert srv.redis_client is fake
        assert srv.backbone is not None
        assert srv.message_store.path == tmp_path / "env.db"
    finally:
        await srv.close()


async def test_server_without_redis_uses_local_delivery():
    srv = await make_server(redis_client=None, database_url=None)
    try:
        assert srv.backbone is None
        assert srv.redis_client is None
        ws, _ = await open_client(srv)
        await ws.send(json.dumps({
            "type": BROADCAST,
            "payload": {"text": "local mode"},
        }))
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        assert msg["payload"]["text"] == "local mode"
        await ws.close()
    finally:
        await srv.close()
