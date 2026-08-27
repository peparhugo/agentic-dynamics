"""HTTP fetching with politeness, conditional GET and retries.

The fetcher is the only component that talks to the network.  It is
responsible for:

* enforcing robots.txt and per-host crawl delays before every request,
* sending a descriptive ``User-Agent`` (legal compliance),
* using conditional requests (``If-None-Match`` / ``If-Modified-Since``) so
  unchanged pages are detected cheaply (HTTP 304) during recrawls,
* handling redirects (with a cap), and backing off on 429 / 5xx,
* returning structured :class:`FetchedPage` results.

The actual HTTP transport is injected via ``http_get`` so the fetcher is
unit-testable offline; the default implementation uses ``requests``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

from webcrawler.rate_limiter import HostPoliteness
from webcrawler.robots import RobotsCache
from webcrawler.url_utils import hostname_of


@dataclass
class HttpResponse:
    url: str
    status: int
    headers: Dict[str, str]
    body: bytes = b""


@dataclass
class FetchedPage:
    url: str
    final_url: str
    status: int
    content: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    from_cache: bool = False

    @property
    def is_html(self) -> bool:
        ctype = self.headers.get("content-type", "").lower()
        return "html" in ctype or ctype == ""

    @property
    def content_type(self) -> str:
        return self.headers.get("content-type", "")


class FetchError(Exception):
    def __init__(self, message: str, code: str = "error", cause: Optional[Exception] = None):
        super().__init__(message)
        self.code = code
        self.cause = cause


def _default_http_get(url: str, headers: Dict[str, str], timeout: float) -> HttpResponse:
    import requests

    resp = requests.get(
        url, headers=headers, timeout=timeout, allow_redirects=True
    )
    return HttpResponse(
        url=resp.url, status=resp.status_code, headers=dict(resp.headers), body=resp.content
    )


class Fetcher:
    def __init__(
        self,
        robots_cache: RobotsCache,
        user_agent: str = "WebCrawler/1.0 (respects robots.txt)",
        default_delay: float = 1.0,
        timeout: float = 10.0,
        max_retries: int = 3,
        backoff: float = 2.0,
        base_delay: float = 0.5,
        http_get: Optional[Callable[[str, Dict[str, str], float], HttpResponse]] = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.robots_cache = robots_cache
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff = backoff
        self.base_delay = base_delay
        self.http_get = http_get or _default_http_get
        self._sleep = sleep
        self.politeness = HostPoliteness(default_delay=default_delay)

    def _throttle(self, host: str) -> None:
        wait = self.politeness.acquire(host)
        if wait > 0:
            self._sleep(wait)

    @staticmethod
    def _parse_retry_after(headers: Dict[str, str]) -> Optional[float]:
        value = headers.get("retry-after")
        if value is None:
            return None
        try:
            return float(value)
        except ValueError:
            return None

    def fetch(
        self, url: str, etag: Optional[str] = None, last_modified: Optional[str] = None
    ) -> FetchedPage:
        host = hostname_of(url)

        if not self.robots_cache.is_allowed(url):
            raise FetchError(f"blocked by robots.txt: {url}", code="robots")

        self._throttle(host)

        headers = {"User-Agent": self.user_agent}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified

        delay = self.base_delay
        last_err: Optional[Exception] = None
        for _ in range(self.max_retries + 1):
            try:
                resp = self.http_get(url, headers, self.timeout)
            except Exception as exc:  # network / DNS / TLS failure
                last_err = exc
            else:
                status = resp.status
                if status == 429:
                    ra = self._parse_retry_after(resp.headers)
                    self._sleep(ra if ra is not None else delay)
                    delay *= self.backoff
                    continue
                if 500 <= status < 600:
                    self._sleep(delay)
                    delay *= self.backoff
                    continue
                return self._to_page(url, resp)
            self._sleep(delay)
            delay *= self.backoff

        raise FetchError(
            f"failed to fetch {url} after {self.max_retries + 1} attempts",
            code="network",
            cause=last_err,
        )

    def _to_page(self, requested_url: str, resp: HttpResponse) -> FetchedPage:
        headers = {k.lower(): v for k, v in resp.headers.items()}
        from_cache = resp.status == 304
        content = "" if from_cache else resp.body.decode("utf-8", errors="replace")
        return FetchedPage(
            url=requested_url,
            final_url=resp.url,
            status=resp.status,
            content=content,
            headers=headers,
            etag=headers.get("etag"),
            last_modified=headers.get("last-modified"),
            from_cache=from_cache,
        )


__all__ = ["Fetcher", "FetchedPage", "FetchError", "HttpResponse"]
