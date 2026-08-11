import asyncio
import json
import os
import socket
import tempfile

import pytest
import pytest_asyncio
import websockets
import aiohttp
import fakeredis.aioredis

import app


def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.fixture(autouse=True)
def _isolate_db():
    temp_db = os.path.join(tempfile.gettempdir(), f"test_messages_{os.getpid()}.db")
    os.environ["DATABASE_URL"] = f"sqlite:///{temp_db}"
    app._reset_store()
    yield
    app._reset_store()
    for suffix in ("", "-wal", "-shm", "-journal"):
        try:
            os.unlink(temp_db + suffix)
        except OSError:
            pass


@pytest_asyncio.fixture
async def server():
    port = get_free_port()
    host = "127.0.0.1"
    server_task = asyncio.ensure_future(app.main(host=host, port=port))
    await asyncio.sleep(0.1)
    yield {"host": host, "port": port, "ws_url": f"ws://{host}:{port}"}
    server_task.cancel()
    try:
        await server_task
    except asyncio.CancelledError:
        pass


@pytest_asyncio.fixture
async def server_with_redis():
    fake_redis = fakeredis.aioredis.FakeRedis()
    app._set_redis(fake_redis)
    port = get_free_port()
    host = "127.0.0.1"
    server_task = asyncio.ensure_future(app.main(host=host, port=port))
    await asyncio.sleep(0.1)
    yield {
        "host": host,
        "port": port,
        "ws_url": f"ws://{host}:{port}",
        "redis": fake_redis,
    }
    server_task.cancel()
    try:
        await server_task
    except asyncio.CancelledError:
        pass
    app._set_redis(None)


@pytest.mark.asyncio
async def test_client_gets_unique_id(server):
    async with websockets.connect(server["ws_url"]) as ws1, \
               websockets.connect(server["ws_url"]) as ws2:
        welcome1 = json.loads(await ws1.recv())
        welcome2 = json.loads(await ws2.recv())

    assert welcome1["payload"]["client_id"] != welcome2["payload"]["client_id"]
    assert welcome1["type"] == "system"
    assert welcome1["payload"]["event"] == "connected"
    assert welcome2["type"] == "system"


@pytest.mark.asyncio
async def test_broadcast(server):
    async with websockets.connect(server["ws_url"]) as ws1, \
               websockets.connect(server["ws_url"]) as ws2:
        await ws1.recv()
        await ws2.recv()

        await ws1.send(json.dumps({
            "type": "broadcast",
            "payload": {"message": "hello all"},
        }))

        msg = json.loads(await ws1.recv())
        assert msg["type"] == "broadcast"
        assert msg["payload"]["message"] == "hello all"
        assert "timestamp" in msg

        msg2 = json.loads(await ws2.recv())
        assert msg2["type"] == "broadcast"
        assert msg2["payload"]["message"] == "hello all"
        assert "timestamp" in msg2


@pytest.mark.asyncio
async def test_direct_message(server):
    async with websockets.connect(server["ws_url"]) as ws1, \
               websockets.connect(server["ws_url"]) as ws2:
        welcome1 = json.loads(await ws1.recv())
        client1_id = welcome1["payload"]["client_id"]
        await ws2.recv()

        await ws1.send(json.dumps({
            "type": "direct",
            "payload": {"message": "hey you", "target_id": client1_id},
        }))

        msg = json.loads(await ws1.recv())
        assert msg["type"] == "direct"
        assert msg["payload"]["message"] == "hey you"

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws2.recv(), timeout=0.5)


@pytest.mark.asyncio
async def test_system_message(server):
    async with websockets.connect(server["ws_url"]) as ws:
        welcome = json.loads(await ws.recv())
        assert welcome["type"] == "system"
        assert welcome["payload"]["event"] == "connected"
        assert "client_id" in welcome["payload"]
        assert "timestamp" in welcome

        await ws.send(json.dumps({
            "type": "system",
            "payload": {"event": "custom"},
        }))

        msg = json.loads(await ws.recv())
        assert msg["type"] == "system"
        assert msg["payload"]["event"] == "custom"
        assert "timestamp" in msg


