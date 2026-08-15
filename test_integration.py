import asyncio
import json
import urllib.error
import urllib.request

import fakeredis.aioredis
import pytest
from websockets.asyncio.client import connect

from app import NotificationServer


def websocket_url(server, suffix=""):
    return f"ws://127.0.0.1:{server.bound_port}{suffix}"


async def receive_json(connection):
    return json.loads(await asyncio.wait_for(connection.recv(), timeout=1))


async def send_message(connection, message_type, payload=None, channel=None):
    notification = {
        "type": message_type,
        "payload": payload or {},
        "timestamp": "2026-08-16T12:00:00Z",
    }
    if channel is not None:
        notification["channel"] = channel
    await connection.send(json.dumps(notification))
    return notification


async def get_json(server, path):
    def request():
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{server.bound_port}{path}", timeout=1
            ) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    return await asyncio.to_thread(request)


@pytest.mark.asyncio
async def test_redis_pubsub_delivers_between_server_instances(tmp_path):
    fake_server = fakeredis.FakeServer()
    first_redis = fakeredis.aioredis.FakeRedis(server=fake_server)
    second_redis = fakeredis.aioredis.FakeRedis(server=fake_server)
    database = str(tmp_path / "messages.db")

    async with NotificationServer(
        port=0, redis_client=first_redis, database_url=database
    ) as first_server, NotificationServer(
        port=0, redis_client=second_redis, database_url=database
    ) as second_server:
        async with connect(websocket_url(first_server)) as sender, connect(
            websocket_url(second_server)
        ) as recipient:
            await asyncio.gather(receive_json(sender), receive_json(recipient))
            await send_message(recipient, "subscribe", channel="alerts")

            # Reading shared state ensures the subscription command was processed.
            for _ in range(20):
                _, channels = await get_json(first_server, "/channels")
                if channels["channels"]:
                    break
                await asyncio.sleep(0.01)

            notification = await send_message(
                sender, "broadcast", {"text": "from another instance"}, "alerts"
            )
            assert await receive_json(recipient) == notification
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(sender.recv(), timeout=0.05)

            _, history = await get_json(second_server, "/messages")
            assert history["messages"] == [
                {
                    "id": 1,
                    "channel": "alerts",
                    "type": "broadcast",
                    "payload": {"text": "from another instance"},
                    "timestamp": "2026-08-16T12:00:00Z",
                }
            ]

    await first_redis.aclose()
    await second_redis.aclose()


@pytest.mark.asyncio
async def test_redis_subscription_state_is_restored_after_restart(tmp_path):
    fake_server = fakeredis.FakeServer()
    redis = fakeredis.aioredis.FakeRedis(server=fake_server)
    database = str(tmp_path / "messages.db")

    async with NotificationServer(
        port=0, redis_client=redis, database_url=database
    ) as server:
        async with connect(websocket_url(server)) as connection:
            welcome = await receive_json(connection)
            client_id = welcome["payload"]["client_id"]
            await send_message(connection, "subscribe", channel="durable")
            for _ in range(20):
                if await redis.sismember("notifications:channel:durable", client_id):
                    break
                await asyncio.sleep(0.01)

    async with NotificationServer(
        port=0, redis_client=redis, database_url=database
    ) as restarted:
        async with connect(
            websocket_url(restarted, f"?client_id={client_id}")
        ) as restored, connect(websocket_url(restarted)) as sender:
            restored_welcome, _ = await asyncio.gather(
                receive_json(restored), receive_json(sender)
            )
            assert restored_welcome["payload"]["client_id"] == client_id

            notification = await send_message(
                sender, "broadcast", {"text": "still subscribed"}, "durable"
            )
            assert await receive_json(restored) == notification

    await redis.aclose()


@pytest.mark.asyncio
async def test_sqlite_message_history_persists_and_paginates(tmp_path):
    database = str(tmp_path / "messages.db")
    async with NotificationServer(port=0, database_url=database) as server:
        async with connect(websocket_url(server)) as connection:
            welcome = await receive_json(connection)
            await send_message(connection, "broadcast", {"sequence": 1})
            await receive_json(connection)
            await send_message(
                connection,
                "direct",
                {"client_id": welcome["payload"]["client_id"], "sequence": 2},
            )
            await receive_json(connection)

    async with NotificationServer(port=0, database_url=database) as restarted:
        status, history = await get_json(restarted, "/messages?limit=1&offset=1")
        assert status == 200
        assert history["messages"] == [
            {
                "id": 2,
                "channel": None,
                "type": "direct",
                "payload": {
                    "client_id": welcome["payload"]["client_id"],
                    "sequence": 2,
                },
                "timestamp": "2026-08-16T12:00:00Z",
            }
        ]

        status, error = await get_json(restarted, "/messages?limit=-1")
        assert status == 400
        assert error == {"error": "limit must be a non-negative integer"}
