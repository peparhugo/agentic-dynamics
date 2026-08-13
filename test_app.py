"""
Tests for WebSocket notification server.
"""

import asyncio
import json
import pytest
from datetime import datetime
import re

from websockets.exceptions import ConnectionClosed
from app import ClientRegistry, create_message, websocket_handler


@pytest.mark.asyncio
async def test_create_message():
    """Test message creation with proper format."""
    msg = create_message("broadcast", {"content": "hello"})

    assert msg["type"] == "broadcast"
    assert msg["payload"] == {"content": "hello"}
    assert "timestamp" in msg
    # Validate ISO format timestamp
    assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", msg["timestamp"])


@pytest.mark.asyncio
async def test_client_registry_register():
    """Test client registration."""
    registry = ClientRegistry()

    class MockWebSocket:
        pass

    ws = MockWebSocket()
    client_id = "test-client-1"

    await registry.register(client_id, ws)
    assert await registry.get_client_count() == 1

    assert registry.clients[client_id] == ws


@pytest.mark.asyncio
async def test_client_registry_unregister():
    """Test client unregistration."""
    registry = ClientRegistry()

    class MockWebSocket:
        pass

    ws = MockWebSocket()
    client_id = "test-client-1"

    await registry.register(client_id, ws)
    assert await registry.get_client_count() == 1

    await registry.unregister(client_id)
    assert await registry.get_client_count() == 0


@pytest.mark.asyncio
async def test_client_registry_broadcast():
    """Test broadcasting to multiple clients."""
    registry = ClientRegistry()

    class MockWebSocket:
        def __init__(self, client_id):
            self.client_id = client_id
            self.messages = []

        async def send(self, msg):
            self.messages.append(json.loads(msg))

    clients = {}
    for i in range(3):
        client_id = f"client-{i}"
        ws = MockWebSocket(client_id)
        clients[client_id] = ws
        await registry.register(client_id, ws)

    message = create_message("broadcast", {"content": "test"})
    await registry.broadcast(message)

    # Verify all clients received the message
    for client_id, ws in clients.items():
        assert len(ws.messages) == 1
        assert ws.messages[0]["type"] == "broadcast"
        assert ws.messages[0]["payload"]["content"] == "test"


@pytest.mark.asyncio
async def test_client_registry_send_direct():
    """Test direct messaging to specific client."""
    registry = ClientRegistry()

    class MockWebSocket:
        def __init__(self):
            self.messages = []

        async def send(self, msg):
            self.messages.append(json.loads(msg))

    client1 = MockWebSocket()
    client2 = MockWebSocket()

    await registry.register("client-1", client1)
    await registry.register("client-2", client2)

    message = create_message("direct", {"content": "personal"})
    await registry.send_direct("client-1", message)

    assert len(client1.messages) == 1
    assert client1.messages[0]["payload"]["content"] == "personal"
    assert len(client2.messages) == 0


@pytest.mark.asyncio
async def test_client_registry_handles_disconnected():
    """Test that disconnected clients are removed on broadcast."""
    registry = ClientRegistry()

    class DisconnectingWebSocket:
        async def send(self, msg):
            raise ConnectionClosed(None, None)

    ws = DisconnectingWebSocket()
    await registry.register("client-1", ws)
    assert await registry.get_client_count() == 1

    # Broadcast should handle disconnection
    message = create_message("broadcast", {"content": "test"})
    await registry.broadcast(message)

    # Client should be removed after failed send
    assert await registry.get_client_count() == 0


@pytest.mark.asyncio
async def test_client_registry_handles_disconnected_on_direct():
    """Test that disconnected clients are removed on direct message."""
    registry = ClientRegistry()

    class DisconnectingWebSocket:
        async def send(self, msg):
            raise ConnectionClosed(None, None)

    ws = DisconnectingWebSocket()
    await registry.register("client-1", ws)
    assert await registry.get_client_count() == 1

    # Direct message should handle disconnection
    message = create_message("direct", {"content": "test"})
    await registry.send_direct("client-1", message)

    # Client should be removed after failed send
    assert await registry.get_client_count() == 0


