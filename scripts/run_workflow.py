"""Run an agent_task workflow (the execute phase) against a goal in a git worktree.

Usage:
    python scripts/run_workflow.py --spec experiments/specs/control_room_portal.yaml \
        --goal "Enhance the admin portal into a Control Room..." \
        --model openai/gpt-5.6-sol --workdir /tmp/pipeline/feature_admin-portal-control-plane

Writes the run ledger to ``experiments/results/workflows/<spec>/<timestamp>.json``.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from instrument.experiment_spec import load_spec  # noqa: E402
from instrument.workflow_runner import run_workflow  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Run an agent_task workflow spec against a goal.")
    ap.add_argument("--spec", required=True, help="path to an ExperimentSpec YAML")
    ap.add_argument("--goal", required=True, help="feature/task prompt (substituted for {goal})")
    ap.add_argument("--model", required=True, help="provider/model id")
    ap.add_argument("--workdir", required=True, help="git worktree to run in")
    ap.add_argument("--backend", default=None, help="opencode | claude_cli (default: auto)")
    ap.add_argument("--thinking-effort", default="high")
    ap.add_argument("--thinking-budget-tokens", type=int, default=0)
    ap.add_argument("--output-token-limit", type=int, default=0)
    ap.add_argument("--timeout", type=int, default=1800, help="per-phase timeout (s)")
    ap.add_argument("--no-commit", action="store_true", help="do not commit after phases")
    ap.add_argument("--resume", action="store_true",
                    help="skip phases that already have a [workflow] <phase> commit")
    args = ap.parse_args()

    spec = load_spec(Path(args.spec))
    result = run_workflow(
        spec,
        goal=args.goal,
        model=args.model,
        workdir=args.workdir,
        backend=args.backend,
        thinking_effort=args.thinking_effort,
        thinking_budget_tokens=args.thinking_budget_tokens,
        output_token_limit=args.output_token_limit,
        timeout=args.timeout,
        commit=not args.no_commit,
        resume=args.resume,
    )

    print(json.dumps(result.to_dict(), indent=2))

    out_dir = ROOT / "experiments" / "results" / "workflows" / spec.name
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = out_dir / f"{ts}.json"
    out_path.write_text(json.dumps(result.to_dict(), indent=2))
    print(f"\nledger: {out_path}", file=sys.stderr)
    print(f"cost: ${result.total_cost_usd:.4f}  ok: {result.ok}", file=sys.stderr)


if __name__ == "__main__":
    main()
