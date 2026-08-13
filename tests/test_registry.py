import asyncio

import pytest

from notification_server.registry import ClientRegistry


class FakeWebSocket:
    def __init__(self, fail: bool = False):
        self.sent = []
        self.fail = fail

    async def send(self, text: str) -> None:
        if self.fail:
            raise ConnectionError("boom")
        self.sent.append(text)


async def test_register_assigns_unique_ids():
    registry = ClientRegistry()
    id1 = await registry.register(FakeWebSocket())
    id2 = await registry.register(FakeWebSocket())
    assert id1 != id2
    assert await registry.count() == 2


async def test_unregister_removes_client():
    registry = ClientRegistry()
    ws = FakeWebSocket()
    client_id = await registry.register(ws)
    await registry.unregister(client_id)
    assert await registry.count() == 0
    assert await registry.get(client_id) is None


async def test_unregister_unknown_id_is_noop():
    registry = ClientRegistry()
    await registry.unregister("does-not-exist")
    assert await registry.count() == 0


async def test_broadcast_sends_to_all_clients():
    registry = ClientRegistry()
    ws1, ws2 = FakeWebSocket(), FakeWebSocket()
    await registry.register(ws1)
    await registry.register(ws2)
    await registry.broadcast("hello")
    assert ws1.sent == ["hello"]
    assert ws2.sent == ["hello"]


async def test_broadcast_excludes_given_ids():
    registry = ClientRegistry()
    ws1, ws2 = FakeWebSocket(), FakeWebSocket()
    id1 = await registry.register(ws1)
    await registry.register(ws2)
    await registry.broadcast("hello", exclude=(id1,))
    assert ws1.sent == []
    assert ws2.sent == ["hello"]


async def test_broadcast_drops_dead_clients():
    registry = ClientRegistry()
    good = FakeWebSocket()
    bad = FakeWebSocket(fail=True)
    good_id = await registry.register(good)
    bad_id = await registry.register(bad)
    dead = await registry.broadcast("hello")
    assert dead == [bad_id]
    assert await registry.count() == 1
    assert await registry.get(good_id) is good
    assert await registry.get(bad_id) is None


async def test_subscribe_adds_client_to_channel():
    registry = ClientRegistry()
    ws = FakeWebSocket()
    client_id = await registry.register(ws)
    assert await registry.subscribe(client_id, "alerts") is True
    assert await registry.subscribers("alerts") == [client_id]
    assert await registry.channels_snapshot() == {"alerts": 1}


async def test_subscribe_unknown_client_returns_false():
    registry = ClientRegistry()
    assert await registry.subscribe("no-such-client", "alerts") is False
    assert await registry.channels_snapshot() == {}


async def test_client_can_subscribe_to_multiple_channels():
    registry = ClientRegistry()
    client_id = await registry.register(FakeWebSocket())
    await registry.subscribe(client_id, "alerts")
    await registry.subscribe(client_id, "chat")
    assert await registry.channels_snapshot() == {"alerts": 1, "chat": 1}


async def test_unsubscribe_removes_client_from_channel():
    registry = ClientRegistry()
    client_id = await registry.register(FakeWebSocket())
    await registry.subscribe(client_id, "alerts")
    await registry.unsubscribe(client_id, "alerts")
    assert await registry.subscribers("alerts") == []
    assert await registry.channels_snapshot() == {}


async def test_unsubscribe_unknown_channel_is_noop():
    registry = ClientRegistry()
    client_id = await registry.register(FakeWebSocket())
    await registry.unsubscribe(client_id, "does-not-exist")
    assert await registry.channels_snapshot() == {}


async def test_unregister_removes_client_from_all_channels():
    registry = ClientRegistry()
    ws1, ws2 = FakeWebSocket(), FakeWebSocket()
    id1 = await registry.register(ws1)
    id2 = await registry.register(ws2)
    await registry.subscribe(id1, "alerts")
    await registry.subscribe(id2, "alerts")
    await registry.subscribe(id1, "chat")
    await registry.unregister(id1)
    assert await registry.subscribers("alerts") == [id2]
    assert await registry.channels_snapshot() == {"alerts": 1}


async def test_broadcast_channel_sends_only_to_subscribers():
    registry = ClientRegistry()
    ws1, ws2, ws3 = FakeWebSocket(), FakeWebSocket(), FakeWebSocket()
    id1 = await registry.register(ws1)
    await registry.register(ws2)
    id3 = await registry.register(ws3)
    await registry.subscribe(id1, "alerts")
    await registry.subscribe(id3, "alerts")
    await registry.broadcast_channel("hello", "alerts")
    assert ws1.sent == ["hello"]
    assert ws2.sent == []
    assert ws3.sent == ["hello"]


async def test_broadcast_channel_excludes_given_ids():
    registry = ClientRegistry()
    ws1, ws2 = FakeWebSocket(), FakeWebSocket()
    id1 = await registry.register(ws1)
    id2 = await registry.register(ws2)
    await registry.subscribe(id1, "alerts")
    await registry.subscribe(id2, "alerts")
    await registry.broadcast_channel("hello", "alerts", exclude=(id1,))
    assert ws1.sent == []
    assert ws2.sent == ["hello"]


async def test_broadcast_channel_unknown_channel_is_noop():
    registry = ClientRegistry()
    ws = FakeWebSocket()
    await registry.register(ws)
    dead = await registry.broadcast_channel("hello", "does-not-exist")
    assert dead == []
    assert ws.sent == []


async def test_broadcast_channel_drops_dead_clients():
    registry = ClientRegistry()
    good = FakeWebSocket()
    bad = FakeWebSocket(fail=True)
    good_id = await registry.register(good)
    bad_id = await registry.register(bad)
    await registry.subscribe(good_id, "alerts")
    await registry.subscribe(bad_id, "alerts")
    dead = await registry.broadcast_channel("hello", "alerts")
    assert dead == [bad_id]
    assert await registry.count() == 1
    assert await registry.subscribers("alerts") == [good_id]


async def test_concurrent_register_unregister_is_consistent():
    registry = ClientRegistry()

    async def churn():
        ws = FakeWebSocket()
        cid = await registry.register(ws)
        await asyncio.sleep(0)
        await registry.unregister(cid)

    await asyncio.gather(*(churn() for _ in range(50)))
    assert await registry.count() == 0
