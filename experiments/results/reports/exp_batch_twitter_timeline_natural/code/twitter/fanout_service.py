from __future__ import annotations

from twitter import models
from twitter.storage import InMemoryStore


class FanoutService:
    def __init__(
        self,
        store: InMemoryStore,
        celebrity_threshold: int = models.DEFAULT_CELEBRITY_THRESHOLD,
    ) -> None:
        self._store = store
        self._celebrity_threshold = celebrity_threshold

    def fanout_tweet(self, tweet: models.Tweet) -> None:
        author = self._store.get_user(tweet.user_id)
        if author is None:
            return

        if author.is_celebrity(self._celebrity_threshold):
            self._celebrity_fanout(tweet, author)
        else:
            self._normal_fanout(tweet, author)

    def _normal_fanout(self, tweet: models.Tweet, author: models.User) -> None:
        followers = self._store.get_followers(author.id)
        for follower_id in followers:
            entry = models.TimelineEntry(
                user_id=follower_id,
                tweet_id=tweet.id,
                author_id=author.id,
                created_at=tweet.created_at,
            )
            self._store.push_timeline_entry(follower_id, entry)

    def _celebrity_fanout(self, tweet: models.Tweet, author: models.User) -> None:
        pass

    def get_celebrity_threshold(self) -> int:
        return self._celebrity_threshold
