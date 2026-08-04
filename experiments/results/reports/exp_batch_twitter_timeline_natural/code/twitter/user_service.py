from __future__ import annotations

import uuid
from typing import Optional

from twitter import models
from twitter.storage import InMemoryStore


class UserService:
    def __init__(self, store: InMemoryStore) -> None:
        self._store = store

    def create_user(self, screen_name: str) -> models.User:
        user = models.User(id=_new_id(), screen_name=screen_name)
        self._store.add_user(user)
        return user

    def get_user(self, user_id: str) -> Optional[models.User]:
        return self._store.get_user(user_id)

    def follow(self, follower_id: str, followee_id: str) -> models.Follow:
        follow = models.Follow(follower_id=follower_id, followee_id=followee_id)
        self._store.add_follow(follow)
        return follow

    def unfollow(self, follower_id: str, followee_id: str) -> None:
        follow = models.Follow(follower_id=follower_id, followee_id=followee_id)
        self._store.remove_follow(follow)

    def get_followers(self, user_id: str) -> set[str]:
        return self._store.get_followers(user_id)

    def get_following(self, user_id: str) -> set[str]:
        return self._store.get_following(user_id)


def _new_id() -> str:
    return uuid.uuid4().hex[:16]
