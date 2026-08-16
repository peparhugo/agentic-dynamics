import asyncio
import json
import urllib.request
from datetime import datetime

import pytest
import pytest_asyncio
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from app import NotificationServer


@pytest_asyncio.fixture
async def running_server():
    notifications = NotificationServer()
    async with serve(
        notifications.handler,
        "127.0.0.1",
        0,
        process_request=notifications.process_request,
    ) as websocket_server:
        port = websocket_server.sockets[0].getsockname()[1]
        yield notifications, port


async def receive_json(websocket):
    return json.loads(await asyncio.wait_for(websocket.recv(), timeout=1))


def assert_message_format(message):
    assert set(message) == {"type", "payload", "timestamp"}
    assert isinstance(message["type"], str)
    assert isinstance(message["payload"], dict)
    datetime.fromisoformat(message["timestamp"].replace("Z", "+00:00"))


@pytest.mark.asyncio
async def test_connect_assigns_unique_ids_and_disconnects(running_server):
    notifications, port = running_server
    async with connect(f"ws://127.0.0.1:{port}") as first, connect(
        f"ws://127.0.0.1:{port}"
    ) as second:
        first_message, second_message = await asyncio.gather(
            receive_json(first), receive_json(second)
        )
        assert first_message["payload"]["client_id"] != second_message["payload"][
            "client_id"
        ]
        assert len(notifications.registry) == 2
    await asyncio.sleep(0)
    assert len(notifications.registry) == 0


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients(running_server):
    _, port = running_server
    async with connect(f"ws://127.0.0.1:{port}") as first, connect(
        f"ws://127.0.0.1:{port}"
    ) as second:
        await asyncio.gather(receive_json(first), receive_json(second))
        outgoing = {
            "type": "broadcast",
            "payload": {"text": "hello"},
            "timestamp": "2026-08-16T00:00:00Z",
        }
        await first.send(json.dumps(outgoing))
        assert await receive_json(first) == outgoing
        assert await receive_json(second) == outgoing


@pytest.mark.asyncio
async def test_direct_reaches_only_target(running_server):
    _, port = running_server
    async with connect(f"ws://127.0.0.1:{port}") as first, connect(
        f"ws://127.0.0.1:{port}"
    ) as second:
        _, second_welcome = await asyncio.gather(
            receive_json(first), receive_json(second)
        )
        outgoing = {
            "type": "direct",
            "payload": {
                "client_id": second_welcome["payload"]["client_id"],
                "text": "private",
            },
            "timestamp": "2026-08-16T00:00:00Z",
        }
        await first.send(json.dumps(outgoing))
        assert await receive_json(second) == outgoing
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(first.recv(), timeout=0.05)


@pytest.mark.asyncio
async def test_invalid_message_returns_formatted_system_error(running_server):
    _, port = running_server
    async with connect(f"ws://127.0.0.1:{port}") as websocket:
        await receive_json(websocket)
        await websocket.send("not json")
        error = await receive_json(websocket)
        assert_message_format(error)
        assert error["type"] == "system"
        assert error["payload"]["event"] == "error"


@pytest.mark.asyncio
async def test_health_reports_connected_clients(running_server):
    _, port = running_server
    async with connect(f"ws://127.0.0.1:{port}") as websocket:
        await receive_json(websocket)

        def get_health():
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health") as response:
                return response.status, response.headers, json.load(response)

        status, headers, body = await asyncio.to_thread(get_health)
        assert status == 200
        assert headers.get_content_type() == "application/json"
        assert body == {"connected_clients": 1}
