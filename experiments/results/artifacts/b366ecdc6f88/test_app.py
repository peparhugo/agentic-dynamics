import asyncio
import json
import os
import urllib.request

import pytest
import websockets

from app import NotificationServer


def get_health(url: str) -> dict:
    with urllib.request.urlopen(url) as response:
        return json.load(response)


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url) as response:
        return json.load(response)


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients_and_disconnect_is_removed():
    server = NotificationServer("127.0.0.1", 0)
    await server.start()
    first = await websockets.connect(f"ws://127.0.0.1:{server.port}")
    second = await websockets.connect(f"ws://127.0.0.1:{server.port}")
    try:
        assert len(server.clients) == 2
        await server.broadcast({"type": "broadcast", "payload": {"message": "hello"}})
        received = await asyncio.gather(first.recv(), second.recv())
        assert [json.loads(message)["payload"] for message in received] == [
            {"message": "hello"},
            {"message": "hello"},
        ]
        await first.close()
        for _ in range(20):
            if len(server.clients) == 1:
                break
            await asyncio.sleep(0.01)
        assert len(server.clients) == 1
    finally:
        await second.close()
        await server.stop()


@pytest.mark.asyncio
async def test_health_returns_connected_client_count():
    server = NotificationServer("127.0.0.1", 0)
    await server.start()
    clients = [await websockets.connect(f"ws://127.0.0.1:{server.port}") for _ in range(2)]
    try:
        health = await asyncio.to_thread(get_health, f"http://127.0.0.1:{server.port}/health")
        assert health == {"connected_clients": 2}
    finally:
        await asyncio.gather(*(client.close() for client in clients))
        await server.stop()


@pytest.mark.asyncio
async def test_messages_are_persisted_and_paginated(tmp_path):
    server = NotificationServer("127.0.0.1", 0, database_url=str(tmp_path / "messages.sqlite"))
    await server.start()
    try:
        await server.broadcast("system", {"event": "started"}, channel="audit")
        await server.broadcast("broadcast", {"event": "ready"})
        result = await asyncio.to_thread(get_json, f"http://127.0.0.1:{server.port}/messages?limit=1&offset=1")
        assert result["messages"][0]["type"] == "broadcast"
        assert result["messages"][0]["payload"] == {"event": "ready"}
        assert result["messages"][0]["channel"] is None
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_rate_limit_returns_error_without_dropping_message(tmp_path, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "1")
    server = NotificationServer("127.0.0.1", 0, database_url=str(tmp_path / "messages.sqlite"))
    await server.start()
    client = await websockets.connect(f"ws://127.0.0.1:{server.port}")
    try:
        await client.send(json.dumps({"type": "broadcast", "payload": {"n": 1}}))
        assert json.loads(await client.recv())["payload"] == {"n": 1}
        await client.send(json.dumps({"type": "broadcast", "payload": {"n": 2}}))
        assert json.loads(await client.recv()) == {"error": "rate limit exceeded"}
    finally:
        await client.close()
        await server.stop()


@pytest.mark.asyncio
async def test_history_filters_since_and_reports_more(tmp_path):
    server = NotificationServer("127.0.0.1", 0, database_url=str(tmp_path / "messages.sqlite"))
    await server.start()
    try:
        await server.broadcast("system", {"n": 1}, channel="audit")
        first = server.store.history("audit")[0][0]
        await server.broadcast("system", {"n": 2}, channel="audit")
        await server.broadcast("system", {"n": 3}, channel="other")
        result = await asyncio.to_thread(
            get_json,
            f"http://127.0.0.1:{server.port}/history?channel=audit&since={first['timestamp']}&limit=1",
        )
        assert [message["payload"] for message in result["messages"]] == [{"n": 2}]
        assert result["has_more"] is False
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_redis_delivers_between_server_instances():
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        pytest.skip("set REDIS_URL to run the Redis integration test")
    first_server = NotificationServer("127.0.0.1", 0, redis_url=redis_url)
    second_server = NotificationServer("127.0.0.1", 0, redis_url=redis_url)
    try:
        await first_server.start()
        await second_server.start()
    except Exception as error:
        await first_server.stop()
        await second_server.stop()
        pytest.skip(f"Redis is unavailable: {error}")
    client = await websockets.connect(f"ws://127.0.0.1:{second_server.port}")
    try:
        await first_server.broadcast("system", {"event": "from-first"})
        message = json.loads(await asyncio.wait_for(client.recv(), timeout=2))
        assert message["payload"] == {"event": "from-first"}
    finally:
        await client.close()
        await first_server.stop()
        await second_server.stop()
