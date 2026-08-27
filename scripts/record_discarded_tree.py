"""Record a discarded tree on the relabel gate's ledger (cap_runner_hardening2 §Gap 2).

The relabel tree-identity gate fails any phase whose committed tree is EXACTLY a tree that
was previously DISCARDED (the revamp2 shape: attempt A's tree was reset away, attempt B
re-committed a byte-identical copy under compliant ``[workflow]`` messages — ``git diff
f6fc35edf 20eeb801b`` is empty). The discarded-trees ledger
(``experiments/results/workflows/<spec>/discarded_trees.jsonl``) is the gate's memory: this
script is the reset/rollback path that WRITES it — the operator runs it right before (or
after) a reset/rollback that throws a worktree state away, so the gate can later recognize
that state if it is ever re-presented as fresh work.

Usage (the reset/rollback path):

    agentic-dynamics workflow discard-tree --spec <spec> --workdir <worktree> [--branch b]
                                           [--commit <rev>] [--reason reset]

``--commit`` defaults to HEAD (the tree about to be discarded); ``--branch`` defaults to the
worktree's current branch (the ledger is keyed ``(spec, branch, tree_hash, discarded_at)``).
Idempotent: re-recording the same (spec, branch, tree) is a no-op.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401

from agentic_dynamics.runtime.workflow_runner import (  # noqa: E402
    discarded_trees_path,
    record_discarded_tree,
)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Record a discarded tree on the relabel gate's ledger — the runner's "
                    "reset/rollback path. FLAG-ONLY: records, never steers."
    )
    ap.add_argument("--spec", required=True, help="spec name (the ledger key namespace)")
    ap.add_argument("--workdir", required=True, help="the git worktree whose tree is discarded")
    ap.add_argument("--branch", default=None, help="branch the tree was discarded on (default: worktree branch)")
    ap.add_argument("--commit", default="HEAD", help="revision whose tree is discarded (default HEAD)")
    ap.add_argument("--reason", default="reset", help="discard reason (default: reset)")
    ap.add_argument("--ledger", default=None, help="override the discarded-trees ledger path (tests)")
    args = ap.parse_args()

    tree_hash = record_discarded_tree(
        args.spec,
        args.workdir,
        branch=args.branch,
        commit=args.commit,
        reason=args.reason,
        ledger_path=Path(args.ledger) if args.ledger else None,
    )
    if not tree_hash:
        print(
            f"[discard-tree] could not resolve a tree for {args.workdir} @ {args.commit} — "
            f"nothing recorded (the worktree may not be a git repo)",
            file=sys.stderr,
        )
        raise SystemExit(1)
    path = discarded_trees_path(args.spec)
    if args.ledger:
        path = Path(args.ledger)
    print(f"[discard-tree] recorded {tree_hash} (spec={args.spec}, reason={args.reason}) -> {path}")


if __name__ == "__main__":
    main()
