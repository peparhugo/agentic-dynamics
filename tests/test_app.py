import asyncio
import json

import pytest
import pytest_asyncio
import websockets

from app import NotificationServer


async def get_health(server):
    reader, writer = await asyncio.open_connection(server.host, server.http_port)
    writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n")
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    return json.loads(response.split(b"\r\n\r\n", 1)[1])


async def get_json(server, path):
    reader, writer = await asyncio.open_connection(server.host, server.http_port)
    writer.write(f"GET {path} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode())
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    return json.loads(response.split(b"\r\n\r\n", 1)[1])


@pytest_asyncio.fixture
async def server():
    instance = NotificationServer(websocket_port=0, http_port=0)
    await instance.start()
    yield instance
    await instance.stop()


@pytest.mark.asyncio
async def test_ids_broadcast_disconnect_and_health(server):
    uri = f"ws://{server.host}:{server.websocket_port}"
    first = await websockets.connect(uri)
    second = await websockets.connect(uri)
    first_welcome = json.loads(await first.recv())
    second_welcome = json.loads(await second.recv())
    assert first_welcome["payload"]["client_id"] != second_welcome["payload"]["client_id"]
    assert (await get_health(server))["connected_clients"] == 2

    await first.send(json.dumps({"type": "broadcast", "payload": {"text": "hello"}}))
    assert json.loads(await first.recv())["payload"] == {"text": "hello"}
    assert json.loads(await second.recv())["payload"] == {"text": "hello"}

    await first.close()
    await asyncio.sleep(0)
    assert (await get_health(server))["connected_clients"] == 1
    await second.close()


@pytest.mark.asyncio
async def test_direct_and_system_messages(server):
    uri = f"ws://{server.host}:{server.websocket_port}"
    first, second = await websockets.connect(uri), await websockets.connect(uri)
    first_id = json.loads(await first.recv())["payload"]["client_id"]
    await second.recv()
    await first.send(json.dumps({"type": "direct", "payload": {"client_id": first_id, "value": 1}}))
    assert json.loads(await first.recv())["payload"]["value"] == 1
    await first.send(json.dumps({"type": "system", "payload": {"event": "maintenance"}}))
    assert json.loads(await second.recv())["type"] == "system"
    await first.close()
    await second.close()


@pytest.mark.asyncio
async def test_channel_subscriptions_route_messages_and_are_exposed_over_http(server):
    uri = f"ws://{server.host}:{server.websocket_port}"
    first, second, third = await asyncio.gather(
        websockets.connect(uri), websockets.connect(uri), websockets.connect(uri)
    )
    first_id = json.loads(await first.recv())["payload"]["client_id"]
    second_id = json.loads(await second.recv())["payload"]["client_id"]
    await third.recv()

    await first.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
    await second.send(json.dumps({"type": "subscribe", "channel": "chat", "payload": {}}))
    for _ in range(20):
        if (await get_json(server, "/channels"))["channels"] == {"alerts": 1, "chat": 1}:
            break
        await asyncio.sleep(0.001)
    await first.send(json.dumps({"type": "broadcast", "channel": "alerts", "payload": {"value": 1}}))
    assert json.loads(await first.recv())["payload"] == {"value": 1}
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(second.recv(), timeout=0.05)
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(third.recv(), timeout=0.05)

    channels = await get_json(server, "/channels")
    assert channels == {"channels": {"alerts": 1, "chat": 1}}
    assert (await get_json(server, f"/channels/alerts/subscribers"))["subscribers"] == [first_id]
    assert (await get_json(server, "/channels/system/subscribers"))["subscribers"] == []

    await first.send(json.dumps({"type": "unsubscribe", "channel": "alerts", "payload": {}}))
    assert (await get_json(server, "/channels/alerts/subscribers"))["subscribers"] == []
    await first.close()
    await second.close()
    await third.close()
