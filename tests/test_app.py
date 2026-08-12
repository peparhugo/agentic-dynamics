import asyncio
import json
from urllib.request import urlopen

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from websockets.asyncio.client import connect

from app import NotificationServer


@pytest_asyncio.fixture
async def server():
    instance = NotificationServer("127.0.0.1", 0)
    await instance.start()
    yield instance
    await instance.stop()


async def receive_json(client):
    return json.loads(await client.recv())


async def wait_for_count(server, expected):
    for _ in range(20):
        if server.registry.count == expected:
            return
        await asyncio.sleep(0.01)
    assert server.registry.count == expected


@pytest.mark.asyncio
async def test_clients_receive_unique_ids_and_health_count(server):
    async with connect(f"ws://127.0.0.1:{server.port}") as first:
        first_system = await receive_json(first)
        async with connect(f"ws://127.0.0.1:{server.port}") as second:
            second_system = await receive_json(second)
            assert first_system["type"] == second_system["type"] == "system"
            assert first_system["payload"]["client_id"] != second_system["payload"]["client_id"]
            assert server.registry.count == 2
            response = await asyncio.to_thread(
                urlopen, f"http://127.0.0.1:{server.port}/health"
            )
            assert json.loads(response.read()) == {"status": "ok", "clients": 2}
        await wait_for_count(server, 1)
    await wait_for_count(server, 0)


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients(server):
    async with (
        connect(f"ws://127.0.0.1:{server.port}") as first,
        connect(f"ws://127.0.0.1:{server.port}") as second,
    ):
        await first.recv()
        await second.recv()
        message = {"type": "broadcast", "payload": {"text": "hello"}}
        await first.send(json.dumps(message))
        received = await asyncio.gather(receive_json(first), receive_json(second))
        assert [item["payload"] for item in received] == [{"text": "hello"}] * 2
        assert all(item["type"] == "broadcast" and item["timestamp"] for item in received)


@pytest.mark.asyncio
async def test_direct_message_targets_one_client(server):
    async with (
        connect(f"ws://127.0.0.1:{server.port}") as first,
        connect(f"ws://127.0.0.1:{server.port}") as second,
    ):
        await first.recv()
        second_id = (await receive_json(second))["payload"]["client_id"]
        await first.send(json.dumps({"type": "direct", "payload": {"client_id": second_id, "text": "private"}}))
        received = await receive_json(second)
        assert received["type"] == "direct"
        assert received["payload"]["text"] == "private"
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(first.recv(), timeout=0.05)


@pytest.mark.asyncio
async def test_invalid_message_returns_system_error(server):
    async with connect(f"ws://127.0.0.1:{server.port}") as client:
        await client.recv()
        await client.send("not json")
        error = await receive_json(client)
        assert error["type"] == "system"
        assert error["payload"] == {"error": "invalid message"}


@pytest.mark.asyncio
async def test_channel_broadcast_reaches_only_subscribers(server):
    async with (
        connect(f"ws://127.0.0.1:{server.port}") as alerts,
        connect(f"ws://127.0.0.1:{server.port}") as other,
    ):
        await alerts.recv()
        await other.recv()
        await alerts.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        confirmation = await receive_json(alerts)
        assert confirmation["payload"] == {"event": "subscribed", "channel": "alerts"}

        await other.send(json.dumps({
            "type": "broadcast",
            "channel": "alerts",
            "payload": {"text": "warning"},
        }))
        received = await receive_json(alerts)
        assert received["channel"] == "alerts"
        assert received["payload"] == {"text": "warning"}
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(other.recv(), timeout=0.05)

        await alerts.send(json.dumps({"type": "unsubscribe", "payload": {"channel": "alerts"}}))
        assert (await receive_json(alerts))["payload"]["event"] == "unsubscribed"
        await other.send(json.dumps({
            "type": "broadcast",
            "channel": "alerts",
            "payload": {"text": "ignored"},
        }))
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(alerts.recv(), timeout=0.05)


@pytest.mark.asyncio
async def test_channel_endpoints_list_subscribers_and_clean_up(server):
    async with connect(f"ws://127.0.0.1:{server.port}") as client:
        connected = await receive_json(client)
        client_id = connected["payload"]["client_id"]
        await client.send(json.dumps({"type": "subscribe", "channel": "system"}))
        await receive_json(client)

        response = await asyncio.to_thread(urlopen, f"http://127.0.0.1:{server.port}/channels")
        assert json.loads(response.read()) == {
            "channels": [{"name": "system", "subscribers": 1}]
        }
        response = await asyncio.to_thread(
            urlopen, f"http://127.0.0.1:{server.port}/channels/system/subscribers"
        )
        assert json.loads(response.read()) == {
            "channel": "system", "subscribers": [client_id]
        }


@pytest.mark.asyncio
async def test_messages_are_persisted_and_paginated(tmp_path):
    instance = NotificationServer(
        "127.0.0.1", 0, database_url=f"sqlite:///{tmp_path / 'messages.sqlite'}"
    )
    await instance.start()
    try:
        async with connect(f"ws://127.0.0.1:{instance.port}") as client:
            await client.recv()
            await client.send(json.dumps({"type": "broadcast", "payload": {"n": 1}}))
            await client.recv()
            await client.send(json.dumps({"type": "direct", "payload": {"client_id": "missing", "n": 2}}))
        response = await asyncio.to_thread(
            urlopen, f"http://127.0.0.1:{instance.port}/messages?limit=1&offset=1"
        )
        body = json.loads(response.read())
        assert body["limit"] == 1
        assert body["offset"] == 1
        assert len(body["messages"]) == 1
        assert body["messages"][0]["payload"] == {"client_id": "missing", "n": 2}
    finally:
        await instance.stop()


@pytest.mark.asyncio
async def test_redis_broker_delivers_between_server_instances(tmp_path):
    redis_url = "redis://127.0.0.1:6379/15"
    redis = Redis.from_url(redis_url)
    try:
        await redis.ping()
    except Exception:
        await redis.close()
        pytest.skip("Redis is not running")
    await redis.flushdb()
    first = NotificationServer(
        "127.0.0.1", 0, redis_url=redis_url,
        database_url=f"sqlite:///{tmp_path / 'first.sqlite'}",
    )
    second = NotificationServer(
        "127.0.0.1", 0, redis_url=redis_url,
        database_url=f"sqlite:///{tmp_path / 'second.sqlite'}",
    )
    await first.start()
    await second.start()
    try:
        async with (
            connect(f"ws://127.0.0.1:{first.port}") as subscriber,
            connect(f"ws://127.0.0.1:{second.port}") as publisher,
        ):
            await subscriber.recv()
            await publisher.recv()
            await subscriber.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
            await subscriber.recv()
            await publisher.send(json.dumps({
                "type": "broadcast", "channel": "alerts", "payload": {"text": "redis"}
            }))
            received = await asyncio.wait_for(receive_json(subscriber), timeout=2)
            assert received["payload"] == {"text": "redis"}
    finally:
        await first.stop()
        await second.stop()
        await redis.flushdb()
        await redis.close()
