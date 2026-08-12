import asyncio
import json

import pytest
import websockets

from app import NotificationHTTPServer, NotificationServer


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients_and_health_counts() -> None:
    notification_server = NotificationServer()
    websocket_server = await websockets.serve(
        notification_server.handle_client, "127.0.0.1", 0
    )
    port = websocket_server.sockets[0].getsockname()[1]
    first = await websockets.connect(f"ws://127.0.0.1:{port}")
    second = await websockets.connect(f"ws://127.0.0.1:{port}")
    try:
        first_welcome = json.loads(await first.recv())
        second_welcome = json.loads(await second.recv())
        assert first_welcome["type"] == "system"
        assert first_welcome["payload"]["client_id"] != second_welcome["payload"]["client_id"]
        assert notification_server.health()["connected_clients"] == 2

        await first.send(json.dumps({"type": "broadcast", "payload": {"text": "hello"}}))
        for client in (first, second):
            received = json.loads(await client.recv())
            assert received["type"] == "broadcast"
            assert received["payload"] == {"text": "hello"}
            assert "timestamp" in received
    finally:
        await first.close()
        await second.close()
        websocket_server.close()
        await websocket_server.wait_closed()
    assert notification_server.connected_client_count == 0


@pytest.mark.asyncio
async def test_direct_message_only_reaches_target() -> None:
    notification_server = NotificationServer()

    class FakeWebSocket:
        def __init__(self) -> None:
            self.messages = []

        async def send(self, message: str) -> None:
            self.messages.append(json.loads(message))

    sender = FakeWebSocket()
    target = FakeWebSocket()
    sender_id = notification_server.add_client(sender)
    target_id = notification_server.add_client(target)
    await notification_server.handle_message(
        sender_id,
        json.dumps({"type": "direct", "payload": {"client_id": target_id, "text": "private"}}),
    )
    assert sender.messages == []
    assert target.messages[0]["payload"]["text"] == "private"


@pytest.mark.asyncio
async def test_health_endpoint_returns_current_count() -> None:
    notification_server = NotificationServer()
    http_server = await asyncio.start_server(
        NotificationHTTPServer(notification_server).handler, "127.0.0.1", 0
    )
    port = http_server.sockets[0].getsockname()[1]
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n")
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    http_server.close()
    await http_server.wait_closed()
    assert b"200 OK" in response
    assert json.loads(response.split(b"\r\n\r\n", 1)[1]) == {
        "status": "ok",
        "connected_clients": 0,
    }