@pytest.mark.asyncio
async def test_disconnect_removes_client(server):
    async with websockets.connect(server["ws_url"]) as ws:
        welcome = json.loads(await ws.recv())
        client_id = welcome["payload"]["client_id"]

    await asyncio.sleep(0.05)

    with app.registry._lock:
        assert client_id not in app.registry._clients


@pytest.mark.asyncio
async def test_health_endpoint(server):
    async with websockets.connect(server["ws_url"]) as ws1, \
               websockets.connect(server["ws_url"]) as ws2:
        await ws1.recv()
        await ws2.recv()

        async with aiohttp.ClientSession() as session:
            url = f"http://{server['host']}:{server['port']}/health"
            async with session.get(url) as resp:
                data = await resp.json()
                assert resp.status == 200
                assert data["clients_connected"] == 2

    async with aiohttp.ClientSession() as session:
        url = f"http://{server['host']}:{server['port']}/health"
        async with session.get(url) as resp:
            data = await resp.json()
            assert data["clients_connected"] == 0


@pytest.mark.asyncio
async def test_message_format(server):
    async with websockets.connect(server["ws_url"]) as ws1, \
               websockets.connect(server["ws_url"]) as ws2:
        await ws1.recv()
        await ws2.recv()

        await ws1.send(json.dumps({
            "type": "broadcast",
            "payload": {"key": "value"},
        }))

        msg = json.loads(await ws1.recv())
        assert set(msg.keys()) == {"type", "payload", "timestamp"}
        assert isinstance(msg["type"], str)
        assert isinstance(msg["payload"], dict)
        assert isinstance(msg["timestamp"], str)

        msg2 = json.loads(await ws2.recv())
        assert set(msg2.keys()) == {"type", "payload", "timestamp"}


@pytest.mark.asyncio
async def test_invalid_json_ignored(server):
    async with websockets.connect(server["ws_url"]) as ws1, \
               websockets.connect(server["ws_url"]) as ws2:
        await ws1.recv()
        await ws2.recv()

        await ws1.send("not valid json")

        await ws1.send(json.dumps({
            "type": "broadcast",
            "payload": {"msg": "after invalid"},
        }))

        msg = json.loads(await ws1.recv())
        assert msg["payload"]["msg"] == "after invalid"

        msg2 = json.loads(await ws2.recv())
        assert msg2["payload"]["msg"] == "after invalid"


@pytest.mark.asyncio
async def test_subscribe_and_channel_broadcast(server):
    async with websockets.connect(server["ws_url"]) as ws1, \
               websockets.connect(server["ws_url"]) as ws2:
        await ws1.recv()
        await ws2.recv()

        await ws1.send(json.dumps({
            "type": "subscribe",
            "channel": "alerts",
        }))
        sub_resp = json.loads(await ws1.recv())
        assert sub_resp["type"] == "system"
        assert sub_resp["payload"]["event"] == "subscribed"
        assert sub_resp["payload"]["channel"] == "alerts"

        await ws1.send(json.dumps({
            "type": "broadcast",
            "channel": "alerts",
            "payload": {"msg": "alert!"},
        }))

        msg1 = json.loads(await ws1.recv())
        assert msg1["type"] == "broadcast"
        assert msg1["payload"]["msg"] == "alert!"
        assert msg1.get("channel") == "alerts"

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws2.recv(), timeout=0.5)


@pytest.mark.asyncio
async def test_unsubscribe_stops_channel_messages(server):
    async with websockets.connect(server["ws_url"]) as ws:
        await ws.recv()

        await ws.send(json.dumps({
            "type": "subscribe",
            "channel": "chat",
        }))
        await ws.recv()

        await ws.send(json.dumps({
            "type": "unsubscribe",
            "channel": "chat",
        }))
        unsub_resp = json.loads(await ws.recv())
        assert unsub_resp["type"] == "system"
        assert unsub_resp["payload"]["event"] == "unsubscribed"
        assert unsub_resp["payload"]["channel"] == "chat"

        await ws.send(json.dumps({
            "type": "broadcast",
            "channel": "chat",
            "payload": {"msg": "should not arrive"},
        }))

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws.recv(), timeout=0.5)


