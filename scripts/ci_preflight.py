#!/usr/bin/env python3
"""Local CI preflight — run the GitHub workflow's gates on a developer box, before a push.

    agentic-dynamics validate preflight
    python3 scripts/ci_preflight.py [--list] [--only <id> ...] [--skip <id> ...]
                                    [--json <path|->] [--quiet] [--no-clean-env]

**What this is.** A zero-model, stdlib-only runner that executes the five gates
``.github/workflows/pytest.yml`` runs on every push, in cheap→expensive order, prints one
``PASS``/``FAIL`` line per gate, and exits non-zero if any gate fails — so a push fails
locally instead of after minutes of waiting for CI. It is a *runner*, never a re-implementation:
every gate invokes the exact command CI invokes, so parity is structural, not a copy that can
drift.

**What this is NOT.** It is deliberately disjoint from the existing ``pipeline ci`` plan
(``experiments/definitions/configs/plans.yaml``): that plan is a Redis-driven phase DAG
(``lint → typecheck → test → build``) with a different mechanism and a different gate set. This
runner spawns subprocesses only — no queue, no mypy, no ``build_data``. It also does not carry
the CI jobs that need docker/a wheel/a network (``verify``, ``workflow-parity``, ``repro``,
``packaging``); "CI parity" here means the five named blocking gates, nothing more.

**The five gates** (ordered cheap→expensive; each is the exact CI argv):

================  ================================================================
id                argv (cwd = repo root)
================  ================================================================
``lint``          ``ruff check .``
``surfaces``      ``python3 scripts/_gen_instructions.py --check``
``docs-drift``    ``python3 scripts/scan_docs_drift.py --check spec_lifecycle --fail-on-drift``
``fast-path``     ``bash scripts/test_fast.sh``
``full-suite``    ``python3 -m pytest tests/ -m "not external" [xdist] [timeout]``
================  ================================================================

**Two deliberate omissions in ``full-suite``** (documented so they are not mistaken for drift):
``--splits/--group`` (a local run is not sharded) and ``-v`` (summary readability). The runner
keeps ``-n auto --dist loadfile`` only when ``pytest-xdist`` is importable and ``--timeout=600``
only when ``pytest-timeout`` is importable, so a thinner box degrades instead of crashing.

**Environment hygiene.** The two pytest gates run with ``FINOPS_CELL_ID`` removed from the child
environment by default, because CI runs in a shell that never sets it and the variable rewrites
the cell scope inside two deterministic-suite tests (measured: ``test_control_room_build_contract``
asserts ``self-wd`` but sees the fleet cell id). Only ``FINOPS_CELL_ID`` is scrubbed — other
``FINOPS_*`` configuration is inherited untouched. ``--no-clean-env`` restores the inherited
environment to reproduce harness-specific behavior. The two stdlib gates (``surfaces``,
``docs-drift``) and ``lint`` keep the variable either way.

**Exit codes.** ``0`` all gates pass · ``1`` one or more gates fail · ``2`` usage error (an id
that matches nothing, or an unreadable ``--json`` target).

**Testability seam.** Process execution and binary resolution are injected:
:func:`run_gate` takes ``runner`` (= :func:`subprocess.run`), and :func:`evaluate_preflight`
takes ``runner`` + ``which`` (= :func:`shutil.which`). Production :func:`main` passes the real
callables; the unit tests pass fakes, so ``tests/test_ci_preflight.py`` never spawns a real
gate, touches Redis, or creates a worktree.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

#: Repo root — every gate runs with this as its cwd, exactly as CI checks out at the root.
ROOT = Path(__file__).resolve().parent.parent

#: The report schema id (a stable machine contract for ``--json``).
SCHEMA = "ci-preflight/v1"

#: Gate status vocabulary. Two values only: a gate either passed or it did not.
PASS = "PASS"
FAIL = "FAIL"

#: The pytest-gate processes that can reach ``cell_scope()``; their children get the
#: harness-only ``FINOPS_CELL_ID`` scrubbed by default (see module docstring).
_CELL_SCOPE_ENV = "FINOPS_CELL_ID"

#: Install hints keyed by the binary a gate requires. A missing binary is a gate FAIL with the
#: hint attached — parity requires the gate to run, so "ruff is not installed" is a red, not a
#: crash and not a silent skip.
INSTALL_HINTS: dict[str, str] = {
    "ruff": "ruff not found on PATH — install the CI pin: pip install ruff==0.16.2",
}

#: The ruff version CI pins (``.github/workflows/pytest.yml:40``). Reported in the header and
#: flagged on mismatch, but never a hard failure on its own (a version mismatch is information,
#: not a verdict).
EXPECTED_RUFF_VERSION = "0.16.2"


@dataclass(frozen=True)
class Gate:
    """One CI-parity gate: a stable id, a human name, and the exact argv to execute.

    ``requires`` names a binary that must resolve on ``PATH`` (``None`` = no probe); ``lint``
    sets it to ``ruff``. ``pytest_gate`` marks the gates whose child environment gets
    ``FINOPS_CELL_ID`` scrubbed by default. ``ci_anchor`` records the workflow lines the argv
    mirrors, so a reader can audit parity without leaving the file.
    """

    id: str
    name: str
    argv: tuple[str, ...]
    ci_anchor: str = ""
    requires: str | None = None
    pytest_gate: bool = False


@dataclass
class GateResult:
    """The outcome of exactly one gate run (or one pre-run refusal)."""

    gate: Gate
    exit_code: int
    status: str
    elapsed_s: float
    detail: str = ""

    @property
    def passed(self) -> bool:
        """True when the gate's process exited zero."""
        return self.status == PASS


