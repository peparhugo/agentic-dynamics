import asyncio
import json
import os
import tempfile
import threading
import time

import pytest
from websockets.asyncio.client import connect

from server import NotificationServer, ClientRegistry, MessageStore, RateLimiter

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")


def _check_redis():
    try:
        import redis
        r = redis.from_url(REDIS_URL)
        r.ping()
        r.close()
        return True
    except Exception:
        return False


_redis_available = _check_redis()
skip_if_no_redis = pytest.mark.skipif(not _redis_available, reason="Redis not available")


async def async_http_get(host, port, path):
    reader, writer = await asyncio.open_connection(host, port)
    request = f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
    writer.write(request.encode())
    await writer.drain()

    raw = b""
    while True:
        chunk = await asyncio.wait_for(reader.read(4096), timeout=5)
        if not chunk:
            break
        raw += chunk

    writer.close()
    await writer.wait_closed()

    parts = raw.split(b"\r\n\r\n", 1)
    body = parts[1] if len(parts) > 1 else b""
    return json.loads(body.decode())


@pytest.fixture
async def notification_server():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        server = NotificationServer(host="localhost", port=0, database_url=db_path, redis_url="")
        async with server.run() as ws_server:
            server.port = ws_server.sockets[0].getsockname()[1]
            yield server
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass


@pytest.fixture
async def rate_limited_server():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        server = NotificationServer(host="localhost", port=0, database_url=db_path, redis_url="", rate_limit=5)
        async with server.run() as ws_server:
            server.port = ws_server.sockets[0].getsockname()[1]
            yield server
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass


class TestClientRegistry:
    def test_add_and_count(self):
        reg = ClientRegistry()
        assert reg.count() == 0
        reg.add("id1", object())
        assert reg.count() == 1
        reg.add("id2", object())
        assert reg.count() == 2

    def test_remove(self):
        reg = ClientRegistry()
        dummy = object()
        reg.add("id1", dummy)
        assert reg.count() == 1
        reg.remove("id1")
        assert reg.count() == 0
        reg.remove("nonexistent")

    def test_get_all_returns_copy(self):
        reg = ClientRegistry()
        dummy = object()
        reg.add("id1", dummy)
        clients = reg.get_all()
        clients["extra"] = "bad"
        assert "extra" not in reg.get_all()

    def test_clear(self):
        reg = ClientRegistry()
        reg.add("a", object())
        reg.add("b", object())
        reg.clear()
        assert reg.count() == 0

    def test_thread_safety(self):
        reg = ClientRegistry()
        errors = []

        def adder(start):
            try:
                for i in range(start, start + 500):
                    reg.add(str(i), object())
            except Exception as e:
                errors.append(e)

        def remover(start):
            try:
                for i in range(start, start + 500):
                    reg.remove(str(i))
            except Exception as e:
                errors.append(e)

        threads = []
        for j in range(5):
            t1 = threading.Thread(target=adder, args=(j * 1000,))
            t2 = threading.Thread(target=remover, args=(j * 1000,))
            threads.extend([t1, t2])

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        reg.clear()


@pytest.mark.asyncio
async def test_client_connects_and_receives_welcome(notification_server):
    uri = f"ws://localhost:{notification_server.port}"
    async with connect(uri) as ws:
        msg = await asyncio.wait_for(ws.recv(), timeout=5)
        data = json.loads(msg)
        assert data["type"] == "system"
        assert "client_id" in data["payload"]
        assert len(data["payload"]["client_id"]) > 0


@pytest.mark.asyncio
async def test_each_client_gets_unique_id(notification_server):
    uri = f"ws://localhost:{notification_server.port}"
    async with connect(uri) as ws1, connect(uri) as ws2:
        data1 = json.loads(await asyncio.wait_for(ws1.recv(), timeout=5))
        data2 = json.loads(await asyncio.wait_for(ws2.recv(), timeout=5))
        assert data1["payload"]["client_id"] != data2["payload"]["client_id"]


@pytest.mark.asyncio
async def test_health_returns_client_count(notification_server):
    port = notification_server.port

    data = await async_http_get("localhost", port, "/health")
    assert data["clients"] == 0

    uri = f"ws://localhost:{port}"
    async with connect(uri) as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)
        await asyncio.sleep(0.05)
        data = await async_http_get("localhost", port, "/health")
        assert data["clients"] == 1


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients(notification_server):
    uri = f"ws://localhost:{notification_server.port}"

    async with connect(uri) as client1, connect(uri) as client2:
        await asyncio.wait_for(client1.recv(), timeout=5)
        await asyncio.wait_for(client2.recv(), timeout=5)

        await client1.send(json.dumps({
            "type": "broadcast",
            "payload": {"message": "hello"}
        }))

        msg1 = await asyncio.wait_for(client1.recv(), timeout=5)
        msg2 = await asyncio.wait_for(client2.recv(), timeout=5)

        d1 = json.loads(msg1)
        d2 = json.loads(msg2)

        assert d1["type"] == "broadcast"
        assert d1["payload"]["message"] == "hello"
        assert d2["type"] == "broadcast"
        assert d2["payload"]["message"] == "hello"


@pytest.mark.asyncio
async def test_direct_message(notification_server):
    uri = f"ws://localhost:{notification_server.port}"

    async with connect(uri) as client1:
        welcome1 = await asyncio.wait_for(client1.recv(), timeout=5)
        client1_id = json.loads(welcome1)["payload"]["client_id"]

        async with connect(uri) as client2:
            welcome2 = await asyncio.wait_for(client2.recv(), timeout=5)
            client2_id = json.loads(welcome2)["payload"]["client_id"]

            await client1.send(json.dumps({
                "type": "direct",
                "target": client2_id,
                "payload": {"message": "private"}
            }))

            direct_msg = await asyncio.wait_for(client2.recv(), timeout=5)
            data = json.loads(direct_msg)
            assert data["type"] == "direct"
            assert data["payload"]["message"] == "private"
            assert data["sender"] == client1_id


