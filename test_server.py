import json
import asyncio
import os
import threading
import tempfile
from unittest.mock import patch

import pytest
import pytest_asyncio
from websockets.asyncio.client import connect

from server import (
    ClientRegistry,
    ChannelManager,
    MessageStore,
    make_message,
    registry,
    channel_manager,
    message_store,
    redis_broker,
    main,
)


@pytest.fixture(autouse=True)
def reset_registry():
    for cid in list(registry.get_all()):
        registry.remove(cid[0])
    channel_manager.reset()
    message_store.clear()
    if redis_broker._redis:
        redis_broker._redis = None
    if redis_broker._pubsub:
        redis_broker._pubsub = None
    if redis_broker._listener_task:
        redis_broker._listener_task = None
    os.environ.pop("REDIS_URL", None)


@pytest_asyncio.fixture
async def server():
    task = asyncio.create_task(main())
    await asyncio.sleep(0.2)
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await asyncio.sleep(0.1)


@pytest_asyncio.fixture
async def server_with_redis():
    import fakeredis.aioredis

    fake_redis = fakeredis.aioredis.FakeRedis()
    os.environ["REDIS_URL"] = "redis://test"

    with patch("redis.asyncio.from_url", return_value=fake_redis):
        task = asyncio.create_task(main())
        await asyncio.sleep(0.4)
        yield fake_redis
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        await asyncio.sleep(0.1)
    await fake_redis.close()


def http_get(url):
    import urllib.request
    resp = urllib.request.urlopen(url)
    return json.loads(resp.read())


# ---------------------------------------------------------------------------
# Existing integration tests (unchanged)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_client_gets_unique_id(server):
    async with connect("ws://127.0.0.1:8765") as ws:
        msg = json.loads(await ws.recv())
        assert msg["type"] == "system"
        assert msg["payload"]["message"] == "connected"
        assert "client_id" in msg["payload"]
        assert isinstance(msg["payload"]["client_id"], str)
        assert len(msg["payload"]["client_id"]) > 0
        assert "timestamp" in msg


@pytest.mark.asyncio
async def test_multiple_clients_get_unique_ids(server):
    async with (
        connect("ws://127.0.0.1:8765") as ws1,
        connect("ws://127.0.0.1:8765") as ws2,
    ):
        msg1 = json.loads(await ws1.recv())
        msg2 = json.loads(await ws2.recv())
        assert msg1["payload"]["client_id"] != msg2["payload"]["client_id"]


@pytest.mark.asyncio
async def test_broadcast_to_all_clients(server):
    async with (
        connect("ws://127.0.0.1:8765") as ws1,
        connect("ws://127.0.0.1:8765") as ws2,
        connect("ws://127.0.0.1:8765") as ws3,
    ):
        await ws1.recv()
        await ws2.recv()
        await ws3.recv()

        await ws1.send(json.dumps({
            "type": "broadcast",
            "payload": {"text": "hello all"},
        }))

        for ws in (ws2, ws3):
            msg = json.loads(await ws.recv())
            assert msg["type"] == "broadcast"
            assert msg["payload"]["text"] == "hello all"
            assert "timestamp" in msg


@pytest.mark.asyncio
async def test_direct_message_type(server):
    async with (
        connect("ws://127.0.0.1:8765") as ws1,
        connect("ws://127.0.0.1:8765") as ws2,
    ):
        await ws1.recv()
        await ws2.recv()

        await ws1.send(json.dumps({
            "type": "direct",
            "payload": {"target": "someone", "text": "private"},
        }))

        msg = json.loads(await ws2.recv())
        assert msg["type"] == "direct"
        assert msg["payload"]["text"] == "private"


@pytest.mark.asyncio
async def test_client_disconnect_removes_from_registry(server):
    for _ in range(3):
        async with connect("ws://127.0.0.1:8765") as ws:
            await ws.recv()
            assert registry.count() >= 1

    await asyncio.sleep(0.2)
    assert registry.count() == 0


