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
