import asyncio
import json
from http import HTTPStatus

import pytest
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from app import NotificationServer


@pytest.fixture
async def notification_server():
    application = NotificationServer()
    async with serve(
        application.handle_connection,
        "127.0.0.1",
        0,
        process_request=application.health_response,
    ) as server:
        port = server.sockets[0].getsockname()[1]
        yield application, f"ws://127.0.0.1:{port}"


async def test_connect_assigns_websocket_id_and_health_counts_client(notification_server):
    application, url = notification_server
    async with connect(url) as client:
        welcome = json.loads(await client.recv())
        client_id = welcome["payload"]["client_id"]

        assert welcome["type"] == "system"
        assert client_id in application.clients
        assert application.connected_client_count == 1

        response = await asyncio.to_thread(http_get, url, "/health")
        assert response == {"connected_clients": 1}


async def test_broadcast_reaches_every_connected_client(notification_server):
    _, url = notification_server
    message = {"type": "broadcast", "payload": {"text": "hello"}, "timestamp": "2026-08-13T00:00:00Z"}
    async with connect(url) as first, connect(url) as second:
        await first.recv()
        await second.recv()
        await first.send(json.dumps(message))

        assert json.loads(await first.recv()) == message
        assert json.loads(await second.recv()) == message


async def test_direct_message_reaches_only_target_client(notification_server):
    _, url = notification_server
    async with connect(url) as sender, connect(url) as target:
        await sender.recv()
        target_welcome = json.loads(await target.recv())
        message = {
            "type": "direct",
            "payload": {"client_id": target_welcome["payload"]["client_id"], "text": "private"},
            "timestamp": "2026-08-13T00:00:00Z",
        }
        await sender.send(json.dumps(message))

        assert json.loads(await target.recv()) == message
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(sender.recv(), timeout=0.05)


async def test_disconnect_removes_client(notification_server):
    application, url = notification_server
    async with connect(url) as client:
        await client.recv()
        assert application.connected_client_count == 1

    for _ in range(20):
        if application.connected_client_count == 0:
            break
        await asyncio.sleep(0.01)
    assert application.connected_client_count == 0


def http_get(websocket_url: str, path: str) -> dict[str, int]:
    import http.client

    host_port = websocket_url.removeprefix("ws://")
    connection = http.client.HTTPConnection(host_port)
    connection.request("GET", path)
    response = connection.getresponse()
    assert response.status == HTTPStatus.OK
    return json.loads(response.read())
