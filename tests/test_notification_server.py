import asyncio
import json
from urllib.request import urlopen

import pytest
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from app import NotificationServer


@pytest.fixture
async def notification_server():
    application = NotificationServer()
    async with serve(
        application.handler,
        "127.0.0.1",
        0,
        process_request=application.process_request,
    ) as server:
        port = server.sockets[0].getsockname()[1]
        yield application, f"ws://127.0.0.1:{port}", port


async def receive_json(websocket):
    return json.loads(await websocket.recv())


def fetch_health(port):
    with urlopen(f"http://127.0.0.1:{port}/health") as response:
        return json.loads(response.read())


async def test_clients_receive_unique_ids_and_health_count(notification_server):
    application, url, port = notification_server
    async with connect(url) as first, connect(url) as second:
        first_connected = await receive_json(first)
        second_connected = await receive_json(second)

        assert first_connected["type"] == "system"
        assert first_connected["payload"]["client_id"] != second_connected["payload"]["client_id"]

        assert await asyncio.to_thread(fetch_health, port) == {"connected_clients": 2}
        assert application.client_count == 2


async def test_broadcast_reaches_all_clients(notification_server):
    _, url, _ = notification_server
    async with connect(url) as sender, connect(url) as recipient:
        await receive_json(sender)
        await receive_json(recipient)

        await sender.send(json.dumps({"type": "broadcast", "payload": {"text": "hello"}}))
        delivered = await asyncio.gather(receive_json(sender), receive_json(recipient))

        assert all(message["type"] == "broadcast" for message in delivered)
        assert all(message["payload"] == {"text": "hello"} for message in delivered)
        assert all(message["timestamp"] for message in delivered)


async def test_direct_message_and_disconnect_removal(notification_server):
    application, url, _ = notification_server
    async with connect(url) as sender, connect(url) as recipient:
        await receive_json(sender)
        recipient_connected = await receive_json(recipient)
        recipient_id = recipient_connected["payload"]["client_id"]

        await sender.send(json.dumps({"type": "direct", "payload": {"client_id": recipient_id, "text": "private"}}))
        assert (await receive_json(recipient))["payload"]["text"] == "private"

    for _ in range(20):
        if application.client_count == 0:
            break
        await asyncio.sleep(0.01)
    assert application.client_count == 0
