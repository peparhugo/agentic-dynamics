import asyncio
import json
from datetime import datetime
from xml.etree import ElementTree

import pytest
import pytest_asyncio
import websockets
import fakeredis.aioredis

from app import NotificationServer, SERVICE_NS, SOAP_ENV


@pytest_asyncio.fixture
async def server(tmp_path):
    broker = fakeredis.aioredis.FakeRedis(decode_responses=True)
    instance = NotificationServer(
        websocket_port=0,
        soap_port=0,
        redis_client=broker,
        database_url=str(tmp_path / "messages.db"),
    )
    await instance.start()
    try:
        yield instance
    finally:
        await instance.stop()
        await broker.aclose()


async def connect(server):
    socket = await websockets.connect(
        f"ws://127.0.0.1:{server.bound_websocket_port}"
    )
    greeting = json.loads(await socket.recv())
    return socket, greeting


def assert_message_shape(data, expected_type):
    assert set(data) == {"type", "payload", "timestamp"}
    assert data["type"] == expected_type
    assert isinstance(data["payload"], dict)
    datetime.fromisoformat(data["timestamp"])


async def soap_request(server, xml):
    reader, writer = await asyncio.open_connection(
        "127.0.0.1", server.bound_soap_port
    )
    body = xml.encode()
    writer.write(
        b"POST /soap HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"Content-Type: text/xml\r\n"
        + f"Content-Length: {len(body)}\r\n\r\n".encode()
        + body
    )
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    headers, response_body = response.split(b"\r\n\r\n", 1)
    return headers.decode(), response_body


async def get_request(server, path):
    reader, writer = await asyncio.open_connection(
        "127.0.0.1", server.bound_soap_port
    )
    writer.write(f"GET {path} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode())
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    headers, response_body = response.split(b"\r\n\r\n", 1)
    return headers.decode(), json.loads(response_body)


async def send_message(socket, message_type, payload=None, channel=None):
    outgoing = {
        "type": message_type,
        "payload": payload or {},
        "timestamp": "client-time",
    }
    if channel is not None:
        outgoing["channel"] = channel
    await socket.send(json.dumps(outgoing))


def envelope(operation="GetHealth"):
    return (
        f'<soap:Envelope xmlns:soap="{SOAP_ENV}" xmlns:ns="{SERVICE_NS}">'
        f"<soap:Body><ns:{operation}/></soap:Body></soap:Envelope>"
    )


@pytest.mark.asyncio
async def test_connection_assigns_unique_ids_and_disconnects_cleanly(server):
    first, first_greeting = await connect(server)
    second, second_greeting = await connect(server)
    assert_message_shape(first_greeting, "system")
    assert first_greeting["payload"]["event"] == "connected"
    assert first_greeting["payload"]["client_id"] != second_greeting["payload"]["client_id"]
    assert server.clients.count == 2

    await first.close()
    for _ in range(20):
        if server.clients.count == 1:
            break
        await asyncio.sleep(0.01)
    assert server.clients.count == 1
    await second.close()


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients(server):
    first, first_greeting = await connect(server)
    second, _ = await connect(server)
    incoming = {"type": "broadcast", "payload": {"text": "hello"}, "timestamp": "client-time"}
    await first.send(json.dumps(incoming))

    first_message, second_message = await asyncio.gather(first.recv(), second.recv())
    for raw in (first_message, second_message):
        received = json.loads(raw)
        assert_message_shape(received, "broadcast")
        assert received["payload"] == {
            "sender_id": first_greeting["payload"]["client_id"],
            "text": "hello",
        }
        assert received["timestamp"] != "client-time"
    await first.close()
    await second.close()


@pytest.mark.asyncio
async def test_direct_message_only_reaches_recipient(server):
    sender, sender_greeting = await connect(server)
    recipient, recipient_greeting = await connect(server)
    await sender.send(json.dumps({
        "type": "direct",
        "payload": {"client_id": recipient_greeting["payload"]["client_id"], "text": "private"},
        "timestamp": "now",
    }))
    received = json.loads(await recipient.recv())
    assert_message_shape(received, "direct")
    assert received["payload"] == {
        "sender_id": sender_greeting["payload"]["client_id"],
        "text": "private",
    }
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(sender.recv(), timeout=0.05)
    await sender.close()
    await recipient.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "outgoing",
    [
        "not json",
        json.dumps({"type": "unknown", "payload": {}, "timestamp": "now"}),
        json.dumps({"type": "broadcast", "payload": "wrong", "timestamp": "now"}),
        json.dumps({"type": "system", "payload": {}, "timestamp": "now"}),
    ],
)
async def test_invalid_or_reserved_messages_return_system_error(server, outgoing):
    socket, _ = await connect(server)
    await socket.send(outgoing)
    response = json.loads(await socket.recv())
    assert_message_shape(response, "system")
    assert response["payload"]["event"] == "error"
    await socket.close()


