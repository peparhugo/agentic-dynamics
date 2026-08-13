from notification_server.store import MessageStore


def test_save_and_get_messages_round_trip(tmp_path):
    store = MessageStore(str(tmp_path / "history.db"))
    store.save_message("broadcast", {"text": "hi"}, "2026-08-13T00:00:00+00:00", channel=None)
    messages = store.get_messages()
    assert len(messages) == 1
    msg = messages[0]
    assert msg["type"] == "broadcast"
    assert msg["payload"] == {"text": "hi"}
    assert msg["channel"] is None
    assert msg["timestamp"] == "2026-08-13T00:00:00+00:00"
    assert isinstance(msg["id"], int)
    store.close()


def test_save_message_records_channel():
    store = MessageStore(":memory:")
    store.save_message("broadcast", {"text": "fire!"}, "2026-08-13T00:00:00+00:00", channel="alerts")
    messages = store.get_messages()
    assert messages[0]["channel"] == "alerts"
    store.close()


def test_get_messages_orders_most_recent_first():
    store = MessageStore(":memory:")
    for i in range(3):
        store.save_message("broadcast", {"seq": i}, f"2026-08-13T00:00:0{i}+00:00")
    messages = store.get_messages()
    assert [m["payload"]["seq"] for m in messages] == [2, 1, 0]
    store.close()


def test_get_messages_respects_limit_and_offset():
    store = MessageStore(":memory:")
    for i in range(5):
        store.save_message("broadcast", {"seq": i}, f"2026-08-13T00:00:0{i}+00:00")
    page = store.get_messages(limit=2, offset=1)
    assert [m["payload"]["seq"] for m in page] == [3, 2]
    store.close()


def test_get_messages_empty_store_returns_empty_list():
    store = MessageStore(":memory:")
    assert store.get_messages() == []
    store.close()


def test_store_persists_across_reopen(tmp_path):
    path = str(tmp_path / "history.db")
    store = MessageStore(path)
    store.save_message("direct", {"text": "psst"}, "2026-08-13T00:00:00+00:00")
    store.close()

    reopened = MessageStore(path)
    messages = reopened.get_messages()
    assert len(messages) == 1
    assert messages[0]["payload"] == {"text": "psst"}
    reopened.close()


def test_get_history_returns_only_matching_channel_in_chronological_order():
    store = MessageStore(":memory:")
    for i in range(3):
        store.save_message("broadcast", {"seq": i}, f"2026-08-13T00:00:0{i}+00:00", channel="alerts")
    store.save_message("broadcast", {"seq": "other"}, "2026-08-13T00:00:00+00:00", channel="chat")
    messages, has_more = store.get_history(channel="alerts")
    assert [m["payload"]["seq"] for m in messages] == [0, 1, 2]
    assert has_more is False
    store.close()


def test_get_history_filters_by_since():
    store = MessageStore(":memory:")
    for i in range(5):
        store.save_message("broadcast", {"seq": i}, f"2026-08-13T00:00:0{i}+00:00", channel="alerts")
    messages, has_more = store.get_history(channel="alerts", since="2026-08-13T00:00:02+00:00")
    assert [m["payload"]["seq"] for m in messages] == [3, 4]
    assert has_more is False
    store.close()


def test_get_history_paginates_with_has_more_flag():
    store = MessageStore(":memory:")
    for i in range(5):
        store.save_message("broadcast", {"seq": i}, f"2026-08-13T00:00:0{i}+00:00", channel="alerts")
    messages, has_more = store.get_history(channel="alerts", limit=2)
    assert [m["payload"]["seq"] for m in messages] == [0, 1]
    assert has_more is True

    messages, has_more = store.get_history(channel="alerts", since="2026-08-13T00:00:01+00:00", limit=2)
    assert [m["payload"]["seq"] for m in messages] == [2, 3]
    assert has_more is True

    messages, has_more = store.get_history(channel="alerts", since="2026-08-13T00:00:03+00:00", limit=2)
    assert [m["payload"]["seq"] for m in messages] == [4]
    assert has_more is False
    store.close()


def test_get_history_empty_channel_returns_empty_list():
    store = MessageStore(":memory:")
    messages, has_more = store.get_history(channel="does-not-exist")
    assert messages == []
    assert has_more is False
    store.close()


def test_delete_older_than_removes_only_stale_messages():
    store = MessageStore(":memory:")
    store.save_message("broadcast", {"seq": "old"}, "2026-08-01T00:00:00+00:00")
    store.save_message("broadcast", {"seq": "new"}, "2026-08-13T00:00:00+00:00")
    deleted = store.delete_older_than("2026-08-10T00:00:00+00:00")
    assert deleted == 1
    remaining = store.get_messages()
    assert len(remaining) == 1
    assert remaining[0]["payload"]["seq"] == "new"
    store.close()


def test_delete_older_than_returns_zero_when_nothing_is_stale():
    store = MessageStore(":memory:")
    store.save_message("broadcast", {"seq": "new"}, "2026-08-13T00:00:00+00:00")
    deleted = store.delete_older_than("2026-08-01T00:00:00+00:00")
    assert deleted == 0
    assert len(store.get_messages()) == 1
    store.close()
