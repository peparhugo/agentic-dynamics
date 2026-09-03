#!/usr/bin/env python3
"""Scaffold a new workflow-v1 definition (``workflow new`` — Wave-3 authoring, a3).

The authoring entry point: a NEW workflow is scaffolded, never copied from a
historical YAML. ``workflow new <name>`` scaffolds a minimal valid workflow from
``workflows/examples/minimal-agent-workflow.yaml`` into
``workflows/repository/<name>.yaml`` — one agent step produces a candidate, a test
gate is bound to it, promotion requires the gate — and validates the file against
the workflow-v1 schema AND the a1 linter AS IT IS WRITTEN.

    agentic-dynamics workflow new <name>
    agentic-dynamics workflow new <name> --output-dir <dir>     # tests / custom homes
    agentic-dynamics workflow new <name> --template <file>      # scaffold from another workflow-v1

Exit codes:
    0   scaffolded and validated (the path is printed).
    2   refused — invalid name, template problem, target already exists, or the
        composed workflow is not schema-valid + linter-clean (nothing is written).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from workflows import scaffold_workflow as scaffold  # noqa: E402

EXIT_CREATED = 0
EXIT_REFUSED = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentic-dynamics workflow new",
        description=(
            "Scaffold a minimal valid workflow-v1 definition from the minimal-agent "
            "example into workflows/repository/<name>.yaml, validated against the "
            "schema + linter as it is written."
        ),
    )
    parser.add_argument("name", help="workflow slug — must match ^[a-z][a-z0-9_-]*$")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="target directory (default: workflows/repository/ under the repo root)",
    )
    parser.add_argument(
        "--template",
        default=None,
        help="workflow-v1 template file (default: workflows/examples/minimal-agent-workflow.yaml)",
    )
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        path = scaffold.scaffold(args.name, output_dir=args.output_dir, template_path=args.template)
    except scaffold.ScaffoldError as exc:
        print(f"workflow new: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    print(f"workflow new: wrote {path} (schema-valid, linter-clean)")
    return EXIT_CREATED


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
