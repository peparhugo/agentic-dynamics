from notification_server.registry import ChannelRegistry, ClientRegistry


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


def test_channel_subscribe_adds_subscriber():
    channels = ChannelRegistry()
    channels.subscribe("alerts", "client-1")
    assert channels.subscribers("alerts") == {"client-1"}
    assert channels.channels() == {"alerts": {"client-1"}}


def test_channel_subscribe_supports_multiple_clients_and_channels():
    channels = ChannelRegistry()
    channels.subscribe("alerts", "client-1")
    channels.subscribe("alerts", "client-2")
    channels.subscribe("chat", "client-1")
    assert channels.subscribers("alerts") == {"client-1", "client-2"}
    assert channels.subscribers("chat") == {"client-1"}
    assert set(channels.channels().keys()) == {"alerts", "chat"}


def test_channel_unsubscribe_removes_subscriber():
    channels = ChannelRegistry()
    channels.subscribe("alerts", "client-1")
    channels.subscribe("alerts", "client-2")
    channels.unsubscribe("alerts", "client-1")
    assert channels.subscribers("alerts") == {"client-2"}


def test_channel_unsubscribe_drops_empty_channel():
    channels = ChannelRegistry()
    channels.subscribe("alerts", "client-1")
    channels.unsubscribe("alerts", "client-1")
    assert channels.channels() == {}
    assert channels.subscribers("alerts") == set()


def test_channel_unsubscribe_unknown_channel_is_noop():
    channels = ChannelRegistry()
    channels.unsubscribe("does-not-exist", "client-1")
    assert channels.channels() == {}


def test_channel_unsubscribe_all_removes_client_from_every_channel():
    channels = ChannelRegistry()
    channels.subscribe("alerts", "client-1")
    channels.subscribe("chat", "client-1")
    channels.subscribe("chat", "client-2")
    channels.unsubscribe_all("client-1")
    assert channels.channels() == {"chat": {"client-2"}}


def test_channel_subscribers_returns_independent_copy():
    channels = ChannelRegistry()
    channels.subscribe("alerts", "client-1")
    snapshot = channels.subscribers("alerts")
    snapshot.clear()
    assert channels.subscribers("alerts") == {"client-1"}
