import asyncio

import fakeredis
import pytest

from notification_server.broker import RedisBroker


@pytest.fixture
def fake_server():
    return fakeredis.FakeServer()


def make_broker(fake_server):
    client = fakeredis.FakeAsyncRedis(server=fake_server, decode_responses=True)
    return RedisBroker(client=client)


async def test_publish_delivers_to_started_worker(fake_server):
    broker = make_broker(fake_server)
    received = []
    event = asyncio.Event()

    async def handler(channel, data):
        received.append((channel, data))
        event.set()

    try:
        await broker.start("ns:*", handler)
        await broker.publish("ns:broadcast", "hello")
        await asyncio.wait_for(event.wait(), timeout=2)
    finally:
        await broker.stop()

    assert received == [("ns:broadcast", "hello")]


async def test_worker_only_receives_matching_pattern(fake_server):
    broker = make_broker(fake_server)
    received = []
    event = asyncio.Event()

    async def handler(channel, data):
        received.append((channel, data))
        event.set()

    try:
        await broker.start("ns:channel:*", handler)
        await broker.publish("other:namespace", "should not arrive")
        await broker.publish("ns:channel:alerts", "should arrive")
        await asyncio.wait_for(event.wait(), timeout=2)
    finally:
        await broker.stop()

    assert received == [("ns:channel:alerts", "should arrive")]


async def test_two_brokers_sharing_fake_server_communicate(fake_server):
    publisher = make_broker(fake_server)
    subscriber = make_broker(fake_server)
    received = []
    event = asyncio.Event()

    async def handler(channel, data):
        received.append((channel, data))
        event.set()

    try:
        await subscriber.start("ns:*", handler)
        await publisher.publish("ns:broadcast", "cross-instance hello")
        await asyncio.wait_for(event.wait(), timeout=2)
    finally:
        await publisher.stop()
        await subscriber.stop()

    assert received == [("ns:broadcast", "cross-instance hello")]


async def test_stop_is_idempotent_and_cancels_worker(fake_server):
    broker = make_broker(fake_server)

    async def handler(channel, data):
        pass

    await broker.start("ns:*", handler)
    await broker.stop()
    await broker.stop()  # should not raise
