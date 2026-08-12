import asyncio
import json

import fakeredis.aioredis
import pytest
import pytest_asyncio
import websockets

from app import NotificationServer


async def get_json(server, path):
    reader, writer = await asyncio.open_connection(server.host, server.http_port)
    writer.write(f"GET {path} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode())
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    return json.loads(response.split(b"\r\n\r\n", 1)[1])


@pytest_asyncio.fixture
async def redis_server(tmp_path):
    fake_server = fakeredis.FakeServer()
    redis_client = fakeredis.aioredis.FakeRedis(server=fake_server, decode_responses=True)
    instance = NotificationServer(
        websocket_port=0,
        http_port=0,
        redis_client=redis_client,
        database_url=f"sqlite:///{tmp_path / 'messages.sqlite3'}",
    )
    await instance.start()
    yield instance, fake_server
    await instance.stop()


@pytest.mark.asyncio
async def test_redis_pubsub_delivers_between_server_instances(tmp_path):
    fake_server = fakeredis.FakeServer()
    first_server = NotificationServer(
        websocket_port=0,
        http_port=0,
        redis_client=fakeredis.aioredis.FakeRedis(server=fake_server, decode_responses=True),
        database_url=f"sqlite:///{tmp_path / 'first.sqlite3'}",
    )
    second_server = NotificationServer(
        websocket_port=0,
        http_port=0,
        redis_client=fakeredis.aioredis.FakeRedis(server=fake_server, decode_responses=True),
        database_url=f"sqlite:///{tmp_path / 'second.sqlite3'}",
    )
    await first_server.start()
    await second_server.start()
    try:
        first = await websockets.connect(f"ws://{first_server.host}:{first_server.websocket_port}")
        second = await websockets.connect(f"ws://{second_server.host}:{second_server.websocket_port}")
        await first.recv()
        await second.recv()
        await first.send(json.dumps({"type": "broadcast", "payload": {"value": "redis"}}))
        assert json.loads(await second.recv())["payload"] == {"value": "redis"}
        await first.close()
        await second.close()
    finally:
        await first_server.stop()
        await second_server.stop()


@pytest.mark.asyncio
async def test_messages_are_persisted_and_paginated(redis_server):
    server, _ = redis_server
    websocket = await websockets.connect(f"ws://{server.host}:{server.websocket_port}")
    await asyncio.wait_for(websocket.recv(), timeout=2)
    await websocket.send(json.dumps({"type": "subscribe", "channel": "history", "payload": {}}))
    await websocket.send(json.dumps({"type": "broadcast", "channel": "history", "payload": {"n": 1}}))
    await asyncio.wait_for(websocket.recv(), timeout=2)
    await websocket.send(json.dumps({"type": "broadcast", "channel": "history", "payload": {"n": 2}}))
    await asyncio.wait_for(websocket.recv(), timeout=2)

    result = await get_json(server, "/messages?limit=1&offset=1")
    assert len(result["messages"]) == 1
    assert result["messages"][0]["channel"] == "history"
    assert result["messages"][0]["payload"] == {"n": 1}
    await websocket.close()


@pytest.mark.asyncio
async def test_rate_limit_returns_system_error_per_client(redis_server, monkeypatch):
    server, _ = redis_server
    monkeypatch.setenv("RATE_LIMIT", "2")
    # The server reads the setting at construction time, so update this test
    # instance after the fixture has started.
    server.rate_limit = 2
    websocket = await websockets.connect(f"ws://{server.host}:{server.websocket_port}")
    await websocket.recv()

    for value in (1, 2):
        await websocket.send(json.dumps({"type": "broadcast", "payload": {"value": value}}))
        assert json.loads(await websocket.recv())["payload"]["value"] == value
    await websocket.send(json.dumps({"type": "broadcast", "payload": {"value": 3}}))
    error = json.loads(await websocket.recv())
    assert error["type"] == "system"
    assert error["payload"] == {"error": "rate limit exceeded"}
    await websocket.close()


@pytest.mark.asyncio
async def test_history_filters_since_and_reports_more(redis_server):
    server, _ = redis_server
    await server.broadcast({"type": "broadcast", "channel": "history", "payload": {"n": 1}, "timestamp": "2026-01-01T00:00:00+00:00"})
    await server.broadcast({"type": "broadcast", "channel": "history", "payload": {"n": 2}, "timestamp": "2026-01-01T00:01:00+00:00"})
    await server.broadcast({"type": "broadcast", "channel": "history", "payload": {"n": 3}, "timestamp": "2026-01-01T00:02:00+00:00"})

    result = await get_json(server, "/history?channel=history&since=2026-01-01T00%3A00%3A00Z&limit=1")
    assert [message["payload"]["n"] for message in result["messages"]] == [2]
    assert result["has_more"] is True