@pytest.mark.asyncio
async def test_direct_message_to_nonexistent(notification_server):
    uri = f"ws://localhost:{notification_server.port}"
    async with connect(uri) as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)
        await ws.send(json.dumps({
            "type": "direct",
            "target": "nonexistent-id",
            "payload": {"message": "nobody"}
        }))


@pytest.mark.asyncio
async def test_client_disconnect_removed_from_registry(notification_server):
    port = notification_server.port
    uri = f"ws://localhost:{port}"

    async with connect(uri) as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)
        data = await async_http_get("localhost", port, "/health")
        assert data["clients"] == 1

    await asyncio.sleep(0.1)
    data = await async_http_get("localhost", port, "/health")
    assert data["clients"] == 0


@pytest.mark.asyncio
async def test_broadcast_skips_disconnected_clients(notification_server):
    uri = f"ws://localhost:{notification_server.port}"

    async with connect(uri) as client1:
        await asyncio.wait_for(client1.recv(), timeout=5)

        async with connect(uri) as client2:
            await asyncio.wait_for(client2.recv(), timeout=5)
            await client2.close()

            await asyncio.sleep(0.05)

            await client1.send(json.dumps({
                "type": "broadcast",
                "payload": {"message": "still alive"}
            }))

            msg = await asyncio.wait_for(client1.recv(), timeout=5)
            data = json.loads(msg)
            assert data["payload"]["message"] == "still alive"


@pytest.mark.asyncio
async def test_ignore_invalid_json(notification_server):
    uri = f"ws://localhost:{notification_server.port}"
    async with connect(uri) as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)
        await ws.send("not valid json{{{{")
        await ws.send(json.dumps({
            "type": "broadcast",
            "payload": {"message": "after bad json"}
        }))
        msg = await asyncio.wait_for(ws.recv(), timeout=5)
        data = json.loads(msg)
        assert data["payload"]["message"] == "after bad json"


@pytest.mark.asyncio
async def test_message_format_fields(notification_server):
    uri = f"ws://localhost:{notification_server.port}"

    async with connect(uri) as ws:
        welcome = await asyncio.wait_for(ws.recv(), timeout=5)
        welcome_data = json.loads(welcome)

        assert "type" in welcome_data
        assert "payload" in welcome_data
        assert "timestamp" in welcome_data
        assert welcome_data["type"] == "system"

        await ws.send(json.dumps({
            "type": "broadcast",
            "payload": {"k": "v"}
        }))

        msg = await asyncio.wait_for(ws.recv(), timeout=5)
        data = json.loads(msg)
        assert data["type"] == "broadcast"
        assert data["payload"] == {"k": "v"}
        assert "timestamp" in data


@pytest.mark.asyncio
async def test_multiple_clients_connect_and_disconnect(notification_server):
    port = notification_server.port
    uri = f"ws://localhost:{port}"

    async with connect(uri) as ws1, connect(uri) as ws2, connect(uri) as ws3:
        await asyncio.wait_for(ws1.recv(), timeout=5)
        await asyncio.wait_for(ws2.recv(), timeout=5)
        await asyncio.wait_for(ws3.recv(), timeout=5)

        await asyncio.sleep(0.05)
        data = await async_http_get("localhost", port, "/health")
        assert data["clients"] == 3

    await asyncio.sleep(0.15)
    data = await async_http_get("localhost", port, "/health")
    assert data["clients"] == 0


class TestClientRegistryChannels:
    def test_subscribe_and_get_subscribers(self):
        reg = ClientRegistry()
        reg.subscribe("id1", "alerts")
        assert reg.get_subscribers("alerts") == ["id1"]
        reg.subscribe("id2", "alerts")
        assert set(reg.get_subscribers("alerts")) == {"id1", "id2"}

    def test_subscribe_multiple_channels(self):
        reg = ClientRegistry()
        reg.subscribe("id1", "alerts")
        reg.subscribe("id1", "system")
        assert set(reg.get_subscribers("alerts")) == {"id1"}
        assert set(reg.get_subscribers("system")) == {"id1"}

    def test_unsubscribe(self):
        reg = ClientRegistry()
        reg.subscribe("id1", "alerts")
        reg.subscribe("id2", "alerts")
        reg.unsubscribe("id1", "alerts")
        assert reg.get_subscribers("alerts") == ["id2"]
        reg.unsubscribe("id2", "alerts")
        assert reg.get_subscribers("alerts") == []

    def test_unsubscribe_nonexistent_channel_is_safe(self):
        reg = ClientRegistry()
        reg.unsubscribe("id1", "alerts")

    def test_get_subscribers_nonexistent_channel(self):
        reg = ClientRegistry()
        assert reg.get_subscribers("nonexistent") == []

    def test_get_channels(self):
        reg = ClientRegistry()
        reg.subscribe("id1", "alerts")
        reg.subscribe("id1", "system")
        reg.subscribe("id2", "alerts")
        channels = reg.get_channels()
        assert channels == {"alerts": 2, "system": 1}

    def test_get_channels_empty(self):
        reg = ClientRegistry()
        assert reg.get_channels() == {}

    def test_remove_cleans_up_subscriptions(self):
        reg = ClientRegistry()
        reg.subscribe("id1", "alerts")
        reg.subscribe("id1", "system")
        reg.add("id1", object())
        reg.remove("id1")
        assert reg.get_subscribers("alerts") == []
        assert reg.get_subscribers("system") == []
        assert reg.get_channels() == {}

    def test_clear_removes_subscriptions(self):
        reg = ClientRegistry()
        reg.subscribe("id1", "alerts")
        reg.add("id1", object())
        reg.clear()
        assert reg.count() == 0
        assert reg.get_channels() == {}
        assert reg.get_subscribers("alerts") == []

    def test_duplicate_subscribe_is_idempotent(self):
        reg = ClientRegistry()
        reg.subscribe("id1", "alerts")
        reg.subscribe("id1", "alerts")
        assert reg.get_subscribers("alerts") == ["id1"]

    def test_get_subscriber_websockets(self):
        reg = ClientRegistry()
        ws1 = object()
        ws2 = object()
        reg.add("id1", ws1)
        reg.add("id2", ws2)
        reg.subscribe("id1", "alerts")
        reg.subscribe("id2", "alerts")
        results = reg.get_subscriber_websockets("alerts")
        assert len(results) == 2
        assert results["id1"] is ws1
        assert results["id2"] is ws2

    def test_get_subscriber_websockets_skips_disconnected(self):
        reg = ClientRegistry()
        ws1 = object()
        reg.add("id1", ws1)
        reg.subscribe("id1", "alerts")
        reg.subscribe("id2", "alerts")
        results = reg.get_subscriber_websockets("alerts")
        assert list(results.keys()) == ["id1"]
        assert results["id1"] is ws1


