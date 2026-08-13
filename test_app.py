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
    assert hasattr(app_module, 'channels_handler')
    assert hasattr(app_module, 'channel_subscribers_handler')


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


@pytest.mark.asyncio
async def test_client_subscribe_to_channel(client_registry):
    """Test client subscribing to a channel."""
    mock_ws = object()
    await client_registry.register("client1", mock_ws)

    result = await client_registry.subscribe("client1", "alerts")
    assert result is True

    subscribers = await client_registry.get_channel_subscribers("alerts")
    assert "client1" in subscribers


@pytest.mark.asyncio
async def test_client_unsubscribe_from_channel(client_registry):
    """Test client unsubscribing from a channel."""
    mock_ws = object()
    await client_registry.register("client1", mock_ws)

    await client_registry.subscribe("client1", "alerts")
    subscribers = await client_registry.get_channel_subscribers("alerts")
    assert "client1" in subscribers

    await client_registry.unsubscribe("client1", "alerts")
    subscribers = await client_registry.get_channel_subscribers("alerts")
    assert "client1" not in subscribers


@pytest.mark.asyncio
async def test_subscribe_nonexistent_client(client_registry):
    """Test subscribing a non-existent client (should fail gracefully)."""
    result = await client_registry.subscribe("nonexistent", "alerts")
    assert result is False


@pytest.mark.asyncio
async def test_get_channels_list(client_registry):
    """Test getting list of all channels with subscriber counts."""
    class MockWebSocket:
        async def send(self, message):
            pass

    mock_ws1 = MockWebSocket()
    mock_ws2 = MockWebSocket()
    mock_ws3 = MockWebSocket()

    await client_registry.register("client1", mock_ws1)
    await client_registry.register("client2", mock_ws2)
    await client_registry.register("client3", mock_ws3)

    await client_registry.subscribe("client1", "alerts")
    await client_registry.subscribe("client2", "alerts")
    await client_registry.subscribe("client2", "system")
    await client_registry.subscribe("client3", "system")

    channels = await client_registry.get_channels()
    assert len(channels) == 2
    assert channels["alerts"] == 2
    assert channels["system"] == 2


@pytest.mark.asyncio
async def test_get_channel_subscribers(client_registry):
    """Test getting subscriber list for a specific channel."""
    class MockWebSocket:
        async def send(self, message):
            pass

    mock_ws1 = MockWebSocket()
    mock_ws2 = MockWebSocket()

    await client_registry.register("client1", mock_ws1)
    await client_registry.register("client2", mock_ws2)

    await client_registry.subscribe("client1", "alerts")
    await client_registry.subscribe("client2", "alerts")

    subscribers = await client_registry.get_channel_subscribers("alerts")
    assert len(subscribers) == 2
    assert "client1" in subscribers
    assert "client2" in subscribers


@pytest.mark.asyncio
async def test_get_nonexistent_channel_subscribers(client_registry):
    """Test getting subscribers for a channel that doesn't exist."""
    subscribers = await client_registry.get_channel_subscribers("nonexistent")
    assert len(subscribers) == 0


@pytest.mark.asyncio
async def test_broadcast_to_specific_channel(client_registry):
    """Test broadcasting to only subscribers of a specific channel."""
    class MockWebSocket:
        def __init__(self):
            self.messages = []

        async def send(self, message):
            self.messages.append(message)

    ws1 = MockWebSocket()
    ws2 = MockWebSocket()
    ws3 = MockWebSocket()

    await client_registry.register("client1", ws1)
    await client_registry.register("client2", ws2)
    await client_registry.register("client3", ws3)

    await client_registry.subscribe("client1", "alerts")
    await client_registry.subscribe("client2", "alerts")
    await client_registry.subscribe("client3", "system")

    message = create_message("broadcast", {"text": "alert message"})
    await client_registry.broadcast(message, channel="alerts")

    # Only subscribers of "alerts" should receive
    assert len(ws1.messages) == 1
    assert len(ws2.messages) == 1
    assert len(ws3.messages) == 0


@pytest.mark.asyncio
async def test_broadcast_without_channel_still_broadcasts_to_all(client_registry):
    """Test that broadcast without channel still broadcasts to all clients."""
    class MockWebSocket:
        def __init__(self):
            self.messages = []

        async def send(self, message):
            self.messages.append(message)

    ws1 = MockWebSocket()
    ws2 = MockWebSocket()
    ws3 = MockWebSocket()

    await client_registry.register("client1", ws1)
    await client_registry.register("client2", ws2)
    await client_registry.register("client3", ws3)

    await client_registry.subscribe("client1", "alerts")
    await client_registry.subscribe("client2", "system")

    message = create_message("broadcast", {"text": "global message"})
    await client_registry.broadcast(message)

    # All clients should receive
    assert len(ws1.messages) == 1
    assert len(ws2.messages) == 1
    assert len(ws3.messages) == 1


