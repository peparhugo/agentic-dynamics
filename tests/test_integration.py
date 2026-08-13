import asyncio
import json
import urllib.request

import fakeredis.aioredis
import pytest
from websockets.asyncio.client import connect

from app import NotificationServer


async def receive_json(websocket):
    return json.loads(await asyncio.wait_for(websocket.recv(), timeout=1))


async def connect_client(server):
    websocket = await connect(f"ws://127.0.0.1:{server.port}")
    greeting = await receive_json(websocket)
    return websocket, greeting


async def fetch_json(server, path):
    def fetch():
        with urllib.request.urlopen(f"http://127.0.0.1:{server.port}{path}") as response:
            return response.status, json.load(response)

    return await asyncio.to_thread(fetch)


@pytest.mark.asyncio
async def test_redis_pubsub_delivers_between_server_instances(tmp_path):
    fake_server = fakeredis.FakeServer()
    first_redis = fakeredis.aioredis.FakeRedis(server=fake_server)
    second_redis = fakeredis.aioredis.FakeRedis(server=fake_server)
    database_url = f"sqlite:///{tmp_path / 'messages.db'}"
    first_server = NotificationServer(port=0, redis_client=first_redis, database_url=database_url)
    second_server = NotificationServer(port=0, redis_client=second_redis, database_url=database_url)
    await first_server.start()
    await second_server.start()
    sender = subscriber = None
    try:
        sender, _ = await connect_client(first_server)
        subscriber, _ = await connect_client(second_server)
        await subscriber.send(json.dumps({"type": "subscribe", "channel": "alerts"}))

        await sender.send(
            json.dumps({"type": "broadcast", "channel": "alerts", "payload": {"text": "shared"}})
        )

        received = await receive_json(subscriber)
        assert received["payload"] == {"text": "shared"}
        assert received["channel"] == "alerts"
        status, channels = await fetch_json(first_server, "/channels")
        assert status == 200
        assert channels == {"channels": [{"name": "alerts", "subscriber_count": 1}]}
    finally:
        if sender is not None:
            await sender.close()
        if subscriber is not None:
            await subscriber.close()
        await first_server.stop()
        await second_server.stop()
        await first_redis.aclose()
        await second_redis.aclose()


@pytest.mark.asyncio
async def test_messages_persist_across_restart_with_pagination(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'history.db'}"
    first_server = NotificationServer(port=0, database_url=database_url)
    await first_server.start()
    client, _ = await connect_client(first_server)
    await client.send(json.dumps({"type": "broadcast", "payload": {"number": 1}}))
    await receive_json(client)
    await client.send(json.dumps({"type": "broadcast", "payload": {"number": 2}}))
    await receive_json(client)
    await client.close()
    await first_server.stop()

    second_server = NotificationServer(port=0, database_url=database_url)
    await second_server.start()
    try:
        status, body = await fetch_json(second_server, "/messages?limit=1&offset=1")
        assert status == 200
        assert len(body["messages"]) == 1
        stored = body["messages"][0]
        assert stored["id"] == 1
        assert stored["channel"] is None
        assert stored["type"] == "broadcast"
        assert stored["payload"] == {"number": 1}
        assert stored["timestamp"].endswith("Z")
    finally:
        await second_server.stop()