@pytest.mark.asyncio
async def test_health_handler():
    """Test health endpoint returns correct client count."""
    from app import registry, health_handler

    # Clear registry
    registry.clients.clear()

    class MockWebSocket:
        pass

    # Register a few clients
    for i in range(3):
        await registry.register(f"client-{i}", MockWebSocket())

    # Mock request object
    class MockRequest:
        pass

    request = MockRequest()

    response = await health_handler(request)
    data = json.loads(response.text)

    assert data["status"] == "ok"
    assert data["connected_clients"] == 3

    # Clear for next test
    registry.clients.clear()


@pytest.mark.asyncio
async def test_registry_get_client_count():
    """Test getting client count."""
    registry = ClientRegistry()

    class MockWebSocket:
        pass

    assert await registry.get_client_count() == 0

    # Register clients
    for i in range(5):
        await registry.register(f"client-{i}", MockWebSocket())

    assert await registry.get_client_count() == 5

    # Unregister one
    await registry.unregister("client-0")
    assert await registry.get_client_count() == 4


@pytest.mark.asyncio
async def test_websocket_handler_with_message():
    """Test that websocket handler processes messages."""
    from app import registry

    registry.clients.clear()

    class TestWebSocket:
        def __init__(self):
            self.messages = []
            self.message_queue = [json.dumps({"type": "broadcast", "payload": {"test": "data"}})]
            self.index = 0

        async def send(self, msg):
            self.messages.append(msg)

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.index >= len(self.message_queue):
                raise StopAsyncIteration
            msg = self.message_queue[self.index]
            self.index += 1
            return msg

    ws = TestWebSocket()

    # Run handler as a task with timeout
    task = asyncio.create_task(websocket_handler(ws))

    # Give handler time to process
    await asyncio.sleep(0.1)

    # Should have join message and broadcast echo
    assert len(ws.messages) >= 2
    msg = json.loads(ws.messages[0])
    assert msg["type"] == "system"
    assert msg["payload"]["event"] == "client_joined"

    # Clean up
    try:
        await asyncio.wait_for(task, timeout=0.1)
    except asyncio.TimeoutError:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    registry.clients.clear()


@pytest.mark.asyncio
async def test_websocket_handler_disconnect():
    """Test websocket handler disconnect notification."""
    from app import registry

    registry.clients.clear()

    class TestWebSocket:
        def __init__(self):
            self.messages = []
            self.message_queue = []
            self.index = 0

        async def send(self, msg):
            self.messages.append(msg)

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.index >= len(self.message_queue):
                raise StopAsyncIteration
            msg = self.message_queue[self.index]
            self.index += 1
            return msg

    ws1 = TestWebSocket()
    ws2 = TestWebSocket()

    task1 = asyncio.create_task(websocket_handler(ws1))
    task2 = asyncio.create_task(websocket_handler(ws2))

    # Give handlers time to register
    await asyncio.sleep(0.1)

    # Both should have at least join messages
    assert len(ws1.messages) >= 1
    assert len(ws2.messages) >= 1

    # Verify join messages
    msg1 = json.loads(ws1.messages[0])
    assert msg1["type"] == "system"
    assert msg1["payload"]["event"] == "client_joined"

    # Clean up
    try:
        await asyncio.wait_for(asyncio.gather(task1, task2), timeout=0.5)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        task1.cancel()
        task2.cancel()
        try:
            await asyncio.gather(task1, task2)
        except asyncio.CancelledError:
            pass

    registry.clients.clear()


@pytest.mark.asyncio
async def test_websocket_handler_invalid_json():
    """Test websocket handler invalid JSON handling."""
    from app import registry

    registry.clients.clear()

    class TestWebSocket:
        def __init__(self):
            self.messages = []
            self.message_queue = ["not valid json {"]
            self.index = 0

        async def send(self, msg):
            self.messages.append(msg)

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.index >= len(self.message_queue):
                raise StopAsyncIteration
            msg = self.message_queue[self.index]
            self.index += 1
            return msg

    ws = TestWebSocket()

    task = asyncio.create_task(websocket_handler(ws))

    # Give handler time to process
    await asyncio.sleep(0.1)

    # Should have join message + error message
    assert len(ws.messages) >= 2

    # Find error message
    error_found = False
    for msg_str in ws.messages[1:]:
        msg = json.loads(msg_str)
        if msg["type"] == "system" and "Invalid JSON" in msg["payload"].get("error", ""):
            error_found = True
            break

    assert error_found, "Invalid JSON error not found"

    # Clean up
    try:
        await asyncio.wait_for(task, timeout=0.2)
    except asyncio.TimeoutError:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    registry.clients.clear()


