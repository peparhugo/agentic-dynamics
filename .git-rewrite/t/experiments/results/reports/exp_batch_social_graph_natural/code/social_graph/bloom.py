from __future__ import annotations

import hashlib
import math


class BloomFilter:
    def __init__(self, expected_elements: int = 10_000, false_positive_rate: float = 0.01) -> None:
        self._size = self._optimal_size(expected_elements, false_positive_rate)
        self._hash_count = self._optimal_hashes(self._size, expected_elements)
        self._bits = bytearray((self._size + 7) // 8)

    @staticmethod
    def _optimal_size(n: int, p: float) -> int:
        return max(1, int(-(n * math.log(p)) / (math.log(2) ** 2)))

    @staticmethod
    def _optimal_hashes(m: int, n: int) -> int:
        return max(1, int((m / n) * math.log(2)))

    def _hashes(self, item: int) -> list[int]:
        h = hashlib.sha256(str(item).encode()).digest()
        results = []
        for i in range(self._hash_count):
            v = (
                int.from_bytes(h[i * 2 : i * 2 + 2], "big")
                if i * 2 + 2 <= len(h)
                else (i * 2654435761 + item) % (2**32)
            )
            results.append(v % self._size)
        return results

    def _set_bit(self, idx: int) -> None:
        self._bits[idx // 8] |= (1 << (idx % 8))

    def _get_bit(self, idx: int) -> bool:
        return bool(self._bits[idx // 8] & (1 << (idx % 8)))

    def add(self, item: int) -> None:
        for idx in self._hashes(item):
            self._set_bit(idx)

    def contains(self, item: int) -> bool:
        return all(self._get_bit(idx) for idx in self._hashes(item))

    def __contains__(self, item: int) -> bool:
        return self.contains(item)

    @property
    def size(self) -> int:
        return self._size

    @property
    def hash_count(self) -> int:
        return self._hash_count

    def clear(self) -> None:
        for i in range(len(self._bits)):
            self._bits[i] = 0
