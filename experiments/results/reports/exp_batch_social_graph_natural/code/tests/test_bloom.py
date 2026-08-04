from __future__ import annotations

import pytest
from social_graph.bloom import BloomFilter


class TestBloomFilter:
    def test_add_and_contains(self) -> None:
        bf = BloomFilter(expected_elements=100, false_positive_rate=0.01)
        bf.add(42)
        assert bf.contains(42)
        assert 42 in bf

    def test_not_contains(self) -> None:
        bf = BloomFilter(expected_elements=100, false_positive_rate=0.01)
        assert not bf.contains(99)
        assert 99 not in bf

    def test_multiple_inserts(self) -> None:
        bf = BloomFilter(expected_elements=1000, false_positive_rate=0.01)
        items = list(range(200))
        for item in items:
            bf.add(item)
        for item in items:
            assert bf.contains(item)

    def test_false_positive_rate(self) -> None:
        bf = BloomFilter(expected_elements=1000, false_positive_rate=0.01)
        inserted = set(range(500))
        for item in inserted:
            bf.add(item)

        false_positives = 0
        tests = 1000
        for i in range(500, 500 + tests):
            if bf.contains(i):
                false_positives += 1

        rate = false_positives / tests
        assert rate < 0.1

    def test_clear(self) -> None:
        bf = BloomFilter(expected_elements=100, false_positive_rate=0.01)
        bf.add(1)
        bf.add(2)
        assert bf.contains(1)
        bf.clear()
        assert not bf.contains(1)
        assert not bf.contains(2)

    def test_size_and_hash_count(self) -> None:
        bf = BloomFilter(expected_elements=1000, false_positive_rate=0.01)
        assert bf.size > 0
        assert bf.hash_count > 0

    def test_large_expected(self) -> None:
        bf = BloomFilter(expected_elements=1_000_000, false_positive_rate=0.001)
        assert bf.size > 1_000_000
        assert bf.hash_count >= 1
        bf.add(123456)
        assert bf.contains(123456)

    def test_negatives_never_false_negative(self) -> None:
        bf = BloomFilter(expected_elements=100, false_positive_rate=0.01)
        items = list(range(50))
        for item in items:
            bf.add(item)
        for item in items:
            assert bf.contains(item)
