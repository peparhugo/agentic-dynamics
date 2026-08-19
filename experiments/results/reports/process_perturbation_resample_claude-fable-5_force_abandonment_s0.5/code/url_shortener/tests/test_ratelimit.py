import sqlite3

import pytest

from app.db import SCHEMA
from app.ratelimit import check_and_record


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    yield conn
    conn.close()


def test_allows_up_to_the_limit(db):
    for _ in range(3):
        assert check_and_record("bucket-a", max_requests=3, window_seconds=60, db=db) is True


def test_blocks_beyond_the_limit(db):
    for _ in range(3):
        check_and_record("bucket-b", max_requests=3, window_seconds=60, db=db)
    assert check_and_record("bucket-b", max_requests=3, window_seconds=60, db=db) is False


def test_window_expiry_allows_requests_again(db):
    now = 1_000_000.0
    for i in range(3):
        check_and_record("bucket-c", max_requests=3, window_seconds=10, db=db, now=now + i)

    assert check_and_record("bucket-c", max_requests=3, window_seconds=10, db=db, now=now + 5) is False
    # advance past the window
    assert check_and_record("bucket-c", max_requests=3, window_seconds=10, db=db, now=now + 21) is True


def test_buckets_are_independent(db):
    for _ in range(3):
        check_and_record("bucket-d1", max_requests=3, window_seconds=60, db=db)
    assert check_and_record("bucket-d2", max_requests=3, window_seconds=60, db=db) is True
