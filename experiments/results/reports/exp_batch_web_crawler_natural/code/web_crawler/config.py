import os
import uuid
from dataclasses import dataclass, field
from typing import Set


@dataclass
class CrawlerConfig:
    user_agent: str = "WebCrawler/0.1 (research-indexer; bot@example.com)"
    max_concurrent_requests: int = 100
    max_requests_per_domain: int = 5
    default_crawl_delay: float = 1.0
    max_crawl_delay: float = 30.0
    request_timeout: float = 10.0
    bloom_filter_size: int = 1_000_000_000
    bloom_filter_hash_count: int = 7
    simhash_threshold: int = 3
    max_redirects: int = 5
    max_url_length: int = 2048
    frontier_max_size: int = 100_000_000
    recrawl_interval_base: float = 86400.0
    politeness_window: float = 1.0
    max_retries: int = 3
    retry_backoff: float = 2.0
    allowed_schemes: Set[str] = field(default_factory=lambda: {"http", "https"})
    respect_robots_txt: bool = True
    respect_meta_robots: bool = True
    respect_x_robots_tag: bool = True
    enable_distributed: bool = False
    redis_url: str = "redis://localhost:6379"
    worker_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    data_dir: str = "./crawler_data"
    max_depth: int = 10
    max_pages: int = 1_000_000_000
    content_max_size: int = 10 * 1024 * 1024
    user_agent_rotation: bool = False
    proxy_list: list = field(default_factory=list)

    def __post_init__(self):
        os.makedirs(self.data_dir, exist_ok=True)