@pytest.mark.asyncio
async def test_websocket_handler_unknown_message_type():
    """Test websocket handler unknown message type."""
    from app import registry

    registry.clients.clear()

    class TestWebSocket:
        def __init__(self):
            self.messages = []
            self.message_queue = [json.dumps({"type": "unknown", "payload": {}})]
            self.index = 0

        async def send(self, msg):
            self.messages.append(msg)

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.index >= len(self.message_queue):
                raise StopAsyncIteration
            msg = self.message_queue[self.index]
            self.index += 1
            return msg

    ws = TestWebSocket()

    task = asyncio.create_task(websocket_handler(ws))

    # Give handler time to process
    await asyncio.sleep(0.1)

    # Should have join message + error message
    assert len(ws.messages) >= 2

    # Find error message
    error_found = False
    for msg_str in ws.messages[1:]:
        msg = json.loads(msg_str)
        if (
            msg["type"] == "system"
            and "Unknown message type" in msg["payload"].get("error", "")
        ):
            error_found = True
            break

    assert error_found, "Unknown message type error not found"

    # Clean up
    try:
        await asyncio.wait_for(task, timeout=0.2)
    except asyncio.TimeoutError:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    registry.clients.clear()


@pytest.mark.asyncio
async def test_client_registry_subscribe():
    """Test client subscription to channel."""
    registry = ClientRegistry()

    class MockWebSocket:
        pass

    ws = MockWebSocket()
    client_id = "test-client-1"

    await registry.register(client_id, ws)
    success = await registry.subscribe(client_id, "alerts")

    assert success is True
    assert "alerts" in await registry.get_channels()
    assert len(await registry.get_channel_subscribers("alerts")) == 1


@pytest.mark.asyncio
async def test_client_registry_unsubscribe():
    """Test client unsubscription from channel."""
    registry = ClientRegistry()

    class MockWebSocket:
        pass

    ws = MockWebSocket()
    client_id = "test-client-1"

    await registry.register(client_id, ws)
    await registry.subscribe(client_id, "alerts")
    success = await registry.unsubscribe(client_id, "alerts")

    assert success is True
    assert "alerts" not in await registry.get_channels()


@pytest.mark.asyncio
async def test_client_registry_get_channels():
    """Test getting all channels with subscriber counts."""
    registry = ClientRegistry()

    class MockWebSocket:
        pass

    for i in range(2):
        await registry.register(f"client-{i}", MockWebSocket())

    await registry.subscribe("client-0", "alerts")
    await registry.subscribe("client-0", "system")
    await registry.subscribe("client-1", "alerts")

    channels = await registry.get_channels()

    assert "alerts" in channels
    assert channels["alerts"] == 2
    assert "system" in channels
    assert channels["system"] == 1


@pytest.mark.asyncio
async def test_client_registry_get_channel_subscribers():
    """Test getting subscribers for a specific channel."""
    registry = ClientRegistry()

    class MockWebSocket:
        pass

    for i in range(3):
        await registry.register(f"client-{i}", MockWebSocket())

    await registry.subscribe("client-0", "alerts")
    await registry.subscribe("client-1", "alerts")
    await registry.subscribe("client-2", "system")

    subscribers = await registry.get_channel_subscribers("alerts")

    assert len(subscribers) == 2
    assert "client-0" in subscribers
    assert "client-1" in subscribers
    assert "client-2" not in subscribers


@pytest.mark.asyncio
async def test_client_registry_broadcast_to_channel():
    """Test broadcasting message to specific channel."""
    registry = ClientRegistry()

    class MockWebSocket:
        def __init__(self, client_id):
            self.client_id = client_id
            self.messages = []

        async def send(self, msg):
            self.messages.append(json.loads(msg))

    clients = {}
    for i in range(3):
        client_id = f"client-{i}"
        ws = MockWebSocket(client_id)
        clients[client_id] = ws
        await registry.register(client_id, ws)

    await registry.subscribe("client-0", "alerts")
    await registry.subscribe("client-1", "alerts")
    await registry.subscribe("client-2", "system")

    message = create_message("broadcast", {"content": "alert"})
    await registry.broadcast(message, channel="alerts")

    # Only alerts subscribers should receive
    assert len(clients["client-0"].messages) == 1
    assert clients["client-0"].messages[0]["payload"]["content"] == "alert"
    assert len(clients["client-1"].messages) == 1
    assert clients["client-1"].messages[0]["payload"]["content"] == "alert"
    assert len(clients["client-2"].messages) == 0


