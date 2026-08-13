"""
Test suite for the WebSocket notification server.

Tests cover:
- Client connection and disconnection
- Unique client ID assignment
- Message broadcasting
- Direct messaging
- Health endpoint
- Thread-safe client registry
- Error handling
"""

import asyncio
import json
import pytest
import pytest_asyncio
import websockets
from unittest.mock import Mock, patch, AsyncMock
from threading import Thread, Event
import time

from notification_server import (
    NotificationServer,
    NotificationMessage,
    ClientRegistry,
    create_server,
)


# ── Fixtures ────────────────────────────────────────────


@pytest_asyncio.fixture
async def server():
    """Create a test server instance."""
    srv = create_server(host="127.0.0.1", ws_port=8765, http_port=8080)
    yield srv


@pytest_asyncio.fixture
async def running_server():
    """Create and start a running server for integration tests."""
    srv = create_server(host="127.0.0.1", ws_port=9765, http_port=9080)

    async def run_server():
        try:
            await srv.start()
        except asyncio.CancelledError:
            pass

    task = asyncio.create_task(run_server())
    await asyncio.sleep(0.5)  # Give server time to start

    yield srv

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


# ── NotificationMessage Tests ────────────────────────────


class TestNotificationMessage:
    """Tests for NotificationMessage class."""

    def test_create_message_with_payload(self):
        """Test creating a message with payload."""
        payload = {"data": "test"}
        msg = NotificationMessage("broadcast", payload)

        assert msg.type == "broadcast"
        assert msg.payload == payload
        assert msg.timestamp is not None

    def test_create_message_without_payload(self):
        """Test creating a message without payload."""
        msg = NotificationMessage("system")

        assert msg.type == "system"
        assert msg.payload == {}
        assert msg.timestamp is not None

    def test_message_to_json(self):
        """Test converting message to JSON."""
        payload = {"action": "test"}
        msg = NotificationMessage("broadcast", payload)
        json_str = msg.to_json()

        data = json.loads(json_str)
        assert data["type"] == "broadcast"
        assert data["payload"] == payload
        assert "timestamp" in data

    def test_message_from_json(self):
        """Test parsing JSON to message."""
        json_str = '{"type": "direct", "payload": {"target": "user1"}, "timestamp": "2026-08-13T10:00:00"}'
        msg = NotificationMessage.from_json(json_str)

        assert msg.type == "direct"
        assert msg.payload == {"target": "user1"}
        assert msg.timestamp == "2026-08-13T10:00:00"

    def test_message_roundtrip(self):
        """Test JSON serialization roundtrip."""
        original = NotificationMessage("broadcast", {"data": "test"})
        json_str = original.to_json()
        restored = NotificationMessage.from_json(json_str)

        assert restored.type == original.type
        assert restored.payload == original.payload


# ── ClientRegistry Tests ────────────────────────────────


