"""Tests for the WebSocket notification server."""

import asyncio
import json
import pytest
import pytest_asyncio
import websockets
from aiohttp import ClientSession
import threading

from client_registry import ClientRegistry
from message_handler import Message, MessageHandler
from notification_server import NotificationServer


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
