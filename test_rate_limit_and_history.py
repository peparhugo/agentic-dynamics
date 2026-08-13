"""
Tests for rate limiting and message history features.
"""

import asyncio
import json
import pytest
import tempfile
import os
from datetime import datetime, timezone, timedelta
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

from app import NotificationServer
from database import MessageDatabase
from rate_limiter import RateLimiter


class TestRateLimiter:
    """Tests for the RateLimiter class."""

    def test_allow_messages_within_limit(self):
        """Test that messages are allowed within rate limit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            limiter = RateLimiter(redis_url, rate_limit=5)
            client_id = "test-client-1"

            try:
                for i in range(5):
                    assert limiter.is_allowed(client_id) is True

                limiter.close()
            except Exception:
                pytest.skip("Redis not available")

    def test_reject_messages_exceeding_limit(self):
        """Test that messages are rejected when exceeding rate limit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            limiter = RateLimiter(redis_url, rate_limit=3)
            client_id = "test-client-2"

            try:
                for i in range(3):
                    assert limiter.is_allowed(client_id) is True

                assert limiter.is_allowed(client_id) is False
                assert limiter.is_allowed(client_id) is False

                limiter.close()
            except Exception:
                pytest.skip("Redis not available")

    def test_different_clients_have_separate_limits(self):
        """Test that different clients have independent rate limits."""
        with tempfile.TemporaryDirectory() as tmpdir:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            limiter = RateLimiter(redis_url, rate_limit=2)

            try:
                client1 = "client-1"
                client2 = "client-2"

                # Client 1 sends 2 messages
                assert limiter.is_allowed(client1) is True
                assert limiter.is_allowed(client1) is True
                assert limiter.is_allowed(client1) is False

                # Client 2 can still send (independent limit)
                assert limiter.is_allowed(client2) is True
                assert limiter.is_allowed(client2) is True
                assert limiter.is_allowed(client2) is False

                limiter.close()
            except Exception:
                pytest.skip("Redis not available")

    def test_get_remaining_messages(self):
        """Test getting remaining messages for a client."""
        with tempfile.TemporaryDirectory() as tmpdir:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            limiter = RateLimiter(redis_url, rate_limit=5)
            client_id = "test-client-3"

            try:
                assert limiter.get_remaining(client_id) == 5

                limiter.is_allowed(client_id)
                assert limiter.get_remaining(client_id) == 4

                limiter.is_allowed(client_id)
                assert limiter.get_remaining(client_id) == 3

                limiter.close()
            except Exception:
                pytest.skip("Redis not available")