@pytest.mark.asyncio
async def test_client_subscribe_to_channel(notification_server):
    uri = f"ws://localhost:{notification_server.port}"
    async with connect(uri) as ws:
        welcome = await asyncio.wait_for(ws.recv(), timeout=5)
        client_id = json.loads(welcome)["payload"]["client_id"]

        await ws.send(json.dumps({
            "type": "subscribe",
            "channel": "alerts"
        }))

        await asyncio.sleep(0.05)
        data = await async_http_get("localhost", notification_server.port,
                                    "/channels/alerts/subscribers")
        assert client_id in data["subscribers"]


@pytest.mark.asyncio
async def test_client_unsubscribe_from_channel(notification_server):
    uri = f"ws://localhost:{notification_server.port}"
    async with connect(uri) as ws:
        welcome = await asyncio.wait_for(ws.recv(), timeout=5)
        client_id = json.loads(welcome)["payload"]["client_id"]

        await ws.send(json.dumps({
            "type": "subscribe",
            "channel": "alerts"
        }))
        await ws.send(json.dumps({
            "type": "unsubscribe",
            "channel": "alerts"
        }))

        await asyncio.sleep(0.05)
        data = await async_http_get("localhost", notification_server.port,
                                    "/channels/alerts/subscribers")
        assert client_id not in data["subscribers"]


@pytest.mark.asyncio
async def test_channel_message_only_reaches_subscribers(notification_server):
    uri = f"ws://localhost:{notification_server.port}"

    async with connect(uri) as client1, connect(uri) as client2:
        await asyncio.wait_for(client1.recv(), timeout=5)
        await asyncio.wait_for(client2.recv(), timeout=5)

        await client1.send(json.dumps({
            "type": "subscribe",
            "channel": "alerts"
        }))
        await asyncio.sleep(0.05)

        await client1.send(json.dumps({
            "type": "broadcast",
            "channel": "alerts",
            "payload": {"message": "alert!"}
        }))

        msg = await asyncio.wait_for(client1.recv(), timeout=5)
        data = json.loads(msg)
        assert data["type"] == "broadcast"
        assert data["channel"] == "alerts"
        assert data["payload"]["message"] == "alert!"

        try:
            msg2 = await asyncio.wait_for(client2.recv(), timeout=1)
            assert False, "client2 should not have received the message"
        except asyncio.TimeoutError:
            pass


@pytest.mark.asyncio
async def test_broadcast_without_channel_reaches_all(notification_server):
    uri = f"ws://localhost:{notification_server.port}"

    async with connect(uri) as client1, connect(uri) as client2:
        await asyncio.wait_for(client1.recv(), timeout=5)
        await asyncio.wait_for(client2.recv(), timeout=5)

        await client1.send(json.dumps({
            "type": "subscribe",
            "channel": "alerts"
        }))
        await asyncio.sleep(0.05)

        await client1.send(json.dumps({
            "type": "broadcast",
            "payload": {"message": "everyone"}
        }))

        msg1 = await asyncio.wait_for(client1.recv(), timeout=5)
        msg2 = await asyncio.wait_for(client2.recv(), timeout=5)
        assert json.loads(msg1)["payload"]["message"] == "everyone"
        assert json.loads(msg2)["payload"]["message"] == "everyone"


@pytest.mark.asyncio
async def test_client_multiple_channel_subscriptions(notification_server):
    uri = f"ws://localhost:{notification_server.port}"

    async with connect(uri) as client:
        await asyncio.wait_for(client.recv(), timeout=5)

        await client.send(json.dumps({
            "type": "subscribe",
            "channel": "alerts"
        }))
        await client.send(json.dumps({
            "type": "subscribe",
            "channel": "system"
        }))
        await asyncio.sleep(0.05)

        port = notification_server.port
        data1 = await async_http_get("localhost", port, "/channels/alerts/subscribers")
        data2 = await async_http_get("localhost", port, "/channels/system/subscribers")
        assert len(data1["subscribers"]) == 1
        assert len(data2["subscribers"]) == 1


