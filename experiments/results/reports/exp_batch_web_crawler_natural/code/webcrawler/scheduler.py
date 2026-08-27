"""Adaptive recrawl scheduling.

The web changes constantly; a crawler that fetches a page once is useless for
an index.  The scheduler decides *when* to revisit each URL.  The policy is
adaptive:

* If a page changed since the last fetch, it is likely to change again soon,
  so the revisit interval is shortened.
* If it did not change, the interval is grown exponentially (backoff) so we
  stop wasting bandwidth on static pages, up to a cap.
* The interval is also bounded below by a minimum so we never revisit faster
  than politeness/legal limits allow.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class RecrawlState:
    url: str
    interval: float
    next_crawl: float
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    last_hash: Optional[str] = None

    def due(self, now: Optional[float] = None) -> bool:
        now = now if now is not None else time.time()
        return now >= self.next_crawl


class RecrawlScheduler:
    """Assigns revisit times using additive-increase / multiplicative-decrease
    on the per-URL interval, keyed on whether content actually changed."""

    def __init__(
        self,
        min_interval: float = 300.0,
        max_interval: float = 604800.0,
        growth: float = 2.0,
        shrink: float = 0.5,
        clock=time.time,
    ):
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.growth = growth
        self.shrink = shrink
        self._clock = clock
        self._states: Dict[str, RecrawlState] = {}

    def schedule(self, url: str, initial_interval: Optional[float] = None) -> RecrawlState:
        interval = initial_interval if initial_interval is not None else self.min_interval
        state = RecrawlState(
            url=url,
            interval=interval,
            next_crawl=self._clock() + interval,
        )
        self._states[url] = state
        return state

    def record(self, url: str, changed: bool, interval: Optional[float] = None) -> float:
        """Record the result of a fetch and return the next interval."""
        state = self._states.get(url)
        if state is None:
            state = self.schedule(url, interval)
            if interval is not None:
                state.interval = interval
        else:
            if interval is not None:
                state.interval = interval
            elif changed:
                state.interval = max(self.min_interval, state.interval * self.shrink)
            else:
                state.interval = min(self.max_interval, state.interval * self.growth)
        state.next_crawl = self._clock() + state.interval
        return state.interval

    def next_interval(self, current: float, changed: bool) -> float:
        """Pure helper used by ``record`` (and tests)."""
        if changed:
            return max(self.min_interval, current * self.shrink)
        return min(self.max_interval, current * self.growth)

    def due(self, now: Optional[float] = None) -> list:
        now = now if now is not None else self._clock()
        return [s for s in self._states.values() if s.due(now)]

    def next_due_time(self, now: Optional[float] = None) -> Optional[float]:
        """Earliest future recrawl time across all tracked URLs."""
        now = now if now is not None else self._clock()
        future = [s.next_crawl for s in self._states.values() if s.next_crawl > now]
        return min(future) if future else None

    def state(self, url: str) -> Optional[RecrawlState]:
        return self._states.get(url)


__all__ = ["RecrawlScheduler", "RecrawlState"]
