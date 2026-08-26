"""LSP diagnostics — language-server-level code quality analysis.

Runs language-specific diagnostic tools (pyright, tsc, golangci-lint,
rust-analyzer) against the codebase and collects structured diagnostics.

Falls back gracefully when tools are not installed — returns empty
diagnostics rather than failing.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentic_dynamics.core.language import LanguageProfile, detect_language

# ── Data Structures ────────────────────────────────────────────

@dataclass
class LSPDiagnostic:
    """A single diagnostic message from a language server."""

    severity: str  # "error", "warning", "info", "hint"
    message: str
    file: str
    line: int = 0
    column: int = 0
    code: str = ""  # rule code (e.g. "reportUndefinedVariable")

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "message": self.message,
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "code": self.code,
        }


@dataclass
class LSPReport:
    """Aggregated LSP diagnostics for a codebase."""

    tool: str
    language: str
    total_diagnostics: int = 0
    errors: int = 0
    warnings: int = 0
    info: int = 0
    hints: int = 0
    diagnostics: list[LSPDiagnostic] = field(default_factory=list)
    available: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "language": self.language,
            "available": self.available,
            "total_diagnostics": self.total_diagnostics,
            "errors": self.errors,
            "warnings": self.warnings,
            "info": self.info,
            "hints": self.hints,
            "diagnostics": [d.to_dict() for d in self.diagnostics[:100]],
            "truncated": len(self.diagnostics) > 100,
        }


# ── Tool Configurations ────────────────────────────────────────

@dataclass
class LSPToolConfig:
    """Configuration for an LSP diagnostic tool."""

    name: str
    language: str
    check_cmd: list[str]  # command to check if tool is installed
    diag_cmd: list[str]   # command to run diagnostics (with {path} placeholder)


_TOOLS: dict[str, LSPToolConfig] = {
    "python": LSPToolConfig(
        name="pyright",
        language="python",
        check_cmd=["pyright", "--version"],
        diag_cmd=["pyright", "--outputjson", "{path}"],
    ),
    "python_mypy": LSPToolConfig(
        name="mypy",
        language="python",
        # mypy is invoked as a module (``sys.executable -m mypy``) so it runs against the same
        # interpreter the workflow uses — mypy is pip-installable but not on PATH here (design
        # §4 of cap_2a_rerun2_measurement_design.md). ``--show-column-numbers`` is REQUIRED:
        # mypy 2.x's default output omits the column (``file:line: error:``), which
        # ``_parse_mypy`` mis-parses into a "warning" severity for every diagnostic.
        check_cmd=[sys.executable, "-m", "mypy", "--version"],
        diag_cmd=[sys.executable, "-m", "mypy", "--show-column-numbers",
                  "--no-error-summary", "--show-error-codes", "{path}"],
    ),
    "typescript": LSPToolConfig(
        name="tsc",
        language="typescript",
        check_cmd=["tsc", "--version"],
        diag_cmd=["tsc", "--noEmit", "--pretty", "false", "--project", "{path}"],
    ),
    "go": LSPToolConfig(
        name="go-vet",
        language="go",
        check_cmd=["go", "version"],
        diag_cmd=["go", "vet", "./..."],
    ),
    "rust": LSPToolConfig(
        name="cargo-check",
        language="rust",
        check_cmd=["cargo", "--version"],
        diag_cmd=["cargo", "check", "--message-format", "json"],
    ),
}


# ── Diagnostics Runner ─────────────────────────────────────────

def run_diagnostics(
    codebase_path: Path,
    profile: LanguageProfile | None = None,
    *,
    tool_name: str | None = None,
) -> LSPReport:
    """Run LSP diagnostics on a codebase.

    Args:
        codebase_path: Root directory of the codebase.
        profile: Language profile. Auto-detected if None.
        tool_name: Specific tool to use. Auto-selects if None.

    Returns:
        LSPReport with all diagnostics. available=False if no tool found.
    """
    if profile is None:
        profile = detect_language(codebase_path)
    if profile is None:
        return LSPReport(tool="unknown", language="unknown", available=False)

    # Select tool
    if tool_name and tool_name in _TOOLS:
        config = _TOOLS[tool_name]
    else:
        config = _TOOLS.get(profile.name)
        if config is None:
            return LSPReport(
                tool="unknown",
                language=profile.name,
                available=False,
            )

    # Check if tool is available
    if not _tool_available(config):
        return LSPReport(tool=config.name, language=profile.name, available=False)

    # Run diagnostics
    return _run_tool(codebase_path, config, profile)


def _tool_available(config: LSPToolConfig) -> bool:
    """Check if an LSP tool is installed and accessible."""
    try:
        result = subprocess.run(
            config.check_cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _run_tool(
    codebase_path: Path,
    config: LSPToolConfig,
    profile: LanguageProfile,
) -> LSPReport:
    """Execute an LSP diagnostic tool and parse its output."""
    # Build command with path substitution
    cmd = [arg.replace("{path}", str(codebase_path)) for arg in config.diag_cmd]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(codebase_path),
            timeout=120,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return LSPReport(tool=config.name, language=profile.name, available=False)

    output = result.stdout or result.stderr

    if config.name == "pyright":
        return _parse_pyright(output, config)
    elif config.name == "mypy":
        return _parse_mypy(output, config)
    elif config.name == "tsc":
        return _parse_tsc(output, config)
    elif config.name == "cargo-check":
        return _parse_cargo(output, config)
    else:
        return _parse_generic(output, config, result.returncode)


# ── Parsers ─────────────────────────────────────────────────────

def _parse_pyright(output: str, config: LSPToolConfig) -> LSPReport:
    """Parse pyright JSON output."""
    report = LSPReport(tool=config.name, language=config.language, available=True)
    try:
        data = json.loads(output)
        diagnostics = data.get("generalDiagnostics", [])
        for d in diagnostics:
            diag = LSPDiagnostic(
                severity=d.get("severity", "error"),
                message=d.get("message", ""),
                file=d.get("file", ""),
                line=d.get("range", {}).get("start", {}).get("line", 0) + 1,
                column=d.get("range", {}).get("start", {}).get("character", 0) + 1,
                code=d.get("rule", ""),
            )
            report.diagnostics.append(diag)
            _count_severity(report, diag.severity)
    except json.JSONDecodeError:
        pass
    return report


def _parse_mypy(output: str, config: LSPToolConfig) -> LSPReport:
    """Parse mypy text output."""
    report = LSPReport(tool=config.name, language=config.language, available=True)
    for line in output.splitlines():
        # Format: file:line:col: severity: message  [code]
        parts = line.split(":", 3)
        if len(parts) < 4:
            continue
        try:
            file_path = parts[0].strip()
            line_num = int(parts[1].strip())
            col_num = int(parts[2].strip()) if parts[2].strip().isdigit() else 0
        except ValueError:
            continue
        rest = parts[3].strip()
        severity = "error" if "error:" in rest.lower() else "warning"
        code = ""
        if "[" in rest and "]" in rest:
            code_start = rest.rfind("[")
            code_end = rest.rfind("]")
            code = rest[code_start + 1:code_end]
            rest = rest[:code_start].strip()

        diag = LSPDiagnostic(
            severity=severity,
            message=rest,
            file=file_path,
            line=line_num,
            column=col_num,
            code=code,
        )
        report.diagnostics.append(diag)
        _count_severity(report, severity)
    return report


def _parse_tsc(output: str, config: LSPToolConfig) -> LSPReport:
    """Parse tsc output."""
    report = LSPReport(tool=config.name, language=config.language, available=True)
    for line in output.splitlines():
        # Format: file(line,col): error TS####: message
        # or:    file(line,col): error TS####: message
        if "error TS" not in line and "warning TS" not in line:
            continue
        is_error = "error TS" in line
        # Split carefully: file(line,col) then the rest
        # e.g. "src/index.ts(10,5): error TS2304: Cannot find name"
        first_colon = line.find(":")
        if first_colon < 0:
            continue
        file_path = line[:first_colon].strip()
        rest = line[first_colon + 1:].strip()

        # Extract code
        code = ""
        import re
        match = re.search(r"TS\d+", line)
        if match:
            code = match.group(0)
            # Remove code prefix from message
            rest = re.sub(r"error TS\d+\s*:\s*", "", rest)
            rest = re.sub(r"warning TS\d+\s*:\s*", "", rest)

        line_num = 0
        col_num = 0
        # Extract line/col from "file(line,col)"
        if "(" in file_path and ")" in file_path:
            try:
                coords = file_path[file_path.find("(") + 1:file_path.find(")")]
                lc = coords.split(",")
                line_num = int(lc[0])
                col_num = int(lc[1]) if len(lc) > 1 else 0
                file_path = file_path[:file_path.find("(")]
            except (ValueError, IndexError):
                pass

        severity = "error" if is_error else "warning"
        diag = LSPDiagnostic(
            severity=severity,
            message=rest.strip(),
            file=file_path,
            line=line_num,
            column=col_num,
            code=code,
        )
        report.diagnostics.append(diag)
        _count_severity(report, severity)
    return report


def _parse_cargo(output: str, config: LSPToolConfig) -> LSPReport:
    """Parse cargo check JSON output."""
    report = LSPReport(tool=config.name, language=config.language, available=True)
    for line in output.splitlines():
        try:
            data = json.loads(line)
            msg = data.get("message", {})
            spans = msg.get("spans", [])
            primary = spans[0] if spans else {}

            diag = LSPDiagnostic(
                severity=msg.get("level", "error"),
                message=msg.get("rendered", msg.get("message", "")),
                file=primary.get("file_name", ""),
                line=primary.get("line_start", 0),
                column=primary.get("column_start", 0),
                code=msg.get("code", {}).get("code", "") if isinstance(msg.get("code"), dict) else str(msg.get("code", "")),
            )
            report.diagnostics.append(diag)
            _count_severity(report, diag.severity)
        except json.JSONDecodeError:
            continue
    return report


def _parse_generic(output: str, config: LSPToolConfig, return_code: int) -> LSPReport:
    """Parse generic tool output (best-effort)."""
    report = LSPReport(tool=config.name, language=config.language, available=True)
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        severity = "error" if return_code != 0 else "warning"
        diag = LSPDiagnostic(severity=severity, message=line, file="")
        report.diagnostics.append(diag)
        _count_severity(report, severity)
    return report


def _count_severity(report: LSPReport, severity: str) -> None:
    """Increment severity counters."""
    report.total_diagnostics += 1
    if severity == "error":
        report.errors += 1
    elif severity == "warning":
        report.warnings += 1
    elif severity == "info":
        report.info += 1
    elif severity == "hint":
        report.hints += 1


# ── Delta Calculation ──────────────────────────────────────────

def diagnostics_delta(before: LSPReport, after: LSPReport) -> dict[str, Any]:
    """Compute the change in diagnostics between two states.

    Positive deltas = more problems introduced.
    Negative deltas = problems fixed.
    """
    return {
        "errors_delta": after.errors - before.errors,
        "warnings_delta": after.warnings - before.warnings,
        "total_delta": after.total_diagnostics - before.total_diagnostics,
        "summary": (
            f"+{after.errors - before.errors} errors, "
            f"+{after.warnings - before.warnings} warnings"
        ),
    }


def error_identity(diag: LSPDiagnostic) -> tuple[str, int, str]:
    """The ``(file, line, code)`` identity for change-introduced error novelty (design §4).

    Two diagnostics are "the same" iff they share file, line, and rule code — the identity the
    v2 reducer's ``new_lsp_error_count`` uses to decide whether an error in the after-state is
    NEW (absent from the before-state) rather than pre-existing.
    """
    return (diag.file, diag.line, diag.code)


def new_error_count(before: LSPReport, after: LSPReport) -> int:
    """Change-introduced error diagnostics: ``|error ids(after) − error ids(before)|``.

    Error-severity only (warnings/info/hints never count), by the ``(file, line, code)``
    identity rule. A pre-existing error (same identity in both) never counts; an error present
    only in the after-report counts once. Pure and deterministic.
    """
    before_ids = {error_identity(d) for d in before.diagnostics if d.severity == "error"}
    return sum(
        1 for d in after.diagnostics if d.severity == "error" and error_identity(d) not in before_ids
    )


def available_tools() -> dict[str, bool]:
    """Check which LSP tools are available on this system."""
    result: dict[str, bool] = {}
    for name, config in _TOOLS.items():
        result[name] = _tool_available(config)
    return result
