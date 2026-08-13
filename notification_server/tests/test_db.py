from notification_server.db import MessageStore, resolve_database_path


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
