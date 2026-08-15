"""Tests for architectural entropy module."""

import tempfile
from pathlib import Path

import pytest

from instrument.entropy import (
    EntropyProfile,
    _classify_name,
    _dict_entropy,
    _histogram,
    _shannon_entropy,
    compute_entropy,
    entropy_delta,
    entropy_delta_detailed,
)


class TestShannonEntropy:
    def test_uniform_distribution(self):
        values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        h = _shannon_entropy(values, bins=5)
        assert h > 0.5  # Uniform should have high entropy

    def test_identical_values(self):
        values = [5, 5, 5, 5, 5]
        h = _shannon_entropy(values, bins=5)
        assert h == 0.0  # Identical should have zero entropy

    def test_empty(self):
        assert _shannon_entropy([], bins=5) == 0.0

    def test_single_value(self):
        assert _shannon_entropy([42], bins=5) == 0.0


class TestDictEntropy:
    def test_uniform(self):
        counts = {"a": 5, "b": 5, "c": 5, "d": 5}
        h = _dict_entropy(counts)
        assert h > 0.8

    def test_concentrated(self):
        counts = {"a": 100, "b": 1}
        h = _dict_entropy(counts)
        assert h < 0.5

    def test_empty(self):
        assert _dict_entropy({}) == 0.0


class TestHistogram:
    def test_basic(self):
        h = _histogram([1, 2, 3, 10, 11, 12])
        assert len(h) > 0


class TestClassifyName:
    def test_snake_case(self):
        assert _classify_name("get_user") == "snake_case"
        assert _classify_name("create_task_api") == "snake_case"

    def test_pascal_case(self):
        assert _classify_name("UserService") == "PascalCase"
        assert _classify_name("TaskRepository") == "PascalCase"

    def test_camel_case(self):
        assert _classify_name("getUser") == "camelCase"

    def test_private(self):
        assert _classify_name("_internal") == "private"
        assert _classify_name("__dunder") == "private"

    def test_empty(self):
        assert _classify_name("") == "empty"


class TestComputeEntropy:
    def test_small_codebase(self):
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            (dp / "app.py").write_text(
                "import os\n\n"
                "def short():\n    pass\n\n"
                "def also_short():\n    pass\n\n"
                "class Thing:\n    pass\n"
            )
            ep = compute_entropy(dp)
            assert isinstance(ep, EntropyProfile)
            assert ep.composite_entropy >= 0.0

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as d:
            ep = compute_entropy(Path(d))
            assert ep.composite_entropy == 0.0

    def test_to_dict(self):
        ep = EntropyProfile(
            function_length_entropy=0.5,
            module_size_entropy=0.3,
            composite_entropy=0.4,
        )
        d = ep.to_dict()
        assert d["function_length_entropy"] == 0.5
        assert "histograms" in d


class TestEntropyDelta:
    def test_positive_when_more_disorder(self):
        before = EntropyProfile(composite_entropy=0.3)
        after = EntropyProfile(composite_entropy=0.7)
        assert entropy_delta(before, after) == pytest.approx(0.4)

    def test_negative_when_less_disorder(self):
        before = EntropyProfile(composite_entropy=0.8)
        after = EntropyProfile(composite_entropy=0.5)
        assert entropy_delta(before, after) == pytest.approx(-0.3)

    def test_detailed_returns_all_dims(self):
        before = EntropyProfile()
        after = EntropyProfile()
        deltas = entropy_delta_detailed(before, after)
        assert "composite_delta" in deltas
        assert "function_length_delta" in deltas
        assert "naming_delta" in deltas
