import asyncio
import json
import threading
from datetime import datetime
from urllib.request import urlopen

import pytest
from websockets.asyncio.client import connect

from app import ClientRegistry, NotificationServer


@pytest.fixture
async def running_server():
    notification_server = NotificationServer()
    async with notification_server.start("127.0.0.1", 0) as websocket_server:
        port = websocket_server.sockets[0].getsockname()[1]
        yield notification_server, f"ws://127.0.0.1:{port}", port


async def receive_json(websocket):
    return json.loads(await asyncio.wait_for(websocket.recv(), timeout=1))


def assert_envelope(message, expected_type):
    assert set(message) == {"type", "payload", "timestamp"}
    assert message["type"] == expected_type
    assert isinstance(message["payload"], dict)
    assert datetime.fromisoformat(message["timestamp"].replace("Z", "+00:00"))


@pytest.mark.asyncio
async def test_assigns_unique_client_ids(running_server):
    server, url, _ = running_server
    async with connect(url) as first, connect(url) as second:
        first_message = await receive_json(first)
        second_message = await receive_json(second)

        assert_envelope(first_message, "system")
        assert first_message["payload"]["event"] == "connected"
        assert first_message["payload"]["client_id"] != second_message["payload"]["client_id"]
        assert len(server.clients) == 2


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients(running_server):
    _, url, _ = running_server
    async with connect(url) as first, connect(url) as second:
        await receive_json(first)
        await receive_json(second)
        incoming = {
            "type": "broadcast",
            "payload": {"text": "hello"},
            "timestamp": "ignored-client-time",
        }
        await first.send(json.dumps(incoming))

        first_received, second_received = await asyncio.gather(
            receive_json(first), receive_json(second)
        )
        assert_envelope(first_received, "broadcast")
        assert first_received["payload"] == {"text": "hello"}
        assert second_received == first_received
        assert first_received["timestamp"] != incoming["timestamp"]


@pytest.mark.asyncio
async def test_direct_message_only_reaches_target(running_server):
    _, url, _ = running_server
    async with connect(url) as sender, connect(url) as target, connect(url) as observer:
        sender_id = (await receive_json(sender))["payload"]["client_id"]
        target_id = (await receive_json(target))["payload"]["client_id"]
        await receive_json(observer)

        await sender.send(
            json.dumps(
                {
                    "type": "direct",
                    "payload": {"client_id": target_id, "text": "private"},
                    "timestamp": "2026-01-01T00:00:00Z",
                }
            )
        )

        received = await receive_json(target)
        assert_envelope(received, "direct")
        assert received["payload"] == {"text": "private", "sender_id": sender_id}
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(observer.recv(), timeout=0.05)


@pytest.mark.asyncio
async def test_disconnect_removes_client(running_server):
    server, url, _ = running_server
    websocket = await connect(url)
    await receive_json(websocket)
    assert len(server.clients) == 1

    await websocket.close()
    for _ in range(20):
        if len(server.clients) == 0:
            break
        await asyncio.sleep(0.01)
    assert len(server.clients) == 0


@pytest.mark.asyncio
async def test_health_returns_connected_client_count(running_server):
    _, url, port = running_server
    async with connect(url) as first, connect(url) as second:
        await receive_json(first)
        await receive_json(second)

        def request_health():
            with urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as response:
                return response.status, response.headers["Content-Type"], json.load(response)

        status, content_type, body = await asyncio.to_thread(request_health)
        assert status == 200
        assert content_type == "application/json"
        assert body == {"connected_clients": 2}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("raw_message", "detail"),
    [
        ("not-json", "invalid JSON"),
        (json.dumps([]), "message must be a JSON object"),
        (json.dumps({"type": "unknown", "payload": {}, "timestamp": "now"}), "unsupported message type"),
        (json.dumps({"type": "broadcast", "payload": "bad", "timestamp": "now"}), "payload must be an object"),
        (json.dumps({"type": "broadcast", "payload": {}}), "timestamp must be a string"),
        (json.dumps({"type": "system", "payload": {}, "timestamp": "now"}), "clients cannot send system messages"),
    ],
)
async def test_invalid_messages_return_system_error(running_server, raw_message, detail):
    _, url, _ = running_server
    async with connect(url) as websocket:
        await receive_json(websocket)
        await websocket.send(raw_message)
        received = await receive_json(websocket)

        assert_envelope(received, "system")
        assert received["payload"] == {"event": "error", "detail": detail}


@pytest.mark.asyncio
async def test_direct_message_to_missing_client_returns_error(running_server):
    _, url, _ = running_server
    async with connect(url) as websocket:
        await receive_json(websocket)
        await websocket.send(
            json.dumps(
                {
                    "type": "direct",
                    "payload": {"client_id": "missing"},
                    "timestamp": "now",
                }
            )
        )
        received = await receive_json(websocket)
        assert received["payload"]["detail"] == "target client is not connected"


def test_client_registry_is_safe_across_threads():
    registry = ClientRegistry()
    connections = [object() for _ in range(100)]

    def add_and_remove(connection):
        client = registry.add(connection)
        assert registry.get(client.id) == client
        registry.remove(client.id)

    threads = [threading.Thread(target=add_and_remove, args=(item,)) for item in connections]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(registry) == 0