@pytest.mark.asyncio
async def test_dynamic_unsubscribe_stops_delivery(notification_server):
    uri = f"ws://localhost:{notification_server.port}"

    async with connect(uri) as client1, connect(uri) as client2:
        await asyncio.wait_for(client1.recv(), timeout=5)
        id2 = json.loads(await asyncio.wait_for(client2.recv(), timeout=5))["payload"]["client_id"]

        await client1.send(json.dumps({
            "type": "subscribe",
            "channel": "alerts"
        }))
        await client2.send(json.dumps({
            "type": "subscribe",
            "channel": "alerts"
        }))
        await asyncio.sleep(0.05)

        await client1.send(json.dumps({
            "type": "broadcast",
            "channel": "alerts",
            "payload": {"message": "first"}
        }))
        await asyncio.wait_for(client1.recv(), timeout=5)
        await asyncio.wait_for(client2.recv(), timeout=5)

        await client1.send(json.dumps({
            "type": "unsubscribe",
            "channel": "alerts"
        }))
        await asyncio.sleep(0.05)

        await client2.send(json.dumps({
            "type": "broadcast",
            "channel": "alerts",
            "payload": {"message": "second"}
        }))

        msg = await asyncio.wait_for(client2.recv(), timeout=5)
        assert json.loads(msg)["payload"]["message"] == "second"

        try:
            msg2 = await asyncio.wait_for(client1.recv(), timeout=1)
            assert False, "client1 should not receive after unsubscribing"
        except asyncio.TimeoutError:
            pass


@pytest.mark.asyncio
async def test_disconnect_cleans_up_subscriptions(notification_server):
    port = notification_server.port
    uri = f"ws://localhost:{port}"

    async with connect(uri) as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)
        await ws.send(json.dumps({
            "type": "subscribe",
            "channel": "alerts"
        }))
        await asyncio.sleep(0.05)
        data = await async_http_get("localhost", port, "/channels")
        assert data["channels"]["alerts"] == 1

    await asyncio.sleep(0.1)
    data = await async_http_get("localhost", port, "/channels")
    assert data["channels"].get("alerts", 0) == 0


@pytest.mark.asyncio
async def test_get_channels_endpoint(notification_server):
    port = notification_server.port
    uri = f"ws://localhost:{port}"

    async with connect(uri) as ws1, connect(uri) as ws2:
        id1 = json.loads(await asyncio.wait_for(ws1.recv(), timeout=5))["payload"]["client_id"]
        id2 = json.loads(await asyncio.wait_for(ws2.recv(), timeout=5))["payload"]["client_id"]

        await ws1.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        await ws2.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        await ws2.send(json.dumps({"type": "subscribe", "channel": "chat"}))
        await asyncio.sleep(0.05)

        data = await async_http_get("localhost", port, "/channels")
        assert data["channels"] == {"alerts": 2, "chat": 1}


@pytest.mark.asyncio
async def test_get_channel_subscribers_endpoint(notification_server):
    port = notification_server.port
    uri = f"ws://localhost:{port}"

    async with connect(uri) as ws:
        welcome = await asyncio.wait_for(ws.recv(), timeout=5)
        client_id = json.loads(welcome)["payload"]["client_id"]

        await ws.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        await asyncio.sleep(0.05)

        data = await async_http_get("localhost", port, "/channels/alerts/subscribers")
        assert data["channel"] == "alerts"
        assert data["subscribers"] == [client_id]


@pytest.mark.asyncio
async def test_channel_message_to_empty_channel(notification_server):
    uri = f"ws://localhost:{notification_server.port}"

    async with connect(uri) as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)

        await ws.send(json.dumps({
            "type": "broadcast",
            "channel": "empty_channel",
            "payload": {"message": "nobody"}
        }))

        await asyncio.sleep(0.1)

        await ws.send(json.dumps({
            "type": "broadcast",
            "payload": {"message": "after empty"}
        }))
        msg = await asyncio.wait_for(ws.recv(), timeout=5)
        assert json.loads(msg)["payload"]["message"] == "after empty"


@pytest.mark.asyncio
async def test_subscribe_without_channel_field_is_safe(notification_server):
    uri = f"ws://localhost:{notification_server.port}"
    async with connect(uri) as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)
        await ws.send(json.dumps({"type": "subscribe"}))
        await ws.send(json.dumps({"type": "unsubscribe"}))
        await ws.send(json.dumps({
            "type": "broadcast",
            "payload": {"message": "hello"}
        }))
        msg = await asyncio.wait_for(ws.recv(), timeout=5)
        assert json.loads(msg)["payload"]["message"] == "hello"


