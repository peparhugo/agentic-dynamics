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

from scripts.archive import kb_produce_registry as kpr


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


def test_sources_table_has_the_six_canonical_sources():
    assert set(kpr._SOURCES.keys()) == {
        "story", "story-worktree", "review",
        "single-task", "contaminated", "meta-audit",
    }


def test_sources_table_labels_match_the_plan():
    labels = {key: label for key, (label, _fn) in kpr._SOURCES.items()}
    assert labels == {
        "story": "story",
        "story-worktree": "story",
        "review": "review",
        "single-task": "finding",
        "contaminated": "story",
        "meta-audit": "meta_session",
    }


def test_sources_table_wires_the_documented_derive_functions():
    fns = {key: fn for key, (_label, fn) in kpr._SOURCES.items()}
    assert fns["story"] is kpr.derive_story_pass1
    assert fns["story-worktree"] is kpr.derive_story_pass3
    assert fns["review"] is kpr.derive_review_pass1
    assert fns["single-task"] is kpr.derive_single_task_pass
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


def test_derive_story_pass3_skips_contaminated_cells(tmp_path, monkeypatch):
    # feature_queue-steer-2 was cut BEFORE the remediation moved the 77 contaminated files
    # into _remediation_contaminated/, so its top-level stories/ still holds them. Pass 3
    # must EXCLUDE those story_ids — otherwise it registers a contaminated cell as a plain
    # upsert (current) before pass 6 can tombstone it, and the tombstone's delete event is
    # deduped away by knowledge_id.
    contam_dir = tmp_path / "contaminated"
    _write_json(contam_dir / "x_early_degrade_contam1.json", _story_result("contam1"))
    monkeypatch.setattr(kpr, "CONTAMINATED_DIR", contam_dir)

    wt = tmp_path / "wt1"
    stories = wt / "experiments" / "results" / "stories"
    _write_json(stories / "x_early_degrade_contam1.json", _story_result("contam1"))
    _write_json(stories / "x_clean_ok1.json", _story_result("ok1"))
    monkeypatch.setattr(kpr, "STRANDED_WORKTREES", (wt,))

    records = kpr.derive_story_pass3("agentic-dynamics")

    assert {r.logical_locator for r in records} == {"ok1"}


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


# ── single-task (clean single-task perturbation arm) ─────────────


def _single_task_run(**overrides) -> dict:
    base = {
        "type": "baseline",
        "model": "deepseek/deepseek-v4-pro",
        "operator": "baseline",
        "perturbation_class": "baseline",
        "strength": 0.0,
        "perturbation_strength": 0.0,
        "test_executed_success": True,
        "correctness": 1.0,
        "cost_usd": 0.01,
        "confidence": 1.0,
        "escape_score": 0.2,
        "workdir": "/tmp/exp_abc123",
    }
    base.update(overrides)
    return base


def _run_file_data(experiment: str, model: str, runs: list) -> dict:
    return {"experiment": experiment, "model": model, "runs": runs}


def test_derive_single_task_pass_emits_finding_records(tmp_path, monkeypatch):
    results_dir = tmp_path / "results"
    _write_json(results_dir / "task_manager_deepseek-v4-pro.json", _run_file_data(
        "task_manager", "deepseek-v4-pro",
        [
            _single_task_run(),
            _single_task_run(
                operator="inject_alien_vocab",
                perturbation_class="process_perturbation",
                perturbation_strength=0.5,
                workdir="/tmp/exp_def456",
            ),
        ],
    ))
    _write_json(results_dir / "process_perturbation_resample_deepseek-v4-pro.json", _run_file_data(
        "process_perturbation_resample", "deepseek-v4-pro",
        [_single_task_run(operator="shift_framing", workdir="/tmp/exp_ghi789")],
    ))
    monkeypatch.setattr(kpr, "SINGLE_TASK_DIR", results_dir)

    records = kpr.derive_single_task_pass("agentic-dynamics")

    assert len(records) == 3
    # source_type is "finding" — never "story" (these are measured single-task re-runs).
    assert all(r.source_type == "finding" for r in records)
    assert all(r.source_type != "story" for r in records)
    assert {r.logical_locator for r in records} == {"exp_abc123", "exp_def456", "exp_ghi789"}
    # Each file's own locator is the source_uri, not the retired aggregate summary.
    assert any("task_manager_deepseek-v4-pro.json" in r.source_uri for r in records)
    assert any("process_perturbation_resample_deepseek-v4-pro.json" in r.source_uri for r in records)


