import asyncio
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from xml.etree import ElementTree as ET

import pytest
import pytest_asyncio
import websockets

from app import MemoryBroker, NotificationServer, SOAP_NS


@pytest_asyncio.fixture
async def notification_server():
    app = NotificationServer()
    websocket_server = await websockets.serve(app.websocket_handler, "127.0.0.1", 0)
    soap_server = await asyncio.start_server(app.soap_handler, "127.0.0.1", 0)
    websocket_port = websocket_server.sockets[0].getsockname()[1]
    soap_port = soap_server.sockets[0].getsockname()[1]
    yield app, websocket_port, soap_port
    websocket_server.close()
    await websocket_server.wait_closed()
    soap_server.close()
    await soap_server.wait_closed()
    await app.close()


async def connect(port):
    socket = await websockets.connect(f"ws://127.0.0.1:{port}")
    welcome = json.loads(await socket.recv())
    return socket, welcome["payload"]["client_id"]


async def get_json(port, path):
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(f"GET {path} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode())
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    status, body = response.split(b"\r\n\r\n", 1)
    return status.split(b"\r\n", 1)[0], json.loads(body)


@pytest.mark.asyncio
async def test_connect_assigns_unique_client_ids(notification_server):
    app, websocket_port, _ = notification_server
    first, first_id = await connect(websocket_port)
    second, second_id = await connect(websocket_port)
    assert first_id != second_id
    assert await app.client_count() == 2
    await first.close()
    await second.close()


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients(notification_server):
    _, websocket_port, _ = notification_server
    sender, _ = await connect(websocket_port)
    recipient, _ = await connect(websocket_port)
    await sender.send(json.dumps({"type": "broadcast", "payload": {"text": "hello"}}))
    messages = [json.loads(await sender.recv()), json.loads(await recipient.recv())]
    assert all(message["type"] == "broadcast" for message in messages)
    assert all(message["payload"] == {"text": "hello"} for message in messages)
    assert all("timestamp" in message for message in messages)
    await sender.close()
    await recipient.close()


@pytest.mark.asyncio
async def test_direct_message_reaches_only_recipient(notification_server):
    _, websocket_port, _ = notification_server
    sender, _ = await connect(websocket_port)
    recipient, recipient_id = await connect(websocket_port)
    await sender.send(json.dumps({"type": "direct", "payload": {"client_id": recipient_id, "message": {"text": "private"}}}))
    message = json.loads(await recipient.recv())
    assert message["type"] == "direct"
    assert message["payload"] == {"text": "private"}
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(sender.recv(), timeout=0.05)
    await sender.close()
    await recipient.close()


@pytest.mark.asyncio
async def test_disconnect_removes_client(notification_server):
    app, websocket_port, _ = notification_server
    socket, _ = await connect(websocket_port)
    await socket.close()
    for _ in range(20):
        if await app.client_count() == 0:
            break
        await asyncio.sleep(0.01)
    assert await app.client_count() == 0


@pytest.mark.asyncio
async def test_channel_broadcast_reaches_only_subscribers(notification_server):
    _, websocket_port, soap_port = notification_server
    first, _ = await connect(websocket_port)
    second, _ = await connect(websocket_port)
    other, _ = await connect(websocket_port)
    await first.send(json.dumps({"type": "subscribe", "channel": "alerts", "payload": {}}))
    await second.send(json.dumps({"type": "subscribe", "channel": "alerts", "payload": {}}))
    await other.send(json.dumps({"type": "subscribe", "channel": "chat", "payload": {}}))
    for _ in range(20):
        _, channels = await get_json(soap_port, "/channels")
        if channels == {"alerts": 2, "chat": 1}:
            break
        await asyncio.sleep(0.01)
    await first.send(json.dumps({"type": "broadcast", "channel": "alerts", "payload": {"text": "warning"}}))
    messages = [json.loads(await first.recv()), json.loads(await second.recv())]
    assert all(message["payload"] == {"text": "warning"} for message in messages)
    assert all(message["channel"] == "alerts" for message in messages)
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(other.recv(), timeout=0.05)
    await first.close()
    await second.close()
    await other.close()


@pytest.mark.asyncio
async def test_unsubscribe_and_channel_rest_endpoints(notification_server):
    _, websocket_port, soap_port = notification_server
    first, first_id = await connect(websocket_port)
    second, second_id = await connect(websocket_port)
    await first.send(json.dumps({"type": "subscribe", "channel": "alerts", "payload": {}}))
    await first.send(json.dumps({"type": "subscribe", "channel": "chat", "payload": {}}))
    await second.send(json.dumps({"type": "subscribe", "channel": "alerts", "payload": {}}))
    for _ in range(20):
        status, channels = await get_json(soap_port, "/channels")
        if channels == {"alerts": 2, "chat": 1}:
            break
        await asyncio.sleep(0.01)
    assert status == b"HTTP/1.1 200 OK"
    assert channels == {"alerts": 2, "chat": 1}
    status, subscribers = await get_json(soap_port, "/channels/alerts/subscribers")
    assert status == b"HTTP/1.1 200 OK"
    assert subscribers == sorted([first_id, second_id])
    await first.send(json.dumps({"type": "unsubscribe", "channel": "alerts", "payload": {}}))
    await first.send(json.dumps({"type": "broadcast", "channel": "alerts", "payload": {"text": "one"}}))
    assert json.loads(await second.recv())["payload"] == {"text": "one"}
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(first.recv(), timeout=0.05)
    await first.close()
    await second.close()


@pytest.mark.asyncio
async def test_soap_health_returns_client_count(notification_server):
    _, websocket_port, soap_port = notification_server
    socket, _ = await connect(websocket_port)
    reader, writer = await asyncio.open_connection("127.0.0.1", soap_port)
    body = f'<soap:Envelope xmlns:soap="{SOAP_NS}"><soap:Body><Health /></soap:Body></soap:Envelope>'.encode()
    writer.write(b"POST / HTTP/1.1\r\nHost: localhost\r\nContent-Type: text/xml\r\nContent-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body)
    await writer.drain()
    response = await reader.read()
    response_body = response.split(b"\r\n\r\n", 1)[1]
    root = ET.fromstring(response_body)
    assert root.find(".//{*}connectedClientCount").text == "1"
    writer.close()
    await writer.wait_closed()
    await socket.close()


@pytest.mark.asyncio
async def test_messages_rest_endpoint_persists_message_history(notification_server):
    _, websocket_port, soap_port = notification_server
    socket, _ = await connect(websocket_port)
    await socket.send(json.dumps({"type": "broadcast", "payload": {"text": "saved"}}))
    assert json.loads(await socket.recv())["payload"] == {"text": "saved"}
    status, messages = await get_json(soap_port, "/messages?limit=50&offset=0")
    assert status == b"HTTP/1.1 200 OK"
    assert messages[0]["channel"] is None
    assert messages[0]["type"] == "broadcast"
    assert messages[0]["payload"] == {"text": "saved"}
    assert "timestamp" in messages[0]
    await socket.close()


@pytest.mark.asyncio
async def test_rate_limit_returns_error_without_dropping_connection():
    app = NotificationServer(rate_limit=1)
    websocket_server = await websockets.serve(app.websocket_handler, "127.0.0.1", 0)
    try:
        port = websocket_server.sockets[0].getsockname()[1]
        socket, _ = await connect(port)
        await socket.send(json.dumps({"type": "broadcast", "payload": {"text": "first"}}))
        assert json.loads(await socket.recv())["payload"] == {"text": "first"}
        await socket.send(json.dumps({"type": "broadcast", "payload": {"text": "second"}}))
        error = json.loads(await socket.recv())
        assert error["type"] == "system"
        assert error["payload"] == {"event": "error", "message": "rate limit exceeded"}
        await socket.close()
    finally:
        websocket_server.close()
        await websocket_server.wait_closed()
        await app.close()


@pytest.mark.asyncio
async def test_history_endpoint_filters_orders_and_paginates(notification_server):
    app, _, soap_port = notification_server
    now = datetime.now(timezone.utc)
    await app.store.add("alerts", "broadcast", {"text": "old"}, (now - timedelta(minutes=2)).isoformat())
    await app.store.add("alerts", "broadcast", {"text": "first"}, (now - timedelta(minutes=1)).isoformat())
    await app.store.add("alerts", "broadcast", {"text": "second"}, now.isoformat())
    await app.store.add("chat", "broadcast", {"text": "other"}, now.isoformat())
    since = (now - timedelta(minutes=1, seconds=1)).isoformat()
    status, history = await get_json(soap_port, f"/history?channel=alerts&since={quote(since)}&limit=2")
    assert status == b"HTTP/1.1 200 OK"
    assert [message["payload"] for message in history["messages"]] == [{"text": "first"}, {"text": "second"}]
    assert [message["timestamp"] for message in history["messages"]] == sorted(message["timestamp"] for message in history["messages"])
    assert history["has_more"] is False
    status, history = await get_json(soap_port, "/history?channel=alerts&limit=2")
    assert status == b"HTTP/1.1 200 OK"
    assert [message["payload"] for message in history["messages"]] == [{"text": "old"}, {"text": "first"}]
    assert history["has_more"] is True


@pytest.mark.asyncio
async def test_shared_broker_delivers_messages_between_server_instances():
    broker = MemoryBroker()
    first_app = NotificationServer(broker=broker)
    second_app = NotificationServer(broker=broker)
    first_server = await websockets.serve(first_app.websocket_handler, "127.0.0.1", 0)
    second_server = await websockets.serve(second_app.websocket_handler, "127.0.0.1", 0)
    try:
        first_port = first_server.sockets[0].getsockname()[1]
        second_port = second_server.sockets[0].getsockname()[1]
        sender, _ = await connect(first_port)
        recipient, _ = await connect(second_port)
        await sender.send(json.dumps({"type": "broadcast", "payload": {"text": "cross-instance"}}))
        assert json.loads(await sender.recv())["payload"] == {"text": "cross-instance"}
        assert json.loads(await recipient.recv())["payload"] == {"text": "cross-instance"}
        await sender.close()
        await recipient.close()
    finally:
        first_server.close()
        second_server.close()
        await first_server.wait_closed()
        await second_server.wait_closed()
        await first_app.close()
        await second_app.close()
