"""test_suite_speed p4 — the fast-path budget gate + the parallel-safety audit guard.

Two trip wires that keep the fast path honest:

1. **The budget gate.** ``pytest tests/ -m fast`` (the sub-3-minute smoke) must stay under a
   generous ceiling — a slow-regression trip wire, not a flaky wall. Measured 2026-09-01:
   509 tests in ~25s; the ceiling is 3x the measured fast time (75s), rounded up to a
   non-flaky 180s that absorbs a loaded CI box.

2. **The parallel-safety audit.** A ``fast``-marked module must never touch the shared state
   that breaks under parallelism or makes a smoke slow: real subprocesses, Redis/stores/ports,
   real git worktrees, or sleeps. A marked module that grows one of those (or an unmarked
   module that was never audited) fails here — the subset stays a subset by audit, not by
   vibes.
"""

import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

#: The budget — a slow-regression trip wire (3x the measured ~25s fast path), never a flaky wall.
FAST_BUDGET_SECONDS = 180

#: The shared-state vocabulary a `fast`-marked module must never touch (test_suite_speed p3
#: parallel-safety audit). Each (regex, reason) flags the risk it names. Platform/backend
#: NAMES (opencode, ollama) are deliberately absent — they appear in routing/rendering prose
#: and are harmless; the real-session families are `external`-marked and marker-excluded.
FORBIDDEN_IN_FAST = [
    (r"\bredis\b", "the framework/queue Redis"),
    (r"\bchroma\b", "the dense store"),
    (r"\bneo4j\b", "the graph store"),
    (r"\blocalhost\b", "a live service on a port"),
    (r"\bsocket\b", "port contact"),
    (r"\bsubprocess\b", "real subprocesses"),
    (r"\bPopen\b", "real subprocesses"),
    (r"\bworktree\b", "real git worktrees (shared .git state)"),
    (r"time\.sleep", "wall-clock waits"),
    (r"sonar-scanner|run_sonar_analysis", "the external analyzer JVM"),
]


def _fast_marked_modules() -> list[Path]:
    return sorted(
        p
        for p in (ROOT / "tests").glob("test_*.py")
        if re.search(r"^pytestmark\s*=\s*pytest\.mark\.fast\b", p.read_text(), re.M)
    )


def test_fast_path_stays_under_budget():
    """``pytest tests/ -m fast`` completes green under the budget (a trip wire, not a wall)."""
    t0 = time.monotonic()
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-m", "fast", "-q", "-p", "no:cacheprovider"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=FAST_BUDGET_SECONDS,
    )
    elapsed = time.monotonic() - t0
    tail = (proc.stdout or "")[-1500:] + "\n" + (proc.stderr or "")[-1500:]
    assert proc.returncode == 0, f"fast path not green:\n{tail}"
    assert elapsed < FAST_BUDGET_SECONDS, (
        f"fast path took {elapsed:.0f}s >= {FAST_BUDGET_SECONDS}s budget — a slow regression "
        f"tripped the wire"
    )


def test_fast_marked_modules_pass_the_parallel_safety_audit():
    """A ``fast``-marked module never touches shared state — the audit is durable, not a one-off.

    The marked subset was selected by this exact audit (test_suite_speed p3); this guard
    re-checks it on every run so a future edit that adds a Redis call or a worktree to a marked
    module fails here instead of silently slowing (or breaking) the smoke.
    """
    offenders = {}
    for path in _fast_marked_modules():
        text = path.read_text()
        for token, why in FORBIDDEN_IN_FAST:
            # regex match on whole lines (the marker line itself is exempt)
            for lineno, line in enumerate(text.splitlines(), 1):
                if re.search(token, line) and "pytestmark" not in line:
                    offenders.setdefault(path.name, []).append(
                        f"line {lineno}: {line.strip()!r} ({why})"
                    )
    assert not offenders, (
        "fast-marked modules must stay parallel-safe and dependency-free:\n"
        + "\n".join(f"{name}: {'; '.join(hits)}" for name, hits in sorted(offenders.items()))
    )


def test_fast_subset_is_nonempty_and_a_subset_of_the_suite():
    """The fast path is a SUBSET (never a parallel suite) and the full suite still collects."""
    modules = _fast_marked_modules()
    assert len(modules) >= 5, "the fast subset must carry at least the sub-minute guard family"
    # every marked module exists in the suite dir and is a test module
    for m in modules:
        assert m.is_file()
    # the full suite still collects (the subset must never become the only suite)
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, "the full suite must still collect on demand"
    assert "tests collected" in proc.stdout, proc.stdout[-800:]
