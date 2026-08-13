import threading

from notification_server.registry import ClientRegistry


def test_add_assigns_unique_id():
    registry = ClientRegistry()
    id1 = registry.add(object())
    id2 = registry.add(object())
    assert id1 != id2
    assert registry.count() == 2


def test_get_returns_added_client():
    registry = ClientRegistry()
    sentinel = object()
    client_id = registry.add(sentinel)
    assert registry.get(client_id) is sentinel


def test_get_unknown_client_returns_none():
    registry = ClientRegistry()
    assert registry.get("does-not-exist") is None


def test_remove_removes_client():
    registry = ClientRegistry()
    client_id = registry.add(object())
    assert registry.count() == 1
    registry.remove(client_id)
    assert registry.count() == 0
    assert registry.get(client_id) is None


def test_remove_unknown_client_is_a_no_op():
    registry = ClientRegistry()
    registry.remove("does-not-exist")
    assert registry.count() == 0


def test_all_clients_and_all_ids():
    registry = ClientRegistry()
    a, b = object(), object()
    id_a = registry.add(a)
    id_b = registry.add(b)
    assert set(registry.all_ids()) == {id_a, id_b}
    assert set(registry.all_clients()) == {a, b}


def test_contains():
    registry = ClientRegistry()
    client_id = registry.add(object())
    assert client_id in registry
    assert "missing" not in registry


def test_concurrent_add_is_thread_safe():
    registry = ClientRegistry()
    added_ids = []
    lock = threading.Lock()

    def worker():
        client_id = registry.add(object())
        with lock:
            added_ids.append(client_id)

    threads = [threading.Thread(target=worker) for _ in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert registry.count() == 50
    assert len(set(added_ids)) == 50
