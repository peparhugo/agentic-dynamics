#!/usr/bin/env python3
"""Binary-resolution probe (D-18) — resolve the model CLIs at container start, fail loudly.

The base image carries the **generic toolchain only** (python / node / git / the sonar
client). The model CLIs (`opencode`, `claude`) are **NOT baked** — they attach through the
D-2 auth mounts. A broken mount or symlink chain must be a *boot-time failure*, not a
surprise mid-run, so this probe is the container's startup assertion (D-18).

Resolution contract (env-overridable; defaults = the D-2 auth set at the container auth
home, which the compose mounts read-only):

    OPENCODE_BIN   — the opencode binary   (default ``$HOME/.opencode/bin/opencode``)
    CLAUDE_BIN     — the claude launcher    (default ``$HOME/.local/bin/claude``)
    HOME           — the container auth home (default ``/home/fleet``)

Checks, in order (each must pass before the next is attempted):

    1. the launcher path exists (for claude: the ``~/.local/bin/claude`` symlink is present);
    2. the chain resolves — ``os.path.realpath`` follows every symlink hop to a REGULAR FILE
       that actually lives inside the container (a host-absolute target that was never
       mounted resolves to a non-existent path and fails here);
    3. the resolved file is executable;
    4. the binary actually runs — ``opencode --version`` / ``claude --version`` exit 0.

Exit codes: 0 = every CLI resolved; 2 = a broken chain (any check above failed). The probe
prints one line per CLI and a final PASS/FAIL verdict; ``--quiet`` suppresses the per-step
detail but never the verdict. The verdict is written to stderr on failure so a dying
container's log carries the reason.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ProbeResult:
    """The outcome of resolving one CLI chain."""

    name: str
    launcher: str
    resolved: str | None = None
    ok: bool = False
    failures: list[str] = field(default_factory=list)
    version: str | None = None


def _default_home() -> str:
    """Return the auth home, preferring the runtime env and falling back to /home/fleet."""
    return os.environ.get("HOME") or "/home/fleet"


def resolve_chain(name: str, launcher: str) -> ProbeResult:
    """Resolve a single CLI chain and run its version probe.

    Args:
        name: Human label for the log line.
        launcher: The path to check (may itself be a symlink).

    Returns:
        A :class:`ProbeResult` describing the pass/fail.
    """
    result = ProbeResult(name=name, launcher=launcher)
    path = Path(launcher)

    # Check 1 — the launcher exists.
    if not path.exists():
        result.failures.append(f"launcher missing: {launcher}")
        return result

    # Check 2 — the symlink chain resolves to a real file inside the container.
    real = Path(os.path.realpath(str(path)))
    if not real.exists():
        result.failures.append(
            f"chain broken: {launcher} -> {path.resolve(strict=False)} -> {real} (target not mounted)"
        )
        return result
    if not real.is_file():
        result.failures.append(f"resolved target is not a regular file: {real}")
        return result
    result.resolved = str(real)

    # Check 3 — the resolved file is executable.
    if not os.access(str(real), os.X_OK):
        result.failures.append(f"target not executable: {real}")
        return result

    # Check 4 — the binary actually runs (a version probe, no network, no auth).
    try:
        probe = subprocess.run(
            [str(real), "--version"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        result.failures.append(f"version probe failed: {exc}")
        return result
    if probe.returncode != 0:
        result.failures.append(
            f"version probe exited {probe.returncode}: {(probe.stderr or '').strip()[:200]}"
        )
        return result

    result.ok = True
    result.version = (probe.stdout or probe.stderr).strip().splitlines()[0] if (
        probe.stdout or probe.stderr
    ) else "ok"
    return result


def probe_all(*, home: str | None = None, opencode_bin: str | None = None,
              claude_bin: str | None = None) -> list[ProbeResult]:
    """Resolve every required CLI and return the results.

    The defaults are the D-2 auth set: ``opencode`` at ``~/.opencode/bin/opencode`` and
    ``claude`` at ``~/.local/bin/claude`` (a symlink into ``~/.local/share/claude``).
    """
    h = home or _default_home()
    opencode = opencode_bin or os.environ.get("OPENCODE_BIN") or f"{h}/.opencode/bin/opencode"
    claude = claude_bin or os.environ.get("CLAUDE_BIN") or f"{h}/.local/bin/claude"
    return [
        resolve_chain("opencode", opencode),
        resolve_chain("claude", claude),
    ]


def main(argv: list[str] | None = None) -> int:
    """Entry point — resolve the CLIs, print a verdict, exit non-zero on a broken chain."""
    parser = argparse.ArgumentParser(description="Resolve the model CLI chains (D-18).")
    parser.add_argument("--home", default=None, help="container auth home (default $HOME or /home/fleet)")
    parser.add_argument("--opencode-bin", default=None, help="opencode binary path")
    parser.add_argument("--claude-bin", default=None, help="claude launcher path")
    parser.add_argument("--quiet", action="store_true", help="print only the verdict")
    args = parser.parse_args(argv)

    results = probe_all(
        home=args.home,
        opencode_bin=args.opencode_bin,
        claude_bin=args.claude_bin,
    )

    all_ok = True
    for r in results:
        if r.ok:
            all_ok = all_ok and True
            if not args.quiet:
                print(f"[ok]     {r.name}: {r.launcher} -> {r.resolved} ({r.version})")
        else:
            all_ok = False
            if not args.quiet:
                print(f"[FAIL]   {r.name}: {r.launcher}")
                for f in r.failures:
                    print(f"         - {f}")

    if all_ok:
        print("BINARY-PROBE: PASS — opencode + claude chains resolve and run.")
        return 0

    print("BINARY-PROBE: FAIL — a CLI chain is broken (see above).", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
