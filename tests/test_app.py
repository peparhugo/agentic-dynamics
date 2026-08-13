import asyncio
import json
from datetime import datetime
from xml.etree import ElementTree

import pytest
import pytest_asyncio
import websockets

from app import NotificationServer, SERVICE_NS, SOAP_ENV


@pytest_asyncio.fixture
async def server():
    instance = NotificationServer(websocket_port=0, soap_port=0)
    await instance.start()
    try:
        yield instance
    finally:
        await instance.stop()


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
