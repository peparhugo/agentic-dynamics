"""Tests for the one-time canonical-state migration driver (kb_produce_registry.py).

Mirrors whatever store-double / dry-run-smoke pattern ``tests/test_knowledge_ingestion.py``'s
batch-producer tests use for ``kb_produce.py``: one test per ``_SOURCES`` key asserting the
right ``derive_*`` function is wired to the right ``source_type`` label and reads the
expected directory/file, plus a ``--dry-run`` smoke test proving it touches neither Redis
nor the filesystem. Every fixture directory is built under ``tmp_path`` and the module's
path constants are monkeypatched onto it — none of these tests depends on (or mutates) the
real ``experiments/`` corpus.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import kb_produce_registry as kpr


def _story_result(story_id: str, **overrides) -> dict:
    base = {
        "story_id": story_id,
        "story_name": f"story_{story_id}",
        "language": "python",
        "model": "deepseek/deepseek-v4-flash",
        "perturbation_condition": "clean",
        "worktree": "/tmp/pipeline/wherever",
        "perturbation_strength": 0.0,
        "test_executed_success": True,
        "summary": {"total_cost": 1.0, "total_tokens": 100, "session_count": 1},
        "sessions": [
            {
                "session_number": 1,
                "commit_hash": f"commit_{story_id}",
                "agentic": {"confidence": 0.7, "total_tokens": 100, "estimated_cost_usd": 1.0},
            }
        ],
    }
    base.update(overrides)
    return base


def _review(story_id: str, **overrides) -> dict:
    base = {
        "story_id": story_id,
        "story_name": f"story_{story_id}",
        "model": "deepseek/deepseek-v4-flash",
        "commit_reviews": [],
        "story_review": None,
    }
    base.update(overrides)
    return base


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


# ── _SOURCES table shape ─────────────────────────────────────────


def test_sources_table_has_the_six_plan_step_9_keys():
    assert set(kpr._SOURCES.keys()) == {
        "story", "story-worktree", "review",
        "summary-recovery", "contaminated", "meta-audit",
    }


def test_sources_table_labels_match_the_plan():
    labels = {key: label for key, (label, _fn) in kpr._SOURCES.items()}
    assert labels == {
        "story": "story",
        "story-worktree": "story",
        "review": "review",
        "summary-recovery": "story",
        "contaminated": "story",
        "meta-audit": "meta_session",
    }


def test_sources_table_wires_the_documented_derive_functions():
    fns = {key: fn for key, (_label, fn) in kpr._SOURCES.items()}
    assert fns["story"] is kpr.derive_story_pass1
    assert fns["story-worktree"] is kpr.derive_story_pass3
    assert fns["review"] is kpr.derive_review_pass1
    assert fns["summary-recovery"] is kpr.derive_summary_recovery_pass
    assert fns["contaminated"] is kpr.derive_contaminated_tombstone_pass
    assert fns["meta-audit"] is kpr.derive_meta_audit_pass


# ── story (pass 1) ────────────────────────────────────────────────


def test_derive_story_pass1_reads_stories_dir_not_contaminated_subdir(tmp_path, monkeypatch):
    stories_dir = tmp_path / "stories"
    _write_json(stories_dir / "a.json", _story_result("story_a"))
    _write_json(stories_dir / "_remediation_contaminated" / "b.json", _story_result("story_b"))
    monkeypatch.setattr(kpr, "STORIES_DIR", stories_dir)

    records = kpr.derive_story_pass1("agentic-dynamics")

    # Only the top-level file — the contaminated subdirectory belongs to its own pass.
    assert len(records) == 1
    assert records[0].source_type == "story"
    assert records[0].logical_locator == "story_a"


# ── story-worktree (pass 3, finding 1) ───────────────────────────


def test_derive_story_pass3_reads_both_stranded_worktrees(tmp_path, monkeypatch):
    wt1 = tmp_path / "wt1"
    wt2 = tmp_path / "wt2"
    _write_json(wt1 / "experiments" / "results" / "stories" / "a.json", _story_result("story_a"))
    _write_json(wt2 / "experiments" / "results" / "stories" / "b.json", _story_result("story_b"))
    monkeypatch.setattr(kpr, "STRANDED_WORKTREES", (wt1, wt2))

    records = kpr.derive_story_pass3("agentic-dynamics")

    assert {r.logical_locator for r in records} == {"story_a", "story_b"}
    assert all(r.source_type == "story" for r in records)


def test_derive_story_pass3_tolerates_a_missing_worktree(tmp_path, monkeypatch):
    gone = tmp_path / "does_not_exist"
    monkeypatch.setattr(kpr, "STRANDED_WORKTREES", (gone,))
    assert kpr.derive_story_pass3("agentic-dynamics") == []


def test_worktree_independent_identity_makes_a_duplicate_a_free_no_op(tmp_path, monkeypatch):
    # The SAME story, byte-identical, present in both the main repo and a stranded
    # worktree, must converge on the same knowledge_id (worktree-independence — see
    # story_ingestion's module docstring).
    stories_dir = tmp_path / "stories"
    _write_json(stories_dir / "a.json", _story_result("story_a"))
    monkeypatch.setattr(kpr, "STORIES_DIR", stories_dir)
    main_repo_records = kpr.derive_story_pass1("agentic-dynamics")

    wt = tmp_path / "wt1"
    _write_json(wt / "experiments" / "results" / "stories" / "a.json", _story_result("story_a"))
    monkeypatch.setattr(kpr, "STRANDED_WORKTREES", (wt,))
    stranded_records = kpr.derive_story_pass3("agentic-dynamics")

    assert main_repo_records[0].knowledge_id == stranded_records[0].knowledge_id


# ── review (pass 1) ───────────────────────────────────────────────


def test_derive_review_pass1_skips_per_session_shards(tmp_path, monkeypatch):
    reviews_dir = tmp_path / "reviews"
    _write_json(reviews_dir / "review_abc123.json", _review("abc123"))
    # Shard files: a per-session commit review and the per-story review — must be
    # excluded (different, incomplete shape from the merged file).
    _write_json(reviews_dir / "review_abc123_S1.json", {"commit_hash": "c1"})
    _write_json(reviews_dir / "review_abc123_story.json", {"story_name": "x"})
    monkeypatch.setattr(kpr, "REVIEWS_DIR", reviews_dir)

    records = kpr.derive_review_pass1("agentic-dynamics")

    assert len(records) == 1
    assert records[0].source_type == "review"
    assert records[0].logical_locator == "abc123"


def test_is_merged_review_file_classification():
    assert kpr._is_merged_review_file(Path("review_abc123.json")) is True
    assert kpr._is_merged_review_file(Path("review_abc123_S1.json")) is False
    assert kpr._is_merged_review_file(Path("review_abc123_S12.json")) is False
    assert kpr._is_merged_review_file(Path("review_abc123_story.json")) is False
    assert kpr._is_merged_review_file(Path("not_a_review.json")) is False


# ── contaminated (pass 6) ─────────────────────────────────────────


def test_derive_contaminated_tombstone_pass_reads_the_contaminated_subdir(tmp_path, monkeypatch):
    contaminated_dir = tmp_path / "contaminated"
    _write_json(contaminated_dir / "bad.json", _story_result("bad_cell"))
    monkeypatch.setattr(kpr, "CONTAMINATED_DIR", contaminated_dir)

    records = kpr.derive_contaminated_tombstone_pass("agentic-dynamics")

    assert len(records) == 1
    assert records[0].source_type == "story"
    assert records[0].logical_locator == "bad_cell"


# ── meta-audit (pass 6, gap b) ────────────────────────────────────


def test_derive_meta_audit_pass_only_emits_meta_titled_sessions(tmp_path, monkeypatch):
    inventory = tmp_path / "inventory.json"
    _write_json(inventory, {
        "experiment_session_titles": [
            {"title": "meta_batch_20260810_010810", "cost": 0.001, "tokens_output": 500},
            {"title": "flask_api_std_1", "cost": 0.05, "tokens_output": 4000},  # real experiment
        ],
    })
    monkeypatch.setattr(kpr, "INVENTORY_PATH", inventory)

    records = kpr.derive_meta_audit_pass("agentic-dynamics")

    assert len(records) == 1
    assert records[0].source_type == "meta_session"


def test_derive_meta_audit_pass_missing_inventory_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(kpr, "INVENTORY_PATH", tmp_path / "does_not_exist.json")
    assert kpr.derive_meta_audit_pass("agentic-dynamics") == []


# ── summary-recovery (pass 3, gap c) ──────────────────────────────


def test_derive_summary_recovery_pass_requires_since_sha():
    with pytest.raises(ValueError):
        kpr.derive_summary_recovery_pass("agentic-dynamics", since_sha=None)


def test_derive_summary_recovery_pass_recovers_only_the_missing_entries(tmp_path, monkeypatch):
    current = tmp_path / "_results_summary.json"
    _write_json(current, {"entries": [{"experiment": "still_here"}]})
    monkeypatch.setattr(kpr, "RESULTS_SUMMARY_PATH", current)

    def _fake_historical(since_sha):
        assert since_sha == "deadbeef"
        return {"entries": [
            {"experiment": "still_here", "model": "x"},
            {"experiment": "long_lost", "model": "deepseek/deepseek-v4-flash",
             "worktree_name": "long_lost", "test_executed_success": True},
        ]}

    monkeypatch.setattr(kpr, "_historical_results_summary", _fake_historical)

    records = kpr.derive_summary_recovery_pass("agentic-dynamics", since_sha="deadbeef")

    assert len(records) == 1
    assert records[0].logical_locator == "long_lost"
    assert records[0].source_type == "story"


# ── BUG-7: perturbation_strength must stay None when absent ──────


def test_summary_entry_absent_perturbation_strength_stays_none():
    # A recovered historical entry lacking the field must flow through as None (unmeasured),
    # never a fabricated 0.0 baseline (which downstream would read as "baseline cell").
    result = kpr._summary_entry_to_story_result({"worktree_name": "wt", "experiment": "e"})
    assert result["perturbation_strength"] is None


def test_summary_entry_present_perturbation_strength_is_preserved():
    result = kpr._summary_entry_to_story_result(
        {"worktree_name": "wt", "experiment": "e", "perturbation_strength": 0.5}
    )
    assert result["perturbation_strength"] == 0.5


# ── --dry-run: touches neither Redis nor the filesystem ─────────


def test_dry_run_does_not_connect_to_redis(tmp_path, monkeypatch, capsys):
    stories_dir = tmp_path / "stories"
    _write_json(stories_dir / "a.json", _story_result("story_a"))
    monkeypatch.setattr(kpr, "STORIES_DIR", stories_dir)

    def _explode(*a, **kw):
        raise AssertionError("dry-run must never attempt a Redis connection")

    monkeypatch.setattr(kpr.ks, "connect", _explode)

    kpr.main(["--source", "story", "--dry-run"])

    out = capsys.readouterr().out
    assert "would emit 1 record" in out


def test_dry_run_writes_no_artifact_files(tmp_path, monkeypatch):
    stories_dir = tmp_path / "stories"
    _write_json(stories_dir / "a.json", _story_result("story_a"))
    monkeypatch.setattr(kpr, "STORIES_DIR", stories_dir)

    artifact_dir = tmp_path / "kb_artifacts"
    monkeypatch.setattr(kpr, "KB_ARTIFACT_DIR", artifact_dir)

    kpr.main(["--source", "story", "--dry-run"])

    assert not artifact_dir.exists()


def test_dry_run_never_sets_finops_kb_write(tmp_path, monkeypatch):
    stories_dir = tmp_path / "stories"
    _write_json(stories_dir / "a.json", _story_result("story_a"))
    monkeypatch.setattr(kpr, "STORIES_DIR", stories_dir)
    monkeypatch.delenv("FINOPS_KB_WRITE", raising=False)

    kpr.main(["--source", "story", "--dry-run"])

    import os

    assert os.environ.get("FINOPS_KB_WRITE") != "1"


def test_module_never_imports_actuation_ingestion():
    # Structural invariant: this file imports only story/review/ledger producers, never
    # actuation_ingestion — the actuation gate cannot be exercised by anything in this
    # module because nothing in it can construct an actuation record in the first place.
    # AST-based (not a raw substring search over the source) so this doesn't false-fail
    # on the module's own docstring/comments explaining exactly this invariant in prose.
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(kpr))
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    } | {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert "actuation_ingestion" not in imported_modules
    assert not hasattr(kpr, "derive_actuation_record")


# ── CLI subprocess smoke test (the literal command the task names) ──


def test_cli_dry_run_against_the_real_repo_touches_nothing(tmp_path):
    """`python scripts/kb_produce_registry.py --dry-run --source story` — the literal
    verification command — must exit 0, print a would-emit summary, and leave the repo's
    git status unchanged (no new/modified tracked or untracked files)."""
    import subprocess

    repo_root = Path(__file__).resolve().parent.parent
    before = subprocess.run(
        ["git", "-C", str(repo_root), "status", "--porcelain"],
        capture_output=True, text=True, check=True,
    ).stdout

    result = subprocess.run(
        ["python3", "scripts/kb_produce_registry.py", "--dry-run", "--source", "story"],
        cwd=repo_root, capture_output=True, text=True,
    )

    after = subprocess.run(
        ["git", "-C", str(repo_root), "status", "--porcelain"],
        capture_output=True, text=True, check=True,
    ).stdout

    assert result.returncode == 0, result.stderr
    assert "would emit" in result.stdout
    assert before == after