@dataclass
class PreflightReport:
    """The aggregate: every gate result plus the run's one-line verdict.

    Carried as a value object so callers (and tests) can inspect the per-gate rows without
    re-parsing the human summary.
    """

    results: list[GateResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        """How many gates passed."""
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        """How many gates failed."""
        return sum(1 for r in self.results if not r.passed)

    @property
    def status(self) -> str:
        """The overall status: ``FAIL`` if any gate failed, else ``PASS``."""
        return FAIL if self.failed else PASS

    @property
    def exit_code(self) -> int:
        """``0`` when every gate passed, ``1`` otherwise (the process contract)."""
        return 0 if self.failed == 0 else 1


class UsageError(Exception):
    """A caller error (an unknown ``--only``/``--skip`` id) → exit ``2``."""


def _probe_module(name: str) -> Any:
    """Return a spec when ``name`` is importable, else ``None`` (never raises).

    ``find_spec`` can raise for a malformed parent package; a plugin probe must degrade to
    "unavailable" rather than crash the runner.
    """
    try:
        return importlib.util.find_spec(name)
    except (ImportError, ValueError):
        return None


def full_suite_argv(*, probe: Callable[[str], Any] = _probe_module) -> tuple[str, ...]:
    """Build the deterministic-suite argv, keeping optional plugin flags only when available.

    CI's shard command is the reference (``.github/workflows/pytest.yml:173-181``); this derives
    it with exactly two deliberate omissions (``--splits/--group`` and ``-v``) and two probed
    additions (``-n auto`` needs ``pytest-xdist``; ``--timeout=600`` needs ``pytest-timeout``).
    The ``probe`` indirection is the test seam for the degraded-argv case.
    """
    argv: list[str] = ["python3", "-m", "pytest", "tests/", "-m", "not external"]
    if probe("xdist") is not None:
        # Parallel workers, one test FILE per worker (file-local fixtures never interleave).
        argv += ["-n", "auto", "--dist", "loadfile"]
    if probe("pytest_timeout") is not None:
        # A hanging test is a failure, never an infinite block (CI's 600s per-test timeout).
        argv += ["--timeout=600"]
    return tuple(argv)


def build_gates(*, probe: Callable[[str], Any] = _probe_module) -> list[Gate]:
    """Materialize the gate registry, ordered cheap→expensive (the exact CI argv per gate).

    The order is load-bearing: a lint or surface drift fails in seconds, before the ~3-minute
    suite, so the cheapest signal surfaces first. ``probe`` is forwarded to
    :func:`full_suite_argv` so the registry can be built for a thin box in tests.
    """
    return [
        Gate(
            id="lint",
            name="Lint (ruff, whole active surface)",
            argv=("ruff", "check", "."),
            ci_anchor=".github/workflows/pytest.yml:38-44",
            requires="ruff",
        ),
        Gate(
            id="surfaces",
            name="Generated instruction surfaces",
            argv=("python3", "scripts/_gen_instructions.py", "--check"),
            ci_anchor=".github/workflows/pytest.yml:66-69",
        ),
        Gate(
            id="docs-drift",
            name="Docs drift (spec lifecycle)",
            argv=(
                "python3",
                "scripts/scan_docs_drift.py",
                "--check",
                "spec_lifecycle",
                "--fail-on-drift",
            ),
            ci_anchor=".github/workflows/pytest.yml:71-81",
        ),
        Gate(
            id="fast-path",
            name="Fast path",
            argv=("bash", "scripts/test_fast.sh"),
            ci_anchor=".github/workflows/pytest.yml:106-118",
            pytest_gate=True,
        ),
        Gate(
            id="full-suite",
            name="Deterministic suite (external excluded)",
            argv=full_suite_argv(probe=probe),
            ci_anchor=".github/workflows/pytest.yml:173-181",
            pytest_gate=True,
        ),
    ]


#: The default registry (all plugin probes available on this box; ``build_gates`` degrades).
GATES: list[Gate] = build_gates()


def select_gates(
    gates: Sequence[Gate],
    *,
    only: Sequence[str] = (),
    skip: Sequence[str] = (),
) -> list[Gate]:
    """Filter the registry by ``--only``/``--skip`` (repeatable), preserving the base order.

    An id that matches no gate is a :class:`UsageError` (exit 2) — a typo silently running a
    different subset than the caller asked for is worse than a loud refusal.
    """
    known = {g.id for g in gates}
    unknown = sorted((set(only) | set(skip)) - known)
    if unknown:
        raise UsageError(
            f"unknown gate id(s): {', '.join(unknown)}; known: {', '.join(sorted(known))}"
        )
    selected = [g for g in gates if (not only or g.id in only) and g.id not in skip]
    return selected


def _child_env(base: Mapping | None, *, gate: Gate, clean_env: bool) -> dict[str, str] | None:
    """Return the child environment for ``gate`` (``None`` is a legal "inherit" value).

    ``base`` is the resolved parent environment. When the gate is a pytest gate and ``clean_env``
    is on, ``FINOPS_CELL_ID`` is dropped — CI's shell never sets it and it rewrites the cell
    scope inside two deterministic tests. Every other variable (including other ``FINOPS_*``)
    is inherited untouched.
    """
    if base is None:
        return None
    env = dict(base)
    if clean_env and gate.pytest_gate:
        env.pop(_CELL_SCOPE_ENV, None)
    return env


def run_gate(
    gate: Gate,
    *,
    runner: Callable[..., Any] = subprocess.run,
    env: dict[str, str] | None = None,
) -> GateResult:
    """Execute one gate's argv and classify the result. Never raises on a missing binary.

    The child inherits the parent's stdout/stderr (``runner`` captures nothing), so a long suite
    is observable while it runs. A ``FileNotFoundError``/``OSError`` is a FAIL with the reason
    attached — the runner must be able to report a broken environment, not crash on it.
    """
    start = time.monotonic()
    detail = ""
    try:
        proc = runner(list(gate.argv), cwd=str(ROOT), env=env)
        exit_code = int(getattr(proc, "returncode", 1))
    except FileNotFoundError as exc:
        # The binary vanished between the ``which`` probe and the spawn (or no probe ran).
        exit_code = 127
        detail = f"command not found: {gate.argv[0]} ({exc})"
    except OSError as exc:  # e.g. permission denied — report, never abort the whole preflight
        exit_code = 126
        detail = f"could not execute {gate.argv[0]}: {exc}"
    elapsed = time.monotonic() - start
    status = PASS if exit_code == 0 else FAIL
    return GateResult(
        gate=gate, exit_code=exit_code, status=status, elapsed_s=elapsed, detail=detail
    )


def evaluate_preflight(
    gates: Sequence[Gate] = GATES,
    *,
    runner: Callable[..., Any] = subprocess.run,
    which: Callable[[str], str | None] = shutil.which,
    env: Mapping | None = None,
    clean_env: bool = True,
) -> PreflightReport:
    """Run every selected gate in order and return the aggregate report.

    A gate whose ``requires`` binary is absent is FAILed *without* spawning, with the install
    hint attached — parity is the point, so a missing tool must be a red, never a skip. The
    environment is resolved once and each gate receives its own child copy (see
    :func:`_child_env`); the base environment is never mutated.
    """
    base_env: dict[str, str] | None = None
    if env is not None:
        base_env = dict(env)
    elif os.environ:
        base_env = dict(os.environ)

    results: list[GateResult] = []
    for gate in gates:
        if gate.requires and which(gate.requires) is None:
            hint = INSTALL_HINTS.get(gate.requires, f"{gate.requires} not found on PATH")
            results.append(
                GateResult(gate=gate, exit_code=127, status=FAIL, elapsed_s=0.0, detail=hint)
            )
            continue
        child_env = _child_env(base_env, gate=gate, clean_env=clean_env)
        results.append(run_gate(gate, runner=runner, env=child_env))
    return PreflightReport(results=results)


def _repo_head_sha() -> str:
    """Best-effort ``git rev-parse HEAD``; ``unknown`` when unavailable (never fatal)."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
    except OSError:
        return "unknown"
    if proc.returncode != 0:
        return "unknown"
    return proc.stdout.strip() or "unknown"


def _detect_ruff_version(*, which: Callable[[str], str | None] = shutil.which) -> str:
    """Best-effort ``ruff --version``; ``unknown`` when ruff is absent (never fatal).

    Reported in the header so a version mismatch against the CI pin is visible; a mismatch is
    never a hard failure by itself.
    """
    if which("ruff") is None:
        return "unknown"
    try:
        proc = subprocess.run(["ruff", "--version"], capture_output=True, text=True)
    except OSError:
        return "unknown"
    if proc.returncode != 0:
        return "unknown"
    # ``ruff --version`` prints ``ruff 0.16.2``; keep the bare version token.
    text = (proc.stdout or "").strip()
    return text.split()[-1] if text else "unknown"


def build_report(
    report: PreflightReport,
    *,
    repo_head_sha: str,
    ruff_version: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Render the aggregate as the ``ci-preflight/v1`` machine document (pure, deterministic).

    ``generated_at`` is injectable so the document is reproducible in tests; production passes
    ``None`` and a UTC timestamp is stamped in.
    """
    return {
        "schema": SCHEMA,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "repo_head_sha": repo_head_sha,
        "ruff_version": ruff_version,
        "gates": [
            {
                "id": r.gate.id,
                "name": r.gate.name,
                "argv": list(r.gate.argv),
                "exit_code": r.exit_code,
                "status": r.status,
                "elapsed_s": round(r.elapsed_s, 3),
            }
            for r in report.results
        ],
        "passed": report.passed,
        "failed": report.failed,
        "status": report.status,
    }


def render_summary(
    report: PreflightReport,
    *,
    repo_head_sha: str,
    ruff_version: str,
    quiet: bool = False,
    stream: Any = None,
) -> None:
    """Print the human summary: a short header, one PASS/FAIL line per gate, and the verdict.

    ``--quiet`` prints only the final ``N passed, M failed`` line. The PASS/FAIL line format is
    ``<STATUS>  <id>  <elapsed>s`` — exactly one such line per gate, so a reader (or a test)
    can count the gates from the output alone.
    """
    out = sys.stdout if stream is None else stream
    if not quiet:
        print(f"ci-preflight: {ROOT}", file=out)
        print(f"  repo HEAD   {repo_head_sha}", file=out)
        ruff_note = ""
        if ruff_version not in ("unknown", EXPECTED_RUFF_VERSION):
            ruff_note = f"  (CI pins {EXPECTED_RUFF_VERSION})"
        print(f"  ruff        {ruff_version}{ruff_note}", file=out)
        print("", file=out)
        for result in report.results:
            line = f"{result.status:<4}  {result.gate.id:<11} {result.gate.name}  ({result.elapsed_s:.1f}s)"
            if result.detail:
                line += f"  — {result.detail}"
            print(line, file=out)
        print("", file=out)
    print(f"{report.passed} passed, {report.failed} failed", file=out)


def run_preflight(
    gates: Sequence[Gate] = GATES,
    *,
    runner: Callable[..., Any] = subprocess.run,
    which: Callable[[str], str | None] = shutil.which,
    env: Mapping | None = None,
    clean_env: bool = True,
    quiet: bool = False,
    repo_head_sha: str | None = None,
    ruff_version: str | None = None,
    stream: Any = None,
) -> int:
    """Run the selected gates, print the summary, and return the process exit code.

    This is the injected seam the unit tests use: ``runner`` and ``which`` are passed through to
    :func:`evaluate_preflight`, and ``repo_head_sha``/``ruff_version`` are injectable so a test
    never shells out for metadata. Production :func:`main` passes the real callables and lets the
    metadata probes run.
    """
    report = evaluate_preflight(gates, runner=runner, which=which, env=env, clean_env=clean_env)
    render_summary(
        report,
        repo_head_sha=repo_head_sha if repo_head_sha is not None else _repo_head_sha(),
        ruff_version=ruff_version
        if ruff_version is not None
        else _detect_ruff_version(which=which),
        quiet=quiet,
        stream=stream,
    )
    return report.exit_code


def build_parser() -> argparse.ArgumentParser:
    """The CLI parser (mirrors the module docstring's usage block)."""
    parser = argparse.ArgumentParser(
        prog="agentic-dynamics validate preflight",
        description=(
            "Run the five CI-parity gates locally (lint, generated surfaces, docs drift, fast "
            "path, deterministic suite) and exit non-zero if any fails."
        ),
    )
    parser.add_argument("--list", action="store_true", help="print the gate registry and exit")
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="ID",
        help="run only this gate id (repeatable; unknown id exits 2)",
    )
    parser.add_argument(
        "--skip",
        action="append",
        default=[],
        metavar="ID",
        help="skip this gate id (repeatable; unknown id exits 2)",
    )
    parser.add_argument(
        "--json",
        default=None,
        metavar="PATH",
        help="write the ci-preflight/v1 report to PATH ('-' = stdout)",
    )
    parser.add_argument("--quiet", action="store_true", help="print only the final summary line")
    parser.add_argument(
        "--no-clean-env",
        action="store_true",
        help="keep the inherited environment for the pytest gates (default: scrub FINOPS_CELL_ID)",
    )
    return parser


