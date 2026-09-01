"""Independent test execution — run a language's test suite and report pass/fail.

Single source of truth for "run the tests ourselves." Shared by
``scripts/verify_tests.py`` (batch verification of story cells) and
``src/instrument/workflow_runner.py`` (the ``verify`` phase of an ``agent_task``
workflow). ``test_executed_success`` is measured by the harness, never taken from the
model's self-reported ``tests_passed``/``tests_total``.

Runners, keyed off ``language.py``:
  - python     → ``python3 -m pytest``
  - typescript → ``node <worktree>/node_modules/jest/bin/jest.js --ci --silent``
  - go / rust  → ``go test ./...`` / ``cargo test --quiet``
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

TIMEOUT = 300


def resolve_node() -> str | None:
    """Locate a node binary (nvm installs are not on PATH by default)."""
    node = shutil.which("node")
    if node:
        return node
    nvm_root = Path.home() / ".nvm" / "versions" / "node"
    if nvm_root.is_dir():
        for c in sorted(nvm_root.glob("*/bin/node"), reverse=True):
            if c.is_file() and os.access(c, os.X_OK):
                return str(c)
    return None


def _int_from(pattern: str, text: str) -> int:
    m = re.search(pattern, text)
    return int(m.group(1)) if m else 0


def _run_pytest(workdir: Path, timeout: int, *, target: str | list[str] | None = None) -> dict:
    """Run pytest over ``target`` (default: the whole worktree), excluding stale generated data.

    ``target`` is the scoped-mode selector (test_suite_speed p2): a spec's test phase passes
    the spec-declared test target (the phase's ``tests:`` field — e.g. ``tests/test_<spec>.py``)
    so the phase runs ITS tests, never the whole multi-thousand-test tree. ``None`` keeps the
    historical whole-tree scope.
    """
    if target:
        targets = [target] if isinstance(target, str) else list(target)
    else:
        targets = ["."]
    cmd = [
        sys.executable, "-m", "pytest", "-q", "--tb=short", *targets,
        # Stale generated artifacts under experiments/results must never be collected.
        "--ignore=experiments/results", "--ignore=experiments/codebases",
    ]
    try:
        proc = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"runner": "pytest", "passed": 0, "failed": 0, "errors": 1, "total": 0,
                "pass_rate": 0.0, "tail": f"timeout after {timeout}s"}
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    passed = _int_from(r"(\d+)\s+passed", output)
    failed = _int_from(r"(\d+)\s+failed", output)
    errors = _int_from(r"(\d+)\s+error", output)
    total = passed + failed + errors
    return {"runner": "pytest", "passed": passed, "failed": failed, "errors": errors,
            "total": total, "pass_rate": round(passed / total, 4) if total else 0.0,
            "tail": output[-600:]}


def _run_jest(workdir: Path, node: str, timeout: int) -> dict:
    jest_bin = workdir / "node_modules" / "jest" / "bin" / "jest.js"
    if not jest_bin.is_file():
        return {"runner": "jest", "passed": 0, "failed": 0, "errors": 1, "total": 0,
                "pass_rate": 0.0, "tail": "jest.js not found in node_modules"}
    try:
        proc = subprocess.run(
            [node, str(jest_bin), "--ci", "--silent"],
            cwd=workdir, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"runner": "jest", "passed": 0, "failed": 0, "errors": 1, "total": 0,
                "pass_rate": 0.0, "tail": f"timeout after {timeout}s"}
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    m = re.search(r"Tests:\s+(\d+)\s+failed,\s+(\d+)\s+passed,\s+(\d+)\s+total", output)
    if m:
        failed, passed, total = int(m.group(1)), int(m.group(2)), int(m.group(3))
        errors = 0
    else:
        m2 = re.search(r"Tests:\s+(\d+)\s+passed,\s+(\d+)\s+total", output)
        if m2:
            passed, total = int(m2.group(1)), int(m2.group(2))
            failed, errors = 0, 0
        else:
            passed = total = 0
            failed = errors = 1
    return {"runner": "jest", "passed": passed, "failed": failed, "errors": errors,
            "total": total, "pass_rate": round(passed / total, 4) if total else 0.0,
            "tail": output[-600:]}


def _run_framework(workdir: Path, cmd: list[str], runner: str, timeout: int) -> dict:
    try:
        proc = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"runner": runner, "passed": 0, "failed": 0, "errors": 1, "total": 0,
                "pass_rate": 0.0, "tail": f"timeout after {timeout}s"}
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    passed = _int_from(r"(\d+)\s+passed", output)
    failed = _int_from(r"(\d+)\s+failed", output)
    total = passed + failed
    errors = 0 if (proc.returncode == 0 or total) else 1
    return {"runner": runner, "passed": passed, "failed": failed, "errors": errors,
            "total": total, "pass_rate": round(passed / total, 4) if total else 0.0,
            "tail": output[-600:]}


def run_suite(
    workdir: Path,
    language: str,
    *,
    node: str | None = None,
    timeout: int = TIMEOUT,
    target: str | list[str] | None = None,
) -> dict:
    """Run the appropriate test suite for ``language``; return a normalized result.

    Result keys: ``runner, passed, failed, errors, total, pass_rate, tail``. The caller
    derives ``test_executed_success = total > 0 and failed == 0 and errors == 0``.

    ``target`` (python only) is the scoped-mode selector: run the given file(s)/node ids
    instead of the whole tree — a spec's test phase targets its own tests
    (``tests/test_<spec>.py`` / the phase's ``tests:`` field), never the whole suite.
    """
    if language == "typescript":
        node = node or resolve_node()
        if node is None:
            return {"runner": "jest", "passed": 0, "failed": 0, "errors": 1, "total": 0,
                    "pass_rate": 0.0, "tail": "node binary not found"}
        return _run_jest(workdir, node, timeout)
    if language == "go":
        return _run_framework(workdir, ["go", "test", "./..."], "go test", timeout)
    if language == "rust":
        return _run_framework(workdir, ["cargo", "test", "--quiet"], "cargo test", timeout)
    return _run_pytest(workdir, timeout, target=target)


def suite_succeeded(result: dict) -> bool:
    """Derive the verified-success boolean from a ``run_suite`` result."""
    return bool(result.get("total", 0) > 0 and result.get("failed", 0) == 0 and result.get("errors", 0) == 0)
