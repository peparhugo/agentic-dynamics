"""The orchestrator: ties the frontier, fetcher, parser, deduper and
scheduler together into a complete crawl loop.

The crawl is event driven: pull the next due URL from the frontier, fetch it
(politely and robots-compliantly), parse it, dedup the content, extract
links, and schedule the next recrawl.  All state is held by the pluggable
components so the crawler can be swapped between an in-memory backend
(testing) and a distributed backend (production).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Iterable, List, Optional

from webcrawler.dedup import ContentDeduper
from webcrawler.fetcher import Fetcher, FetchedPage, FetchError
from webcrawler.frontier import Frontier
from webcrawler.legal import CrawlPolicy
from webcrawler.parser import parse_html
from webcrawler.scheduler import RecrawlScheduler
from webcrawler.url_utils import hostname_of, is_http_url, normalize_url


@dataclass
class CrawlStats:
    pages_crawled: int = 0
    pages_indexed: int = 0
    duplicates: int = 0
    blocked_by_robots: int = 0
    errors: int = 0
    not_modified: int = 0
    urls_enqueued: int = 0
    recrawls: int = 0
    noindex: int = 0


class Crawler:
    def __init__(
        self,
        fetcher: Fetcher,
        frontier: Optional[Frontier] = None,
        deduper: Optional[ContentDeduper] = None,
        scheduler: Optional[RecrawlScheduler] = None,
        policy: Optional[CrawlPolicy] = None,
        store: Optional[Callable[[FetchedPage, object], None]] = None,
        recrawl: bool = True,
        sleep: Callable[[float], None] = time.sleep,
        clock=time.time,
    ):
        self.fetcher = fetcher
        self.frontier = frontier or Frontier()
        self.deduper = deduper or ContentDeduper()
        self.scheduler = scheduler or RecrawlScheduler()
        self.policy = policy or CrawlPolicy(fetcher.robots_cache, fetcher.user_agent)
        self._store = store
        self.documents: dict = {}
        self.recrawl = recrawl
        self._sleep = sleep
        self._clock = clock
        self._recrawl_enqueued: set = set()
        self._crawled_once: set = set()

    def _persist(self, page: FetchedPage, parsed) -> None:
        key = normalize_url(page.final_url or page.url)
        doc = {
            "url": key,
            "title": parsed.title,
            "description": parsed.description,
            "content_hash": self.deduper.hash_content(page.content),
        }
        self.documents[key] = doc
        if self._store is not None:
            self._store(page, parsed)

    def _enqueue_due(self) -> int:
        if not self.recrawl:
            return 0
        added = 0
        for state in self.scheduler.due(self._clock()):
            if state.url in self._recrawl_enqueued:
                continue
            if self.frontier.requeue(state.url, priority=1.0):
                self._recrawl_enqueued.add(state.url)
                added += 1
        return added

    def _has_pending_recrawls(self) -> bool:
        return self.recrawl and bool(self.scheduler._states)

    def crawl(
        self,
        seed_urls: Iterable[str],
        max_pages: int = 100,
        max_seconds: Optional[float] = None,
    ) -> CrawlStats:
        stats = CrawlStats()
        for url in seed_urls:
            if self.frontier.add(url, priority=1.0):
                stats.urls_enqueued += 1
            self.scheduler.schedule(normalize_url(url))

        deadline = None if max_seconds is None else self._clock() + max_seconds

        while stats.pages_crawled < max_pages:
            if deadline is not None and self._clock() >= deadline:
                break

            self._enqueue_due()

            url = self.frontier.next()
            if url is None:
                if not self.frontier and not self._has_pending_recrawls():
                    break
                now = self._clock()
                ready = self.frontier.next_ready_time()
                next_due = self.scheduler.next_due_time(now) if self.recrawl else None
                targets = [t for t in (ready, next_due) if t is not None and t > now]
                if targets:
                    self._sleep(min(min(targets) - now, 0.1))
                else:
                    self._sleep(0.05)
                continue

            stats.pages_crawled += 1
            self._recrawl_enqueued.discard(url)
            self._process(url, stats)

        return stats

    def _process(self, url: str, stats: CrawlStats) -> None:
        host = hostname_of(url)
        state = self.scheduler.state(url)
        etag = state.etag if state else None
        last_modified = state.last_modified if state else None
        is_recrawl = url in self._crawled_once

        try:
            page = self.fetcher.fetch(url, etag=etag, last_modified=last_modified)
        except FetchError as exc:
            stats.errors += 1
            if exc.code == "robots":
                stats.blocked_by_robots += 1
            self.scheduler.record(url, changed=False)
            return
        finally:
            # Ensure the host is released even if an unexpected error escapes.
            self.frontier.complete(host)

        if is_recrawl:
            stats.recrawls += 1

        if page.status == 304:
            stats.not_modified += 1
            self._update_metadata(url, page)
            self.scheduler.record(url, changed=False)
            return

        if page.status != 200:
            stats.errors += 1
            self.scheduler.record(url, changed=False)
            return

        self._crawled_once.add(url)

        new_hash = self.deduper.hash_content(page.content)
        changed = state is not None and state.last_hash is not None and state.last_hash != new_hash
        if state is None or state.last_hash is None:
            changed = True

        if self.deduper.is_duplicate(page.content):
            stats.duplicates += 1
            self._update_metadata(url, page, new_hash)
            self.scheduler.record(url, changed=False)
            return

        parsed = parse_html(page.content, url=page.final_url or url)

        if not self.policy.may_index(parsed):
            stats.noindex += 1
            self._update_metadata(url, page, new_hash)
            self.scheduler.record(url, changed=changed)
            return

        stats.pages_indexed += 1
        self._persist(page, parsed)
        self._update_metadata(url, page, new_hash)
        self.scheduler.record(url, changed=changed)

        if self.policy.may_follow(parsed):
            for link in parsed.followable_links():
                nurl = normalize_url(link)
                if is_http_url(nurl) and self.frontier.add(nurl):
                    stats.urls_enqueued += 1

    def _update_metadata(self, url: str, page: FetchedPage, content_hash: Optional[str] = None) -> None:
        state = self.scheduler.state(url)
        if state is None:
            state = self.scheduler.schedule(url)
        state.etag = page.etag
        state.last_modified = page.last_modified
        if content_hash is not None:
            state.last_hash = content_hash


__all__ = ["Crawler", "CrawlStats"]