def test_derive_single_task_pass_skips_invalid_gpt56(tmp_path, monkeypatch):
    results_dir = tmp_path / "results"
    # The invalid plain gpt-5.6 (server error, all-zero runs) — must be skipped.
    _write_json(results_dir / "process_perturbation_resample_gpt-5.6.json", _run_file_data(
        "process_perturbation_resample", "gpt-5.6",
        [_single_task_run(
            model="openai/gpt-5.6", correctness=0.0, cost_usd=0.0,
            test_executed_success=False, workdir="/tmp/exp_invalid",
        )],
    ))
    # The valid gpt-5.6-sol variant — must be kept.
    _write_json(results_dir / "process_perturbation_resample_gpt-5.6-sol.json", _run_file_data(
        "process_perturbation_resample", "gpt-5.6-sol",
        [_single_task_run(model="openai/gpt-5.6-sol", workdir="/tmp/exp_sol")],
    ))
    monkeypatch.setattr(kpr, "SINGLE_TASK_DIR", results_dir)

    records = kpr.derive_single_task_pass("agentic-dynamics")

    assert len(records) == 1
    assert records[0].text.startswith("openai/gpt-5.6-sol under")
    assert all("openai/gpt-5.6 under" not in r.text for r in records)


def test_run_to_entry_renames_cost_and_escape_and_worktree():
    entry = kpr._run_to_entry(
        {
            "model": "deepseek/deepseek-v4-pro",
            "operator": "baseline",
            "perturbation_class": "baseline",
            "correctness": 1.0,
            "cost_usd": 0.01,
            "escape_score": 0.2,
            "test_executed_success": True,
            "workdir": "/tmp/exp_abc123",
        },
        "deepseek-v4-pro",
    )
    assert entry["worktree_name"] == "exp_abc123"
    assert entry["run_id"] == "exp_abc123"
    assert entry["cost"] == 0.01
    assert entry["escape"] == 0.2
    assert entry["test_executed_success"] is True


def test_run_to_entry_falls_back_to_file_model():
    entry = kpr._run_to_entry({"workdir": "/tmp/exp_xyz"}, "deepseek-v4-pro")
    assert entry["model"] == "deepseek-v4-pro"


# ── RETIRE: summary-recovery + the flawed 144 are gone ──────────


def test_summary_recovery_is_retired():
    # The summary-recovery source (the flawed 144-entry _results_summary.json fold) is
    # removed wholesale: no source key, no derive fn, no --since-sha helpers, no path constant.
    assert "summary-recovery" not in kpr._SOURCES
    assert not hasattr(kpr, "derive_summary_recovery_pass")
    assert not hasattr(kpr, "_historical_results_summary")
    assert not hasattr(kpr, "_summary_entry_to_story_result")
    assert not hasattr(kpr, "RESULTS_SUMMARY_PATH")


def test_cli_rejects_the_retired_summary_recovery_source(tmp_path):
    # --source summary-recovery is no longer a valid choice (argparse exits non-zero),
    # and --since-sha no longer exists as a flag.
    with pytest.raises(SystemExit):
        kpr.main(["--source", "summary-recovery", "--dry-run"])
    with pytest.raises(SystemExit):
        kpr.main(["--source", "story", "--dry-run", "--since-sha", "deadbeef"])


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

