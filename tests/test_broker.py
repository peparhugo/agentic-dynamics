import asyncio

import fakeredis
import pytest

from notification_server.broker import RedisBroker


@pytest.fixture
def fake_server():
    return fakeredis.FakeServer()


def make_broker(fake_server, channel="test-channel"):
    client = fakeredis.FakeAsyncRedis(server=fake_server)
    return RedisBroker(client, channel=channel)


async def test_publish_delivers_to_started_worker(fake_server):
    broker = make_broker(fake_server)
    received = []
    ready = asyncio.Event()

    async def on_envelope(envelope):
        received.append(envelope)
        ready.set()

    await broker.start(on_envelope)
    try:
        await asyncio.sleep(0.05)  # let the subscribe land before publishing
        await broker.publish({"type": "broadcast", "payload": {"text": "hi"}})
        await asyncio.wait_for(ready.wait(), timeout=2)
    finally:
        await broker.stop()

    assert received == [{"type": "broadcast", "payload": {"text": "hi"}}]


async def test_multiple_brokers_share_same_fake_server(fake_server):
    """Simulates two server instances subscribed to the same Redis backbone."""
    broker_a = make_broker(fake_server)
    broker_b = make_broker(fake_server)

    received_a = []
    received_b = []

    async def on_a(envelope):
        received_a.append(envelope)

    async def on_b(envelope):
        received_b.append(envelope)

    await broker_a.start(on_a)
    await broker_b.start(on_b)
    try:
        await asyncio.sleep(0.05)
        await broker_a.publish({"payload": {"text": "cross-instance"}})
        await asyncio.sleep(0.2)
    finally:
        await broker_a.stop()
        await broker_b.stop()

    assert received_a == [{"payload": {"text": "cross-instance"}}]
    assert received_b == [{"payload": {"text": "cross-instance"}}]


async def test_malformed_envelope_is_dropped_not_raised(fake_server):
    client = fakeredis.FakeAsyncRedis(server=fake_server)
    broker = RedisBroker(client, channel="bad-channel")
    received = []

    async def on_envelope(envelope):
        received.append(envelope)

    await broker.start(on_envelope)
    try:
        await asyncio.sleep(0.05)
        await client.publish("bad-channel", "not json")
        await broker.publish({"ok": True})
        await asyncio.sleep(0.2)
    finally:
        await broker.stop()

    assert received == [{"ok": True}]


async def test_stop_is_idempotent(fake_server):
    broker = make_broker(fake_server)

    async def on_envelope(envelope):
        pass

    await broker.start(on_envelope)
    await broker.stop()
    await broker.stop()
