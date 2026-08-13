"""Tests for the WebSocket notification server."""

import asyncio
import json
import pytest
import pytest_asyncio
import websockets
from aiohttp import ClientSession
import threading
import tempfile
import os
from unittest.mock import patch, AsyncMock
from datetime import datetime, timedelta

from client_registry import ClientRegistry
from message_handler import Message, MessageHandler
from notification_server import NotificationServer
from message_persistence import MessagePersistence
from rate_limiter import RateLimiter
from redis_broker import RedisBroker


# ── ClientRegistry Tests ──────────────────────────────────────

class TestClientRegistry:
    """Tests for ClientRegistry."""

    def test_register_client(self):
        """Test registering a new client."""
        registry = ClientRegistry()
        client_id = registry.register("mock_websocket")
        assert client_id is not None
        assert isinstance(client_id, str)
        assert len(client_id) > 0

    def test_unregister_client(self):
        """Test unregistering a client."""
        registry = ClientRegistry()
        client_id = registry.register("mock_websocket")
        registry.unregister(client_id)
        assert registry.get_client(client_id) is None

    def test_get_client(self):
        """Test retrieving a specific client."""
        registry = ClientRegistry()
        ws = "mock_websocket"
        client_id = registry.register(ws)
        assert registry.get_client(client_id) == ws

    def test_get_client_count(self):
        """Test getting client count."""
        registry = ClientRegistry()
        assert registry.get_client_count() == 0

        registry.register("client1")
        assert registry.get_client_count() == 1

        registry.register("client2")
        assert registry.get_client_count() == 2

    def test_get_all_clients(self):
        """Test getting all clients."""
        registry = ClientRegistry()
        registry.register("client1")
        registry.register("client2")
        clients = registry.get_all_clients()
        assert len(clients) == 2
        assert "client1" in clients.values()
        assert "client2" in clients.values()

    def test_thread_safety(self):
        """Test thread-safe concurrent operations."""
        registry = ClientRegistry()
        client_ids = []

        def register_clients():
            for i in range(10):
                client_id = registry.register(f"client_{i}")
                client_ids.append(client_id)

        threads = [threading.Thread(target=register_clients) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert registry.get_client_count() == 50
        assert len(set(client_ids)) == 50  # All IDs are unique


# ── Message Tests ────────────────────────────────────────────

class TestMessage:
    """Tests for Message class."""

    def test_message_creation(self):
        """Test creating a message."""
        msg = Message('broadcast', {'text': 'hello'})
        assert msg.type == 'broadcast'
        assert msg.payload == {'text': 'hello'}
        assert msg.timestamp is not None

    def test_message_with_timestamp(self):
        """Test creating a message with explicit timestamp."""
        ts = '2024-01-01T00:00:00'
        msg = Message('system', {}, timestamp=ts)
        assert msg.timestamp == ts

    def test_message_to_json(self):
        """Test message serialization."""
        msg = Message('broadcast', {'text': 'hello'}, timestamp='2024-01-01T00:00:00')
        json_str = msg.to_json()
        obj = json.loads(json_str)
        assert obj['type'] == 'broadcast'
        assert obj['payload'] == {'text': 'hello'}
        assert obj['timestamp'] == '2024-01-01T00:00:00'

    def test_message_from_json(self):
        """Test message deserialization."""
        json_str = json.dumps({
            'type': 'direct',
            'payload': {'recipient_id': '123', 'text': 'hello'},
            'timestamp': '2024-01-01T00:00:00'
        })
        msg = Message.from_json(json_str)
        assert msg.type == 'direct'
        assert msg.payload['recipient_id'] == '123'
        assert msg.payload['text'] == 'hello'
        assert msg.timestamp == '2024-01-01T00:00:00'


# ── MessageHandler Tests ──────────────────────────────────────

class TestMessageHandler:
    """Tests for MessageHandler."""

    def test_validate_broadcast_message(self):
        """Test validating a valid broadcast message."""
        msg = json.dumps({
            'type': 'broadcast',
            'payload': {'text': 'hello'},
            'timestamp': '2024-01-01T00:00:00'
        })
        assert MessageHandler.validate_message(msg) is True

    def test_validate_direct_message(self):
        """Test validating a valid direct message."""
        msg = json.dumps({
            'type': 'direct',
            'payload': {'recipient_id': '123', 'text': 'hello'},
            'timestamp': '2024-01-01T00:00:00'
        })
        assert MessageHandler.validate_message(msg) is True

    def test_validate_system_message(self):
        """Test validating a valid system message."""
        msg = json.dumps({
            'type': 'system',
            'payload': {'client_id': '123'},
            'timestamp': '2024-01-01T00:00:00'
        })
        assert MessageHandler.validate_message(msg) is True

    def test_validate_invalid_type(self):
        """Test rejecting message with invalid type."""
        msg = json.dumps({
            'type': 'invalid',
            'payload': {},
            'timestamp': '2024-01-01T00:00:00'
        })
        assert MessageHandler.validate_message(msg) is False

    def test_validate_missing_payload(self):
        """Test rejecting message without payload."""
        msg = json.dumps({
            'type': 'broadcast',
            'timestamp': '2024-01-01T00:00:00'
        })
        assert MessageHandler.validate_message(msg) is False

    def test_validate_non_dict_payload(self):
        """Test rejecting message with non-dict payload."""
        msg = json.dumps({
            'type': 'broadcast',
            'payload': 'not a dict',
            'timestamp': '2024-01-01T00:00:00'
        })
        assert MessageHandler.validate_message(msg) is False

    def test_validate_invalid_json(self):
        """Test rejecting invalid JSON."""
        assert MessageHandler.validate_message("not json") is False
        assert MessageHandler.validate_message("{invalid") is False


# ── WebSocket Server Tests ────────────────────────────────────

@pytest_asyncio.fixture
async def server():
    """Fixture providing a running notification server."""
    ns = NotificationServer(
        ws_host='localhost',
        ws_port=8765,
        rest_port=8080
    )
    server_task = asyncio.create_task(ns.run())
    await asyncio.sleep(0.3)  # Give server time to start
    yield ns
    await ns.stop()
    try:
        await asyncio.wait_for(server_task, timeout=2)
    except asyncio.TimeoutError:
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass


class TestWebSocketConnections:
    """Tests for WebSocket connections."""

    @pytest.mark.asyncio
    async def test_client_connection(self, server):
        """Test client can connect to server."""
        async with websockets.connect('ws://localhost:8765') as ws:
            data = await asyncio.wait_for(ws.recv(), timeout=2)
            msg = json.loads(data)
            assert msg['type'] == 'system'
            assert 'client_id' in msg['payload']

    @pytest.mark.asyncio
    async def test_client_id_uniqueness(self, server):
        """Test that each client gets a unique ID."""
        client_ids = []
        for _ in range(3):
            async with websockets.connect('ws://localhost:8765') as ws:
                data = await asyncio.wait_for(ws.recv(), timeout=2)
                client_id = json.loads(data)['payload']['client_id']
                client_ids.append(client_id)

        assert len(set(client_ids)) == 3  # All IDs are unique

    @pytest.mark.asyncio
    async def test_client_disconnect_cleanup(self, server):
        """Test that client is cleaned up on disconnect."""
        initial_count = server.client_registry.get_client_count()

        async with websockets.connect('ws://localhost:8765') as ws:
            await asyncio.wait_for(ws.recv(), timeout=2)
            assert server.client_registry.get_client_count() == initial_count + 1

        await asyncio.sleep(0.1)
        assert server.client_registry.get_client_count() == initial_count


class TestBroadcastMessages:
    """Tests for broadcast functionality."""

    @pytest.mark.asyncio
    async def test_broadcast_to_all_clients(self, server):
        """Test broadcasting a message to all clients."""
        # Connect two clients
        clients = []
        for _ in range(2):
            ws = await websockets.connect('ws://localhost:8765')
            await asyncio.wait_for(ws.recv(), timeout=2)  # Consume system message
            clients.append(ws)

        # Send broadcast from first client
        broadcast_msg = json.dumps({
            'type': 'broadcast',
            'payload': {'text': 'hello all'},
            'timestamp': '2024-01-01T00:00:00'
        })
        await clients[0].send(broadcast_msg)
        await asyncio.sleep(0.1)

        # Both clients should receive the broadcast
        for ws in clients:
            received = await asyncio.wait_for(ws.recv(), timeout=2)
            data = json.loads(received)
            assert data['type'] == 'broadcast'
            assert data['payload']['text'] == 'hello all'

        # Cleanup
        for ws in clients:
            await ws.close()

    @pytest.mark.asyncio
    async def test_broadcast_to_multiple_clients(self, server):
        """Test broadcasting to multiple clients."""
        # Connect three clients
        clients = []
        for _ in range(3):
            ws = await websockets.connect('ws://localhost:8765')
            await asyncio.wait_for(ws.recv(), timeout=2)
            clients.append(ws)

        # Send broadcast
        broadcast_msg = json.dumps({
            'type': 'broadcast',
            'payload': {'msg': 'test'},
            'timestamp': '2024-01-01T00:00:00'
        })
        await clients[0].send(broadcast_msg)
        await asyncio.sleep(0.1)

        # All should receive it
        for ws in clients:
            received = await asyncio.wait_for(ws.recv(), timeout=2)
            assert json.loads(received)['type'] == 'broadcast'

        for ws in clients:
            await ws.close()

    @pytest.mark.asyncio
    async def test_broadcast_empty_clients(self, server):
        """Test broadcast with no clients."""
        # This should not raise an error
        server.client_registry._clients.clear()
        # Manually test broadcast handler
        msg = Message('broadcast', {'text': 'test'})
        await server._broadcast_message(msg)


class TestDirectMessages:
    """Tests for direct messaging."""

    @pytest.mark.asyncio
    async def test_direct_message(self, server):
        """Test sending a direct message."""
        # Connect first client
        ws1 = await websockets.connect('ws://localhost:8765')
        data1 = await asyncio.wait_for(ws1.recv(), timeout=2)
        client_id_1 = json.loads(data1)['payload']['client_id']

        # Connect second client
        ws2 = await websockets.connect('ws://localhost:8765')
        data2 = await asyncio.wait_for(ws2.recv(), timeout=2)
        client_id_2 = json.loads(data2)['payload']['client_id']

        # Send direct message from ws1 to ws2
        direct_msg = json.dumps({
            'type': 'direct',
            'payload': {'recipient_id': client_id_2, 'text': 'hello client2'},
            'timestamp': '2024-01-01T00:00:00'
        })
        await ws1.send(direct_msg)
        await asyncio.sleep(0.1)

        # Only ws2 should receive it
        received = await asyncio.wait_for(ws2.recv(), timeout=2)
        data = json.loads(received)
        assert data['type'] == 'direct'
        assert data['payload']['text'] == 'hello client2'

        # ws1 should not receive anything new
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws1.recv(), timeout=0.2)

        await ws1.close()
        await ws2.close()

    @pytest.mark.asyncio
    async def test_direct_message_to_nonexistent_client(self, server):
        """Test direct message to nonexistent client."""
        ws = await websockets.connect('ws://localhost:8765')
        await asyncio.wait_for(ws.recv(), timeout=2)

        direct_msg = json.dumps({
            'type': 'direct',
            'payload': {'recipient_id': 'nonexistent', 'text': 'hello'},
            'timestamp': '2024-01-01T00:00:00'
        })
        # Should not raise an error, just log warning
        await ws.send(direct_msg)
        await asyncio.sleep(0.1)

        await ws.close()

    @pytest.mark.asyncio
    async def test_direct_message_without_recipient(self, server):
        """Test direct message without recipient_id."""
        ws = await websockets.connect('ws://localhost:8765')
        await asyncio.wait_for(ws.recv(), timeout=2)

        direct_msg = json.dumps({
            'type': 'direct',
            'payload': {'text': 'hello'},
            'timestamp': '2024-01-01T00:00:00'
        })
        # Should not raise an error
        await ws.send(direct_msg)
        await asyncio.sleep(0.1)

        await ws.close()


