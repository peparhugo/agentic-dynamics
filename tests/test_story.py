"""Tests for multi-session story orchestrator."""

import tempfile
from pathlib import Path

import pytest

from agentic_dynamics.runtime.story import (
    BUILTIN_STORIES,
    PerturbationCondition,
    SessionResult,
    SessionSpec,
    StoryConfig,
    StoryResult,
    _detect_or_use,
    _git,
    _prepare_worktree,
    condition_to_mutations,
    load_story_result,
    notification_service_story,
    run_story,
    save_story_result,
    static_site_gen_story,
    task_manager_story,
)


class TestSessionSpec:
    def test_serialization_roundtrip(self):
        s = SessionSpec(
            session_number=1,
            task_type="greenfield",
            prompt="Build a REST API.",
            description="Create endpoints",
        )
        d = s.to_dict()
        s2 = SessionSpec.from_dict(d)
        assert s2.session_number == 1
        assert s2.task_type == "greenfield"
        assert s2.prompt == "Build a REST API."


class TestStoryConfig:
    def test_serialization_roundtrip(self):
        config = StoryConfig(
            name="test_story",
            description="A test story",
            language="python",
            sessions=[
                SessionSpec(1, "greenfield", "Build API."),
                SessionSpec(2, "feature_addition", "Add auth."),
            ],
        )
        d = config.to_dict()
        config2 = StoryConfig.from_dict(d)
        assert config2.name == "test_story"
        assert len(config2.sessions) == 2

    def test_yaml_roundtrip(self):
        config = StoryConfig(
            name="yaml_test",
            description="YAML roundtrip test",
            language="python",
            sessions=[SessionSpec(1, "greenfield", "Do thing.")],
        )
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            config.to_yaml(dp / "story.yaml")
            loaded = StoryConfig.from_yaml(dp / "story.yaml")
            assert loaded.name == "yaml_test"
            assert len(loaded.sessions) == 1

    def test_empty_sessions(self):
        config = StoryConfig(name="empty")
        assert len(config.sessions) == 0


class TestStoryResult:
    def test_properties(self):
        result = StoryResult(
            story_name="test",
            sessions=[
                SessionResult(1, "greenfield", "A", cost_usd=1.0, total_tokens=100),
                SessionResult(2, "refactor", "B", cost_usd=2.0, total_tokens=200),
            ],
        )
        assert result.total_cost == 3.0
        assert result.total_tokens == 300
        assert result.session_count == 2

    def test_serialization(self):
        result = StoryResult(
            story_name="test",
            story_id="abc123",
            model="deepseek/test",
            sessions=[
                SessionResult(1, "greenfield", "Build.", cost_usd=5.0, total_tokens=500),
            ],
        )
        d = result.to_dict()
        assert d["story_name"] == "test"
        assert d["summary"]["total_cost"] == 5.0
        assert len(d["sessions"]) == 1

    def test_save_and_load(self):
        result = StoryResult(
            story_name="test",
            story_id="abc123",
            sessions=[
                SessionResult(1, "greenfield", "Build.", cost_usd=3.0, total_tokens=300),
            ],
        )
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            save_story_result(result, dp / "result.json")
            loaded = load_story_result(dp / "result.json")
            assert loaded.story_name == "test"
            assert loaded.total_cost == 3.0

    def test_save_story_result_skips_emission_when_kb_write_unset(self, monkeypatch):
        # Default test environment: FINOPS_KB_WRITE is unset, so a plain save must never
        # attempt a knowledge-stream connection — canonical-state round 2, plan step 10.
        monkeypatch.delenv("FINOPS_KB_WRITE", raising=False)
        from agentic_dynamics.knowledge import knowledge_stream as ks

        def _explode(*a, **kw):
            raise AssertionError("must not connect to the knowledge stream when KB_WRITE is unset")

        monkeypatch.setattr(ks, "connect", _explode)

        result = StoryResult(story_name="test", story_id="abc123")
        with tempfile.TemporaryDirectory() as d:
            save_story_result(result, Path(d) / "result.json")
        # No assertion error raised above == no connection attempt was made.

    def test_save_story_result_emits_registry_event_when_kb_write_enabled(self, monkeypatch):
        monkeypatch.setenv("FINOPS_KB_WRITE", "1")
        from agentic_dynamics.knowledge import knowledge_stream as ks

        published = []
        monkeypatch.setattr(ks, "connect", lambda: object())
        monkeypatch.setattr(
            ks, "publish_event",
            lambda r, event, **kw: published.append((event, kw)) or "0-1",
        )

        result = StoryResult(
            story_name="test", story_id="abc123",
            sessions=[SessionResult(1, "greenfield", "Build.", cost_usd=3.0, total_tokens=300)],
        )
        with tempfile.TemporaryDirectory() as d:
            save_story_result(result, Path(d) / "result.json")

        assert len(published) == 1
        event, kwargs = published[0]
        assert kwargs["source_type"] == "story"
        assert kwargs["authorized"] is True
        assert event.knowledge_id  # a real (non-empty) identity was derived

    def test_all_successful(self):
        result = StoryResult(
            story_name="test",
            sessions=[
                SessionResult(1, "greenfield", "A", exit_code=0),
                SessionResult(2, "refactor", "B", exit_code=1),
            ],
        )
        assert not result.all_successful

        result2 = StoryResult(
            story_name="test2",
            sessions=[
                SessionResult(1, "greenfield", "A", exit_code=0),
                SessionResult(2, "refactor", "B", exit_code=0),
            ],
        )
        assert result2.all_successful


