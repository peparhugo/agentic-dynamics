from __future__ import annotations

import heapq
from typing import Optional

from twitter import models
from twitter.storage import InMemoryStore


class TimelineService:
    def __init__(
        self,
        store: InMemoryStore,
        celebrity_threshold: int = models.DEFAULT_CELEBRITY_THRESHOLD,
    ) -> None:
        self._store = store
        self._celebrity_threshold = celebrity_threshold

    def get_timeline(self, user_id: str, limit: int = 20) -> list[models.TimelineEntry]:
        push_entries = self._store.get_timeline(user_id)
        pull_entries = self._get_celebrity_tweets(user_id)
        merged = list(heapq.merge(
            sorted(push_entries, key=lambda e: e.created_at, reverse=True),
            sorted(pull_entries, key=lambda e: e.created_at, reverse=True),
            key=lambda e: e.created_at,
            reverse=True,
        ))
        return merged[:limit]

    def _get_celebrity_tweets(self, user_id: str) -> list[models.TimelineEntry]:
        entries: list[models.TimelineEntry] = []
        following = self._store.get_following(user_id)

        for followee_id in following:
            followee = self._store.get_user(followee_id)
            if followee is None:
                continue
            if not followee.is_celebrity(self._celebrity_threshold):
                continue

            tweets = self._store.get_tweets_by_user(followee_id)
            for tweet in tweets:
                entry = models.TimelineEntry(
                    user_id=user_id,
                    tweet_id=tweet.id,
                    author_id=tweet.user_id,
                    created_at=tweet.created_at,
                )
                entries.append(entry)

        return entries

    def get_user_tweets(self, user_id: str, limit: int = 20) -> list[models.Tweet]:
        tweets = self._store.get_tweets_by_user(user_id)
        tweets.sort(key=lambda t: t.created_at, reverse=True)
        return tweets[:limit]

    def get_tweet(self, tweet_id: str) -> Optional[models.Tweet]:
        return self._store.get_tweet(tweet_id)
