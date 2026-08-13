import fakeredis
import pytest

from notification_server.state import RedisClientState


@pytest.fixture
def state():
    client = fakeredis.FakeAsyncRedis(decode_responses=True)
    return RedisClientState(client)


async def test_add_and_is_connected(state):
    await state.add_client("c1")
    assert await state.is_connected("c1")
    assert not await state.is_connected("c2")


async def test_count_reflects_connected_clients(state):
    await state.add_client("c1")
    await state.add_client("c2")
    assert await state.count() == 2


async def test_remove_client(state):
    await state.add_client("c1")
    await state.remove_client("c1")
    assert not await state.is_connected("c1")
    assert await state.count() == 0


async def test_subscribe_and_channel_subscribers(state):
    await state.subscribe("alerts", "c1")
    await state.subscribe("alerts", "c2")
    assert await state.channel_subscribers("alerts") == ["c1", "c2"]


async def test_unsubscribe_removes_from_channel(state):
    await state.subscribe("alerts", "c1")
    await state.unsubscribe("alerts", "c1")
    assert await state.channel_subscribers("alerts") == []


async def test_empty_channel_removed_from_all_channels(state):
    await state.subscribe("alerts", "c1")
    await state.unsubscribe("alerts", "c1")
    assert await state.all_channels() == {}


async def test_all_channels_reports_counts(state):
    await state.subscribe("alerts", "c1")
    await state.subscribe("alerts", "c2")
    await state.subscribe("chat", "c1")
    assert await state.all_channels() == {"alerts": 2, "chat": 1}


async def test_unsubscribe_all_removes_client_from_every_channel(state):
    await state.subscribe("alerts", "c1")
    await state.subscribe("chat", "c1")
    await state.subscribe("chat", "c2")
    await state.unsubscribe_all("c1")
    assert await state.channel_subscribers("alerts") == []
    assert await state.channel_subscribers("chat") == ["c2"]


async def test_state_shared_across_instances_pointing_at_same_backend():
    fake_server = fakeredis.FakeServer()
    client_a = fakeredis.FakeAsyncRedis(server=fake_server, decode_responses=True)
    client_b = fakeredis.FakeAsyncRedis(server=fake_server, decode_responses=True)
    state_a = RedisClientState(client_a)
    state_b = RedisClientState(client_b)

    await state_a.add_client("c1")
    assert await state_b.is_connected("c1")
