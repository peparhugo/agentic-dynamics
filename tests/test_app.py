import asyncio
import json

import pytest
import fakeredis.aioredis
from websockets.asyncio.client import connect

from app import NotificationServer


@pytest.fixture
async def server():
    application = NotificationServer(
        database_url="sqlite:///:memory:", redis_client=fakeredis.aioredis.FakeRedis(decode_responses=True)
    )
    await application.start()
    try:
        async with application.create_server(port=0) as running_server:
            port = running_server.sockets[0].getsockname()[1]
            yield application, f"ws://127.0.0.1:{port}"
    finally:
        await application.close()


async def receive_json(connection):
    return json.loads(await connection.recv())


async def get_json(host, port, path):
    reader, writer = await asyncio.open_connection(host, int(port))
    writer.write(f"GET {path} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n".encode())
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    status_line, body = response.split(b"\r\n\r\n", 1)
    assert b"200 OK" in status_line
    return json.loads(body)


async def test_connection_receives_address_derived_client_id(server):
    _, url = server
    async with connect(url) as client:
        welcome = await receive_json(client)
        host, port = client.local_address[:2]

    assert welcome["type"] == "system"
    assert welcome["payload"]["client_id"] == f"{host}:{port}"


async def test_broadcast_reaches_all_connected_clients(server):
    _, url = server
    async with connect(url) as first, connect(url) as second:
        await receive_json(first)
        await receive_json(second)
        await first.send(json.dumps({"type": "broadcast", "payload": {"text": "hello"}}))

        first_message, second_message = await receive_json(first), await receive_json(second)

    assert first_message["type"] == "broadcast"
    assert first_message["payload"] == {"text": "hello"}
    assert second_message["payload"] == {"text": "hello"}
    assert "timestamp" in first_message


async def test_disconnect_removes_client_from_health_count(server):
    application, url = server
    async with connect(url) as client:
        await receive_json(client)
        assert len(application.clients) == 1

    for _ in range(10):
        if len(application.clients) == 0:
            break
        await asyncio.sleep(0.01)

    assert len(application.clients) == 0


async def test_health_endpoint_returns_connected_client_count(server):
    _, url = server
    host_and_port = url.removeprefix("ws://")
    host, port = host_and_port.rsplit(":", 1)
    async with connect(url) as client:
        await receive_json(client)
        reader, writer = await asyncio.open_connection(host, int(port))
        writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
        await writer.drain()
        response = await reader.read()
        writer.close()
        await writer.wait_closed()

    status_line, body = response.split(b"\r\n\r\n", 1)
    assert b"200 OK" in status_line
    assert json.loads(body) == {"connected_clients": 1}


async def test_channel_messages_reach_only_subscribers(server):
    _, url = server
    async with connect(url) as first, connect(url) as second, connect(url) as third:
        await receive_json(first)
        await receive_json(second)
        await receive_json(third)
        await first.send(json.dumps({"type": "subscribe", "payload": {}, "channel": "alerts"}))
        await second.send(json.dumps({"type": "subscribe", "payload": {}, "channel": "alerts"}))
        await third.send(json.dumps({"type": "subscribe", "payload": {}, "channel": "chat"}))
        await asyncio.sleep(0.01)
        await first.send(
            json.dumps({"type": "broadcast", "payload": {"text": "warning"}, "channel": "alerts"})
        )

        first_message, second_message = await receive_json(first), await receive_json(second)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(third.recv(), timeout=0.05)

    assert first_message["channel"] == "alerts"
    assert second_message["payload"] == {"text": "warning"}


async def test_unsubscribe_removes_client_from_channel(server):
    application, url = server
    async with connect(url) as client:
        await receive_json(client)
        await client.send(json.dumps({"type": "subscribe", "payload": {}, "channel": "alerts"}))
        await client.send(json.dumps({"type": "unsubscribe", "payload": {}, "channel": "alerts"}))
        await asyncio.sleep(0)

        assert application.clients.channels() == []


async def test_channel_endpoints_report_active_subscribers(server):
    _, url = server
    host_and_port = url.removeprefix("ws://")
    host, port = host_and_port.rsplit(":", 1)
    async with connect(url) as first, connect(url) as second:
        first_welcome = await receive_json(first)
        second_welcome = await receive_json(second)
        await first.send(json.dumps({"type": "subscribe", "payload": {}, "channel": "alerts"}))
        await second.send(json.dumps({"type": "subscribe", "payload": {}, "channel": "alerts"}))
        await asyncio.sleep(0)

        channels = await get_json(host, port, "/channels")
        subscribers = await get_json(host, port, "/channels/alerts/subscribers")

    assert channels == {"channels": [{"name": "alerts", "subscriber_count": 2}]}
    assert subscribers == {
        "subscribers": sorted(
            [first_welcome["payload"]["client_id"], second_welcome["payload"]["client_id"]]
        )
    }


