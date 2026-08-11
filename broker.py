import os
import json
import uuid
import redis.asyncio as redis


REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")


class RedisBroker:
    def __init__(self, redis_url: str | None = None):
        self.redis_url = redis_url or REDIS_URL
        self._pub: redis.Redis | None = None
        self._sub: redis.Redis | None = None
        self._server_id = str(uuid.uuid4())
        self._pubsub = None

    @property
    def server_id(self) -> str:
        return self._server_id

    async def connect(self) -> None:
        if self._pubsub is not None:
            try:
                await self._pubsub.unsubscribe()
            except Exception:
                pass
            self._pubsub = None
        if self._pub is not None:
            await self._pub.close()
        if self._sub is not None:
            await self._sub.close()
        self._pub = redis.Redis.from_url(self.redis_url)
        self._sub = redis.Redis.from_url(self.redis_url)

    async def publish(self, channel: str, message: str) -> None:
        await self._pub.publish(channel, message)

    async def subscribe(self, channel: str) -> None:
        if self._pubsub is None:
            self._pubsub = self._sub.pubsub()
        await self._pubsub.subscribe(channel)

    async def listen(self, callback) -> None:
        async for msg in self._pubsub.listen():
            if msg["type"] == "message":
                ch = msg["channel"].decode()
                data = msg["data"].decode()
                await callback(ch, data)

    async def register_client(self, client_id: str, server_id: str) -> None:
        await self._pub.setex(f"client:{client_id}:server", 120, server_id)

    async def deregister_client(self, client_id: str) -> None:
        await self._pub.delete(f"client:{client_id}:server")
        await self._pub.delete(f"client:{client_id}:subscriptions")

    async def set_client_subscriptions(self, client_id: str, channels: list[str]) -> None:
        key = f"client:{client_id}:subscriptions"
        await self._pub.delete(key)
        if channels:
            await self._pub.sadd(key, *channels)
        await self._pub.expire(key, 120)

    async def close(self) -> None:
        if self._pubsub is not None:
            try:
                await self._pubsub.unsubscribe()
            except Exception:
                pass
            try:
                await self._pubsub.reset()
            except Exception:
                pass
            self._pubsub = None
        if self._pub is not None:
            await self._pub.close()
            self._pub = None
        if self._sub is not None:
            await self._sub.close()
            self._sub = None
