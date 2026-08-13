"""
Tests for WebSocket notification server.
"""

import asyncio
import json
import pytest
from datetime import datetime
import re

from websockets.exceptions import ConnectionClosed
from app import ClientRegistry, create_message, websocket_handler


@pytest.mark.asyncio
async def test_create_message():
    """Test message creation with proper format."""
    msg = create_message("broadcast", {"content": "hello"})

    assert msg["type"] == "broadcast"
    assert msg["payload"] == {"content": "hello"}
    assert "timestamp" in msg
    # Validate ISO format timestamp
    assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", msg["timestamp"])


@pytest.mark.asyncio
async def test_client_registry_register():
    """Test client registration."""
    registry = ClientRegistry()

    class MockWebSocket:
        pass

    ws = MockWebSocket()
    client_id = "test-client-1"

    await registry.register(client_id, ws)
    assert await registry.get_client_count() == 1

    assert registry.clients[client_id] == ws


@pytest.mark.asyncio
async def test_client_registry_unregister():
    """Test client unregistration."""
    registry = ClientRegistry()

    class MockWebSocket:
        pass

    ws = MockWebSocket()
    client_id = "test-client-1"

    await registry.register(client_id, ws)
    assert await registry.get_client_count() == 1

    await registry.unregister(client_id)
    assert await registry.get_client_count() == 0


@pytest.mark.asyncio
async def test_client_registry_broadcast():
    """Test broadcasting to multiple clients."""
    registry = ClientRegistry()

    class MockWebSocket:
        def __init__(self, client_id):
            self.client_id = client_id
            self.messages = []

        async def send(self, msg):
            self.messages.append(json.loads(msg))

    clients = {}
    for i in range(3):
        client_id = f"client-{i}"
        ws = MockWebSocket(client_id)
        clients[client_id] = ws
        await registry.register(client_id, ws)

    message = create_message("broadcast", {"content": "test"})
    await registry.broadcast(message)

    # Verify all clients received the message
    for client_id, ws in clients.items():
        assert len(ws.messages) == 1
        assert ws.messages[0]["type"] == "broadcast"
        assert ws.messages[0]["payload"]["content"] == "test"


@pytest.mark.asyncio
async def test_client_registry_send_direct():
    """Test direct messaging to specific client."""
    registry = ClientRegistry()

    class MockWebSocket:
        def __init__(self):
            self.messages = []

        async def send(self, msg):
            self.messages.append(json.loads(msg))

    client1 = MockWebSocket()
    client2 = MockWebSocket()

    await registry.register("client-1", client1)
    await registry.register("client-2", client2)

    message = create_message("direct", {"content": "personal"})
    await registry.send_direct("client-1", message)

    assert len(client1.messages) == 1
    assert client1.messages[0]["payload"]["content"] == "personal"
    assert len(client2.messages) == 0


@pytest.mark.asyncio
async def test_client_registry_handles_disconnected():
    """Test that disconnected clients are removed on broadcast."""
    registry = ClientRegistry()

    class DisconnectingWebSocket:
        async def send(self, msg):
            raise ConnectionClosed(None, None)

    ws = DisconnectingWebSocket()
    await registry.register("client-1", ws)
    assert await registry.get_client_count() == 1

    # Broadcast should handle disconnection
    message = create_message("broadcast", {"content": "test"})
    await registry.broadcast(message)

    # Client should be removed after failed send
    assert await registry.get_client_count() == 0


@pytest.mark.asyncio
async def test_client_registry_handles_disconnected_on_direct():
    """Test that disconnected clients are removed on direct message."""
    registry = ClientRegistry()

    class DisconnectingWebSocket:
        async def send(self, msg):
            raise ConnectionClosed(None, None)

    ws = DisconnectingWebSocket()
    await registry.register("client-1", ws)
    assert await registry.get_client_count() == 1

    # Direct message should handle disconnection
    message = create_message("direct", {"content": "test"})
    await registry.send_direct("client-1", message)

    # Client should be removed after failed send
    assert await registry.get_client_count() == 0


@pytest.mark.asyncio
async def test_health_handler():
    """Test health endpoint returns correct client count."""
    from app import registry, health_handler

    # Clear registry
    registry.clients.clear()

    class MockWebSocket:
        pass

    # Register a few clients
    for i in range(3):
        await registry.register(f"client-{i}", MockWebSocket())

    # Mock request object
    class MockRequest:
        pass

    request = MockRequest()

    response = await health_handler(request)
    data = json.loads(response.text)

    assert data["status"] == "ok"
    assert data["connected_clients"] == 3

    # Clear for next test
    registry.clients.clear()


@pytest.mark.asyncio
async def test_registry_get_client_count():
    """Test getting client count."""
    registry = ClientRegistry()

    class MockWebSocket:
        pass

    assert await registry.get_client_count() == 0

    # Register clients
    for i in range(5):
        await registry.register(f"client-{i}", MockWebSocket())

    assert await registry.get_client_count() == 5

    # Unregister one
    await registry.unregister("client-0")
    assert await registry.get_client_count() == 4