@pytest.mark.asyncio
async def test_health_returns_client_count(server):
    async with (
        connect("ws://127.0.0.1:8765") as ws1,
        connect("ws://127.0.0.1:8765") as ws2,
    ):
        await ws1.recv()
        await ws2.recv()

        data = await asyncio.to_thread(http_get, "http://127.0.0.1:8766/health")
        assert data["clients"] == 2


@pytest.mark.asyncio
async def test_health_returns_zero_with_no_clients(server):
    data = await asyncio.to_thread(http_get, "http://127.0.0.1:8766/health")
    assert data["clients"] == 0


@pytest.mark.asyncio
async def test_subscribe_to_channel(server):
    async with connect("ws://127.0.0.1:8765") as ws:
        welcome = json.loads(await ws.recv())

        await ws.send(json.dumps({
            "type": "subscribe",
            "channel": "alerts",
        }))
        resp = json.loads(await ws.recv())
        assert resp["type"] == "subscribe"
        assert resp["payload"]["channel"] == "alerts"
        assert resp["payload"]["status"] == "subscribed"
        assert resp["payload"]["client_id"] == welcome["payload"]["client_id"]


@pytest.mark.asyncio
async def test_unsubscribe_from_channel(server):
    async with connect("ws://127.0.0.1:8765") as ws:
        welcome = json.loads(await ws.recv())

        await ws.send(json.dumps({
            "type": "subscribe",
            "channel": "alerts",
        }))
        await ws.recv()

        await ws.send(json.dumps({
            "type": "unsubscribe",
            "channel": "alerts",
        }))
        resp = json.loads(await ws.recv())
        assert resp["type"] == "unsubscribe"
        assert resp["payload"]["channel"] == "alerts"
        assert resp["payload"]["status"] == "unsubscribed"


@pytest.mark.asyncio
async def test_channel_message_only_reaches_subscribers(server):
    async with (
        connect("ws://127.0.0.1:8765") as ws1,
        connect("ws://127.0.0.1:8765") as ws2,
        connect("ws://127.0.0.1:8765") as ws3,
    ):
        w1 = json.loads(await ws1.recv())
        w2 = json.loads(await ws2.recv())
        await ws3.recv()

        await ws1.send(json.dumps({
            "type": "subscribe",
            "channel": "alerts",
        }))
        await ws1.recv()

        await ws2.send(json.dumps({
            "type": "subscribe",
            "channel": "alerts",
        }))
        await ws2.recv()

        await ws1.send(json.dumps({
            "type": "alert",
            "channel": "alerts",
            "payload": {"text": "fire!"},
        }))

        msg2 = json.loads(await ws2.recv())
        assert msg2["type"] == "alert"
        assert msg2["payload"]["text"] == "fire!"

        done, _ = await asyncio.wait([asyncio.create_task(ws3.recv())], timeout=0.5)
        assert not done


@pytest.mark.asyncio
async def test_multiple_channels(server):
    async with (
        connect("ws://127.0.0.1:8765") as ws1,
        connect("ws://127.0.0.1:8765") as ws2,
    ):
        await ws1.recv()
        await ws2.recv()

        await ws1.send(json.dumps({
            "type": "subscribe",
            "channel": "alerts",
        }))
        await ws1.recv()

        await ws1.send(json.dumps({
            "type": "subscribe",
            "channel": "chat",
        }))
        await ws1.recv()

        await ws2.send(json.dumps({
            "type": "subscribe",
            "channel": "chat",
        }))
        await ws2.recv()

        await ws1.send(json.dumps({
            "type": "msg",
            "channel": "chat",
            "payload": {"text": "hello"},
        }))

        m1 = json.loads(await ws1.recv())
        assert m1["payload"]["text"] == "hello"
        m2 = json.loads(await ws2.recv())
        assert m2["payload"]["text"] == "hello"


