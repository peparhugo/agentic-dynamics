"""
Tests for the WebSocket notification server.
Uses pytest and pytest-asyncio for async testing.
"""

import asyncio
import json
import pytest
import websockets
from aiohttp import ClientSession

from websocket_server import NotificationServer, ClientRegistry


@pytest.fixture
def client_registry():
    """Create a fresh client registry."""
    return ClientRegistry()


class TestClientRegistry:
    """Tests for thread-safe client registry."""

    def test_add_and_get_client(self, client_registry):
        """Test adding and retrieving a client."""
        class MockWebSocket:
            pass

        ws = MockWebSocket()
        client_id = "test-client-1"
        client_registry.add(client_id, ws)

        retrieved = client_registry.get(client_id)
        assert retrieved is ws

    def test_remove_client(self, client_registry):
        """Test removing a client from registry."""
        class MockWebSocket:
            pass

        ws = MockWebSocket()
        client_id = "test-client-2"
        client_registry.add(client_id, ws)
        client_registry.remove(client_id)

        retrieved = client_registry.get(client_id)
        assert retrieved is None

    def test_get_all_clients(self, client_registry):
        """Test retrieving all clients."""
        class MockWebSocket:
            pass

        ws1 = MockWebSocket()
        ws2 = MockWebSocket()
        client_registry.add("client-1", ws1)
        client_registry.add("client-2", ws2)

        all_clients = client_registry.get_all()
        assert len(all_clients) == 2
        assert all_clients["client-1"] is ws1
        assert all_clients["client-2"] is ws2

    def test_get_count(self, client_registry):
        """Test getting client count."""
        class MockWebSocket:
            pass

        client_registry.add("client-1", MockWebSocket())
        client_registry.add("client-2", MockWebSocket())
        client_registry.add("client-3", MockWebSocket())

        assert client_registry.get_count() == 3

    def test_remove_nonexistent_client(self, client_registry):
        """Test removing a client that doesn't exist."""
        client_registry.remove("nonexistent")
        assert client_registry.get_count() == 0

    def test_get_nonexistent_client(self, client_registry):
        """Test retrieving a client that doesn't exist."""
        result = client_registry.get("nonexistent")
        assert result is None