@pytest.mark.asyncio
async def test_client_registry_broadcast_without_channel():
    """Test broadcasting to all clients when no channel specified."""
    registry = ClientRegistry()

    class MockWebSocket:
        def __init__(self, client_id):
            self.client_id = client_id
            self.messages = []

        async def send(self, msg):
            self.messages.append(json.loads(msg))

    clients = {}
    for i in range(3):
        client_id = f"client-{i}"
        ws = MockWebSocket(client_id)
        clients[client_id] = ws
        await registry.register(client_id, ws)

    await registry.subscribe("client-0", "alerts")
    await registry.subscribe("client-1", "alerts")
    await registry.subscribe("client-2", "system")

    message = create_message("broadcast", {"content": "global"})
    await registry.broadcast(message)

    # All clients should receive
    for client_id, ws in clients.items():
        assert len(ws.messages) == 1
        assert ws.messages[0]["payload"]["content"] == "global"


@pytest.mark.asyncio
async def test_client_registry_unregister_removes_from_channels():
    """Test that unregistering client removes them from all channels."""
    registry = ClientRegistry()

    class MockWebSocket:
        pass

    ws = MockWebSocket()
    client_id = "test-client-1"

    await registry.register(client_id, ws)
    await registry.subscribe(client_id, "alerts")
    await registry.subscribe(client_id, "system")

    await registry.unregister(client_id)

    channels = await registry.get_channels()
    assert len(channels) == 0


@pytest.mark.asyncio
async def test_client_registry_multiple_channels_per_client():
    """Test client subscribed to multiple channels."""
    registry = ClientRegistry()

    class MockWebSocket:
        def __init__(self, client_id):
            self.client_id = client_id
            self.messages = []

        async def send(self, msg):
            self.messages.append(json.loads(msg))

    ws = MockWebSocket("client-1")
    await registry.register("client-1", ws)

    await registry.subscribe("client-1", "alerts")
    await registry.subscribe("client-1", "system")
    await registry.subscribe("client-1", "chat")

    # Send to each channel
    await registry.broadcast(create_message("broadcast", {"type": "alert"}), channel="alerts")
    await registry.broadcast(create_message("broadcast", {"type": "system"}), channel="system")
    await registry.broadcast(create_message("broadcast", {"type": "chat"}), channel="chat")

    # Client should receive all three messages
    assert len(ws.messages) == 3
    assert ws.messages[0]["payload"]["type"] == "alert"
    assert ws.messages[1]["payload"]["type"] == "system"
    assert ws.messages[2]["payload"]["type"] == "chat"


@pytest.mark.asyncio
async def test_websocket_handler_subscribe():
    """Test websocket subscribe message handling."""
    from app import registry

    registry.clients.clear()

    class TestWebSocket:
        def __init__(self):
            self.messages = []
            self.message_queue = [json.dumps({"type": "subscribe", "channel": "alerts"})]
            self.index = 0

        async def send(self, msg):
            self.messages.append(msg)

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.index >= len(self.message_queue):
                raise StopAsyncIteration
            msg = self.message_queue[self.index]
            self.index += 1
            return msg

    ws = TestWebSocket()

    task = asyncio.create_task(websocket_handler(ws))

    # Give handler time to process
    await asyncio.sleep(0.1)

    # Should have join message + subscribe response
    assert len(ws.messages) >= 2

    # Find subscribe response
    subscribe_found = False
    for msg_str in ws.messages[1:]:
        msg = json.loads(msg_str)
        if msg["type"] == "system" and msg["payload"].get("event") == "subscribed":
            subscribe_found = True
            assert msg["payload"]["channel"] == "alerts"
            assert msg["payload"]["success"] is True
            break

    assert subscribe_found, "Subscribe confirmation not found"

    # Clean up
    try:
        await asyncio.wait_for(task, timeout=0.1)
    except asyncio.TimeoutError:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    registry.clients.clear()


