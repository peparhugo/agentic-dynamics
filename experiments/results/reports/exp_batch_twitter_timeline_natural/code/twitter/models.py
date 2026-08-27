from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Tweet:
    tweet_id: int
    user_id: int
    text: str
    created_at: float = field(default_factory=time.time)


@dataclass
class User:
    user_id: int
    username: str
