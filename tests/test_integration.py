import asyncio
import json
import urllib.request
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

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


@pytest.mark.asyncio
async def test_rate_limit_uses_per_client_redis_counters(tmp_path):
    redis_client = fakeredis.aioredis.FakeRedis()
    server = NotificationServer(
        port=0,
        redis_client=redis_client,
        database_url=f"sqlite:///{tmp_path / 'rate-limit.db'}",
        rate_limit=2,
    )
    await server.start()
    first = second = None
    try:
        first, _ = await connect_client(server)
        second, _ = await connect_client(server)
        request = json.dumps({"type": "broadcast", "payload": {"text": "hello"}})

        await first.send(request)
        await receive_json(first)
        await receive_json(second)
        await first.send(request)
        await receive_json(first)
        await receive_json(second)
        await first.send(request)
        error = await receive_json(first)

        assert error["type"] == "system"
        assert error["payload"] == {"error": "rate limit exceeded"}
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(second.recv(), timeout=0.05)

        await second.send(request)
        assert (await receive_json(first))["type"] == "broadcast"
        assert (await receive_json(second))["type"] == "broadcast"
        assert len(server.messages.list(10, 0)) == 3
    finally:
        if first is not None:
            await first.close()
        if second is not None:
            await second.close()
        await server.stop()
        await redis_client.aclose()


@pytest.mark.asyncio
async def test_history_filters_and_paginates_chronologically(tmp_path):
    server = NotificationServer(
        port=0, database_url=f"sqlite:///{tmp_path / 'channel-history.db'}"
    )
    for channel, number, created_at in (
        ("alerts", 1, "2026-08-13T10:00:00Z"),
        ("other", 2, "2026-08-13T10:30:00Z"),
        ("alerts", 3, "2026-08-13T11:00:00Z"),
        ("alerts", 4, "2026-08-13T12:00:00Z"),
    ):
        server.messages.add(
            {
                "type": "broadcast",
                "channel": channel,
                "payload": {"number": number},
                "timestamp": created_at,
            }
        )
    await server.start()
    try:
        query = urlencode(
            {"channel": "alerts", "since": "2026-08-13T10:30:00Z", "limit": 1}
        )
        status, body = await fetch_json(server, f"/history?{query}")

        assert status == 200
        assert body["has_more"] is True
        assert [item["payload"]["number"] for item in body["messages"]] == [3]

        query = urlencode(
            {"channel": "alerts", "since": "2026-08-13T10:30:00Z", "limit": 50}
        )
        _, body = await fetch_json(server, f"/history?{query}")
        assert body["has_more"] is False
        assert [item["payload"]["number"] for item in body["messages"]] == [3, 4]
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_startup_cleanup_removes_expired_messages(tmp_path):
    server = NotificationServer(
        port=0,
        database_url=f"sqlite:///{tmp_path / 'expiry.db'}",
        message_ttl_days=7,
    )
    now = datetime.now(timezone.utc)
    for number, created_at in (
        (1, now - timedelta(days=8)),
        (2, now - timedelta(days=6)),
    ):
        server.messages.add(
            {
                "type": "broadcast",
                "channel": "alerts",
                "payload": {"number": number},
                "timestamp": created_at.isoformat().replace("+00:00", "Z"),
            }
        )
    await server.start()
    try:
        for _ in range(20):
            if len(server.messages.list(10, 0)) == 1:
                break
            await asyncio.sleep(0.01)
        assert [item["payload"]["number"] for item in server.messages.list(10, 0)] == [2]
    finally:
        await server.stop()