class TestWebSocketServer:
    """Tests for WebSocket server functionality."""

    @pytest.mark.asyncio
    async def test_server_starts(self):
        """Test that server starts successfully."""
        server = NotificationServer(host="127.0.0.1", port=8766)
        await server.start()
        assert server.server is not None
        assert server.http_runner is not None
        await server.stop()

    @pytest.mark.asyncio
    async def test_client_connection(self):
        """Test that a client can connect to the server."""
        server = NotificationServer(host="127.0.0.1", port=8767)
        await server.start()

        async with websockets.connect("ws://127.0.0.1:8767") as websocket:
            message = await websocket.recv()
            data = json.loads(message)

            assert data["type"] == "system"
            assert "client_id" in data["payload"]
            assert "Connected to notification server" in data["payload"]["message"]
            assert "timestamp" in data

        await server.stop()

    @pytest.mark.asyncio
    async def test_multiple_clients_connect(self):
        """Test multiple clients connecting simultaneously."""
        server = NotificationServer(host="127.0.0.1", port=8768)
        await server.start()

        async def connect_client():
            async with websockets.connect("ws://127.0.0.1:8768") as ws:
                message = await ws.recv()
                data = json.loads(message)
                return data["payload"]["client_id"]

        client_ids = await asyncio.gather(
            connect_client(),
            connect_client(),
            connect_client()
        )

        assert len(set(client_ids)) == 3
        assert server.registry.get_count() == 0

        await server.stop()

    @pytest.mark.asyncio
    async def test_broadcast_message(self):
        """Test broadcasting a message to all clients."""
        server = NotificationServer(host="127.0.0.1", port=8769)
        await server.start()

        async def connect_and_listen():
            async with websockets.connect("ws://127.0.0.1:8769") as ws:
                greeting = await ws.recv()
                json.loads(greeting)

                message = await ws.recv()
                return json.loads(message)

        async def send_broadcast():
            await asyncio.sleep(0.1)
            async with websockets.connect("ws://127.0.0.1:8769") as ws:
                greeting = await ws.recv()
                json.loads(greeting)

                payload = {"text": "Hello all clients"}
                await ws.send(json.dumps({
                    "type": "broadcast",
                    "payload": payload
                }))

        listeners = [
            asyncio.create_task(connect_and_listen()),
            asyncio.create_task(connect_and_listen())
        ]
        broadcaster = asyncio.create_task(send_broadcast())

        await asyncio.sleep(0.5)
        results = await asyncio.gather(*listeners, broadcaster)
        messages = results[:2]

        for msg in messages:
            assert msg["type"] == "broadcast"
            assert msg["payload"]["text"] == "Hello all clients"
            assert "timestamp" in msg

        await server.stop()

    @pytest.mark.asyncio
    async def test_invalid_json_handling(self):
        """Test that invalid JSON is handled gracefully."""
        server = NotificationServer(host="127.0.0.1", port=8770)
        await server.start()

        async with websockets.connect("ws://127.0.0.1:8770") as ws:
            greeting = await ws.recv()
            json.loads(greeting)

            await ws.send("{invalid json}")
            error_msg = await ws.recv()
            data = json.loads(error_msg)

            assert data["type"] == "system"
            assert "Invalid JSON" in data["payload"]["error"]

        await server.stop()

    @pytest.mark.asyncio
    async def test_message_format(self):
        """Test that messages follow the correct format."""
        server = NotificationServer(host="127.0.0.1", port=8771)
        await server.start()

        async with websockets.connect("ws://127.0.0.1:8771") as ws:
            message = await ws.recv()
            data = json.loads(message)

            assert "type" in data
            assert "payload" in data
            assert "timestamp" in data

            assert isinstance(data["type"], str)
            assert isinstance(data["payload"], dict)
            assert isinstance(data["timestamp"], str)

        await server.stop()

    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        """Test the REST health endpoint."""
        server = NotificationServer(host="127.0.0.1", port=8772)
        await server.start()

        async with ClientSession() as session:
            async with session.get("http://127.0.0.1:9772/health") as response:
                assert response.status == 200
                data = await response.json()

                assert data["status"] == "healthy"
                assert "connected_clients" in data
                assert isinstance(data["connected_clients"], int)
                assert data["connected_clients"] == 0

        await server.stop()

    @pytest.mark.asyncio
    async def test_health_endpoint_with_clients(self):
        """Test health endpoint reflects connected client count."""
        server = NotificationServer(host="127.0.0.1", port=8773)
        await server.start()

        async def keep_connection_open():
            async with websockets.connect("ws://127.0.0.1:8773") as ws:
                greeting = await ws.recv()
                json.loads(greeting)

                await asyncio.sleep(0.5)

        async def check_health():
            await asyncio.sleep(0.1)
            async with ClientSession() as session:
                async with session.get("http://127.0.0.1:9773/health") as response:
                    data = await response.json()
                    return data["connected_clients"]

        task1 = asyncio.create_task(keep_connection_open())
        task2 = asyncio.create_task(keep_connection_open())
        count_task = asyncio.create_task(check_health())

        count = await count_task
        assert count == 2

        await asyncio.gather(task1, task2)
        await server.stop()

    @pytest.mark.asyncio
    async def test_disconnect_handling(self):
        """Test that disconnected clients are removed from registry."""
        server = NotificationServer(host="127.0.0.1", port=8774)
        await server.start()

        async with websockets.connect("ws://127.0.0.1:8774") as ws:
            greeting = await ws.recv()
            json.loads(greeting)

            assert server.registry.get_count() == 1

        await asyncio.sleep(0.1)
        assert server.registry.get_count() == 0

        await server.stop()

    @pytest.mark.asyncio
    async def test_broadcast_to_empty_registry(self):
        """Test broadcasting when no clients are connected."""
        server = NotificationServer(host="127.0.0.1", port=8775)
        await server.start()

        await server.broadcast({"text": "Test message"})
        assert server.registry.get_count() == 0

        await server.stop()

    @pytest.mark.asyncio
    async def test_direct_message(self):
        """Test sending a direct message to a specific client."""
        server = NotificationServer(host="127.0.0.1", port=8776)
        await server.start()

        client_id = None

        async def receiver():
            nonlocal client_id
            async with websockets.connect("ws://127.0.0.1:8776") as ws:
                greeting = await ws.recv()
                data = json.loads(greeting)
                client_id = data["payload"]["client_id"]

                direct_msg = await ws.recv()
                return json.loads(direct_msg)

        async def send_direct():
            await asyncio.sleep(0.1)
            while client_id is None:
                await asyncio.sleep(0.01)

            await server.send_direct(client_id, {
                "text": "Direct message",
                "from": "sender"
            })

        receiver_task = asyncio.create_task(receiver())
        sender_task = asyncio.create_task(send_direct())

        msg = await receiver_task
        await sender_task

        assert msg["type"] == "direct"
        assert msg["payload"]["text"] == "Direct message"
        assert msg["payload"]["from"] == "sender"

        await server.stop()

    @pytest.mark.asyncio
    async def test_direct_message_to_nonexistent_client(self):
        """Test sending a direct message to a client that doesn't exist."""
        server = NotificationServer(host="127.0.0.1", port=8777)
        await server.start()

        await server.send_direct("nonexistent-client-id", {"text": "test"})
        assert server.registry.get_count() == 0

        await server.stop()

    @pytest.mark.asyncio
    async def test_client_id_uniqueness(self):
        """Test that each client gets a unique ID."""
        server = NotificationServer(host="127.0.0.1", port=8778)
        await server.start()

        async def get_client_id():
            async with websockets.connect("ws://127.0.0.1:8778") as ws:
                greeting = await ws.recv()
                data = json.loads(greeting)
                return data["payload"]["client_id"]

        tasks = [get_client_id() for _ in range(10)]
        client_ids = await asyncio.gather(*tasks)

        assert len(set(client_ids)) == 10

        await server.stop()

    @pytest.mark.asyncio
    async def test_message_timestamp_format(self):
        """Test that timestamps are in ISO format."""
        server = NotificationServer(host="127.0.0.1", port=8779)
        await server.start()

        async with websockets.connect("ws://127.0.0.1:8779") as ws:
            message = await ws.recv()
            data = json.loads(message)
            timestamp = data["timestamp"]

            try:
                from datetime import datetime
                datetime.fromisoformat(timestamp)
                valid = True
            except ValueError:
                valid = False

            assert valid, f"Timestamp {timestamp} is not valid ISO format"

        await server.stop()
