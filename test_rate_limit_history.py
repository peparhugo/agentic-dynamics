import asyncio
import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import fakeredis.aioredis
import pytest
from websockets.asyncio.client import connect

from app import NotificationServer


def websocket_url(server, client_id=None):
    suffix = "" if client_id is None else f"?client_id={client_id}"
    return f"ws://127.0.0.1:{server.bound_port}{suffix}"


async def receive_json(connection):
    return json.loads(await asyncio.wait_for(connection.recv(), timeout=1))


async def get_json(server, path):
    def request():
        with urllib.request.urlopen(
            f"http://127.0.0.1:{server.bound_port}{path}", timeout=1
        ) as response:
            return response.status, json.load(response)

    return await asyncio.to_thread(request)


def notification(sequence, timestamp, channel=None):
    value = {
        "type": "broadcast",
        "payload": {"sequence": sequence},
        "timestamp": timestamp,
    }
    if channel is not None:
        value["channel"] = channel
    return value


@pytest.mark.asyncio
async def test_redis_rate_limit_is_shared_by_client_id_and_keeps_connection_open():
    redis = fakeredis.aioredis.FakeRedis()
    try:
        async with NotificationServer(
            port=0, redis_client=redis, rate_limit=2
        ) as server:
            async with connect(websocket_url(server, "limited-client")) as connection:
                await receive_json(connection)
                for sequence in range(2):
                    value = notification(sequence, "2026-08-16T12:00:00Z")
                    await connection.send(json.dumps(value))
                    assert await receive_json(connection) == value

                await connection.send(
                    json.dumps(notification(3, "2026-08-16T12:00:00Z"))
                )
                error = await receive_json(connection)
                assert error["type"] == "system"
                assert error["payload"] == {"error": "rate limit exceeded"}

                await connection.ping()

            async with connect(websocket_url(server, "limited-client")) as reconnected:
                await receive_json(reconnected)
                await reconnected.send(
                    json.dumps(notification(4, "2026-08-16T12:00:00Z"))
                )
                assert (await receive_json(reconnected))["payload"] == {
                    "error": "rate limit exceeded"
                }
    finally:
        await redis.aclose()


@pytest.mark.asyncio
async def test_history_filters_orders_and_paginates_by_channel_and_time(tmp_path):
    database = str(tmp_path / "history.db")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    timestamps = [
        (now - timedelta(minutes=3)).isoformat().replace("+00:00", "Z"),
        (now - timedelta(minutes=2)).isoformat().replace("+00:00", "Z"),
        (now - timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
    ]

    async with NotificationServer(port=0, database_url=database) as server:
        async with connect(websocket_url(server)) as connection:
            await receive_json(connection)
            values = [
                notification(3, timestamps[2], "alerts"),
                notification(99, timestamps[1], "chat"),
                notification(1, timestamps[0], "alerts"),
                notification(2, timestamps[1], "alerts"),
            ]
            for value in values:
                await connection.send(json.dumps(value))

            for _ in range(50):
                if len(server.messages.list(50, 0)) == len(values):
                    break
                await asyncio.sleep(0.01)

        query = urllib.parse.urlencode(
            {"channel": "alerts", "since": timestamps[0], "limit": 2}
        )
        status, first_page = await get_json(server, f"/history?{query}")

        assert status == 200
        assert [item["payload"]["sequence"] for item in first_page["messages"]] == [
            1,
            2,
        ]
        assert first_page["has_more"] is True

        query = urllib.parse.urlencode(
            {"channel": "alerts", "since": timestamps[1], "limit": 50}
        )
        _, later = await get_json(server, f"/history?{query}")
        assert [item["payload"]["sequence"] for item in later["messages"]] == [2, 3]
        assert later["has_more"] is False


@pytest.mark.asyncio
async def test_startup_cleanup_removes_messages_older_than_configured_ttl(tmp_path):
    database = str(tmp_path / "expiry.db")
    now = datetime.now(timezone.utc)

    server = NotificationServer(port=0, database_url=database, message_ttl_days=7)
    server.messages.add(
        notification(
            1, (now - timedelta(days=8)).isoformat().replace("+00:00", "Z"), "alerts"
        )
    )
    server.messages.add(
        notification(
            2, (now - timedelta(days=6)).isoformat().replace("+00:00", "Z"), "alerts"
        )
    )

    async with server:
        assert server._cleanup_task is not None
        await server._cleanup_task
        remaining = server.messages.list(50, 0)
        assert [item["payload"]["sequence"] for item in remaining] == [2]
