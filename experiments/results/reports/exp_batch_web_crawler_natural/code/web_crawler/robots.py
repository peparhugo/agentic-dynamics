import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse


@dataclass
class RobotsRule:
    path: str
    allowed: bool

    def matches(self, request_path: str) -> bool:
        if not request_path.startswith("/"):
            request_path = "/" + request_path
        if self.path == "/":
            return True
        if self.path.endswith("*") and request_path.startswith(self.path[:-1]):
            return True
        if request_path.startswith(self.path):
            return True
        if self.path.endswith("$") and request_path == self.path[:-1]:
            return True
        if self.path.endswith("$"):
            return False
        return request_path.startswith(self.path)

    def __len__(self):
        return len(self.path.rstrip("$*"))


@dataclass
class UserAgentBlock:
    user_agents: List[str]
    rules: List[RobotsRule] = field(default_factory=list)
    crawl_delay: Optional[float] = None

    def is_allowed(self, path: str) -> bool:
        best_match: Optional[RobotsRule] = None
        best_len = -1
        for rule in self.rules:
            if rule.matches(path):
                rule_len = len(rule)
                if rule_len > best_len:
                    best_len = rule_len
                    best_match = rule
        if best_match is None:
            return True
        return best_match.allowed


class RobotsParser:

    _GROUP_START = re.compile(r"^\s*[Uu][Ss][Ee][Rr]\s*-\s*[Aa][Gg][Ee][Nn][Tt]\s*:\s*(.*)$")
    _RULE_ALLOW = re.compile(r"^\s*[Aa][Ll][Ll][Oo][Ww]\s*:\s*(.*)$")
    _RULE_DISALLOW = re.compile(r"^\s*[Dd][Ii][Ss][Aa][Ll][Ll][Oo][Ww]\s*:\s*(.*)$")
    _CRAWL_DELAY = re.compile(r"^\s*[Cc][Rr][Aa][Ww][Ll]\s*-\s*[Dd][Ee][Ll][Aa][Yy]\s*:\s*(.*)$")
    _SITEMAP = re.compile(r"^\s*[Ss][Ii][Tt][Ee][Mm][Aa][Pp]\s*:\s*(.*)$")

    def __init__(self, robots_txt: str, fetch_time: Optional[float] = None):
        self.raw = robots_txt
        self.fetch_time = fetch_time
        self.blocks: List[UserAgentBlock] = []
        self.default_block: Optional[UserAgentBlock] = None
        self.sitemaps: List[str] = []
        self._parse(robots_txt)

    def _parse(self, text: str):
        text = text.lstrip("\ufeff")
        lines = text.splitlines()
        current_block: Optional[UserAgentBlock] = None

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            m = self._GROUP_START.match(line)
            if m:
                agents = [a.strip() for a in m.group(1).split(",")]
                current_block = UserAgentBlock(user_agents=agents)
                for agent in agents:
                    if agent.strip() == "*":
                        self.default_block = current_block
                self.blocks.append(current_block)
                continue

            if current_block is None:
                current_block = UserAgentBlock(user_agents=["*"])
                self.default_block = current_block
                self.blocks.append(current_block)

            m = self._RULE_DISALLOW.match(line)
            if m:
                path = m.group(1).strip()
                if path:
                    current_block.rules.append(RobotsRule(path=path, allowed=False))
                continue

            m = self._RULE_ALLOW.match(line)
            if m:
                path = m.group(1).strip()
                if path:
                    current_block.rules.append(RobotsRule(path=path, allowed=True))
                continue

            m = self._CRAWL_DELAY.match(line)
            if m:
                try:
                    current_block.crawl_delay = float(m.group(1).strip())
                except ValueError:
                    pass
                continue

            m = self._SITEMAP.match(line)
            if m:
                self.sitemaps.append(m.group(1).strip())

    def _find_block(self, user_agent: str) -> Optional[UserAgentBlock]:
        user_agent_lower = user_agent.lower()
        best_match = None
        longest_len = -1

        for block in self.blocks:
            for agent in block.user_agents:
                agent_lower = agent.lower()
                if agent == "*":
                    if best_match is None:
                        best_match = block
                    continue
                if agent_lower in user_agent_lower or user_agent_lower in agent_lower:
                    if len(agent_lower) > longest_len:
                        longest_len = len(agent_lower)
                        best_match = block

        return best_match or self.default_block

    def is_allowed(self, url: str, user_agent: str = "*") -> bool:
        try:
            parsed = urlparse(url)
            path = parsed.path or "/"
            if parsed.query:
                path += "?" + parsed.query
        except Exception:
            return True

        block = self._find_block(user_agent)
        if block is None:
            return True

        return block.is_allowed(path)

    def get_crawl_delay(self, user_agent: str = "*") -> Optional[float]:
        block = self._find_block(user_agent)
        if block:
            return block.crawl_delay
        return None

    def get_sitemaps(self) -> List[str]:
        return list(self.sitemaps)

    def __repr__(self):
        return f"RobotsParser(blocks={len(self.blocks)}, sitemaps={len(self.sitemaps)})"


class RobotsCache:
    def __init__(self, ttl: float = 3600):
        self._cache: Dict[str, Tuple[RobotsParser, float]] = {}
        self._ttl = ttl

    def get(self, domain: str) -> Optional[RobotsParser]:
        import time
        entry = self._cache.get(domain)
        if entry is None:
            return None
        parser, timestamp = entry
        if time.time() - timestamp > self._ttl:
            del self._cache[domain]
            return None
        return parser

    def set(self, domain: str, parser: RobotsParser):
        import time
        self._cache[domain] = (parser, time.time())

    def invalidate(self, domain: str):
        self._cache.pop(domain, None)

    def __len__(self):
        import time
        now = time.time()
        valid = sum(1 for _, ts in self._cache.values() if now - ts <= self._ttl)
        return valid
