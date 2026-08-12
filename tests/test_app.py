import asyncio
import json
from urllib.request import urlopen

import pytest
import pytest_asyncio
from websockets.asyncio.client import connect

from app import NotificationServer


async def receive_json(websocket):
    return json.loads(await websocket.recv())


@pytest_asyncio.fixture
async def server():
    instance = NotificationServer(port=0)
    await instance.start()
    yield instance
    await instance.stop()


@pytest.mark.asyncio
async def test_connections_get_unique_ids_and_health_count(server):
    uri = f"ws://127.0.0.1:{server.bound_port}"
    async with connect(uri) as first, connect(uri) as second:
        first_message = await receive_json(first)
        second_message = await receive_json(second)
        first_id = first_message["payload"]["client_id"]
        second_id = second_message["payload"]["client_id"]
        assert first_id != second_id
        assert first_message["type"] == second_message["type"] == "system"
        assert first_message["timestamp"]
        response = await asyncio.to_thread(
            urlopen, f"http://127.0.0.1:{server.bound_port}/health"
        )
        assert json.loads(response.read()) == {"connected_clients": 2}


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients(server):
    uri = f"ws://127.0.0.1:{server.bound_port}"
    async with connect(uri) as first, connect(uri) as second:
        await first.recv()
        await second.recv()
        await first.send(json.dumps({"type": "broadcast", "payload": {"text": "hello"}}))
        messages = await asyncio.gather(receive_json(first), receive_json(second))
        assert all(message["type"] == "broadcast" for message in messages)
        assert all(message["payload"] == {"text": "hello"} for message in messages)
        assert all(message["timestamp"] for message in messages)


@pytest.mark.asyncio
async def test_direct_message_only_reaches_target(server):
    uri = f"ws://127.0.0.1:{server.bound_port}"
    async with connect(uri) as sender, connect(uri) as target:
        await sender.recv()
        target_id = (await receive_json(target))["payload"]["client_id"]
        await sender.send(
            json.dumps(
                {"type": "direct", "payload": {"client_id": target_id, "text": "private"}}
            )
        )
        message = await receive_json(target)
        assert message["type"] == "direct"
        assert message["payload"]["text"] == "private"
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(sender.recv(), timeout=0.05)


@pytest.mark.asyncio
async def test_disconnect_removes_client(server):
    uri = f"ws://127.0.0.1:{server.bound_port}"
    connection = await connect(uri)
    await connection.recv()
    assert await server.client_count() == 1
    await connection.close()
    for _ in range(20):
        if await server.client_count() == 0:
            break
        await asyncio.sleep(0.01)
    assert await server.client_count() == 0


@pytest.mark.asyncio
async def test_invalid_message_returns_system_error(server):
    uri = f"ws://127.0.0.1:{server.bound_port}"
    async with connect(uri) as connection:
        await connection.recv()
        await connection.send("not json")
        message = await receive_json(connection)
        assert message["type"] == "system"
        assert "error" in message["payload"]
