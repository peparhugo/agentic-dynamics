"""A distributed, polite, robots-respecting web crawler.

This package implements the core components required to index the entire
web:

* ``url_utils``    -- URL normalization / canonicalization (avoid duplicate
  crawl work and infinite loops on billions of pages).
* ``robots``       -- RFC 9309 robots.txt parsing and caching.
* ``dedup``        -- Bloom filters for the seen-URL set, exact hashing and
  SimHash near-duplicate detection for page content.
* ``rate_limiter`` -- token-bucket rate limiting + per-host politeness.
* ``frontier``     -- a polite, priority-aware URL frontier.
* ``fetcher``      -- HTTP fetching with conditional GET, retries and robots
  enforcement.
* ``parser``       -- HTML parsing and link extraction.
* ``scheduler``    -- adaptive recrawl scheduling for changing pages.
* ``distribution`` -- consistent-hash sharding of the URL space across
  worker machines.
* ``legal``        -- crawl policy: robots, opt-outs, noindex/nofollow.
* ``crawler``      -- the orchestrator tying everything together.
"""

from webcrawler.crawler import Crawler, CrawlStats
from webcrawler.dedup import BloomFilter, SimHasher, ContentDeduper
from webcrawler.distribution import HashRing, Distributor
from webcrawler.fetcher import Fetcher, FetchedPage, FetchError
from webcrawler.frontier import Frontier
from webcrawler.legal import CrawlPolicy
from webcrawler.parser import ParsedPage
from webcrawler.rate_limiter import TokenBucket, HostPoliteness
from webcrawler.robots import RobotsTxt, RobotsCache
from webcrawler.scheduler import RecrawlScheduler
from webcrawler.url_utils import normalize_url, canonicalize_url

__all__ = [
    "BloomFilter",
    "ContentDeduper",
    "CrawlPolicy",
    "Crawler",
    "CrawlStats",
    "Distributor",
    "Fetcher",
    "FetchedPage",
    "FetchError",
    "Frontier",
    "HashRing",
    "HostPoliteness",
    "ParsedPage",
    "RecrawlScheduler",
    "RobotsCache",
    "RobotsTxt",
    "SimHasher",
    "TokenBucket",
    "canonicalize_url",
    "normalize_url",
]

__version__ = "1.0.0"
