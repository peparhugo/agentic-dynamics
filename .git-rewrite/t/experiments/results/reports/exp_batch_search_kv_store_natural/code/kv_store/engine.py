"Storage engine per shard with ordered key-value storage and range query support.

Uses a sorted list of keys with bisect for O(log n) range queries.
Values are lists of document IDs (for search engine keyword indexing).
Supports hot key detection and dynamic replication hints.
"""

import bisect
import threading
import time
from collections import OrderedDict, defaultdict
from typing import Any, Dict, List, Optional, Tuple


class StorageEngine:
    def __init__(self, hot_key_threshold: int = 1000):
        self._data: Dict[str, List[Any]] = {}
        self._sorted_keys: List[str] = []
        self._lock = threading.RLock()
        self._hot_key_threshold = hot_key_threshold
        self._access_counts: Dict[str, int] = defaultdict(int)
        self._write_counts: Dict[str, int] = defaultdict(int)
        self._access_window_start = time.monotonic()
        self._window_duration = 60.0

    def put(self, key: str, value: Any):
        with self._lock:
            if key not in self._data:
                self._data[key] = []
                bisect.insort(self._sorted_keys, key)
            self._data[key].append(value)
            self._write_counts[key] += 1

    def get(self, key: str) -> Optional[List[Any]]:
        with self._lock:
            self._access_counts[key] += 1
            self._maybe_rotate_window()
            return self._data.get(key)

    def range_query(
        self, start: str, end: str, inclusive: bool = True
    ) -> List[Tuple[str, List[Any]]]:
        with self._lock:
            if inclusive:
                left = bisect.bisect_left(self._sorted_keys, start)
                right = bisect.bisect_right(self._sorted_keys, end)
            else:
                left = bisect.bisect_right(self._sorted_keys, start)
                right = bisect.bisect_left(self._sorted_keys, end)
            keys = self._sorted_keys[left:right]
            return [(k, self._data[k]) for k in keys]

    def prefix_scan(self, prefix: str) -> List[Tuple[str, List[Any]]]:
        with self._lock:
            left = bisect.bisect_left(self._sorted_keys, prefix)
            result = []
            for i in range(left, len(self._sorted_keys)):
                k = self._sorted_keys[i]
                if not k.startswith(prefix):
                    break
                result.append((k, self._data[k]))
            return result

    def batch_put(self, entries: List[Tuple[str, Any]]):
        with self._lock:
            for key, value in entries:
                if key not in self._data:
                    self._data[key] = []
                    bisect.insort(self._sorted_keys, key)
                self._data[key].append(value)
                self._write_counts[key] += 1

    def remove(self, key: str) -> bool:
        with self._lock:
            if key in self._data:
                del self._data[key]
                self._sorted_keys.remove(key)
                self._access_counts.pop(key, None)
                self._write_counts.pop(key, None)
                return True
            return False

    def contains(self, key: str) -> bool:
        with self._lock:
            return key in self._data

    def key_count(self) -> int:
        with self._lock:
            return len(self._sorted_keys)

    def total_values(self) -> int:
        with self._lock:
            return sum(len(v) for v in self._data.values())

    def get_all_keys(self) -> List[str]:
        with self._lock:
            return list(self._sorted_keys)

    def get_snapshot(self) -> Dict[str, List[Any]]:
        with self._lock:
            return {k: list(v) for k, v in self._data.items()}

    def get_hot_keys(self, top_n: int = 10) -> List[Tuple[str, int]]:
        with self._lock:
            self._maybe_rotate_window()
            sorted_keys = sorted(
                self._access_counts.items(), key=lambda x: x[1], reverse=True
            )
            return sorted_keys[:top_n]

    def get_hot_write_keys(self, top_n: int = 10) -> List[Tuple[str, int]]:
        with self._lock:
            self._maybe_rotate_window()
            sorted_keys = sorted(
                self._write_counts.items(), key=lambda x: x[1], reverse=True
            )
            return sorted_keys[:top_n]

    def _maybe_rotate_window(self):
        now = time.monotonic()
        if now - self._access_window_start > self._window_duration:
            self._access_counts.clear()
            self._write_counts.clear()
            self._access_window_start = now

    def __len__(self) -> int:
        return self.key_count()
