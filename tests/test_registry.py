from notification_server.registry import ClientRegistry


def test_add_and_get():
    registry = ClientRegistry()
    registry.add("a", "conn-a")
    assert registry.get("a") == "conn-a"


def test_count_reflects_number_of_clients():
    registry = ClientRegistry()
    assert registry.count() == 0
    registry.add("a", "conn-a")
    registry.add("b", "conn-b")
    assert registry.count() == 2


def test_remove_deletes_client():
    registry = ClientRegistry()
    registry.add("a", "conn-a")
    registry.remove("a")
    assert registry.count() == 0
    assert registry.get("a") is None


def test_remove_unknown_client_is_a_no_op():
    registry = ClientRegistry()
    registry.remove("does-not-exist")
    assert registry.count() == 0


def test_contains():
    registry = ClientRegistry()
    registry.add("a", "conn-a")
    assert "a" in registry
    assert "b" not in registry


def test_connections_and_ids():
    registry = ClientRegistry()
    registry.add("a", "conn-a")
    registry.add("b", "conn-b")
    assert set(registry.ids()) == {"a", "b"}
    assert set(registry.connections()) == {"conn-a", "conn-b"}


def test_concurrent_add_remove_is_thread_safe():
    import threading

    registry = ClientRegistry()

    def worker(n):
        client_id = f"client-{n}"
        registry.add(client_id, object())
        registry.remove(client_id)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert registry.count() == 0