class TestMessageStore:
    def test_init_creates_table(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            store = MessageStore(f.name)
            messages = store.get_messages()
            assert messages == []

    def test_save_and_retrieve(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            store = MessageStore(f.name)
            store.save("alerts", "broadcast", {"msg": "hello"}, "2024-01-01T00:00:00")
            store.save("system", "broadcast", {"msg": "world"}, "2024-01-01T00:00:01")

            messages = store.get_messages()
            assert len(messages) == 2
            assert messages[0]["channel"] == "system"
            assert messages[1]["channel"] == "alerts"

    def test_get_messages_with_limit_and_offset(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            store = MessageStore(f.name)
            for i in range(10):
                store.save("test", "broadcast", {"idx": i}, f"2024-01-01T00:00:{i:02d}")

            messages = store.get_messages(limit=3, offset=0)
            assert len(messages) == 3
            assert messages[0]["payload"]["idx"] == 9

            messages = store.get_messages(limit=3, offset=3)
            assert len(messages) == 3
            assert messages[0]["payload"]["idx"] == 6

    def test_empty_channel_is_stored(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            store = MessageStore(f.name)
            store.save("", "direct", {"msg": "test"}, "2024-01-01T00:00:00")
            messages = store.get_messages()
            assert len(messages) == 1
            assert messages[0]["channel"] == ""

    def test_none_channel_is_stored_as_empty(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            store = MessageStore(f.name)
            store.save(None, "system", {"msg": "test"}, "2024-01-01T00:00:00")
            messages = store.get_messages()
            assert len(messages) == 1
            assert messages[0]["channel"] == ""


@pytest.mark.asyncio
async def test_messages_endpoint_returns_empty(notification_server):
    port = notification_server.port
    data = await async_http_get("localhost", port, "/messages")
    assert "messages" in data
    assert data["messages"] == []


@pytest.mark.asyncio
async def test_messages_endpoint_with_data(notification_server):
    uri = f"ws://localhost:{notification_server.port}"

    async with connect(uri) as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)

        await ws.send(json.dumps({
            "type": "broadcast",
            "payload": {"message": "first"}
        }))
        await asyncio.wait_for(ws.recv(), timeout=5)

        await ws.send(json.dumps({
            "type": "broadcast",
            "payload": {"message": "second"}
        }))
        await asyncio.wait_for(ws.recv(), timeout=5)

    await asyncio.sleep(0.1)
    data = await async_http_get("localhost", notification_server.port, "/messages")
    assert len(data["messages"]) == 2
    assert data["messages"][0]["payload"]["message"] == "second"
    assert data["messages"][1]["payload"]["message"] == "first"


@pytest.mark.asyncio
async def test_messages_endpoint_respects_limit(notification_server):
    uri = f"ws://localhost:{notification_server.port}"

    async with connect(uri) as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)
        for i in range(5):
            await ws.send(json.dumps({
                "type": "broadcast",
                "payload": {"idx": i}
            }))
            await asyncio.wait_for(ws.recv(), timeout=5)

    await asyncio.sleep(0.1)
    data = await async_http_get("localhost", notification_server.port, "/messages?limit=2")
    assert len(data["messages"]) == 2


@pytest.mark.asyncio
async def test_messages_endpoint_respects_offset(notification_server):
    uri = f"ws://localhost:{notification_server.port}"

    async with connect(uri) as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)
        for i in range(5):
            await ws.send(json.dumps({
                "type": "broadcast",
                "payload": {"idx": i}
            }))
            await asyncio.wait_for(ws.recv(), timeout=5)

    await asyncio.sleep(0.1)
    data = await async_http_get("localhost", notification_server.port, "/messages?limit=2&offset=2")
    assert len(data["messages"]) == 2
    assert data["messages"][0]["payload"]["idx"] == 2


@pytest.mark.asyncio
async def test_messages_endpoint_includes_channel_field(notification_server):
    uri = f"ws://localhost:{notification_server.port}"

    async with connect(uri) as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)
        await ws.send(json.dumps({
            "type": "subscribe",
            "channel": "alerts",
        }))
        await asyncio.sleep(0.05)
        await ws.send(json.dumps({
            "type": "broadcast",
            "channel": "alerts",
            "payload": {"message": "test"}
        }))
        await asyncio.wait_for(ws.recv(), timeout=5)

    await asyncio.sleep(0.1)
    data = await async_http_get("localhost", notification_server.port, "/messages")
    assert len(data["messages"]) == 1
    assert data["messages"][0]["channel"] == "alerts"
    assert data["messages"][0]["type"] == "broadcast"


@pytest.mark.asyncio
async def test_direct_message_is_persisted(notification_server):
    uri = f"ws://localhost:{notification_server.port}"

    async with connect(uri) as sender, connect(uri) as target:
        welcome1 = await asyncio.wait_for(sender.recv(), timeout=5)
        welcome2 = await asyncio.wait_for(target.recv(), timeout=5)
        target_id = json.loads(welcome2)["payload"]["client_id"]

        await sender.send(json.dumps({
            "type": "direct",
            "target": target_id,
            "payload": {"message": "private"}
        }))
        await asyncio.wait_for(target.recv(), timeout=5)

    await asyncio.sleep(0.1)
    data = await async_http_get("localhost", notification_server.port, "/messages")
    assert len(data["messages"]) == 1
    assert data["messages"][0]["type"] == "direct"
    assert data["messages"][0]["payload"]["message"] == "private"


@pytest.mark.asyncio
async def test_messages_persist_across_server_connections(notification_server):
    port = notification_server.port
    uri = f"ws://localhost:{port}"

    async with connect(uri) as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)
        await ws.send(json.dumps({
            "type": "broadcast",
            "payload": {"message": "persistent"}
        }))
        await asyncio.wait_for(ws.recv(), timeout=5)

    await asyncio.sleep(0.1)
    data = await async_http_get("localhost", port, "/messages")
    assert len(data["messages"]) == 1
    assert data["messages"][0]["payload"]["message"] == "persistent"


