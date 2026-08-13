import asyncio
import json

import pytest
from websockets.asyncio.client import connect

from app import NotificationServer


@pytest.fixture
async def server():
    application = NotificationServer()
    async with application.create_server(port=0) as running_server:
        port = running_server.sockets[0].getsockname()[1]
        yield application, f"ws://127.0.0.1:{port}"


async def receive_json(connection):
    return json.loads(await connection.recv())


async def test_connection_receives_address_derived_client_id(server):
    _, url = server
    async with connect(url) as client:
        welcome = await receive_json(client)
        host, port = client.local_address[:2]

    assert welcome["type"] == "system"
    assert welcome["payload"]["client_id"] == f"{host}:{port}"


async def test_broadcast_reaches_all_connected_clients(server):
    _, url = server
    async with connect(url) as first, connect(url) as second:
        await receive_json(first)
        await receive_json(second)
        await first.send(json.dumps({"type": "broadcast", "payload": {"text": "hello"}}))

        first_message, second_message = await receive_json(first), await receive_json(second)

    assert first_message["type"] == "broadcast"
    assert first_message["payload"] == {"text": "hello"}
    assert second_message["payload"] == {"text": "hello"}
    assert "timestamp" in first_message


async def test_disconnect_removes_client_from_health_count(server):
    application, url = server
    async with connect(url) as client:
        await receive_json(client)
        assert len(application.clients) == 1

    for _ in range(10):
        if len(application.clients) == 0:
            break
        await asyncio.sleep(0.01)

    assert len(application.clients) == 0


async def test_health_endpoint_returns_connected_client_count(server):
    _, url = server
    host_and_port = url.removeprefix("ws://")
    host, port = host_and_port.rsplit(":", 1)
    async with connect(url) as client:
        await receive_json(client)
        reader, writer = await asyncio.open_connection(host, int(port))
        writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
        await writer.drain()
        response = await reader.read()
        writer.close()
        await writer.wait_closed()

    status_line, body = response.split(b"\r\n\r\n", 1)
    assert b"200 OK" in status_line
    assert json.loads(body) == {"connected_clients": 1}
