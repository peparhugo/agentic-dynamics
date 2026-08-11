import asyncio
import json
import uuid

import aiohttp
import pytest
import pytest_asyncio
import websockets

from server import main, registry


WS_PORT = 18765
HTTP_PORT = 18080
HOST = "127.0.0.1"


@pytest.fixture(autouse=True)
def clear_registry():
    registry._clients.clear()
    yield
    registry._clients.clear()


@pytest_asyncio.fixture
async def server():
    task = asyncio.create_task(main(HOST, WS_PORT, HTTP_PORT))
    await asyncio.sleep(0.2)
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await asyncio.sleep(0.05)


@pytest.mark.asyncio
async def test_client_connect_and_receive_welcome(server):
    async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws:
        raw = await asyncio.wait_for(ws.recv(), timeout=5)
        msg = json.loads(raw)
        assert msg["type"] == "system"
        assert "client_id" in msg["payload"]
        assert msg["payload"]["message"] == "Connected"
        assert "timestamp" in msg
        assert isinstance(uuid.UUID(msg["payload"]["client_id"]), uuid.UUID)


@pytest.mark.asyncio
async def test_health_endpoint_returns_client_count(server):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"http://{HOST}:{HTTP_PORT}/health") as resp:
            assert resp.status == 200
            data = await resp.json()
            assert "clients" in data
            assert data["clients"] == 0

    async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://{HOST}:{HTTP_PORT}/health") as resp:
                data = await resp.json()
                assert data["clients"] == 1


@pytest.mark.asyncio
async def test_broadcast_to_all_clients(server):
    async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws1:
        await asyncio.wait_for(ws1.recv(), timeout=5)

        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws2:
            await asyncio.wait_for(ws2.recv(), timeout=5)

            await ws1.send(json.dumps({
                "type": "broadcast",
                "payload": {"text": "hello all"},
            }))

            raw = await asyncio.wait_for(ws2.recv(), timeout=5)
            msg = json.loads(raw)
            assert msg["type"] == "broadcast"
            assert msg["payload"]["text"] == "hello all"
            assert "timestamp" in msg


@pytest.mark.asyncio
async def test_broadcast_excludes_sender(server):
    broadcast_received = []

    async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws1:
        await asyncio.wait_for(ws1.recv(), timeout=5)

        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws2:
            await asyncio.wait_for(ws2.recv(), timeout=5)

            await ws1.send(json.dumps({
                "type": "broadcast",
                "payload": {"text": "only to others"},
            }))

            await ws2.recv()

            try:
                extra = await asyncio.wait_for(ws1.recv(), timeout=0.5)
                broadcast_received.append(extra)
            except asyncio.TimeoutError:
                pass

    assert len(broadcast_received) == 0


@pytest.mark.asyncio
async def test_direct_message(server):
    async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws1:
        raw1 = await asyncio.wait_for(ws1.recv(), timeout=5)
        data1 = json.loads(raw1)
        cid1 = data1["payload"]["client_id"]

        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws2:
            raw2 = await asyncio.wait_for(ws2.recv(), timeout=5)
            data2 = json.loads(raw2)
            cid2 = data2["payload"]["client_id"]

            await ws1.send(json.dumps({
                "type": "direct",
                "target": cid2,
                "payload": {"text": "secret"},
            }))

            raw = await asyncio.wait_for(ws2.recv(), timeout=5)
            msg = json.loads(raw)
            assert msg["type"] == "direct"
            assert msg["payload"]["text"] == "secret"
            assert "timestamp" in msg


@pytest.mark.asyncio
async def test_client_disconnect_notifies_others(server):
    async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws1:
        await asyncio.wait_for(ws1.recv(), timeout=5)

        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws2:
            raw2 = await asyncio.wait_for(ws2.recv(), timeout=5)
            data2 = json.loads(raw2)
            cid2 = data2["payload"]["client_id"]

            await ws2.close()

            raw = await asyncio.wait_for(ws1.recv(), timeout=5)
            msg = json.loads(raw)
            assert msg["type"] == "system"
            assert msg["payload"]["client_id"] == cid2
            assert msg["payload"]["message"] == "Disconnected"
            assert "timestamp" in msg


@pytest.mark.asyncio
async def test_health_zero_clients_after_disconnect(server):
    async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)

    await asyncio.sleep(0.1)

    async with aiohttp.ClientSession() as session:
        async with session.get(f"http://{HOST}:{HTTP_PORT}/health") as resp:
            data = await resp.json()
            assert data["clients"] == 0


@pytest.mark.asyncio
async def test_invalid_json_is_ignored(server):
    async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)
        await ws.send("not json at all")

        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://{HOST}:{HTTP_PORT}/health") as resp:
                data = await resp.json()
                assert data["clients"] == 1


@pytest.mark.asyncio
async def test_message_format_has_all_fields(server):
    async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws:
        raw = await asyncio.wait_for(ws.recv(), timeout=5)
        msg = json.loads(raw)
        assert set(msg.keys()) == {"type", "payload", "timestamp"}
        assert isinstance(msg["type"], str)
        assert isinstance(msg["payload"], dict)
        assert isinstance(msg["timestamp"], str)