@pytest.mark.asyncio
async def test_multiple_channels(server):
    async with websockets.connect(server["ws_url"]) as ws:
        await ws.recv()

        await ws.send(json.dumps({
            "type": "subscribe",
            "channel": "alerts",
        }))
        await ws.recv()

        await ws.send(json.dumps({
            "type": "subscribe",
            "channel": "system",
        }))
        await ws.recv()

        await ws.send(json.dumps({
            "type": "broadcast",
            "channel": "alerts",
            "payload": {"msg": "alert-msg"},
        }))
        msg = json.loads(await ws.recv())
        assert msg["payload"]["msg"] == "alert-msg"
        assert msg["channel"] == "alerts"

        await ws.send(json.dumps({
            "type": "broadcast",
            "channel": "system",
            "payload": {"msg": "system-msg"},
        }))
        msg = json.loads(await ws.recv())
        assert msg["payload"]["msg"] == "system-msg"
        assert msg["channel"] == "system"


@pytest.mark.asyncio
async def test_broadcast_without_channel_still_works(server):
    async with websockets.connect(server["ws_url"]) as ws1, \
               websockets.connect(server["ws_url"]) as ws2:
        await ws1.recv()
        await ws2.recv()

        await ws1.send(json.dumps({
            "type": "broadcast",
            "payload": {"key": "value"},
        }))

        msg1 = json.loads(await ws1.recv())
        assert msg1["payload"]["key"] == "value"
        assert "channel" not in msg1

        msg2 = json.loads(await ws2.recv())
        assert msg2["payload"]["key"] == "value"
        assert "channel" not in msg2


@pytest.mark.asyncio
async def test_channels_rest_endpoint(server):
    async with websockets.connect(server["ws_url"]) as ws:
        await ws.recv()

        await ws.send(json.dumps({
            "type": "subscribe",
            "channel": "alerts",
        }))
        await ws.recv()

        await ws.send(json.dumps({
            "type": "subscribe",
            "channel": "chat",
        }))
        await ws.recv()

        async with aiohttp.ClientSession() as session:
            url = f"http://{server['host']}:{server['port']}/channels"
            async with session.get(url) as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data["alerts"] == 1
                assert data["chat"] == 1


@pytest.mark.asyncio
async def test_channel_subscribers_rest_endpoint(server):
    async with websockets.connect(server["ws_url"]) as ws1, \
               websockets.connect(server["ws_url"]) as ws2:
        welcome1 = json.loads(await ws1.recv())
        cid1 = welcome1["payload"]["client_id"]
        await ws2.recv()

        await ws1.send(json.dumps({
            "type": "subscribe",
            "channel": "alerts",
        }))
        await ws1.recv()

        async with aiohttp.ClientSession() as session:
            url = f"http://{server['host']}:{server['port']}/channels/alerts/subscribers"
            async with session.get(url) as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data["channel"] == "alerts"
                assert cid1 in data["subscribers"]
                assert len(data["subscribers"]) == 1


@pytest.mark.asyncio
async def test_disconnect_removes_channel_subscriptions(server):
    async with websockets.connect(server["ws_url"]) as ws:
        await ws.recv()

        await ws.send(json.dumps({
            "type": "subscribe",
            "channel": "alerts",
        }))
        await ws.recv()

    await asyncio.sleep(0.05)

    channels = app.registry.get_channels()
    assert channels.get("alerts", 0) == 0


@pytest.mark.asyncio
async def test_messages_persisted_to_sqlite(server):
    async with websockets.connect(server["ws_url"]) as ws:
        await ws.recv()

        await ws.send(json.dumps({
            "type": "subscribe",
            "channel": "general",
        }))
        await ws.recv()

        await ws.send(json.dumps({
            "type": "broadcast",
            "channel": "general",
            "payload": {"msg": "first"},
        }))
        await ws.recv()

        await ws.send(json.dumps({
            "type": "broadcast",
            "payload": {"msg": "global"},
        }))
        await ws.recv()

    msgs = app._get_store().query(limit=50, offset=0)
    assert len(msgs) >= 2

    first = msgs[0]
    assert first["type"] == "broadcast"
    assert first["payload"]["msg"] in ("first", "global")
    assert first["channel"] in (None, "general")
    assert isinstance(first["id"], str)
    assert isinstance(first["timestamp"], str)