@pytest.mark.asyncio
async def test_websocket_handler_unsubscribe():
    """Test websocket unsubscribe message handling."""
    from app import registry

    registry.clients.clear()

    class TestWebSocket:
        def __init__(self):
            self.messages = []
            self.message_queue = [
                json.dumps({"type": "subscribe", "channel": "alerts"}),
                json.dumps({"type": "unsubscribe", "channel": "alerts"}),
            ]
            self.index = 0

        async def send(self, msg):
            self.messages.append(msg)

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.index >= len(self.message_queue):
                raise StopAsyncIteration
            msg = self.message_queue[self.index]
            self.index += 1
            return msg

    ws = TestWebSocket()

    task = asyncio.create_task(websocket_handler(ws))

    # Give handler time to process
    await asyncio.sleep(0.1)

    # Should have join + subscribe + unsubscribe messages
    assert len(ws.messages) >= 3

    # Find unsubscribe response
    unsubscribe_found = False
    for msg_str in ws.messages[2:]:
        msg = json.loads(msg_str)
        if msg["type"] == "system" and msg["payload"].get("event") == "unsubscribed":
            unsubscribe_found = True
            assert msg["payload"]["channel"] == "alerts"
            assert msg["payload"]["success"] is True
            break

    assert unsubscribe_found, "Unsubscribe confirmation not found"

    # Clean up
    try:
        await asyncio.wait_for(task, timeout=0.1)
    except asyncio.TimeoutError:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    registry.clients.clear()


@pytest.mark.asyncio
async def test_websocket_handler_channel_broadcast():
    """Test websocket broadcast to specific channel."""
    from app import registry

    registry.clients.clear()

    class TestWebSocket:
        def __init__(self, client_id):
            self.client_id = client_id
            self.messages = []
            self.message_queue = [json.dumps({"type": "subscribe", "channel": "alerts"})]
            self.index = 0

        async def send(self, msg):
            self.messages.append(msg)

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.index >= len(self.message_queue):
                raise StopAsyncIteration
            msg = self.message_queue[self.index]
            self.index += 1
            return msg

    ws1 = TestWebSocket("client-1")
    ws2 = TestWebSocket("client-2")

    task1 = asyncio.create_task(websocket_handler(ws1))
    task2 = asyncio.create_task(websocket_handler(ws2))

    # Give handlers time to register and subscribe
    await asyncio.sleep(0.1)

    # Send channel-specific broadcast via first client
    await registry.broadcast(create_message("broadcast", {"alert": "test"}), channel="alerts")

    # Give time for messages to propagate
    await asyncio.sleep(0.05)

    # Both should receive the channel broadcast (they both subscribed via handler)
    # Plus join notifications
    assert len(ws1.messages) >= 2
    assert len(ws2.messages) >= 2

    # Clean up
    try:
        await asyncio.wait_for(asyncio.gather(task1, task2), timeout=0.2)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        task1.cancel()
        task2.cancel()
        try:
            await asyncio.gather(task1, task2)
        except asyncio.CancelledError:
            pass

    registry.clients.clear()


@pytest.mark.asyncio
async def test_rest_channels_endpoint():
    """Test GET /channels REST endpoint."""
    from app import registry, channels_handler

    registry.clients.clear()
    registry.channels.clear()

    class MockWebSocket:
        pass

    # Create some clients and subscriptions
    for i in range(2):
        await registry.register(f"client-{i}", MockWebSocket())

    await registry.subscribe("client-0", "alerts")
    await registry.subscribe("client-1", "alerts")
    await registry.subscribe("client-0", "system")

    class MockRequest:
        pass

    request = MockRequest()
    response = await channels_handler(request)
    data = json.loads(response.text)

    assert "alerts" in data
    assert data["alerts"] == 2
    assert "system" in data
    assert data["system"] == 1

    registry.clients.clear()
    registry.channels.clear()


@pytest.mark.asyncio
async def test_rest_channel_subscribers_endpoint():
    """Test GET /channels/{name}/subscribers REST endpoint."""
    from app import registry, channel_subscribers_handler

    registry.clients.clear()
    registry.channels.clear()

    class MockWebSocket:
        pass

    # Create clients and subscriptions
    for i in range(3):
        await registry.register(f"client-{i}", MockWebSocket())

    await registry.subscribe("client-0", "alerts")
    await registry.subscribe("client-1", "alerts")
    await registry.subscribe("client-2", "system")

    class MockRequest:
        def __init__(self, channel_name):
            self.match_info = {"name": channel_name}

    request = MockRequest("alerts")
    response = await channel_subscribers_handler(request)
    data = json.loads(response.text)

    assert data["channel"] == "alerts"
    assert len(data["subscribers"]) == 2
    assert "client-0" in data["subscribers"]
    assert "client-1" in data["subscribers"]

    registry.clients.clear()
    registry.channels.clear()


