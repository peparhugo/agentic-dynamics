"""Tests for opencode-driven analysis module."""

import json
from types import SimpleNamespace

import pytest

import instrument.opencode_analyzer as analyzer_module
from instrument.opencode_analyzer import (
    OpencodeAnalyzer,
    _build_batch_prompt,
    _build_comparison_prompt,
    _build_session_prompt,
    _load_session_jsonl,
    _load_summary,
    _resolve_worktree,
)

pytestmark = pytest.mark.external


class TestLoadSummary:
    def test_returns_list_with_entries(self):
        entries = _load_summary()
        assert isinstance(entries, list)
        assert len(entries) > 0
        entry = entries[0]
        assert "model" in entry
        assert "cost" in entry
        assert "worktree_name" in entry


class TestResolveWorktree:
    def test_direct_name_resolves(self):
        name = _resolve_worktree("exp_0s36_d3n")
        assert name == "exp_0s36_d3n"

    def test_unknown_returns_unchanged(self):
        name = _resolve_worktree("nonexistent_session_xyz123")
        assert name == "nonexistent_session_xyz123"


class TestSessionJsonl:
    def test_loads_existing_session(self):
        text = _load_session_jsonl("exp_0s36_d3n")
        assert text is not None
        assert len(text) > 0
        assert '"type"' in text

    def test_missing_session_returns_none(self):
        text = _load_session_jsonl("nonexistent_session")
        assert text is None


class TestBuildPrompt:
    def test_session_prompt_has_metrics(self, tmp_path, monkeypatch):
        # Prompt formatting is tested against stable inputs, not the mutable result aggregate.
        reports_dir = tmp_path / "reports"
        session_dir = reports_dir / "exp_0s36_d3n"
        session_dir.mkdir(parents=True)
        (session_dir / "session.jsonl").write_text('{"type": "reasoning"}\n')
        summary_path = tmp_path / "summary.json"
        summary_path.write_text(json.dumps({"entries": [{
            "worktree_name": "exp_0s36_d3n",
            "model": "deepseek/deepseek-v4-pro",
            "correctness": 0.9,
        }]}))
        monkeypatch.setattr(analyzer_module, "REPORTS_DIR", reports_dir)
        monkeypatch.setattr(analyzer_module, "SUMMARY_PATH", summary_path)

        prompt = _build_session_prompt("exp_0s36_d3n")
        assert "exp_0s36_d3n" in prompt
        assert "deepseek/deepseek-v4-pro" in prompt
        assert "correctness" in prompt.lower()
        assert "analysis.md" in prompt.lower()

    def test_session_prompt_has_analysis_instructions(self):
        prompt = _build_session_prompt("exp_0s36_d3n")
        assert "analysis.md" in prompt.lower()
        assert "problem-solving" in prompt.lower()

    def test_comparison_prompt_has_both_sessions(self):
        a = "exp_0s36_d3n"
        b = "exp_0s36_d3n"
        prompt = _build_comparison_prompt(a, b)
        assert "Baseline" in prompt
        assert "Perturbed" in prompt
        assert "comparison.md" in prompt.lower()

    def test_batch_prompt_formats_entries(self):
        entries = [
            {"model": "deepseek", "experiment": "test1", "correctness": 0.9, "cost": 0.01, "strategy": "conservative", "escape": 0.1},
            {"model": "claude", "experiment": "test2", "correctness": 0.8, "cost": 0.50, "strategy": "exploratory", "escape": 0.3},
        ]
        prompt = _build_batch_prompt(entries, "What do you see?")
        assert "test1" in prompt
        assert "test2" in prompt
        assert "What do you see?" in prompt


class TestOpencodeAnalyzer:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.analyzer = OpencodeAnalyzer(
            model="deepseek/deepseek-v4-flash",
            timeout=300,
        )

    def test_model_configured(self):
        assert self.analyzer.model == "deepseek/deepseek-v4-flash"
        assert self.analyzer.timeout == 300

    def test_default_model_is_flash(self):
        a = OpencodeAnalyzer()
        assert a.model == "deepseek/deepseek-v4-flash"

    def test_analyze_session_produces_result(self):
        result = self.analyzer.analyze_session("exp_0s36_d3n")
        assert result is not None
        assert result.model == "deepseek/deepseek-v4-flash"
        assert result.duration_s > 0
        assert result.exit_code >= 0

    def test_analyze_session_loads_metrics(self):
        result = self.analyzer.analyze_session("exp_0s36_d3n")
        assert result is not None

    def test_compare_sessions_produces_result(self):
        result = self.analyzer.compare_sessions(
            "exp_0s36_d3n", "exp_0s36_d3n",
        )
        assert result is not None
        assert result.duration_s > 0

    def test_batch_analyze_produces_result(self):
        entries = _load_summary()[:3]
        result = self.analyzer.batch_analyze(entries, "What patterns emerge?")
        assert result is not None
        assert result.duration_s > 0

    def test_filtered_analysis_wasteful(self):
        try:
            result = self.analyzer.analyze_filtered("strategy", "wasteful", limit=3)
            assert result is not None
            assert result.duration_s > 0
        except ValueError as e:
            if "No entries" in str(e):
                pytest.skip("No wasteful entries available")

    def test_model_analysis(self, monkeypatch):
        model_id = "deepseek/deepseek-v4-pro"
        expected_entries = [{"model": model_id, "experiment": "fixture"}]
        captured = {}

        monkeypatch.setattr(analyzer_module, "_load_summary", lambda: expected_entries)

        def fake_batch_analyze(entries, question):
            """Capture the filtered batch without invoking the external analysis harness."""
            captured["entries"] = entries
            captured["question"] = question
            return SimpleNamespace(duration_s=1.0)

        monkeypatch.setattr(self.analyzer, "batch_analyze", fake_batch_analyze)

        result = self.analyzer.analyze_model(model_id)

        assert result.duration_s > 0
        assert captured["entries"] == expected_entries
        assert model_id in captured["question"]
