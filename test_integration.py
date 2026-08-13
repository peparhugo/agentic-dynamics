import asyncio
import json
import urllib.request
from datetime import datetime, timedelta, timezone

import fakeredis
import fakeredis.aioredis
import pytest
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from app import MessageStore, NotificationServer, RedisBackbone


async def receive_json(websocket):
    return json.loads(await asyncio.wait_for(websocket.recv(), timeout=1))


def valid_message(message_type, payload, channel=None):
    outgoing = {
        "type": message_type,
        "payload": payload,
        "timestamp": "2026-01-01T00:00:00Z",
    }
    if channel is not None:
        outgoing["channel"] = channel
    return outgoing


async def fetch_json(port, path):
    def fetch():
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}") as response:
            return response.status, json.load(response)

    return await asyncio.to_thread(fetch)


@pytest.mark.asyncio
async def test_redis_pubsub_delivers_between_server_instances(
    unused_tcp_port_factory, tmp_path
):
    fake_server = fakeredis.FakeServer()
    first_redis = fakeredis.aioredis.FakeRedis(
        server=fake_server, decode_responses=True
    )
    second_redis = fakeredis.aioredis.FakeRedis(
        server=fake_server, decode_responses=True
    )
    first = NotificationServer(
        RedisBackbone("redis://unused", first_redis),
        MessageStore(str(tmp_path / "first.db")),
    )
    second = NotificationServer(
        RedisBackbone("redis://unused", second_redis),
        MessageStore(str(tmp_path / "second.db")),
    )
    first_port = unused_tcp_port_factory()
    second_port = unused_tcp_port_factory()

    await first.start()
    await second.start()
    try:
        async with serve(
            first.handler,
            "127.0.0.1",
            first_port,
            process_request=first.process_request,
        ), serve(
            second.handler,
            "127.0.0.1",
            second_port,
            process_request=second.process_request,
        ):
            async with connect(f"ws://127.0.0.1:{first_port}") as sender, connect(
                f"ws://127.0.0.1:{second_port}"
            ) as recipient:
                await receive_json(sender)
                await receive_json(recipient)
                outgoing = valid_message("broadcast", {"text": "shared"})
                await sender.send(json.dumps(outgoing))

                assert await receive_json(sender) == outgoing
                assert await receive_json(recipient) == outgoing
                assert await fetch_json(first_port, "/health") == (
                    200,
                    {"connected_clients": 2},
                )
    finally:
        await first.close()
        await second.close()
        await first_redis.aclose()
        await second_redis.aclose()


@pytest.mark.asyncio
async def test_redis_stores_shared_channel_membership(
    unused_tcp_port, tmp_path
):
    fake_server = fakeredis.FakeServer()
    redis_client = fakeredis.aioredis.FakeRedis(
        server=fake_server, decode_responses=True
    )
    notification_server = NotificationServer(
        RedisBackbone("redis://unused", redis_client),
        MessageStore(str(tmp_path / "channels.db")),
    )
    await notification_server.start()
    try:
        async with serve(
            notification_server.handler,
            "127.0.0.1",
            unused_tcp_port,
            process_request=notification_server.process_request,
        ):
            async with connect(f"ws://127.0.0.1:{unused_tcp_port}") as websocket:
                client_id = (await receive_json(websocket))["payload"]["client_id"]
                await websocket.send(
                    json.dumps(valid_message("subscribe", {}, "persistent"))
                )

                assert await redis_client.sismember("notifications:clients", client_id)
                for _ in range(20):
                    if await redis_client.sismember(
                        "notifications:channel:persistent", client_id
                    ):
                        break
                    await asyncio.sleep(0.01)
                assert await redis_client.sismember(
                    "notifications:channel:persistent", client_id
                )
                assert await fetch_json(unused_tcp_port, "/channels") == (
                    200,
                    {"channels": {"persistent": 1}},
                )
    finally:
        await notification_server.close()
        await redis_client.aclose()


@pytest.mark.asyncio
async def test_sqlite_message_history_persists_and_paginates(
    unused_tcp_port, tmp_path
):
    database_path = tmp_path / "messages.db"
    notification_server = NotificationServer(store=MessageStore(str(database_path)))
    try:
        async with serve(
            notification_server.handler,
            "127.0.0.1",
            unused_tcp_port,
            process_request=notification_server.process_request,
        ):
            async with connect(f"ws://127.0.0.1:{unused_tcp_port}") as websocket:
                await receive_json(websocket)
                first = valid_message("broadcast", {"text": "first"})
                second = valid_message("broadcast", {"text": "second"})
                await websocket.send(json.dumps(first))
                await receive_json(websocket)
                await websocket.send(json.dumps(second))
                await receive_json(websocket)

                status, body = await fetch_json(
                    unused_tcp_port, "/messages?limit=1&offset=1"
                )
                assert status == 200
                assert body["messages"] == [
                    {
                        "id": 2,
                        "channel": None,
                        "type": "broadcast",
                        "payload": {"text": "second"},
                        "timestamp": "2026-01-01T00:00:00Z",
                    }
                ]
    finally:
        await notification_server.close()

    reopened = MessageStore(str(database_path))
    try:
        assert [item["payload"]["text"] for item in reopened.list(50, 0)] == [
            "first",
            "second",
        ]
    finally:
        reopened.close()


