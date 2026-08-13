from notification_server.db import (
    DEFAULT_MESSAGE_TTL_DAYS,
    MessageStore,
    resolve_database_path,
    resolve_message_ttl_days,
)


def test_save_message_returns_stored_record(tmp_path):
    store = MessageStore(tmp_path / "messages.db")
    record = store.save_message("broadcast", {"text": "hi"}, "2024-01-01T00:00:00+00:00")
    assert record["id"] == 1
    assert record["channel"] is None
    assert record["type"] == "broadcast"
    assert record["payload"] == {"text": "hi"}
    assert record["timestamp"] == "2024-01-01T00:00:00+00:00"


def test_save_message_stores_channel(tmp_path):
    store = MessageStore(tmp_path / "messages.db")
    record = store.save_message(
        "broadcast", {"text": "fire!"}, "2024-01-01T00:00:00+00:00", channel="alerts"
    )
    assert record["channel"] == "alerts"


def test_list_messages_orders_most_recent_first(tmp_path):
    store = MessageStore(tmp_path / "messages.db")
    store.save_message("broadcast", {"n": 1}, "t1")
    store.save_message("broadcast", {"n": 2}, "t2")
    store.save_message("broadcast", {"n": 3}, "t3")

    messages = store.list_messages()
    assert [m["payload"]["n"] for m in messages] == [3, 2, 1]


def test_list_messages_respects_limit_and_offset(tmp_path):
    store = MessageStore(tmp_path / "messages.db")
    for i in range(5):
        store.save_message("broadcast", {"n": i}, f"t{i}")

    page1 = store.list_messages(limit=2, offset=0)
    page2 = store.list_messages(limit=2, offset=2)
    assert [m["payload"]["n"] for m in page1] == [4, 3]
    assert [m["payload"]["n"] for m in page2] == [2, 1]


def test_list_messages_empty_store_returns_empty_list(tmp_path):
    store = MessageStore(tmp_path / "messages.db")
    assert store.list_messages() == []


def test_clear_removes_all_messages(tmp_path):
    store = MessageStore(tmp_path / "messages.db")
    store.save_message("broadcast", {"n": 1}, "t1")
    store.clear()
    assert store.list_messages() == []


def test_creates_parent_directories(tmp_path):
    path = tmp_path / "nested" / "dir" / "messages.db"
    store = MessageStore(path)
    store.save_message("broadcast", {"n": 1}, "t1")
    assert path.exists()


def test_resolve_database_path_defaults_to_env(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", str(tmp_path / "from_env.db"))
    assert resolve_database_path() == tmp_path / "from_env.db"


def test_resolve_database_path_supports_sqlite_url_scheme(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert resolve_database_path("sqlite:////tmp/somewhere.db") == __import__("pathlib").Path(
        "/tmp/somewhere.db"
    )


def test_resolve_database_path_falls_back_to_default(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from notification_server.db import DEFAULT_DB_PATH

    assert resolve_database_path() == DEFAULT_DB_PATH


# ── list_by_channel (GET /history) ──────────────────────────────


def test_list_by_channel_returns_only_matching_channel_in_chronological_order(tmp_path):
    store = MessageStore(tmp_path / "messages.db")
    store.save_message("broadcast", {"n": 1}, "2024-01-01T00:00:01+00:00", channel="alerts")
    store.save_message("broadcast", {"n": 2}, "2024-01-01T00:00:02+00:00", channel="chat")
    store.save_message("broadcast", {"n": 3}, "2024-01-01T00:00:03+00:00", channel="alerts")

    messages, has_more = store.list_by_channel("alerts")
    assert [m["payload"]["n"] for m in messages] == [1, 3]
    assert has_more is False


def test_list_by_channel_filters_by_since_exclusive(tmp_path):
    store = MessageStore(tmp_path / "messages.db")
    store.save_message("broadcast", {"n": 1}, "2024-01-01T00:00:01+00:00", channel="alerts")
    store.save_message("broadcast", {"n": 2}, "2024-01-01T00:00:02+00:00", channel="alerts")
    store.save_message("broadcast", {"n": 3}, "2024-01-01T00:00:03+00:00", channel="alerts")

    messages, _ = store.list_by_channel("alerts", since="2024-01-01T00:00:01+00:00")
    assert [m["payload"]["n"] for m in messages] == [2, 3]


def test_list_by_channel_sets_has_more_when_extra_rows_exist(tmp_path):
    store = MessageStore(tmp_path / "messages.db")
    for i in range(5):
        store.save_message(
            "broadcast", {"n": i}, f"2024-01-01T00:00:0{i}+00:00", channel="alerts"
        )

    page, has_more = store.list_by_channel("alerts", limit=3)
    assert [m["payload"]["n"] for m in page] == [0, 1, 2]
    assert has_more is True

    next_page, has_more = store.list_by_channel(
        "alerts", since=page[-1]["timestamp"], limit=3
    )
    assert [m["payload"]["n"] for m in next_page] == [3, 4]
    assert has_more is False


def test_list_by_channel_empty_for_unknown_channel(tmp_path):
    store = MessageStore(tmp_path / "messages.db")
    store.save_message("broadcast", {"n": 1}, "2024-01-01T00:00:01+00:00", channel="alerts")
    messages, has_more = store.list_by_channel("does-not-exist")
    assert messages == []
    assert has_more is False


# ── delete_older_than (message expiry) ──────────────────────────


def test_delete_older_than_removes_only_old_messages(tmp_path):
    store = MessageStore(tmp_path / "messages.db")
    store.save_message("broadcast", {"n": 1}, "2024-01-01T00:00:00+00:00", channel="alerts")
    store.save_message("broadcast", {"n": 2}, "2024-06-01T00:00:00+00:00", channel="alerts")

    removed = store.delete_older_than("2024-03-01T00:00:00+00:00")
    assert removed == 1
    remaining = store.list_messages()
    assert [m["payload"]["n"] for m in remaining] == [2]


def test_delete_older_than_returns_zero_when_nothing_expired(tmp_path):
    store = MessageStore(tmp_path / "messages.db")
    store.save_message("broadcast", {"n": 1}, "2024-06-01T00:00:00+00:00", channel="alerts")
    assert store.delete_older_than("2024-01-01T00:00:00+00:00") == 0


# ── resolve_message_ttl_days ─────────────────────────────────────


def test_resolve_message_ttl_days_prefers_explicit_argument(monkeypatch):
    monkeypatch.setenv("MESSAGE_TTL_DAYS", "30")
    assert resolve_message_ttl_days(3) == 3


def test_resolve_message_ttl_days_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("MESSAGE_TTL_DAYS", "14")
    assert resolve_message_ttl_days() == 14


def test_resolve_message_ttl_days_defaults_when_unset(monkeypatch):
    monkeypatch.delenv("MESSAGE_TTL_DAYS", raising=False)
    assert resolve_message_ttl_days() == DEFAULT_MESSAGE_TTL_DAYS
