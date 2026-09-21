"""Hermetic unit tests for the local CI preflight (``scripts/ci_preflight.py``).

The preflight is a *runner*: its whole job is to spawn the exact commands CI spawns and classify
the exit codes. The tests below therefore never spawn a real gate — every process execution and
binary resolution is injected through the runner's seams (:func:`ci_preflight.run_gate` takes
``runner``; :func:`ci_preflight.evaluate_preflight` takes ``runner`` + ``which``). That keeps this
module a ~millisecond pure unit test: no subprocesses, no Redis, no git worktrees, no ports.

Deliberately NOT ``fast``-marked: the module it imports pulls in ``subprocess`` (the
fast-path audit's ``FORBIDDEN_IN_FAST`` verbatim). It runs in the full deterministic suite, where
it is cheap; marking it fast would be a lie about what it imports.

The parity tests (1 and 2) pin the gate registry to ``.github/workflows/pytest.yml`` by exact
token list, and the degraded-argv test (10) pins the "thinner box degrades, does not crash"
contract. The rest defend the process contract: exit codes, the one-line-per-gate summary, the
missing-ruff refusal, the ``FINOPS_CELL_ID`` scrub, and the ``ci-preflight/v1`` JSON shape.
"""

from __future__ import annotations

import sys
from io import StringIO
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import ci_preflight as preflight  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────────────────────
# Fixtures — injected fakes (no real process is ever spawned)
# ─────────────────────────────────────────────────────────────────────────────────────────────


