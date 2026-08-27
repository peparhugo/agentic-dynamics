"""De-duplication primitives for a web-scale crawler.

Three layers of dedup are needed at scale:

1. **Seen-URL Bloom filter** -- a space-efficient probabilistic set used by
   the frontier so we never re-enqueue a URL we have already visited.  With
   ~10 bits per URL a 1% false-positive rate holds ~10^11 URLs in ~125 GB.

2. **Exact content hashing** -- SHA-256 over the canonicalized page body
   collapses byte-identical pages (``?tracking=1`` style mirrors).

3. **SimHash near-duplicate detection** -- pages that differ in a few words
   (boilerplate, timestamps, ads) still hash to fingerprints within a small
   Hamming distance, letting us discard near-duplicate content.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Iterable, List, Set


def _hash64(data: bytes) -> int:
    return int.from_bytes(hashlib.blake2b(data, digest_size=8).digest(), "big")


class BloomFilter:
    """A classic Bloom filter using double hashing.

    ``add`` and ``__contains__`` accept either ``str`` or ``bytes``.
    """

    def __init__(self, capacity: int, error_rate: float = 0.01):
        self.capacity = max(1, capacity)
        self.error_rate = error_rate
        self.num_bits = self._optimal_bits(capacity, error_rate)
        self.num_hashes = self._optimal_hashes(self.num_bits, capacity)
        # Bit array stored as an array of 64-bit words for compactness.
        self._words = bytearray((self.num_bits + 7) // 8)

    @staticmethod
    def _optimal_bits(n: int, p: float) -> int:
        m = -n * math.log(p) / (math.log(2) ** 2)
        return max(64, int(math.ceil(m)))

    @staticmethod
    def _optimal_hashes(m: int, n: int) -> int:
        k = (m / n) * math.log(2)
        return max(1, int(round(k)))

    def _locations(self, item) -> Iterable[int]:
        if isinstance(item, str):
            item = item.encode("utf-8")
        h1 = _hash64(item)
        h2 = _hash64(item + b"\x00") or 1
        for i in range(self.num_hashes):
            yield (h1 + i * h2) % self.num_bits

    def add(self, item) -> None:
        for idx in self._locations(item):
            byte = idx // 8
            self._words[byte] |= 1 << (idx % 8)

    def __contains__(self, item) -> bool:
        for idx in self._locations(item):
            byte = idx // 8
            if not (self._words[byte] & (1 << (idx % 8))):
                return False
        return True

    def add_many(self, items: Iterable) -> None:
        for item in items:
            self.add(item)

    def __len__(self) -> int:
        return self.capacity


class SimHasher:
    """Locality-sensitive hashing producing 64-bit fingerprints.

    Tokenizes text into weighted shingles, hashes each shingle, and sums the
    signed bits.  Near-duplicate documents share small Hamming distance.
    """

    def __init__(self, shingle_size: int = 3, hash_bits: int = 64):
        self.shingle_size = shingle_size
        self.hash_bits = hash_bits

    def _shingles(self, text: str) -> Iterable[str]:
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        if len(tokens) <= self.shingle_size:
            return tokens
        return (" ".join(tokens[i : i + self.shingle_size]) for i in range(len(tokens) - self.shingle_size + 1))

    def fingerprint(self, text: str) -> int:
        counts: dict = {}
        for shingle in self._shingles(text):
            counts[shingle] = counts.get(shingle, 0) + 1
        vector = [0] * self.hash_bits
        for shingle, weight in counts.items():
            h = _hash64(shingle.encode("utf-8"))
            for bit in range(self.hash_bits):
                if (h >> bit) & 1:
                    vector[bit] += weight
                else:
                    vector[bit] -= weight
        fp = 0
        for bit, v in enumerate(vector):
            if v > 0:
                fp |= 1 << bit
        return fp

    @staticmethod
    def hamming_distance(a: int, b: int) -> int:
        return (a ^ b).bit_count()

    def is_near_duplicate(self, a: int, b: int, threshold: int = 3) -> bool:
        return self.hamming_distance(a, b) <= threshold


class ContentDeduper:
    """Exact + near-duplicate detection for page bodies."""

    def __init__(self, near_dup_threshold: int = 3):
        self.sim = SimHasher()
        self._exact: Set[str] = set()
        self._fingerprints: List[int] = []
        self.near_dup_threshold = near_dup_threshold

    def hash_content(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def is_duplicate(self, content: str) -> bool:
        """Return True if ``content`` is an exact or near duplicate of one
        we have already seen."""
        digest = self.hash_content(content)
        if digest in self._exact:
            return True
        fp = self.sim.fingerprint(content)
        for existing in self._fingerprints:
            if self.sim.is_near_duplicate(fp, existing, self.near_dup_threshold):
                return True
        self._exact.add(digest)
        self._fingerprints.append(fp)
        return False

    def add(self, content: str) -> None:
        self.is_duplicate(content)

    def __len__(self) -> int:
        return len(self._exact)


__all__ = ["BloomFilter", "SimHasher", "ContentDeduper"]