class TestGitHelpers:
    def test_init_and_commit(self):
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            _git(dp, "init")
            (dp / "test.txt").write_text("hello")
            _git(dp, "add", "-A")
            _git(dp, "commit", "-m", "initial commit")
            log = _git(dp, "log", "--oneline")
            assert "initial commit" in log

    def test_ls_files(self):
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            _git(dp, "init")
            (dp / "a.txt").write_text("a")
            (dp / "b.txt").write_text("b")
            _git(dp, "add", "-A")
            _git(dp, "commit", "-m", "init")
            files = _git(dp, "ls-files").strip().splitlines()
            assert "a.txt" in files
            assert "b.txt" in files

    def test_rev_parse(self):
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            _git(dp, "init")
            (dp / "x.txt").write_text("x")
            _git(dp, "add", "-A")
            _git(dp, "commit", "-m", "first")
            commit = _git(dp, "rev-parse", "HEAD").strip()
            assert len(commit) == 40  # full SHA


class TestPrepareWorktree:
    def test_clones_and_inits_git(self):
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            # Create seed codebase
            seed = dp / "seed"
            seed.mkdir()
            (seed / "app.py").write_text("x = 1\n")

            worktree = dp / "worktree"
            _prepare_worktree(str(seed), worktree, None)

            assert (worktree / ".git").is_dir()
            assert (worktree / "app.py").exists()
            log = _git(worktree, "log", "--oneline")
            assert "Initial seed codebase" in log


class TestBuiltinStories:
    def test_task_manager_story(self):
        story = task_manager_story()
        assert story.name == "task_manager_api"
        assert story.language == "python"
        assert len(story.sessions) == 5
        types = [s.task_type for s in story.sessions]
        assert types == ["greenfield", "feature_addition", "integration", "refactor", "cross_cutting"]

    def test_static_site_story(self):
        story = static_site_gen_story()
        assert story.name == "static_site_gen"
        assert story.language == "typescript"
        assert len(story.sessions) == 5

    def test_builtin_catalog(self):
        assert "task_manager_api" in BUILTIN_STORIES
        assert "static_site_gen" in BUILTIN_STORIES

    def test_all_sessions_have_prompts(self):
        for name, story in BUILTIN_STORIES.items():
            for s in story.sessions:
                assert s.prompt, f"{name} session {s.session_number} has empty prompt"
                assert len(s.prompt) > 50, f"{name} session {s.session_number} prompt too short"

    def test_yaml_export_import(self):
        for _name, story in BUILTIN_STORIES.items():
            d = story.to_dict()
            reloaded = StoryConfig.from_dict(d)
            assert reloaded.name == story.name
            assert len(reloaded.sessions) == len(story.sessions)


