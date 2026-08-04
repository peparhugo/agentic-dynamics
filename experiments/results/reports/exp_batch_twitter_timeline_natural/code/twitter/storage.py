from __future__ import annotations

import threading
from collections import defaultdict
from typing import Optional

from twitter.models import Follow, TimelineEntry, Tweet, User


class InMemoryStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.users: dict[str, User] = {}
        self.tweets: dict[str, Tweet] = {}
        self.follows: set[Follow] = set()
        self.followers: dict[str, set[str]] = defaultdict(set)
        self.following: dict[str, set[str]] = defaultdict(set)
        self.timelines: dict[str, list[TimelineEntry]] = defaultdict(list)
        self.tweets_by_user: dict[str, list[Tweet]] = defaultdict(list)
        self.inverted_index: dict[str, list[str]] = defaultdict(list)

    def add_user(self, user: User) -> None:
        with self._lock:
            self.users[user.id] = user

    def get_user(self, user_id: str) -> Optional[User]:
        with self._lock:
            return self.users.get(user_id)

    def add_tweet(self, tweet: Tweet) -> None:
        with self._lock:
            self.tweets[tweet.id] = tweet
            self.tweets_by_user[tweet.user_id].append(tweet)

    def get_tweet(self, tweet_id: str) -> Optional[Tweet]:
        with self._lock:
            return self.tweets.get(tweet_id)

    def add_follow(self, follow: Follow) -> None:
        with self._lock:
            if follow in self.follows:
                return
            self.follows.add(follow)
            self.followers[follow.followee_id].add(follow.follower_id)
            self.following[follow.follower_id].add(follow.followee_id)
            user = self.users.get(follow.followee_id)
            if user:
                user.follower_count += 1

    def remove_follow(self, follow: Follow) -> None:
        with self._lock:
            if follow not in self.follows:
                return
            self.follows.discard(follow)
            self.followers[follow.followee_id].discard(follow.follower_id)
            self.following[follow.follower_id].discard(follow.followee_id)
            user = self.users.get(follow.followee_id)
            if user and user.follower_count > 0:
                user.follower_count -= 1

    def get_followers(self, user_id: str) -> set[str]:
        with self._lock:
            return set(self.followers.get(user_id, set()))

    def get_following(self, user_id: str) -> set[str]:
        with self._lock:
            return set(self.following.get(user_id, set()))

    def push_timeline_entry(self, user_id: str, entry: TimelineEntry) -> None:
        with self._lock:
            self.timelines[user_id].append(entry)

    def get_timeline(self, user_id: str) -> list[TimelineEntry]:
        with self._lock:
            return list(self.timelines.get(user_id, []))

    def get_tweets_by_user(self, user_id: str) -> list[Tweet]:
        with self._lock:
            return list(self.tweets_by_user.get(user_id, []))

    def add_to_index(self, token: str, tweet_id: str) -> None:
        with self._lock:
            self.inverted_index[token].append(tweet_id)

    def get_index_entries(self, token: str) -> list[str]:
        with self._lock:
            return list(self.inverted_index.get(token, []))
