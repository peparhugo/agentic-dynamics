"""Tests for the auto-triggered post-hoc handoff.

Covers the wiring introduced in the implement phase:

    execute (worker.py)  --trigger_analysis-->  analyze (analysis_worker.py)
                          --trigger_reviews-->  review (review_all.py)

The four required checks:

1. ``worker._trigger_analysis`` enqueues an analysis job after a cell completes.
2. ``analysis_worker._trigger_reviews`` enqueues review jobs after analysis.
3. A trigger failure is swallowed — it never fails the underlying cell/analysis.
4. The backfill scripts (``enqueue_analysis`` / ``enqueue_reviews``) still build
   and enqueue the same job shapes through the shared ``instrument.posthoc``
   helpers (no drift).

The worker/analysis-worker scripts are loaded by file path (they live in
``scripts/`` and are not importable as a package); their ``main()`` loops are
not exercised here — we test the trigger seams they call, plus the shared
helpers and the backfill scripts end-to-end against a fake Redis.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

import agentic_dynamics.runtime.posthoc as posthoc

# scripts/ is not on the default test path (conftest only adds repo root + src),
# so add it and load the scripts by file path under controlled module names.
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _load_script(name: str):
    """Import a ``scripts/<name>.py`` file as a module without running main()."""
    path = SCRIPTS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # register so relative re-imports resolve identically
    spec.loader.exec_module(module)
    return module


worker = _load_script("worker")
analysis_worker = _load_script("analysis_worker")
enqueue_analysis = _load_script("enqueue_analysis")
enqueue_reviews = _load_script("enqueue_reviews")


class FakeRedis:
    """Minimal in-memory stand-in for the subset of the Redis client we touch.

    ``lpush`` stores JSON-decoded job dicts in push order; ``hset`` records
    ``(key, field) -> value`` so tests can assert the status ledger directly.
    """

    def __init__(self):
        self.queues: dict[str, list[dict]] = {}       # key -> job dicts (push order)
        self.statuses: dict[tuple[str, str], str] = {}  # (key, field) -> value
        self.deleted: list[str] = []

    def ping(self) -> bool:
        return True

    def lpush(self, key: str, value: str) -> None:
        self.queues.setdefault(key, []).append(json.loads(value))

    def hset(self, key: str, field: str, value: str) -> None:
        self.statuses[(key, field)] = value

    def llen(self, key: str) -> int:
        return len(self.queues.get(key, []))

    def delete(self, *keys: str) -> None:
        self.deleted.extend(keys)


@pytest.fixture
def story_worktree(tmp_path: Path) -> Path:
    """Create a git worktree with two ``Session N`` commits, like run_story leaves."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    for i in (1, 2):
        f = repo / "file.txt"
        f.write_text(f"version {i}\n")
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t",
             "commit", "-qm", f"Session {i}"],
            check=True,
        )
    return repo


@pytest.fixture
def story_result_file(tmp_path: Path, story_worktree: Path) -> Path:
    """A saved StoryResult JSON referencing the worktree (what run_story writes)."""
    path = tmp_path / "stories" / "result_s1.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "story_name": "task_manager_api",
        "story_id": "s1",
        "worktree": str(story_worktree),
        "model": "deepseek/deepseek-v4-pro",
        "sessions": [],
    }))
    return path


# ── 1. worker auto-enqueues analysis after a cell ──────────────────────────

def test_result_path_from_stdout_parses_json_line():
    """The worker reads the machine-readable JSON handoff line."""
    stdout = 'Story complete: x\n{"result_path": "experiments/results/stories/x.json"}\n'
    assert worker._result_path_from_stdout(stdout) == Path(
        "experiments/results/stories/x.json"
    )


def test_result_path_from_stdout_falls_back_to_results_line():
    """Backward compatibility: the older ``Results: <path>`` line still works."""
    stdout = "Story complete: x\n  Results: experiments/results/stories/x.json\n"
    assert worker._result_path_from_stdout(stdout) == Path(
        "experiments/results/stories/x.json"
    )


def test_result_path_from_stdout_returns_none_without_results_line():
    assert worker._result_path_from_stdout("no results line here\n") is None