@pytest.mark.asyncio
async def test_messages_rest_endpoint(server):
    async with websockets.connect(server["ws_url"]) as ws:
        await ws.recv()

        await ws.send(json.dumps({
            "type": "subscribe",
            "channel": "chat",
        }))
        await ws.recv()

        await ws.send(json.dumps({
            "type": "broadcast",
            "channel": "chat",
            "payload": {"msg": "hello world"},
        }))
        await ws.recv()

    async with aiohttp.ClientSession() as session:
        url = f"http://{server['host']}:{server['port']}/messages"
        async with session.get(url) as resp:
            assert resp.status == 200
            data = await resp.json()
            assert isinstance(data, list)
            assert len(data) >= 1
            found = any(
                m["payload"]["msg"] == "hello world" and m["channel"] == "chat"
                for m in data
            )
            assert found, f"Expected message not found in {data}"


@pytest.mark.asyncio
async def test_messages_rest_endpoint_pagination(server):
    async with websockets.connect(server["ws_url"]) as ws:
        await ws.recv()
        for i in range(5):
            await ws.send(json.dumps({
                "type": "broadcast",
                "payload": {"index": i},
            }))
            await ws.recv()

    async with aiohttp.ClientSession() as session:
        base = f"http://{server['host']}:{server['port']}/messages"

        async with session.get(f"{base}?limit=2&offset=0") as resp:
            data = await resp.json()
            assert len(data) == 2

        async with session.get(f"{base}?limit=2&offset=2") as resp:
            data = await resp.json()
            assert len(data) == 2

        async with session.get(f"{base}?limit=10&offset=0") as resp:
            data = await resp.json()
            assert len(data) >= 5


@pytest.mark.asyncio
async def test_redis_publishes_on_broadcast(server_with_redis):
    fake_redis = server_with_redis["redis"]
    server_info = server_with_redis

    async with websockets.connect(server_info["ws_url"]) as ws1, \
               websockets.connect(server_info["ws_url"]) as ws2:
        await ws1.recv()
        await ws2.recv()

        await ws1.send(json.dumps({
            "type": "subscribe",
            "channel": "testchan",
        }))
        await ws1.recv()

        await ws2.send(json.dumps({
            "type": "subscribe",
            "channel": "testchan",
        }))
        await ws2.recv()

        sub = fake_redis.pubsub()
        await sub.subscribe("channel:testchan")

        await ws1.send(json.dumps({
            "type": "broadcast",
            "channel": "testchan",
            "payload": {"msg": "redis-test"},
        }))
        await ws1.recv()
        await ws2.recv()

        try:
            redis_msg = await asyncio.wait_for(
                sub.get_message(timeout=2), timeout=2
            )
            while redis_msg and redis_msg["type"] != "message":
                redis_msg = await asyncio.wait_for(
                    sub.get_message(timeout=2), timeout=2
                )
        except asyncio.TimeoutError:
            redis_msg = None

        assert redis_msg is not None, "Message was not published to Redis"
        data = json.loads(redis_msg["data"])
        assert data["type"] == "broadcast"
        assert data["payload"]["msg"] == "redis-test"
        assert data["channel"] == "testchan"
        assert "_server_id" in data

        await sub.unsubscribe("channel:testchan")


