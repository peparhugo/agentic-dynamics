import asyncio
import json

import pytest
from websockets.legacy.client import connect
from websockets.legacy.server import serve

from app import NotificationServer


@pytest.fixture
async def notification_server():
    server = NotificationServer()
    async with serve(server.handler, "127.0.0.1", 0, process_request=server.health_response) as listener:
        port = listener.sockets[0].getsockname()[1]
        yield server, f"ws://127.0.0.1:{port}"


async def receive_json(client):
    return json.loads(await client.recv())


async def wait_for_client_count(server, expected_count):
    for _ in range(20):
        if server.client_count == expected_count:
            return
        await asyncio.sleep(0.01)
    assert server.client_count == expected_count


async def wait_for_channel_subscriber_count(server, channel, expected_count):
    for _ in range(20):
        if server.channels.get(channel) == expected_count:
            return
        await asyncio.sleep(0.01)
    assert server.channels.get(channel) == expected_count


async def test_connect_assigns_unique_client_ids_and_removes_disconnect(notification_server):
    server, uri = notification_server
    async with connect(uri) as first, connect(uri) as second:
        first_notice, second_notice = await asyncio.gather(receive_json(first), receive_json(second))
        assert first_notice["type"] == second_notice["type"] == "system"
        assert first_notice["payload"]["client_id"] != second_notice["payload"]["client_id"]
        assert server.client_count == 2

    await wait_for_client_count(server, 0)


async def test_broadcast_reaches_all_clients_with_standard_format(notification_server):
    _server, uri = notification_server
    async with connect(uri) as first, connect(uri) as second:
        await asyncio.gather(receive_json(first), receive_json(second))
        await first.send(json.dumps({"type": "broadcast", "payload": {"text": "hello"}}))
        messages = await asyncio.gather(receive_json(first), receive_json(second))

    assert all(message["type"] == "broadcast" for message in messages)
    assert all(message["payload"] == {"text": "hello"} for message in messages)
    assert all("timestamp" in message for message in messages)


async def test_direct_message_reaches_only_its_recipient(notification_server):
    _server, uri = notification_server
    async with connect(uri) as first, connect(uri) as second:
        first_notice, second_notice = await asyncio.gather(receive_json(first), receive_json(second))
        recipient_id = second_notice["payload"]["client_id"]
        await first.send(json.dumps({"type": "direct", "payload": {"client_id": recipient_id, "text": "private"}}))
        direct_message = await receive_json(second)
        assert direct_message["type"] == "direct"
        assert direct_message["payload"]["text"] == "private"
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(first.recv(), timeout=0.05)


async def test_health_endpoint_returns_connected_client_count(notification_server):
    _server, uri = notification_server
    host_and_port = uri.removeprefix("ws://")
    reader, writer = await asyncio.open_connection(*host_and_port.rsplit(":", 1))
    writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()

    assert b"200 OK" in response
    assert response.endswith(b'{"connected_clients": 0}')


async def get_json(uri, path):
    host, port = uri.removeprefix("ws://").rsplit(":", 1)
    reader, writer = await asyncio.open_connection(host, port)
    writer.write(f"GET {path} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n".encode())
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    return response


async def test_channel_messages_reach_only_subscribers(notification_server):
    _server, uri = notification_server
    async with connect(uri) as first, connect(uri) as second, connect(uri) as third:
        await asyncio.gather(receive_json(first), receive_json(second), receive_json(third))
        await first.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await second.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await third.send(json.dumps({"type": "subscribe", "payload": {"channel": "chat"}}))
        await wait_for_channel_subscriber_count(_server, "alerts", 2)
        await first.send(json.dumps({"type": "broadcast", "channel": "alerts", "payload": {"text": "warning"}}))
        messages = await asyncio.gather(receive_json(first), receive_json(second))

        assert all(message["channel"] == "alerts" for message in messages)
        assert all(message["payload"] == {"text": "warning"} for message in messages)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(third.recv(), timeout=0.05)


async def test_unsubscribe_stops_channel_delivery_and_channels_endpoints(notification_server):
    _server, uri = notification_server
    async with connect(uri) as first, connect(uri) as second:
        first_notice, second_notice = await asyncio.gather(receive_json(first), receive_json(second))
        first_id = first_notice["payload"]["client_id"]
        second_id = second_notice["payload"]["client_id"]
        await first.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await second.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await wait_for_channel_subscriber_count(_server, "alerts", 2)

        channels = await get_json(uri, "/channels")
        subscribers = await get_json(uri, "/channels/alerts/subscribers")
        assert channels.endswith(b'{"channels": {"alerts": 2}}')
        assert set(json.loads(subscribers.split(b"\r\n\r\n", 1)[1])["subscribers"]) == {first_id, second_id}

        await second.send(json.dumps({"type": "unsubscribe", "payload": {"channel": "alerts"}}))
        await wait_for_channel_subscriber_count(_server, "alerts", 1)
        await first.send(json.dumps({"type": "broadcast", "channel": "alerts", "payload": {"text": "warning"}}))
        assert (await receive_json(first))["payload"]["text"] == "warning"
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(second.recv(), timeout=0.05)
