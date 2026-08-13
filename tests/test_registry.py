import threading

from notification_server.registry import ClientRegistry, ChannelRegistry


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


def test_channel_subscribe_adds_subscriber():
    channels = ChannelRegistry()
    channels.subscribe("alerts", "client-1")
    assert channels.subscribers("alerts") == ["client-1"]
    assert channels.is_subscribed("alerts", "client-1")


def test_channel_subscribers_returns_sorted_list():
    channels = ChannelRegistry()
    channels.subscribe("alerts", "client-2")
    channels.subscribe("alerts", "client-1")
    assert channels.subscribers("alerts") == ["client-1", "client-2"]


def test_channel_subscribers_unknown_channel_is_empty():
    channels = ChannelRegistry()
    assert channels.subscribers("does-not-exist") == []


def test_channel_unsubscribe_removes_subscriber():
    channels = ChannelRegistry()
    channels.subscribe("alerts", "client-1")
    channels.unsubscribe("alerts", "client-1")
    assert channels.subscribers("alerts") == []
    assert not channels.is_subscribed("alerts", "client-1")


def test_channel_unsubscribe_unknown_channel_is_a_no_op():
    channels = ChannelRegistry()
    channels.unsubscribe("does-not-exist", "client-1")
    assert channels.all_channels() == {}


def test_channel_unsubscribe_all_removes_client_from_every_channel():
    channels = ChannelRegistry()
    channels.subscribe("alerts", "client-1")
    channels.subscribe("chat", "client-1")
    channels.subscribe("chat", "client-2")
    channels.unsubscribe_all("client-1")
    assert channels.subscribers("alerts") == []
    assert channels.subscribers("chat") == ["client-2"]


def test_client_can_be_subscribed_to_multiple_channels():
    channels = ChannelRegistry()
    channels.subscribe("alerts", "client-1")
    channels.subscribe("chat", "client-1")
    assert channels.is_subscribed("alerts", "client-1")
    assert channels.is_subscribed("chat", "client-1")


def test_all_channels_reports_subscriber_counts():
    channels = ChannelRegistry()
    channels.subscribe("alerts", "client-1")
    channels.subscribe("alerts", "client-2")
    channels.subscribe("chat", "client-1")
    assert channels.all_channels() == {"alerts": 2, "chat": 1}


def test_empty_channel_is_removed_from_all_channels():
    channels = ChannelRegistry()
    channels.subscribe("alerts", "client-1")
    channels.unsubscribe("alerts", "client-1")
    assert channels.all_channels() == {}


def test_channel_concurrent_subscribe_is_thread_safe():
    channels = ChannelRegistry()

    def worker(i):
        channels.subscribe("alerts", f"client-{i}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert channels.all_channels() == {"alerts": 50}
