import pytest
import time
from datetime import datetime, timedelta, timezone

from models import ShortURL
from storage import Storage


class TestStorage:
    @pytest.fixture
    def storage(self):
        s = Storage(":memory:")
        yield s
        s.close()

    def test_insert_and_get(self, storage):
        entry = ShortURL(
            short_code="abc123",
            original_url="https://example.com",
            created_at=ShortURL.now_iso(),
        )
        storage.insert(entry)
        fetched = storage.get("abc123")
        assert fetched is not None
        assert fetched.short_code == "abc123"
        assert fetched.original_url == "https://example.com"
        assert fetched.access_count == 0

    def test_get_nonexistent(self, storage):
        assert storage.get("nope") is None

    def test_increment_access(self, storage):
        entry = ShortURL(
            short_code="cnt456",
            original_url="https://count.example",
            created_at=ShortURL.now_iso(),
        )
        storage.insert(entry)
        storage.increment_access("cnt456")
        storage.increment_access("cnt456")
        assert storage.get("cnt456").access_count == 2

    def test_exists(self, storage):
        entry = ShortURL(
            short_code="ex789",
            original_url="https://exists.example",
            created_at=ShortURL.now_iso(),
        )
        storage.insert(entry)
        assert storage.exists("ex789") is True
        assert storage.exists("missing") is False

    def test_purge_expired(self, storage):
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

        storage.insert(ShortURL(
            short_code="exp1",
            original_url="https://expired.example",
            created_at=past,
            expires_at=past,
        ))
        storage.insert(ShortURL(
            short_code="exp2",
            original_url="https://active.example",
            created_at=ShortURL.now_iso(),
            expires_at=future,
        ))
        storage.insert(ShortURL(
            short_code="exp3",
            original_url="https://noexpiry.example",
            created_at=ShortURL.now_iso(),
        ))

        purged = storage.purge_expired()
        assert purged == 1
        assert storage.get("exp1") is None
        assert storage.get("exp2") is not None
        assert storage.get("exp3") is not None

    def test_insert_overwrites(self, storage):
        e1 = ShortURL(short_code="ow", original_url="https://first.example",
                       created_at=ShortURL.now_iso())
        e2 = ShortURL(short_code="ow", original_url="https://second.example",
                       created_at=ShortURL.now_iso())
        storage.insert(e1)
        storage.insert(e2)
        assert storage.get("ow").original_url == "https://second.example"