async def test_redis_pubsub_distributes_between_server_instances():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    first = NotificationServer(database_url="sqlite:///:memory:", redis_client=redis)
    second = NotificationServer(database_url="sqlite:///:memory:", redis_client=redis)
    await first.start()
    await second.start()
    try:
        async with first.create_server(port=0) as first_server, second.create_server(port=0) as second_server:
            first_port = first_server.sockets[0].getsockname()[1]
            second_port = second_server.sockets[0].getsockname()[1]
            async with connect(f"ws://127.0.0.1:{first_port}") as publisher, connect(
                f"ws://127.0.0.1:{second_port}"
            ) as subscriber:
                await receive_json(publisher)
                await receive_json(subscriber)
                await subscriber.send(json.dumps({"type": "subscribe", "payload": {}, "channel": "alerts"}))
                await asyncio.sleep(0.01)
                await publisher.send(
                    json.dumps({"type": "broadcast", "payload": {"text": "shared"}, "channel": "alerts"})
                )
                message = await receive_json(subscriber)
        assert message["payload"] == {"text": "shared"}
    finally:
        await first.close()
        await second.close()


async def test_messages_endpoint_returns_persisted_history(tmp_path):
    application = NotificationServer(
        database_url=f"sqlite:///{tmp_path / 'messages.db'}",
        redis_client=fakeredis.aioredis.FakeRedis(decode_responses=True),
    )
    await application.start()
    try:
        async with application.create_server(port=0) as running_server:
            port = running_server.sockets[0].getsockname()[1]
            async with connect(f"ws://127.0.0.1:{port}") as client:
                await receive_json(client)
                await client.send(json.dumps({"type": "broadcast", "payload": {"text": "first"}}))
                await receive_json(client)
                await client.send(json.dumps({"type": "broadcast", "payload": {"text": "second"}}))
                await receive_json(client)
            history = await get_json("127.0.0.1", port, "/messages?limit=1&offset=1")
        assert history["messages"][0]["payload"] == {"text": "first"}
        assert history["messages"][0]["channel"] is None
    finally:
        await application.close()


async def test_rate_limit_returns_error_without_dropping_connection():
    application = NotificationServer(
        database_url="sqlite:///:memory:",
        redis_client=fakeredis.aioredis.FakeRedis(decode_responses=True),
        rate_limit=1,
    )
    await application.start()
    try:
        async with application.create_server(port=0) as running_server:
            port = running_server.sockets[0].getsockname()[1]
            async with connect(f"ws://127.0.0.1:{port}") as client:
                await receive_json(client)
                await client.send(json.dumps({"type": "broadcast", "payload": {"text": "first"}}))
                assert (await receive_json(client))["payload"] == {"text": "first"}
                await client.send(json.dumps({"type": "broadcast", "payload": {"text": "second"}}))
                error = await receive_json(client)
        assert error == {"type": "system", "payload": {"error": "rate limit exceeded"}, "timestamp": error["timestamp"]}
    finally:
        await application.close()


async def test_history_returns_channel_messages_in_order_with_pagination(server):
    _, url = server
    host_and_port = url.removeprefix("ws://")
    host, port = host_and_port.rsplit(":", 1)
    async with connect(url) as client:
        await receive_json(client)
        await client.send(json.dumps({"type": "subscribe", "payload": {}, "channel": "alerts"}))
        for text in ("first", "second", "third"):
            await client.send(json.dumps({"type": "broadcast", "payload": {"text": text}, "channel": "alerts"}))
            await receive_json(client)

        history = await get_json(host, port, "/history?channel=alerts&since=1970-01-01T00:00:00Z&limit=2")
        second_page = await get_json(
            host, port, "/history?channel=alerts&since=1970-01-01T00:00:00Z&limit=2&offset=2"
        )

    assert [message["payload"]["text"] for message in history["messages"]] == ["first", "second"]
    assert history["has_more"] is True
    assert [message["payload"]["text"] for message in second_page["messages"]] == ["third"]
    assert second_page["has_more"] is False
