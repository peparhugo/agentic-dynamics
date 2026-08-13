from notification_server.registry import ClientRegistry


def test_add_generates_unique_ids():
    registry = ClientRegistry()
    id1 = registry.add(object())
    id2 = registry.add(object())
    assert id1 != id2
    assert registry.count() == 2


def test_get_returns_registered_websocket():
    registry = ClientRegistry()
    ws = object()
    client_id = registry.add(ws)
    assert registry.get(client_id) is ws


def test_get_unknown_id_returns_none():
    registry = ClientRegistry()
    assert registry.get("does-not-exist") is None


def test_remove_deletes_client():
    registry = ClientRegistry()
    client_id = registry.add(object())
    registry.remove(client_id)
    assert registry.count() == 0
    assert registry.get(client_id) is None


def test_remove_unknown_id_is_noop():
    registry = ClientRegistry()
    registry.remove("does-not-exist")
    assert registry.count() == 0


def test_all_returns_independent_copy():
    registry = ClientRegistry()
    client_id = registry.add(object())
    snapshot = registry.all()
    snapshot.clear()
    assert registry.count() == 1
    assert client_id in registry.all()
