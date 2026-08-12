import asyncio
import json
from pathlib import Path

import pytest
import pytest_asyncio
import redis.asyncio as redis
import websockets

from app import NotificationServer


async def http_health(host: str, port: int) -> dict:
    reader, writer = await asyncio.open_connection(host, port)
    writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    return json.loads(response.split(b"\r\n\r\n", 1)[1])


async def http_get(host: str, port: int, path: str) -> dict:
    reader, writer = await asyncio.open_connection(host, port)
    writer.write(f"GET {path} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n".encode())
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    return json.loads(response.split(b"\r\n\r\n", 1)[1])


@pytest_asyncio.fixture
async def server():
    instance = NotificationServer(port=0)
    running = await instance.start()
    instance.port = running.sockets[0].getsockname()[1]
    yield instance
    await instance.stop()


@pytest.mark.asyncio
async def test_connect_broadcast_and_health(server):
    uri = f"ws://{server.host}:{server.port}/"
    async with websockets.connect(uri) as first, websockets.connect(uri) as second:
        assert await http_health(server.host, server.port) == {
            "status": "ok", "connected_clients": 2
        }
        await first.send(json.dumps({"type": "broadcast", "payload": {"text": "hello"}}))
        for client in (first, second):
            message = json.loads(await asyncio.wait_for(client.recv(), 1))
            assert message["type"] == "broadcast"
            assert message["payload"] == {"text": "hello"}
            assert isinstance(message["timestamp"], str)


@pytest.mark.asyncio
async def test_disconnect_is_removed(server):
    uri = f"ws://{server.host}:{server.port}/"
    client = await websockets.connect(uri)
    assert server.connected_client_count == 1
    await client.close()
    for _ in range(20):
        if server.connected_client_count == 0:
            break
        await asyncio.sleep(0.01)
    assert server.connected_client_count == 0


@pytest.mark.asyncio
async def test_client_ids_are_monotonic_and_direct_messages_work(server):
    uri = f"ws://{server.host}:{server.port}/"
    async with websockets.connect(uri) as first, websockets.connect(uri) as second:
        ids = sorted(server.clients)
        assert ids[1] > ids[0] >= 1
        await first.send(json.dumps({"type": "direct", "payload": {"client_id": ids[1], "value": 3}}))
        message = json.loads(await asyncio.wait_for(second.recv(), 1))
        assert message["type"] == "direct"
        assert message["payload"]["value"] == 3


@pytest.mark.asyncio
async def test_messages_are_persisted_and_paginated(tmp_path: Path):
    database = f"sqlite:///{tmp_path / 'messages.sqlite'}"
    instance = NotificationServer(port=0, database_url=database, redis_url="redis://localhost:63999")
    running = await instance.start()
    instance.port = running.sockets[0].getsockname()[1]
    uri = f"ws://{instance.host}:{instance.port}/"
    async with websockets.connect(uri) as client:
        await client.send(json.dumps({"type": "subscribe", "channel": "audit"}))
        await client.send(json.dumps({"type": "system", "channel": "audit", "payload": {"ok": True}}))
        message = json.loads(await asyncio.wait_for(client.recv(), 1))
        assert message["payload"] == {"ok": True}
    await instance.stop()

    restarted = NotificationServer(port=0, database_url=database, redis_url="redis://localhost:63999")
    running = await restarted.start()
    restarted.port = running.sockets[0].getsockname()[1]
    try:
        result = await http_get(restarted.host, restarted.port, "/messages?limit=1&offset=0")
        assert result["messages"][0]["channel"] == "audit"
        assert result["messages"][0]["payload"] == {"ok": True}
    finally:
        await restarted.stop()


@pytest.mark.asyncio
async def test_servers_share_redis_pubsub(tmp_path: Path):
    redis_url = "redis://localhost:6379/15"
    broker = redis.from_url(redis_url, decode_responses=True)
    try:
        await broker.ping()
    except Exception:
        await broker.close()


@pytest.mark.asyncio
async def test_history_filters_channel_since_and_reports_more(tmp_path: Path):
    instance = NotificationServer(
        port=0,
        database_url=f"sqlite:///{tmp_path / 'history.sqlite'}",
        redis_url="redis://localhost:63999",
    )
    running = await instance.start()
    instance.port = running.sockets[0].getsockname()[1]
    uri = f"ws://{instance.host}:{instance.port}/"
    try:
        async with websockets.connect(uri) as client:
            await client.send(json.dumps({"type": "subscribe", "channel": "history"}))
            await client.send(json.dumps({"type": "system", "channel": "history", "payload": {"n": 1}}))
            first = json.loads(await asyncio.wait_for(client.recv(), 1))
            await client.send(json.dumps({"type": "system", "channel": "other", "payload": {"n": 2}}))
            await client.send(json.dumps({"type": "system", "channel": "history", "payload": {"n": 3}}))
            third = json.loads(await asyncio.wait_for(client.recv(), 1))

        result = await http_get(
            instance.host,
            instance.port,
            f"/history?channel=history&since={first['timestamp']}&limit=1",
        )
        assert [message["payload"]["n"] for message in result["messages"]] == [1]
        assert result["has_more"] is True
        assert third["timestamp"] > first["timestamp"]
    finally:
        await instance.stop()


@pytest.mark.asyncio
async def test_rate_limit_returns_error_without_dropping_connection(tmp_path: Path):
    redis_url = "redis://localhost:6379/14"
    broker = redis.from_url(redis_url, decode_responses=True)
    try:
        await broker.ping()
    except Exception:
        await broker.close()
        pytest.skip("Redis is not available")
    await broker.flushdb()
    instance = NotificationServer(
        port=0,
        rate_limit=2,
        redis_url=redis_url,
        database_url=f"sqlite:///{tmp_path / 'rate.sqlite'}",
    )
    running = await instance.start()
    instance.port = running.sockets[0].getsockname()[1]
    try:
        async with websockets.connect(f"ws://{instance.host}:{instance.port}/") as client:
            for value in (1, 2):
                await client.send(json.dumps({"type": "broadcast", "payload": {"n": value}}))
                assert json.loads(await asyncio.wait_for(client.recv(), 1))["payload"]["n"] == value
            await client.send(json.dumps({"type": "broadcast", "payload": {"n": 3}}))
            error = json.loads(await asyncio.wait_for(client.recv(), 1))
            assert error["type"] == "error"
            assert error["payload"]["error"] == "rate limit exceeded"
    finally:
        await instance.stop()
        await broker.close()
        pytest.skip("Redis is not available")
    await broker.flushdb()
    first = NotificationServer(port=0, redis_url=redis_url, database_url=f"sqlite:///{tmp_path / 'first.sqlite'}")
    second = NotificationServer(port=0, redis_url=redis_url, database_url=f"sqlite:///{tmp_path / 'second.sqlite'}")
    first_running = await first.start()
    second_running = await second.start()
    first.port = first_running.sockets[0].getsockname()[1]
    second.port = second_running.sockets[0].getsockname()[1]
    try:
        async with websockets.connect(f"ws://{first.host}:{first.port}/") as subscriber:
            await subscriber.send(json.dumps({"type": "subscribe", "channel": "shared"}))
            async with websockets.connect(f"ws://{second.host}:{second.port}/") as publisher:
                await publisher.send(json.dumps({"type": "broadcast", "channel": "shared", "payload": {"n": 1}}))
            message = json.loads(await asyncio.wait_for(subscriber.recv(), 2))
            assert message["payload"] == {"n": 1}
    finally:
        await first.stop()
        await second.stop()
        await broker.close()