@pytest.mark.asyncio
async def test_message_without_channel_broadcasts_to_all(server):
    async with (
        connect("ws://127.0.0.1:8765") as ws1,
        connect("ws://127.0.0.1:8765") as ws2,
    ):
        await ws1.recv()
        await ws2.recv()

        await ws1.send(json.dumps({
            "type": "subscribe",
            "channel": "alerts",
        }))
        await ws1.recv()

        await ws1.send(json.dumps({
            "type": "broadcast",
            "payload": {"text": "everyone"},
        }))

        m1 = json.loads(await ws1.recv())
        m2 = json.loads(await ws2.recv())
        assert m1["payload"]["text"] == "everyone"
        assert m2["payload"]["text"] == "everyone"


@pytest.mark.asyncio
async def test_disconnect_unsubscribes_from_all_channels(server):
    async with connect("ws://127.0.0.1:8765") as ws:
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

        data = await asyncio.to_thread(http_get, "http://127.0.0.1:8766/channels")
        assert data.get("alerts") == 1
        assert data.get("chat") == 1

    await asyncio.sleep(0.2)
    data = await asyncio.to_thread(http_get, "http://127.0.0.1:8766/channels")
    assert "alerts" not in data
    assert "chat" not in data


@pytest.mark.asyncio
async def test_channels_endpoint(server):
    async with (
        connect("ws://127.0.0.1:8765") as ws1,
        connect("ws://127.0.0.1:8765") as ws2,
    ):
        await ws1.recv()
        await ws2.recv()

        await ws1.send(json.dumps({
            "type": "subscribe",
            "channel": "alerts",
        }))
        await ws1.recv()

        await ws2.send(json.dumps({
            "type": "subscribe",
            "channel": "alerts",
        }))
        await ws2.recv()

        await ws1.send(json.dumps({
            "type": "subscribe",
            "channel": "system",
        }))
        await ws1.recv()

        data = await asyncio.to_thread(http_get, "http://127.0.0.1:8766/channels")
        assert data["alerts"] == 2
        assert data["system"] == 1


@pytest.mark.asyncio
async def test_channels_subscribers_endpoint(server):
    async with connect("ws://127.0.0.1:8765") as ws:
        welcome = json.loads(await ws.recv())
        client_id = welcome["payload"]["client_id"]

        await ws.send(json.dumps({
            "type": "subscribe",
            "channel": "alerts",
        }))
        await ws.recv()

        data = await asyncio.to_thread(http_get, "http://127.0.0.1:8766/channels/alerts/subscribers")
        assert data["channel"] == "alerts"
        assert client_id in data["subscribers"]


@pytest.mark.asyncio
async def test_channels_empty_subscribers(server):
    data = await asyncio.to_thread(http_get, "http://127.0.0.1:8766/channels/nonexistent/subscribers")
    assert data["channel"] == "nonexistent"
    assert data["subscribers"] == []


# ---------------------------------------------------------------------------
# Existing unit tests (unchanged)
# ---------------------------------------------------------------------------

class TestClientRegistry:
    def test_add_client(self):
        reg = ClientRegistry()
        cid = reg.add("fake_ws_1")
        assert isinstance(cid, str)
        assert len(cid) > 0
        assert reg.count() == 1

    def test_remove_client(self):
        reg = ClientRegistry()
        cid = reg.add("fake_ws_1")
        assert reg.count() == 1
        reg.remove(cid)
        assert reg.count() == 0

    def test_remove_nonexistent(self):
        reg = ClientRegistry()
        reg.remove("nonexistent")
        assert reg.count() == 0

    def test_count(self):
        reg = ClientRegistry()
        assert reg.count() == 0
        reg.add("a")
        reg.add("b")
        assert reg.count() == 2

    def test_get_all(self):
        reg = ClientRegistry()
        cid1 = reg.add("ws1")
        cid2 = reg.add("ws2")
        all_clients = reg.get_all()
        assert len(all_clients) == 2
        ids = {c[0] for c in all_clients}
        assert cid1 in ids
        assert cid2 in ids

    def test_thread_safety(self):
        reg = ClientRegistry()
        errors = []

        def add_and_remove():
            try:
                for _ in range(100):
                    cid = reg.add(object())
                    reg.remove(cid)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_and_remove) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert reg.count() == 0


