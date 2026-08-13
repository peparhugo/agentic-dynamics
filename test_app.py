import asyncio
import json
from datetime import datetime
from xml.etree import ElementTree

import pytest
from websockets.asyncio.client import connect

from app import NotificationServer, SOAP_ENV, SERVICE_NS


@pytest.fixture
async def server():
    instance = NotificationServer(websocket_port=0, soap_port=0)
    await instance.start()
    try:
        yield instance
    finally:
        await instance.stop()


async def receive_json(websocket):
    result = json.loads(await asyncio.wait_for(websocket.recv(), timeout=1))
    assert set(result) == {"type", "payload", "timestamp"}
    datetime.fromisoformat(result["timestamp"].replace("Z", "+00:00"))
    return result


async def soap_request(server, body, method="POST", path="/health"):
    reader, writer = await asyncio.open_connection(server.host, server.soap_port)
    encoded = body.encode()
    request = (
        f"{method} {path} HTTP/1.1\r\n"
        f"Host: {server.host}\r\n"
        "Content-Type: text/xml; charset=utf-8\r\n"
        f"Content-Length: {len(encoded)}\r\n\r\n"
    ).encode() + encoded
    writer.write(request)
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    headers, response_body = response.split(b"\r\n\r\n", 1)
    return headers, response_body


def health_envelope():
    return f"""<?xml version="1.0"?>
    <soap:Envelope xmlns:soap="{SOAP_ENV}" xmlns:ns="{SERVICE_NS}">
      <soap:Body><ns:Health/></soap:Body>
    </soap:Envelope>"""


@pytest.mark.asyncio
async def test_connect_assigns_unique_ids_and_disconnects_cleanly(server):
    uri = f"ws://{server.host}:{server.websocket_port}"
    first = await connect(uri)
    second = await connect(uri)
    first_message = await receive_json(first)
    second_message = await receive_json(second)

    assert first_message["type"] == "system"
    assert first_message["payload"]["event"] == "connected"
    assert first_message["payload"]["client_id"] != second_message["payload"]["client_id"]
    assert server.clients.count == 2

    await first.close()
    await second.close()
    await asyncio.sleep(0)
    assert server.clients.count == 0


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients(server):
    uri = f"ws://{server.host}:{server.websocket_port}"
    async with connect(uri) as sender, connect(uri) as recipient:
        sender_id = (await receive_json(sender))["payload"]["client_id"]
        await receive_json(recipient)
        await sender.send(json.dumps({
            "type": "broadcast",
            "payload": {"text": "maintenance"},
            "timestamp": "ignored by server",
        }))

        sender_message, recipient_message = await asyncio.gather(
            receive_json(sender), receive_json(recipient)
        )
        assert sender_message == recipient_message
        assert sender_message["type"] == "broadcast"
        assert sender_message["payload"] == {
            "text": "maintenance",
            "sender_id": sender_id,
        }


@pytest.mark.asyncio
async def test_direct_reaches_only_target(server):
    uri = f"ws://{server.host}:{server.websocket_port}"
    async with connect(uri) as sender, connect(uri) as target:
        sender_id = (await receive_json(sender))["payload"]["client_id"]
        target_id = (await receive_json(target))["payload"]["client_id"]
        await sender.send(json.dumps({
            "type": "direct",
            "payload": {"client_id": target_id, "text": "private"},
            "timestamp": "2020-01-01T00:00:00Z",
        }))

        direct = await receive_json(target)
        assert direct["type"] == "direct"
        assert direct["payload"]["sender_id"] == sender_id
        assert direct["payload"]["text"] == "private"
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(sender.recv(), timeout=0.05)


@pytest.mark.asyncio
async def test_invalid_and_client_system_messages_return_system_errors(server):
    uri = f"ws://{server.host}:{server.websocket_port}"
    async with connect(uri) as websocket:
        await receive_json(websocket)
        await websocket.send("not json")
        invalid = await receive_json(websocket)
        assert invalid["payload"]["event"] == "error"

        await websocket.send(json.dumps({"type": "system", "payload": {}}))
        reserved = await receive_json(websocket)
        assert reserved["type"] == "system"
        assert "server-only" in reserved["payload"]["detail"]


@pytest.mark.asyncio
async def test_soap_health_reports_connected_count(server):
    uri = f"ws://{server.host}:{server.websocket_port}"
    async with connect(uri) as first, connect(uri) as second:
        await receive_json(first)
        await receive_json(second)
        headers, body = await soap_request(server, health_envelope())

    assert headers.startswith(b"HTTP/1.1 200 OK")
    assert b"text/xml" in headers
    root = ElementTree.fromstring(body)
    count = root.find(f".//{{{SERVICE_NS}}}connectedClientCount")
    assert count is not None
    assert count.text == "2"


@pytest.mark.asyncio
async def test_health_is_soap_only_and_faults_on_wrong_operation(server):
    get_headers, _ = await soap_request(server, "", method="GET")
    assert get_headers.startswith(b"HTTP/1.1 404 Not Found")

    wrong = health_envelope().replace("Health", "Unknown")
    headers, body = await soap_request(server, wrong)
    assert headers.startswith(b"HTTP/1.1 200 OK")
    root = ElementTree.fromstring(body)
    assert root.find(f".//{{{SOAP_ENV}}}Fault") is not None
