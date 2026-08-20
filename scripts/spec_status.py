"""Regenerate the derived spec lifecycle index: experiments/specs/{index.json,STATUS.md}.

Usage:
    python scripts/spec_status.py                 # regenerate both artifacts
    python scripts/spec_status.py --print         # ... and print the STATUS.md table
    python scripts/spec_status.py --json          # ... and print index.json to stdout
    python scripts/spec_status.py --dry-run       # derive + report, write nothing
    python scripts/spec_status.py --spec <name>   # report one spec's row after refreshing

Thin by design: every derivation lives in :mod:`instrument.spec_status` so it stays
unit-testable without a filesystem CLI in the way. This file only parses flags, calls the
module, and reports.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401


from agentic_dynamics.experiment.spec_status import (  # noqa: E402
    build_index,
    collect_entries,
    refresh_spec_status,
    render_status_md,
)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Derive experiments/specs/index.json + STATUS.md from the spec corpus "
        "and the workflow run ledgers."
    )
    ap.add_argument(
        "--root",
        default=str(ROOT),
        help="repo root to scan (default: this checkout) — useful for a worktree",
    )
    ap.add_argument(
        "--spec",
        default=None,
        help="report this spec's derived row after the refresh (does not filter the "
        "write: both artifacts are always regenerated in full)",
    )
    ap.add_argument("--dry-run", action="store_true", help="derive and report; write nothing")
    ap.add_argument("--json", action="store_true", help="print index.json to stdout")
    ap.add_argument("--print", dest="print_table", action="store_true",
                    help="print STATUS.md to stdout")
    args = ap.parse_args()

    root = Path(args.root).resolve()

    if args.dry_run:
        # Same derivation, no writes — so a caller can inspect what *would* land.
        entries = collect_entries(root=root)
        if args.json:
            print(json.dumps(build_index(entries), indent=2))
        if args.print_table:
            print(render_status_md(entries))
        print(f"[dry-run] {len(entries)} spec(s) derived; nothing written", file=sys.stderr)
        _report_one(entries, args.spec)
        return 0

    report = refresh_spec_status(args.spec, root=root)

    if args.json:
        print(report.index_path.read_text())
    if args.print_table:
        print(report.status_path.read_text())

    print(f"{report.n_specs} spec(s) indexed", file=sys.stderr)
    print(f"index:  {report.index_path}", file=sys.stderr)
    print(f"status: {report.status_path}", file=sys.stderr)
    _report_one(report.entries, args.spec)
    return 0


def _report_one(entries: list, spec_name: str | None) -> None:
    """Print a single spec's derived row to stderr, when ``--spec`` was given."""
    if not spec_name:
        return
    match = next((e for e in entries if e.name == spec_name), None)
    if match is None:
        print(f"warning: spec {spec_name!r} not found in the corpus", file=sys.stderr)
        return
    print(json.dumps(match.to_dict(), indent=2), file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
