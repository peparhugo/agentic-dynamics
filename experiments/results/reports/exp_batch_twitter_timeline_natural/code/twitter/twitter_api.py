from __future__ import annotations

from typing import Optional

from twitter import models
from twitter.storage import InMemoryStore
from twitter.user_service import UserService
from twitter.tweet_service import TweetService
from twitter.fanout_service import FanoutService
from twitter.timeline_service import TimelineService
from twitter.search_service import SearchService


class TwitterAPI:
    def __init__(
        self,
        celebrity_threshold: int = models.DEFAULT_CELEBRITY_THRESHOLD,
    ) -> None:
        self._store = InMemoryStore()
        self._fanout = FanoutService(self._store, celebrity_threshold)
        self._search = SearchService(self._store)
        self.users = UserService(self._store)
        self.tweets = TweetService(self._store, self._fanout, self._search)
        self.timeline = TimelineService(self._store, celebrity_threshold)
        self.search = self._search
        self._celebrity_threshold = celebrity_threshold

    def create_user(self, screen_name: str) -> models.User:
        return self.users.create_user(screen_name)

    def get_user(self, user_id: str) -> Optional[models.User]:
        return self.users.get_user(user_id)

    def follow(self, follower_id: str, followee_id: str) -> models.Follow:
        return self.users.follow(follower_id, followee_id)

    def unfollow(self, follower_id: str, followee_id: str) -> None:
        self.users.unfollow(follower_id, followee_id)

    def post_tweet(self, user_id: str, content: str) -> models.Tweet:
        return self.tweets.post_tweet(user_id, content)

    def get_tweet(self, tweet_id: str) -> Optional[models.Tweet]:
        return self.tweets.get_tweet(tweet_id)

    def get_timeline(self, user_id: str, limit: int = 20) -> list[models.TimelineEntry]:
        return self.timeline.get_timeline(user_id, limit)

    def get_user_tweets(self, user_id: str, limit: int = 20) -> list[models.Tweet]:
        return self.timeline.get_user_tweets(user_id, limit)

    def search_tweets(self, query: str, limit: int = 20) -> list[models.Tweet]:
        return self.search.search(query, limit)

    def get_followers(self, user_id: str) -> set[str]:
        return self.users.get_followers(user_id)

    def get_following(self, user_id: str) -> set[str]:
        return self.users.get_following(user_id)
