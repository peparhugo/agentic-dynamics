import pytest
from fakeredis import aioredis as fakeredis_aioredis

from notification_server.registry import ClientRegistry


class FakeWebSocket:
    def __init__(self):
        self.sent = []

    async def send(self, text: str) -> None:
        self.sent.append(text)


@pytest.fixture
def redis_client():
    return fakeredis_aioredis.FakeRedis()


async def test_register_mirrors_client_to_redis(redis_client):
    registry = ClientRegistry(redis_client=redis_client, server_id="server-a")
    client_id = await registry.register(FakeWebSocket())
    assert await redis_client.hget("notification_server:clients", client_id) == b"server-a"


async def test_unregister_removes_client_from_redis(redis_client):
    registry = ClientRegistry(redis_client=redis_client, server_id="server-a")
    client_id = await registry.register(FakeWebSocket())
    await registry.unregister(client_id)
    assert await redis_client.hexists("notification_server:clients", client_id) is False


async def test_exists_is_true_for_locally_registered_client(redis_client):
    registry = ClientRegistry(redis_client=redis_client)
    client_id = await registry.register(FakeWebSocket())
    assert await registry.exists(client_id) is True


async def test_exists_is_true_for_client_registered_on_another_instance(redis_client):
    registry_a = ClientRegistry(redis_client=redis_client, server_id="server-a")
    registry_b = ClientRegistry(redis_client=redis_client, server_id="server-b")
    client_id = await registry_a.register(FakeWebSocket())
    assert await registry_b.exists(client_id) is True
    assert await registry_b.get(client_id) is None  # not local to b


async def test_exists_is_false_for_unknown_client(redis_client):
    registry = ClientRegistry(redis_client=redis_client)
    assert await registry.exists("no-such-client") is False


async def test_global_count_reflects_clients_across_instances(redis_client):
    registry_a = ClientRegistry(redis_client=redis_client, server_id="server-a")
    registry_b = ClientRegistry(redis_client=redis_client, server_id="server-b")
    await registry_a.register(FakeWebSocket())
    await registry_b.register(FakeWebSocket())
    assert await registry_a.global_count() == 2
    assert await registry_b.global_count() == 2


async def test_subscribe_mirrors_channel_membership_to_redis(redis_client):
    registry = ClientRegistry(redis_client=redis_client)
    client_id = await registry.register(FakeWebSocket())
    await registry.subscribe(client_id, "alerts")
    members = await redis_client.smembers("notification_server:channel:alerts")
    assert members == {client_id.encode("utf-8")}
    assert await redis_client.sismember("notification_server:channels", "alerts")


async def test_unsubscribe_removes_channel_from_redis_when_empty(redis_client):
    registry = ClientRegistry(redis_client=redis_client)
    client_id = await registry.register(FakeWebSocket())
    await registry.subscribe(client_id, "alerts")
    await registry.unsubscribe(client_id, "alerts")
    assert await redis_client.scard("notification_server:channel:alerts") == 0
    assert not await redis_client.sismember("notification_server:channels", "alerts")


async def test_unregister_cleans_up_channel_membership_in_redis(redis_client):
    registry = ClientRegistry(redis_client=redis_client)
    client_id = await registry.register(FakeWebSocket())
    await registry.subscribe(client_id, "alerts")
    await registry.unregister(client_id)
    assert await redis_client.scard("notification_server:channel:alerts") == 0
    assert not await redis_client.sismember("notification_server:channels", "alerts")


async def test_global_channels_snapshot_spans_instances(redis_client):
    registry_a = ClientRegistry(redis_client=redis_client, server_id="server-a")
    registry_b = ClientRegistry(redis_client=redis_client, server_id="server-b")
    id_a = await registry_a.register(FakeWebSocket())
    id_b = await registry_b.register(FakeWebSocket())
    await registry_a.subscribe(id_a, "alerts")
    await registry_b.subscribe(id_b, "alerts")
    snapshot = await registry_a.global_channels_snapshot()
    assert snapshot == {"alerts": 2}


async def test_global_subscribers_spans_instances(redis_client):
    registry_a = ClientRegistry(redis_client=redis_client, server_id="server-a")
    registry_b = ClientRegistry(redis_client=redis_client, server_id="server-b")
    id_a = await registry_a.register(FakeWebSocket())
    id_b = await registry_b.register(FakeWebSocket())
    await registry_a.subscribe(id_a, "alerts")
    await registry_b.subscribe(id_b, "alerts")
    subscribers = await registry_a.global_subscribers("alerts")
    assert subscribers == sorted([id_a, id_b])


async def test_registry_without_redis_behaves_as_before():
    registry = ClientRegistry()
    client_id = await registry.register(FakeWebSocket())
    assert await registry.global_count() == await registry.count() == 1
    assert await registry.exists(client_id) is True
    assert await registry.exists("nope") is False