class TestRESTEndpoints:
    """Tests for REST API endpoints."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, server):
        """Test the health endpoint."""
        await asyncio.sleep(0.2)

        async with ClientSession() as session:
            async with session.get('http://localhost:8080/health') as resp:
                assert resp.status == 200
                data = await resp.json()
                assert 'connected_clients' in data
                assert 'status' in data
                assert data['status'] == 'ok'

    @pytest.mark.asyncio
    async def test_health_endpoint_client_count(self, server):
        """Test that health endpoint returns correct client count."""
        await asyncio.sleep(0.2)

        # Connect a client
        ws = await websockets.connect('ws://localhost:8765')
        await asyncio.wait_for(ws.recv(), timeout=2)
        await asyncio.sleep(0.1)

        async with ClientSession() as session:
            async with session.get('http://localhost:8080/health') as resp:
                data = await resp.json()
                assert data['connected_clients'] == 1

        await ws.close()
        await asyncio.sleep(0.1)

        # Check count is zero after disconnect
        async with ClientSession() as session:
            async with session.get('http://localhost:8080/health') as resp:
                data = await resp.json()
                assert data['connected_clients'] == 0

    @pytest.mark.asyncio
    async def test_health_endpoint_multiple_clients(self, server):
        """Test health endpoint with multiple clients."""
        await asyncio.sleep(0.2)

        # Connect multiple clients
        clients = []
        for _ in range(3):
            ws = await websockets.connect('ws://localhost:8765')
            await asyncio.wait_for(ws.recv(), timeout=2)
            clients.append(ws)

        await asyncio.sleep(0.1)

        async with ClientSession() as session:
            async with session.get('http://localhost:8080/health') as resp:
                data = await resp.json()
                assert data['connected_clients'] == 3

        for ws in clients:
            await ws.close()


class TestMessageValidation:
    """Tests for message validation."""

    @pytest.mark.asyncio
    async def test_invalid_message_rejected(self, server):
        """Test that invalid messages are rejected gracefully."""
        ws = await websockets.connect('ws://localhost:8765')
        await asyncio.wait_for(ws.recv(), timeout=2)

        # Send invalid message
        await ws.send("not valid json")
        await asyncio.sleep(0.1)

        # Connection should still be open
        assert not ws.closed

        await ws.close()

    @pytest.mark.asyncio
    async def test_malformed_payload_rejected(self, server):
        """Test that malformed payloads are rejected."""
        ws = await websockets.connect('ws://localhost:8765')
        await asyncio.wait_for(ws.recv(), timeout=2)

        # Send message with invalid type
        await ws.send(json.dumps({
            'type': 'unknown',
            'payload': {},
            'timestamp': '2024-01-01T00:00:00'
        }))
        await asyncio.sleep(0.1)

        # Connection should still be open
        assert not ws.closed

        await ws.close()


class TestChannelSubscriptions:
    """Tests for channel subscription functionality."""

    @pytest.mark.asyncio
    async def test_subscribe_to_channel(self, server):
        """Test client can subscribe to a channel."""
        ws = await websockets.connect('ws://localhost:8765')
        data = await asyncio.wait_for(ws.recv(), timeout=2)
        client_id = json.loads(data)['payload']['client_id']

        # Subscribe to a channel
        subscribe_msg = json.dumps({
            'type': 'subscribe',
            'payload': {'channel': 'alerts'},
            'timestamp': '2024-01-01T00:00:00'
        })
        await ws.send(subscribe_msg)
        await asyncio.sleep(0.1)

        # Verify subscription
        channels = server.client_registry.get_active_channels()
        assert 'alerts' in channels
        assert channels['alerts'] == 1

        await ws.close()

    @pytest.mark.asyncio
    async def test_unsubscribe_from_channel(self, server):
        """Test client can unsubscribe from a channel."""
        ws = await websockets.connect('ws://localhost:8765')
        data = await asyncio.wait_for(ws.recv(), timeout=2)
        client_id = json.loads(data)['payload']['client_id']

        # Subscribe to a channel
        subscribe_msg = json.dumps({
            'type': 'subscribe',
            'payload': {'channel': 'alerts'},
            'timestamp': '2024-01-01T00:00:00'
        })
        await ws.send(subscribe_msg)
        await asyncio.sleep(0.1)

        # Unsubscribe from channel
        unsubscribe_msg = json.dumps({
            'type': 'unsubscribe',
            'payload': {'channel': 'alerts'},
            'timestamp': '2024-01-01T00:00:00'
        })
        await ws.send(unsubscribe_msg)
        await asyncio.sleep(0.1)

        # Verify unsubscription
        channels = server.client_registry.get_active_channels()
        assert 'alerts' not in channels

        await ws.close()

    @pytest.mark.asyncio
    async def test_multiple_channel_subscriptions(self, server):
        """Test client can subscribe to multiple channels."""
        ws = await websockets.connect('ws://localhost:8765')
        data = await asyncio.wait_for(ws.recv(), timeout=2)

        # Subscribe to multiple channels
        for channel in ['alerts', 'system', 'chat']:
            subscribe_msg = json.dumps({
                'type': 'subscribe',
                'payload': {'channel': channel},
                'timestamp': '2024-01-01T00:00:00'
            })
            await ws.send(subscribe_msg)
        await asyncio.sleep(0.1)

        # Verify subscriptions
        channels = server.client_registry.get_active_channels()
        assert len(channels) == 3
        assert all(ch in channels for ch in ['alerts', 'system', 'chat'])
        assert all(channels[ch] == 1 for ch in ['alerts', 'system', 'chat'])

        await ws.close()

    @pytest.mark.asyncio
    async def test_channel_message_routing(self, server):
        """Test messages are routed only to channel subscribers."""
        # Connect two clients
        ws1 = await websockets.connect('ws://localhost:8765')
        await asyncio.wait_for(ws1.recv(), timeout=2)  # Consume system message

        ws2 = await websockets.connect('ws://localhost:8765')
        await asyncio.wait_for(ws2.recv(), timeout=2)  # Consume system message

        # Subscribe ws1 to 'alerts' channel
        subscribe_msg = json.dumps({
            'type': 'subscribe',
            'payload': {'channel': 'alerts'},
            'timestamp': '2024-01-01T00:00:00'
        })
        await ws1.send(subscribe_msg)
        await asyncio.sleep(0.1)

        # Send message to 'alerts' channel from ws2
        channel_msg = json.dumps({
            'type': 'broadcast',
            'payload': {'channel': 'alerts', 'text': 'alert message'},
            'timestamp': '2024-01-01T00:00:00'
        })
        await ws2.send(channel_msg)
        await asyncio.sleep(0.1)

        # Only ws1 should receive the message
        received = await asyncio.wait_for(ws1.recv(), timeout=2)
        data = json.loads(received)
        assert data['type'] == 'broadcast'
        assert data['payload']['text'] == 'alert message'

        # ws2 should not receive anything new
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws2.recv(), timeout=0.2)

        await ws1.close()
        await ws2.close()

    @pytest.mark.asyncio
    async def test_broadcast_without_channel_reaches_all(self, server):
        """Test broadcast without channel still reaches all clients."""
        # Connect two clients
        ws1 = await websockets.connect('ws://localhost:8765')
        await asyncio.wait_for(ws1.recv(), timeout=2)

        ws2 = await websockets.connect('ws://localhost:8765')
        await asyncio.wait_for(ws2.recv(), timeout=2)

        # Subscribe ws1 to a channel
        subscribe_msg = json.dumps({
            'type': 'subscribe',
            'payload': {'channel': 'alerts'},
            'timestamp': '2024-01-01T00:00:00'
        })
        await ws1.send(subscribe_msg)
        await asyncio.sleep(0.1)

        # Send broadcast without channel
        broadcast_msg = json.dumps({
            'type': 'broadcast',
            'payload': {'text': 'broadcast to all'},
            'timestamp': '2024-01-01T00:00:00'
        })
        await ws1.send(broadcast_msg)
        await asyncio.sleep(0.1)

        # Both should receive the broadcast
        for ws in [ws1, ws2]:
            received = await asyncio.wait_for(ws.recv(), timeout=2)
            data = json.loads(received)
            assert data['type'] == 'broadcast'
            assert data['payload']['text'] == 'broadcast to all'

        await ws1.close()
        await ws2.close()

    @pytest.mark.asyncio
    async def test_multiple_clients_same_channel(self, server):
        """Test multiple clients can subscribe to the same channel."""
        clients = []
        for _ in range(3):
            ws = await websockets.connect('ws://localhost:8765')
            await asyncio.wait_for(ws.recv(), timeout=2)
            clients.append(ws)

        # Subscribe all to 'system' channel
        for ws in clients:
            subscribe_msg = json.dumps({
                'type': 'subscribe',
                'payload': {'channel': 'system'},
                'timestamp': '2024-01-01T00:00:00'
            })
            await ws.send(subscribe_msg)
        await asyncio.sleep(0.1)

        # Verify all 3 are subscribed
        channels = server.client_registry.get_active_channels()
        assert channels['system'] == 3

        # Send message to channel
        channel_msg = json.dumps({
            'type': 'broadcast',
            'payload': {'channel': 'system', 'text': 'system alert'},
            'timestamp': '2024-01-01T00:00:00'
        })
        await clients[0].send(channel_msg)
        await asyncio.sleep(0.1)

        # All should receive
        for ws in clients:
            received = await asyncio.wait_for(ws.recv(), timeout=2)
            data = json.loads(received)
            assert data['payload']['text'] == 'system alert'

        for ws in clients:
            await ws.close()


class TestChannelRESTEndpoints:
    """Tests for channel REST endpoints."""

    @pytest.mark.asyncio
    async def test_get_channels_endpoint(self, server):
        """Test GET /channels endpoint."""
        await asyncio.sleep(0.2)

        # Connect a client and subscribe to channels
        ws = await websockets.connect('ws://localhost:8765')
        await asyncio.wait_for(ws.recv(), timeout=2)

        for channel in ['alerts', 'system', 'chat']:
            subscribe_msg = json.dumps({
                'type': 'subscribe',
                'payload': {'channel': channel},
                'timestamp': '2024-01-01T00:00:00'
            })
            await ws.send(subscribe_msg)
        await asyncio.sleep(0.1)

        # Call endpoint
        async with ClientSession() as session:
            async with session.get('http://localhost:8080/channels') as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data['count'] == 3
                assert 'channels' in data
                assert data['channels']['alerts'] == 1
                assert data['channels']['system'] == 1
                assert data['channels']['chat'] == 1

        await ws.close()

    @pytest.mark.asyncio
    async def test_get_channel_subscribers_endpoint(self, server):
        """Test GET /channels/{name}/subscribers endpoint."""
        await asyncio.sleep(0.2)

        # Connect two clients and subscribe both to a channel
        clients = []
        for _ in range(2):
            ws = await websockets.connect('ws://localhost:8765')
            data = await asyncio.wait_for(ws.recv(), timeout=2)
            client_id = json.loads(data)['payload']['client_id']
            clients.append((ws, client_id))

        for ws, _ in clients:
            subscribe_msg = json.dumps({
                'type': 'subscribe',
                'payload': {'channel': 'alerts'},
                'timestamp': '2024-01-01T00:00:00'
            })
            await ws.send(subscribe_msg)
        await asyncio.sleep(0.1)

        # Call endpoint
        async with ClientSession() as session:
            async with session.get('http://localhost:8080/channels/alerts/subscribers') as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data['channel'] == 'alerts'
                assert data['count'] == 2
                assert len(data['subscribers']) == 2
                subscriber_ids = [client_id for _, client_id in clients]
                for sub_id in data['subscribers']:
                    assert sub_id in subscriber_ids

        for ws, _ in clients:
            await ws.close()

    @pytest.mark.asyncio
    async def test_get_channels_empty(self, server):
        """Test GET /channels when no channels exist."""
        await asyncio.sleep(0.2)

        async with ClientSession() as session:
            async with session.get('http://localhost:8080/channels') as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data['count'] == 0
                assert data['channels'] == {}

    @pytest.mark.asyncio
    async def test_get_channel_subscribers_nonexistent(self, server):
        """Test GET /channels/{name}/subscribers for nonexistent channel."""
        await asyncio.sleep(0.2)

        async with ClientSession() as session:
            async with session.get('http://localhost:8080/channels/nonexistent/subscribers') as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data['channel'] == 'nonexistent'
                assert data['count'] == 0
                assert data['subscribers'] == []


# ── Message Persistence Tests ──────────────────────────────────────

class TestMessagePersistence:
    """Tests for message persistence with SQLite."""

    def test_message_persistence_init(self):
        """Test initializing message persistence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db_url = f"sqlite:///{db_path}"
            persistence = MessagePersistence(db_url)
            assert persistence.db_path == db_path
            assert os.path.exists(db_path)

    def test_store_and_retrieve_message(self):
        """Test storing and retrieving messages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db_url = f"sqlite:///{db_path}"
            persistence = MessagePersistence(db_url)

            msg_id = persistence.store_message(
                channel="alerts",
                message_type="broadcast",
                payload={"text": "hello"},
                timestamp="2024-01-01T00:00:00"
            )

            assert msg_id > 0

            messages = persistence.get_messages(channel="alerts")
            assert len(messages) == 1
            assert messages[0]["channel"] == "alerts"
            assert messages[0]["type"] == "broadcast"
            assert messages[0]["payload"]["text"] == "hello"

    def test_store_multiple_messages(self):
        """Test storing and retrieving multiple messages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db_url = f"sqlite:///{db_path}"
            persistence = MessagePersistence(db_url)

            for i in range(5):
                persistence.store_message(
                    channel="alerts",
                    message_type="broadcast",
                    payload={"text": f"message {i}"},
                    timestamp=f"2024-01-01T00:00:{i:02d}"
                )

            messages = persistence.get_messages(channel="alerts")
            assert len(messages) == 5

    def test_get_messages_with_limit(self):
        """Test retrieving messages with limit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db_url = f"sqlite:///{db_path}"
            persistence = MessagePersistence(db_url)

            for i in range(10):
                persistence.store_message(
                    channel="alerts",
                    message_type="broadcast",
                    payload={"text": f"message {i}"},
                    timestamp=f"2024-01-01T00:00:{i:02d}"
                )

            messages = persistence.get_messages(channel="alerts", limit=5)
            assert len(messages) == 5

    def test_get_messages_with_offset(self):
        """Test retrieving messages with offset."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db_url = f"sqlite:///{db_path}"
            persistence = MessagePersistence(db_url)

            for i in range(10):
                persistence.store_message(
                    channel="alerts",
                    message_type="broadcast",
                    payload={"text": f"message {i}"},
                    timestamp=f"2024-01-01T00:00:{i:02d}"
                )

            messages = persistence.get_messages(channel="alerts", limit=5, offset=5)
            assert len(messages) == 5

    def test_get_message_count(self):
        """Test getting message count."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db_url = f"sqlite:///{db_path}"
            persistence = MessagePersistence(db_url)

            for i in range(3):
                persistence.store_message(
                    channel="alerts",
                    message_type="broadcast",
                    payload={"text": f"message {i}"},
                    timestamp=f"2024-01-01T00:00:{i:02d}"
                )

            count = persistence.get_message_count(channel="alerts")
            assert count == 3

    def test_clear_messages_by_channel(self):
        """Test clearing messages by channel."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db_url = f"sqlite:///{db_path}"
            persistence = MessagePersistence(db_url)

            persistence.store_message(
                channel="alerts",
                message_type="broadcast",
                payload={"text": "hello"},
                timestamp="2024-01-01T00:00:00"
            )

            persistence.store_message(
                channel="chat",
                message_type="broadcast",
                payload={"text": "hello"},
                timestamp="2024-01-01T00:00:01"
            )

            persistence.clear_messages(channel="alerts")

            assert persistence.get_message_count(channel="alerts") == 0
            assert persistence.get_message_count(channel="chat") == 1

    def test_get_all_messages(self):
        """Test retrieving all messages across channels."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db_url = f"sqlite:///{db_path}"
            persistence = MessagePersistence(db_url)

            persistence.store_message(
                channel="alerts",
                message_type="broadcast",
                payload={"text": "alert"},
                timestamp="2024-01-01T00:00:00"
            )

            persistence.store_message(
                channel="chat",
                message_type="broadcast",
                payload={"text": "chat"},
                timestamp="2024-01-01T00:00:01"
            )

            messages = persistence.get_messages()
            assert len(messages) == 2
            assert messages[0]["channel"] in ["alerts", "chat"]


# ── Redis Broker Tests ─────────────────────────────────────────────

class TestRedisBroker:
    """Tests for Redis pub/sub broker."""

    def test_broker_initialization(self):
        """Test Redis broker initialization."""
        broker = RedisBroker(redis_url="redis://localhost:6379")
        assert broker.redis_url == "redis://localhost:6379"
        assert broker.redis is None
        assert broker.pubsub is None


# ── REST Messages Endpoint Tests ───────────────────────────────────

class TestMessagesRESTEndpoint:
    """Tests for the /messages REST endpoint."""

    @pytest.mark.asyncio
    async def test_messages_endpoint(self, server):
        """Test the /messages endpoint."""
        await asyncio.sleep(0.2)

        async with websockets.connect('ws://localhost:8765') as ws:
            await asyncio.wait_for(ws.recv(), timeout=2)

            broadcast_msg = json.dumps({
                'type': 'broadcast',
                'payload': {'text': 'test message'},
                'timestamp': '2024-01-01T00:00:00'
            })
            await ws.send(broadcast_msg)
            await asyncio.sleep(0.1)

        await asyncio.sleep(0.2)

        async with ClientSession() as session:
            async with session.get('http://localhost:8080/messages') as resp:
                assert resp.status == 200
                data = await resp.json()
                assert 'messages' in data
                assert 'count' in data
                assert 'total' in data

    @pytest.mark.asyncio
    async def test_messages_endpoint_with_limit(self, server):
        """Test /messages endpoint with limit parameter."""
        await asyncio.sleep(0.2)

        async with websockets.connect('ws://localhost:8765') as ws:
            await asyncio.wait_for(ws.recv(), timeout=2)

            for i in range(5):
                broadcast_msg = json.dumps({
                    'type': 'broadcast',
                    'payload': {'text': f'message {i}'},
                    'timestamp': '2024-01-01T00:00:00'
                })
                await ws.send(broadcast_msg)
            await asyncio.sleep(0.1)

        await asyncio.sleep(0.2)

        async with ClientSession() as session:
            async with session.get('http://localhost:8080/messages?limit=2') as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data['count'] <= 2
                assert data['limit'] == 2

    @pytest.mark.asyncio
    async def test_messages_endpoint_with_offset(self, server):
        """Test /messages endpoint with offset parameter."""
        await asyncio.sleep(0.2)

        async with websockets.connect('ws://localhost:8765') as ws:
            await asyncio.wait_for(ws.recv(), timeout=2)

            for i in range(5):
                broadcast_msg = json.dumps({
                    'type': 'broadcast',
                    'payload': {'text': f'message {i}'},
                    'timestamp': '2024-01-01T00:00:00'
                })
                await ws.send(broadcast_msg)
            await asyncio.sleep(0.1)

        await asyncio.sleep(0.2)

        async with ClientSession() as session:
            async with session.get('http://localhost:8080/messages?limit=10&offset=2') as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data['offset'] == 2

    @pytest.mark.asyncio
    async def test_messages_endpoint_by_channel(self, server):
        """Test /messages endpoint filtering by channel."""
        await asyncio.sleep(0.2)

        async with websockets.connect('ws://localhost:8765') as ws:
            await asyncio.wait_for(ws.recv(), timeout=2)

            broadcast_msg = json.dumps({
                'type': 'broadcast',
                'payload': {'channel': 'alerts', 'text': 'alert'},
                'timestamp': '2024-01-01T00:00:00'
            })
            await ws.send(broadcast_msg)
            await asyncio.sleep(0.1)

        await asyncio.sleep(0.2)

        async with ClientSession() as session:
            async with session.get('http://localhost:8080/messages?channel=alerts') as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data['channel'] == 'alerts'


# ── Rate Limiter Tests ─────────────────────────────────────────

class TestRateLimiter:
    """Tests for rate limiting functionality."""

    def test_rate_limiter_initialization(self):
        """Test rate limiter initialization."""
        limiter = RateLimiter(limit=100)
        assert limiter.limit == 100
        assert limiter.window_seconds == 60

    def test_rate_limiter_with_custom_limit(self):
        """Test rate limiter with custom limit."""
        limiter = RateLimiter(limit=50)
        assert limiter.limit == 50

    @pytest.mark.asyncio
    async def test_rate_limiter_no_redis(self):
        """Test rate limiter without Redis (should allow all)."""
        limiter = RateLimiter(limit=5)
        is_allowed, remaining = await limiter.check_rate_limit("test-client")
        assert is_allowed is True
        assert remaining == 5


class TestHistoryEndpoint:
    """Tests for the /history REST endpoint."""

    @pytest.mark.asyncio
    async def test_history_endpoint_requires_channel(self, server):
        """Test that /history endpoint requires channel parameter."""
        await asyncio.sleep(0.2)

        async with ClientSession() as session:
            async with session.get('http://localhost:8080/history') as resp:
                assert resp.status == 400
                data = await resp.json()
                assert 'error' in data

    @pytest.mark.asyncio
    async def test_history_endpoint_single_message(self, server):
        """Test /history endpoint with a single message."""
        await asyncio.sleep(0.2)

        async with websockets.connect('ws://localhost:8765') as ws:
            await asyncio.wait_for(ws.recv(), timeout=2)

            broadcast_msg = json.dumps({
                'type': 'broadcast',
                'payload': {'channel': 'alerts', 'text': 'alert message'},
                'timestamp': '2024-01-01T10:00:00'
            })
            await ws.send(broadcast_msg)
            await asyncio.sleep(0.1)

        await asyncio.sleep(0.2)

        async with ClientSession() as session:
            async with session.get('http://localhost:8080/history?channel=alerts') as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data['channel'] == 'alerts'
                assert len(data['messages']) > 0
                assert data['has_more'] is False

    @pytest.mark.asyncio
    async def test_history_endpoint_multiple_messages(self, server):
        """Test /history endpoint with multiple messages."""
        await asyncio.sleep(0.2)

        async with websockets.connect('ws://localhost:8765') as ws:
            await asyncio.wait_for(ws.recv(), timeout=2)

            for i in range(5):
                broadcast_msg = json.dumps({
                    'type': 'broadcast',
                    'payload': {'channel': 'alerts', 'text': f'message {i}'},
                    'timestamp': f'2024-01-01T10:00:{i:02d}'
                })
                await ws.send(broadcast_msg)
            await asyncio.sleep(0.1)

        await asyncio.sleep(0.2)

        async with ClientSession() as session:
            async with session.get('http://localhost:8080/history?channel=alerts') as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data['channel'] == 'alerts'
                assert len(data['messages']) > 0

    @pytest.mark.asyncio
    async def test_history_endpoint_with_limit(self, server):
        """Test /history endpoint with limit parameter."""
        await asyncio.sleep(0.2)

        async with websockets.connect('ws://localhost:8765') as ws:
            await asyncio.wait_for(ws.recv(), timeout=2)

            for i in range(10):
                broadcast_msg = json.dumps({
                    'type': 'broadcast',
                    'payload': {'channel': 'alerts', 'text': f'message {i}'},
                    'timestamp': f'2024-01-01T10:00:{i:02d}'
                })
                await ws.send(broadcast_msg)
            await asyncio.sleep(0.1)

        await asyncio.sleep(0.2)

        async with ClientSession() as session:
            async with session.get('http://localhost:8080/history?channel=alerts&limit=3') as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data['limit'] == 3
                assert len(data['messages']) <= 3

    @pytest.mark.asyncio
    async def test_history_endpoint_with_since(self, server):
        """Test /history endpoint with since parameter for time filtering."""
        await asyncio.sleep(0.2)

        async with websockets.connect('ws://localhost:8765') as ws:
            await asyncio.wait_for(ws.recv(), timeout=2)

            broadcast_msg = json.dumps({
                'type': 'broadcast',
                'payload': {'channel': 'alerts', 'text': 'message before'},
                'timestamp': '2024-01-01T09:00:00'
            })
            await ws.send(broadcast_msg)

            broadcast_msg = json.dumps({
                'type': 'broadcast',
                'payload': {'channel': 'alerts', 'text': 'message after'},
                'timestamp': '2024-01-01T11:00:00'
            })
            await ws.send(broadcast_msg)
            await asyncio.sleep(0.1)

        await asyncio.sleep(0.2)

        async with ClientSession() as session:
            async with session.get('http://localhost:8080/history?channel=alerts&since=2024-01-01T10:00:00') as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data['since'] == '2024-01-01T10:00:00'
                assert len(data['messages']) >= 1

    @pytest.mark.asyncio
    async def test_history_endpoint_pagination(self, server):
        """Test /history endpoint with pagination (offset)."""
        await asyncio.sleep(0.2)

        async with websockets.connect('ws://localhost:8765') as ws:
            await asyncio.wait_for(ws.recv(), timeout=2)

            for i in range(5):
                broadcast_msg = json.dumps({
                    'type': 'broadcast',
                    'payload': {'channel': 'alerts', 'text': f'message {i}'},
                    'timestamp': f'2024-01-01T10:00:{i:02d}'
                })
                await ws.send(broadcast_msg)
            await asyncio.sleep(0.1)

        await asyncio.sleep(0.2)

        async with ClientSession() as session:
            async with session.get('http://localhost:8080/history?channel=alerts&limit=2&offset=0') as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data['offset'] == 0
                assert len(data['messages']) <= 2

    @pytest.mark.asyncio
    async def test_history_endpoint_chronological_order(self, server):
        """Test that /history returns messages in chronological order."""
        await asyncio.sleep(0.2)

        async with websockets.connect('ws://localhost:8765') as ws:
            await asyncio.wait_for(ws.recv(), timeout=2)

            timestamps = ['2024-01-01T10:00:00', '2024-01-01T10:00:01', '2024-01-01T10:00:02']
            for i, ts in enumerate(timestamps):
                broadcast_msg = json.dumps({
                    'type': 'broadcast',
                    'payload': {'channel': 'timeline', 'text': f'message {i}'},
                    'timestamp': ts
                })
                await ws.send(broadcast_msg)
            await asyncio.sleep(0.1)

        await asyncio.sleep(0.2)

        async with ClientSession() as session:
            async with session.get('http://localhost:8080/history?channel=timeline') as resp:
                assert resp.status == 200
                data = await resp.json()
                assert len(data['messages']) >= 3
                for i in range(len(data['messages']) - 1):
                    assert data['messages'][i]['timestamp'] <= data['messages'][i + 1]['timestamp']

    @pytest.mark.asyncio
    async def test_history_endpoint_has_more_flag(self, server):
        """Test that has_more flag is set correctly."""
        await asyncio.sleep(0.2)

        async with websockets.connect('ws://localhost:8765') as ws:
            await asyncio.wait_for(ws.recv(), timeout=2)

            for i in range(5):
                broadcast_msg = json.dumps({
                    'type': 'broadcast',
                    'payload': {'channel': 'alerts', 'text': f'message {i}'},
                    'timestamp': f'2024-01-01T10:00:{i:02d}'
                })
                await ws.send(broadcast_msg)
            await asyncio.sleep(0.1)

        await asyncio.sleep(0.2)

        async with ClientSession() as session:
            async with session.get('http://localhost:8080/history?channel=alerts&limit=2') as resp:
                assert resp.status == 200
                data = await resp.json()
                assert 'has_more' in data
                if data['total'] > data['limit']:
                    assert data['has_more'] is True

    @pytest.mark.asyncio
    async def test_history_endpoint_empty_channel(self, server):
        """Test /history endpoint with channel that has no messages."""
        await asyncio.sleep(0.2)

        async with ClientSession() as session:
            async with session.get('http://localhost:8080/history?channel=empty') as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data['channel'] == 'empty'
                assert len(data['messages']) == 0
                assert data['has_more'] is False


# ── Message Cleanup Tests ──────────────────────────────────────

class TestMessageCleanup:
    """Tests for message cleanup functionality."""

    def test_cleanup_old_messages(self):
        """Test cleaning up messages older than TTL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db_url = f"sqlite:///{db_path}"
            persistence = MessagePersistence(db_url)

            old_date = (datetime.utcnow() - timedelta(days=8)).isoformat()
            recent_date = datetime.utcnow().isoformat()

            persistence.store_message(
                channel="alerts",
                message_type="broadcast",
                payload={"text": "old message"},
                timestamp=old_date
            )

            persistence.store_message(
                channel="alerts",
                message_type="broadcast",
                payload={"text": "recent message"},
                timestamp=recent_date
            )

            deleted = persistence.cleanup_old_messages(ttl_days=7)
            assert deleted == 1

            remaining = persistence.get_message_count(channel="alerts")
            assert remaining == 1

    def test_cleanup_multiple_old_messages(self):
        """Test cleaning up multiple old messages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db_url = f"sqlite:///{db_path}"
            persistence = MessagePersistence(db_url)

            old_date = (datetime.utcnow() - timedelta(days=10)).isoformat()
            recent_date = datetime.utcnow().isoformat()

            for i in range(3):
                persistence.store_message(
                    channel="alerts",
                    message_type="broadcast",
                    payload={"text": f"old message {i}"},
                    timestamp=old_date
                )

            for i in range(2):
                persistence.store_message(
                    channel="alerts",
                    message_type="broadcast",
                    payload={"text": f"recent message {i}"},
                    timestamp=recent_date
                )

            deleted = persistence.cleanup_old_messages(ttl_days=7)
            assert deleted == 3

            remaining = persistence.get_message_count(channel="alerts")
            assert remaining == 2

    def test_cleanup_with_custom_ttl(self):
        """Test cleanup with custom TTL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db_url = f"sqlite:///{db_path}"
            persistence = MessagePersistence(db_url)

            old_date = (datetime.utcnow() - timedelta(days=15)).isoformat()
            somewhat_old = (datetime.utcnow() - timedelta(days=8)).isoformat()
            recent = datetime.utcnow().isoformat()

            persistence.store_message(
                channel="alerts",
                message_type="broadcast",
                payload={"text": "very old"},
                timestamp=old_date
            )

            persistence.store_message(
                channel="alerts",
                message_type="broadcast",
                payload={"text": "somewhat old"},
                timestamp=somewhat_old
            )

            persistence.store_message(
                channel="alerts",
                message_type="broadcast",
                payload={"text": "recent"},
                timestamp=recent
            )

            deleted = persistence.cleanup_old_messages(ttl_days=10)
            assert deleted == 1

            remaining = persistence.get_message_count(channel="alerts")
            assert remaining == 2

    def test_cleanup_no_old_messages(self):
        """Test cleanup when there are no old messages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db_url = f"sqlite:///{db_path}"
            persistence = MessagePersistence(db_url)

            recent = datetime.utcnow().isoformat()
            persistence.store_message(
                channel="alerts",
                message_type="broadcast",
                payload={"text": "recent"},
                timestamp=recent
            )

            deleted = persistence.cleanup_old_messages(ttl_days=7)
            assert deleted == 0

            remaining = persistence.get_message_count(channel="alerts")
            assert remaining == 1


# ── Message Persistence Time Range Tests ──────────────────────

class TestMessagePersistenceTimeRange:
    """Tests for time-based message querying."""

    def test_get_messages_since(self):
        """Test retrieving messages since a specific timestamp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db_url = f"sqlite:///{db_path}"
            persistence = MessagePersistence(db_url)

            persistence.store_message(
                channel="alerts",
                message_type="broadcast",
                payload={"text": "old"},
                timestamp="2024-01-01T09:00:00"
            )

            persistence.store_message(
                channel="alerts",
                message_type="broadcast",
                payload={"text": "new"},
                timestamp="2024-01-01T11:00:00"
            )

            messages = persistence.get_messages_since(
                channel="alerts",
                since="2024-01-01T10:00:00"
            )

            assert len(messages) == 1
            assert messages[0]["payload"]["text"] == "new"

    def test_get_messages_since_with_limit(self):
        """Test retrieving messages since timestamp with limit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db_url = f"sqlite:///{db_path}"
            persistence = MessagePersistence(db_url)

            for i in range(5):
                persistence.store_message(
                    channel="alerts",
                    message_type="broadcast",
                    payload={"text": f"message {i}"},
                    timestamp=f"2024-01-01T10:00:{i:02d}"
                )

            messages = persistence.get_messages_since(
                channel="alerts",
                since="2024-01-01T09:00:00",
                limit=2
            )

            assert len(messages) <= 2

    def test_get_messages_count_since(self):
        """Test getting count of messages since a timestamp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db_url = f"sqlite:///{db_path}"
            persistence = MessagePersistence(db_url)

            persistence.store_message(
                channel="alerts",
                message_type="broadcast",
                payload={"text": "old"},
                timestamp="2024-01-01T09:00:00"
            )

            persistence.store_message(
                channel="alerts",
                message_type="broadcast",
                payload={"text": "new1"},
                timestamp="2024-01-01T11:00:00"
            )

            persistence.store_message(
                channel="alerts",
                message_type="broadcast",
                payload={"text": "new2"},
                timestamp="2024-01-01T12:00:00"
            )

            count = persistence.get_messages_count_since(
                channel="alerts",
                since="2024-01-01T10:00:00"
            )

            assert count == 2
