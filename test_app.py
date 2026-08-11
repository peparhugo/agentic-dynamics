import asyncio
import json
import socket

import pytest
import pytest_asyncio
import websockets
import aiohttp

from app import registry, main


def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest_asyncio.fixture
async def server():
    port = get_free_port()
    host = "127.0.0.1"
    server_task = asyncio.ensure_future(main(host=host, port=port))
    await asyncio.sleep(0.1)
    yield {"host": host, "port": port, "ws_url": f"ws://{host}:{port}"}
    server_task.cancel()
    try:
        await server_task
    except asyncio.CancelledError:
        pass


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

    with registry._lock:
        assert client_id not in registry._clients


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

    channels = registry.get_channels()
    assert channels.get("alerts", 0) == 0
