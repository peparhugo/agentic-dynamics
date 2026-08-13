from notification_server.storage import FlatFileStorage


def test_append_and_read_events(tmp_path):
    storage = FlatFileStorage(tmp_path / "events.jsonl")
    storage.append_event({"event": "connect", "client_id": "abc"})
    storage.append_event({"event": "disconnect", "client_id": "abc"})

    events = storage.read_events()
    assert events == [
        {"event": "connect", "client_id": "abc"},
        {"event": "disconnect", "client_id": "abc"},
    ]


def test_read_events_missing_file_returns_empty_list(tmp_path):
    storage = FlatFileStorage(tmp_path / "missing.jsonl")
    assert storage.read_events() == []


def test_storage_is_a_flat_file_not_a_database(tmp_path):
    path = tmp_path / "events.jsonl"
    storage = FlatFileStorage(path)
    storage.append_event({"event": "connect", "client_id": "abc"})

    assert path.exists()
    raw = path.read_text(encoding="utf-8")
    assert raw.count("\n") == 1
    assert raw.strip().startswith("{")


def test_clear_removes_file(tmp_path):
    path = tmp_path / "events.jsonl"
    storage = FlatFileStorage(path)
    storage.append_event({"event": "connect", "client_id": "abc"})
    storage.clear()
    assert not path.exists()
    assert storage.read_events() == []


def test_creates_parent_directories(tmp_path):
    path = tmp_path / "nested" / "dir" / "events.jsonl"
    storage = FlatFileStorage(path)
    storage.append_event({"event": "connect", "client_id": "abc"})
    assert path.exists()