class TestDetectOrUse:
    def test_falls_back_when_no_code(self):
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            (dp / "readme.md").write_text("# hello")
            result = _detect_or_use(dp, "python")
            assert result == "python"  # no Python files, falls back

    def test_detects_python(self):
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            (dp / "app.py").write_text("x = 1")
            result = _detect_or_use(dp, "typescript")
            assert result == "python"  # detected, overrides fallback


def test_run_story_validates_sessions():
    config = StoryConfig(name="empty", sessions=[])
    with pytest.raises(ValueError, match="no sessions"):
        run_story(config, codebase_path="/tmp")


class TestPerturbationCondition:
    def test_clean_returns_no_mutations(self):
        cm, sm = condition_to_mutations(
            PerturbationCondition.CLEAN,
            Path("."),
            ["spec1", "spec2"],
        )
        assert cm is None
        assert sm == {}

    def test_early_degrade_returns_session1_mutation(self, monkeypatch):
        monkeypatch.setattr(
            "instrument.story.compile_mutation",
            lambda specification, operator, strength, model, cache_dir: None,
        )
        cm, sm = condition_to_mutations(
            PerturbationCondition.EARLY_DEGRADE,
            Path("."),
            ["build api", "add auth"],
        )
        assert cm is None
        assert 1 in sm

    def test_early_degrade_empty_specs(self):
        cm, sm = condition_to_mutations(
            PerturbationCondition.EARLY_DEGRADE,
            Path("."),
            [],
        )
        assert cm is None
        assert sm == {}

    def test_bad_seed_nonexistent_path(self):
        cm, sm = condition_to_mutations(
            PerturbationCondition.BAD_SEED,
            Path("/nonexistent/path/xyz"),
            [],
        )
        assert cm is None

    def test_all_conditions_are_strings(self):
        for cond in PerturbationCondition:
            assert isinstance(cond.value, str)

    def test_story_result_tracks_condition(self):
        result = StoryResult(
            story_name="test",
            perturbation_condition="bad_seed",
        )
        assert result.perturbation_condition == "bad_seed"

    def test_cascade_recovery_none_with_few_sessions(self):
        result = StoryResult(
            story_name="test",
            sessions=[SessionResult(1, "greenfield", "A")],
        )
        assert result.cascade_recovery is None

    def test_cascade_recovery_with_improvement(self):
        from agentic_dynamics.adapters.opencode import AgenticResult
        s1 = SessionResult(1, "greenfield", "A")
        s1.agentic = AgenticResult(tests_passed=2, tests_total=10)  # 0.2
        s2 = SessionResult(2, "refactor", "B")
        s2.agentic = AgenticResult(tests_passed=8, tests_total=10)  # 0.8
        result = StoryResult(
            story_name="test",
            sessions=[s1, s2],
        )
        assert result.cascade_recovery is True


class TestNotificationStory:
    def test_exists_in_builtins(self):
        assert "notification_service" in BUILTIN_STORIES

    def test_has_five_sessions(self):
        story = notification_service_story()
        assert len(story.sessions) == 5

    def test_session_types(self):
        story = notification_service_story()
        types = [s.task_type for s in story.sessions]
        assert types == ["greenfield", "feature_addition", "integration", "refactor", "cross_cutting"]

    def test_all_prompts_are_substantial(self):
        story = notification_service_story()
        for s in story.sessions:
            assert len(s.prompt) > 100, f"Session {s.session_number} prompt too short"