@skip_if_no_redis
class TestRedisPubSub:
    async def _flush_redis(self):
        import redis.asyncio as aioredis
        r = aioredis.from_url(REDIS_URL)
        await r.flushdb()
        await r.close()

    @pytest.fixture
    async def redis_server(self):
        await self._flush_redis()
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            server = NotificationServer(host="localhost", port=0, redis_url=REDIS_URL, database_url=db_path)
            async with server.run() as ws_server:
                server.port = ws_server.sockets[0].getsockname()[1]
                yield server
        finally:
            try:
                os.unlink(db_path)
            except OSError:
                pass

    @pytest.mark.asyncio
    async def test_redis_connection_is_established(self, redis_server):
        assert redis_server._redis_available is True
        assert redis_server._redis is not None

    @pytest.mark.asyncio
    async def test_broadcast_via_redis_reaches_client(self, redis_server):
        uri = f"ws://localhost:{redis_server.port}"

        async with connect(uri) as client1, connect(uri) as client2:
            await asyncio.wait_for(client1.recv(), timeout=5)
            await asyncio.wait_for(client2.recv(), timeout=5)

            await client1.send(json.dumps({
                "type": "broadcast",
                "payload": {"message": "via_redis"}
            }))

            msg1 = await asyncio.wait_for(client1.recv(), timeout=5)
            msg2 = await asyncio.wait_for(client2.recv(), timeout=5)

            assert json.loads(msg1)["payload"]["message"] == "via_redis"
            assert json.loads(msg2)["payload"]["message"] == "via_redis"

    @pytest.mark.asyncio
    async def test_channel_message_via_redis(self, redis_server):
        uri = f"ws://localhost:{redis_server.port}"

        async with connect(uri) as client1, connect(uri) as client2:
            await asyncio.wait_for(client1.recv(), timeout=5)
            await asyncio.wait_for(client2.recv(), timeout=5)

            await client1.send(json.dumps({
                "type": "subscribe",
                "channel": "alerts"
            }))
            await asyncio.sleep(0.1)

            await client1.send(json.dumps({
                "type": "broadcast",
                "channel": "alerts",
                "payload": {"message": "redis_alert"}
            }))

            msg = await asyncio.wait_for(client1.recv(), timeout=5)
            assert json.loads(msg)["payload"]["message"] == "redis_alert"
            assert json.loads(msg)["channel"] == "alerts"

            try:
                await asyncio.wait_for(client2.recv(), timeout=1)
                assert False, "client2 should not receive channel message"
            except asyncio.TimeoutError:
                pass

    @pytest.mark.asyncio
    async def test_subscription_stored_in_redis(self, redis_server):
        import redis.asyncio as aioredis
        r = aioredis.from_url(REDIS_URL)
        uri = f"ws://localhost:{redis_server.port}"

        async with connect(uri) as ws:
            await asyncio.wait_for(ws.recv(), timeout=5)

            await ws.send(json.dumps({
                "type": "subscribe",
                "channel": "alerts"
            }))
            await asyncio.sleep(0.1)

            members = await r.smembers("sub:alerts")
            assert len(members) == 1

        await r.close()

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_from_redis(self, redis_server):
        import redis.asyncio as aioredis
        r = aioredis.from_url(REDIS_URL)
        uri = f"ws://localhost:{redis_server.port}"

        async with connect(uri) as ws:
            await asyncio.wait_for(ws.recv(), timeout=5)

            await ws.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
            await asyncio.sleep(0.05)

            await ws.send(json.dumps({"type": "unsubscribe", "channel": "alerts"}))
            await asyncio.sleep(0.05)

            members = await r.smembers("sub:alerts")
            assert len(members) == 0

        await r.close()

    @pytest.mark.asyncio
    async def test_disconnect_cleans_redis_subscriptions(self, redis_server):
        import redis.asyncio as aioredis
        r = aioredis.from_url(REDIS_URL)
        uri = f"ws://localhost:{redis_server.port}"

        async with connect(uri) as ws:
            await asyncio.wait_for(ws.recv(), timeout=5)
            await ws.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
            await asyncio.sleep(0.05)

            members = await r.smembers("sub:alerts")
            assert len(members) == 1

        await asyncio.sleep(0.1)
        members = await r.smembers("sub:alerts")
        assert len(members) == 0

        await r.close()

    @pytest.mark.asyncio
    async def test_direct_message_not_sent_via_redis(self, redis_server):
        uri = f"ws://localhost:{redis_server.port}"

        async with connect(uri) as sender, connect(uri) as target:
            welcome1 = await asyncio.wait_for(sender.recv(), timeout=5)
            welcome2 = await asyncio.wait_for(target.recv(), timeout=5)
            sender_id = json.loads(welcome1)["payload"]["client_id"]
            target_id = json.loads(welcome2)["payload"]["client_id"]

            await sender.send(json.dumps({
                "type": "direct",
                "target": target_id,
                "payload": {"message": "private"}
            }))

            msg = await asyncio.wait_for(target.recv(), timeout=5)
            assert json.loads(msg)["type"] == "direct"
            assert json.loads(msg)["sender"] == sender_id

    @pytest.mark.asyncio
    async def test_message_persistence_in_redis_mode(self, redis_server):
        uri = f"ws://localhost:{redis_server.port}"

        async with connect(uri) as ws:
            await asyncio.wait_for(ws.recv(), timeout=5)
            await ws.send(json.dumps({
                "type": "broadcast",
                "payload": {"message": "persisted"}
            }))
            await asyncio.wait_for(ws.recv(), timeout=5)

        await asyncio.sleep(0.1)
        data = await async_http_get("localhost", redis_server.port, "/messages")
        assert len(data["messages"]) == 1
        assert data["messages"][0]["payload"]["message"] == "persisted"


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_allows_within_limit(self):
        limiter = RateLimiter(limit=3)
        for _ in range(3):
            allowed, _ = await limiter.check_and_increment("client1")
            assert allowed is True

    @pytest.mark.asyncio
    async def test_blocks_exceeded(self):
        limiter = RateLimiter(limit=3)
        for _ in range(3):
            await limiter.check_and_increment("client1")
        allowed, count = await limiter.check_and_increment("client1")
        assert allowed is False
        assert count == 4

    @pytest.mark.asyncio
    async def test_different_clients_separate_counters(self):
        limiter = RateLimiter(limit=2)
        for _ in range(3):
            await limiter.check_and_increment("client1")
        allowed, _ = await limiter.check_and_increment("client2")
        assert allowed is True

    @pytest.mark.asyncio
    async def test_increment_returns_count(self):
        limiter = RateLimiter(limit=100)
        _, count1 = await limiter.check_and_increment("c1")
        _, count2 = await limiter.check_and_increment("c1")
        assert count1 == 1
        assert count2 == 2

    def test_thread_safety_local_mode(self):
        limiter = RateLimiter(limit=10000)
        errors = []

        async def burst(client_id, count):
            try:
                for _ in range(count):
                    await limiter.check_and_increment(client_id)
            except Exception as e:
                errors.append(e)

        async def run():
            tasks = [
                burst("a", 200),
                burst("b", 200),
                burst("c", 200),
            ]
            await asyncio.gather(*tasks)

        asyncio.run(run())
        assert len(errors) == 0