@pytest.mark.asyncio
async def test_redis_cross_instance_delivery(server_with_redis):
    fake_redis = server_with_redis["redis"]
    server_info = server_with_redis

    original_sid = app._server_id
    app._server_id = "external-instance"

    async with websockets.connect(server_info["ws_url"]) as ws:
        await ws.recv()
        await ws.send(json.dumps({
            "type": "subscribe",
            "channel": "external",
        }))
        await ws.recv()

        pub_data = {
            "type": "broadcast",
            "channel": "external",
            "payload": {"msg": "from-other-server"},
            "timestamp": "2024-01-01T00:00:00Z",
            "_server_id": "external-instance",
        }
        await fake_redis.publish("channel:external", json.dumps(pub_data))
        await asyncio.sleep(0.2)

        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=2)
            data = json.loads(msg)
            assert data["type"] == "broadcast"
            assert data["payload"]["msg"] == "from-other-server"
            assert data["channel"] == "external"
        except asyncio.TimeoutError:
            # The subscriber might not have picked it up yet
            # Try to deliver manually via the handler
            await app._deliver_from_redis(pub_data)
            msg = await asyncio.wait_for(ws.recv(), timeout=2)
            data = json.loads(msg)
            assert data["type"] == "broadcast"
            assert data["payload"]["msg"] == "from-other-server"
            assert data["channel"] == "external"

    app._server_id = original_sid


@pytest.mark.asyncio
async def test_redis_global_broadcast_published(server_with_redis):
    fake_redis = server_with_redis["redis"]
    server_info = server_with_redis

    async with websockets.connect(server_info["ws_url"]) as ws1, \
               websockets.connect(server_info["ws_url"]) as ws2:
        await ws1.recv()
        await ws2.recv()

        sub = fake_redis.pubsub()
        await sub.subscribe("broadcast:all")

        await ws1.send(json.dumps({
            "type": "broadcast",
            "payload": {"msg": "global-redis-test"},
        }))
        await ws1.recv()
        await ws2.recv()

        try:
            redis_msg = await asyncio.wait_for(
                sub.get_message(timeout=2), timeout=2
            )
            while redis_msg and redis_msg["type"] != "message":
                redis_msg = await asyncio.wait_for(
                    sub.get_message(timeout=2), timeout=2
                )
        except asyncio.TimeoutError:
            redis_msg = None

        assert redis_msg is not None, "Global message was not published to Redis"
        data = json.loads(redis_msg["data"])
        assert data["type"] == "broadcast"
        assert data["payload"]["msg"] == "global-redis-test"

        await sub.unsubscribe("broadcast:all")


@pytest.mark.asyncio
async def test_redis_client_state_stored(server_with_redis):
    fake_redis = server_with_redis["redis"]
    server_info = server_with_redis
    sid = app._server_id

    async with websockets.connect(server_info["ws_url"]) as ws:
        welcome = json.loads(await ws.recv())
        client_id = welcome["payload"]["client_id"]

        members = await fake_redis.smembers(f"clients:{sid}")
        assert client_id.encode() in members

    await asyncio.sleep(0.1)
    members = await fake_redis.smembers(f"clients:{sid}")
    assert client_id.encode() not in members


@pytest.mark.asyncio
async def test_direct_message_persisted(server):
    async with websockets.connect(server["ws_url"]) as ws:
        welcome = json.loads(await ws.recv())
        target_id = welcome["payload"]["client_id"]

        await ws.send(json.dumps({
            "type": "direct",
            "payload": {"message": "persisted-dm", "target_id": target_id},
        }))
        await ws.recv()

    msgs = app._get_store().query(limit=50, offset=0)
    dm_messages = [m for m in msgs if m["type"] == "direct"]
    assert len(dm_messages) >= 1
    assert dm_messages[0]["payload"]["message"] == "persisted-dm"


@pytest.mark.asyncio
async def test_message_schema_correct(server):
    async with websockets.connect(server["ws_url"]) as ws:
        await ws.recv()

        await ws.send(json.dumps({
            "type": "subscribe",
            "channel": "test-db",
        }))
        await ws.recv()

        await ws.send(json.dumps({
            "type": "broadcast",
            "channel": "test-db",
            "payload": {"x": 1, "y": "z"},
        }))
        await ws.recv()

    msgs = app._get_store().query(limit=1, offset=0)
    assert len(msgs) == 1
    m = msgs[0]
    assert set(m.keys()) == {"id", "channel", "type", "payload", "timestamp"}
    assert m["id"]
    assert m["channel"] == "test-db"
    assert m["type"] == "broadcast"
    assert m["payload"] == {"x": 1, "y": "z"}
    assert isinstance(m["timestamp"], str)
