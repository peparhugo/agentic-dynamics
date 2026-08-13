"""
Tests for WebSocket notification server.

Tests cover:
- Client registration and deregistration
- Broadcasting to all clients
- Direct messaging
- Health endpoint
- Message format validation
- Connection lifecycle
"""

import pytest
import json
import asyncio
import websockets
from aiohttp import web
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app import (
    ClientRegistry,
    create_message,
    websocket_handler,
    health_handler,
    registry,
)


@pytest.fixture
def client_registry():
    """Provide a fresh client registry for each test."""
    return ClientRegistry()


@pytest.mark.asyncio
async def test_client_registry_register_and_get_count(client_registry):
    """Test registering clients and getting count."""
    mock_ws1 = object()
    mock_ws2 = object()

    await client_registry.register("client1", mock_ws1)
    assert await client_registry.get_client_count() == 1

    await client_registry.register("client2", mock_ws2)
    assert await client_registry.get_client_count() == 2


@pytest.mark.asyncio
async def test_client_registry_unregister(client_registry):
    """Test unregistering clients."""
    mock_ws = object()
    await client_registry.register("client1", mock_ws)
    assert await client_registry.get_client_count() == 1

    await client_registry.unregister("client1")
    assert await client_registry.get_client_count() == 0


@pytest.mark.asyncio
async def test_client_registry_unregister_nonexistent(client_registry):
    """Test unregistering a non-existent client (should not raise)."""
    await client_registry.unregister("nonexistent")
    assert await client_registry.get_client_count() == 0


@pytest.mark.asyncio
async def test_client_registry_get_all_clients(client_registry):
    """Test retrieving all clients."""
    mock_ws1 = object()
    mock_ws2 = object()

    await client_registry.register("client1", mock_ws1)
    await client_registry.register("client2", mock_ws2)

    clients = await client_registry.get_all_clients()
    assert len(clients) == 2
    assert "client1" in clients
    assert "client2" in clients
    assert clients["client1"] is mock_ws1
    assert clients["client2"] is mock_ws2


def test_create_message():
    """Test message creation with proper format."""
    message = create_message("broadcast", {"text": "hello"})

    assert message["type"] == "broadcast"
    assert message["payload"] == {"text": "hello"}
    assert "timestamp" in message
    assert isinstance(message["timestamp"], str)

    # Validate ISO format timestamp
    datetime.fromisoformat(message["timestamp"])


def test_create_message_with_empty_payload():
    """Test creating message with empty payload."""
    message = create_message("system", {})

    assert message["type"] == "system"
    assert message["payload"] == {}
    assert "timestamp" in message


def test_create_message_with_complex_payload():
    """Test creating message with nested payload."""
    payload = {
        "nested": {"key": "value"},
        "list": [1, 2, 3],
        "bool": True,
        "null": None
    }
    message = create_message("direct", payload)

    assert message["type"] == "direct"
    assert message["payload"] == payload


@pytest.mark.asyncio
async def test_health_endpoint():
    """Test the health endpoint returns correct format."""
    # Mock request object
    class MockRequest:
        pass

    test_registry = ClientRegistry()

    # Add some test clients
    mock_ws1 = object()
    mock_ws2 = object()
    await test_registry.register("client1", mock_ws1)
    await test_registry.register("client2", mock_ws2)

    # Swap registry temporarily
    original_registry = sys.modules['app'].registry
    sys.modules['app'].registry = test_registry

    try:
        request = MockRequest()
        response = await health_handler(request)
        data = json.loads(response.text)

        assert data["status"] == "ok"
        assert data["connected_clients"] == 2
        assert "timestamp" in data
        assert isinstance(data["timestamp"], str)
    finally:
        sys.modules['app'].registry = original_registry


@pytest.mark.asyncio
async def test_broadcast_message():
    """Test broadcasting to multiple clients."""
    client_registry = ClientRegistry()

    # Create mock WebSocket-like objects that track sent messages
    class MockWebSocket:
        def __init__(self):
            self.messages = []
            self.closed = False

        async def send(self, message):
            if self.closed:
                raise websockets.exceptions.ConnectionClosed(None, None)
            self.messages.append(message)

    ws1 = MockWebSocket()
    ws2 = MockWebSocket()
    ws3 = MockWebSocket()

    await client_registry.register("client1", ws1)
    await client_registry.register("client2", ws2)
    await client_registry.register("client3", ws3)

    message = create_message("broadcast", {"text": "hello all"})
    await client_registry.broadcast(message)

    assert len(ws1.messages) == 1
    assert len(ws2.messages) == 1
    assert len(ws3.messages) == 1

    # Verify message content
    sent_data = json.loads(ws1.messages[0])
    assert sent_data["type"] == "broadcast"
    assert sent_data["payload"]["text"] == "hello all"


@pytest.mark.asyncio
async def test_broadcast_with_disconnected_client():
    """Test broadcast handles disconnected clients gracefully."""
    client_registry = ClientRegistry()

    class MockWebSocket:
        def __init__(self, will_fail=False):
            self.messages = []
            self.will_fail = will_fail

        async def send(self, message):
            if self.will_fail:
                raise websockets.exceptions.ConnectionClosed(None, None)
            self.messages.append(message)

    ws1 = MockWebSocket()
    ws2 = MockWebSocket(will_fail=True)  # This one will fail
    ws3 = MockWebSocket()

    await client_registry.register("client1", ws1)
    await client_registry.register("client2", ws2)
    await client_registry.register("client3", ws3)

    message = create_message("broadcast", {"text": "test"})
    await client_registry.broadcast(message)

    # All successful clients should have the message
    assert len(ws1.messages) == 1
    assert len(ws3.messages) == 1

    # Disconnected client should be removed
    assert await client_registry.get_client_count() == 2