class TestMessageStoreHistory:
    def test_get_history_empty(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            store = MessageStore(f.name)
            result = store.get_history()
            assert result["messages"] == []
            assert result["has_more"] is False

    def test_get_history_channel_filter(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            store = MessageStore(f.name)
            store.save("alerts", "broadcast", {"msg": "a"}, "2024-01-01T00:00:00+00:00")
            store.save("system", "broadcast", {"msg": "b"}, "2024-01-01T00:00:01+00:00")
            store.save("alerts", "broadcast", {"msg": "c"}, "2024-01-01T00:00:02+00:00")

            result = store.get_history(channel="alerts")
            assert len(result["messages"]) == 2
            assert result["messages"][0]["payload"]["msg"] == "a"
            assert result["messages"][1]["payload"]["msg"] == "c"
            assert result["has_more"] is False

    def test_get_history_since_filter(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            store = MessageStore(f.name)
            store.save("test", "broadcast", {"msg": "old"}, "2024-01-01T00:00:00+00:00")
            store.save("test", "broadcast", {"msg": "new"}, "2024-01-01T00:00:02+00:00")

            result = store.get_history(since="2024-01-01T00:00:01+00:00")
            assert len(result["messages"]) == 1
            assert result["messages"][0]["payload"]["msg"] == "new"

    def test_get_history_chronological_order(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            store = MessageStore(f.name)
            store.save("test", "broadcast", {"idx": 2}, "2024-01-01T00:00:02+00:00")
            store.save("test", "broadcast", {"idx": 1}, "2024-01-01T00:00:01+00:00")
            store.save("test", "broadcast", {"idx": 3}, "2024-01-01T00:00:03+00:00")

            result = store.get_history()
            assert [m["payload"]["idx"] for m in result["messages"]] == [1, 2, 3]

    def test_get_history_limit(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            store = MessageStore(f.name)
            for i in range(10):
                store.save("test", "broadcast", {"idx": i}, f"2024-01-01T00:00:{i:02d}+00:00")

            result = store.get_history(limit=3)
            assert len(result["messages"]) == 3
            assert [m["payload"]["idx"] for m in result["messages"]] == [0, 1, 2]

    def test_get_history_has_more(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            store = MessageStore(f.name)
            for i in range(5):
                store.save("test", "broadcast", {"idx": i}, f"2024-01-01T00:00:{i:02d}+00:00")

            result = store.get_history(limit=3)
            assert result["has_more"] is True
            assert len(result["messages"]) == 3

            result = store.get_history(limit=10)
            assert result["has_more"] is False
            assert len(result["messages"]) == 5

    def test_get_history_channel_and_since(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            store = MessageStore(f.name)
            store.save("a", "broadcast", {"msg": "1"}, "2024-01-01T00:00:00+00:00")
            store.save("b", "broadcast", {"msg": "2"}, "2024-01-01T00:00:01+00:00")
            store.save("a", "broadcast", {"msg": "3"}, "2024-01-01T00:00:02+00:00")
            store.save("a", "broadcast", {"msg": "4"}, "2024-01-01T00:00:03+00:00")

            result = store.get_history(channel="a", since="2024-01-01T00:00:01+00:00")
            assert len(result["messages"]) == 2
            assert [m["payload"]["msg"] for m in result["messages"]] == ["3", "4"]

    def test_cleanup_old(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            store = MessageStore(f.name)
            from datetime import datetime, timedelta, timezone

            recent = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
            old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()

            store.save("test", "broadcast", {"msg": "old"}, old)
            store.save("test", "broadcast", {"msg": "recent"}, recent)

            store.cleanup_old(ttl_days=7)

            messages = store.get_messages()
            assert len(messages) == 1
            assert messages[0]["payload"]["msg"] == "recent"

    def test_cleanup_old_default(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            store = MessageStore(f.name)
            from datetime import datetime, timedelta, timezone

            recent = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
            very_old = "2020-01-01T00:00:00+00:00"

            store.save("test", "broadcast", {"msg": "ancient"}, very_old)
            store.save("test", "broadcast", {"msg": "recent"}, recent)

            store.cleanup_old(ttl_days=7)

            messages = store.get_messages()
            assert len(messages) == 1
            assert messages[0]["payload"]["msg"] == "recent"


@pytest.mark.asyncio
async def test_rate_limit_exceeded_sends_error(rate_limited_server):
    uri = f"ws://localhost:{rate_limited_server.port}"
    async with connect(uri) as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)

        for _ in range(6):
            await ws.send(json.dumps({
                "type": "broadcast",
                "payload": {"msg": "test"}
            }))

        messages = []
        for _ in range(10):
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=2)
                messages.append(json.loads(msg))
            except asyncio.TimeoutError:
                break

        error_messages = [m for m in messages if m["type"] == "error"]
        assert len(error_messages) >= 1
        assert "Rate limit exceeded" in error_messages[0]["payload"]["message"]


@pytest.mark.asyncio
async def test_rate_limit_stops_processing(rate_limited_server):
    uri = f"ws://localhost:{rate_limited_server.port}"
    async with connect(uri) as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)

        for i in range(10):
            await ws.send(json.dumps({
                "type": "broadcast",
                "payload": {"idx": i}
            }))

        received = []
        for _ in range(10):
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=2)
                received.append(json.loads(msg))
            except asyncio.TimeoutError:
                break

        errors = [m for m in received if m["type"] == "error"]
        broadcasts = [m for m in received if m["type"] == "broadcast"]
        assert len(errors) >= 1
        assert len(broadcasts) <= 5


@pytest.mark.asyncio
async def test_history_endpoint_empty(notification_server):
    port = notification_server.port
    data = await async_http_get("localhost", port, "/history")
    assert data["messages"] == []
    assert data["has_more"] is False


@pytest.mark.asyncio
async def test_history_endpoint_with_data(notification_server):
    uri = f"ws://localhost:{notification_server.port}"

    async with connect(uri) as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)

        for i in range(3):
            await ws.send(json.dumps({
                "type": "broadcast",
                "payload": {"idx": i}
            }))
            await asyncio.wait_for(ws.recv(), timeout=5)

    await asyncio.sleep(0.1)
    data = await async_http_get("localhost", notification_server.port, "/history")
    assert len(data["messages"]) == 3
    assert data["has_more"] is False


@pytest.mark.asyncio
async def test_history_endpoint_channel_filter(notification_server):
    uri = f"ws://localhost:{notification_server.port}"

    async with connect(uri) as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)
        await ws.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        await asyncio.sleep(0.05)

        await ws.send(json.dumps({
            "type": "broadcast",
            "channel": "alerts",
            "payload": {"msg": "alert1"}
        }))
        await asyncio.wait_for(ws.recv(), timeout=5)

        await ws.send(json.dumps({
            "type": "broadcast",
            "payload": {"msg": "sys1"}
        }))
        await asyncio.wait_for(ws.recv(), timeout=5)

    await asyncio.sleep(0.1)
    data = await async_http_get("localhost", notification_server.port,
                                "/history?channel=alerts")
    assert len(data["messages"]) == 1
    assert data["messages"][0]["channel"] == "alerts"
    assert data["messages"][0]["payload"]["msg"] == "alert1"


@pytest.mark.asyncio
async def test_history_endpoint_has_more(notification_server):
    uri = f"ws://localhost:{notification_server.port}"

    async with connect(uri) as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)
        for i in range(5):
            await ws.send(json.dumps({
                "type": "broadcast",
                "payload": {"idx": i}
            }))
            await asyncio.wait_for(ws.recv(), timeout=5)

    await asyncio.sleep(0.1)
    data = await async_http_get("localhost", notification_server.port, "/history?limit=2")
    assert len(data["messages"]) == 2
    assert data["has_more"] is True

    data = await async_http_get("localhost", notification_server.port, "/history?limit=10")
    assert len(data["messages"]) == 5
    assert data["has_more"] is False


@pytest.mark.asyncio
async def test_history_endpoint_respects_limit(notification_server):
    uri = f"ws://localhost:{notification_server.port}"

    async with connect(uri) as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)
        for i in range(10):
            await ws.send(json.dumps({
                "type": "broadcast",
                "payload": {"idx": i}
            }))
            await asyncio.wait_for(ws.recv(), timeout=5)

    await asyncio.sleep(0.1)
    data = await async_http_get("localhost", notification_server.port, "/history?limit=3")
    assert len(data["messages"]) == 3


@pytest.mark.asyncio
async def test_history_endpoint_chronological_order(notification_server):
    uri = f"ws://localhost:{notification_server.port}"

    async with connect(uri) as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)
        for i in range(3):
            await ws.send(json.dumps({
                "type": "broadcast",
                "payload": {"idx": i}
            }))
            await asyncio.wait_for(ws.recv(), timeout=5)
            await asyncio.sleep(0.02)

    await asyncio.sleep(0.1)
    data = await async_http_get("localhost", notification_server.port, "/history")
    idxs = [m["payload"]["idx"] for m in data["messages"]]
    assert idxs == sorted(idxs)


@pytest.mark.asyncio
async def test_history_endpoint_with_channel_and_since(notification_server):
    uri = f"ws://localhost:{notification_server.port}"

    t_before = None
    async with connect(uri) as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)
        await ws.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        await asyncio.sleep(0.05)

        for i in range(3):
            await ws.send(json.dumps({
                "type": "broadcast",
                "channel": "alerts",
                "payload": {"idx": i}
            }))
            await asyncio.wait_for(ws.recv(), timeout=5)
            await asyncio.sleep(0.02)

        t_before = "2024-01-01T00:00:00+00:00"

    await asyncio.sleep(0.1)

    data = await async_http_get("localhost", notification_server.port,
                                f"/history?channel=alerts&since={t_before}")
    assert len(data["messages"]) == 3
    for m in data["messages"]:
        assert m["channel"] == "alerts"
