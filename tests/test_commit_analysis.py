"""Tests for per-commit analysis module."""

import tempfile
from pathlib import Path

from agentic_dynamics.measurement.commit_analysis import (
    CommitAnalysis,
    StoryAnalysis,
    _run_git,
    analyze_story_worktree,
    compute_ast_diff,
    get_convention_rules,
    score_conventions,
)


class TestCommitAnalysis:
    def test_serialization(self):
        ca = CommitAnalysis(
            commit_hash="abc123",
            commit_message="Add auth",
            session_number=2,
            files_added=2,
            files_modified=1,
            lines_added=50,
            lines_removed=10,
            functions_added=3,
            functions_removed=1,
            convention_score=0.85,
        )
        d = ca.to_dict()
        assert d["commit_hash"] == "abc123"
        assert d["ast"]["files_added"] == 2
        assert d["convention"]["score"] == 0.85

    def test_defaults(self):
        ca = CommitAnalysis(commit_hash="def456")
        assert ca.files_added == 0
        assert ca.sonar_available is False


class TestStoryAnalysis:
    def test_properties(self):
        sa = StoryAnalysis(
            story_name="test",
            commits=[
                CommitAnalysis(commit_hash="a", lines_added=100, lines_removed=0, convention_score=0.9),
                CommitAnalysis(commit_hash="b", lines_added=50, lines_removed=20, convention_score=0.7),
            ],
        )
        assert sa.total_lines_added == 150
        assert sa.total_lines_removed == 20
        assert sa.net_lines == 130
        assert sa.average_convention_score == 0.8

    def test_serialization(self):
        sa = StoryAnalysis(
            story_name="test_story",
            story_id="abc123",
            language="python",
            commits=[CommitAnalysis(commit_hash="a", lines_added=10)],
        )
        d = sa.to_dict()
        assert d["story_name"] == "test_story"
        assert d["summary"]["commits"] == 1


class TestConventions:
    def test_python_conventions_exist(self):
        rules = get_convention_rules("python")
        assert len(rules.naming_patterns) > 0

    def test_typescript_conventions_exist(self):
        rules = get_convention_rules("typescript")
        assert len(rules.naming_patterns) > 0

    def test_unknown_language_gets_empty_rules(self):
        rules = get_convention_rules("haskell")
        assert rules.language == "haskell"
        assert len(rules.naming_patterns) == 0



# A temporary repo created by ``git init`` inherits no identity: this host sets ``user.name`` /
# ``user.email`` only in the project repo, never globally, so ``git commit`` inside a tmp_path
# repo dies with "Author identity unknown". Every other scratch-repo test in this suite
# (test_workflow_runner, test_opencode_events, test_checkpoint_mechanism, test_auto_posthoc)
# already stamps a local identity after init; these helpers bring the remaining files onto that
# same convention so the suite is deterministic regardless of the host's global git config.
def _init_repo(dp: Path) -> None:
    """``git init`` a scratch repo AND stamp a local identity so commits succeed."""
    _run_git(dp, "init")
    _run_git(dp, "config", "user.email", "test@instrument.local")
    _run_git(dp, "config", "user.name", "Instrument Test")


class TestScoreConventions:
    def test_scores_python_naming(self):
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            _init_repo(dp)
            (dp / "app.py").write_text(
                "def get_user(id):\n    pass\n\nclass UserService:\n    pass\n"
            )
            _run_git(dp, "add", "-A")
            _run_git(dp, "commit", "-m", "init")
            commit = _run_git(dp, "rev-parse", "HEAD").strip()

            score, violations = score_conventions(dp, commit)
            assert 0.0 <= score <= 1.0

    def test_scores_lower_with_bad_naming(self):
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            _init_repo(dp)
            # Bad naming: camelCase function, lowercase class
            (dp / "app.py").write_text(
                "def GetUser(id):\n    pass\n\nclass user_service:\n    pass\n"
            )
            _run_git(dp, "add", "-A")
            _run_git(dp, "commit", "-m", "bad names")
            commit = _run_git(dp, "rev-parse", "HEAD").strip()

            score, violations = score_conventions(dp, commit)
            assert score <= 0.5  # Bad naming should score poorly


class TestASTDiff:
    def test_computes_delta(self):
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            _init_repo(dp)
            # Commit 1: initial
            (dp / "app.py").write_text("import os\n\ndef foo():\n    pass\n")
            _run_git(dp, "add", "-A")
            _run_git(dp, "commit", "-m", "initial")
            c1 = _run_git(dp, "rev-parse", "HEAD").strip()

            # Commit 2: add function
            (dp / "app.py").write_text("import os\nimport sys\n\ndef foo():\n    pass\n\ndef bar():\n    pass\n")
            _run_git(dp, "add", "-A")
            _run_git(dp, "commit", "-m", "add bar")
            c2 = _run_git(dp, "rev-parse", "HEAD").strip()

            diff = compute_ast_diff(dp, c1, c2)
            assert diff.files_modified == 1
            assert diff.lines_added > 0
            assert diff.functions_added >= 1
            assert diff.imports_added >= 1

    def test_counts_go_functions(self):
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            _init_repo(dp)
            (dp / "main.go").write_text("package main\n\nfunc Foo() {}\n")
            _run_git(dp, "add", "-A")
            _run_git(dp, "commit", "-m", "initial")
            c1 = _run_git(dp, "rev-parse", "HEAD").strip()

            (dp / "main.go").write_text("package main\n\nfunc Foo() {}\n\nfunc Bar() {}\n")
            _run_git(dp, "add", "-A")
            _run_git(dp, "commit", "-m", "add Bar")
            c2 = _run_git(dp, "rev-parse", "HEAD").strip()

            diff = compute_ast_diff(dp, c1, c2)
            assert diff.functions_added >= 1

    def test_counts_rust_functions(self):
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            _init_repo(dp)
            (dp / "main.rs").write_text("fn foo() {}\n")
            _run_git(dp, "add", "-A")
            _run_git(dp, "commit", "-m", "initial")
            c1 = _run_git(dp, "rev-parse", "HEAD").strip()

            (dp / "main.rs").write_text("fn foo() {}\n\nfn bar() {}\n")
            _run_git(dp, "add", "-A")
            _run_git(dp, "commit", "-m", "add bar")
            c2 = _run_git(dp, "rev-parse", "HEAD").strip()

            diff = compute_ast_diff(dp, c1, c2)
            assert diff.functions_added >= 1


class TestAnalyzeStoryWorktree:
    def test_empty_worktree(self):
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            _init_repo(dp)
            analysis = analyze_story_worktree(dp)
            assert len(analysis.commits) == 0

    def test_with_session_commits(self):
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            _init_repo(dp)
            (dp / "app.py").write_text("x = 1\n")
            _run_git(dp, "add", "-A")
            _run_git(dp, "commit", "-m", "Initial seed")
            (dp / "app.py").write_text("x = 1\ny = 2\n")
            _run_git(dp, "add", "-A")
            _run_git(dp, "commit", "-m", "[story] Session 1: greenfield")
            (dp / "app.py").write_text("x = 1\ny = 2\nz = 3\n")
            _run_git(dp, "add", "-A")
            _run_git(dp, "commit", "-m", "[story] Session 2: refactor")

            analysis = analyze_story_worktree(dp)
            assert len(analysis.commits) == 2
            assert analysis.commits[0].session_number == 1
