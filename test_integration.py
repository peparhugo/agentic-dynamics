"""
Integration tests for Redis pub/sub and SQLite message persistence.

Tests cover:
- Message storage in SQLite database
- REST /messages endpoint with pagination
- Redis broker connectivity
- Client connection state in Redis
- Message retrieval by channel
"""

import pytest
import json
import asyncio
import os
import tempfile
from datetime import datetime
from database import MessageDatabase
from redis_broker import RedisBroker
from app import (
    ClientRegistry,
    create_message,
)


@pytest.fixture
def temp_db():
    """Provide a temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    db = MessageDatabase(db_path=db_path)
    yield db

    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


class TestMessageDatabase:
    """Tests for SQLite message storage."""

    def test_database_initialization(self, temp_db):
        """Test that database initializes correctly."""
        assert os.path.exists(temp_db.db_path)

    def test_store_message(self, temp_db):
        """Test storing a message in the database."""
        msg_id = temp_db.store_message(
            channel="alerts",
            msg_type="broadcast",
            payload={"text": "test message"},
            timestamp="2024-08-13T12:00:00"
        )

        assert msg_id is not None
        assert msg_id > 0

    def test_get_messages(self, temp_db):
        """Test retrieving messages from the database."""
        temp_db.store_message(
            channel="alerts",
            msg_type="broadcast",
            payload={"text": "message 1"},
            timestamp="2024-08-13T12:00:00"
        )
        temp_db.store_message(
            channel="alerts",
            msg_type="broadcast",
            payload={"text": "message 2"},
            timestamp="2024-08-13T12:01:00"
        )

        messages = temp_db.get_messages(limit=10)
        assert len(messages) == 2

        # Most recent first
        assert messages[0]["payload"]["text"] == "message 2"
        assert messages[1]["payload"]["text"] == "message 1"

    def test_get_messages_with_pagination(self, temp_db):
        """Test message retrieval with limit and offset."""
        for i in range(5):
            temp_db.store_message(
                channel="alerts",
                msg_type="broadcast",
                payload={"index": i},
                timestamp=f"2024-08-13T12:{i:02d}:00"
            )

        # First page
        messages = temp_db.get_messages(limit=2, offset=0)
        assert len(messages) == 2

        # Second page
        messages = temp_db.get_messages(limit=2, offset=2)
        assert len(messages) == 2

        # Out of range
        messages = temp_db.get_messages(limit=10, offset=100)
        assert len(messages) == 0

    def test_get_messages_by_channel(self, temp_db):
        """Test filtering messages by channel."""
        temp_db.store_message("alerts", "broadcast", {"text": "alert 1"}, "2024-08-13T12:00:00")
        temp_db.store_message("alerts", "broadcast", {"text": "alert 2"}, "2024-08-13T12:01:00")
        temp_db.store_message("system", "broadcast", {"text": "system 1"}, "2024-08-13T12:02:00")

        alerts = temp_db.get_messages_by_channel("alerts")
        assert len(alerts) == 2
        assert all(m["channel"] == "alerts" for m in alerts)

        system = temp_db.get_messages_by_channel("system")
        assert len(system) == 1
        assert system[0]["channel"] == "system"

    def test_get_message_count(self, temp_db):
        """Test getting total message count."""
        assert temp_db.get_message_count() == 0

        temp_db.store_message("alerts", "broadcast", {"text": "msg 1"}, "2024-08-13T12:00:00")
        temp_db.store_message("alerts", "broadcast", {"text": "msg 2"}, "2024-08-13T12:01:00")
        temp_db.store_message("system", "broadcast", {"text": "msg 3"}, "2024-08-13T12:02:00")

        assert temp_db.get_message_count() == 3

    def test_message_payload_encoding(self, temp_db):
        """Test that complex payloads are stored correctly."""
        complex_payload = {
            "nested": {"key": "value"},
            "list": [1, 2, 3],
            "bool": True,
            "null": None,
            "number": 42.5
        }

        temp_db.store_message("test", "broadcast", complex_payload, "2024-08-13T12:00:00")

        messages = temp_db.get_messages(limit=1)
        assert len(messages) == 1
        assert messages[0]["payload"] == complex_payload

    def test_clear_messages(self, temp_db):
        """Test clearing all messages from database."""
        temp_db.store_message("alerts", "broadcast", {"text": "msg"}, "2024-08-13T12:00:00")
        assert temp_db.get_message_count() == 1

        temp_db.clear_messages()
        assert temp_db.get_message_count() == 0

    def test_message_with_different_types(self, temp_db):
        """Test storing messages with different types."""
        types = ["broadcast", "direct", "system", "custom"]

        for msg_type in types:
            temp_db.store_message(
                "test",
                msg_type,
                {"type": msg_type},
                "2024-08-13T12:00:00"
            )

        messages = temp_db.get_messages(limit=10)
        assert len(messages) == len(types)

        stored_types = {m["type"] for m in messages}
        assert stored_types == set(types)

    def test_timestamp_persistence(self, temp_db):
        """Test that timestamps are stored correctly."""
        timestamp = "2024-08-13T12:30:45.123456"
        temp_db.store_message("test", "broadcast", {}, timestamp)

        messages = temp_db.get_messages(limit=1)
        assert messages[0]["timestamp"] == timestamp


@pytest.mark.asyncio
class TestRedisBroker:
    """Tests for Redis broker functionality."""

    async def test_broker_initialization(self):
        """Test that broker initializes correctly."""
        broker = RedisBroker()
        assert broker.redis_url is not None
        assert not broker._connected

    async def test_broker_disconnect_when_not_connected(self):
        """Test disconnect gracefully when not connected."""
        broker = RedisBroker()
        await broker.disconnect()  # Should not raise

    async def test_broker_publish_when_disconnected(self):
        """Test publish gracefully handles disconnected state."""
        broker = RedisBroker()
        # Should not raise even though not connected
        await broker.publish("test_channel", {"message": "test"})

    async def test_broker_is_connected_false_initially(self):
        """Test is_connected returns False initially."""
        broker = RedisBroker()
        is_connected = await broker.is_connected()
        assert is_connected is False

    async def test_store_client_connection_when_disconnected(self):
        """Test storing client connection when broker is disconnected."""
        broker = RedisBroker()
        # Should not raise
        await broker.store_client_connection("test_client")

    async def test_remove_client_connection_when_disconnected(self):
        """Test removing client connection when broker is disconnected."""
        broker = RedisBroker()
        # Should not raise
        await broker.remove_client_connection("test_client")

    async def test_get_client_connections_when_disconnected(self):
        """Test getting client connections when disconnected."""
        broker = RedisBroker()
        connections = await broker.get_client_connections()
        assert connections == {}


@pytest.mark.asyncio
class TestMessagePersistenceIntegration:
    """Integration tests for message persistence with ClientRegistry."""

    @pytest.fixture
    def temp_db_fixture(self):
        """Provide a temporary database."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        db = MessageDatabase(db_path=db_path)
        yield db
        if os.path.exists(db_path):
            os.unlink(db_path)

    async def test_broadcast_and_store_stores_message(self, temp_db_fixture):
        """Test that broadcast_and_store persists messages."""
        # Temporarily replace the global database
        import app
        original_db = app.database
        original_broker = app.broker

        app.database = temp_db_fixture
        app.broker = RedisBroker()

        try:
            registry = ClientRegistry()

            class MockWebSocket:
                async def send(self, message):
                    pass

            ws = MockWebSocket()
            await registry.register("client1", ws)

            message = create_message("broadcast", {"text": "test"})
            await registry.broadcast_and_store(message, channel="alerts")

            # Verify message is stored
            messages = temp_db_fixture.get_messages(limit=10)
            assert len(messages) > 0
            assert messages[0]["type"] == "broadcast"

        finally:
            app.database = original_db
            app.broker = original_broker

    async def test_system_messages_are_stored(self, temp_db_fixture):
        """Test that system messages are stored."""
        import app
        original_db = app.database
        original_broker = app.broker

        app.database = temp_db_fixture
        app.broker = RedisBroker()

        try:
            registry = ClientRegistry()

            class MockWebSocket:
                async def send(self, message):
                    pass

            ws = MockWebSocket()
            await registry.register("client1", ws)

            # Simulate connection message
            message = create_message("system", {
                "event": "client_connected",
                "client_id": "client1"
            })
            await registry.broadcast_and_store(message)

            # Verify system message is stored
            messages = temp_db_fixture.get_messages(limit=10)
            assert len(messages) > 0
            assert messages[0]["type"] == "system"
            assert messages[0]["payload"]["event"] == "client_connected"

        finally:
            app.database = original_db
            app.broker = original_broker


