import asyncio
import json

import pytest
import websockets

from app import NotificationServer


async def receive_json(websocket):
    return json.loads(await websocket.recv())


async def http_json(port, path):
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(f"GET {path} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n".encode())
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    return json.loads(response.split(b"\r\n\r\n", 1)[1])


@pytest.fixture
async def running_server():
    server = NotificationServer("127.0.0.1", 0)
    await server.start()
    port = server._server.sockets[0].getsockname()[1]
    yield server, port
    await server.stop()


@pytest.mark.asyncio
async def test_clients_receive_unique_ids_and_disconnect_is_clean(running_server):
    server, port = running_server
    first = await websockets.connect(f"ws://127.0.0.1:{port}")
    second = await websockets.connect(f"ws://127.0.0.1:{port}")
    first_message = await receive_json(first)
    second_message = await receive_json(second)

    assert first_message["type"] == "system"
    first_id = first_message["payload"]["client_id"]
    second_id = second_message["payload"]["client_id"]
    assert first_id != second_id
    assert server.connected_clients == 2

    await first.close()
    for _ in range(20):
        if server.connected_clients == 1:
            break
        await asyncio.sleep(0.01)
    assert server.connected_clients == 1
    await second.close()


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients(running_server):
    server, port = running_server
    first = await websockets.connect(f"ws://127.0.0.1:{port}")
    second = await websockets.connect(f"ws://127.0.0.1:{port}")
    await receive_json(first)
    await receive_json(second)

    await first.send(json.dumps({"type": "broadcast", "payload": {"message": "hello"}}))
    messages = await asyncio.gather(receive_json(first), receive_json(second))
    assert all(message["type"] == "broadcast" for message in messages)
    assert all(message["payload"] == {"message": "hello"} for message in messages)
    assert all(isinstance(message["timestamp"], str) for message in messages)
    await first.close()
    await second.close()


@pytest.mark.asyncio
async def test_direct_message_only_reaches_target(running_server):
    server, port = running_server
    sender = await websockets.connect(f"ws://127.0.0.1:{port}")
    target = await websockets.connect(f"ws://127.0.0.1:{port}")
    await receive_json(sender)
    target_id = (await receive_json(target))["payload"]["client_id"]

    await sender.send(json.dumps({"type": "direct", "payload": {"client_id": target_id, "value": 42}}))
    message = await asyncio.wait_for(receive_json(target), timeout=1)
    assert message["type"] == "direct"
    assert message["payload"]["value"] == 42
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(receive_json(sender), timeout=0.05)
    await sender.close()
    await target.close()


@pytest.mark.asyncio
async def test_health_returns_connected_client_count(running_server):
    server, port = running_server
    client = await websockets.connect(f"ws://127.0.0.1:{port}")
    await receive_json(client)

    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()

    assert b"200 OK" in response
    body = json.loads(response.split(b"\r\n\r\n", 1)[1])
    assert body == {"status": "ok", "connected_clients": 1}
    await client.close()


@pytest.mark.asyncio
async def test_invalid_json_does_not_disconnect_client(running_server):
    server, port = running_server
    client = await websockets.connect(f"ws://127.0.0.1:{port}")
    await receive_json(client)
    await client.send("not json")
    assert server.connected_clients == 1
    await client.close()


@pytest.mark.asyncio
async def test_channel_broadcast_reaches_only_subscribers_and_can_unsubscribe(running_server):
    server, port = running_server
    subscriber = await websockets.connect(f"ws://127.0.0.1:{port}")
    other = await websockets.connect(f"ws://127.0.0.1:{port}")
    await receive_json(subscriber)
    await receive_json(other)

    await subscriber.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
    await subscriber.send(json.dumps({"type": "broadcast", "channel": "alerts", "payload": {"value": 1}}))
    message = await asyncio.wait_for(receive_json(subscriber), timeout=1)
    assert message["channel"] == "alerts"
    assert message["payload"] == {"value": 1}
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(receive_json(other), timeout=0.05)

    await subscriber.send(json.dumps({"type": "unsubscribe", "payload": {"channel": "alerts"}}))
    await subscriber.send(json.dumps({"type": "broadcast", "channel": "alerts", "payload": {"value": 2}}))
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(receive_json(subscriber), timeout=0.05)
    await subscriber.close()
    await other.close()


@pytest.mark.asyncio
async def test_channel_endpoints_report_subscribers_and_disconnect_cleanup(running_server):
    server, port = running_server
    client = await websockets.connect(f"ws://127.0.0.1:{port}")
    client_id = (await receive_json(client))["payload"]["client_id"]
    await client.send(json.dumps({"type": "subscribe", "payload": {"channel": "system"}}))

    assert (await http_json(port, "/channels")) == {"channels": {"system": 1}}
    assert (await http_json(port, "/channels/system/subscribers")) == {
        "channel": "system",
        "subscribers": [client_id],
    }
    await client.close()