def test_worker_triggers_analysis_after_cell(story_result_file):
    """A completed cell enqueues exactly one analysis job with a seeded status."""
    fake = FakeRedis()
    stdout = f"...\n  Results: {story_result_file}\n"

    worker._trigger_analysis(fake, stdout, "cell_1")

    jobs = fake.queues["analysis_jobs"]
    assert len(jobs) == 1
    assert jobs[0]["story_id"] == "s1"
    assert jobs[0]["result_path"] == str(story_result_file)
    # The worktree is copied verbatim from the result JSON (tmp_path/repo).
    assert jobs[0]["worktree"] == str(story_result_file.parent.parent / "repo")
    # The status ledger is seeded so the queue is monitorable/resumable.
    assert fake.statuses[("analysis_status", "s1")] == "queued"


def test_worker_trigger_skips_when_no_result_line():
    """Missing result path => no-op (never a crash)."""
    fake = FakeRedis()
    worker._trigger_analysis(fake, "no results line\n", "cell_1")
    assert "analysis_jobs" not in fake.queues


# ── 2. analysis worker auto-enqueues review after analysis ─────────────────

def test_analysis_worker_triggers_reviews_after_analysis(story_worktree):
    """After analysis, one commit job per session commit + a story-level job."""
    fake = FakeRedis()

    analysis_worker._trigger_reviews(fake, "s1", "task_manager_api", story_worktree)

    jobs = fake.queues["review_jobs"]
    job_ids = [j["job_id"] for j in jobs]
    assert job_ids == ["s1_1", "s1_2", "s1_story"]

    commit_jobs = [j for j in jobs if j.get("job_type") != "story_review"]
    story_jobs = [j for j in jobs if j.get("job_type") == "story_review"]
    assert len(commit_jobs) == 2
    assert {j["session_number"] for j in commit_jobs} == {1, 2}
    assert all(j["model"] == posthoc.DEFAULT_REVIEW_MODEL for j in jobs)
    assert story_jobs[0]["commit_hash"] == ""

    # Every review job seeds its status under its own job_id.
    for jid in job_ids:
        assert fake.statuses[("review_status", jid)] == "queued"


def test_analysis_worker_skips_reviews_when_no_commits(tmp_path):
    """A worktree with no session commits produces no review jobs (mirrors backfill)."""
    empty = tmp_path / "empty"
    empty.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(empty)], check=True)

    fake = FakeRedis()
    analysis_worker._trigger_reviews(fake, "s1", "story", empty)
    assert "review_jobs" not in fake.queues


# ── 3. trigger failure does not fail the cell ──────────────────────────────

def test_worker_trigger_failure_is_swallowed(monkeypatch, story_result_file):
    """If the analysis trigger raises, the cell still completes (no exception)."""
    def boom(r, result_path):
        raise RuntimeError("redis down")

    monkeypatch.setattr(worker, "trigger_analysis", boom)
    fake = FakeRedis()
    # Must not raise — the worker's `completed += 1` path continues regardless.
    worker._trigger_analysis(fake, f"...\n  Results: {story_result_file}\n", "cell_1")


def test_analysis_worker_trigger_failure_is_swallowed(monkeypatch, story_worktree):
    """If the review trigger raises, the analysis still completes (no exception)."""
    def boom(r, story_id, story_name, worktree, model=posthoc.DEFAULT_REVIEW_MODEL):
        raise RuntimeError("redis down")

    monkeypatch.setattr(analysis_worker, "trigger_reviews", boom)
    analysis_worker._trigger_reviews(FakeRedis(), "s1", "story", story_worktree)


def test_posthoc_trigger_analysis_returns_false_for_bad_input(tmp_path):
    """A malformed result (missing story_id) yields False, not an exception."""
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"worktree": "/tmp/nope"}))
    assert posthoc.trigger_analysis(FakeRedis(), bad) is False


# ── 4. backfill scripts still work (same job shape, no drift) ──────────────