@pytest.mark.asyncio
async def test_client_multiple_channel_subscriptions(client_registry):
    """Test that a client can subscribe to multiple channels."""
    class MockWebSocket:
        async def send(self, message):
            pass

    mock_ws = MockWebSocket()
    await client_registry.register("client1", mock_ws)

    await client_registry.subscribe("client1", "alerts")
    await client_registry.subscribe("client1", "system")
    await client_registry.subscribe("client1", "chat")

    alerts_subs = await client_registry.get_channel_subscribers("alerts")
    system_subs = await client_registry.get_channel_subscribers("system")
    chat_subs = await client_registry.get_channel_subscribers("chat")

    assert "client1" in alerts_subs
    assert "client1" in system_subs
    assert "client1" in chat_subs


@pytest.mark.asyncio
async def test_unregister_removes_from_all_channels(client_registry):
    """Test that unregistering a client removes it from all channel subscriptions."""
    class MockWebSocket:
        async def send(self, message):
            pass

    mock_ws = MockWebSocket()
    await client_registry.register("client1", mock_ws)

    await client_registry.subscribe("client1", "alerts")
    await client_registry.subscribe("client1", "system")

    # Verify subscriptions exist
    alerts_subs = await client_registry.get_channel_subscribers("alerts")
    assert "client1" in alerts_subs

    # Unregister client
    await client_registry.unregister("client1")

    # Verify client is removed from all channels
    alerts_subs = await client_registry.get_channel_subscribers("alerts")
    system_subs = await client_registry.get_channel_subscribers("system")
    assert "client1" not in alerts_subs
    assert "client1" not in system_subs

    # Verify empty channels are cleaned up
    channels = await client_registry.get_channels()
    assert len(channels) == 0


@pytest.mark.asyncio
async def test_broadcast_to_empty_channel(client_registry):
    """Test broadcasting to a channel with no subscribers."""
    class MockWebSocket:
        def __init__(self):
            self.messages = []

        async def send(self, message):
            self.messages.append(message)

    ws1 = MockWebSocket()
    await client_registry.register("client1", ws1)

    message = create_message("broadcast", {"text": "nobody listening"})
    # Should not raise
    await client_registry.broadcast(message, channel="empty")

    # Client should not receive message
    assert len(ws1.messages) == 0


@pytest.mark.asyncio
async def test_channels_endpoint(client_registry):
    """Test the /channels endpoint returns correct format."""
    class MockWebSocket:
        async def send(self, message):
            pass

    mock_ws1 = MockWebSocket()
    mock_ws2 = MockWebSocket()
    mock_ws3 = MockWebSocket()

    await client_registry.register("client1", mock_ws1)
    await client_registry.register("client2", mock_ws2)
    await client_registry.register("client3", mock_ws3)

    await client_registry.subscribe("client1", "alerts")
    await client_registry.subscribe("client2", "alerts")
    await client_registry.subscribe("client3", "system")

    # Swap registry temporarily
    original_registry = sys.modules['app'].registry
    sys.modules['app'].registry = client_registry

    try:
        from app import channels_handler
        class MockRequest:
            pass

        request = MockRequest()
        response = await channels_handler(request)
        data = json.loads(response.text)

        assert "channels" in data
        assert "timestamp" in data
        assert data["channels"]["alerts"] == 2
        assert data["channels"]["system"] == 1
    finally:
        sys.modules['app'].registry = original_registry


@pytest.mark.asyncio
async def test_channel_subscribers_endpoint(client_registry):
    """Test the /channels/{name}/subscribers endpoint."""
    class MockWebSocket:
        async def send(self, message):
            pass

    mock_ws1 = MockWebSocket()
    mock_ws2 = MockWebSocket()

    await client_registry.register("client1", mock_ws1)
    await client_registry.register("client2", mock_ws2)

    await client_registry.subscribe("client1", "alerts")
    await client_registry.subscribe("client2", "alerts")

    # Swap registry temporarily
    original_registry = sys.modules['app'].registry
    sys.modules['app'].registry = client_registry

    try:
        from app import channel_subscribers_handler

        class MockRequest:
            def __init__(self):
                self.match_info = {"name": "alerts"}

        request = MockRequest()
        response = await channel_subscribers_handler(request)
        data = json.loads(response.text)

        assert data["channel"] == "alerts"
        assert len(data["subscribers"]) == 2
        assert data["count"] == 2
        assert "client1" in data["subscribers"]
        assert "client2" in data["subscribers"]
        assert "timestamp" in data
    finally:
        sys.modules['app'].registry = original_registry
