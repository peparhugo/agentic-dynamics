import asyncio
import json
import tempfile
from urllib.request import urlopen

import pytest
import pytest_asyncio
import redis.asyncio as redis
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


@pytest.mark.asyncio
async def test_channel_messages_only_reach_subscribers_and_can_unsubscribe(server):
    uri = f"ws://127.0.0.1:{server.bound_port}"
    async with connect(uri) as alerts, connect(uri) as other:
        await alerts.recv()
        await other.recv()
        await alerts.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await alerts.send(
            json.dumps({"type": "broadcast", "payload": {"channel": "alerts", "text": "one"}})
        )
        message = await receive_json(alerts)
        assert message["payload"]["text"] == "one"
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(other.recv(), timeout=0.05)

        await alerts.send(json.dumps({"type": "unsubscribe", "payload": {"channel": "alerts"}}))
        await alerts.send(
            json.dumps({"type": "broadcast", "payload": {"channel": "alerts", "text": "two"}})
        )
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(alerts.recv(), timeout=0.05)


@pytest.mark.asyncio
async def test_channel_endpoints_list_subscribers(server):
    uri = f"ws://127.0.0.1:{server.bound_port}"
    async with connect(uri) as connection:
        client_id = (await receive_json(connection))["payload"]["client_id"]
        await connection.send(json.dumps({"type": "subscribe", "payload": {"channel": "system"}}))
        response = await asyncio.to_thread(
            urlopen, f"http://127.0.0.1:{server.bound_port}/channels"
        )
        assert json.loads(response.read()) == {"channels": {"system": 1}}
        response = await asyncio.to_thread(
            urlopen, f"http://127.0.0.1:{server.bound_port}/channels/system/subscribers"
        )
        assert json.loads(response.read()) == {"channel": "system", "subscribers": [client_id]}


@pytest.mark.asyncio
async def test_messages_are_persisted_and_paginated():
    with tempfile.NamedTemporaryFile(suffix=".db") as database:
        instance = NotificationServer(port=0, database_url=database.name, redis_url="redis://127.0.0.1:1")
        await instance.start()
        try:
            uri = f"ws://127.0.0.1:{instance.bound_port}"
            async with connect(uri) as connection:
                await connection.recv()
                await connection.send(json.dumps({"type": "broadcast", "payload": {"text": "saved"}}))
                assert (await receive_json(connection))["payload"]["text"] == "saved"
            response = await asyncio.to_thread(
                urlopen, f"http://127.0.0.1:{instance.bound_port}/messages?limit=1&offset=0"
            )
            result = json.loads(response.read())
            assert len(result["messages"]) == 1
            assert result["messages"][0]["type"] == "broadcast"
            assert result["messages"][0]["payload"] == {"text": "saved"}
        finally:
            await instance.stop()


@pytest.mark.asyncio
async def test_two_servers_share_redis_backbone():
    broker = redis.from_url("redis://127.0.0.1:6379/0", decode_responses=True)
    try:
        await broker.ping()
    except redis.RedisError:
        await broker.close()
        pytest.skip("Redis is not running")
    first = NotificationServer(port=0, redis_url="redis://127.0.0.1:6379/0")
    second = NotificationServer(port=0, redis_url="redis://127.0.0.1:6379/0")
    await first.start()
    await second.start()
    try:
        async with connect(f"ws://127.0.0.1:{second.bound_port}") as receiver:
            await receiver.recv()
            async with connect(f"ws://127.0.0.1:{first.bound_port}") as sender:
                await sender.recv()
                await sender.send(json.dumps({"type": "broadcast", "payload": {"text": "redis"}}))
                message = await asyncio.wait_for(receive_json(receiver), timeout=1)
                assert message["payload"] == {"text": "redis"}
    finally:
        await first.stop()
        await second.stop()
        await broker.close()
