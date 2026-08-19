import sqlite3

import pytest

from app.db import SCHEMA
from app.repository import ClickRepository, LinkRepository


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    yield conn
    conn.close()


def test_get_or_create_is_idempotent_for_same_url(db):
    repo = LinkRepository(db)
    link1, created1 = repo.get_or_create("https://example.com/foo")
    link2, created2 = repo.get_or_create("https://example.com/foo")

    assert created1 is True
    assert created2 is False
    assert link1.code == link2.code


def test_get_or_create_different_urls_get_different_codes(db):
    repo = LinkRepository(db)
    link1, _ = repo.get_or_create("https://example.com/foo")
    link2, _ = repo.get_or_create("https://example.com/bar")

    assert link1.code != link2.code


def test_collision_is_resolved_by_advancing_salt(db, monkeypatch):
    import app.repository as repo_module

    def fake_candidates(url, length=7, max_attempts=1000):
        # Force the first candidate to always collide so the repository
        # must fall through to the second, distinct candidate.
        yield "SAMECODE", 0
        yield "SAMECODE" if url == "will-not-happen" else "SECONDCODE", 1

    monkeypatch.setattr(repo_module, "candidate_codes", fake_candidates)
    repo = LinkRepository(db)

    link1, created1 = repo.get_or_create("https://example.com/one")
    link2, created2 = repo.get_or_create("https://example.com/two")

    assert created1 is True and created2 is True
    assert link1.code == "SAMECODE"
    assert link2.code == "SECONDCODE"


def test_delete_removes_link(db):
    repo = LinkRepository(db)
    link, _ = repo.get_or_create("https://example.com/gone")
    assert repo.delete(link.code) is True
    assert repo.find_by_code(link.code) is None
    assert repo.delete(link.code) is False


def test_click_repository_records_and_counts(db):
    link_repo = LinkRepository(db)
    click_repo = ClickRepository(db)
    link, _ = link_repo.get_or_create("https://example.com/clicked")

    assert click_repo.count_for(link.code) == 0
    click_repo.record(link.code, referrer="https://ref.example", ip="1.2.3.4")
    click_repo.record(link.code, referrer=None, ip="5.6.7.8")

    assert click_repo.count_for(link.code) == 2
    events = click_repo.list_for(link.code)
    assert {e.ip for e in events} == {"1.2.3.4", "5.6.7.8"}
    assert click_repo.last_click(link.code) is not None
