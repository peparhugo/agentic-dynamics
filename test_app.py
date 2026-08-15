import asyncio
import json
import os
import urllib.request
from urllib.parse import urlencode

import pytest
import websockets

from app import NotificationServer


async def health(port: int) -> dict:
    response = await asyncio.to_thread(urllib.request.urlopen, f"http://127.0.0.1:{port}/health")
    return json.loads(response.read())


async def messages(port: int, limit: int = 50, offset: int = 0) -> dict:
    response = await asyncio.to_thread(
        urllib.request.urlopen,
        f"http://127.0.0.1:{port}/messages?limit={limit}&offset={offset}",
    )
    return json.loads(response.read())


async def history(port: int, **params: str | int) -> dict:
    query = urlencode(params)
    response = await asyncio.to_thread(
        urllib.request.urlopen, f"http://127.0.0.1:{port}/history?{query}"
    )
    return json.loads(response.read())


@pytest.mark.asyncio
async def test_health_reports_connected_clients():
    async with NotificationServer(port=0) as server:
        assert (await health(server.port))["connected_clients"] == 0
        async with websockets.connect(f"ws://127.0.0.1:{server.port}"):
            assert (await health(server.port))["connected_clients"] == 1


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients():
    async with NotificationServer(port=0) as server:
        async with (
            websockets.connect(f"ws://127.0.0.1:{server.port}") as first,
            websockets.connect(f"ws://127.0.0.1:{server.port}") as second,
        ):
            await first.send(json.dumps({"type": "broadcast", "payload": {"text": "hello"}}))
            for client in (first, second):
                message = json.loads(await client.recv())
                assert message["type"] == "broadcast"
                assert message["payload"] == {"text": "hello"}
                assert isinstance(message["timestamp"], str)


@pytest.mark.asyncio
async def test_direct_message_reaches_only_target():
    async with NotificationServer(port=0) as server:
        async with (
            websockets.connect(f"ws://127.0.0.1:{server.port}") as sender,
            websockets.connect(f"ws://127.0.0.1:{server.port}") as target,
        ):
            sender_id, target_id = list(server.clients)
            await sender.send(json.dumps({"type": "direct", "payload": {"client_id": target_id, "text": "private"}}))
            message = json.loads(await target.recv())
            assert message["payload"]["text"] == "private"
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(sender.recv(), timeout=0.05)
            assert sender_id != target_id


@pytest.mark.asyncio
async def test_disconnect_removes_client():
    async with NotificationServer(port=0) as server:
        client = await websockets.connect(f"ws://127.0.0.1:{server.port}")
        assert server.client_count == 1
        await client.close()
        for _ in range(20):
            if server.client_count == 0:
                break
            await asyncio.sleep(0.01)
        assert server.client_count == 0


@pytest.mark.asyncio
async def test_messages_are_persisted_and_paginated(tmp_path):
    async with NotificationServer(port=0, database_url=str(tmp_path / "messages.db")) as server:
        async with websockets.connect(f"ws://127.0.0.1:{server.port}") as client:
            await client.send(json.dumps({"type": "subscribe", "channel": "updates"}))
            await client.send(json.dumps({"type": "broadcast", "channel": "updates", "payload": {"id": 1}}))
            await client.recv()
        result = await messages(server.port, limit=1)
        assert len(result["messages"]) == 1
        assert result["messages"][0]["channel"] == "updates"
        assert result["messages"][0]["payload"] == {"id": 1}
        assert await messages(server.port, offset=1) == {"messages": []}


@pytest.mark.asyncio
async def test_history_filters_by_channel_and_supports_since_and_has_more(tmp_path):
    async with NotificationServer(port=0, database_url=str(tmp_path / "messages.db")) as server:
        async with websockets.connect(f"ws://127.0.0.1:{server.port}") as client:
            await client.send(json.dumps({"type": "subscribe", "channel": "one"}))
            for channel, message_id in (("one", 1), ("two", 2), ("one", 3)):
                await client.send(
                    json.dumps(
                        {"type": "broadcast", "channel": channel, "payload": {"id": message_id}}
                    )
                )
                if channel == "one":
                    await client.recv()

        first_page = await history(server.port, channel="one", limit=1)
        assert [message["payload"]["id"] for message in first_page["messages"]] == [1]
        assert first_page["has_more"] is True

        second_page = await history(
            server.port, channel="one", since=first_page["messages"][0]["timestamp"]
        )
        assert [message["payload"]["id"] for message in second_page["messages"]] == [3]
        assert second_page["has_more"] is False


@pytest.mark.asyncio
async def test_rate_limit_returns_error_without_dropping_message(tmp_path):
    async with NotificationServer(
        port=0, database_url=str(tmp_path / "messages.db"), rate_limit=2
    ) as server:
        async with websockets.connect(f"ws://127.0.0.1:{server.port}") as client:
            for message_id in (1, 2):
                await client.send(json.dumps({"type": "broadcast", "payload": {"id": message_id}}))
                assert json.loads(await client.recv())["payload"]["id"] == message_id

            await client.send(json.dumps({"type": "broadcast", "payload": {"id": 3}}))
            error = json.loads(await client.recv())
            assert error == {
                "type": "system",
                "payload": {"error": "rate limit exceeded"},
                "timestamp": error["timestamp"],
            }


@pytest.mark.asyncio
async def test_redis_pubsub_delivers_between_server_instances(tmp_path):
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        pytest.skip("REDIS_URL is required for Redis integration tests")
    first = NotificationServer(port=0, redis_url=redis_url, database_url=str(tmp_path / "first.db"))
    second = NotificationServer(port=0, redis_url=redis_url, database_url=str(tmp_path / "second.db"))
    try:
        await first.start()
        await second.start()
        async with websockets.connect(f"ws://127.0.0.1:{second.port}") as receiver:
            async with websockets.connect(f"ws://127.0.0.1:{first.port}") as sender:
                await sender.send(json.dumps({"type": "broadcast", "payload": {"text": "redis"}}))
                assert json.loads(await receiver.recv())["payload"] == {"text": "redis"}
    finally:
        await first.stop()
        await second.stop()
