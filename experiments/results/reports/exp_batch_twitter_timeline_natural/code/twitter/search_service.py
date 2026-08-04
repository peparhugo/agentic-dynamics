from __future__ import annotations

from twitter import models
from twitter.storage import InMemoryStore


class SearchService:
    def __init__(self, store: InMemoryStore) -> None:
        self._store = store

    def index_tweet(self, tweet: models.Tweet) -> None:
        tokens = set(models._tokenize(tweet.content))
        for token in tokens:
            self._store.add_to_index(token, tweet.id)

    def search(self, query: str, limit: int = 20) -> list[models.Tweet]:
        query_tokens = set(models._tokenize(query))
        if not query_tokens:
            return []

        candidate_sets: list[set[str]] = []
        for token in query_tokens:
            entries = self._store.get_index_entries(token)
            candidate_sets.append(set(entries))

        if not candidate_sets:
            return []

        matching_ids = candidate_sets[0]
        for cs in candidate_sets[1:]:
            matching_ids = matching_ids & cs

        tweets: list[models.Tweet] = []
        for tweet_id in matching_ids:
            tweet = self._store.get_tweet(tweet_id)
            if tweet is not None:
                tweets.append(tweet)

        tweets.sort(key=lambda t: t.created_at, reverse=True)
        return tweets[:limit]

    def reindex_tweet(self, tweet: models.Tweet) -> None:
        pass