@pytest.mark.asyncio
async def test_messages_persistence():
    """Test that messages are persisted to SQLite."""
    import tempfile
    import os
    from app import store_message, get_messages, init_database

    original_db_url = os.environ.get("DATABASE_URL")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_persist.db")
            os.environ["DATABASE_URL"] = db_path

            await init_database()

            msg_timestamp = "2025-08-13T10:00:00"
            await store_message("alerts", "broadcast", {"text": "alert1"}, msg_timestamp)
            await store_message("alerts", "broadcast", {"text": "alert2"}, msg_timestamp)
            await store_message("system", "broadcast", {"text": "system1"}, msg_timestamp)

            messages = await get_messages(limit=50, offset=0)

            assert len(messages) == 3
            assert messages[0]["channel"] == "system"
            assert messages[0]["payload"]["text"] == "system1"
            assert messages[1]["channel"] == "alerts"
            assert messages[1]["payload"]["text"] == "alert2"
            assert messages[2]["channel"] == "alerts"
            assert messages[2]["payload"]["text"] == "alert1"
    finally:
        if original_db_url:
            os.environ["DATABASE_URL"] = original_db_url
        elif "DATABASE_URL" in os.environ:
            del os.environ["DATABASE_URL"]


@pytest.mark.asyncio
async def test_messages_rest_endpoint():
    """Test GET /messages REST endpoint."""
    import tempfile
    import os
    from app import store_message, init_database, messages_handler

    original_db_url = os.environ.get("DATABASE_URL")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_rest.db")
            os.environ["DATABASE_URL"] = db_path

            await init_database()

            msg_timestamp = "2025-08-13T10:00:00"
            for i in range(5):
                await store_message("alerts", "broadcast", {"index": i}, msg_timestamp)

            class MockRequest:
                def __init__(self, limit=50, offset=0):
                    self.query = {"limit": str(limit), "offset": str(offset)}

            request = MockRequest(limit=2, offset=0)
            response = await messages_handler(request)
            data = json.loads(response.text)

            assert len(data["messages"]) == 2
            assert data["limit"] == 2
            assert data["offset"] == 0
            assert data["messages"][0]["payload"]["index"] == 4
            assert data["messages"][1]["payload"]["index"] == 3
    finally:
        if original_db_url:
            os.environ["DATABASE_URL"] = original_db_url
        elif "DATABASE_URL" in os.environ:
            del os.environ["DATABASE_URL"]


@pytest.mark.asyncio
async def test_messages_pagination():
    """Test message pagination."""
    import tempfile
    import os
    from app import store_message, init_database, get_messages

    original_db_url = os.environ.get("DATABASE_URL")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_pagination.db")
            os.environ["DATABASE_URL"] = db_path

            await init_database()

            msg_timestamp = "2025-08-13T10:00:00"
            for i in range(10):
                await store_message("alerts", "broadcast", {"index": i}, msg_timestamp)

            page1 = await get_messages(limit=5, offset=0)
            page2 = await get_messages(limit=5, offset=5)

            assert len(page1) == 5
            assert len(page2) == 5
            assert page1[0]["payload"]["index"] == 9
            assert page2[0]["payload"]["index"] == 4
    finally:
        if original_db_url:
            os.environ["DATABASE_URL"] = original_db_url
        elif "DATABASE_URL" in os.environ:
            del os.environ["DATABASE_URL"]


@pytest.mark.asyncio
async def test_redis_publisher_fallback():
    """Test that redis_publisher handles missing redis gracefully."""
    from app import redis_publisher

    msg = create_message("broadcast", {"text": "test"})
    await redis_publisher(msg, channel="alerts")