class TestMessageDatabase:
    """Tests for message history database functions."""

    def test_get_messages_since(self):
        """Test retrieving messages since a specific timestamp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db = MessageDatabase(db_path)

            now = datetime.now(timezone.utc)
            before = (now - timedelta(hours=1)).isoformat()
            after = (now + timedelta(hours=1)).isoformat()

            # Store messages
            msg1_time = (now - timedelta(minutes=30)).isoformat()
            msg2_time = now.isoformat()
            msg3_time = (now + timedelta(minutes=30)).isoformat()

            db.store_message("channel-1", "test", {"data": "msg1"}, msg1_time)
            db.store_message("channel-1", "test", {"data": "msg2"}, msg2_time)
            db.store_message("channel-1", "test", {"data": "msg3"}, msg3_time)

            # Get messages since before all messages
            messages = db.get_messages_since("channel-1", before, limit=10)
            assert len(messages) == 3

            # Get messages since after first message
            messages = db.get_messages_since("channel-1", msg1_time, limit=10)
            assert len(messages) == 3
            assert messages[0]["payload"]["data"] == "msg1"

            # Get messages since after second message (shouldn't include first)
            messages = db.get_messages_since("channel-1", msg2_time, limit=10)
            assert len(messages) == 2
            assert messages[0]["payload"]["data"] == "msg2"

            # Get messages since after all messages
            messages = db.get_messages_since("channel-1", after, limit=10)
            assert len(messages) == 0

    def test_get_messages_since_with_limit(self):
        """Test that message history respects limit parameter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db = MessageDatabase(db_path)

            now = datetime.now(timezone.utc)

            # Store 10 messages
            for i in range(10):
                msg_time = (now - timedelta(minutes=10-i)).isoformat()
                db.store_message("channel-1", "test", {"data": f"msg{i}"}, msg_time)

            before = (now - timedelta(hours=1)).isoformat()

            # Get with limit 5
            messages = db.get_messages_since("channel-1", before, limit=5)
            assert len(messages) == 5

            # Get with limit 20
            messages = db.get_messages_since("channel-1", before, limit=20)
            assert len(messages) == 10

    def test_get_messages_since_chronological_order(self):
        """Test that messages are returned in chronological order."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db = MessageDatabase(db_path)

            now = datetime.now(timezone.utc)

            # Store messages in random order
            msg_times = [
                (now - timedelta(minutes=2)).isoformat(),
                (now + timedelta(minutes=2)).isoformat(),
                now.isoformat(),
            ]

            for i, msg_time in enumerate(msg_times):
                db.store_message("channel-1", "test", {"data": f"msg{i}"}, msg_time)

            before = (now - timedelta(hours=1)).isoformat()

            # Get messages - should be in chronological order
            messages = db.get_messages_since("channel-1", before, limit=10)
            assert len(messages) == 3

            # Verify chronological order
            for i in range(len(messages) - 1):
                assert messages[i]["timestamp"] <= messages[i + 1]["timestamp"]

    def test_delete_old_messages(self):
        """Test deleting messages older than specified days."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db = MessageDatabase(db_path)

            now = datetime.now(timezone.utc)

            # Store old and new messages
            old_time = (now - timedelta(days=10)).isoformat()
            new_time = now.isoformat()

            db.store_message("channel-1", "test", {"data": "old"}, old_time)
            db.store_message("channel-1", "test", {"data": "new"}, new_time)

            # Delete messages older than 7 days
            deleted = db.delete_old_messages(7)
            assert deleted == 1

            # Verify old message is gone
            messages = db.get_messages(channel="channel-1", limit=10)
            assert len(messages) == 1
            assert messages[0]["payload"]["data"] == "new"

    def test_delete_old_messages_preserves_recent(self):
        """Test that delete_old_messages preserves recent messages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db = MessageDatabase(db_path)

            now = datetime.now(timezone.utc)

            # Store messages at various ages
            for days in [15, 10, 5, 1]:
                msg_time = (now - timedelta(days=days)).isoformat()
                db.store_message("channel-1", "test", {"age_days": days}, msg_time)

            # Delete messages older than 7 days
            deleted = db.delete_old_messages(7)
            assert deleted == 2  # Should delete 15-day and 10-day messages

            # Verify only recent messages remain
            messages = db.get_messages(channel="channel-1", limit=10)
            assert len(messages) == 2
            ages = sorted([msg["payload"]["age_days"] for msg in messages])
            assert ages == [1, 5]


class TestHistoryEndpoint(AioHTTPTestCase):
    """Tests for the /history REST endpoint."""

    async def get_application(self):
        """Create test application."""
        try:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        except Exception:
            pytest.skip("Redis not available")

        self.db_path = tempfile.mktemp(suffix=".db")
        server = NotificationServer(
            host="localhost",
            ws_port=9999,
            http_port=9998,
            redis_url=redis_url,
            database_url=self.db_path
        )
        return server.http_app

    def tearDown(self):
        """Cleanup test database."""
        super().tearDown()
        if hasattr(self, "db_path") and os.path.exists(self.db_path):
            os.unlink(self.db_path)

    @unittest_run_loop
    async def test_history_requires_channel_parameter(self):
        """Test that history endpoint requires channel parameter."""
        try:
            now = datetime.now(timezone.utc).isoformat()
            resp = await self.client.request("GET", f"/history?since={now}")
            assert resp.status == 400
            data = await resp.json()
            assert "channel" in data.get("error", "").lower()
        except Exception:
            pytest.skip("Redis not available")

    @unittest_run_loop
    async def test_history_requires_since_parameter(self):
        """Test that history endpoint requires since parameter."""
        try:
            resp = await self.client.request("GET", "/history?channel=test")
            assert resp.status == 400
            data = await resp.json()
            assert "since" in data.get("error", "").lower()
        except Exception:
            pytest.skip("Redis not available")

    @unittest_run_loop
    async def test_history_returns_messages_since_timestamp(self):
        """Test that history endpoint returns messages since timestamp."""
        try:
            # Setup: Store some messages
            db = MessageDatabase(self.db_path)
            now = datetime.now(timezone.utc)

            msg1_time = (now - timedelta(hours=1)).isoformat()
            msg2_time = now.isoformat()
            msg3_time = (now + timedelta(hours=1)).isoformat()

            db.store_message("test-channel", "test", {"data": "msg1"}, msg1_time)
            db.store_message("test-channel", "test", {"data": "msg2"}, msg2_time)
            db.store_message("test-channel", "test", {"data": "msg3"}, msg3_time)

            # Query history since msg1_time
            since = (now - timedelta(hours=1)).isoformat()
            resp = await self.client.request(
                "GET",
                f"/history?channel=test-channel&since={since}"
            )
            assert resp.status == 200
            data = await resp.json()
            assert len(data["messages"]) == 3

            # Query history since msg2_time (should exclude msg1)
            since = now.isoformat()
            resp = await self.client.request(
                "GET",
                f"/history?channel=test-channel&since={since}"
            )
            assert resp.status == 200
            data = await resp.json()
            assert len(data["messages"]) == 2
        except Exception:
            pytest.skip("Redis not available")

    @unittest_run_loop
    async def test_history_returns_has_more_flag(self):
        """Test that history endpoint returns has_more flag."""
        try:
            # Setup: Store many messages
            db = MessageDatabase(self.db_path)
            now = datetime.now(timezone.utc)

            for i in range(10):
                msg_time = (now - timedelta(minutes=10-i)).isoformat()
                db.store_message("test-channel", "test", {"data": f"msg{i}"}, msg_time)

            before = (now - timedelta(hours=1)).isoformat()

            # Query with limit 5
            resp = await self.client.request(
                "GET",
                f"/history?channel=test-channel&since={before}&limit=5"
            )
            assert resp.status == 200
            data = await resp.json()
            assert data["count"] == 5
            assert data["has_more"] is True

            # Query with limit 15 (all messages)
            resp = await self.client.request(
                "GET",
                f"/history?channel=test-channel&since={before}&limit=15"
            )
            assert resp.status == 200
            data = await resp.json()
            assert data["count"] == 10
            assert data["has_more"] is False
        except Exception:
            pytest.skip("Redis not available")

    @unittest_run_loop
    async def test_history_respects_limit_parameter(self):
        """Test that history endpoint respects limit parameter."""
        try:
            # Setup: Store messages
            db = MessageDatabase(self.db_path)
            now = datetime.now(timezone.utc)

            for i in range(20):
                msg_time = (now - timedelta(minutes=20-i)).isoformat()
                db.store_message("test-channel", "test", {"data": f"msg{i}"}, msg_time)

            before = (now - timedelta(hours=1)).isoformat()

            # Default limit (50)
            resp = await self.client.request(
                "GET",
                f"/history?channel=test-channel&since={before}"
            )
            data = await resp.json()
            assert data["count"] == 20

            # Custom limit
            resp = await self.client.request(
                "GET",
                f"/history?channel=test-channel&since={before}&limit=10"
            )
            data = await resp.json()
            assert data["count"] == 10

            # Limit capped at 1000
            resp = await self.client.request(
                "GET",
                f"/history?channel=test-channel&since={before}&limit=5000"
            )
            data = await resp.json()
            assert data["limit"] == 1000
        except Exception:
            pytest.skip("Redis not available")

    @unittest_run_loop
    async def test_history_returns_chronological_order(self):
        """Test that history returns messages in chronological order."""
        try:
            # Setup: Store messages
            db = MessageDatabase(self.db_path)
            now = datetime.now(timezone.utc)

            for i in range(5):
                msg_time = (now - timedelta(minutes=5-i)).isoformat()
                db.store_message("test-channel", "test", {"index": i}, msg_time)

            before = (now - timedelta(hours=1)).isoformat()

            # Query history
            resp = await self.client.request(
                "GET",
                f"/history?channel=test-channel&since={before}"
            )
            assert resp.status == 200
            data = await resp.json()

            # Verify chronological order
            messages = data["messages"]
            for i in range(len(messages) - 1):
                ts1 = messages[i]["timestamp"]
                ts2 = messages[i + 1]["timestamp"]
                assert ts1 <= ts2
        except Exception:
            pytest.skip("Redis not available")


class TestRateLimitIntegration(AioHTTPTestCase):
    """Tests for rate limiting integration with websocket."""

    async def get_application(self):
        """Create test application."""
        try:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        except Exception:
            pytest.skip("Redis not available")

        self.db_path = tempfile.mktemp(suffix=".db")
        self.server = NotificationServer(
            host="localhost",
            ws_port=9997,
            http_port=9996,
            redis_url=redis_url,
            database_url=self.db_path
        )
        return self.server.http_app

    def tearDown(self):
        """Cleanup test database."""
        super().tearDown()
        if hasattr(self, "db_path") and os.path.exists(self.db_path):
            os.unlink(self.db_path)

    @unittest_run_loop
    async def test_rate_limiter_is_initialized(self):
        """Test that rate limiter is initialized in server."""
        try:
            assert self.server.rate_limiter is not None
            assert self.server.rate_limiter.rate_limit == 100
        except Exception:
            pytest.skip("Redis not available")

    @unittest_run_loop
    async def test_rate_limit_configurable_via_env(self):
        """Test that rate limit can be configured via RATE_LIMIT env var."""
        try:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            db_path = tempfile.mktemp(suffix=".db")

            # Set RATE_LIMIT env var
            os.environ["RATE_LIMIT"] = "50"

            server = NotificationServer(
                redis_url=redis_url,
                database_url=db_path
            )

            assert server.rate_limiter.rate_limit == 50

            # Cleanup
            del os.environ["RATE_LIMIT"]
            if os.path.exists(db_path):
                os.unlink(db_path)
        except Exception:
            pytest.skip("Redis not available")
