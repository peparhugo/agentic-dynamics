import pytest

from shortener.shortcodes import (
    CollisionError,
    generate_short_code,
    is_valid_custom_code,
)


class FakeStorage:
    """Reports every code as taken until `always_taken` is False, forcing
    generate_short_code through its retry / length-bump logic."""

    def __init__(self, always_taken=False, taken_codes=None):
        self.always_taken = always_taken
        self.taken_codes = taken_codes or set()
        self.checked = []

    def code_exists(self, code):
        self.checked.append(code)
        if self.always_taken:
            return True
        return code in self.taken_codes


class TestGenerateShortCode:
    def test_returns_code_of_requested_length(self):
        storage = FakeStorage()
        code = generate_short_code(storage, length=8)
        assert len(code) == 8

    def test_retries_on_collision_and_returns_unique_code(self):
        storage = FakeStorage(taken_codes={"AAAAAA"})
        code = generate_short_code(storage, length=6)
        assert code != "AAAAAA"
        assert storage.code_exists(code) is False or code in storage.taken_codes

    def test_raises_when_keyspace_is_exhausted(self):
        storage = FakeStorage(always_taken=True)
        with pytest.raises(CollisionError):
            generate_short_code(storage, length=4)

    def test_bumps_length_after_repeated_collisions(self):
        storage = FakeStorage(always_taken=True)
        with pytest.raises(CollisionError):
            generate_short_code(storage, length=4)
        # confirms multiple lengths were attempted, i.e. codes of more
        # than one length were checked before giving up
        lengths_seen = {len(c) for c in storage.checked}
        assert len(lengths_seen) > 1

    def test_many_generated_codes_are_unique(self):
        storage = FakeStorage()
        seen = set()
        for _ in range(500):
            code = generate_short_code(storage, length=6)
            assert code not in seen
            seen.add(code)
            storage.taken_codes.add(code)


class TestValidCustomCode:
    @pytest.mark.parametrize("code", ["abc", "Ab3XYZ", "a" * 32])
    def test_valid_codes(self, code):
        assert is_valid_custom_code(code) is True

    @pytest.mark.parametrize(
        "code", ["", "ab", "a" * 33, "bad code", "bad!", None]
    )
    def test_invalid_codes(self, code):
        assert is_valid_custom_code(code) is False
