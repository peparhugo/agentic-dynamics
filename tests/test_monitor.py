"""Tests for monitor.py — the three-stage pipeline view (--json + human output).

The post-hoc stages are surfaced alongside the story stage: analyze from
(analysis_jobs/analysis_status), and review from the review FILES (the trigger →
review_all cut-over retired the legacy review_jobs/review_status Redis state from the
display — see pipeline_status.review_stage_summary). These tests lock down that the
legacy flat fields remain, the ``stages`` block is correct, and ``--clear`` drops every
stage's keys.
"""

import json
import sys

from agentic_dynamics.control import pipeline_status
from scripts import monitor


class StubRedis:
    """Implement only the Redis reads ``monitor.get_status`` performs."""

    def __init__(self, *, llen=None, hgetall=None):
        self._llen = llen or {}
        self._hgetall = hgetall or {}

    def llen(self, key):
        return self._llen.get(key, 0)

    def hgetall(self, key):
        return self._hgetall.get(key, {})


def _redis(
    story_statuses,
    analysis_statuses,
    review_statuses,
    *,
    story_jobs=0,
    analysis_jobs=0,
    review_jobs=0,
    story_results=None,
) -> StubRedis:
    """Build a stub Redis seeded with the three queue/status pairs."""
    return StubRedis(
        llen={
            "story_jobs": story_jobs,
            "analysis_jobs": analysis_jobs,
            "review_jobs": review_jobs,
        },
        hgetall={
            "story_status": story_statuses,
            "story_results": story_results or {},
            "analysis_status": analysis_statuses,
            "review_status": review_statuses,
        },
    )


def _review_fixture(tmp_path, monkeypatch):
    """Seed a review-files fixture and point the file-derived review stage at it."""
    reviews = tmp_path / "reviews"
    results = tmp_path / "stories"
    reviews.mkdir()
    results.mkdir()
    complete = {"story_review": {"ok": True}, "commit_reviews": [{"session_number": 1}]}
    incomplete = {"story_review": None, "commit_reviews": []}
    (results / "s1_abc123456789.json").write_text("{}")
    (results / "s1_def456789012.json").write_text("{}")
    (results / "s1_111222333444.json").write_text("{}")
    (reviews / "review_abc123456789.json").write_text(json.dumps(complete))
    (reviews / "review_def456789012.json").write_text(json.dumps(incomplete))
    (reviews / "review_111222333444.error").write_text(json.dumps({"error": "no session commits"}))
    monkeypatch.setattr(pipeline_status, "REVIEWS_DIR", reviews)
    monkeypatch.setattr(pipeline_status, "RESULTS_DIR", results)
    return reviews, results


def test_get_status_exposes_three_stages_and_legacy_fields():
    """The ``stages`` block is additive; legacy flat fields are unchanged."""
    r = _redis(
        story_statuses={"a": "done", "b": "running"},
        analysis_statuses={"a": "done"},
        review_statuses={"a_S1": "retry_1"},
        story_jobs=2,
        analysis_jobs=1,
        story_results={"a": "x.json"},
    )

    status = monitor.get_status(r)

    # Legacy flat fields (story stage) survive for existing --json consumers.
    assert status["total"] == 2
    assert status["done"] == 1
    assert status["running"] == 1
    assert status["remaining_in_queue"] == 2
    assert status["results_saved"] == 1

    stages = status["stages"]
    assert set(stages) == {"execute", "analyze", "review"}
    assert stages["analyze"]["done"] == 1
    assert stages["analyze"]["remaining_in_queue"] == 1
    assert stages["analyze"]["results_saved"] is None
    # The review stage ignores the legacy hash (file-derived since the cut-over).
    assert stages["review"]["retry"] == 0
    assert stages["review"]["running"] == 0
    assert stages["review"]["remaining_in_queue"] == 0


def test_review_stage_is_file_derived(tmp_path, monkeypatch):
    """The review stage counts complete aggregates + error markers from the files."""
    _review_fixture(tmp_path, monkeypatch)
    r = _redis({}, {}, {})

    review = monitor.get_status(r)["stages"]["review"]

    assert review["total"] == 3          # the corpus
    assert review["done"] == 1           # the complete aggregate only
    assert review["failed"] == 1         # the error marker (unreviewable story)
    assert review["queued"] == 0
    assert review["running"] == 0
    assert review["retry"] == 0
    assert review["remaining_in_queue"] == 0


def test_get_status_retry_folds_into_running():
    """Every retry_N status folds into ``running`` and is counted in ``retry``."""
    r = _redis({}, {"a": "running", "b": "retry_1", "c": "retry_2"}, {})

    analyze = monitor.get_status(r)["stages"]["analyze"]

    assert analyze["retry"] == 2
    assert analyze["running"] == 3  # 1 running + 2 retries, still in flight
    assert analyze["total"] == 3


def test_get_status_empty_posthoc_stages_are_zeroed(tmp_path, monkeypatch):
    """Absent post-hoc data yields zero counts, never a missing key."""
    reviews = tmp_path / "reviews"
    results = tmp_path / "stories"
    reviews.mkdir()
    results.mkdir()
    monkeypatch.setattr(pipeline_status, "REVIEWS_DIR", reviews)
    monkeypatch.setattr(pipeline_status, "RESULTS_DIR", results)
    r = _redis({"a": "done"}, {}, {})

    stages = monitor.get_status(r)["stages"]

    assert stages["analyze"]["total"] == 0
    assert stages["analyze"]["remaining_in_queue"] == 0
    assert stages["analyze"]["cells"] == {}
    assert stages["review"]["total"] == 0
    assert stages["review"]["done"] == 0
    assert stages["review"]["failed"] == 0


def test_print_status_lists_each_stage(capsys, tmp_path, monkeypatch):
    """The human-readable output names all three pipeline stages."""
    _review_fixture(tmp_path, monkeypatch)
    r = _redis(
        {"a": "done"},
        {"a": "done"},
        {"a_S1": "done"},
    )

    monitor.print_status(monitor.get_status(r), clear_screen=False)
    out = capsys.readouterr().out

    assert "Pipeline stages:" in out
    for label in ("EXECUTE", "ANALYZE", "REVIEW"):
        assert label in out


def test_print_status_surfaces_review_counts(capsys, tmp_path, monkeypatch):
    """The review stage's file-derived counts are visible to the human reader."""
    _review_fixture(tmp_path, monkeypatch)
    r = _redis({"a": "done"}, {}, {})

    monitor.print_status(monitor.get_status(r), clear_screen=False)
    out = capsys.readouterr().out

    assert "REVIEW" in out
    assert "done 1" in out
    assert "failed 1" in out


def test_clear_removes_all_three_stage_keys(monkeypatch, capsys):
    """``--clear`` drops the post-hoc queues alongside the story queue."""
    deleted = []

    class FakeRedisModule:
        class Redis:
            def __init__(self, **kwargs):
                pass

            def delete(self, key):
                deleted.append(key)

    monkeypatch.setattr(monitor, "redis", FakeRedisModule)
    monkeypatch.setattr(sys, "argv", ["monitor.py", "--clear"])

    monitor.main()

    assert sorted(deleted) == sorted([
        "story_jobs", "story_status", "story_results",
        "analysis_jobs", "analysis_status",
        "review_jobs", "review_status",
    ])
    assert "Queue cleared" in capsys.readouterr().out
