#!/usr/bin/env python3
"""Lint a workflow-v1 definition (``workflow lint`` — Wave-3 authoring, a3).

The CI-able surface of the a1 linter: run ``workflows/lint_workflow.py`` against ONE
workflow-v1 definition file and report its named findings.

    agentic-dynamics workflow lint <file>          # human: findings to stdout, silence on clean
    agentic-dynamics workflow lint <file> --json   # machine: the workflow-lint/v1 report

Exit codes (the CI contract — a caller branches on the code, never on parsing prose):
    0   clean — the definition validates against the workflow-v1 schema AND every a1
        semantic rule; default mode prints nothing (silence is the pass signal).
    1   findings — at least one named violation; each finding is one ``code: message``
        line (human) or a ``workflow-lint/v1`` JSON report (``--json``).
    2   invalid request — the file is missing/unreadable, is not valid YAML, or is
        NOT a workflow-v1 definition (an ExperimentSpec corpus document is a
        different kind and is never linted as a workflow). A non-workflow file can
        never "pass" lint — that would let CI certify nothing.

The linter targets new/touched workflow-v1 documents only; the historical
ExperimentSpec corpus under ``workflows/repository|operations|research`` is a
different document kind and is deliberately not expected to pass.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from workflows import lint_workflow as lw  # noqa: E402

LINT_SCHEMA_ID = "workflow-lint/v1"

EXIT_CLEAN = 0
EXIT_FINDINGS = 1
EXIT_INVALID = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentic-dynamics workflow lint",
        description=(
            "Lint a workflow-v1 definition against the authoring contract: the "
            "workflow-v1 schema AND the a1 semantic rules (authored status, mutating "
            "without verification, promotion without gates, unbound gates, "
            "prompt-as-evidence)."
        ),
    )
    parser.add_argument("file", help="path to a workflow-v1 definition (.yaml/.yml/.json)")
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the machine-readable workflow-lint/v1 report instead of human lines",
    )
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path = Path(args.file)

    if not path.is_file():
        return _invalid(f"file not found: {path}", args.json)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return _invalid(f"cannot read {path}: {exc}", args.json)
    try:
        document = lw.load_document(text)
    except yaml.YAMLError as exc:
        return _invalid(f"{path} is not valid YAML: {exc}", args.json)

    if not lw.is_workflow_v1_document(document):
        return _invalid(
            f"{path} is not a workflow-v1 definition (missing apiVersion/kind/metadata/"
            "spec). An ExperimentSpec corpus document is a different document kind and "
            "is never linted as a workflow — lint a NEW or touched workflow-v1 file.",
            args.json,
        )

    report = lw.lint(document)
    if args.json:
        print(
            json.dumps(
                {
                    "schema": LINT_SCHEMA_ID,
                    "source": str(path),
                    "document_kind": "workflow-v1",
                    "ok": report.ok,
                    "findings": [f.as_dict() for f in report.findings],
                },
                indent=2,
                sort_keys=False,
            )
        )
        return EXIT_CLEAN if report.ok else EXIT_FINDINGS

    for finding in report.findings:
        print(f"{finding.code}: {finding.message} [{finding.path}]")
    return EXIT_CLEAN if report.ok else EXIT_FINDINGS


def _invalid(message: str, as_json: bool) -> int:
    if as_json:
        print(
            json.dumps(
                {"schema": LINT_SCHEMA_ID, "ok": False, "error": message},
                indent=2,
                sort_keys=False,
            )
        )
    else:
        print(f"workflow lint: {message}", file=sys.stderr)
    return EXIT_INVALID


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