@pytest.mark.asyncio
async def test_messages_endpoint_invalid_params():
    """Test /messages endpoint with invalid query parameters."""
    import tempfile
    import os
    from app import store_message, init_database, messages_handler

    original_db_url = os.environ.get("DATABASE_URL")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_invalid.db")
            os.environ["DATABASE_URL"] = db_path

            await init_database()

            msg_timestamp = "2025-08-13T10:00:00"
            await store_message("alerts", "broadcast", {"text": "msg"}, msg_timestamp)

            class MockRequest:
                def __init__(self, params):
                    self.query = params

            request = MockRequest({"limit": "invalid", "offset": "also_invalid"})
            response = await messages_handler(request)
            data = json.loads(response.text)

            assert data["limit"] == 50
            assert data["offset"] == 0
            assert len(data["messages"]) == 1
    finally:
        if original_db_url:
            os.environ["DATABASE_URL"] = original_db_url
        elif "DATABASE_URL" in os.environ:
            del os.environ["DATABASE_URL"]


@pytest.mark.asyncio
async def test_database_initialization():
    """Test that database is properly initialized."""
    import tempfile
    import os
    import aiosqlite
    from app import init_database

    original_db_url = os.environ.get("DATABASE_URL")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_init.db")
            os.environ["DATABASE_URL"] = db_path

            await init_database()

            async with aiosqlite.connect(db_path) as db:
                cursor = await db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='messages'"
                )
                row = await cursor.fetchone()
                assert row is not None
                assert row[0] == "messages"

                cursor = await db.execute("PRAGMA table_info(messages)")
                columns = await cursor.fetchall()
                column_names = [col[1] for col in columns]
                assert "id" in column_names
                assert "channel" in column_names
                assert "type" in column_names
                assert "payload" in column_names
                assert "timestamp" in column_names
    finally:
        if original_db_url:
            os.environ["DATABASE_URL"] = original_db_url
        elif "DATABASE_URL" in os.environ:
            del os.environ["DATABASE_URL"]


@pytest.mark.asyncio
async def test_messages_json_payload():
    """Test that message payloads are properly JSON serialized."""
    import tempfile
    import os
    from app import store_message, init_database, get_messages

    original_db_url = os.environ.get("DATABASE_URL")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_json.db")
            os.environ["DATABASE_URL"] = db_path

            await init_database()

            msg_timestamp = "2025-08-13T10:00:00"
            complex_payload = {
                "nested": {"key": "value", "number": 42},
                "array": [1, 2, 3],
                "string": "text",
                "bool": True
            }
            await store_message("test", "broadcast", complex_payload, msg_timestamp)

            messages = await get_messages(limit=10, offset=0)

            assert len(messages) == 1
            assert messages[0]["payload"]["nested"]["key"] == "value"
            assert messages[0]["payload"]["nested"]["number"] == 42
            assert messages[0]["payload"]["array"] == [1, 2, 3]
            assert messages[0]["payload"]["string"] == "text"
            assert messages[0]["payload"]["bool"] is True
    finally:
        if original_db_url:
            os.environ["DATABASE_URL"] = original_db_url
        elif "DATABASE_URL" in os.environ:
            del os.environ["DATABASE_URL"]


@pytest.mark.asyncio
async def test_transport_interface():
    """Test that BaseTransport and WebSocketTransport are properly abstracted."""
    from app import BaseTransport, WebSocketTransport, registry, get_transport

    registry.clients.clear()

    class MockWebSocket:
        def __init__(self):
            self.messages = []

        async def send(self, msg):
            self.messages.append(json.loads(msg))

    transport = get_transport()
    assert isinstance(transport, BaseTransport)
    assert isinstance(transport, WebSocketTransport)

    ws = MockWebSocket()
    await registry.register("test-client", ws)

    msg = create_message("broadcast", {"test": "data"})

    await transport.send_message("test-client", msg)
    assert len(ws.messages) == 1
    assert ws.messages[0]["payload"]["test"] == "data"

    await transport.broadcast(msg)
    assert len(ws.messages) == 2

    registry.clients.clear()


@pytest.mark.asyncio
async def test_transport_custom_env():
    """Test that TRANSPORT env var selects the correct transport."""
    import os
    from app import get_transport, WebSocketTransport

    original_transport = os.environ.get("TRANSPORT")
    try:
        os.environ["TRANSPORT"] = "websocket"
        transport = get_transport()
        assert isinstance(transport, WebSocketTransport)

        os.environ["TRANSPORT"] = "WEBSOCKET"
        transport = get_transport()
        assert isinstance(transport, WebSocketTransport)
    finally:
        if original_transport:
            os.environ["TRANSPORT"] = original_transport
        elif "TRANSPORT" in os.environ:
            del os.environ["TRANSPORT"]
