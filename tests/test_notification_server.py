import asyncio
import json

import aiohttp
import pytest
import websockets

from conftest import recv_message, wait_for_count


@pytest.mark.asyncio
async def test_connect_assigns_unique_id_and_sends_system_message(ws_url, running_server):
    async with websockets.connect(ws_url) as ws1, websockets.connect(ws_url) as ws2:
        id1 = (await recv_message(ws1))["payload"]["client_id"]
        id2 = (await recv_message(ws2))["payload"]["client_id"]
        assert id1 != id2
        assert isinstance(id1, str) and id1
        assert running_server.registry.count() == 2


@pytest.mark.asyncio
async def test_welcome_message_format(ws_url):
    async with websockets.connect(ws_url) as ws:
        message = await recv_message(ws)
        assert set(message.keys()) == {"type", "payload", "timestamp"}
        assert message["type"] == "system"
        assert isinstance(message["payload"], dict)
        assert "client_id" in message["payload"]
        assert isinstance(message["timestamp"], str) and message["timestamp"]


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients(ws_url, running_server):
    async with websockets.connect(ws_url) as ws1, websockets.connect(ws_url) as ws2, \
               websockets.connect(ws_url) as ws3:
        for ws in (ws1, ws2, ws3):
            await recv_message(ws)

        await running_server.broadcast({"greeting": "hello"})

        for ws in (ws1, ws2, ws3):
            message = await recv_message(ws)
            assert message["type"] == "broadcast"
            assert message["payload"] == {"greeting": "hello"}


@pytest.mark.asyncio
async def test_direct_message_goes_to_only_target(ws_url, running_server):
    async with websockets.connect(ws_url) as ws1, websockets.connect(ws_url) as ws2:
        id1 = (await recv_message(ws1))["payload"]["client_id"]
        await recv_message(ws2)

        sent = await running_server.send_direct(id1, {"note": "private"})
        assert sent is True

        received = await recv_message(ws1)
        assert received["type"] == "direct"
        assert received["payload"] == {"note": "private"}


@pytest.mark.asyncio
async def test_direct_to_unknown_client_returns_false(running_server):
    sent = await running_server.send_direct("does-not-exist", {"note": "x"})
    assert sent is False


@pytest.mark.asyncio
async def test_disconnect_cleanly_removes_client(ws_url, running_server):
    ws1 = await websockets.connect(ws_url)
    await recv_message(ws1)
    ws2 = await websockets.connect(ws_url)
    await recv_message(ws2)
    assert running_server.registry.count() == 2

    await ws1.close()
    await wait_for_count(running_server.registry, 1)

    await ws2.close()
    await wait_for_count(running_server.registry, 0)


@pytest.mark.asyncio
async def test_health_endpoint_reports_client_count(ws_url, http_url, running_server):
    assert running_server.registry.count() == 0
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{http_url}/health") as response:
            assert response.status == 200
            body = await response.json()
            assert body == {"clients": 0}

        async with websockets.connect(ws_url) as ws:
            await recv_message(ws)
            async with session.get(f"{http_url}/health") as response:
                assert response.status == 200
                body = await response.json()
                assert body == {"clients": 1}


@pytest.mark.asyncio
async def test_client_sent_broadcast_is_forwarded(ws_url):
    async with websockets.connect(ws_url) as ws1, websockets.connect(ws_url) as ws2:
        await recv_message(ws1)
        await recv_message(ws2)

        await ws1.send(json.dumps({"type": "broadcast", "payload": {"ping": True}}))

        for ws in (ws1, ws2):
            message = await recv_message(ws)
            assert message["type"] == "broadcast"
            assert message["payload"] == {"ping": True}


@pytest.mark.asyncio
async def test_invalid_json_is_ignored(ws_url, running_server):
    async with websockets.connect(ws_url) as ws:
        await recv_message(ws)
        await ws.send("this is not json")

        await asyncio.sleep(0.1)
        assert running_server.registry.count() == 1
        assert ws.close_code is None
