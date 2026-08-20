"""Tests for scripts/finalize_reviews.py — merging per-session review shards into
aggregate review_{story_id}.json files, plus (canonical-state round 2, plan step 12)
the FINOPS_KB_WRITE-gated inline registry emission that now follows each merge write.

New file — no test previously covered ``finalize_reviews.py`` at all (confirmed by
search at implementation time), so this file covers both the pre-existing merge logic
and the new emission call together, per the plan's guidance to extend in place rather
than leaving the base behavior untested while only covering the new addition.
"""

from __future__ import annotations

import json

from agentic_dynamics.knowledge import knowledge_stream as ks
from scripts import finalize_reviews as fr


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


# ── Pre-existing merge logic (previously untested) ───────────────


def test_finalize_story_merges_session_shards_and_story_review(tmp_path, monkeypatch):
    monkeypatch.setattr(fr, "REVIEWS_DIR", tmp_path)
    _write(tmp_path / "review_abc123_S1.json", {
        "commit_hash": "c1", "story_name": "task_manager_api", "session_number": 1,
        "better_or_worse": "better",
    })
    _write(tmp_path / "review_abc123_S2.json", {
        "commit_hash": "c2", "story_name": "task_manager_api", "session_number": 2,
        "better_or_worse": "worse",
    })
    _write(tmp_path / "review_abc123_story.json", {
        "story_name": "task_manager_api", "overall_coherence": 0.7,
    })

    written = fr._finalize_story("abc123")

    assert written is True
    merged = json.loads((tmp_path / "review_abc123.json").read_text())
    assert merged["story_id"] == "abc123"
    assert merged["story_name"] == "task_manager_api"
    assert [c["session_number"] for c in merged["commit_reviews"]] == [1, 2]
    assert merged["story_review"]["overall_coherence"] == 0.7


def test_finalize_story_returns_false_when_nothing_to_merge(tmp_path, monkeypatch):
    monkeypatch.setattr(fr, "REVIEWS_DIR", tmp_path)
    assert fr._finalize_story("no_such_story") is False
    assert not (tmp_path / "review_no_such_story.json").exists()


def test_finalize_story_tolerates_a_missing_story_review(tmp_path, monkeypatch):
    monkeypatch.setattr(fr, "REVIEWS_DIR", tmp_path)
    _write(tmp_path / "review_xyz_S1.json", {
        "commit_hash": "c1", "story_name": "s", "session_number": 1,
    })

    assert fr._finalize_story("xyz") is True
    merged = json.loads((tmp_path / "review_xyz.json").read_text())
    assert merged["story_review"] is None
    assert len(merged["commit_reviews"]) == 1


def test_finalize_story_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(fr, "REVIEWS_DIR", tmp_path)
    _write(tmp_path / "review_rep_S1.json", {
        "commit_hash": "c1", "story_name": "s", "session_number": 1,
    })

    first = fr._finalize_story("rep")
    second = fr._finalize_story("rep")
    assert first is True
    assert second is True  # re-running is safe (module docstring: "Idempotent")


# ── canonical-state round 2, plan step 12: registry emission ────


def test_finalize_story_skips_emission_when_kb_write_unset(tmp_path, monkeypatch):
    monkeypatch.setattr(fr, "REVIEWS_DIR", tmp_path)
    monkeypatch.delenv("FINOPS_KB_WRITE", raising=False)
    _write(tmp_path / "review_abc123_S1.json", {
        "commit_hash": "c1", "story_name": "s", "session_number": 1,
    })

    def _explode(*a, **kw):
        raise AssertionError("must not connect to the knowledge stream when KB_WRITE is unset")

    monkeypatch.setattr(ks, "connect", _explode)

    fr._finalize_story("abc123")
    # No assertion error raised above == no connection attempt was made.


def test_finalize_story_emits_registry_event_when_kb_write_enabled(tmp_path, monkeypatch):
    monkeypatch.setattr(fr, "REVIEWS_DIR", tmp_path)
    monkeypatch.setenv("FINOPS_KB_WRITE", "1")
    _write(tmp_path / "review_abc123_S1.json", {
        "commit_hash": "c1", "story_name": "s", "session_number": 1,
    })

    published = []
    monkeypatch.setattr(ks, "connect", lambda: object())
    monkeypatch.setattr(
        ks, "publish_event",
        lambda r, event, **kw: published.append((event, kw)) or "0-1",
    )

    fr._finalize_story("abc123")

    assert len(published) == 1
    event, kwargs = published[0]
    assert kwargs["source_type"] == "review"
    assert kwargs["authorized"] is True
    assert event.knowledge_id


def test_finalize_story_emission_deliberately_lets_a_downed_stream_raise(tmp_path, monkeypatch):
    # UNLIKE supervise.py's inline emit (a live, always-running loop), this call site
    # follows story.py:save_story_result's convention: no try/except once opted in, so
    # a downed knowledge stream is visible rather than silently dropped — see
    # story.py's save_story_result docstring for the full rationale.
    monkeypatch.setattr(fr, "REVIEWS_DIR", tmp_path)
    monkeypatch.setenv("FINOPS_KB_WRITE", "1")
    _write(tmp_path / "review_abc123_S1.json", {
        "commit_hash": "c1", "story_name": "s", "session_number": 1,
    })
    monkeypatch.setattr(
        ks, "connect", lambda: (_ for _ in ()).throw(RuntimeError("db2 down")),
    )

    import pytest

    with pytest.raises(RuntimeError):
        fr._finalize_story("abc123")

    # The merged file itself was still written before the (now-raised) emission step.
    assert (tmp_path / "review_abc123.json").exists()