class _FakeProc:
    """The minimal ``subprocess.CompletedProcess`` surface the runner reads (``returncode``)."""

    def __init__(self, returncode: int = 0, stdout: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = ""


class FakeRunner:
    """A recording process runner: returns a canned exit code per argv, records every call.

    ``codes`` maps an argv tuple to an exit code (default ``default``). Every call's
    ``(argv, cwd, env)`` is appended to ``calls`` so a test can assert the exact command and the
    exact child environment — which is how the ``FINOPS_CELL_ID`` scrub test observes the seam.
    """

    def __init__(self, codes: dict[tuple[str, ...], int] | None = None, default: int = 0) -> None:
        self.codes = codes or {}
        self.default = default
        self.calls: list[tuple[list[str], str | None, dict[str, str] | None]] = []

    def __call__(self, argv, *, cwd=None, env=None, **_kwargs):
        argv = list(argv)
        self.calls.append((argv, cwd, None if env is None else dict(env)))
        return _FakeProc(self.codes.get(tuple(argv), self.default))

    def call_for(self, gate_id: str) -> tuple[list[str], str | None, dict[str, str] | None]:
        """Return the recorded call whose argv matches the named gate (the gate must have run)."""
        gate = next(g for g in preflight.GATES if g.id == gate_id)
        for argv, cwd, env in self.calls:
            if tuple(argv) == gate.argv:
                return argv, cwd, env
        raise AssertionError(f"gate {gate_id!r} ({gate.argv}) was never run")


def _which_found(name: str) -> str:
    """A ``shutil.which`` fake that resolves every binary (so no probe short-circuits)."""
    return f"/usr/bin/{name}"


def _which_missing(_name: str) -> None:
    """A ``shutil.which`` fake that resolves nothing (the thin-box / missing-tool case)."""
    return None


def _evaluate(runner: FakeRunner, *, which=_which_found, env=None, clean_env=True, gates=None):
    """Run :func:`evaluate_preflight` with fakes and a tiny explicit environment."""
    return preflight.evaluate_preflight(
        preflight.GATES if gates is None else gates,
        runner=runner,
        which=which,
        env={"PATH": "/usr/bin"} if env is None else env,
        clean_env=clean_env,
    )


# ─────────────────────────────────────────────────────────────────────────────────────────────
# 1-2. Registry + parity — the gate set and the exact CI argv
# ─────────────────────────────────────────────────────────────────────────────────────────────


def test_registry_is_exactly_the_five_parity_gates() -> None:
    """The registry carries exactly the five gates, ordered cheap → expensive."""
    ids = [gate.id for gate in preflight.GATES]
    assert ids == ["lint", "surfaces", "docs-drift", "fast-path", "full-suite"]
    # Set equality is the same fact stated independently of order (guards against a rename).
    assert set(ids) == {"lint", "surfaces", "docs-drift", "fast-path", "full-suite"}


def test_gate_argv_matches_the_workflow() -> None:
    """Every gate argv equals the CI command (``.github/workflows/pytest.yml``), token for token.

    Built with a probe that reports BOTH optional plugins available, so the full-suite token
    list is the maximal CI-parity form; the two deliberate omissions (``--splits/--group`` and
    ``-v``) are asserted absent.
    """
    gates = {gate.id: list(gate.argv) for gate in preflight.build_gates(probe=lambda _n: object())}

    assert gates["lint"] == ["ruff", "check", "."]
    assert gates["surfaces"] == ["python3", "scripts/_gen_instructions.py", "--check"]
    assert gates["docs-drift"] == [
        "python3",
        "scripts/scan_docs_drift.py",
        "--check",
        "spec_lifecycle",
        "--fail-on-drift",
    ]
    assert gates["fast-path"] == ["bash", "scripts/test_fast.sh"]

    full = gates["full-suite"]
    assert full == [
        "python3",
        "-m",
        "pytest",
        "tests/",
        "-m",
        "not external",
        "-n",
        "auto",
        "--dist",
        "loadfile",
        "--timeout=600",
    ]
    # The two deliberate omissions (a local run is not sharded; the summary needs no -v).
    assert "--splits" not in full and "--group" not in full and "-v" not in full
    # Every gate names its workflow anchor (auditable parity without leaving the file).
    assert all(
        gate.ci_anchor.startswith(".github/workflows/pytest.yml:") for gate in preflight.GATES
    )


# ─────────────────────────────────────────────────────────────────────────────────────────────
# 3-5. The process contract — exit codes and the per-gate summary
# ─────────────────────────────────────────────────────────────────────────────────────────────


def test_all_pass_exits_zero() -> None:
    """A zero exit from every gate → preflight exit 0, every row PASS."""
    report = _evaluate(FakeRunner(default=0))
    assert report.exit_code == 0
    assert report.status == preflight.PASS
    assert report.passed == len(preflight.GATES)
    assert report.failed == 0
    assert all(result.status == preflight.PASS for result in report.results)


def test_any_failure_exits_nonzero() -> None:
    """One non-zero gate → preflight exit 1, and the summary names the failing gate."""
    runner = FakeRunner(codes={("ruff", "check", "."): 1})
    report = _evaluate(runner)
    assert report.exit_code == 1
    assert report.status == preflight.FAIL
    assert report.failed == 1

    stream = StringIO()
    preflight.render_summary(report, repo_head_sha="deadbeef", ruff_version="0.16.2", stream=stream)
    text = stream.getvalue()
    assert "FAIL  lint" in text
    assert "4 passed, 1 failed" in text


def test_summary_prints_one_pass_fail_line_per_gate() -> None:
    """The summary emits exactly one PASS/FAIL line per gate, each naming the gate id."""
    report = _evaluate(FakeRunner())
    stream = StringIO()
    preflight.render_summary(report, repo_head_sha="deadbeef", ruff_version="0.16.2", stream=stream)

    lines = [ln for ln in stream.getvalue().splitlines() if ln.startswith(("PASS", "FAIL"))]
    assert len(lines) == len(preflight.GATES)
    for gate in preflight.GATES:
        assert any(gate.id in line for line in lines), gate.id


# ─────────────────────────────────────────────────────────────────────────────────────────────
# 6-7. Refusals and environment hygiene
# ─────────────────────────────────────────────────────────────────────────────────────────────


def test_missing_ruff_is_a_gate_failure_with_an_install_hint() -> None:
    """A missing ``ruff`` FAILs the lint gate with the install pin — never a crash or a skip."""
    runner = FakeRunner()
    report = _evaluate(runner, which=_which_missing)

    lint = next(result for result in report.results if result.gate.id == "lint")
    assert lint.status == preflight.FAIL
    assert lint.exit_code == 127
    assert "pip install ruff==0.16.2" in lint.detail
    # It short-circuited WITHOUT spawning: the fake runner was never asked to run ruff.
    assert all(argv != ["ruff", "check", "."] for argv, _cwd, _env in runner.calls)
    # The other four gates still ran (a missing tool must not abort the rest of the preflight).
    assert report.passed == len(preflight.GATES) - 1


def test_cell_id_is_scrubbed_for_pytest_gates_and_restorable() -> None:
    """``FINOPS_CELL_ID`` is dropped for the pytest gates by default and kept by ``--no-clean-env``.

    The two stdlib/lint gates keep it either way (only the pytest children can reach
    ``cell_scope()``); this asymmetry is the documented default.
    """
    base_env = {"PATH": "/usr/bin", "FINOPS_CELL_ID": "wf_world_model_loop"}

    runner = FakeRunner()
    _evaluate(runner, env=base_env, clean_env=True)
    assert preflight._CELL_SCOPE_ENV not in runner.call_for("fast-path")[2]
    assert preflight._CELL_SCOPE_ENV not in runner.call_for("full-suite")[2]
    # Non-pytest gates inherit the variable untouched.
    assert runner.call_for("lint")[2][preflight._CELL_SCOPE_ENV] == "wf_world_model_loop"
    assert runner.call_for("surfaces")[2][preflight._CELL_SCOPE_ENV] == "wf_world_model_loop"
    assert runner.call_for("docs-drift")[2][preflight._CELL_SCOPE_ENV] == "wf_world_model_loop"

    # --no-clean-env restores the inherited environment for the pytest gates too.
    runner_raw = FakeRunner()
    _evaluate(runner_raw, env=base_env, clean_env=False)
    assert runner_raw.call_for("fast-path")[2][preflight._CELL_SCOPE_ENV] == "wf_world_model_loop"
    assert runner_raw.call_for("full-suite")[2][preflight._CELL_SCOPE_ENV] == "wf_world_model_loop"


# ─────────────────────────────────────────────────────────────────────────────────────────────
# 8. The machine report
# ─────────────────────────────────────────────────────────────────────────────────────────────


def test_json_report_is_ci_preflight_v1() -> None:
    """``build_report`` emits the documented ``ci-preflight/v1`` shape."""
    report = _evaluate(FakeRunner())
    document = preflight.build_report(
        report,
        repo_head_sha="abc1234",
        ruff_version="0.16.2",
        generated_at="2026-09-21T00:00:00+00:00",
    )
    assert document["schema"] == "ci-preflight/v1"
    assert document["repo_head_sha"] == "abc1234"
    assert document["ruff_version"] == "0.16.2"
    assert document["generated_at"] == "2026-09-21T00:00:00+00:00"
    assert document["status"] == preflight.PASS
    assert document["passed"] == len(preflight.GATES)
    assert document["failed"] == 0
    assert [row["id"] for row in document["gates"]] == [g.id for g in preflight.GATES]
    for row in document["gates"]:
        assert set(row) == {"id", "name", "argv", "exit_code", "status", "elapsed_s"}
        assert isinstance(row["argv"], list)


# ─────────────────────────────────────────────────────────────────────────────────────────────
# 9-10. Selection and the degraded (thin-box) argv
# ─────────────────────────────────────────────────────────────────────────────────────────────


def test_only_skip_select_a_subset_and_unknown_id_exits_2() -> None:
    """``--only``/``--skip`` filter the registry; an unknown id is a usage error (exit 2)."""
    only = preflight.select_gates(preflight.GATES, only=["lint", "surfaces"])
    assert [g.id for g in only] == ["lint", "surfaces"]

    skipped = preflight.select_gates(preflight.GATES, skip=["full-suite"])
    assert [g.id for g in skipped] == ["lint", "surfaces", "docs-drift", "fast-path"]

    with pytest.raises(preflight.UsageError):
        preflight.select_gates(preflight.GATES, only=["does-not-exist"])

    # main refuses the typo before running anything (exit 2, the usage contract).
    assert preflight.main(["--only", "does-not-exist"]) == 2


def test_full_suite_argv_omits_xdist_when_unavailable() -> None:
    """A thinner box (no plugins) gets the plugin-free argv — degradation, not a crash."""
    thin = preflight.full_suite_argv(probe=lambda _n: None)
    assert thin == ("python3", "-m", "pytest", "tests/", "-m", "not external")
    assert "-n" not in thin and "--dist" not in thin and "--timeout=600" not in thin

    # And the registry built for that box carries the degraded argv (not the maximal one).
    full = next(g for g in preflight.build_gates(probe=lambda _n: None) if g.id == "full-suite")
    assert full.argv == thin
