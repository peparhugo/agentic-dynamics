from __future__ import annotations

import threading
from collections import defaultdict, deque

from .models import Tweet, User
from .search import SearchIndex


class Twitter:
    """Hybrid fan-out timeline with real-time search.

    Regular users fan out on write: a new tweet is pushed into the home
    timeline cache of every follower. Users whose follower count reaches
    ``celebrity_threshold`` stop being pushed and are instead merged at read
    time from their own recent tweets (fan out on read), avoiding a
    multi-million-row write amplification per post.
    """

    def __init__(
        self,
        celebrity_threshold: int = 100_000,
        timeline_capacity: int = 1000,
        celebrity_recent: int = 100,
    ) -> None:
        self._celebrity_threshold = celebrity_threshold
        self._timeline_capacity = timeline_capacity
        self._celebrity_recent = celebrity_recent

        self._lock = threading.RLock()
        self._next_id = 1

        self._users: dict[int, User] = {}
        self._usernames: dict[str, int] = {}
        self._tweets: dict[int, Tweet] = {}
        self._user_tweets: dict[int, list[int]] = defaultdict(list)
        self._following: dict[int, set[int]] = defaultdict(set)
        self._followers: dict[int, set[int]] = defaultdict(set)
        self._home_timeline: dict[int, deque[int]] = defaultdict(deque)
        self._search = SearchIndex()

    # ---- user graph -----------------------------------------------------
    def create_user(self, username: str) -> User:
        with self._lock:
            if username in self._usernames:
                raise ValueError(f"username already taken: {username}")
            user = User(self._next_id, username)
            self._next_id += 1
            self._users[user.user_id] = user
            self._usernames[username] = user.user_id
            return user

    def follow(self, follower_id: int, followee_id: int) -> None:
        with self._lock:
            self._users[follower_id]
            self._users[followee_id]
            if follower_id == followee_id:
                raise ValueError("cannot follow self")
            self._following[follower_id].add(followee_id)
            self._followers[followee_id].add(follower_id)

    def unfollow(self, follower_id: int, followee_id: int) -> None:
        with self._lock:
            self._following[follower_id].discard(followee_id)
            self._followers[followee_id].discard(follower_id)

    def follower_count(self, user_id: int) -> int:
        with self._lock:
            return len(self._followers[user_id])

    # ---- timeline -------------------------------------------------------
    def post_tweet(self, user_id: int, text: str) -> Tweet:
        with self._lock:
            self._users[user_id]
            tweet = Tweet(self._next_id, user_id, text)
            self._next_id += 1
            self._tweets[tweet.tweet_id] = tweet
            self._user_tweets[user_id].append(tweet.tweet_id)

            self._push(self._home_timeline[user_id], tweet.tweet_id)

            if not self._is_celebrity(user_id):
                for follower_id in self._followers[user_id]:
                    self._push(self._home_timeline[follower_id], tweet.tweet_id)

            self._search.index(tweet)
            return tweet

    def get_timeline(self, user_id: int, limit: int = 20) -> list[Tweet]:
        with self._lock:
            self._users[user_id]
            ids: list[int] = list(self._home_timeline[user_id])
            for followee_id in self._following[user_id]:
                if self._is_celebrity(followee_id):
                    recent = self._user_tweets[followee_id][-self._celebrity_recent:]
                    ids.extend(recent)

            seen: set[int] = set()
            ordered: list[int] = []
            for tweet_id in sorted(ids, reverse=True):
                if tweet_id in seen:
                    continue
                seen.add(tweet_id)
                ordered.append(tweet_id)
                if len(ordered) >= limit:
                    break
            return [self._tweets[i] for i in ordered]

    # ---- search ---------------------------------------------------------
    def search(self, query: str, limit: int = 20) -> list[Tweet]:
        with self._lock:
            return self._search.search(query, self._tweets, limit)

    # ---- internals ------------------------------------------------------
    def _is_celebrity(self, user_id: int) -> bool:
        return len(self._followers[user_id]) >= self._celebrity_threshold

    def _push(self, timeline: deque[int], tweet_id: int) -> None:
        timeline.append(tweet_id)
        while len(timeline) > self._timeline_capacity:
            timeline.popleft()
