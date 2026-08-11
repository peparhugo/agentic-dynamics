import asyncio
import json
import time

import pytest
import websockets
from aiohttp import ClientSession

from server import start_server, _registry

HOST = "127.0.0.1"
WS_PORT = 18765
HTTP_PORT = 18080


@pytest.fixture(autouse=True)
def reset_registry():
    _registry.clear()
    yield
    _registry.clear()


@pytest.fixture(scope="module")
def server():
    t1, t2 = start_server(HOST, WS_PORT, HTTP_PORT)
    time.sleep(0.3)
    yield
    # Daemon threads, nothing to explicitly stop


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_returns_zero_when_no_clients(self, server):
        async with ClientSession() as session:
            async with session.get(f"http://{HOST}:{HTTP_PORT}/health") as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data["clients"] == 0

    @pytest.mark.asyncio
    async def test_health_reflects_connected_clients(self, server):
        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws1:
            await ws1.recv()
            async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws2:
                await ws2.recv()
                await asyncio.sleep(0.1)
                async with ClientSession() as session:
                    async with session.get(f"http://{HOST}:{HTTP_PORT}/health") as resp:
                        data = await resp.json()
                        assert data["clients"] == 2


class TestClientConnection:
    @pytest.mark.asyncio
    async def test_connect_receives_welcome_message(self, server):
        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws:
            raw = await ws.recv()
            data = json.loads(raw)
            assert data["type"] == "system"
            assert "client_id" in data["payload"]
            assert data["payload"]["message"] == "Connected"
            assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_connect_assigns_unique_ids(self, server):
        ids = set()
        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws1:
            d1 = json.loads(await ws1.recv())
            ids.add(d1["payload"]["client_id"])
            async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws2:
                d2 = json.loads(await ws2.recv())
                ids.add(d2["payload"]["client_id"])
        assert len(ids) == 2

    @pytest.mark.asyncio
    async def test_disconnect_removes_client(self, server):
        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws:
            await ws.recv()
            assert _registry.count() == 1
        await asyncio.sleep(0.2)
        assert _registry.count() == 0


class TestBroadcast:
    @pytest.mark.asyncio
    async def test_broadcast_delivers_to_all(self, server):
        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws1, \
                   websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws2:
            await ws1.recv()
            await ws2.recv()

            await ws1.send(json.dumps({
                "type": "broadcast",
                "payload": {"text": "hello all"}
            }))

            msg2_raw = await asyncio.wait_for(ws2.recv(), timeout=2)
            msg2 = json.loads(msg2_raw)
            assert msg2["type"] == "broadcast"
            assert msg2["payload"]["text"] == "hello all"

    @pytest.mark.asyncio
    async def test_broadcast_sender_does_not_receive_own_message(self, server):
        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws1, \
                   websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws2:
            d1 = json.loads(await ws1.recv())
            sender_id = d1["payload"]["client_id"]
            await ws2.recv()

            await ws1.send(json.dumps({
                "type": "broadcast",
                "payload": {"text": "hello"}
            }))

            msg = json.loads(await asyncio.wait_for(ws2.recv(), timeout=2))
            assert msg["from"] == sender_id


class TestDirectMessage:
    @pytest.mark.asyncio
    async def test_direct_message_delivers_to_target(self, server):
        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws1, \
                   websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws2, \
                   websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws3:
            d1 = json.loads(await ws1.recv())
            d2 = json.loads(await ws2.recv())
            d3 = json.loads(await ws3.recv())

            target_id = d2["payload"]["client_id"]

            await ws1.send(json.dumps({
                "type": "direct",
                "payload": {"target": target_id, "text": "secret"}
            }))

            msg = json.loads(await asyncio.wait_for(ws2.recv(), timeout=2))
            assert msg["type"] == "direct"
            assert msg["payload"]["text"] == "secret"
            assert msg["from"] == d1["payload"]["client_id"]

            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(ws3.recv(), timeout=0.5)


class TestDisconnectNotification:
    @pytest.mark.asyncio
    async def test_disconnect_notifies_remaining_clients(self, server):
        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws1:
            d1 = json.loads(await ws1.recv())
            async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws2:
                d2 = json.loads(await ws2.recv())
                # Close ws2
                await ws2.close()
                await asyncio.sleep(0.2)
                # ws1 should receive disconnect notification for ws2's client_id
                notify = json.loads(await asyncio.wait_for(ws1.recv(), timeout=3))
                assert notify["type"] == "system"
                assert notify["payload"]["message"] == "Disconnected"
                assert notify["payload"]["client_id"] == d2["payload"]["client_id"]


class TestMessageFormat:
    @pytest.mark.asyncio
    async def test_message_has_required_fields(self, server):
        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws1, \
                   websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws2:
            await ws1.recv()
            await ws2.recv()

            await ws1.send(json.dumps({
                "type": "broadcast",
                "payload": {"text": "check format"}
            }))

            msg = json.loads(await asyncio.wait_for(ws2.recv(), timeout=2))
            assert "type" in msg
            assert "payload" in msg
            assert "timestamp" in msg
            assert msg["type"] == "broadcast"

    @pytest.mark.asyncio
    async def test_invalid_json_is_gracefully_ignored(self, server):
        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws1, \
                   websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws2:
            await ws1.recv()
            await ws2.recv()

            await ws1.send("not json")

            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(ws2.recv(), timeout=0.5)


class TestThreadSafety:
    @pytest.mark.asyncio
    async def test_concurrent_connections(self, server):
        async def connect_and_send():
            async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws:
                await ws.recv()
                await ws.send(json.dumps({
                    "type": "broadcast",
                    "payload": {"text": "concurrent"}
                }))

        tasks = [asyncio.create_task(connect_and_send()) for _ in range(10)]
        await asyncio.gather(*tasks)
        await asyncio.sleep(0.2)
        assert _registry.count() == 0


class TestSystemMessage:
    @pytest.mark.asyncio
    async def test_system_message_on_connect(self, server):
        async with websockets.connect(f"ws://{HOST}:{WS_PORT}") as ws:
            msg = json.loads(await ws.recv())
            assert msg["type"] == "system"
            assert msg["payload"]["message"] == "Connected"
