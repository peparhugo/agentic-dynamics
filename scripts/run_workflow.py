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

from instrument.experiment_spec import ExperimentSpec, load_spec  # noqa: E402
from instrument.signal_store import build_signal_store, load_results  # noqa: E402
from instrument.spec_status import refresh_spec_status  # noqa: E402
from instrument.step_routing import ModelSignals  # noqa: E402
from instrument.workflow_runner import run_workflow  # noqa: E402


def _spec_declares_routing(spec: ExperimentSpec) -> bool:
    """True when the spec activates per-step routing (mirrors ``validate_workflow_routing``).

    Routing is active when the workflow declares a ``model_pool``, any per-phase
    ``model``/``allowed_models`` selector, or a ``preferences`` block. Only then do we bother
    building the signal store; single-model specs run unchanged (cold router).
    """
    params = spec.workflow.params
    if params.get("model_pool"):
        return True
    if params.get("preferences"):
        return True
    return any(
        "model" in p or "allowed_models" in p for p in (params.get("phases") or [])
    )


def _load_signals(path: str) -> dict[str, ModelSignals]:
    """Load an explicit signals override from a JSON file: ``{model: {field: value, …}}``."""
    with open(path) as fh:
        raw = json.load(fh)
    return {m: ModelSignals.from_dict(d) for m, d in raw.items()}


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
                    help="skip phases that already have a [workflow] <phase> commit; when the "
                         "worktree has no such commits, fall back to the phases the derived "
                         "spec index (experiments/specs/index.json) shows as ok for this goal")
    ap.add_argument("--signals", default=None,
                    help="path to a JSON file mapping model id -> measured signals "
                         "(overrides the auto-built signal store)")
    args = ap.parse_args()

    spec = load_spec(Path(args.spec))

    # Signal-store wiring (docs/routing_next_steps.md item 1): when the spec declares routing
    # and no explicit --signals override was supplied, build the store from the measured
    # corpus so the router consumes real data instead of cold-starting. The explicit
    # signals/preferences kwargs on run_workflow remain the override hook.
    signals: dict[str, ModelSignals] | None = None
    if args.signals:
        signals = _load_signals(args.signals)
    elif _spec_declares_routing(spec):
        try:
            signals = build_signal_store(load_results())
        except (FileNotFoundError, json.JSONDecodeError):
            # No measured corpus available — let the router cold-start deterministically.
            signals = None

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
        signals=signals,
    )

    print(json.dumps(result.to_dict(), indent=2))

    out_dir = ROOT / "experiments" / "results" / "workflows" / spec.name
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = out_dir / f"{ts}.json"
    out_path.write_text(json.dumps(result.to_dict(), indent=2))
    print(f"\nledger: {out_path}", file=sys.stderr)
    print(f"cost: ${result.total_cost_usd:.4f}  ok: {result.ok}", file=sys.stderr)

    _refresh_index(spec.name)


def _refresh_index(spec_name: str) -> None:
    """Refresh the derived spec index now that this run's ledger is on disk.

    Best-effort by construction (the ``emit_self`` pattern of
    ``workflow_runner.py:254-267``): the run has already completed and its ledger is
    already written, so an index problem — an unreadable spec YAML, a read-only
    ``experiments/specs/``, anything — must degrade to a printed warning. It may never
    fail the run or change its exit status.
    """
    try:
        report = refresh_spec_status(spec_name, root=ROOT)
        print(f"spec index: {report.index_path} ({report.n_specs} specs)", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 — a post-run bookkeeping step, never a gate
        print(
            f"warning: spec index refresh failed ({exc}) — run itself unaffected",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
