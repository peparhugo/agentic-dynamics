import asyncio
import json
import urllib.request

import pytest
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from app import NotificationServer


@pytest.fixture
async def running_server(unused_tcp_port):
    notification_server = NotificationServer()
    async with serve(
        notification_server.handler,
        "127.0.0.1",
        unused_tcp_port,
        process_request=notification_server.process_request,
    ):
        yield notification_server, unused_tcp_port


async def receive_json(websocket):
    return json.loads(await asyncio.wait_for(websocket.recv(), timeout=1))


def valid_message(message_type, payload):
    return {"type": message_type, "payload": payload, "timestamp": "2026-01-01T00:00:00Z"}


@pytest.mark.asyncio
async def test_assigns_unique_client_ids(running_server):
    _, port = running_server
    async with connect(f"ws://127.0.0.1:{port}") as first, connect(
        f"ws://127.0.0.1:{port}"
    ) as second:
        first_message = await receive_json(first)
        second_message = await receive_json(second)

        assert first_message["type"] == "system"
        assert first_message["payload"]["event"] == "connected"
        assert first_message["payload"]["client_id"] != second_message["payload"]["client_id"]
        assert isinstance(first_message["timestamp"], str)


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients_including_sender(running_server):
    _, port = running_server
    async with connect(f"ws://127.0.0.1:{port}") as first, connect(
        f"ws://127.0.0.1:{port}"
    ) as second:
        await receive_json(first)
        await receive_json(second)
        outgoing = valid_message("broadcast", {"text": "hello"})
        await first.send(json.dumps(outgoing))

        assert await receive_json(first) == outgoing
        assert await receive_json(second) == outgoing


@pytest.mark.asyncio
async def test_direct_message_only_reaches_target(running_server):
    _, port = running_server
    async with connect(f"ws://127.0.0.1:{port}") as first, connect(
        f"ws://127.0.0.1:{port}"
    ) as second:
        await receive_json(first)
        second_id = (await receive_json(second))["payload"]["client_id"]
        outgoing = valid_message("direct", {"client_id": second_id, "text": "private"})
        await first.send(json.dumps(outgoing))

        assert await receive_json(second) == outgoing
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(first.recv(), timeout=0.05)


@pytest.mark.asyncio
async def test_disconnect_removes_client(running_server):
    notification_server, port = running_server
    websocket = await connect(f"ws://127.0.0.1:{port}")
    await receive_json(websocket)
    assert len(notification_server.clients) == 1

    await websocket.close()
    for _ in range(20):
        if len(notification_server.clients) == 0:
            break
        await asyncio.sleep(0.01)
    assert len(notification_server.clients) == 0


@pytest.mark.asyncio
async def test_health_reports_connected_clients(running_server):
    _, port = running_server
    async with connect(f"ws://127.0.0.1:{port}") as websocket:
        await receive_json(websocket)

        def fetch_health():
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health") as response:
                return response.status, json.load(response)

        status, body = await asyncio.to_thread(fetch_health)
        assert status == 200
        assert body == {"connected_clients": 1}


@pytest.mark.asyncio
async def test_invalid_messages_return_system_error(running_server):
    _, port = running_server
    async with connect(f"ws://127.0.0.1:{port}") as websocket:
        await receive_json(websocket)
        await websocket.send("not-json")
        response = await receive_json(websocket)

        assert response["type"] == "system"
        assert response["payload"] == {"error": "invalid JSON"}
        assert isinstance(response["timestamp"], str)
