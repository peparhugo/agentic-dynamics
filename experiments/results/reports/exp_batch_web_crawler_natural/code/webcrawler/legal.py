"""Legal compliance and crawl policy.

A crawler that indexes the entire web operates in a heavily regulated space.
This module centralizes the *policy* decisions so the rest of the crawler can
simply ask "may I crawl this?":

* **robots.txt** -- the primary, legally recognised opt-out mechanism.
* **meta robots ``noindex``/``nofollow``** -- per-page directives discovered
  during parsing.
* **explicit opt-out registry** -- hosts that asked (via email/ToS) not to be
  crawled, tracked here so we always honour their request.
* **``rel=nofollow``** -- honoured during link extraction.

The crawler must *also* identify itself (descriptive ``User-Agent`` with a
contact URL) and never circumvent access controls.  Those concerns are
enforced by :class:`Fetcher`.
"""

from __future__ import annotations

from typing import Iterable, Optional, Set


class CrawlPolicy:
    """Aggregates all compliance signals into a single allow/deny decision."""

    def __init__(
        self,
        robots_cache,
        user_agent: str = "*",
        opt_out_hosts: Optional[Iterable[str]] = None,
    ):
        self.robots_cache = robots_cache
        self.user_agent = user_agent
        self._opt_out: Set[str] = {h.lower() for h in (opt_out_hosts or [])}

    def opt_out(self, host: str) -> None:
        self._opt_out.add(host.lower())

    def is_opted_out(self, host: str) -> bool:
        return host.lower() in self._opt_out

    def can_crawl(self, url: str) -> bool:
        """Top-level legal gate used before fetching a URL."""
        from webcrawler.url_utils import hostname_of

        host = hostname_of(url)
        if self.is_opted_out(host):
            return False
        return self.robots_cache.is_allowed(url)

    def may_index(self, parsed_page) -> bool:
        """True unless the page asked not to be indexed (meta noindex)."""
        return not parsed_page.noindex

    def may_follow(self, parsed_page) -> bool:
        return not parsed_page.nofollow


__all__ = ["CrawlPolicy"]