def test_enqueue_analysis_build_jobs_uses_shared_helper(tmp_path, monkeypatch):
    """build_jobs emits the shared analysis-job shape and honors skip_existing."""
    results = tmp_path / "results"
    analysis = tmp_path / "analysis"
    results.mkdir(parents=True)
    analysis.mkdir(parents=True)

    (results / "a.json").write_text(json.dumps({"story_id": "a", "worktree": "/tmp/w_a"}))
    (results / "b.json").write_text(json.dumps({"story_id": "b", "worktree": "/tmp/w_b"}))
    (results / "no_id.json").write_text(json.dumps({"worktree": "/tmp/w"}))
    # c is already analyzed -> skipped when skip_existing=True
    (results / "c.json").write_text(json.dumps({"story_id": "c", "worktree": "/tmp/w_c"}))
    (analysis / "analysis_c.json").write_text("{}")

    monkeypatch.setattr(enqueue_analysis, "RESULTS_DIR", results)
    monkeypatch.setattr(enqueue_analysis, "ANALYSIS_DIR", analysis)

    jobs = enqueue_analysis.build_jobs(skip_existing=True)
    assert [j["story_id"] for j in jobs] == ["a", "b"]
    # The shape is built by the shared helper, so it can't drift.
    assert all(set(j) == {"story_id", "worktree", "result_path"} for j in jobs)


def test_enqueue_analysis_main_enqueues_via_shared_path(tmp_path, monkeypatch):
    """The analysis backfill still lpush + hset through enqueue_job."""
    results = tmp_path / "results"
    analysis = tmp_path / "analysis"
    results.mkdir()
    (results / "a.json").write_text(json.dumps({"story_id": "a", "worktree": "/tmp/w_a"}))

    monkeypatch.setattr(enqueue_analysis, "RESULTS_DIR", results)
    monkeypatch.setattr(enqueue_analysis, "ANALYSIS_DIR", analysis)
    monkeypatch.setattr(sys, "argv", ["enqueue_analysis.py"])

    fake = FakeRedis()
    monkeypatch.setattr(enqueue_analysis.redis, "Redis", lambda *a, **k: fake)

    enqueue_analysis.main()

    assert fake.queues["analysis_jobs"] == [
        {"story_id": "a", "worktree": "/tmp/w_a", "result_path": str(results / "a.json")}
    ]
    assert fake.statuses[("analysis_status", "a")] == "queued"


def test_enqueue_reviews_main_still_works(story_worktree, tmp_path, monkeypatch):
    """The review backfill builds commit + story jobs via the shared helpers."""
    results = tmp_path / "results"
    reviews = tmp_path / "reviews"
    results.mkdir()
    reviews.mkdir()

    result_file = results / "result_s1.json"
    result_file.write_text(json.dumps({
        "story_name": "task_manager_api",
        "story_id": "s1",
        "worktree": str(story_worktree),
        "sessions": [],
    }))

    monkeypatch.setattr(enqueue_reviews, "RESULTS_DIR", results)
    monkeypatch.setattr(enqueue_reviews, "REVIEWS_DIR", reviews)
    monkeypatch.setattr(sys, "argv", ["enqueue_reviews.py"])

    fake = FakeRedis()
    monkeypatch.setattr(enqueue_reviews.redis, "Redis", lambda *a, **k: fake)

    enqueue_reviews.main()

    jobs = fake.queues["review_jobs"]
    assert [j["job_id"] for j in jobs] == ["s1_1", "s1_2", "s1_story"]
    assert all(j["model"] == posthoc.DEFAULT_REVIEW_MODEL for j in jobs)


def test_scripts_share_posthoc_constants():
    """The scripts import (not redefine) the canonical keys/model — no drift."""
    assert enqueue_analysis.ANALYSIS_QUEUE is posthoc.ANALYSIS_QUEUE
    assert enqueue_analysis.ANALYSIS_STATUS is posthoc.ANALYSIS_STATUS
    assert enqueue_reviews.REVIEW_QUEUE is posthoc.REVIEW_QUEUE
    assert enqueue_reviews.REVIEW_STATUS is posthoc.REVIEW_STATUS
    assert enqueue_reviews.DEFAULT_REVIEW_MODEL is posthoc.DEFAULT_REVIEW_MODEL
    assert enqueue_reviews.worktree_commits is posthoc.worktree_commits
    assert enqueue_reviews.build_commit_review_job is posthoc.build_commit_review_job
    assert enqueue_reviews.build_story_review_job is posthoc.build_story_review_job