class TestClientRegistry:
    """Tests for ClientRegistry class."""

    def test_add_client(self):
        """Test adding a client."""
        registry = ClientRegistry()
        connection = Mock()

        registry.add("client_1", connection)
        assert registry.count() == 1

    def test_get_client(self):
        """Test retrieving a client."""
        registry = ClientRegistry()
        connection = Mock()

        registry.add("client_1", connection)
        retrieved = registry.get("client_1")

        assert retrieved is connection

    def test_get_nonexistent_client(self):
        """Test retrieving a non-existent client."""
        registry = ClientRegistry()
        retrieved = registry.get("nonexistent")

        assert retrieved is None

    def test_remove_client(self):
        """Test removing a client."""
        registry = ClientRegistry()
        connection = Mock()

        registry.add("client_1", connection)
        assert registry.count() == 1

        registry.remove("client_1")
        assert registry.count() == 0

    def test_remove_nonexistent_client(self):
        """Test removing a non-existent client (should not raise)."""
        registry = ClientRegistry()
        registry.remove("nonexistent")  # Should not raise
        assert registry.count() == 0

    def test_get_all_clients(self):
        """Test getting all clients."""
        registry = ClientRegistry()
        conn1, conn2 = Mock(), Mock()

        registry.add("client_1", conn1)
        registry.add("client_2", conn2)

        all_clients = registry.get_all()
        assert len(all_clients) == 2
        assert all_clients["client_1"] is conn1
        assert all_clients["client_2"] is conn2

    def test_thread_safe_add(self):
        """Test thread-safe client addition."""
        registry = ClientRegistry()
        results = []

        def add_client(client_id):
            connection = Mock()
            registry.add(client_id, connection)
            results.append(client_id)

        threads = [Thread(target=add_client, args=(f"client_{i}",)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert registry.count() == 10
        assert len(results) == 10

    def test_thread_safe_remove(self):
        """Test thread-safe client removal."""
        registry = ClientRegistry()

        for i in range(10):
            registry.add(f"client_{i}", Mock())

        results = []

        def remove_client(client_id):
            registry.remove(client_id)
            results.append(client_id)

        threads = [Thread(target=remove_client, args=(f"client_{i}",)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert registry.count() == 0
        assert len(results) == 10

    def test_subscribe_client_to_channel(self):
        """Test subscribing a client to a channel."""
        registry = ClientRegistry()
        registry.add("client_1", Mock())

        registry.subscribe("client_1", "alerts")
        subs = registry.get_subscriptions("client_1")

        assert "alerts" in subs

    def test_unsubscribe_client_from_channel(self):
        """Test unsubscribing a client from a channel."""
        registry = ClientRegistry()
        registry.add("client_1", Mock())

        registry.subscribe("client_1", "alerts")
        registry.unsubscribe("client_1", "alerts")
        subs = registry.get_subscriptions("client_1")

        assert "alerts" not in subs

    def test_get_channel_subscribers(self):
        """Test getting all subscribers to a channel."""
        registry = ClientRegistry()
        registry.add("client_1", Mock())
        registry.add("client_2", Mock())
        registry.add("client_3", Mock())

        registry.subscribe("client_1", "alerts")
        registry.subscribe("client_2", "alerts")
        registry.subscribe("client_3", "system")

        subscribers = registry.get_channel_subscribers("alerts")
        assert len(subscribers) == 2
        assert "client_1" in subscribers
        assert "client_2" in subscribers

    def test_client_multiple_subscriptions(self):
        """Test a client can subscribe to multiple channels."""
        registry = ClientRegistry()
        registry.add("client_1", Mock())

        registry.subscribe("client_1", "alerts")
        registry.subscribe("client_1", "chat")
        registry.subscribe("client_1", "system")

        subs = registry.get_subscriptions("client_1")
        assert len(subs) == 3
        assert "alerts" in subs
        assert "chat" in subs
        assert "system" in subs

    def test_get_all_channels(self):
        """Test getting all active channels and subscriber counts."""
        registry = ClientRegistry()
        registry.add("client_1", Mock())
        registry.add("client_2", Mock())
        registry.add("client_3", Mock())

        registry.subscribe("client_1", "alerts")
        registry.subscribe("client_2", "alerts")
        registry.subscribe("client_2", "chat")
        registry.subscribe("client_3", "chat")

        channels = registry.get_all_channels()
        assert channels["alerts"] == 2
        assert channels["chat"] == 2

    def test_remove_client_cleans_subscriptions(self):
        """Test that removing a client cleans up subscriptions."""
        registry = ClientRegistry()
        registry.add("client_1", Mock())

        registry.subscribe("client_1", "alerts")
        registry.remove("client_1")

        subscribers = registry.get_channel_subscribers("alerts")
        assert "client_1" not in subscribers


# ── NotificationServer Tests ────────────────────────────


class TestNotificationServer:
    """Tests for NotificationServer class."""

    @pytest.mark.asyncio
    async def test_server_creation(self, server):
        """Test server instantiation."""
        assert server.host == "127.0.0.1"
        assert server.ws_port == 8765
        assert server.http_port == 8080
        assert server.clients.count() == 0

    @pytest.mark.asyncio
    async def test_broadcast_to_empty_registry(self, server):
        """Test broadcasting with no clients (should not raise)."""
        msg = NotificationMessage("broadcast", {"data": "test"})
        await server.broadcast(msg)  # Should complete without error

    @pytest.mark.asyncio
    async def test_broadcast_to_multiple_clients(self, server):
        """Test broadcasting to multiple clients."""
        conn1 = AsyncMock()
        conn2 = AsyncMock()

        server.clients.add("client_1", conn1)
        server.clients.add("client_2", conn2)

        msg = NotificationMessage("broadcast", {"data": "test"})
        await server.broadcast(msg)

        assert conn1.send.called
        assert conn2.send.called

    @pytest.mark.asyncio
    async def test_send_direct_to_existing_client(self, server):
        """Test sending a direct message to an existing client."""
        connection = AsyncMock()
        server.clients.add("client_1", connection)

        msg = NotificationMessage("direct", {"target_id": "client_1"})
        await server.send_direct("client_1", msg)

        assert connection.send.called

    @pytest.mark.asyncio
    async def test_send_direct_to_nonexistent_client(self, server):
        """Test sending a direct message to non-existent client (should not raise)."""
        msg = NotificationMessage("direct", {"target_id": "nonexistent"})
        await server.send_direct("nonexistent", msg)  # Should not raise

    @pytest.mark.asyncio
    async def test_send_safe_handles_closed_connection(self, server):
        """Test _send_safe handles closed connections."""
        connection = AsyncMock()
        connection.send.side_effect = websockets.exceptions.ConnectionClosed(None, None)

        await server._send_safe(connection, "test message", "client_1")
        # Should not raise

    @pytest.mark.asyncio
    async def test_send_safe_handles_cancelled_error(self, server):
        """Test _send_safe handles cancelled errors."""
        connection = AsyncMock()
        connection.send.side_effect = asyncio.CancelledError()

        await server._send_safe(connection, "test message", "client_1")
        # Should not raise

    @pytest.mark.asyncio
    async def test_factory_function(self):
        """Test create_server factory function."""
        srv = create_server(host="192.168.1.1", ws_port=9765, http_port=9080)

        assert srv.host == "192.168.1.1"
        assert srv.ws_port == 9765
        assert srv.http_port == 9080

    @pytest.mark.asyncio
    async def test_broadcast_to_channel(self, server):
        """Test broadcasting to a specific channel."""
        conn1 = AsyncMock()
        conn2 = AsyncMock()
        conn3 = AsyncMock()

        server.clients.add("client_1", conn1)
        server.clients.add("client_2", conn2)
        server.clients.add("client_3", conn3)

        server.clients.subscribe("client_1", "alerts")
        server.clients.subscribe("client_2", "alerts")
        server.clients.subscribe("client_3", "chat")

        msg = NotificationMessage("alert", {"data": "alert message", "channel": "alerts"})
        await server.broadcast_to_channel("alerts", msg)

        assert conn1.send.called
        assert conn2.send.called
        assert not conn3.send.called

    @pytest.mark.asyncio
    async def test_broadcast_to_empty_channel(self, server):
        """Test broadcasting to a channel with no subscribers."""
        msg = NotificationMessage("alert", {"data": "test", "channel": "empty"})
        await server.broadcast_to_channel("empty", msg)  # Should not raise


# ── HTTP Health Endpoint Tests ──────────────────────────


@pytest.mark.asyncio
async def test_http_health_endpoint():
    """Test HTTP /health endpoint returns client count."""
    srv = create_server(host="127.0.0.1", ws_port=9765, http_port=9081)

    # Add some clients
    srv.clients.add("client_1", Mock())
    srv.clients.add("client_2", Mock())

    # Mock reader and writer
    reader = AsyncMock()
    writer = Mock()
    writer.drain = AsyncMock()

    # Simulate GET /health request
    reader.readline = AsyncMock(return_value=b"GET /health HTTP/1.1\r\n")

    await srv.http_health(reader, writer)

    # Verify response was written
    assert writer.write.called
    response = writer.write.call_args[0][0].decode()
    assert "200 OK" in response
    assert "connected_clients" in response
    assert '"connected_clients": 2' in response


@pytest.mark.asyncio
async def test_http_not_found():
    """Test HTTP endpoint returns 404 for unknown path."""
    srv = create_server(host="127.0.0.1", ws_port=9765, http_port=9081)

    reader = AsyncMock()
    writer = Mock()
    writer.drain = AsyncMock()

    reader.readline = AsyncMock(return_value=b"GET /unknown HTTP/1.1\r\n")

    await srv.http_health(reader, writer)

    assert writer.write.called
    response = writer.write.call_args[0][0].decode()
    assert "404 Not Found" in response


@pytest.mark.asyncio
async def test_http_empty_request():
    """Test HTTP endpoint handles empty request."""
    srv = create_server(host="127.0.0.1", ws_port=9765, http_port=9081)

    reader = AsyncMock()
    writer = Mock()
    writer.drain = AsyncMock()

    reader.readline = AsyncMock(return_value=b"")

    await srv.http_health(reader, writer)

    assert writer.close.called


@pytest.mark.asyncio
async def test_http_channels_endpoint():
    """Test HTTP GET /channels endpoint returns active channels."""
    srv = create_server(host="127.0.0.1", ws_port=9765, http_port=9081)

    srv.clients.add("client_1", Mock())
    srv.clients.add("client_2", Mock())
    srv.clients.add("client_3", Mock())

    srv.clients.subscribe("client_1", "alerts")
    srv.clients.subscribe("client_2", "alerts")
    srv.clients.subscribe("client_3", "chat")

    reader = AsyncMock()
    writer = Mock()
    writer.drain = AsyncMock()

    reader.readline = AsyncMock(return_value=b"GET /channels HTTP/1.1\r\n")

    await srv.http_health(reader, writer)

    assert writer.write.called
    response = writer.write.call_args[0][0].decode()
    assert "200 OK" in response
    assert "alerts" in response
    assert "chat" in response


@pytest.mark.asyncio
async def test_http_channel_subscribers_endpoint():
    """Test HTTP GET /channels/{name}/subscribers endpoint."""
    srv = create_server(host="127.0.0.1", ws_port=9765, http_port=9081)

    srv.clients.add("client_1", Mock())
    srv.clients.add("client_2", Mock())
    srv.clients.add("client_3", Mock())

    srv.clients.subscribe("client_1", "alerts")
    srv.clients.subscribe("client_2", "alerts")
    srv.clients.subscribe("client_3", "chat")

    reader = AsyncMock()
    writer = Mock()
    writer.drain = AsyncMock()

    reader.readline = AsyncMock(return_value=b"GET /channels/alerts/subscribers HTTP/1.1\r\n")

    await srv.http_health(reader, writer)

    assert writer.write.called
    response = writer.write.call_args[0][0].decode()
    assert "200 OK" in response
    assert "alerts" in response
    assert "client_1" in response
    assert "client_2" in response


# ── Integration Tests ──────────────────────────────────


@pytest.mark.asyncio
async def test_multiple_clients_can_connect(running_server):
    """Test multiple clients can connect simultaneously."""
    async with websockets.connect("ws://127.0.0.1:9765") as ws1, \
               websockets.connect("ws://127.0.0.1:9765") as ws2:

        # Receive connection confirmation
        msg1 = await asyncio.wait_for(ws1.recv(), timeout=1.0)
        msg2 = await asyncio.wait_for(ws2.recv(), timeout=1.0)

        data1 = json.loads(msg1)
        data2 = json.loads(msg2)

        assert data1["type"] == "system"
        assert data1["payload"]["action"] == "connected"
        assert "client_id" in data1["payload"]

        assert data2["type"] == "system"
        assert data2["payload"]["action"] == "connected"
        assert "client_id" in data2["payload"]

        # Client IDs should be different
        assert data1["payload"]["client_id"] != data2["payload"]["client_id"]

        assert running_server.clients.count() == 2


@pytest.mark.asyncio
async def test_broadcast_message_received_by_all_clients(running_server):
    """Test broadcast messages are received by all connected clients."""
    async with websockets.connect("ws://127.0.0.1:9765") as ws1, \
               websockets.connect("ws://127.0.0.1:9765") as ws2:

        # Skip connection messages
        await asyncio.wait_for(ws1.recv(), timeout=1.0)
        await asyncio.wait_for(ws2.recv(), timeout=1.0)

        # Send broadcast from client 1
        broadcast_msg = json.dumps({
            "type": "broadcast",
            "payload": {"data": "hello all"},
            "timestamp": "2026-08-13T10:00:00"
        })
        await ws1.send(broadcast_msg)

        # Both clients should receive the broadcast
        msg1 = await asyncio.wait_for(ws1.recv(), timeout=1.0)
        msg2 = await asyncio.wait_for(ws2.recv(), timeout=1.0)

        data1 = json.loads(msg1)
        data2 = json.loads(msg2)

        assert data1["type"] == "broadcast"
        assert data1["payload"]["data"] == "hello all"
        assert data2["type"] == "broadcast"
        assert data2["payload"]["data"] == "hello all"


@pytest.mark.asyncio
async def test_client_disconnect_updates_registry(running_server):
    """Test client disconnect removes from registry."""
    async with websockets.connect("ws://127.0.0.1:9765") as ws:
        await asyncio.wait_for(ws.recv(), timeout=1.0)
        assert running_server.clients.count() == 1

    # After disconnect
    await asyncio.sleep(0.2)
    assert running_server.clients.count() == 0


@pytest.mark.asyncio
async def test_system_message_broadcast(running_server):
    """Test system messages are broadcast to all clients."""
    async with websockets.connect("ws://127.0.0.1:9765") as ws1, \
               websockets.connect("ws://127.0.0.1:9765") as ws2:

        # Skip connection messages
        await asyncio.wait_for(ws1.recv(), timeout=1.0)
        await asyncio.wait_for(ws2.recv(), timeout=1.0)

        # Send system message
        system_msg = json.dumps({
            "type": "system",
            "payload": {"action": "alert", "message": "System update"},
            "timestamp": "2026-08-13T10:00:00"
        })
        await ws1.send(system_msg)

        # Both should receive it
        msg1 = await asyncio.wait_for(ws1.recv(), timeout=1.0)
        msg2 = await asyncio.wait_for(ws2.recv(), timeout=1.0)

        data1 = json.loads(msg1)
        data2 = json.loads(msg2)

        assert data1["type"] == "system"
        assert data1["payload"]["action"] == "alert"


@pytest.mark.asyncio
async def test_invalid_json_handling(running_server):
    """Test server handles invalid JSON gracefully."""
    async with websockets.connect("ws://127.0.0.1:9765") as ws:
        await asyncio.wait_for(ws.recv(), timeout=1.0)

        # Send invalid JSON
        await ws.send("not valid json {")

        # Should receive error message
        error_msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
        data = json.loads(error_msg)

        assert data["type"] == "system"
        assert "error" in data["payload"]["action"]


@pytest.mark.asyncio
async def test_direct_message_to_specific_client(running_server):
    """Test direct messages sent to specific clients."""
    async with websockets.connect("ws://127.0.0.1:9765") as ws1, \
               websockets.connect("ws://127.0.0.1:9765") as ws2:

        # Get client IDs
        msg1 = await asyncio.wait_for(ws1.recv(), timeout=1.0)
        msg2 = await asyncio.wait_for(ws2.recv(), timeout=1.0)

        client1_id = json.loads(msg1)["payload"]["client_id"]
        client2_id = json.loads(msg2)["payload"]["client_id"]

        # Client 1 sends direct message to Client 2
        direct_msg = json.dumps({
            "type": "direct",
            "payload": {"target_id": client2_id, "message": "hello client 2"},
            "timestamp": "2026-08-13T10:00:00"
        })
        await ws1.send(direct_msg)

        # Client 2 should receive it
        received = await asyncio.wait_for(ws2.recv(), timeout=1.0)
        data = json.loads(received)

        assert data["type"] == "direct"
        assert data["payload"]["target_id"] == client2_id
        assert data["payload"]["message"] == "hello client 2"


@pytest.mark.asyncio
async def test_health_endpoint_accuracy(running_server):
    """Test /health endpoint returns accurate client count."""
    import httpx

    async with httpx.AsyncClient() as client:
        # Test with 0 clients
        response = await client.get("http://127.0.0.1:9080/health")
        assert response.status_code == 200
        data = response.json()
        assert data["connected_clients"] == 0

        # Connect a client
        async with websockets.connect("ws://127.0.0.1:9765"):
            await asyncio.sleep(0.1)

            response = await client.get("http://127.0.0.1:9080/health")
            data = response.json()
            assert data["connected_clients"] == 1


@pytest.mark.asyncio
async def test_message_timestamp_preserved(running_server):
    """Test that message timestamps are properly formatted."""
    async with websockets.connect("ws://127.0.0.1:9765") as ws1, \
               websockets.connect("ws://127.0.0.1:9765") as ws2:

        await asyncio.wait_for(ws1.recv(), timeout=1.0)
        await asyncio.wait_for(ws2.recv(), timeout=1.0)

        broadcast_msg = json.dumps({
            "type": "broadcast",
            "payload": {"test": "data"},
            "timestamp": "2026-08-13T10:00:00Z"
        })
        await ws1.send(broadcast_msg)

        msg = await asyncio.wait_for(ws2.recv(), timeout=1.0)
        data = json.loads(msg)

        assert "timestamp" in data
        # Timestamp should be ISO format
        assert "T" in data["timestamp"]


@pytest.mark.asyncio
async def test_subscribe_message(running_server):
    """Test client can subscribe to a channel."""
    async with websockets.connect("ws://127.0.0.1:9765") as ws:
        await asyncio.wait_for(ws.recv(), timeout=1.0)

        subscribe_msg = json.dumps({
            "type": "subscribe",
            "payload": {"channel": "alerts"},
            "timestamp": "2026-08-13T10:00:00Z"
        })
        await ws.send(subscribe_msg)

        # Server should process subscription (no response expected for subscribe)
        await asyncio.sleep(0.1)

        # Verify subscription by checking server state
        assert running_server.clients.get_subscriptions(
            list(running_server.clients.get_all().keys())[0]
        ) == {"alerts"}


@pytest.mark.asyncio
async def test_unsubscribe_message(running_server):
    """Test client can unsubscribe from a channel."""
    async with websockets.connect("ws://127.0.0.1:9765") as ws:
        await asyncio.wait_for(ws.recv(), timeout=1.0)

        client_id = list(running_server.clients.get_all().keys())[0]

        subscribe_msg = json.dumps({
            "type": "subscribe",
            "payload": {"channel": "alerts"},
            "timestamp": "2026-08-13T10:00:00Z"
        })
        await ws.send(subscribe_msg)
        await asyncio.sleep(0.1)

        unsubscribe_msg = json.dumps({
            "type": "unsubscribe",
            "payload": {"channel": "alerts"},
            "timestamp": "2026-08-13T10:00:00Z"
        })
        await ws.send(unsubscribe_msg)
        await asyncio.sleep(0.1)

        assert running_server.clients.get_subscriptions(client_id) == set()


@pytest.mark.asyncio
async def test_channel_message_routing(running_server):
    """Test messages with channel are only delivered to subscribers."""
    async with websockets.connect("ws://127.0.0.1:9765") as ws1, \
               websockets.connect("ws://127.0.0.1:9765") as ws2, \
               websockets.connect("ws://127.0.0.1:9765") as ws3:

        # Get initial connection messages
        await asyncio.wait_for(ws1.recv(), timeout=1.0)
        await asyncio.wait_for(ws2.recv(), timeout=1.0)
        await asyncio.wait_for(ws3.recv(), timeout=1.0)

        # Subscribe clients to channels
        sub1 = json.dumps({
            "type": "subscribe",
            "payload": {"channel": "alerts"},
            "timestamp": "2026-08-13T10:00:00Z"
        })
        sub2 = json.dumps({
            "type": "subscribe",
            "payload": {"channel": "chat"},
            "timestamp": "2026-08-13T10:00:00Z"
        })
        await ws1.send(sub1)
        await ws2.send(sub2)
        await asyncio.sleep(0.1)

        # Send message to alerts channel
        alert_msg = json.dumps({
            "type": "alert",
            "payload": {"data": "urgent alert", "channel": "alerts"},
            "timestamp": "2026-08-13T10:00:00Z"
        })
        await ws1.send(alert_msg)

        # Only ws1 should receive it (it's subscribed to alerts)
        msg1 = await asyncio.wait_for(ws1.recv(), timeout=1.0)
        data1 = json.loads(msg1)
        assert data1["payload"]["data"] == "urgent alert"

        # ws2 should NOT receive the alert (subscribed to chat)
        # We need to ensure ws2 doesn't get the message
        try:
            await asyncio.wait_for(ws2.recv(), timeout=0.2)
            # If we get here, ws2 received something it shouldn't
            assert False, "ws2 should not receive alert message"
        except asyncio.TimeoutError:
            # This is expected - ws2 should not receive the message
            pass


@pytest.mark.asyncio
async def test_message_without_channel_still_broadcasts(running_server):
    """Test that messages without channel field are broadcast to all."""
    async with websockets.connect("ws://127.0.0.1:9765") as ws1, \
               websockets.connect("ws://127.0.0.1:9765") as ws2:

        await asyncio.wait_for(ws1.recv(), timeout=1.0)
        await asyncio.wait_for(ws2.recv(), timeout=1.0)

        broadcast_msg = json.dumps({
            "type": "broadcast",
            "payload": {"data": "hello all"},
            "timestamp": "2026-08-13T10:00:00Z"
        })
        await ws1.send(broadcast_msg)

        # Both should receive it
        msg1 = await asyncio.wait_for(ws1.recv(), timeout=1.0)
        msg2 = await asyncio.wait_for(ws2.recv(), timeout=1.0)

        assert json.loads(msg1)["payload"]["data"] == "hello all"
        assert json.loads(msg2)["payload"]["data"] == "hello all"


@pytest.mark.asyncio
async def test_channels_endpoint_integration(running_server):
    """Test /channels endpoint with real server."""
    import httpx

    async with httpx.AsyncClient() as client:
        # Subscribe some clients
        async with websockets.connect("ws://127.0.0.1:9765") as ws1, \
                   websockets.connect("ws://127.0.0.1:9765") as ws2:

            await asyncio.wait_for(ws1.recv(), timeout=1.0)
            await asyncio.wait_for(ws2.recv(), timeout=1.0)

            sub1 = json.dumps({
                "type": "subscribe",
                "payload": {"channel": "alerts"},
                "timestamp": "2026-08-13T10:00:00Z"
            })
            sub2 = json.dumps({
                "type": "subscribe",
                "payload": {"channel": "alerts"},
                "timestamp": "2026-08-13T10:00:00Z"
            })
            await ws1.send(sub1)
            await ws2.send(sub2)
            await asyncio.sleep(0.1)

            response = await client.get("http://127.0.0.1:9080/channels")
            assert response.status_code == 200
            data = response.json()
            assert "channels" in data
            assert data["channels"]["alerts"] == 2


@pytest.mark.asyncio
async def test_channel_subscribers_endpoint_integration(running_server):
    """Test /channels/{name}/subscribers endpoint with real server."""
    import httpx

    async with httpx.AsyncClient() as client:
        async with websockets.connect("ws://127.0.0.1:9765") as ws1, \
                   websockets.connect("ws://127.0.0.1:9765") as ws2:

            msg1 = await asyncio.wait_for(ws1.recv(), timeout=1.0)
            msg2 = await asyncio.wait_for(ws2.recv(), timeout=1.0)

            client1_id = json.loads(msg1)["payload"]["client_id"]
            client2_id = json.loads(msg2)["payload"]["client_id"]

            sub1 = json.dumps({
                "type": "subscribe",
                "payload": {"channel": "alerts"},
                "timestamp": "2026-08-13T10:00:00Z"
            })
            sub2 = json.dumps({
                "type": "subscribe",
                "payload": {"channel": "alerts"},
                "timestamp": "2026-08-13T10:00:00Z"
            })
            await ws1.send(sub1)
            await ws2.send(sub2)
            await asyncio.sleep(0.1)

            response = await client.get("http://127.0.0.1:9080/channels/alerts/subscribers")
            assert response.status_code == 200
            data = response.json()
            assert data["channel"] == "alerts"
            assert len(data["subscribers"]) == 2
            assert client1_id in data["subscribers"]
            assert client2_id in data["subscribers"]
