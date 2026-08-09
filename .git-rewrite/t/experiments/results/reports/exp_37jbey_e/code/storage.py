import threading
from datetime import datetime


class URLStorage:
    def __init__(self):
        self._urls = {}
        self._lock = threading.Lock()

    def save(self, short_code, url, created_at=None):
        with self._lock:
            if short_code in self._urls:
                return False
            self._urls[short_code] = {
                "url": url,
                "created_at": created_at or datetime.utcnow().isoformat(),
                "access_count": 0,
            }
            return True

    def get(self, short_code):
        with self._lock:
            entry = self._urls.get(short_code)
            if entry:
                entry["access_count"] += 1
            return entry

    def exists(self, short_code):
        with self._lock:
            return short_code in self._urls

    def stats(self, short_code):
        with self._lock:
            entry = self._urls.get(short_code)
            if entry is None:
                return None
            return {
                "url": entry["url"],
                "short_code": short_code,
                "created_at": entry["created_at"],
                "access_count": entry["access_count"],
            }

    def all_urls(self):
        with self._lock:
            return dict(self._urls)
