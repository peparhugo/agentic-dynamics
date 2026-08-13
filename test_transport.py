"""
Tests demonstrating the pluggable transport layer.

Shows that NotificationServer can work with different transport implementations
without modification of the core logic.
"""

import pytest
import json
from app import NotificationServer, ClientRegistry
from transport import BaseTransport, WebSocketTransport


class MockTransport(BaseTransport):
    """Mock transport for testing."""

    def __init__(self, registry):
        super().__init__(registry)
        self.sent_messages = []
        self.broadcasted_messages = []

    async def send_message(self, client_id: str, message: dict) -> None:
        """Store sent message in mock."""
        self.sent_messages.append({
            "client_id": client_id,
            "message": message,
        })

    async def broadcast(
        self, message: dict, exclude: str | None = None, channel: str | None = None
    ) -> None:
        """Store broadcasted message in mock."""
        self.broadcasted_messages.append({
            "message": message,
            "exclude": exclude,
            "channel": channel,
        })


@pytest.mark.asyncio
async def test_notification_server_with_custom_transport():
    """Test that NotificationServer works with custom transport implementations."""
    registry = ClientRegistry()
    custom_transport = MockTransport(registry)
    server = NotificationServer(transport=custom_transport)

    # Verify the transport is set correctly
    assert isinstance(server.transport, MockTransport)
    assert server.transport is custom_transport


@pytest.mark.asyncio
async def test_send_direct_uses_transport():
    """Test that send_direct uses the transport layer."""
    registry = ClientRegistry()
    custom_transport = MockTransport(registry)
    server = NotificationServer(transport=custom_transport)

    # Register a mock client
    from test_app import AsyncMockWebSocket
    ws = AsyncMockWebSocket()
    registry.register("client-1", ws)

    # Send a direct message
    message = {
        "type": "direct",
        "payload": {"message": "hello"},
        "timestamp": "2024-01-01T00:00:00+00:00",
    }
    await server.send_direct("client-1", message)

    # Verify transport was called
    assert len(custom_transport.sent_messages) == 1
    assert custom_transport.sent_messages[0]["client_id"] == "client-1"
    assert custom_transport.sent_messages[0]["message"] == message


@pytest.mark.asyncio
async def test_broadcast_uses_transport():
    """Test that broadcast uses the transport layer."""
    registry = ClientRegistry()
    custom_transport = MockTransport(registry)
    server = NotificationServer(transport=custom_transport)

    # Broadcast a message
    message = {
        "type": "broadcast",
        "payload": {"content": "hello"},
        "timestamp": "2024-01-01T00:00:00+00:00",
    }
    await server.broadcast(message)

    # Verify transport was called
    assert len(custom_transport.broadcasted_messages) == 1
    assert custom_transport.broadcasted_messages[0]["message"] == message
    assert custom_transport.broadcasted_messages[0]["exclude"] is None
    assert custom_transport.broadcasted_messages[0]["channel"] is None


@pytest.mark.asyncio
async def test_broadcast_with_channel_uses_transport():
    """Test that broadcast with channel uses the transport layer."""
    registry = ClientRegistry()
    custom_transport = MockTransport(registry)
    server = NotificationServer(transport=custom_transport)

    # Broadcast to a channel
    message = {
        "type": "broadcast",
        "payload": {"content": "alert"},
        "timestamp": "2024-01-01T00:00:00+00:00",
    }
    await server.broadcast(message, channel="alerts")

    # Verify transport was called with channel
    assert len(custom_transport.broadcasted_messages) == 1
    assert custom_transport.broadcasted_messages[0]["channel"] == "alerts"


@pytest.mark.asyncio
async def test_websocket_transport_is_default():
    """Test that WebSocketTransport is used by default."""
    server = NotificationServer()
    assert isinstance(server.transport, WebSocketTransport)


@pytest.mark.asyncio
async def test_transport_with_exclude():
    """Test that exclude parameter is passed to transport."""
    registry = ClientRegistry()
    custom_transport = MockTransport(registry)
    server = NotificationServer(transport=custom_transport)

    message = {
        "type": "broadcast",
        "payload": {"content": "hello"},
        "timestamp": "2024-01-01T00:00:00+00:00",
    }
    await server.broadcast(message, exclude="client-1")

    # Verify exclude was passed to transport
    assert len(custom_transport.broadcasted_messages) == 1
    assert custom_transport.broadcasted_messages[0]["exclude"] == "client-1"
