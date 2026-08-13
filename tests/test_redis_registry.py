import fakeredis
import pytest

from notification_server.redis_registry import RedisPresence


@pytest.fixture
def fake_server():
    return fakeredis.FakeServer()


def make_presence(fake_server, server_id="server-1"):
    client = fakeredis.FakeAsyncRedis(server=fake_server)
    return RedisPresence(client, server_id=server_id)


async def test_add_client_marks_as_connected(fake_server):
    presence = make_presence(fake_server)
    await presence.add_client("a")
    assert await presence.is_connected("a") is True
    assert await presence.count() == 1


async def test_remove_client_marks_as_disconnected(fake_server):
    presence = make_presence(fake_server)
    await presence.add_client("a")
    await presence.remove_client("a")
    assert await presence.is_connected("a") is False
    assert await presence.count() == 0


async def test_unknown_client_is_not_connected(fake_server):
    presence = make_presence(fake_server)
    assert await presence.is_connected("nope") is False


async def test_subscribe_and_channel_subscribers(fake_server):
    presence = make_presence(fake_server)
    await presence.add_client("a")
    await presence.add_client("b")
    await presence.subscribe("a", "alerts")
    await presence.subscribe("b", "alerts")
    assert await presence.channel_subscribers("alerts") == ["a", "b"]
    assert await presence.channels() == {"alerts": 2}


async def test_unsubscribe_removes_channel_when_empty(fake_server):
    presence = make_presence(fake_server)
    await presence.add_client("a")
    await presence.subscribe("a", "alerts")
    await presence.unsubscribe("a", "alerts")
    assert await presence.channel_subscribers("alerts") == []
    assert await presence.channels() == {}


async def test_remove_client_cleans_up_subscriptions(fake_server):
    presence = make_presence(fake_server)
    await presence.add_client("a")
    await presence.add_client("b")
    await presence.subscribe("a", "alerts")
    await presence.subscribe("b", "alerts")
    await presence.remove_client("a")
    assert await presence.channel_subscribers("alerts") == ["b"]


async def test_state_visible_across_separate_client_instances(fake_server):
    """Two separate RedisPresence objects backed by the same Redis server
    simulate two server processes sharing one Redis backbone; state set by
    one must be visible to the other, and survives if one process 'restarts'
    (i.e. constructs a brand new presence object against the same server)."""
    presence_1 = make_presence(fake_server, server_id="server-1")
    presence_2 = make_presence(fake_server, server_id="server-2")

    await presence_1.add_client("client-on-server-1")
    assert await presence_2.is_connected("client-on-server-1") is True

    # Simulate server-1 restarting: a fresh presence object, same backend.
    restarted_presence_1 = make_presence(fake_server, server_id="server-1")
    assert await restarted_presence_1.is_connected("client-on-server-1") is True