@pytest.mark.asyncio
async def test_redis_rate_limit_returns_error_and_does_not_publish(
    unused_tcp_port, tmp_path
):
    redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    notification_server = NotificationServer(
        RedisBackbone("redis://unused", redis_client),
        MessageStore(str(tmp_path / "rate-limit.db")),
        rate_limit=2,
    )
    await notification_server.start()
    try:
        async with serve(
            notification_server.handler,
            "127.0.0.1",
            unused_tcp_port,
            process_request=notification_server.process_request,
        ):
            async with connect(f"ws://127.0.0.1:{unused_tcp_port}") as websocket:
                client_id = (await receive_json(websocket))["payload"]["client_id"]
                for text in ("first", "second"):
                    outgoing = valid_message("broadcast", {"text": text})
                    await websocket.send(json.dumps(outgoing))
                    assert await receive_json(websocket) == outgoing

                await websocket.send(
                    json.dumps(valid_message("broadcast", {"text": "blocked"}))
                )
                response = await receive_json(websocket)
                assert response["type"] == "system"
                assert response["payload"] == {"error": "rate limit exceeded"}

                keys = await redis_client.keys(
                    f"notifications:rate-limit:{client_id}:*"
                )
                assert len(keys) == 1
                assert await redis_client.get(keys[0]) == "3"
                assert [
                    item["payload"]["text"]
                    for item in notification_server.store.list(50, 0)
                ] == ["first", "second"]
    finally:
        await notification_server.close()
        await redis_client.aclose()


@pytest.mark.asyncio
async def test_history_filters_channel_and_time_and_reports_has_more(
    unused_tcp_port, tmp_path
):
    notification_server = NotificationServer(
        store=MessageStore(str(tmp_path / "history.db"))
    )
    try:
        async with serve(
            notification_server.handler,
            "127.0.0.1",
            unused_tcp_port,
            process_request=notification_server.process_request,
        ):
            async with connect(f"ws://127.0.0.1:{unused_tcp_port}") as websocket:
                await receive_json(websocket)
                messages = [
                    valid_message("broadcast", {"text": "old"}, "alerts"),
                    valid_message("broadcast", {"text": "other"}, "chat"),
                    valid_message("broadcast", {"text": "third"}, "alerts"),
                    valid_message("broadcast", {"text": "second"}, "alerts"),
                ]
                messages[0]["timestamp"] = "2026-01-01T00:00:00Z"
                messages[1]["timestamp"] = "2026-01-02T00:00:00Z"
                messages[2]["timestamp"] = "2026-01-03T00:00:00Z"
                messages[3]["timestamp"] = "2026-01-02T00:00:00Z"
                for outgoing in messages:
                    await websocket.send(json.dumps(outgoing))
                    if outgoing["channel"] == "alerts":
                        continue

                status, body = await fetch_json(
                    unused_tcp_port,
                    "/history?channel=alerts&since=2026-01-02T00%3A00%3A00Z&limit=1",
                )
                assert status == 200
                assert body["has_more"] is True
                assert [item["payload"]["text"] for item in body["messages"]] == [
                    "second"
                ]

                status, body = await fetch_json(
                    unused_tcp_port,
                    "/history?channel=alerts&since=2026-01-02T00%3A00%3A00Z&limit=50",
                )
                assert status == 200
                assert body["has_more"] is False
                assert [item["payload"]["text"] for item in body["messages"]] == [
                    "second",
                    "third",
                ]
    finally:
        await notification_server.close()


@pytest.mark.asyncio
async def test_startup_cleanup_removes_expired_messages(tmp_path):
    store = MessageStore(str(tmp_path / "expiry.db"))
    expired = valid_message("broadcast", {"text": "expired"}, "alerts")
    expired["timestamp"] = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    current = valid_message("broadcast", {"text": "current"}, "alerts")
    current["timestamp"] = datetime.now(timezone.utc).isoformat()
    store.add(expired)
    store.add(current)
    notification_server = NotificationServer(store=store, message_ttl_days=7)

    await notification_server.start()
    try:
        await asyncio.sleep(0)
        assert [item["payload"]["text"] for item in store.list(50, 0)] == ["current"]
    finally:
        await notification_server.close()