def _print_registry(gates: Sequence[Gate]) -> None:
    """``--list``: one line per gate, in run order (the registry as data)."""
    print(f"{len(gates)} gates (cheap -> expensive):")
    for gate in gates:
        extra = f"  [requires {gate.requires}]" if gate.requires else ""
        print(f"  {gate.id:<11} {gate.name}{extra}")
        print(f"              {' '.join(gate.argv)}")
        if gate.ci_anchor:
            print(f"              CI anchor: {gate.ci_anchor}")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: parse args, select gates, run, and emit the requested report form.

    Exit ``0`` all pass · ``1`` one or more fail · ``2`` a usage error (unknown gate id or an
    unwritable ``--json`` path).
    """
    args = build_parser().parse_args(argv)

    if args.list:
        _print_registry(GATES)
        return 0

    try:
        gates = select_gates(GATES, only=args.only, skip=args.skip)
    except UsageError as exc:
        print(f"ci-preflight: {exc}", file=sys.stderr)
        return 2

    report_holder: dict[str, Any] = {}

    # Wrap the real seam so the JSON report can carry the metadata the run already computed.
    def _run() -> int:
        report = evaluate_preflight(
            gates,
            runner=subprocess.run,
            which=shutil.which,
            env=os.environ,
            clean_env=not args.no_clean_env,
        )
        report_holder["report"] = report
        report_holder["repo_head_sha"] = _repo_head_sha()
        report_holder["ruff_version"] = _detect_ruff_version()
        render_summary(
            report,
            repo_head_sha=report_holder["repo_head_sha"],
            ruff_version=report_holder["ruff_version"],
            quiet=args.quiet,
        )
        return report.exit_code

    code = _run()

    if args.json:
        document = build_report(
            report_holder["report"],
            repo_head_sha=report_holder["repo_head_sha"],
            ruff_version=report_holder["ruff_version"],
        )
        payload = json.dumps(document, indent=2, ensure_ascii=False)
        if args.json == "-":
            print(payload)
        else:
            try:
                Path(args.json).write_text(payload + "\n", encoding="utf-8")
            except OSError as exc:
                print(f"ci-preflight: cannot write {args.json}: {exc}", file=sys.stderr)
                return 2

    return code


if __name__ == "__main__":
    raise SystemExit(main())