class TestMakeMessage:
    def test_format(self):
        msg = make_message("broadcast", {"text": "hello"})
        data = json.loads(msg)
        assert data["type"] == "broadcast"
        assert data["payload"] == {"text": "hello"}
        assert "timestamp" in data

    def test_system_type(self):
        msg = make_message("system", {"info": "test"})
        data = json.loads(msg)
        assert data["type"] == "system"

    def test_direct_type(self):
        msg = make_message("direct", {"to": "abc"})
        data = json.loads(msg)
        assert data["type"] == "direct"


class TestChannelManager:
    def test_subscribe(self):
        cm = ChannelManager()
        cm.subscribe("client1", "alerts")
        assert cm.get_channels() == {"alerts": 1}

    def test_unsubscribe(self):
        cm = ChannelManager()
        cm.subscribe("client1", "alerts")
        cm.unsubscribe("client1", "alerts")
        assert cm.get_channels() == {}

    def test_unsubscribe_removes_empty_channel(self):
        cm = ChannelManager()
        cm.subscribe("client1", "alerts")
        cm.unsubscribe("client1", "alerts")
        subscribers = cm.get_subscribers("alerts")
        assert subscribers == []

    def test_multiple_subscribers(self):
        cm = ChannelManager()
        cm.subscribe("c1", "alerts")
        cm.subscribe("c2", "alerts")
        assert cm.get_channels() == {"alerts": 2}

    def test_get_subscribers(self):
        cm = ChannelManager()
        cm.subscribe("c1", "alerts")
        cm.subscribe("c2", "alerts")
        subs = cm.get_subscribers("alerts")
        assert set(subs) == {"c1", "c2"}

    def test_get_subscribers_nonexistent(self):
        cm = ChannelManager()
        assert cm.get_subscribers("nonexistent") == []

    def test_unsubscribe_all(self):
        cm = ChannelManager()
        cm.subscribe("c1", "alerts")
        cm.subscribe("c1", "chat")
        cm.subscribe("c2", "alerts")
        cm.unsubscribe_all("c1")
        assert cm.get_channels() == {"alerts": 1}

    def test_reset(self):
        cm = ChannelManager()
        cm.subscribe("c1", "alerts")
        cm.subscribe("c2", "chat")
        cm.reset()
        assert cm.get_channels() == {}

    def test_thread_safety(self):
        cm = ChannelManager()
        errors = []

        def sub_unsub():
            try:
                for i in range(100):
                    cid = f"client_{i}"
                    cm.subscribe(cid, "alerts")
                    cm.unsubscribe(cid, "alerts")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=sub_unsub) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


# ---------------------------------------------------------------------------
# New tests: MessageStore
# ---------------------------------------------------------------------------

