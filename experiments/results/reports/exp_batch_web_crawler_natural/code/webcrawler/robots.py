"""RFC 9309 robots.txt parsing and caching.

A web-scale crawler *must* respect robots.txt both for politeness and legal
compliance.  This module implements the matching rules from RFC 9309:

* Rules are grouped by ``User-agent`` lines; a group matches a crawler when
  the group's product token is a case-insensitive substring of the crawler's
  ``User-Agent`` header, or when it is ``*`` (the wildcard group).
* ``Allow`` / ``Disallow`` patterns may contain ``*`` (wildcard) and a
  trailing ``$`` (end-of-path anchor).  When several rules match a URL, the
  rule with the *longest* matching pattern wins; ties resolve to ``Disallow``
  (safety first).
* ``Crawl-delay`` requests a minimum delay between requests to that host.
* ``Sitemap`` lines are surfaced so the crawler can seed its frontier.
"""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Iterable, List, Optional, Tuple
from urllib.parse import urlsplit


@dataclass
class _Rule:
    allow: bool
    pattern: str
    _regex: re.Pattern = field(repr=False)

    def match_len(self, path: str) -> int:
        m = self._regex.search(path)
        if m is None:
            return -1
        return len(m.group(0))


def _pattern_to_regex(pattern: str) -> re.Pattern:
    anchored = pattern.endswith("$")
    if anchored:
        pattern = pattern[:-1]
    parts = re.split(r"(\*)", pattern)
    out = "^"
    for part in parts:
        if part == "*":
            out += ".*"
        elif part:
            out += re.escape(part)
    out += "$" if anchored else ""
    return re.compile(out)


@dataclass
class _Group:
    user_agents: List[str]
    rules: List[_Rule] = field(default_factory=list)
    crawl_delay: Optional[float] = None


class RobotsTxt:
    """Parsed representation of a robots.txt file."""

    def __init__(self, text: str, fetch_time: Optional[float] = None):
        self.text = text
        self.fetch_time = fetch_time if fetch_time is not None else time.time()
        self.groups: List[_Group] = []
        self.sitemaps: List[str] = []
        self._parse(text)

    @property
    def is_empty(self) -> bool:
        return not self.groups and not self.sitemaps

    def _parse(self, text: str) -> None:
        current: Optional[_Group] = None
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                continue
            field, _, value = line.partition(":")
            field = field.strip().lower()
            value = value.strip()
            if field == "user-agent":
                current = _Group(user_agents=[value])
                self.groups.append(current)
            elif field in ("allow", "disallow"):
                if current is None:
                    current = _Group(user_agents=["*"])
                    self.groups.append(current)
                rule = _Rule(
                    allow=(field == "allow"),
                    pattern=value,
                    _regex=_pattern_to_regex(value),
                )
                current.rules.append(rule)
            elif field == "crawl-delay" and current is not None:
                try:
                    current.crawl_delay = float(value)
                except ValueError:
                    pass
            elif field == "sitemap":
                self.sitemaps.append(value)

    def _matching_groups(self, user_agent: str) -> List[_Group]:
        ua = user_agent.lower()
        matching = [
            g
            for g in self.groups
            if any(ua_token == "*" or ua_token.lower() in ua for ua_token in g.user_agents)
        ]
        return matching

    def _path(self, url: str) -> str:
        parts = urlsplit(url)
        path = parts.path or "/"
        return path

    def is_allowed(self, url: str, user_agent: str = "*") -> bool:
        """Return True if ``url`` may be fetched by ``user_agent``."""
        path = self._path(url)
        best: Optional[_Rule] = None
        best_len = -1
        for group in self._matching_groups(user_agent):
            for rule in group.rules:
                length = rule.match_len(path)
                if length > best_len:
                    best = rule
                    best_len = length
                elif length == best_len and length >= 0 and best is not None:
                    # Tie -> disallow wins (conservative).
                    if not rule.allow and best.allow:
                        best = rule
        if best is None:
            return True
        return best.allow

    def crawl_delay(self, user_agent: str = "*") -> Optional[float]:
        """Return the crawl-delay for the most specific matching group."""
        groups = self._matching_groups(user_agent)
        for group in reversed(groups):
            if group.crawl_delay is not None:
                return group.crawl_delay
        return None


class RobotsCache:
    """Caches robots.txt per host with a TTL, and enforces access rules.

    The ``fetcher`` callable is injected so the cache can be unit-tested
    without the network and reused by a real HTTP client in production.
    """

    def __init__(
        self,
        fetcher: Callable[[str], Tuple[int, Optional[str]]],
        user_agent: str = "*",
        ttl: float = 3600.0,
        default_allowed: bool = True,
    ):
        self._fetcher = fetcher
        self.user_agent = user_agent
        self.ttl = ttl
        self.default_allowed = default_allowed
        self._lock = threading.Lock()
        self._cache: dict = {}

    def _host(self, url: str) -> str:
        return urlsplit(url).netloc.lower()

    def _robots_url(self, url: str) -> str:
        parts = urlsplit(url)
        return f"{parts.scheme}://{parts.netloc}/robots.txt"

    def get(self, url: str) -> Optional[RobotsTxt]:
        """Return the cached robots.txt for the host, fetching if needed."""
        host = self._host(url)
        with self._lock:
            entry = self._cache.get(host)
            now = time.time()
            if entry is not None and (now - entry.fetch_time) < self.ttl:
                return entry
            # fall through and fetch outside lock
        try:
            status, text = self._fetcher(self._robots_url(url))
        except Exception:
            # Network failure -> be permissive (or restrictive per policy).
            return RobotsTxt("") if self.default_allowed else RobotsTxt(
                "User-agent: *\nDisallow: /\n"
            )
        if status == 404 or status >= 500:
            # 4xx (other than 404) or 5xx behave differently per RFC 9309;
            # a 404 means "no robots.txt" -> allow everything.
            if status == 404:
                robots = RobotsTxt("")
            else:
                robots = RobotsTxt("User-agent: *\nDisallow: /\n")
        else:
            robots = RobotsTxt(text or "")
        with self._lock:
            self._cache[host] = robots
        return robots

    def is_allowed(self, url: str) -> bool:
        robots = self.get(url)
        if robots is None:
            return self.default_allowed
        return robots.is_allowed(url, self.user_agent)

    def crawl_delay(self, url: str) -> Optional[float]:
        robots = self.get(url)
        if robots is None:
            return None
        return robots.crawl_delay(self.user_agent)

    def sitemaps(self, url: str) -> List[str]:
        robots = self.get(url)
        if robots is None:
            return []
        return list(robots.sitemaps)


__all__ = ["RobotsTxt", "RobotsCache"]
