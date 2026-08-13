import os
import tempfile

import pytest

from notification_server.messages import Message
from notification_server.persistence import MessageStore


@pytest.fixture
def store():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    s = MessageStore(path)
    try:
        yield s
    finally:
        s.close()
        os.remove(path)


def test_save_assigns_incrementing_ids(store):
    id1 = store.save(Message(type="broadcast", payload={"text": "a"}, timestamp="t1"))
    id2 = store.save(Message(type="broadcast", payload={"text": "b"}, timestamp="t2"))
    assert id2 == id1 + 1


def test_fetch_returns_most_recent_first(store):
    store.save(Message(type="broadcast", payload={"text": "first"}, timestamp="t1"))
    store.save(Message(type="broadcast", payload={"text": "second"}, timestamp="t2"))
    store.save(Message(type="broadcast", payload={"text": "third"}, timestamp="t3"))

    rows = store.fetch(limit=50, offset=0)
    assert [r["payload"]["text"] for r in rows] == ["third", "second", "first"]


def test_fetch_respects_limit_and_offset(store):
    for i in range(5):
        store.save(Message(type="broadcast", payload={"i": i}, timestamp=f"t{i}"))

    page1 = store.fetch(limit=2, offset=0)
    page2 = store.fetch(limit=2, offset=2)
    assert [r["payload"]["i"] for r in page1] == [4, 3]
    assert [r["payload"]["i"] for r in page2] == [2, 1]


def test_fetch_preserves_channel_type_and_timestamp(store):
    store.save(Message(type="broadcast", payload={"text": "hi"}, timestamp="2026-01-01T00:00:00+00:00", channel="alerts"))
    [row] = store.fetch()
    assert row["channel"] == "alerts"
    assert row["type"] == "broadcast"
    assert row["timestamp"] == "2026-01-01T00:00:00+00:00"
    assert row["payload"] == {"text": "hi"}
    assert isinstance(row["id"], int)


def test_fetch_channel_defaults_to_none_when_absent(store):
    store.save(Message(type="broadcast", payload={"text": "no channel"}, timestamp="t1"))
    [row] = store.fetch()
    assert row["channel"] is None


def test_fetch_empty_store_returns_empty_list(store):
    assert store.fetch() == []


def test_data_survives_reopening_the_same_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        store1 = MessageStore(path)
        store1.save(Message(type="broadcast", payload={"text": "persisted"}, timestamp="t1"))
        store1.close()

        store2 = MessageStore(path)
        rows = store2.fetch()
        store2.close()
        assert len(rows) == 1
        assert rows[0]["payload"]["text"] == "persisted"
    finally:
        os.remove(path)
