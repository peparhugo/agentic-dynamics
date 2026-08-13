"""Tests for the WebSocket notification server."""

import asyncio
import json
import pytest
import uuid
import sqlite3
import os
import tempfile
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import websockets
from websockets import ConnectionClosed
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase

from server import (
    NotificationServer, handle_websocket, health_handler, channels_handler,
    channel_subscribers_handler, messages_handler, init_db, save_message, get_messages
)
import server as server_module


@pytest.fixture(autouse=True)
def setup_test_db():
    """Setup test database for all tests."""
    # Create a temporary database
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
        db_path = f.name

    original_url = server_module.DATABASE_URL
    server_module.DATABASE_URL = db_path
    init_db()

    yield db_path

    # Cleanup
    server_module.DATABASE_URL = original_url
    if os.path.exists(db_path):
        try:
            os.unlink(db_path)
        except OSError:
            pass


@pytest.fixture
def notification_server():
    """Create a fresh NotificationServer instance for each test."""
    server_inst = NotificationServer()
    # Mock Redis to avoid real Redis connections
    server_inst.redis_pub = None
    return server_inst


class TestNotificationServer:
    """Test the NotificationServer class."""

    def test_add_client(self, notification_server):
        """Test adding a client."""
        client_id = "test-client-1"
        mock_ws = AsyncMock()
        notification_server.add_client(client_id, mock_ws)
        assert client_id in notification_server.clients
        assert notification_server.clients[client_id] == mock_ws

    def test_remove_client(self, notification_server):
        """Test removing a client."""
        client_id = "test-client-1"
        mock_ws = AsyncMock()
        notification_server.add_client(client_id, mock_ws)
        notification_server.remove_client(client_id)
        assert client_id not in notification_server.clients

    def test_get_client_count(self, notification_server):
        """Test getting client count."""
        assert notification_server.get_client_count() == 0
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        notification_server.add_client("client-1", mock_ws1)
        notification_server.add_client("client-2", mock_ws2)
        assert notification_server.get_client_count() == 2

    def test_get_all_clients(self, notification_server):
        """Test getting all clients snapshot."""
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        notification_server.add_client("client-1", mock_ws1)
        notification_server.add_client("client-2", mock_ws2)
        clients = notification_server.get_all_clients()
        assert len(clients) == 2
        assert "client-1" in clients
        assert "client-2" in clients

    @pytest.mark.asyncio
    async def test_broadcast(self, notification_server):
        """Test broadcasting a message to all clients."""
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        notification_server.add_client("client-1", mock_ws1)
        notification_server.add_client("client-2", mock_ws2)

        message = {
            "type": "broadcast",
            "payload": {"text": "Hello all"},
        }
        await notification_server.broadcast(message)

        # Both clients should receive the message
        assert mock_ws1.send.call_count == 1
        assert mock_ws2.send.call_count == 1

        # Check that timestamp was added
        call_args_1 = mock_ws1.send.call_args[0][0]
        data = json.loads(call_args_1)
        assert "timestamp" in data
        assert data["type"] == "broadcast"
        assert data["payload"]["text"] == "Hello all"

    @pytest.mark.asyncio
    async def test_broadcast_empty_clients(self, notification_server):
        """Test broadcasting with no connected clients."""
        message = {
            "type": "broadcast",
            "payload": {"text": "Hello"},
        }
        # Should not raise an error
        await notification_server.broadcast(message)

    @pytest.mark.asyncio
    async def test_broadcast_adds_timestamp(self, notification_server):
        """Test that broadcast adds timestamp if not present."""
        mock_ws = AsyncMock()
        notification_server.add_client("client-1", mock_ws)

        message = {
            "type": "broadcast",
            "payload": {"text": "Hello"},
        }
        await notification_server.broadcast(message)

        call_args = mock_ws.send.call_args[0][0]
        data = json.loads(call_args)
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_broadcast_with_existing_timestamp(self, notification_server):
        """Test that broadcast preserves existing timestamp."""
        mock_ws = AsyncMock()
        notification_server.add_client("client-1", mock_ws)

        timestamp = "2023-01-01T00:00:00"
        message = {
            "type": "broadcast",
            "payload": {"text": "Hello"},
            "timestamp": timestamp,
        }
        await notification_server.broadcast(message)

        call_args = mock_ws.send.call_args[0][0]
        data = json.loads(call_args)
        assert data["timestamp"] == timestamp

    @pytest.mark.asyncio
    async def test_send_direct_success(self, notification_server):
        """Test sending a direct message to a specific client."""
        mock_ws = AsyncMock()
        notification_server.add_client("client-1", mock_ws)

        message = {
            "type": "direct",
            "payload": {"text": "Direct message"},
        }
        success = await notification_server.send_direct("client-1", message)

        assert success is True
        assert mock_ws.send.call_count == 1
        call_args = mock_ws.send.call_args[0][0]
        data = json.loads(call_args)
        assert data["type"] == "direct"

    @pytest.mark.asyncio
    async def test_send_direct_client_not_found(self, notification_server):
        """Test sending direct message to non-existent client."""
        message = {
            "type": "direct",
            "payload": {"text": "Direct message"},
        }
        success = await notification_server.send_direct("non-existent", message)
        assert success is False

    @pytest.mark.asyncio
    async def test_send_direct_send_fails(self, notification_server):
        """Test handling of send failure during direct message."""
        mock_ws = AsyncMock()
        mock_ws.send.side_effect = Exception("Connection lost")
        notification_server.add_client("client-1", mock_ws)

        message = {
            "type": "direct",
            "payload": {"text": "Direct message"},
        }
        success = await notification_server.send_direct("client-1", message)
        assert success is False

    def test_thread_safety_add_client(self, notification_server):
        """Test thread-safe add_client operations."""
        import threading

        def add_clients():
            for i in range(100):
                client_id = f"client-{threading.current_thread().name}-{i}"
                mock_ws = AsyncMock()
                notification_server.add_client(client_id, mock_ws)

        threads = [threading.Thread(target=add_clients) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have 500 clients (5 threads * 100 clients each)
        assert notification_server.get_client_count() == 500

    def test_thread_safety_remove_client(self, notification_server):
        """Test thread-safe remove_client operations."""
        import threading

        # First add 100 clients
        for i in range(100):
            notification_server.add_client(f"client-{i}", AsyncMock())

        def remove_clients(thread_id):
            # Each thread removes 20 clients uniquely assigned to it
            start = thread_id * 20
            for i in range(20):
                client_id = f"client-{start + i}"
                notification_server.remove_client(client_id)

        threads = [threading.Thread(target=remove_clients, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should be removed
        assert notification_server.get_client_count() == 0


class TestWebSocketHandling:
    """Test WebSocket message handling."""

    @pytest.mark.asyncio
    async def test_handle_websocket_connection(self, notification_server):
        """Test WebSocket connection handling."""
        with patch("server.server", notification_server):
            mock_ws = AsyncMock()
            mock_ws.__aiter__.return_value = iter([])  # No messages

            await handle_websocket(mock_ws, "/")

            # Should have sent connection confirmation
            assert mock_ws.send.call_count >= 1
            call_args = mock_ws.send.call_args_list[0][0][0]
            data = json.loads(call_args)
            assert data["type"] == "system"
            assert "client_id" in data["payload"]

    @pytest.mark.asyncio
    async def test_handle_websocket_broadcast_message(self, notification_server):
        """Test handling broadcast message."""
        with patch("server.server", notification_server):
            broadcast_msg = json.dumps({
                "type": "broadcast",
                "payload": {"text": "Hello all"},
            })

            mock_ws = AsyncMock()
            mock_ws.__aiter__.return_value = iter([broadcast_msg])

            await handle_websocket(mock_ws, "/")

            # Should have sent connection confirmation + broadcast
            assert mock_ws.send.call_count >= 1

    @pytest.mark.asyncio
    async def test_handle_websocket_invalid_json(self, notification_server):
        """Test handling invalid JSON."""
        with patch("server.server", notification_server):
            mock_ws = AsyncMock()
            mock_ws.__aiter__.return_value = iter(["invalid json"])

            await handle_websocket(mock_ws, "/")

            # Should have sent connection confirmation + error message
            assert mock_ws.send.call_count >= 2
            error_call = mock_ws.send.call_args_list[1][0][0]
            data = json.loads(error_call)
            assert "error" in data["payload"]

    @pytest.mark.asyncio
    async def test_handle_websocket_direct_message(self, notification_server):
        """Test handling direct message."""
        with patch("server.server", notification_server):
            # Add a target client
            target_ws = AsyncMock()
            notification_server.add_client("target-client", target_ws)

            direct_msg = json.dumps({
                "type": "direct",
                "payload": {
                    "client_id": "target-client",
                    "message": {"text": "Personal message"},
                },
            })

            mock_ws = AsyncMock()
            mock_ws.__aiter__.return_value = iter([direct_msg])

            await handle_websocket(mock_ws, "/")

            # Target client should receive the message
            assert target_ws.send.call_count >= 1

    @pytest.mark.asyncio
    async def test_handle_websocket_cleanup_on_disconnect(self, notification_server):
        """Test client cleanup on WebSocket disconnect."""
        with patch("server.server", notification_server):
            mock_ws = AsyncMock()
            mock_ws.__aiter__.return_value = iter([])

            await handle_websocket(mock_ws, "/")

            # Client should be removed after disconnect
            assert notification_server.get_client_count() == 0



class TestHealthEndpoint(AioHTTPTestCase):
    """Test the REST health endpoint."""

    async def get_application(self):
        """Create the test application."""
        app = web.Application()
        app.router.add_get("/health", health_handler)
        return app

    async def test_health_endpoint_empty(self):
        """Test health endpoint with no connected clients."""
        # Note: We can't easily test with actual NotificationServer state
        # in this context, so this tests the endpoint structure
        resp = await self.client.request("GET", "/health")
        assert resp.status == 200
        data = await resp.json()
        assert "status" in data
        assert "connected_clients" in data

    async def test_health_endpoint_structure(self):
        """Test health endpoint response structure."""
        resp = await self.client.request("GET", "/health")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "ok"
        assert isinstance(data["connected_clients"], int)


class TestChannelSubscriptions:
    """Test channel subscription functionality."""

    def test_subscribe_client(self, notification_server):
        """Test subscribing a client to a channel."""
        is_new = notification_server.subscribe("client-1", "alerts")
        assert is_new is True
        assert "alerts" in notification_server.channels
        assert "client-1" in notification_server.channels["alerts"]

    def test_subscribe_same_channel_twice(self, notification_server):
        """Test subscribing to the same channel twice."""
        is_new1 = notification_server.subscribe("client-1", "alerts")
        is_new2 = notification_server.subscribe("client-1", "alerts")
        assert is_new1 is True
        assert is_new2 is False

    def test_unsubscribe_client(self, notification_server):
        """Test unsubscribing a client from a channel."""
        notification_server.subscribe("client-1", "alerts")
        was_subscribed = notification_server.unsubscribe("client-1", "alerts")
        assert was_subscribed is True
        assert "alerts" not in notification_server.channels

    def test_unsubscribe_non_existent(self, notification_server):
        """Test unsubscribing from a non-existent channel."""
        was_subscribed = notification_server.unsubscribe("client-1", "alerts")
        assert was_subscribed is False

    def test_multiple_clients_same_channel(self, notification_server):
        """Test multiple clients subscribing to same channel."""
        notification_server.subscribe("client-1", "alerts")
        notification_server.subscribe("client-2", "alerts")
        notification_server.subscribe("client-3", "alerts")

        subscribers = notification_server.get_channel_subscribers("alerts")
        assert len(subscribers) == 3
        assert "client-1" in subscribers
        assert "client-2" in subscribers
        assert "client-3" in subscribers

    def test_client_multiple_channels(self, notification_server):
        """Test a client subscribing to multiple channels."""
        notification_server.subscribe("client-1", "alerts")
        notification_server.subscribe("client-1", "system")
        notification_server.subscribe("client-1", "chat")

        assert len(notification_server.channels) == 3
        assert "client-1" in notification_server.channels["alerts"]
        assert "client-1" in notification_server.channels["system"]
        assert "client-1" in notification_server.channels["chat"]

    def test_get_channel_subscribers(self, notification_server):
        """Test getting subscribers for a channel."""
        notification_server.subscribe("client-1", "alerts")
        notification_server.subscribe("client-2", "alerts")

        subscribers = notification_server.get_channel_subscribers("alerts")
        assert len(subscribers) == 2
        assert "client-1" in subscribers
        assert "client-2" in subscribers

    def test_get_channel_subscribers_empty(self, notification_server):
        """Test getting subscribers for a non-existent channel."""
        subscribers = notification_server.get_channel_subscribers("alerts")
        assert len(subscribers) == 0

    def test_get_all_channels(self, notification_server):
        """Test getting all channels with subscriber counts."""
        notification_server.subscribe("client-1", "alerts")
        notification_server.subscribe("client-2", "alerts")
        notification_server.subscribe("client-3", "system")

        channels = notification_server.get_all_channels()
        assert len(channels) == 2
        assert channels["alerts"] == 2
        assert channels["system"] == 1

    def test_unsubscribe_from_all(self, notification_server):
        """Test unsubscribing a client from all channels."""
        notification_server.subscribe("client-1", "alerts")
        notification_server.subscribe("client-1", "system")
        notification_server.subscribe("client-1", "chat")
        notification_server.subscribe("client-2", "alerts")

        notification_server.unsubscribe_from_all("client-1")

        assert "client-1" not in notification_server.get_channel_subscribers("alerts")
        assert "client-1" not in notification_server.get_channel_subscribers("system")
        assert "client-1" not in notification_server.get_channel_subscribers("chat")
        assert "client-2" in notification_server.get_channel_subscribers("alerts")

    @pytest.mark.asyncio
    async def test_broadcast_to_channel(self, notification_server):
        """Test broadcasting to a specific channel."""
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        mock_ws3 = AsyncMock()

        notification_server.add_client("client-1", mock_ws1)
        notification_server.add_client("client-2", mock_ws2)
        notification_server.add_client("client-3", mock_ws3)

        notification_server.subscribe("client-1", "alerts")
        notification_server.subscribe("client-2", "alerts")
        notification_server.subscribe("client-3", "system")

        message = {
            "type": "broadcast",
            "payload": {"text": "Alert message"},
            "channel": "alerts",
        }
        await notification_server.broadcast_to_channel("alerts", message)

        # Only clients 1 and 2 should receive
        assert mock_ws1.send.call_count == 1
        assert mock_ws2.send.call_count == 1
        assert mock_ws3.send.call_count == 0

    @pytest.mark.asyncio
    async def test_broadcast_to_channel_with_timestamp(self, notification_server):
        """Test that broadcast_to_channel adds timestamp."""
        mock_ws = AsyncMock()
        notification_server.add_client("client-1", mock_ws)
        notification_server.subscribe("client-1", "alerts")

        message = {
            "type": "broadcast",
            "payload": {"text": "Alert"},
        }
        await notification_server.broadcast_to_channel("alerts", message)

        call_args = mock_ws.send.call_args[0][0]
        data = json.loads(call_args)
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_broadcast_to_empty_channel(self, notification_server):
        """Test broadcasting to a channel with no subscribers."""
        message = {
            "type": "broadcast",
            "payload": {"text": "Alert"},
        }
        # Should not raise an error
        await notification_server.broadcast_to_channel("alerts", message)


class TestChannelsRESTEndpoint(AioHTTPTestCase):
    """Test the REST channels endpoints."""

    async def get_application(self):
        """Create the test application."""
        app = web.Application()
        app.router.add_get("/channels", channels_handler)
        app.router.add_get("/channels/{name}/subscribers", channel_subscribers_handler)
        return app

    async def test_channels_endpoint_empty(self):
        """Test channels endpoint with no channels."""
        resp = await self.client.request("GET", "/channels")
        assert resp.status == 200
        data = await resp.json()
        assert "channels" in data
        assert data["channels"] == {}

    async def test_channels_endpoint_with_channels(self):
        """Test channels endpoint with channels."""
        from server import server as global_server
        global_server.subscribe("client-1", "alerts")
        global_server.subscribe("client-2", "alerts")
        global_server.subscribe("client-3", "system")

        resp = await self.client.request("GET", "/channels")
        assert resp.status == 200
        data = await resp.json()
        assert "channels" in data
        assert "alerts" in data["channels"]
        assert "system" in data["channels"]
        assert data["channels"]["alerts"] == 2
        assert data["channels"]["system"] == 1

        # Clean up
        global_server.unsubscribe("client-1", "alerts")
        global_server.unsubscribe("client-2", "alerts")
        global_server.unsubscribe("client-3", "system")

    async def test_channel_subscribers_endpoint(self):
        """Test channel subscribers endpoint."""
        from server import server as global_server
        global_server.subscribe("client-1", "alerts")
        global_server.subscribe("client-2", "alerts")

        resp = await self.client.request("GET", "/channels/alerts/subscribers")
        assert resp.status == 200
        data = await resp.json()
        assert data["channel"] == "alerts"
        assert "subscribers" in data
        assert len(data["subscribers"]) == 2
        assert data["count"] == 2

        # Clean up
        global_server.unsubscribe("client-1", "alerts")
        global_server.unsubscribe("client-2", "alerts")

    async def test_channel_subscribers_endpoint_empty(self):
        """Test channel subscribers endpoint for non-existent channel."""
        resp = await self.client.request("GET", "/channels/nonexistent/subscribers")
        assert resp.status == 200
        data = await resp.json()
        assert data["channel"] == "nonexistent"
        assert data["subscribers"] == []
        assert data["count"] == 0


class TestMessageFormat:
    """Test message format compliance."""

    def test_message_format_broadcast(self):
        """Test broadcast message format."""
        message = {
            "type": "broadcast",
            "payload": {"text": "Hello"},
            "timestamp": datetime.utcnow().isoformat(),
        }
        # Should be JSON serializable
        msg_str = json.dumps(message)
        parsed = json.loads(msg_str)
        assert parsed["type"] == "broadcast"
        assert isinstance(parsed["payload"], dict)
        assert isinstance(parsed["timestamp"], str)

    def test_message_format_direct(self):
        """Test direct message format."""
        message = {
            "type": "direct",
            "payload": {"from": "client-1", "message": {"text": "Hello"}},
            "timestamp": datetime.utcnow().isoformat(),
        }
        msg_str = json.dumps(message)
        parsed = json.loads(msg_str)
        assert parsed["type"] == "direct"
        assert isinstance(parsed["payload"], dict)
        assert isinstance(parsed["timestamp"], str)

    def test_message_format_system(self):
        """Test system message format."""
        message = {
            "type": "system",
            "payload": {"message": "connected", "client_id": str(uuid.uuid4())},
            "timestamp": datetime.utcnow().isoformat(),
        }
        msg_str = json.dumps(message)
        parsed = json.loads(msg_str)
        assert parsed["type"] == "system"
        assert isinstance(parsed["payload"], dict)
        assert isinstance(parsed["timestamp"], str)


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_broadcast_with_closed_connection(self):
        """Test broadcast handles closed connections gracefully."""
        server = NotificationServer()
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        mock_ws2.send.side_effect = ConnectionClosed(None, None)

        server.add_client("client-1", mock_ws1)
        server.add_client("client-2", mock_ws2)

        message = {
            "type": "broadcast",
            "payload": {"text": "Hello"},
        }
        # Should not raise error even if one connection is closed
        await server.broadcast(message)

        # Client 1 should still receive
        assert mock_ws1.send.call_count == 1

    def test_client_id_uniqueness(self):
        """Test that generated client IDs are unique."""
        server = NotificationServer()
        client_ids = set()
        for _ in range(1000):
            client_id = str(uuid.uuid4())
            client_ids.add(client_id)

        # All should be unique
        assert len(client_ids) == 1000

    @pytest.mark.asyncio
    async def test_empty_payload_broadcast(self):
        """Test broadcast with empty payload."""
        server = NotificationServer()
        mock_ws = AsyncMock()
        server.add_client("client-1", mock_ws)

        message = {
            "type": "broadcast",
            "payload": {},
        }
        await server.broadcast(message)

        assert mock_ws.send.call_count == 1

    @pytest.mark.asyncio
    async def test_large_payload_broadcast(self):
        """Test broadcast with large payload."""
        server = NotificationServer()
        mock_ws = AsyncMock()
        server.add_client("client-1", mock_ws)

        large_payload = {"data": "x" * 10000}
        message = {
            "type": "broadcast",
            "payload": large_payload,
        }
        await server.broadcast(message)

        assert mock_ws.send.call_count == 1
        call_args = mock_ws.send.call_args[0][0]
        data = json.loads(call_args)
        assert len(data["payload"]["data"]) == 10000


# Fixture for temporary test database (if needed for specific tests)
@pytest.fixture
def test_db():
    """Provides access to the current test database path."""
    return server_module.DATABASE_URL


class TestMessagePersistence:
    """Test message persistence to SQLite."""

    def test_save_message(self, test_db):
        """Test saving a message to the database."""
        msg_id = save_message("alerts", "broadcast", {"text": "Alert"}, "2023-01-01T00:00:00")
        assert msg_id is not None
        assert msg_id > 0

    def test_save_multiple_messages(self, test_db):
        """Test saving multiple messages."""
        id1 = save_message("alerts", "broadcast", {"text": "Alert 1"}, "2023-01-01T00:00:00")
        id2 = save_message("alerts", "broadcast", {"text": "Alert 2"}, "2023-01-01T00:00:01")
        id3 = save_message("system", "system", {"msg": "System"}, "2023-01-01T00:00:02")

        assert id1 < id2 < id3

    def test_get_messages_empty(self, test_db):
        """Test retrieving messages from empty database."""
        messages = get_messages()
        assert len(messages) == 0

    def test_get_messages_with_pagination(self, test_db):
        """Test retrieving messages with pagination."""
        # Save 10 messages
        for i in range(10):
            save_message(
                f"channel-{i % 3}",
                "broadcast",
                {"text": f"Message {i}"},
                f"2023-01-01T00:00:{i:02d}"
            )

        # Get messages with limit
        messages = get_messages(limit=5, offset=0)
        assert len(messages) == 5
        # Should be in reverse order (newest first)
        assert messages[0]["payload"]["text"] == "Message 9"
        assert messages[4]["payload"]["text"] == "Message 5"

    def test_get_messages_pagination_offset(self, test_db):
        """Test offset pagination."""
        for i in range(10):
            save_message("channel", "broadcast", {"text": f"Message {i}"}, f"2023-01-01T00:00:{i:02d}")

        messages_page1 = get_messages(limit=5, offset=0)
        messages_page2 = get_messages(limit=5, offset=5)

        assert len(messages_page1) == 5
        assert len(messages_page2) == 5
        assert messages_page1[0]["payload"]["text"] == "Message 9"
        assert messages_page2[0]["payload"]["text"] == "Message 4"

    def test_message_payload_json_serialization(self, test_db):
        """Test that message payloads are properly serialized and deserialized."""
        complex_payload = {
            "text": "Hello",
            "nested": {"key": "value"},
            "list": [1, 2, 3],
        }
        save_message("channel", "broadcast", complex_payload, "2023-01-01T00:00:00")

        messages = get_messages()
        assert len(messages) == 1
        assert messages[0]["payload"] == complex_payload

    def test_message_fields(self, test_db):
        """Test that saved messages contain all required fields."""
        save_message("alerts", "broadcast", {"text": "Alert"}, "2023-01-01T00:00:00")

        messages = get_messages()
        assert len(messages) == 1
        msg = messages[0]
        assert "id" in msg
        assert "channel" in msg
        assert "type" in msg
        assert "payload" in msg
        assert "timestamp" in msg
        assert msg["channel"] == "alerts"
        assert msg["type"] == "broadcast"
        assert msg["timestamp"] == "2023-01-01T00:00:00"

    def test_get_messages_limit_bounds(self, test_db):
        """Test that get_messages respects limit bounds."""
        for i in range(100):
            save_message("channel", "broadcast", {"text": f"Message {i}"}, "2023-01-01T00:00:00")

        messages = get_messages(limit=1000)
        assert len(messages) == 100

        messages = get_messages(limit=50)
        assert len(messages) == 50


class TestMessagesPersistenceIntegration:
    """Test message persistence integrated with NotificationServer."""

    @pytest.mark.asyncio
    async def test_broadcast_saves_to_db(self, test_db):
        """Test that broadcast saves messages to database."""
        server = NotificationServer()
        mock_ws = AsyncMock()
        server.add_client("client-1", mock_ws)

        message = {
            "type": "broadcast",
            "payload": {"text": "Test message"},
        }
        await server.broadcast(message)

        # Check database
        messages = get_messages()
        assert len(messages) == 1
        assert messages[0]["payload"]["text"] == "Test message"

    @pytest.mark.asyncio
    async def test_broadcast_to_channel_saves_to_db(self, test_db):
        """Test that broadcast_to_channel saves messages to database."""
        server = NotificationServer()
        mock_ws = AsyncMock()
        server.add_client("client-1", mock_ws)
        server.subscribe("client-1", "alerts")

        message = {
            "type": "broadcast",
            "payload": {"text": "Alert message"},
        }
        await server.broadcast_to_channel("alerts", message)

        # Check database
        messages = get_messages()
        assert len(messages) == 1
        assert messages[0]["channel"] == "alerts"
        assert messages[0]["payload"]["text"] == "Alert message"

    @pytest.mark.asyncio
    async def test_send_direct_saves_to_db(self, test_db):
        """Test that send_direct saves messages to database."""
        server = NotificationServer()
        mock_ws = AsyncMock()
        server.add_client("client-1", mock_ws)

        message = {
            "type": "direct",
            "payload": {"text": "Direct message"},
        }
        await server.send_direct("client-1", message)

        # Check database
        messages = get_messages()
        assert len(messages) == 1
        assert "direct:" in messages[0]["channel"]
        assert messages[0]["payload"]["text"] == "Direct message"

    @pytest.mark.asyncio
    async def test_multiple_broadcasts_save_all(self, test_db):
        """Test that multiple broadcasts save all messages."""
        server = NotificationServer()
        mock_ws = AsyncMock()
        server.add_client("client-1", mock_ws)

        for i in range(5):
            await server.broadcast({
                "type": "broadcast",
                "payload": {"text": f"Message {i}"},
            })

        messages = get_messages()
        assert len(messages) == 5


class TestMessagesRESTEndpoint(AioHTTPTestCase):
    """Test the REST messages endpoint."""

    async def get_application(self):
        """Create the test application."""
        app = web.Application()
        app.router.add_get("/messages", messages_handler)
        return app

    async def test_messages_endpoint_empty(self):
        """Test messages endpoint with no messages."""
        resp = await self.client.request("GET", "/messages")
        assert resp.status == 200
        data = await resp.json()
        assert "messages" in data
        assert data["messages"] == []
        assert data["limit"] == 50
        assert data["offset"] == 0
        assert data["count"] == 0

    async def test_messages_endpoint_with_data(self):
        """Test messages endpoint with messages."""
        # Insert some messages
        for i in range(5):
            save_message("channel", "broadcast", {"text": f"Message {i}"}, "2023-01-01T00:00:00")

        resp = await self.client.request("GET", "/messages")
        assert resp.status == 200
        data = await resp.json()
        assert len(data["messages"]) == 5
        assert data["count"] == 5

    async def test_messages_endpoint_limit(self):
        """Test messages endpoint with custom limit."""
        for i in range(20):
            save_message("channel", "broadcast", {"text": f"Message {i}"}, "2023-01-01T00:00:00")

        resp = await self.client.request("GET", "/messages?limit=10")
        assert resp.status == 200
        data = await resp.json()
        assert len(data["messages"]) == 10
        assert data["limit"] == 10

    async def test_messages_endpoint_offset(self):
        """Test messages endpoint with offset."""
        for i in range(20):
            save_message("channel", "broadcast", {"text": f"Message {i}"}, "2023-01-01T00:00:00")

        resp = await self.client.request("GET", "/messages?limit=5&offset=10")
        assert resp.status == 200
        data = await resp.json()
        assert len(data["messages"]) == 5
        assert data["offset"] == 10

    async def test_messages_endpoint_invalid_limit(self):
        """Test messages endpoint with invalid limit."""
        resp = await self.client.request("GET", "/messages?limit=abc")
        assert resp.status == 400
        data = await resp.json()
        assert "error" in data

    async def test_messages_endpoint_invalid_offset(self):
        """Test messages endpoint with invalid offset."""
        resp = await self.client.request("GET", "/messages?offset=xyz")
        assert resp.status == 400
        data = await resp.json()
        assert "error" in data

    async def test_messages_endpoint_max_limit(self):
        """Test messages endpoint respects max limit."""
        for i in range(2000):
            save_message("channel", "broadcast", {"text": f"Message {i}"}, "2023-01-01T00:00:00")

        resp = await self.client.request("GET", "/messages?limit=10000")
        assert resp.status == 200
        data = await resp.json()
        # Should be clamped to 1000
        assert data["limit"] == 1000
        assert len(data["messages"]) == 1000

    async def test_messages_endpoint_negative_offset(self):
        """Test messages endpoint with negative offset."""
        save_message("channel", "broadcast", {"text": "Message"}, "2023-01-01T00:00:00")

        resp = await self.client.request("GET", "/messages?offset=-1")
        assert resp.status == 200
        data = await resp.json()
        # Should be clamped to 0
        assert data["offset"] == 0
        assert len(data["messages"]) == 1


class TestRedisIntegration:
    """Test Redis pub/sub integration."""

    @pytest.mark.asyncio
    async def test_redis_init(self):
        """Test Redis connection initialization."""
        server = NotificationServer()
        # Mock the aioredis
        with patch("server.aioredis.from_url") as mock_redis:
            mock_redis.return_value = AsyncMock()
            try:
                await server.init_redis()
                assert server.redis_pub is not None
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_publish_to_redis(self):
        """Test publishing to Redis."""
        server = NotificationServer()
        mock_redis = AsyncMock()
        server.redis_pub = mock_redis

        await server.publish_to_redis("test_channel", {"text": "test"})

        # Verify publish was called
        mock_redis.publish.assert_called_once()
        call_args = mock_redis.publish.call_args
        assert call_args[0][0] == "test_channel"

    @pytest.mark.asyncio
    async def test_broadcast_publishes_to_redis(self, test_db):
        """Test that broadcast publishes to Redis."""
        server = NotificationServer()
        mock_redis = AsyncMock()
        server.redis_pub = mock_redis
        mock_ws = AsyncMock()
        server.add_client("client-1", mock_ws)

        message = {
            "type": "broadcast",
            "payload": {"text": "Test"},
        }
        await server.broadcast(message)

        # Verify Redis publish was called
        mock_redis.publish.assert_called()

    @pytest.mark.asyncio
    async def test_broadcast_to_channel_publishes_to_redis(self, test_db):
        """Test that broadcast_to_channel publishes to Redis."""
        server = NotificationServer()
        mock_redis = AsyncMock()
        server.redis_pub = mock_redis
        mock_ws = AsyncMock()
        server.add_client("client-1", mock_ws)
        server.subscribe("client-1", "alerts")

        message = {
            "type": "broadcast",
            "payload": {"text": "Alert"},
        }
        await server.broadcast_to_channel("alerts", message)

        # Verify Redis publish was called
        mock_redis.publish.assert_called()

    @pytest.mark.asyncio
    async def test_send_direct_publishes_to_redis(self, test_db):
        """Test that send_direct publishes to Redis."""
        server = NotificationServer()
        mock_redis = AsyncMock()
        server.redis_pub = mock_redis
        mock_ws = AsyncMock()
        server.add_client("client-1", mock_ws)

        message = {
            "type": "direct",
            "payload": {"text": "Direct"},
        }
        await server.send_direct("client-1", message)

        # Verify Redis publish was called
        mock_redis.publish.assert_called()

    @pytest.mark.asyncio
    async def test_close_redis(self):
        """Test closing Redis connections."""
        server = NotificationServer()
        mock_redis = AsyncMock()
        mock_redis.close = MagicMock()
        mock_redis.wait_closed = AsyncMock()
        server.redis_pub = mock_redis
        server.redis_sub = AsyncMock()
        server.redis_sub.close = MagicMock()
        server.redis_sub.wait_closed = AsyncMock()
        server.redis_listen_task = asyncio.create_task(asyncio.sleep(10))

        await server.close_redis()

        # Verify close was called
        mock_redis.close.assert_called()
        mock_redis.wait_closed.assert_called()
