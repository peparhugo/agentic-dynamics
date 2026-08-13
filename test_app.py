"""
Tests for the WebSocket notification server.
"""

import asyncio
import json
import pytest
from websockets import ConnectionClosed
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

from app import NotificationServer, ClientRegistry


class TestClientRegistry:
    """Tests for the ClientRegistry class."""

    def test_register_and_get_client(self):
        """Test registering and retrieving a client."""
        registry = ClientRegistry()
        mock_websocket = object()
        client_id = "test-client-1"

        registry.register(client_id, mock_websocket)
        assert registry.get_client(client_id) == mock_websocket

    def test_unregister_client(self):
        """Test unregistering a client."""
        registry = ClientRegistry()
        mock_websocket = object()
        client_id = "test-client-1"

        registry.register(client_id, mock_websocket)
        registry.unregister(client_id)
        assert registry.get_client(client_id) is None

    def test_get_count(self):
        """Test getting the count of connected clients."""
        registry = ClientRegistry()

        assert registry.get_count() == 0

        registry.register("client-1", object())
        assert registry.get_count() == 1

        registry.register("client-2", object())
        assert registry.get_count() == 2

        registry.unregister("client-1")
        assert registry.get_count() == 1

    def test_get_all_clients(self):
        """Test retrieving all clients."""
        registry = ClientRegistry()
        ws1 = object()
        ws2 = object()

        registry.register("client-1", ws1)
        registry.register("client-2", ws2)

        clients = registry.get_all_clients()
        assert len(clients) == 2
        assert clients["client-1"] == ws1
        assert clients["client-2"] == ws2

    def test_thread_safety(self):
        """Test thread-safe operations on registry."""
        import threading
        import uuid

        registry = ClientRegistry()
        counter = {"value": 0}
        lock = threading.Lock()

        def register_clients():
            for i in range(10):
                client_id = str(uuid.uuid4())
                registry.register(client_id, object())
                with lock:
                    counter["value"] += 1

        threads = [threading.Thread(target=register_clients) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert registry.get_count() == 50
        assert counter["value"] == 50

    def test_subscribe_client_to_channel(self):
        """Test subscribing a client to a channel."""
        registry = ClientRegistry()
        client_id = "client-1"
        registry.register(client_id, object())

        registry.subscribe(client_id, "alerts")
        subscribers = registry.get_channel_subscribers("alerts")
        assert client_id in subscribers

    def test_unsubscribe_client_from_channel(self):
        """Test unsubscribing a client from a channel."""
        registry = ClientRegistry()
        client_id = "client-1"
        registry.register(client_id, object())

        registry.subscribe(client_id, "alerts")
        registry.unsubscribe(client_id, "alerts")
        subscribers = registry.get_channel_subscribers("alerts")
        assert client_id not in subscribers

    def test_multiple_subscribers_to_channel(self):
        """Test multiple clients subscribing to the same channel."""
        registry = ClientRegistry()

        for i in range(3):
            client_id = f"client-{i}"
            registry.register(client_id, object())
            registry.subscribe(client_id, "alerts")

        subscribers = registry.get_channel_subscribers("alerts")
        assert len(subscribers) == 3
        assert all(f"client-{i}" in subscribers for i in range(3))

    def test_client_multiple_channels(self):
        """Test a client subscribing to multiple channels."""
        registry = ClientRegistry()
        client_id = "client-1"
        registry.register(client_id, object())

        registry.subscribe(client_id, "alerts")
        registry.subscribe(client_id, "system")
        registry.subscribe(client_id, "chat")

        assert client_id in registry.get_channel_subscribers("alerts")
        assert client_id in registry.get_channel_subscribers("system")
        assert client_id in registry.get_channel_subscribers("chat")

    def test_get_active_channels(self):
        """Test getting active channels and subscriber counts."""
        registry = ClientRegistry()

        for i in range(3):
            client_id = f"client-{i}"
            registry.register(client_id, object())

        for i in range(2):
            client_id = f"client-{i}"
            registry.subscribe(client_id, "alerts")

        for i in range(3):
            client_id = f"client-{i}"
            registry.subscribe(client_id, "system")

        channels = registry.get_active_channels()
        assert channels["alerts"] == 2
        assert channels["system"] == 3

    def test_get_active_channels_empty(self):
        """Test getting active channels when none exist."""
        registry = ClientRegistry()
        registry.register("client-1", object())

        channels = registry.get_active_channels()
        assert len(channels) == 0

    def test_unsubscribe_nonexistent_channel(self):
        """Test unsubscribing from a non-existent channel."""
        registry = ClientRegistry()
        client_id = "client-1"
        registry.register(client_id, object())

        registry.unsubscribe(client_id, "nonexistent")

    def test_get_channel_subscribers_empty(self):
        """Test getting subscribers for a channel with no subscribers."""
        registry = ClientRegistry()

        subscribers = registry.get_channel_subscribers("empty-channel")
        assert len(subscribers) == 0


@pytest.mark.asyncio
class TestNotificationServer:
    """Tests for the NotificationServer class."""

    @pytest.fixture
    def server(self):
        """Create a test server instance."""
        server = NotificationServer(host="localhost", ws_port=8765, http_port=8080)
        return server

    async def test_broadcast_message(self, server):
        """Test broadcasting a message."""
        ws1 = AsyncMockWebSocket()
        ws2 = AsyncMockWebSocket()

        server.registry.register("client-1", ws1)
        server.registry.register("client-2", ws2)

        message = {
            "type": "broadcast",
            "payload": {"content": "hello"},
            "timestamp": "2024-01-01T00:00:00+00:00",
        }

        await server.broadcast(message)

        assert len(ws1.sent_messages) == 1
        assert len(ws2.sent_messages) == 1

        received = json.loads(ws1.sent_messages[0])
        assert received["type"] == "broadcast"
        assert received["payload"]["content"] == "hello"

    async def test_broadcast_exclude(self, server):
        """Test broadcasting with exclusion."""
        ws1 = AsyncMockWebSocket()
        ws2 = AsyncMockWebSocket()

        server.registry.register("client-1", ws1)
        server.registry.register("client-2", ws2)

        message = {
            "type": "broadcast",
            "payload": {"content": "hello"},
            "timestamp": "2024-01-01T00:00:00+00:00",
        }

        await server.broadcast(message, exclude="client-1")

        assert len(ws1.sent_messages) == 0
        assert len(ws2.sent_messages) == 1

    async def test_send_direct(self, server):
        """Test sending a direct message to a client."""
        ws1 = AsyncMockWebSocket()
        ws2 = AsyncMockWebSocket()

        server.registry.register("client-1", ws1)
        server.registry.register("client-2", ws2)

        message = {
            "type": "direct",
            "payload": {"from": "client-1", "message": "hello"},
            "timestamp": "2024-01-01T00:00:00+00:00",
        }

        await server.send_direct("client-2", message)

        assert len(ws1.sent_messages) == 0
        assert len(ws2.sent_messages) == 1

        received = json.loads(ws2.sent_messages[0])
        assert received["type"] == "direct"

    async def test_send_direct_nonexistent_client(self, server):
        """Test sending to a non-existent client."""
        message = {
            "type": "direct",
            "payload": {"from": "client-1", "message": "hello"},
            "timestamp": "2024-01-01T00:00:00+00:00",
        }

        await server.send_direct("nonexistent-client", message)

    async def test_handle_message_broadcast_type(self, server):
        """Test handling a broadcast message from a client."""
        ws1 = AsyncMockWebSocket()
        ws2 = AsyncMockWebSocket()

        server.registry.register("client-1", ws1)
        server.registry.register("client-2", ws2)

        raw_message = json.dumps({
            "type": "broadcast",
            "payload": {"content": "hello from client-1"},
        })

        await server._handle_message("client-1", raw_message)

        # Client 1 shouldn't receive their own broadcast
        assert len(ws1.sent_messages) == 0
        # Client 2 should receive it
        assert len(ws2.sent_messages) == 1

    async def test_handle_message_direct_type(self, server):
        """Test handling a direct message from a client."""
        ws1 = AsyncMockWebSocket()
        ws2 = AsyncMockWebSocket()

        server.registry.register("client-1", ws1)
        server.registry.register("client-2", ws2)

        raw_message = json.dumps({
            "type": "direct",
            "payload": {
                "target_id": "client-2",
                "message": "hello client-2",
            },
        })

        await server._handle_message("client-1", raw_message)

        assert len(ws2.sent_messages) == 1
        received = json.loads(ws2.sent_messages[0])
        assert received["type"] == "direct"
        assert received["payload"]["from"] == "client-1"

    async def test_handle_message_invalid_json(self, server):
        """Test handling invalid JSON message."""
        ws = AsyncMockWebSocket()
        server.registry.register("client-1", ws)

        await server._handle_message("client-1", "invalid json {")

    async def test_send_safe_closed_connection(self, server):
        """Test sending to a closed connection."""
        ws = AsyncMockWebSocketClosed()

        await server._send_safe(ws, json.dumps({"type": "test"}))

    async def test_broadcast_empty_clients(self, server):
        """Test broadcasting with no connected clients."""
        message = {
            "type": "broadcast",
            "payload": {"content": "hello"},
            "timestamp": "2024-01-01T00:00:00+00:00",
        }

        await server.broadcast(message)

    async def test_handle_subscribe_message(self, server):
        """Test handling a subscribe message from a client."""
        ws = AsyncMockWebSocket()
        server.registry.register("client-1", ws)

        raw_message = json.dumps({
            "type": "subscribe",
            "payload": {"channel": "alerts"},
        })

        await server._handle_message("client-1", raw_message)

        subscribers = server.registry.get_channel_subscribers("alerts")
        assert "client-1" in subscribers

    async def test_handle_unsubscribe_message(self, server):
        """Test handling an unsubscribe message from a client."""
        ws = AsyncMockWebSocket()
        server.registry.register("client-1", ws)
        server.registry.subscribe("client-1", "alerts")

        raw_message = json.dumps({
            "type": "unsubscribe",
            "payload": {"channel": "alerts"},
        })

        await server._handle_message("client-1", raw_message)

        subscribers = server.registry.get_channel_subscribers("alerts")
        assert "client-1" not in subscribers

    async def test_broadcast_to_channel(self, server):
        """Test broadcasting a message to a specific channel."""
        ws1 = AsyncMockWebSocket()
        ws2 = AsyncMockWebSocket()
        ws3 = AsyncMockWebSocket()

        server.registry.register("client-1", ws1)
        server.registry.register("client-2", ws2)
        server.registry.register("client-3", ws3)

        server.registry.subscribe("client-1", "alerts")
        server.registry.subscribe("client-2", "alerts")
        server.registry.subscribe("client-3", "system")

        message = {
            "type": "broadcast",
            "payload": {"content": "alert"},
            "timestamp": "2024-01-01T00:00:00+00:00",
        }

        await server.broadcast(message, channel="alerts")

        assert len(ws1.sent_messages) == 1
        assert len(ws2.sent_messages) == 1
        assert len(ws3.sent_messages) == 0

    async def test_broadcast_without_channel(self, server):
        """Test broadcasting to all clients (no channel specified)."""
        ws1 = AsyncMockWebSocket()
        ws2 = AsyncMockWebSocket()

        server.registry.register("client-1", ws1)
        server.registry.register("client-2", ws2)

        server.registry.subscribe("client-1", "alerts")
        server.registry.subscribe("client-2", "system")

        message = {
            "type": "broadcast",
            "payload": {"content": "hello"},
            "timestamp": "2024-01-01T00:00:00+00:00",
        }

        await server.broadcast(message, channel=None)

        assert len(ws1.sent_messages) == 1
        assert len(ws2.sent_messages) == 1

    async def test_broadcast_to_channel_with_exclude(self, server):
        """Test broadcasting to a channel with sender exclusion."""
        ws1 = AsyncMockWebSocket()
        ws2 = AsyncMockWebSocket()

        server.registry.register("client-1", ws1)
        server.registry.register("client-2", ws2)

        server.registry.subscribe("client-1", "alerts")
        server.registry.subscribe("client-2", "alerts")

        message = {
            "type": "broadcast",
            "payload": {"content": "alert"},
            "timestamp": "2024-01-01T00:00:00+00:00",
        }

        await server.broadcast(message, channel="alerts", exclude="client-1")

        assert len(ws1.sent_messages) == 0
        assert len(ws2.sent_messages) == 1

    async def test_handle_message_broadcast_with_channel(self, server):
        """Test handling a broadcast message with channel field."""
        ws1 = AsyncMockWebSocket()
        ws2 = AsyncMockWebSocket()

        server.registry.register("client-1", ws1)
        server.registry.register("client-2", ws2)

        server.registry.subscribe("client-1", "alerts")
        server.registry.subscribe("client-2", "system")

        raw_message = json.dumps({
            "type": "broadcast",
            "channel": "alerts",
            "payload": {"content": "alert message"},
        })

        await server._handle_message("client-1", raw_message)

        assert len(ws1.sent_messages) == 0
        assert len(ws2.sent_messages) == 0


class TestNotificationServerHTTP(AioHTTPTestCase):
    """Tests for the HTTP endpoints."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.notification_server = NotificationServer(host="localhost", ws_port=8765, http_port=8080)

    async def get_application(self):
        """Create the test application."""
        return self.notification_server.http_app

    async def test_health_endpoint_empty(self):
        """Test health endpoint with no connected clients."""
        resp = await self.client.request("GET", "/health")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "healthy"
        assert data["connected_clients"] == 0
        assert "timestamp" in data

    async def test_health_endpoint_with_clients(self):
        """Test health endpoint with connected clients."""
        # Simulate connected clients
        ws1 = AsyncMockWebSocket()
        ws2 = AsyncMockWebSocket()
        self.notification_server.registry.register("client-1", ws1)
        self.notification_server.registry.register("client-2", ws2)

        resp = await self.client.request("GET", "/health")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "healthy"
        assert data["connected_clients"] == 2

    async def test_channels_endpoint_empty(self):
        """Test channels endpoint with no active channels."""
        resp = await self.client.request("GET", "/channels")
        assert resp.status == 200
        data = await resp.json()
        assert data["channels"] == {}
        assert "timestamp" in data

    async def test_channels_endpoint_with_channels(self):
        """Test channels endpoint with active channels."""
        ws1 = AsyncMockWebSocket()
        ws2 = AsyncMockWebSocket()
        ws3 = AsyncMockWebSocket()

        self.notification_server.registry.register("client-1", ws1)
        self.notification_server.registry.register("client-2", ws2)
        self.notification_server.registry.register("client-3", ws3)

        self.notification_server.registry.subscribe("client-1", "alerts")
        self.notification_server.registry.subscribe("client-2", "alerts")
        self.notification_server.registry.subscribe("client-3", "system")

        resp = await self.client.request("GET", "/channels")
        assert resp.status == 200
        data = await resp.json()
        assert data["channels"]["alerts"] == 2
        assert data["channels"]["system"] == 1

    async def test_channel_subscribers_endpoint(self):
        """Test channel subscribers endpoint."""
        ws1 = AsyncMockWebSocket()
        ws2 = AsyncMockWebSocket()

        self.notification_server.registry.register("client-1", ws1)
        self.notification_server.registry.register("client-2", ws2)

        self.notification_server.registry.subscribe("client-1", "alerts")
        self.notification_server.registry.subscribe("client-2", "alerts")

        resp = await self.client.request("GET", "/channels/alerts/subscribers")
        assert resp.status == 200
        data = await resp.json()
        assert data["channel"] == "alerts"
        assert len(data["subscribers"]) == 2
        assert data["count"] == 2
        assert "client-1" in data["subscribers"]
        assert "client-2" in data["subscribers"]

    async def test_channel_subscribers_endpoint_no_subscribers(self):
        """Test channel subscribers endpoint for non-existent channel."""
        resp = await self.client.request("GET", "/channels/nonexistent/subscribers")
        assert resp.status == 200
        data = await resp.json()
        assert data["channel"] == "nonexistent"
        assert data["subscribers"] == []
        assert data["count"] == 0


class AsyncMockWebSocket:
    """Mock WebSocket for testing."""

    def __init__(self):
        self.sent_messages = []

    async def send(self, message: str):
        """Mock send method."""
        self.sent_messages.append(message)


class AsyncMockWebSocketClosed:
    """Mock WebSocket that simulates a closed connection."""

    async def send(self, message: str):
        """Raise ConnectionClosed exception."""
        raise ConnectionClosed(None, None)


@pytest.mark.asyncio
async def test_message_format():
    """Test that messages have the correct format."""
    server = NotificationServer()

    ws = AsyncMockWebSocket()
    server.registry.register("client-1", ws)

    message = {
        "type": "broadcast",
        "payload": {"content": "test"},
        "timestamp": "2024-01-01T00:00:00+00:00",
    }

    await server.broadcast(message)

    sent = json.loads(ws.sent_messages[0])
    assert "type" in sent
    assert "payload" in sent
    assert "timestamp" in sent
    assert sent["type"] in ["broadcast", "direct", "system"]


@pytest.mark.asyncio
async def test_system_messages_format():
    """Test that system messages have correct format."""
    server = NotificationServer()

    ws = AsyncMockWebSocket()
    server.registry.register("client-1", ws)

    message = {
        "type": "system",
        "payload": {"message": "Client connected", "client_id": "client-1"},
        "timestamp": "2024-01-01T00:00:00+00:00",
    }

    await server.broadcast(message)

    sent = json.loads(ws.sent_messages[0])
    assert sent["type"] == "system"
    assert "message" in sent["payload"]
