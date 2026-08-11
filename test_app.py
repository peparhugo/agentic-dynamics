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
