import asyncio
import json

import pytest
import pytest_asyncio
from websockets.asyncio.client import connect

from notification_server import NotificationServer


@pytest_asyncio.fixture
async def server(unused_tcp_port):
    instance = NotificationServer("127.0.0.1", unused_tcp_port)
    await instance.start()
    yield instance
    await instance.stop()


async def receive_json(client):
    return json.loads(await asyncio.wait_for(client.recv(), timeout=1))


async def health_response(port):
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    return response


@pytest.mark.asyncio
async def test_assigns_unique_ids_and_health_count(server):
    uri = f"ws://127.0.0.1:{server.port}"
    first = await connect(uri)
    second = await connect(uri)
    try:
        first_message = await receive_json(first)
        second_message = await receive_json(second)
        assert first_message["type"] == second_message["type"] == "system"
        assert first_message["payload"]["client_id"] != second_message["payload"]["client_id"]
        assert server.connected_client_count == 2
    finally:
        await first.close()
        await second.close()


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients(server):
    uri = f"ws://127.0.0.1:{server.port}"
    clients = [await connect(uri), await connect(uri)]
    try:
        for client in clients:
            await receive_json(client)
        await clients[0].send(json.dumps({"type": "broadcast", "payload": {"text": "hello"}}))
        messages = [await receive_json(client) for client in clients]
        assert all(message["payload"] == {"text": "hello"} for message in messages)
        assert all("timestamp" in message for message in messages)
    finally:
        await asyncio.gather(*(client.close() for client in clients))


@pytest.mark.asyncio
async def test_direct_message_only_reaches_target(server):
    uri = f"ws://127.0.0.1:{server.port}"
    sender, target = await connect(uri), await connect(uri)
    try:
        await receive_json(sender)
        target_id = (await receive_json(target))["payload"]["client_id"]
        await sender.send(json.dumps({
            "type": "direct",
            "payload": {"client_id": target_id, "text": "private"},
        }))
        message = await receive_json(target)
        assert message["type"] == "direct"
        assert message["payload"]["text"] == "private"
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(sender.recv(), timeout=0.1)
    finally:
        await sender.close()
        await target.close()


@pytest.mark.asyncio
async def test_disconnect_removes_client_and_health_endpoint(server):
    response = await health_response(server.port)
    assert b"200 OK" in response
    assert json.loads(response.split(b"\r\n\r\n", 1)[1]) == {"connected_clients": 0}

    uri = f"ws://127.0.0.1:{server.port}"
    client = await connect(uri)
    await receive_json(client)
    assert server.connected_client_count == 1
    await client.close()
    for _ in range(20):
        if server.connected_client_count == 0:
            break
        await asyncio.sleep(0.01)
    assert server.connected_client_count == 0
    response = await health_response(server.port)
    assert json.loads(response.split(b"\r\n\r\n", 1)[1]) == {"connected_clients": 0}
