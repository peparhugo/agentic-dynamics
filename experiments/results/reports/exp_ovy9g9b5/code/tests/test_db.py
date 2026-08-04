import sqlite3

import pytest


class TestUrls:
    def test_insert_and_get(self, db):
        row = db.insert_url("abc1234", "https://example.com")
        assert row["code"] == "abc1234"
        assert row["long_url"] == "https://example.com"
        assert row["created_at"]

        fetched = db.get_url_by_code("abc1234")
        assert fetched["id"] == row["id"]

    def test_get_missing_returns_none(self, db):
        assert db.get_url_by_code("nope") is None

    def test_duplicate_code_raises(self, db):
        db.insert_url("dup1234", "https://a.example")
        with pytest.raises(sqlite3.IntegrityError):
            db.insert_url("dup1234", "https://b.example")

    def test_code_exists(self, db):
        assert not db.code_exists("xyz")
        db.insert_url("xyz", "https://example.com")
        assert db.code_exists("xyz")

    def test_find_by_long_url(self, db):
        db.insert_url("first12", "https://example.com/x")
        found = db.find_by_long_url("https://example.com/x")
        assert found["code"] == "first12"
        assert db.find_by_long_url("https://missing.example") is None

    def test_delete(self, db):
        db.insert_url("gone123", "https://example.com")
        assert db.delete_url("gone123") is True
        assert db.get_url_by_code("gone123") is None
        assert db.delete_url("gone123") is False


class TestClicks:
    def test_record_and_count(self, db):
        row = db.insert_url("clicky1", "https://example.com")
        assert db.click_count(row["id"]) == 0
        db.record_click(row["id"], ip="1.2.3.4", user_agent="UA", referrer="https://ref.example")
        db.record_click(row["id"])
        assert db.click_count(row["id"]) == 2

    def test_stats_shape(self, db):
        row = db.insert_url("stats12", "https://example.com")
        db.record_click(row["id"], referrer="https://ref.example")
        db.record_click(row["id"])  # direct click
        stats = db.click_stats(row["id"])
        assert stats["total_clicks"] == 2
        assert stats["last_clicked_at"] is not None
        assert stats["referrers"]["https://ref.example"] == 1
        assert stats["referrers"]["(direct)"] == 1
        assert sum(stats["clicks_by_day"].values()) == 2

    def test_stats_empty(self, db):
        row = db.insert_url("quiet12", "https://example.com")
        stats = db.click_stats(row["id"])
        assert stats["total_clicks"] == 0
        assert stats["last_clicked_at"] is None
        assert stats["referrers"] == {}
        assert stats["clicks_by_day"] == {}

    def test_delete_cascades_clicks(self, db):
        row = db.insert_url("cascade", "https://example.com")
        db.record_click(row["id"])
        db.delete_url("cascade")
        assert db.click_count(row["id"]) == 0