@pytest.mark.asyncio
async def test_missing_direct_recipient_returns_error(server):
    socket, _ = await connect(server)
    await socket.send(json.dumps({
        "type": "direct",
        "payload": {"client_id": "missing", "text": "hello"},
        "timestamp": "now",
    }))
    response = json.loads(await socket.recv())
    assert response["type"] == "system"
    assert response["payload"]["detail"] == "client not found"
    await socket.close()


@pytest.mark.asyncio
async def test_channel_broadcast_only_reaches_subscribers(server):
    sender, sender_greeting = await connect(server)
    subscriber, _ = await connect(server)
    outsider, _ = await connect(server)
    await send_message(sender, "subscribe", channel="alerts")
    await send_message(subscriber, "subscribe", channel="alerts")
    for socket in (sender, subscriber):
        acknowledgement = json.loads(await socket.recv())
        assert acknowledgement["payload"]["event"] == "subscribed"

    await send_message(sender, "broadcast", {"text": "warning"}, "alerts")
    for socket in (sender, subscriber):
        received = json.loads(await socket.recv())
        assert_message_shape({key: received[key] for key in ("type", "payload", "timestamp")}, "broadcast")
        assert received["channel"] == "alerts"
        assert received["payload"] == {
            "sender_id": sender_greeting["payload"]["client_id"],
            "text": "warning",
        }
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(outsider.recv(), timeout=0.05)
    await asyncio.gather(sender.close(), subscriber.close(), outsider.close())


@pytest.mark.asyncio
async def test_unsubscribe_and_multiple_channel_memberships(server):
    socket, _ = await connect(server)
    for channel in ("alerts", "chat"):
        await send_message(socket, "subscribe", channel=channel)
        await socket.recv()

    headers, body = await get_request(server, "/channels")
    assert headers.startswith("HTTP/1.1 200 OK")
    assert body == {"channels": [
        {"name": "alerts", "subscriber_count": 1},
        {"name": "chat", "subscriber_count": 1},
    ]}

    await send_message(socket, "unsubscribe", channel="alerts")
    acknowledgement = json.loads(await socket.recv())
    assert acknowledgement["payload"]["event"] == "unsubscribed"
    _, body = await get_request(server, "/channels")
    assert body == {"channels": [{"name": "chat", "subscriber_count": 1}]}
    await socket.close()


@pytest.mark.asyncio
async def test_channel_subscribers_endpoint_and_disconnect_cleanup(server):
    first, first_greeting = await connect(server)
    second, second_greeting = await connect(server)
    for socket in (first, second):
        await send_message(socket, "subscribe", channel="system status")
        await socket.recv()

    headers, body = await get_request(server, "/channels/system%20status/subscribers")
    assert headers.startswith("HTTP/1.1 200 OK")
    assert body["channel"] == "system status"
    assert body["subscribers"] == sorted([
        first_greeting["payload"]["client_id"],
        second_greeting["payload"]["client_id"],
    ])

    await first.close()
    for _ in range(20):
        _, body = await get_request(server, "/channels/system%20status/subscribers")
        if len(body["subscribers"]) == 1:
            break
        await asyncio.sleep(0.01)
    assert body["subscribers"] == [second_greeting["payload"]["client_id"]]
    await second.close()


@pytest.mark.asyncio
async def test_messages_without_channel_still_broadcast_to_all(server):
    first, _ = await connect(server)
    second, _ = await connect(server)
    await send_message(first, "subscribe", channel="alerts")
    await first.recv()
    await send_message(second, "broadcast", {"text": "global"})
    first_received, second_received = await asyncio.gather(first.recv(), second.recv())
    assert json.loads(first_received)["payload"]["text"] == "global"
    assert json.loads(second_received)["payload"]["text"] == "global"
    await asyncio.gather(first.close(), second.close())


