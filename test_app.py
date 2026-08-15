import asyncio
import json
import urllib.request

import pytest
from websockets.asyncio.client import connect

from app import NotificationServer


@pytest.fixture
async def server():
    async with NotificationServer(port=0) as running_server:
        yield running_server


def websocket_url(server):
    return f"ws://127.0.0.1:{server.bound_port}"


async def receive_json(connection):
    return json.loads(await asyncio.wait_for(connection.recv(), timeout=1))


@pytest.mark.asyncio
async def test_connection_gets_unique_id_and_disconnect_is_removed(server):
    async with connect(websocket_url(server)) as first, connect(
        websocket_url(server)
    ) as second:
        first_welcome, second_welcome = await asyncio.gather(
            receive_json(first), receive_json(second)
        )
        assert first_welcome["type"] == "system"
        assert first_welcome["payload"]["event"] == "connected"
        assert first_welcome["payload"]["client_id"] != second_welcome["payload"][
            "client_id"
        ]
        assert server.connected_count == 2

    await asyncio.sleep(0)
    assert server.connected_count == 0


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients_including_sender(server):
    async with connect(websocket_url(server)) as first, connect(
        websocket_url(server)
    ) as second:
        await asyncio.gather(receive_json(first), receive_json(second))
        notification = {
            "type": "broadcast",
            "payload": {"text": "deployment complete"},
            "timestamp": "2026-08-16T12:00:00Z",
        }
        await first.send(json.dumps(notification))

        assert await receive_json(first) == notification
        assert await receive_json(second) == notification


@pytest.mark.asyncio
async def test_direct_message_only_reaches_target(server):
    async with connect(websocket_url(server)) as sender, connect(
        websocket_url(server)
    ) as recipient:
        sender_welcome, recipient_welcome = await asyncio.gather(
            receive_json(sender), receive_json(recipient)
        )
        notification = {
            "type": "direct",
            "payload": {
                "client_id": recipient_welcome["payload"]["client_id"],
                "text": "private",
            },
            "timestamp": "2026-08-16T12:00:00Z",
        }
        await sender.send(json.dumps(notification))

        assert await receive_json(recipient) == notification
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(sender.recv(), timeout=0.05)
        assert sender_welcome["payload"]["client_id"] != recipient_welcome["payload"][
            "client_id"
        ]


@pytest.mark.asyncio
async def test_invalid_message_returns_formatted_system_error(server):
    async with connect(websocket_url(server)) as connection:
        await receive_json(connection)
        await connection.send("not json")
        error = await receive_json(connection)

        assert set(error) == {"type", "payload", "timestamp"}
        assert error["type"] == "system"
        assert error["payload"] == {"error": "message must be valid JSON"}


@pytest.mark.asyncio
async def test_health_returns_connected_client_count(server):
    async with connect(websocket_url(server)) as connection:
        await receive_json(connection)

        def request_health():
            with urllib.request.urlopen(
                f"http://127.0.0.1:{server.bound_port}/health", timeout=1
            ) as response:
                return response.status, json.load(response)

        status, body = await asyncio.to_thread(request_health)
        assert status == 200
        assert body == {"connected_clients": 1}
