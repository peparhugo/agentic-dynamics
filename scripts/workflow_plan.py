#!/usr/bin/env python3
"""Render a workflow-v1 definition's plan (``workflow plan`` — Wave-3 authoring, a3).

The look-before-you-run surface: render a workflow-v1 definition's step DAG
(``needs`` + ``candidateFrom`` edges), its gates and what each binds, and its
promotion contract, so a human or the AIO Control Agent can see the plan BEFORE
running the workflow.

    agentic-dynamics workflow plan <file>            # human: the text plan
    agentic-dynamics workflow plan <file> --json     # machine: workflow-plan/v1

The plan is a RENDER of the declared shape — it never invents run state (status is
derived from run evidence, never planned) — and it embeds the a1 lint report inline
(``validation.ok`` + findings), so a violating definition still renders so a reader
can see exactly why it is not clean.

Exit codes:
    0   plan rendered.
    2   invalid request — the file is missing/unreadable, is not valid YAML, or is
        NOT a workflow-v1 definition (an ExperimentSpec corpus document is a
        different document kind and has no workflow plan to render).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from workflows import lint_workflow as lw  # noqa: E402
from workflows import plan_workflow as plan  # noqa: E402

EXIT_RENDERED = 0
EXIT_INVALID = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentic-dynamics workflow plan",
        description=(
            "Render a workflow-v1 definition's step DAG, gates, and promotion "
            "contract as a plan a human or the AIO reads before running the workflow."
        ),
    )
    parser.add_argument("file", help="path to a workflow-v1 definition (.yaml/.yml/.json)")
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the machine-readable workflow-plan/v1 document instead of the text plan",
    )
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path = Path(args.file)

    if not path.is_file():
        print(f"workflow plan: file not found: {path}", file=sys.stderr)
        return EXIT_INVALID
    try:
        document = lw.load_document(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        print(f"workflow plan: cannot read {path}: {exc}", file=sys.stderr)
        return EXIT_INVALID

    if not lw.is_workflow_v1_document(document):
        print(
            f"workflow plan: {path} is not a workflow-v1 definition (missing "
            "apiVersion/kind/metadata/spec) — an ExperimentSpec corpus document is a "
            "different document kind and has no workflow plan to render.",
            file=sys.stderr,
        )
        return EXIT_INVALID

    plan_dict = plan.build_plan(document, source=str(path))
    if args.json:
        print(plan.dump_plan_json(plan_dict))
    else:
        print(plan.render_plan_text(plan_dict))
    return EXIT_RENDERED


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
