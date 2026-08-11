import asyncio
import json

import httpx
import pytest
import pytest_asyncio
import websockets

from app import handler, process_request, registry
from websockets.asyncio.server import serve


def _free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest_asyncio.fixture
async def server_url():
    port = _free_port()
    async with serve(handler, "127.0.0.1", port, process_request=process_request) as srv:
        yield f"ws://127.0.0.1:{port}"
    registry._clients.clear()


async def _recv_json(ws):
    raw = await ws.recv()
    return json.loads(raw)


class TestConnection:
    @pytest.mark.asyncio
    async def test_connect_receives_welcome(self, server_url):
        async with websockets.connect(server_url) as ws:
            msg = await _recv_json(ws)
            assert msg["type"] == "system"
            assert msg["payload"]["message"] == "connected"
            assert "client_id" in msg["payload"]

    @pytest.mark.asyncio
    async def test_unique_client_ids(self, server_url):
        async with websockets.connect(server_url) as ws1, websockets.connect(
            server_url
        ) as ws2:
            m1 = await _recv_json(ws1)
            m2 = await _recv_json(ws2)
            assert m1["payload"]["client_id"] != m2["payload"]["client_id"]

    @pytest.mark.asyncio
    async def test_disconnect_cleanup(self, server_url):
        async with websockets.connect(server_url) as ws:
            await _recv_json(ws)
        await asyncio.sleep(0.1)

    @pytest.mark.asyncio
    async def test_disconnect_notifies_others(self, server_url):
        async with websockets.connect(server_url) as ws1:
            w1 = await _recv_json(ws1)
            cid1 = w1["payload"]["client_id"]

            async with websockets.connect(server_url) as ws2:
                await _recv_json(ws2)

            disconnect_msg = await _recv_json(ws1)
            assert disconnect_msg["type"] == "system"
            assert disconnect_msg["payload"]["message"] == "disconnected"
            assert "client_id" in disconnect_msg["payload"]
            assert disconnect_msg["payload"]["client_id"] != cid1


class TestBroadcast:
    @pytest.mark.asyncio
    async def test_broadcast_to_all(self, server_url):
        async with websockets.connect(server_url) as ws1, websockets.connect(
            server_url
        ) as ws2:
            await _recv_json(ws1)
            await _recv_json(ws2)

            payload = {"text": "hello everyone"}
            await ws1.send(
                json.dumps({"type": "broadcast", "payload": payload})
            )

            msg_on_ws2 = await _recv_json(ws2)
            assert msg_on_ws2["type"] == "broadcast"
            assert msg_on_ws2["payload"]["text"] == "hello everyone"

    @pytest.mark.asyncio
    async def test_broadcast_includes_from(self, server_url):
        async with websockets.connect(server_url) as ws1, websockets.connect(
            server_url
        ) as ws2:
            w1 = await _recv_json(ws1)
            cid1 = w1["payload"]["client_id"]
            await _recv_json(ws2)

            await ws1.send(
                json.dumps({"type": "broadcast", "payload": {"x": 1}})
            )

            msg = await _recv_json(ws2)
            assert msg["payload"]["from"] == cid1


class TestDirect:
    @pytest.mark.asyncio
    async def test_direct_message(self, server_url):
        async with websockets.connect(server_url) as ws1, websockets.connect(
            server_url
        ) as ws2:
            w1 = await _recv_json(ws1)
            w2 = await _recv_json(ws2)
            cid1 = w1["payload"]["client_id"]
            cid2 = w2["payload"]["client_id"]

            await ws1.send(
                json.dumps(
                    {
                        "type": "direct",
                        "payload": {"target": cid2, "message": "secret"},
                    }
                )
            )

            msg = await _recv_json(ws2)
            assert msg["type"] == "direct"
            assert msg["payload"]["from"] == cid1
            assert msg["payload"]["message"] == "secret"

    @pytest.mark.asyncio
    async def test_direct_nonexistent_silent(self, server_url):
        async with websockets.connect(server_url) as ws:
            await _recv_json(ws)
            await ws.send(
                json.dumps(
                    {
                        "type": "direct",
                        "payload": {"target": "no-such-id", "message": "hi"},
                    }
                )
            )
            await asyncio.sleep(0.05)


class TestHealth:
    @pytest.mark.asyncio
    async def test_health_returns_count(self, server_url):
        http_url = server_url.replace("ws://", "http://")
        async with websockets.connect(server_url) as ws:
            await _recv_json(ws)
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{http_url}/health")
                assert resp.status_code == 200
                data = resp.json()
                assert data["connected_clients"] == 1

    @pytest.mark.asyncio
    async def test_health_zero(self, server_url):
        http_url = server_url.replace("ws://", "http://")
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{http_url}/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["connected_clients"] == 0


class TestSystem:
    @pytest.mark.asyncio
    async def test_invalid_json_ignored(self, server_url):
        async with websockets.connect(server_url) as ws:
            await _recv_json(ws)
            await ws.send("not json!!!")
            await asyncio.sleep(0.05)

    @pytest.mark.asyncio
    async def test_message_has_timestamp(self, server_url):
        async with websockets.connect(server_url) as ws1, websockets.connect(
            server_url
        ) as ws2:
            await _recv_json(ws1)
            await _recv_json(ws2)
            await ws1.send(
                json.dumps({"type": "broadcast", "payload": {"text": "ts"}})
            )
            msg = await _recv_json(ws2)
            assert "timestamp" in msg
            assert isinstance(msg["timestamp"], str)
