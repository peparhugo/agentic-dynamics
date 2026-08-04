import time
import threading
from collections import OrderedDict


class TTLCache:
    def __init__(self, ttl: float = 60, max_size: int = 1000):
        self._cache = OrderedDict()
        self._ttl = ttl
        self._max_size = max_size
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            if key not in self._cache:
                return None
            value, expiry = self._cache[key]
            if time.time() > expiry:
                del self._cache[key]
                return None
            self._cache.move_to_end(key)
            return value

    def set(self, key, value, ttl=None):
        with self._lock:
            expiry = time.time() + (ttl if ttl is not None else self._ttl)
            if key in self._cache:
                del self._cache[key]
            self._cache[key] = (value, expiry)
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)

    def delete(self, key):
        with self._lock:
            self._cache.pop(key, None)

    def clear(self):
        with self._lock:
            self._cache.clear()

    def size(self):
        with self._lock:
            return len(self._cache)

    def keys(self):
        with self._lock:
            return list(self._cache.keys())
