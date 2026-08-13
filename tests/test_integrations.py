import asyncio
import json

import fakeredis.aioredis
import pytest
from websockets.asyncio.client import connect

from app import MessageStore, NotificationServer, RedisBackbone


async def receive_json(websocket):
    return json.loads(await asyncio.wait_for(websocket.recv(), timeout=1))


async def send_message(websocket, message_type, payload=None, channel=None):
    outgoing = {
        "type": message_type,
        "payload": payload or {},
        "timestamp": "2026-01-01T00:00:00Z",
    }
    if channel is not None:
        outgoing["channel"] = channel
    await websocket.send(json.dumps(outgoing))


@pytest.mark.asyncio
async def test_redis_pubsub_distributes_between_server_instances():
    redis_server = fakeredis.FakeServer()
    first_redis = fakeredis.aioredis.FakeRedis(
        server=redis_server, decode_responses=True
    )
    second_redis = fakeredis.aioredis.FakeRedis(
        server=redis_server, decode_responses=True
    )
    first = NotificationServer(RedisBackbone("redis://unused", first_redis))
    second = NotificationServer(RedisBackbone("redis://unused", second_redis))

    try:
        async with first.start("127.0.0.1", 0) as first_http, second.start(
            "127.0.0.1", 0
        ) as second_http:
            first_url = f"ws://127.0.0.1:{first_http.sockets[0].getsockname()[1]}"
            second_url = f"ws://127.0.0.1:{second_http.sockets[0].getsockname()[1]}"
            async with connect(first_url) as sender, connect(second_url) as receiver:
                await receive_json(sender)
                receiver_id = (await receive_json(receiver))["payload"]["client_id"]

                await send_message(receiver, "subscribe", channel="alerts")
                await send_message(sender, "broadcast", {"text": "shared"}, "alerts")
                broadcast = await receive_json(receiver)
                assert broadcast["payload"] == {"text": "shared"}
                assert broadcast["channel"] == "alerts"

                await send_message(
                    sender,
                    "direct",
                    {"client_id": receiver_id, "text": "private"},
                    "alerts",
                )
                direct = await receive_json(receiver)
                assert direct["payload"]["text"] == "private"
                assert direct["type"] == "direct"
    finally:
        await first.backbone.close()
        await second.backbone.close()


@pytest.mark.asyncio
async def test_messages_endpoint_reads_persistent_sqlite_history(tmp_path):
    database_path = tmp_path / "messages.db"
    server = NotificationServer(database_url=str(database_path))
    async with server.start("127.0.0.1", 0) as http_server:
        port = http_server.sockets[0].getsockname()[1]
        url = f"ws://127.0.0.1:{port}"
        async with connect(url) as websocket:
            await receive_json(websocket)
            await send_message(websocket, "broadcast", {"number": 1})
            await receive_json(websocket)
            await send_message(websocket, "broadcast", {"number": 2}, "updates")

        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(
            b"GET /messages?limit=1&offset=1 HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\nConnection: close\r\n\r\n"
        )
        await writer.drain()
        response = await reader.read()
        writer.close()
        await writer.wait_closed()

    body = json.loads(response.split(b"\r\n\r\n", 1)[1])
    assert len(body["messages"]) == 1
    assert body["messages"][0]["payload"] == {"number": 1}
    assert set(body["messages"][0]) == {
        "id",
        "channel",
        "type",
        "payload",
        "timestamp",
    }
    server.messages.close()

    reopened = MessageStore(str(database_path))
    try:
        messages = reopened.list()
        assert [item["payload"] for item in messages] == [
            {"number": 2},
            {"number": 1},
        ]
    finally:
        reopened.close()
