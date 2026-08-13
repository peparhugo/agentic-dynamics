import pytest

from notification_server.store import MessageStore


@pytest.fixture
def store(tmp_path):
    return MessageStore(str(tmp_path / "messages.db"))


def test_record_returns_incrementing_ids(store):
    id1 = store.record("broadcast", {"text": "hi"}, "2026-01-01T00:00:00Z")
    id2 = store.record("broadcast", {"text": "there"}, "2026-01-01T00:00:01Z")
    assert id2 == id1 + 1


def test_list_messages_returns_most_recent_first(store):
    store.record("broadcast", {"text": "first"}, "2026-01-01T00:00:00Z")
    store.record("broadcast", {"text": "second"}, "2026-01-01T00:00:01Z")
    messages = store.list_messages()
    assert [m["payload"]["text"] for m in messages] == ["second", "first"]


def test_list_messages_respects_limit_and_offset(store):
    for i in range(5):
        store.record("broadcast", {"n": i}, f"2026-01-01T00:00:0{i}Z")
    page1 = store.list_messages(limit=2, offset=0)
    page2 = store.list_messages(limit=2, offset=2)
    assert [m["payload"]["n"] for m in page1] == [4, 3]
    assert [m["payload"]["n"] for m in page2] == [2, 1]


def test_record_stores_channel(store):
    store.record("broadcast", {"text": "hi"}, "2026-01-01T00:00:00Z", channel="alerts")
    [message] = store.list_messages()
    assert message["channel"] == "alerts"


def test_record_channel_defaults_to_none(store):
    store.record("direct", {"text": "hi"}, "2026-01-01T00:00:00Z")
    [message] = store.list_messages()
    assert message["channel"] is None


def test_list_messages_empty_store(store):
    assert store.list_messages() == []


async def test_async_record_and_list(store):
    await store.arecord("broadcast", {"text": "async"}, "2026-01-01T00:00:00Z", "alerts")
    messages = await store.alist_messages()
    assert len(messages) == 1
    assert messages[0]["payload"]["text"] == "async"
    assert messages[0]["channel"] == "alerts"


def test_store_persists_across_instances(tmp_path):
    path = str(tmp_path / "shared.db")
    store1 = MessageStore(path)
    store1.record("broadcast", {"text": "persisted"}, "2026-01-01T00:00:00Z")
    store2 = MessageStore(path)
    messages = store2.list_messages()
    assert len(messages) == 1
    assert messages[0]["payload"]["text"] == "persisted"
