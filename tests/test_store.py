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
