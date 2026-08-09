from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import time as _time


@dataclass
class User:
    id: str
    screen_name: str
    created_at: float = field(default_factory=_time.time)
    follower_count: int = 0

    def is_celebrity(self, threshold: int = 10_000) -> bool:
        return self.follower_count >= threshold


@dataclass
class Tweet:
    id: str
    user_id: str
    content: str
    created_at: float = field(default_factory=_time.time)

    @property
    def hashtags(self) -> list[str]:
        return [token for token in _tokenize(self.content) if token.startswith("#")]


@dataclass
class Follow:
    follower_id: str
    followee_id: str
    created_at: float = field(default_factory=_time.time)

    def __hash__(self) -> int:
        return hash((self.follower_id, self.followee_id))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Follow):
            return False
        return (self.follower_id == other.follower_id
                and self.followee_id == other.followee_id)


@dataclass
class TimelineEntry:
    user_id: str
    tweet_id: str
    author_id: str
    created_at: float

    def __lt__(self, other: TimelineEntry) -> bool:
        return self.created_at < other.created_at


def _tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    buf: list[str] = []
    for ch in text.lower():
        if ch.isalnum() or ch in ("#", "_"):
            buf.append(ch)
        else:
            if buf:
                tokens.append("".join(buf))
                buf = []
    if buf:
        tokens.append("".join(buf))
    return tokens


DEFAULT_CELEBRITY_THRESHOLD = 10_000