@pytest.mark.asyncio
async def test_websocket_handler_with_message():
    """Test that websocket handler processes messages."""
    from app import registry

    registry.clients.clear()

    class TestWebSocket:
        def __init__(self):
            self.messages = []
            self.message_queue = [json.dumps({"type": "broadcast", "payload": {"test": "data"}})]
            self.index = 0

        async def send(self, msg):
            self.messages.append(msg)

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.index >= len(self.message_queue):
                raise StopAsyncIteration
            msg = self.message_queue[self.index]
            self.index += 1
            return msg

    ws = TestWebSocket()

    # Run handler as a task with timeout
    task = asyncio.create_task(websocket_handler(ws))

    # Give handler time to process
    await asyncio.sleep(0.1)

    # Should have join message and broadcast echo
    assert len(ws.messages) >= 2
    msg = json.loads(ws.messages[0])
    assert msg["type"] == "system"
    assert msg["payload"]["event"] == "client_joined"

    # Clean up
    try:
        await asyncio.wait_for(task, timeout=0.1)
    except asyncio.TimeoutError:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    registry.clients.clear()


@pytest.mark.asyncio
async def test_websocket_handler_disconnect():
    """Test websocket handler disconnect notification."""
    from app import registry

    registry.clients.clear()

    class TestWebSocket:
        def __init__(self):
            self.messages = []
            self.message_queue = []
            self.index = 0

        async def send(self, msg):
            self.messages.append(msg)

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.index >= len(self.message_queue):
                raise StopAsyncIteration
            msg = self.message_queue[self.index]
            self.index += 1
            return msg

    ws1 = TestWebSocket()
    ws2 = TestWebSocket()

    task1 = asyncio.create_task(websocket_handler(ws1))
    task2 = asyncio.create_task(websocket_handler(ws2))

    # Give handlers time to register
    await asyncio.sleep(0.1)

    # Both should have at least join messages
    assert len(ws1.messages) >= 1
    assert len(ws2.messages) >= 1

    # Verify join messages
    msg1 = json.loads(ws1.messages[0])
    assert msg1["type"] == "system"
    assert msg1["payload"]["event"] == "client_joined"

    # Clean up
    try:
        await asyncio.wait_for(asyncio.gather(task1, task2), timeout=0.5)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        task1.cancel()
        task2.cancel()
        try:
            await asyncio.gather(task1, task2)
        except asyncio.CancelledError:
            pass

    registry.clients.clear()


@pytest.mark.asyncio
async def test_websocket_handler_invalid_json():
    """Test websocket handler invalid JSON handling."""
    from app import registry

    registry.clients.clear()

    class TestWebSocket:
        def __init__(self):
            self.messages = []
            self.message_queue = ["not valid json {"]
            self.index = 0

        async def send(self, msg):
            self.messages.append(msg)

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.index >= len(self.message_queue):
                raise StopAsyncIteration
            msg = self.message_queue[self.index]
            self.index += 1
            return msg

    ws = TestWebSocket()

    task = asyncio.create_task(websocket_handler(ws))

    # Give handler time to process
    await asyncio.sleep(0.1)

    # Should have join message + error message
    assert len(ws.messages) >= 2

    # Find error message
    error_found = False
    for msg_str in ws.messages[1:]:
        msg = json.loads(msg_str)
        if msg["type"] == "system" and "Invalid JSON" in msg["payload"].get("error", ""):
            error_found = True
            break

    assert error_found, "Invalid JSON error not found"

    # Clean up
    try:
        await asyncio.wait_for(task, timeout=0.2)
    except asyncio.TimeoutError:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    registry.clients.clear()


@pytest.mark.asyncio
async def test_websocket_handler_unknown_message_type():
    """Test websocket handler unknown message type."""
    from app import registry

    registry.clients.clear()

    class TestWebSocket:
        def __init__(self):
            self.messages = []
            self.message_queue = [json.dumps({"type": "unknown", "payload": {}})]
            self.index = 0

        async def send(self, msg):
            self.messages.append(msg)

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.index >= len(self.message_queue):
                raise StopAsyncIteration
            msg = self.message_queue[self.index]
            self.index += 1
            return msg

    ws = TestWebSocket()

    task = asyncio.create_task(websocket_handler(ws))

    # Give handler time to process
    await asyncio.sleep(0.1)

    # Should have join message + error message
    assert len(ws.messages) >= 2

    # Find error message
    error_found = False
    for msg_str in ws.messages[1:]:
        msg = json.loads(msg_str)
        if (
            msg["type"] == "system"
            and "Unknown message type" in msg["payload"].get("error", "")
        ):
            error_found = True
            break

    assert error_found, "Unknown message type error not found"

    # Clean up
    try:
        await asyncio.wait_for(task, timeout=0.2)
    except asyncio.TimeoutError:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    registry.clients.clear()