@pytest.mark.asyncio
async def test_broadcast_no_clients():
    """Test broadcast when no clients are connected."""
    client_registry = ClientRegistry()

    message = create_message("broadcast", {"text": "nobody home"})
    # Should not raise
    await client_registry.broadcast(message)

    assert await client_registry.get_client_count() == 0


@pytest.mark.asyncio
async def test_message_format_validation():
    """Test that messages follow the correct format."""
    for msg_type in ["broadcast", "direct", "system"]:
        message = create_message(msg_type, {"test": "data"})

        # Must be JSON serializable
        json_str = json.dumps(message)
        parsed = json.loads(json_str)

        assert "type" in parsed
        assert "payload" in parsed
        assert "timestamp" in parsed
        assert len(parsed.keys()) == 3


@pytest.mark.asyncio
async def test_concurrent_client_operations():
    """Test thread-safe operations with concurrent clients."""
    client_registry = ClientRegistry()

    class MockWebSocket:
        def __init__(self):
            self.messages = []

        async def send(self, message):
            self.messages.append(message)

    # Simulate concurrent registrations
    tasks = []
    for i in range(10):
        ws = MockWebSocket()
        tasks.append(client_registry.register(f"client{i}", ws))

    await asyncio.gather(*tasks)
    assert await client_registry.get_client_count() == 10

    # Simulate concurrent unregistrations
    tasks = []
    for i in range(5):
        tasks.append(client_registry.unregister(f"client{i}"))

    await asyncio.gather(*tasks)
    assert await client_registry.get_client_count() == 5


@pytest.mark.asyncio
async def test_message_with_from_client():
    """Test that broadcast includes from_client in payload."""
    client_registry = ClientRegistry()

    class MockWebSocket:
        def __init__(self):
            self.messages = []

        async def send(self, message):
            self.messages.append(json.loads(message))

    ws = MockWebSocket()
    await client_registry.register("test_client", ws)

    message = create_message("broadcast", {"text": "hello", "from_client": "sender123"})
    await client_registry.broadcast(message)

    assert len(ws.messages) == 1
    sent = ws.messages[0]
    assert sent["payload"]["from_client"] == "sender123"


@pytest.mark.asyncio
async def test_registry_isolation():
    """Test that multiple registries are independent."""
    registry1 = ClientRegistry()
    registry2 = ClientRegistry()

    class MockWebSocket:
        pass

    ws1 = MockWebSocket()
    ws2 = MockWebSocket()

    await registry1.register("client1", ws1)
    await registry2.register("client1", ws2)

    assert await registry1.get_client_count() == 1
    assert await registry2.get_client_count() == 1

    await registry1.unregister("client1")
    assert await registry1.get_client_count() == 0
    assert await registry2.get_client_count() == 1


@pytest.mark.asyncio
async def test_timestamp_format():
    """Test that timestamps are valid ISO 8601."""
    message = create_message("broadcast", {})
    timestamp_str = message["timestamp"]

    # Should not raise
    dt = datetime.fromisoformat(timestamp_str)
    assert dt is not None


@pytest.mark.asyncio
async def test_client_count_after_operations():
    """Test client count accuracy through various operations."""
    client_registry = ClientRegistry()

    class MockWebSocket:
        pass

    ws1 = MockWebSocket()
    ws2 = MockWebSocket()
    ws3 = MockWebSocket()

    await client_registry.register("c1", ws1)
    assert await client_registry.get_client_count() == 1

    await client_registry.register("c2", ws2)
    await client_registry.register("c3", ws3)
    assert await client_registry.get_client_count() == 3

    await client_registry.unregister("c2")
    assert await client_registry.get_client_count() == 2

    await client_registry.unregister("c1")
    await client_registry.unregister("c3")
    assert await client_registry.get_client_count() == 0


def test_app_imports():
    """Test that app module can be imported without errors."""
    import app as app_module
    assert hasattr(app_module, 'ClientRegistry')
    assert hasattr(app_module, 'websocket_handler')
    assert hasattr(app_module, 'health_handler')
    assert hasattr(app_module, 'create_message')


def test_message_json_serializable():
    """Test that all created messages are JSON serializable."""
    test_payloads = [
        {},
        {"text": "hello"},
        {"nested": {"data": [1, 2, 3]}},
        {"numbers": 123, "floats": 45.67, "bools": True, "none": None},
    ]

    for payload in test_payloads:
        message = create_message("broadcast", payload)
        json_str = json.dumps(message)
        assert isinstance(json_str, str)
        assert len(json_str) > 0


@pytest.mark.asyncio
async def test_broadcast_preserves_message_structure():
    """Test that broadcast doesn't modify the original message."""
    client_registry = ClientRegistry()

    class MockWebSocket:
        def __init__(self):
            self.messages = []

        async def send(self, message):
            self.messages.append(message)

    ws = MockWebSocket()
    await client_registry.register("client1", ws)

    original_message = create_message("broadcast", {"key": "value", "number": 42})
    await client_registry.broadcast(original_message)

    # Verify message was sent exactly as provided
    sent_json = ws.messages[0]
    sent_message = json.loads(sent_json)

    assert sent_message["type"] == "broadcast"
    assert sent_message["payload"]["key"] == "value"
    assert sent_message["payload"]["number"] == 42
    assert sent_message["timestamp"] == original_message["timestamp"]