class TestMessageStore:
    def test_store_and_retrieve(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            ms = MessageStore(db_path)
            ms.store("alerts", "alert", {"text": "hello"}, "2026-01-01T00:00:00Z")
            ms.store(None, "broadcast", {"text": "all"}, "2026-01-01T00:00:01Z")

            messages = ms.get_messages(limit=10, offset=0)
            assert len(messages) == 2
            assert messages[0]["channel"] is None
            assert messages[0]["type"] == "broadcast"
            assert messages[0]["payload"] == {"text": "all"}
            assert messages[1]["channel"] == "alerts"
            assert messages[1]["type"] == "alert"
            assert messages[1]["payload"] == {"text": "hello"}
        finally:
            os.unlink(db_path)

    def test_get_messages_default_params(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            ms = MessageStore(db_path)
            for i in range(10):
                ms.store("ch", "msg", {"idx": i}, "ts")
            messages = ms.get_messages()
            assert len(messages) == 10
        finally:
            os.unlink(db_path)

    def test_get_messages_limit_and_offset(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            ms = MessageStore(db_path)
            for i in range(5):
                ms.store("ch", "msg", {"idx": i}, "ts")

            messages = ms.get_messages(limit=2, offset=0)
            assert len(messages) == 2
            assert messages[0]["payload"]["idx"] == 4
            assert messages[1]["payload"]["idx"] == 3

            messages = ms.get_messages(limit=2, offset=2)
            assert len(messages) == 2
            assert messages[0]["payload"]["idx"] == 2
            assert messages[1]["payload"]["idx"] == 1

            messages = ms.get_messages(limit=2, offset=4)
            assert len(messages) == 1
        finally:
            os.unlink(db_path)

    def test_clear(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            ms = MessageStore(db_path)
            ms.store("ch", "msg", {"x": 1}, "ts")
            assert len(ms.get_messages()) == 1
            ms.clear()
            assert len(ms.get_messages()) == 0
        finally:
            os.unlink(db_path)

    def test_channel_none_stored_as_empty(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            ms = MessageStore(db_path)
            ms.store(None, "broadcast", {"text": "hi"}, "ts")
            messages = ms.get_messages()
            assert messages[0]["channel"] is None
        finally:
            os.unlink(db_path)

    def test_payload_is_json_parsed(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            ms = MessageStore(db_path)
            ms.store("ch", "msg", {"nested": {"key": "value"}, "list": [1, 2, 3]}, "ts")
            messages = ms.get_messages()
            assert messages[0]["payload"] == {"nested": {"key": "value"}, "list": [1, 2, 3]}
        finally:
            os.unlink(db_path)


# ---------------------------------------------------------------------------
# New tests: GET /messages endpoint (without Redis)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_messages_endpoint_empty(server):
    data = await asyncio.to_thread(http_get, "http://127.0.0.1:8766/messages")
    assert data["messages"] == []
    assert data["limit"] == 50
    assert data["offset"] == 0


@pytest.mark.asyncio
async def test_messages_endpoint_stores_sent_messages(server):
    async with (
        connect("ws://127.0.0.1:8765") as ws1,
        connect("ws://127.0.0.1:8765") as ws2,
    ):
        await ws1.recv()
        await ws2.recv()

        await ws1.send(json.dumps({
            "type": "broadcast",
            "payload": {"text": "first"},
        }))
        await ws2.recv()

        await ws1.send(json.dumps({
            "type": "alert",
            "payload": {"text": "second"},
        }))

        data = await asyncio.to_thread(http_get, "http://127.0.0.1:8766/messages")
        assert len(data["messages"]) == 2
        assert data["messages"][0]["type"] == "alert"
        assert data["messages"][1]["type"] == "broadcast"


@pytest.mark.asyncio
async def test_messages_endpoint_with_channel(server):
    async with (
        connect("ws://127.0.0.1:8765") as ws1,
        connect("ws://127.0.0.1:8765") as ws2,
    ):
        await ws1.recv()
        await ws2.recv()

        await ws1.send(json.dumps({
            "type": "subscribe",
            "channel": "alerts",
        }))
        await ws1.recv()
        await ws2.send(json.dumps({
            "type": "subscribe",
            "channel": "alerts",
        }))
        await ws2.recv()

        await ws1.send(json.dumps({
            "type": "alert",
            "channel": "alerts",
            "payload": {"text": "chan_msg"},
        }))

        data = await asyncio.to_thread(http_get, "http://127.0.0.1:8766/messages")
        assert len(data["messages"]) == 1
        assert data["messages"][0]["channel"] == "alerts"
        assert data["messages"][0]["type"] == "alert"
        assert data["messages"][0]["payload"]["text"] == "chan_msg"


@pytest.mark.asyncio
async def test_messages_endpoint_limit_and_offset(server):
    async with connect("ws://127.0.0.1:8765") as ws:
        await ws.recv()

        for i in range(5):
            await ws.send(json.dumps({
                "type": "msg",
                "payload": {"idx": i},
            }))
            await asyncio.sleep(0.05)

    data = await asyncio.to_thread(http_get, "http://127.0.0.1:8766/messages?limit=2&offset=0")
    assert len(data["messages"]) == 2
    assert data["limit"] == 2
    assert data["offset"] == 0

    data = await asyncio.to_thread(http_get, "http://127.0.0.1:8766/messages?limit=3&offset=2")
    assert len(data["messages"]) == 3
    assert data["limit"] == 3
    assert data["offset"] == 2


# ---------------------------------------------------------------------------
# New tests: Redis pub/sub integration (using fakeredis)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_redis_broadcast_message_distribution(server_with_redis):
    async with (
        connect("ws://127.0.0.1:8765") as ws1,
        connect("ws://127.0.0.1:8765") as ws2,
        connect("ws://127.0.0.1:8765") as ws3,
    ):
        for ws in (ws1, ws2, ws3):
            await ws.recv()

        await ws1.send(json.dumps({
            "type": "broadcast",
            "payload": {"text": "redis_test"},
        }))

        await asyncio.sleep(0)

        for ws in (ws2, ws3):
            msg = json.loads(await ws.recv())
            assert msg["type"] == "broadcast"
            assert msg["payload"]["text"] == "redis_test"


@pytest.mark.asyncio
async def test_redis_channel_message_routing(server_with_redis):
    async with (
        connect("ws://127.0.0.1:8765") as ws1,
        connect("ws://127.0.0.1:8765") as ws2,
        connect("ws://127.0.0.1:8765") as ws3,
    ):
        for ws in (ws1, ws2, ws3):
            await ws.recv()

        await ws1.send(json.dumps({
            "type": "subscribe",
            "channel": "alerts",
        }))
        await ws1.recv()

        await ws2.send(json.dumps({
            "type": "subscribe",
            "channel": "alerts",
        }))
        await ws2.recv()

        await ws1.send(json.dumps({
            "type": "alert",
            "channel": "alerts",
            "payload": {"text": "redis_chan"},
        }))

        await asyncio.sleep(0)

        msg = json.loads(await ws2.recv())
        assert msg["type"] == "alert"
        assert msg["payload"]["text"] == "redis_chan"

        done, _ = await asyncio.wait([asyncio.create_task(ws3.recv())], timeout=0.3)
        assert not done


@pytest.mark.asyncio
async def test_redis_message_persistence(server_with_redis):
    async with (
        connect("ws://127.0.0.1:8765") as ws1,
        connect("ws://127.0.0.1:8765") as ws2,
    ):
        await ws1.recv()
        await ws2.recv()

        await ws1.send(json.dumps({
            "type": "broadcast",
            "payload": {"persist": True},
        }))
        await asyncio.sleep(0)

        data = await asyncio.to_thread(http_get, "http://127.0.0.1:8766/messages")
        assert len(data["messages"]) == 1
        assert data["messages"][0]["type"] == "broadcast"
        assert data["messages"][0]["payload"]["persist"] is True


@pytest.mark.asyncio
async def test_redis_client_state_stored_on_connect(server_with_redis):
    fake_redis = server_with_redis
    async with connect("ws://127.0.0.1:8765") as ws:
        welcome = json.loads(await ws.recv())
        client_id = welcome["payload"]["client_id"]

        await asyncio.sleep(0.1)

        key = f"clients:{client_id}"
        data = await fake_redis.hgetall(key)
        assert len(data) > 0

        members = await fake_redis.smembers("connected_clients")
        assert client_id.encode() in members


@pytest.mark.asyncio
async def test_redis_client_state_removed_on_disconnect(server_with_redis):
    fake_redis = server_with_redis
    client_id = None
    async with connect("ws://127.0.0.1:8765") as ws:
        welcome = json.loads(await ws.recv())
        client_id = welcome["payload"]["client_id"]

    await asyncio.sleep(0.1)

    members = await fake_redis.smembers("connected_clients")
    assert client_id.encode() not in members


# ------