@pytest.mark.asyncio
class TestMessagesRESTEndpoint:
    """Tests for the /messages REST endpoint."""

    async def test_messages_endpoint_format(self, temp_db_fixture):
        """Test that /messages endpoint returns correct format."""
        from aiohttp import web
        from app import messages_handler

        # Mock request object
        class MockRequest:
            def __init__(self, query_dict=None):
                self.query = query_dict or {}

        import app
        original_db = app.database
        app.database = temp_db_fixture

        try:
            # Add test data
            temp_db_fixture.store_message("alerts", "broadcast", {"text": "msg1"}, "2024-08-13T12:00:00")
            temp_db_fixture.store_message("system", "broadcast", {"text": "msg2"}, "2024-08-13T12:01:00")

            request = MockRequest()
            response = await messages_handler(request)
            data = json.loads(response.text)

            assert "messages" in data
            assert "count" in data
            assert "total" in data
            assert "limit" in data
            assert "offset" in data
            assert "timestamp" in data
            assert data["count"] == 2
            assert data["total"] == 2

        finally:
            app.database = original_db

    async def test_messages_endpoint_with_channel_filter(self, temp_db_fixture):
        """Test /messages endpoint with channel filter."""
        from app import messages_handler

        class MockRequest:
            def __init__(self, query_dict=None):
                self.query = query_dict or {}

        import app
        original_db = app.database
        app.database = temp_db_fixture

        try:
            temp_db_fixture.store_message("alerts", "broadcast", {"text": "alert"}, "2024-08-13T12:00:00")
            temp_db_fixture.store_message("system", "broadcast", {"text": "sys"}, "2024-08-13T12:01:00")
            temp_db_fixture.store_message("alerts", "broadcast", {"text": "alert2"}, "2024-08-13T12:02:00")

            request = MockRequest({"channel": "alerts"})
            response = await messages_handler(request)
            data = json.loads(response.text)

            assert data["count"] == 2
            assert all(m["channel"] == "alerts" for m in data["messages"])

        finally:
            app.database = original_db

    async def test_messages_endpoint_pagination(self, temp_db_fixture):
        """Test /messages endpoint pagination."""
        from app import messages_handler

        class MockRequest:
            def __init__(self, query_dict=None):
                self.query = query_dict or {}

        import app
        original_db = app.database
        app.database = temp_db_fixture

        try:
            for i in range(5):
                temp_db_fixture.store_message("test", "broadcast", {"index": i}, f"2024-08-13T12:{i:02d}:00")

            # First page
            request = MockRequest({"limit": "2", "offset": "0"})
            response = await messages_handler(request)
            data = json.loads(response.text)

            assert data["count"] == 2
            assert data["limit"] == 2
            assert data["offset"] == 0

            # Second page
            request = MockRequest({"limit": "2", "offset": "2"})
            response = await messages_handler(request)
            data = json.loads(response.text)

            assert data["count"] == 2
            assert data["limit"] == 2
            assert data["offset"] == 2

        finally:
            app.database = original_db

    async def test_messages_endpoint_limit_cap(self, temp_db_fixture):
        """Test /messages endpoint enforces limit cap."""
        from app import messages_handler

        class MockRequest:
            def __init__(self, query_dict=None):
                self.query = query_dict or {}

        import app
        original_db = app.database
        app.database = temp_db_fixture

        try:
            for i in range(10):
                temp_db_fixture.store_message("test", "broadcast", {"index": i}, f"2024-08-13T12:{i:02d}:00")

            # Request with limit > 500
            request = MockRequest({"limit": "1000"})
            response = await messages_handler(request)
            data = json.loads(response.text)

            assert data["limit"] == 500

        finally:
            app.database = original_db


@pytest.fixture
def temp_db_fixture():
    """Provide a temporary database."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    db = MessageDatabase(db_path=db_path)
    yield db
    if os.path.exists(db_path):
        os.unlink(db_path)


class TestDatabaseConcurrency:
    """Test concurrent database operations."""

    @pytest.mark.asyncio
    async def test_concurrent_message_storage(self, temp_db_fixture):
        """Test storing messages concurrently."""
        async def store_message(index):
            temp_db_fixture.store_message(
                f"channel_{index % 3}",
                "broadcast",
                {"index": index},
                f"2024-08-13T12:{index:02d}:00"
            )

        # Store 20 messages concurrently
        tasks = [store_message(i) for i in range(20)]
        await asyncio.gather(*tasks)

        assert temp_db_fixture.get_message_count() == 20

    def test_message_ordering(self, temp_db_fixture):
        """Test that messages are returned in correct order."""
        for i in range(10):
            temp_db_fixture.store_message(
                "test",
                "broadcast",
                {"index": i},
                f"2024-08-13T12:{i:02d}:00"
            )

        messages = temp_db_fixture.get_messages(limit=10)

        # Most recent first
        for i, msg in enumerate(messages):
            assert msg["payload"]["index"] == 9 - i
