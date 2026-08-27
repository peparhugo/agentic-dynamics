from __future__ import annotations

from collections import defaultdict

from .models import Tweet
from .tokenizer import tokenize


class SearchIndex:
    """In-memory inverted index with real-time indexing on write."""

    def __init__(self) -> None:
        self._postings: dict[str, list[int]] = defaultdict(list)

    def index(self, tweet: Tweet) -> None:
        for token in tokenize(tweet.text):
            self._postings[token].append(tweet.tweet_id)

    def search(self, query: str, tweets: dict[int, Tweet], limit: int) -> list[Tweet]:
        tokens = tokenize(query)
        if not tokens:
            return []
        result: set[int] | None = None
        for token in tokens:
            posting = self._postings.get(token)
            if posting is None:
                return []
            if result is None:
                result = set(posting)
            else:
                result &= set(posting)
            if not result:
                return []
        assert result is not None
        ordered = sorted(result, reverse=True)[:limit]
        return [tweets[i] for i in ordered]
