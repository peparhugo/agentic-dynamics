import asyncio
import json
import urllib.request

import pytest
from websockets.asyncio.client import connect

from app import NotificationServer


@pytest.fixture
async def server():
    instance = NotificationServer(port=0)
    await instance.start()
    try:
        yield instance
    finally:
        await instance.stop()


async def receive_json(websocket):
    return json.loads(await asyncio.wait_for(websocket.recv(), timeout=1))


async def connect_client(server):
    websocket = await connect(f"ws://127.0.0.1:{server.port}")
    greeting = await receive_json(websocket)
    return websocket, greeting


@pytest.mark.asyncio
async def test_connection_assigns_unique_ids_and_disconnects_cleanly(server):
    first, first_greeting = await connect_client(server)
    second, second_greeting = await connect_client(server)

    assert first_greeting["type"] == "system"
    assert first_greeting["payload"]["event"] == "connected"
    assert first_greeting["payload"]["client_id"] != second_greeting["payload"]["client_id"]
    assert first_greeting["timestamp"].endswith("Z")
    assert server.clients.count == 2

    await first.close()
    await second.close()
    for _ in range(20):
        if server.clients.count == 0:
            break
        await asyncio.sleep(0.01)
    assert server.clients.count == 0


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients(server):
    first, _ = await connect_client(server)
    second, _ = await connect_client(server)
    request = {"type": "broadcast", "payload": {"text": "hello"}, "timestamp": "ignored"}

    await first.send(json.dumps(request))
    first_message, second_message = await asyncio.gather(receive_json(first), receive_json(second))

    assert first_message["type"] == second_message["type"] == "broadcast"
    assert first_message["payload"] == second_message["payload"] == {"text": "hello"}
    assert first_message["timestamp"]
    await first.close()
    await second.close()


@pytest.mark.asyncio
async def test_direct_reaches_only_target(server):
    sender, _ = await connect_client(server)
    target, target_greeting = await connect_client(server)
    payload = {"target_id": target_greeting["payload"]["client_id"], "text": "private"}

    await sender.send(json.dumps({"type": "direct", "payload": payload, "timestamp": "ignored"}))

    received = await receive_json(target)
    assert received["type"] == "direct"
    assert received["payload"] == payload
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(sender.recv(), timeout=0.05)
    await sender.close()
    await target.close()


@pytest.mark.asyncio
async def test_invalid_messages_return_system_error(server):
    client, _ = await connect_client(server)
    await client.send("not json")
    response = await receive_json(client)
    assert response["type"] == "system"
    assert response["payload"] == {"error": "invalid JSON"}
    await client.close()


@pytest.mark.asyncio
async def test_health_reports_connected_client_count(server):
    client, _ = await connect_client(server)

    def fetch_health():
        with urllib.request.urlopen(f"http://127.0.0.1:{server.port}/health") as response:
            return response.status, json.load(response)

    status, body = await asyncio.to_thread(fetch_health)
    assert status == 200
    assert body == {"connected_clients": 1}
    await client.close()
