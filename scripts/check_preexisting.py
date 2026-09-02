#!/usr/bin/env python3
"""The pre-existing-drift guard CLI (``control_db_evidence`` e5) — "pre-existing" must be PROVEN.

    agentic-dynamics validate preexisting --test <node id> --base <merge-base sha> [--head <sha>]
    agentic-dynamics validate preexisting --test <node id> --base <merge-base sha> --json
    agentic-dynamics validate preexisting --doc <review-doc.md> [--json]

"Pre-existing" must be proven, not claimed. Given a failing pytest node and a merge-base sha,
this command checks out the base into a temporary git worktree, runs the SAME node there, and
compares the base outcome against the head outcome. Deterministic, fast (a single test, a
temp worktree), ZERO model calls — the guard is a pytest exit classification on two trees.

Exit codes (the prove mode — what the author may do next depends on them):

* ``0`` — the guard PASSED: ``verdict=pre-existing`` (the failure exists at the merge-base).
  The author MAY call the failure pre-existing, and the machine citation the command prints
  (``preexisting-guard-evidence: verdict=pre-existing base=... test=... before=FAIL
  after=FAIL``) is the evidence a review doc must embed when it does.
* ``1`` — the guard FAILED: ``verdict=branch-introduced`` (the test PASSED or was ABSENT at
  the merge-base but fails at the head) — the mislabeling pattern is caught mechanically, and
  calling the failure pre-existing is refused. Also ``not-failing`` (the test does not fail at
  the head — nothing to explain) and ``unverifiable`` (the base tree could not run the node —
  an unverifiable claim is never accepted).
* ``2`` — a usage/guard error refused the check (bad args, not a git repo, unresolvable sha,
  unreadable review doc).

The doc mode (``--doc``) scans a review doc and flags lines that make a "pre-existing" claim
about a failure WITHOUT a valid ``preexisting-guard-evidence`` citation; exit 0 = accepted,
1 = one or more uncited claims flagged.

Core logic: :mod:`agentic_dynamics.runtime.preexisting_guard`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
try:
    import _bootstrap  # noqa: F401  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: F401

from agentic_dynamics.runtime import preexisting_guard as pg  # noqa: E402
from agentic_dynamics.runtime.preexisting_guard import GuardError  # noqa: E402

#: Exit code for "the guard PASSED — pre-existing proven, author may cite the evidence."
EXIT_PRE_EXISTING = 0

#: Exit code for "the guard FAILED — the failure is branch-introduced / not failing /
#: unverifiable, so the author may NOT call it pre-existing." A nonzero distinct from 2 so a
#: caller can tell a genuine verdict from a refusal-to-run.
EXIT_CLAIM_REFUSED = 1

#: Exit code for a usage/guard error (bad args, non-git repo, unresolvable sha, unreadable doc).
EXIT_ERROR = 2

SCHEMA = "check-preexisting/v1"


def _load_doc(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise GuardError(f"cannot read review doc {path}: {exc}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentic-dynamics validate preexisting",
        description=(
            "Prove a failure exists at a merge-base before calling it pre-existing, or "
            "validate that a review doc's pre-existing claims cite the guard's evidence."
        ),
    )
    parser.add_argument(
        "--test",
        default=None,
        help="the failing pytest node id (e.g. tests/test_doc_lifecycle.py::test_...). "
        "Required in prove mode.",
    )
    parser.add_argument(
        "--base",
        default=None,
        help="the merge-base sha/ref the failure is claimed to predate. Required in prove mode.",
    )
    parser.add_argument(
        "--head",
        default="HEAD",
        help="the head sha/ref to compare against (default: the checkout's HEAD).",
    )
    parser.add_argument(
        "--repo",
        default=None,
        help="git checkout under review (default: the repo containing this script).",
    )
    parser.add_argument(
        "--doc",
        default=None,
        help="review-doc mode: scan this markdown review doc for pre-existing claims that "
        "carry no guard evidence citation.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="per-tree pytest timeout in seconds (default: 120).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the machine-readable record instead of the human summary.",
    )
    return parser


def _prove(args) -> int:  # noqa: ANN001
    if not args.test or not args.base:
        raise GuardError("prove mode requires --test and --base")
    repo = Path(args.repo).resolve() if args.repo else ROOT
    if not (repo / ".git").exists() and not _is_git_dir(repo):
        raise GuardError(f"{repo} is not a git checkout (no .git)")
    evidence = pg.prove_preexisting(
        repo,
        test=args.test,
        base=args.base,
        head=args.head,
        timeout=args.timeout,
    )
    doc = evidence.to_dict()
    if args.json:
        print(json.dumps(doc, indent=2, ensure_ascii=False))
    else:
        print(f"check-preexisting: {evidence.verdict}")
        print(f"  test       {evidence.test}")
        print(f"  base       {evidence.base_sha}")
        print(f"  head       {evidence.head_sha}")
        print(f"  before     {evidence.base_outcome}")
        print(f"  after      {evidence.head_outcome}")
        if evidence.note:
            print(f"  note       {evidence.note}")
        print(f"  citation   {evidence.citation()}")
        if evidence.verdict == pg.VERDICT_PRE_EXISTING:
            print("  -> the author MAY call this failure pre-existing (embed the citation above)")
        else:
            print("  -> calling this failure pre-existing is REFUSED (the guard did not pass)")
    if evidence.verdict == pg.VERDICT_PRE_EXISTING:
        return EXIT_PRE_EXISTING
    return EXIT_CLAIM_REFUSED


def _check_doc(args) -> int:  # noqa: ANN001
    text = _load_doc(Path(args.doc))
    flagged = pg.flag_uncited_preexisting_claims(text)
    doc = {
        "schema": SCHEMA,
        "mode": "doc",
        "doc": args.doc,
        "pre_existing_claims_without_evidence": flagged,
        "accepted": not flagged,
    }
    if args.json:
        print(json.dumps(doc, indent=2, ensure_ascii=False))
    elif flagged:
        print(f"check-preexisting doc: {len(flagged)} uncited pre-existing claim(s) flagged:")
        for line in flagged:
            print(f"  {line}")
    else:
        print(
            "check-preexisting doc: accepted — every pre-existing claim cites the guard's "
            "evidence (or the doc makes no such claim)"
        )
    return EXIT_PRE_EXISTING if not flagged else EXIT_CLAIM_REFUSED


def _is_git_dir(repo: Path) -> bool:
    import subprocess

    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
        )
        return proc.returncode == 0 and proc.stdout.strip() == "true"
    except OSError:
        return False


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.doc:
            return _check_doc(args)
        return _prove(args)
    except GuardError as exc:
        envelope = {"schema": SCHEMA, "error": "guard_error", "detail": str(exc)}
        if args.json:
            print(json.dumps(envelope, indent=2, ensure_ascii=False))
        else:
            print(f"check-preexisting: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
