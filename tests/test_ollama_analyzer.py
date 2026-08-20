"""Tests for Ollama analyzer module."""

import json
import socket
import tempfile
from pathlib import Path

import pytest

from agentic_dynamics.reporting.ollama_analyzer import OllamaAnalyzer, load_summary_data

try:
    s = socket.create_connection(("localhost", 11434), timeout=2)
    s.close()
    _OLLAMA_OK = True
except Exception:
    _OLLAMA_OK = False

pytestmark = [
    pytest.mark.external,
    pytest.mark.skipif(not _OLLAMA_OK, reason="Ollama not available on localhost:11434"),
]


class TestOllamaAnalyzer:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.analyzer = OllamaAnalyzer(model="deepseek-r1:1.5b")

    def test_model_configured(self):
        assert self.analyzer.model == "deepseek-r1:1.5b"

    def test_summarize_experiment_basic(self):
        metrics = {
            "model": "test-model",
            "experiment": "typescript_ssg",
            "operator": "baseline",
            "perturbation_class": "baseline",
            "cost": 0.015,
            "correctness": 0.92,
            "strategy": "conservative",
            "escape": 0.2,
            "code_lines": 500,
            "tokens": 50000,
            "thinking_ratio": 0.07,
            "constraints_met": 6,
            "constraints_total": 7,
            "architecture_divergence": 0.1,
            "structure_divergence": 0.15,
            "novelty_score": 0.3,
        }
        result = self.analyzer.summarize_experiment(metrics)
        assert isinstance(result, str)
        assert len(result) > 20

    def test_compare_sessions(self):
        baseline = {
            "model": "deepseek/deepseek-v4-pro",
            "cost": 0.01,
            "correctness": 0.95,
            "tokens": 40000,
            "strategy": "conservative",
        }
        perturbed = {
            "model": "deepseek/deepseek-v4-pro",
            "operator": "inject_alien_vocab",
            "perturbation_class": "process_perturbation",
            "cost": 0.02,
            "correctness": 0.70,
            "escape": 0.45,
            "tokens": 60000,
            "strategy": "exploratory",
        }
        result = self.analyzer.compare_sessions(baseline, perturbed)
        assert isinstance(result, str)
        assert len(result) > 20

    def test_batch_analyze_returns_string(self):
        entries = [
            {"model": "deepseek", "experiment": "test1", "correctness": 0.9, "cost": 0.01, "strategy": "conservative"},
            {"model": "claude", "experiment": "test2", "correctness": 0.6, "cost": 0.50, "strategy": "wasteful"},
        ]
        result = self.analyzer.batch_analyze(entries, "What patterns do you see?")
        assert isinstance(result, str)
        assert len(result) > 10

    def test_analyze_session_from_file(self):
        session_file = (
            Path(__file__).resolve().parent.parent
            / "experiments" / "results" / "reports"
            / "exp_0s36_d3n" / "session.jsonl"
        )
        if not session_file.exists():
            pytest.skip("No session.jsonl available for testing")

        result = self.analyzer.analyze_session(session_file)
        assert isinstance(result, str)
        assert len(result) > 20

    def test_analyze_missing_file_does_not_crash(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False) as f:
            f.write('{"type": "reasoning", "text": "test reasoning"}\n')
            f.write('{"type": "step-finish", "cost": 0.001}\n')
            f.write('{"type": "tool", "tool": "write", "state": {"output": "done"}}\n')
            tmp_path = Path(f.name)

        try:
            result = self.analyzer.analyze_session(tmp_path)
            assert isinstance(result, str)
            assert len(result) > 10
        finally:
            tmp_path.unlink()


class TestLoadSummaryData:
    def test_returns_list(self, tmp_path):
        # Loader behavior should not depend on whichever experiment corpus is generated locally.
        summary_path = tmp_path / "summary.json"
        summary_path.write_text(json.dumps({"entries": [{
            "model": "test-model",
            "cost": 0.01,
            "correctness": 0.9,
        }]}))

        entries = load_summary_data(summary_path)
        assert isinstance(entries, list)
        entry = entries[0]
        assert "model" in entry
        assert "cost" in entry
        assert "correctness" in entry

    def test_missing_file_returns_empty_list(self):
        entries = load_summary_data(Path("/nonexistent/summary.json"))
        assert entries == []
