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


# ── list_history ─────────────────────────────────────────────────────


def test_list_history_returns_chronological_order(store):
    store.record("broadcast", {"n": 1}, "2026-01-01T00:00:00Z", channel="alerts")
    store.record("broadcast", {"n": 2}, "2026-01-01T00:00:01Z", channel="alerts")
    store.record("broadcast", {"n": 3}, "2026-01-01T00:00:02Z", channel="alerts")
    messages, has_more = store.list_history(channel="alerts")
    assert [m["payload"]["n"] for m in messages] == [1, 2, 3]
    assert has_more is False


def test_list_history_filters_by_channel(store):
    store.record("broadcast", {"text": "in"}, "2026-01-01T00:00:00Z", channel="alerts")
    store.record("broadcast", {"text": "out"}, "2026-01-01T00:00:01Z", channel="other")
    messages, _has_more = store.list_history(channel="alerts")
    assert [m["payload"]["text"] for m in messages] == ["in"]


def test_list_history_filters_by_since(store):
    store.record("broadcast", {"n": 1}, "2026-01-01T00:00:00Z", channel="alerts")
    store.record("broadcast", {"n": 2}, "2026-01-01T00:00:01Z", channel="alerts")
    store.record("broadcast", {"n": 3}, "2026-01-01T00:00:02Z", channel="alerts")
    messages, _has_more = store.list_history(channel="alerts", since="2026-01-01T00:00:00Z")
    assert [m["payload"]["n"] for m in messages] == [2, 3]


def test_list_history_paginates_with_has_more(store):
    for i in range(5):
        store.record("broadcast", {"n": i}, f"2026-01-01T00:00:0{i}Z", channel="alerts")
    page1, has_more1 = store.list_history(channel="alerts", limit=2)
    assert [m["payload"]["n"] for m in page1] == [0, 1]
    assert has_more1 is True

    page2, has_more2 = store.list_history(
        channel="alerts", since=page1[-1]["timestamp"], limit=2
    )
    assert [m["payload"]["n"] for m in page2] == [2, 3]
    assert has_more2 is True

    page3, has_more3 = store.list_history(
        channel="alerts", since=page2[-1]["timestamp"], limit=2
    )
    assert [m["payload"]["n"] for m in page3] == [4]
    assert has_more3 is False


def test_list_history_without_channel_returns_all(store):
    store.record("broadcast", {"text": "a"}, "2026-01-01T00:00:00Z", channel="alerts")
    store.record("direct", {"text": "b"}, "2026-01-01T00:00:01Z")
    messages, _has_more = store.list_history()
    assert len(messages) == 2


def test_list_history_empty_store(store):
    messages, has_more = store.list_history(channel="alerts")
    assert messages == []
    assert has_more is False


async def test_alist_history(store):
    await store.arecord("broadcast", {"text": "hi"}, "2026-01-01T00:00:00Z", "alerts")
    messages, has_more = await store.alist_history(channel="alerts")
    assert len(messages) == 1
    assert has_more is False


# ── delete_older_than ───────────────────────────────────────────────


def test_delete_older_than_removes_expired_messages(store):
    store.record("broadcast", {"text": "old"}, "2026-01-01T00:00:00Z")
    store.record("broadcast", {"text": "new"}, "2026-01-10T00:00:00Z")
    deleted = store.delete_older_than("2026-01-05T00:00:00Z")
    assert deleted == 1
    remaining = store.list_messages()
    assert [m["payload"]["text"] for m in remaining] == ["new"]


def test_delete_older_than_returns_zero_when_nothing_expired(store):
    store.record("broadcast", {"text": "new"}, "2026-01-10T00:00:00Z")
    assert store.delete_older_than("2026-01-01T00:00:00Z") == 0


async def test_adelete_older_than(store):
    await store.arecord("broadcast", {"text": "old"}, "2026-01-01T00:00:00Z")
    deleted = await store.adelete_older_than("2026-01-05T00:00:00Z")
    assert deleted == 1
