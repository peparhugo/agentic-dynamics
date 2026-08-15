import asyncio
import json
import os

import pytest
from websockets.asyncio.client import connect

from notification_server import NotificationServer


async def receive_json(client):
    return json.loads(await asyncio.wait_for(client.recv(), timeout=2))


async def get_json(port, path):
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(f"GET {path} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n".encode())
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    return json.loads(response.split(b"\r\n\r\n", 1)[1])


@pytest.mark.asyncio
async def test_messages_are_persisted_and_paginated(unused_tcp_port, tmp_path):
    server = NotificationServer(
        "127.0.0.1", unused_tcp_port, database_url=str(tmp_path / "messages.db")
    )
    await server.start()
    client = await connect(f"ws://127.0.0.1:{unused_tcp_port}")
    try:
        await receive_json(client)
        await client.send(json.dumps({"type": "subscribe", "channel": "audit"}))
        await client.send(json.dumps({
            "type": "broadcast", "channel": "audit", "payload": {"value": 1}
        }))
        message = await receive_json(client)
        history = await get_json(unused_tcp_port, "/messages?limit=1&offset=0")
        assert history == [{
            "id": 1,
            "channel": "audit",
            "type": "broadcast",
            "payload": {"value": 1},
            "timestamp": message["timestamp"],
        }]
    finally:
        await client.close()
        await server.stop()


@pytest.mark.asyncio
async def test_redis_pubsub_delivers_between_server_instances(unused_tcp_port_factory, tmp_path):
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        pytest.skip("REDIS_URL is required for the Redis integration test")
    first = NotificationServer(
        "127.0.0.1", unused_tcp_port_factory(), redis_url=redis_url,
        database_url=str(tmp_path / "first.db"),
    )
    second = NotificationServer(
        "127.0.0.1", unused_tcp_port_factory(), redis_url=redis_url,
        database_url=str(tmp_path / "second.db"),
    )
    await first.start()
    await second.start()
    subscriber = await connect(f"ws://127.0.0.1:{second.port}")
    publisher = await connect(f"ws://127.0.0.1:{first.port}")
    try:
        await receive_json(subscriber)
        await receive_json(publisher)
        await subscriber.send(json.dumps({"type": "subscribe", "channel": "shared"}))
        await publisher.send(json.dumps({
            "type": "broadcast", "channel": "shared", "payload": {"ok": True}
        }))
        assert (await receive_json(subscriber))["payload"] == {"ok": True}
    finally:
        await subscriber.close()
        await publisher.close()
        await second.stop()
        await first.stop()
