from __future__ import annotations

import uuid
from typing import Optional

from twitter import models
from twitter.storage import InMemoryStore
from twitter.fanout_service import FanoutService
from twitter.search_service import SearchService


class TweetService:
    def __init__(
        self,
        store: InMemoryStore,
        fanout: FanoutService,
        search: SearchService,
    ) -> None:
        self._store = store
        self._fanout = fanout
        self._search = search

    def post_tweet(self, user_id: str, content: str) -> models.Tweet:
        tweet = models.Tweet(
            id=_new_id(),
            user_id=user_id,
            content=content,
        )
        self._store.add_tweet(tweet)
        self._search.index_tweet(tweet)
        self._fanout.fanout_tweet(tweet)
        return tweet

    def get_tweet(self, tweet_id: str) -> Optional[models.Tweet]:
        return self._store.get_tweet(tweet_id)

    def get_tweets_by_user(self, user_id: str) -> list[models.Tweet]:
        return self._store.get_tweets_by_user(user_id)


def _new_id() -> str:
    return uuid.uuid4().hex[:16]
