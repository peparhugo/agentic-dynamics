import threading
from datetime import datetime, timezone


class URLStorage:
    def __init__(self):
        self._lock = threading.Lock()
        self._urls: dict[str, dict] = {}

    def save(self, code: str, url: str) -> None:
        with self._lock:
            self._urls[code] = {
                "url": url,
                "clicks": 0,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

    def get(self, code: str) -> str | None:
        with self._lock:
            entry = self._urls.get(code)
            if entry is None:
                return None
            entry["clicks"] += 1
            return entry["url"]

    def stats(self, code: str) -> dict | None:
        with self._lock:
            entry = self._urls.get(code)
            if entry is None:
                return None
            return {
                "short_code": code,
                "url": entry["url"],
                "clicks": entry["clicks"],
                "created_at": entry["created_at"],
            }

    def exists(self, code: str) -> bool:
        with self._lock:
            return code in self._urls
