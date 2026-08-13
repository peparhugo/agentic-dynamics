import asyncio
from datetime import datetime, timedelta, timezone

import fakeredis.aioredis
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from app import MessageStore, NotificationServer, RedisBackbone, make_message
from tests.test_app import health_request, receive_json, send_message


async def test_redis_rate_limit_returns_error_and_is_per_client():
    fake_server = fakeredis.FakeServer()
    server = NotificationServer(
        backbone=RedisBackbone(fakeredis.aioredis.FakeRedis(server=fake_server)),
        rate_limit=2,
    )
    try:
        async with serve(server.websocket_handler, "127.0.0.1", 0) as websocket_server:
            port = websocket_server.sockets[0].getsockname()[1]
            async with connect(f"ws://127.0.0.1:{port}") as first, connect(
                f"ws://127.0.0.1:{port}"
            ) as second:
                await receive_json(first)
                await receive_json(second)

                await send_message(first, "subscribe", channel="one")
                await send_message(first, "subscribe", channel="two")
                await send_message(first, "subscribe", channel="three")
                error = await receive_json(first)

                assert error["type"] == "system"
                assert error["payload"] == {
                    "event": "error",
                    "message": "rate limit exceeded",
                }

                await send_message(second, "subscribe", channel="three")
                await asyncio.sleep(0.01)
                assert await server.clients.subscribers("three")
    finally:
        await server.close()


async def test_history_filters_orders_and_paginates_by_channel(tmp_path):
    server = NotificationServer(database_url=str(tmp_path / "history.db"))
    timestamps = [
        "2026-01-01T00:00:03+00:00",
        "2026-01-01T00:00:01+00:00",
        "2026-01-01T00:00:02+00:00",
    ]
    await server.store.save(
        {**make_message("broadcast", {"sequence": 3}, "news"), "timestamp": timestamps[0]}
    )
    await server.store.save(
        {**make_message("broadcast", {"sequence": 1}, "news"), "timestamp": timestamps[1]}
    )
    await server.store.save(
        {**make_message("broadcast", {"sequence": 99}, "other"), "timestamp": timestamps[1]}
    )
    await server.store.save(
        {**make_message("broadcast", {"sequence": 2}, "news"), "timestamp": timestamps[2]}
    )

    http_server = await asyncio.start_server(server.health_handler, "127.0.0.1", 0)
    port = http_server.sockets[0].getsockname()[1]
    try:
        async with http_server:
            header, body = await health_request(
                port,
                "/history?channel=news&since=2026-01-01T00%3A00%3A01Z&limit=2",
            )
        assert "200 OK" in header
        assert [message["payload"]["sequence"] for message in body["messages"]] == [1, 2]
        assert body["has_more"] is True
    finally:
        await server.close()


async def test_history_persists_and_validates_query(tmp_path):
    database = tmp_path / "persistent-history.db"
    first = NotificationServer(database_url=str(database))
    await first.store.save(
        {
            **make_message("broadcast", {"text": "persisted"}, "news"),
            "timestamp": "2026-01-01T00:00:00+00:00",
        }
    )
    await first.close()

    second = NotificationServer(database_url=str(database))
    http_server = await asyncio.start_server(second.health_handler, "127.0.0.1", 0)
    port = http_server.sockets[0].getsockname()[1]
    try:
        async with http_server:
            _, body = await health_request(
                port, "/history?channel=news&since=2025-01-01T00%3A00%3A00Z"
            )
            invalid_header, invalid = await health_request(port, "/history?channel=news")
        assert body["messages"][0]["payload"] == {"text": "persisted"}
        assert body["has_more"] is False
        assert "400 Bad Request" in invalid_header
        assert "error" in invalid
    finally:
        await second.close()


async def test_startup_cleanup_removes_expired_messages(tmp_path):
    database = tmp_path / "expiry.db"
    store = MessageStore(str(database))
    old = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    recent = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    await store.save({**make_message("broadcast", {"age": "old"}, "news"), "timestamp": old})
    await store.save(
        {**make_message("broadcast", {"age": "recent"}, "news"), "timestamp": recent}
    )
    await store.close()

    server = NotificationServer(database_url=str(database), message_ttl_days=7)
    try:
        await server.start()
        await server._cleanup_task
        messages, has_more = await server.store.history("news", old, 50)
        assert [message["payload"]["age"] for message in messages] == ["recent"]
        assert has_more is False
    finally:
        await server.close()