@pytest.mark.asyncio
async def test_subscription_requires_valid_channel(server):
    socket, _ = await connect(server)
    await send_message(socket, "subscribe")
    response = json.loads(await socket.recv())
    assert response["payload"]["detail"] == "subscribe requires channel"

    await socket.send(json.dumps({
        "type": "subscribe",
        "payload": {},
        "timestamp": "now",
        "channel": "",
    }))
    response = json.loads(await socket.recv())
    assert response["payload"]["detail"] == "channel must be a non-empty string"
    await socket.close()


@pytest.mark.asyncio
async def test_soap_health_reports_connected_client_count(server):
    first, _ = await connect(server)
    second, _ = await connect(server)
    headers, body = await soap_request(server, envelope())
    assert headers.startswith("HTTP/1.1 200 OK")
    root = ElementTree.fromstring(body)
    count = root.find(
        f".//{{{SERVICE_NS}}}connectedClientCount"
    )
    assert count is not None and count.text == "2"
    await first.close()
    await second.close()


@pytest.mark.asyncio
async def test_soap_rejects_unsupported_operation(server):
    headers, body = await soap_request(server, envelope("DeleteEverything"))
    assert headers.startswith("HTTP/1.1 400 Bad Request")
    root = ElementTree.fromstring(body)
    fault = root.find(f".//{{{SOAP_ENV}}}Fault")
    assert fault is not None
    assert "unsupported SOAP operation" in body.decode()


@pytest.mark.asyncio
async def test_redis_pubsub_delivers_between_server_instances(tmp_path):
    fake_server = fakeredis.FakeServer()
    first_broker = fakeredis.aioredis.FakeRedis(
        server=fake_server, decode_responses=True
    )
    second_broker = fakeredis.aioredis.FakeRedis(
        server=fake_server, decode_responses=True
    )
    first_server = NotificationServer(
        websocket_port=0,
        soap_port=0,
        redis_client=first_broker,
        database_url=str(tmp_path / "first.db"),
    )
    second_server = NotificationServer(
        websocket_port=0,
        soap_port=0,
        redis_client=second_broker,
        database_url=str(tmp_path / "second.db"),
    )
    await asyncio.gather(first_server.start(), second_server.start())
    sender, greeting = await connect(first_server)
    recipient, _ = await connect(second_server)
    try:
        await send_message(sender, "broadcast", {"text": "distributed"})
        sender_message, recipient_message = await asyncio.gather(
            sender.recv(), recipient.recv()
        )
        for raw in (sender_message, recipient_message):
            received = json.loads(raw)
            assert received["payload"] == {
                "sender_id": greeting["payload"]["client_id"],
                "text": "distributed",
            }
    finally:
        await asyncio.gather(sender.close(), recipient.close())
        await asyncio.gather(first_server.stop(), second_server.stop())
        await asyncio.gather(first_broker.aclose(), second_broker.aclose())


@pytest.mark.asyncio
async def test_message_history_persists_across_restart(tmp_path):
    database = str(tmp_path / "history.db")
    fake_server = fakeredis.FakeServer()

    async def start_server():
        broker = fakeredis.aioredis.FakeRedis(
            server=fake_server, decode_responses=True
        )
        instance = NotificationServer(
            websocket_port=0,
            soap_port=0,
            redis_client=broker,
            database_url=database,
        )
        await instance.start()
        return instance, broker

    first, first_broker = await start_server()
    socket, _ = await connect(first)
    await send_message(socket, "subscribe", channel="history")
    await socket.recv()
    await send_message(socket, "broadcast", {"sequence": 1}, "history")
    await send_message(socket, "broadcast", {"sequence": 2}, "history")
    await socket.recv()
    await socket.recv()
    await socket.close()
    await first.stop()
    await first_broker.aclose()

    second, second_broker = await start_server()
    try:
        headers, body = await get_request(second, "/messages?limit=1&offset=1")
        assert headers.startswith("HTTP/1.1 200 OK")
        assert len(body["messages"]) == 1
        stored = body["messages"][0]
        assert set(stored) == {"id", "channel", "type", "payload", "timestamp"}
        assert stored["channel"] == "history"
        assert stored["type"] == "broadcast"
        assert stored["payload"]["sequence"] == 1
    finally:
        await second.stop()
        await second_broker.aclose()
