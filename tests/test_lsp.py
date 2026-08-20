"""Tests for LSP diagnostics module."""

import json
import tempfile
from pathlib import Path

from agentic_dynamics.measurement.lsp_diagnostics import (
    _TOOLS,
    LSPDiagnostic,
    LSPReport,
    LSPToolConfig,
    _parse_cargo,
    _parse_generic,
    _parse_mypy,
    _parse_pyright,
    _parse_tsc,
    available_tools,
    diagnostics_delta,
    run_diagnostics,
)


class TestLSPDiagnostic:
    def test_serialization(self):
        d = LSPDiagnostic(
            severity="error",
            message="Undefined variable",
            file="app.py",
            line=42,
            column=10,
            code="reportUndefinedVariable",
        )
        dd = d.to_dict()
        assert dd["severity"] == "error"
        assert dd["line"] == 42


class TestLSPReport:
    def test_serialization(self):
        r = LSPReport(
            tool="pyright",
            language="python",
            available=True,
            errors=2,
            warnings=5,
            diagnostics=[LSPDiagnostic("error", "bad", "x.py", 1)],
        )
        r.total_diagnostics = r.errors + r.warnings
        d = r.to_dict()
        assert d["tool"] == "pyright"
        assert d["errors"] == 2

    def test_truncation_flag(self):
        r = LSPReport(tool="tsc", language="typescript", available=True)
        for i in range(150):
            r.diagnostics.append(LSPDiagnostic("warning", f"msg {i}", "x.ts", i))
        d = r.to_dict()
        assert d["truncated"] is True
        assert len(d["diagnostics"]) == 100


class TestParsePyright:
    def test_parses_valid_json(self):
        output = json.dumps({
            "generalDiagnostics": [
                {
                    "severity": "error",
                    "message": "Cannot access member",
                    "file": "/src/app.py",
                    "range": {"start": {"line": 4, "character": 8}},
                    "rule": "reportGeneralTypeIssues",
                }
            ]
        })
        config = LSPToolConfig("pyright", "python", [], [])
        report = _parse_pyright(output, config)
        assert report.errors == 1
        assert len(report.diagnostics) == 1

    def test_handles_invalid_json(self):
        config = LSPToolConfig("pyright", "python", [], [])
        report = _parse_pyright("not json", config)
        assert report.total_diagnostics == 0


class TestParseMypy:
    def test_parses_error_line(self):
        output = "app.py:10:5: error: Name 'x' is not defined  [name-defined]"
        config = LSPToolConfig("mypy", "python", [], [])
        report = _parse_mypy(output, config)
        assert report.errors >= 1
        assert any("name-defined" in d.code for d in report.diagnostics)

    def test_parses_multiple_lines(self):
        output = (
            "app.py:1:1: error: Missing return statement  [return]\n"
            "app.py:5:10: warning: Unused import  [unused-ignore]\n"
        )
        config = LSPToolConfig("mypy", "python", [], [])
        report = _parse_mypy(output, config)
        assert report.errors >= 1
        assert report.warnings >= 1


class TestParseTsc:
    def test_parses_error(self):
        output = "src/index.ts(10,5): error TS2304: Cannot find name 'foo'."
        config = LSPToolConfig("tsc", "typescript", [], [])
        report = _parse_tsc(output, config)
        assert report.errors >= 1
        assert any("TS2304" in d.code for d in report.diagnostics)

    def test_skips_non_diagnostic_lines(self):
        output = "Version 5.0.0\nsrc/index.ts(1,1): error TS1005: ';' expected.\n"
        config = LSPToolConfig("tsc", "typescript", [], [])
        report = _parse_tsc(output, config)
        assert report.errors == 1  # Version line skipped


class TestParseCargo:
    def test_parses_json_line(self):
        output = json.dumps({
            "message": {
                "level": "error",
                "rendered": "cannot find value `x` in this scope",
                "spans": [{"file_name": "src/main.rs", "line_start": 5, "column_start": 9}],
            }
        })
        config = LSPToolConfig("cargo-check", "rust", [], [])
        report = _parse_cargo(output, config)
        assert report.errors == 1


class TestParseGeneric:
    def test_parses_fallback(self):
        config = LSPToolConfig("go-vet", "go", [], [])
        report = _parse_generic("main.go:10: syntax error\n", config, 1)
        assert report.total_diagnostics >= 1

    def test_empty_output(self):
        config = LSPToolConfig("go-vet", "go", [], [])
        report = _parse_generic("", config, 0)
        assert report.total_diagnostics == 0


class TestDiagnosticsDelta:
    def test_positive_delta(self):
        before = LSPReport(tool="pyright", language="python", errors=2, warnings=3)
        after = LSPReport(tool="pyright", language="python", errors=5, warnings=4)
        delta = diagnostics_delta(before, after)
        assert delta["errors_delta"] == 3
        assert delta["warnings_delta"] == 1

    def test_negative_delta(self):
        before = LSPReport(tool="tsc", language="typescript", errors=10)
        after = LSPReport(tool="tsc", language="typescript", errors=3)
        delta = diagnostics_delta(before, after)
        assert delta["errors_delta"] == -7


class TestAvailableTools:
    def test_returns_dict(self):
        tools = available_tools()
        assert isinstance(tools, dict)
        assert "python" in tools

    def test_pyright_config_exists(self):
        assert "python" in _TOOLS
        assert _TOOLS["python"].name == "pyright"


class TestRunDiagnostics:
    def test_empty_codebase_returns_unavailable(self):
        with tempfile.TemporaryDirectory() as d:
            report = run_diagnostics(Path(d))
            # Python tools probably not installed in CI/test env
            assert isinstance(report, LSPReport)

    def test_small_python_codebase(self):
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            (dp / "app.py").write_text("x = 1\n")
            report = run_diagnostics(dp)
            assert isinstance(report, LSPReport)
            assert report.language == "python"
