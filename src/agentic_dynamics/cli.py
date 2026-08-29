"""The ``agentic-dynamics`` command-line interface (critique rec 5, rec 8).

A thin dispatcher over the maintained ``scripts/`` surface: each subcommand forwards its
arguments to the backing script via a subprocess. The CLI composes — it never re-implements a
script's logic, and it never imports a ``control`` module to steer a running session (observe-only,
per the supervisor design).

Design: ``docs/consolidation/design.md`` §5 (the complete subcommand tree).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

#: Static leaf commands: (argv prefix) -> backing script. Remaining argv is forwarded verbatim.
_COMMANDS: dict[tuple[str, ...], str] = {
    # experiment
    ("experiment", "run"): "run.py",
    ("experiment", "cap-grit-grid"): "run_cap_grit_grid.py",
    ("experiment", "cap-grit-measure"): "measure_cap_grit_grid.py",
    ("experiment", "cap-2c-grid"): "run_cap_2c_grid.py",
    ("experiment", "cap-2c-score"): "score_cap_2c.py",
    ("experiment", "cap-2d-grid"): "run_cap_2d_grid.py",
    ("experiment", "cap-2d-score"): "score_cap_2d.py",
    ("experiment", "cap-2e-grid"): "run_cap_2e_grid.py",
    ("experiment", "cap-2e-score"): "score_cap_2e.py",
    ("experiment", "cap-2f-grid"): "run_cap_2f_grid.py",
    ("experiment", "cap-2f-score"): "score_cap_2f.py",
    ("experiment", "sweep-parallel"): "sweep_parallel.py",
    ("experiment", "sweep-silent"): "sweep_silent_mode.py",
    ("experiment", "batch"): "batch_run.py",
    ("experiment", "remaining"): "remaining_batch.py",
    ("experiment", "multi-phase"): "multi_phase.py",
    # story
    ("story", "run"): "run_story.py",
    ("story", "batch"): "batch_stories.py",
    # workflow
    ("workflow", "run"): "run_workflow.py",
    ("workflow", "discard-tree"): "record_discarded_tree.py",
    # queue
    ("queue", "enqueue"): "enqueue.py",
    ("queue", "worker"): "worker.py",
    ("queue", "monitor"): "monitor.py",
    ("queue", "reinterleave"): "reinterleave_queue.py",
    ("queue", "analysis-enqueue"): "enqueue_analysis.py",
    ("queue", "analysis-worker"): "analysis_worker.py",
    # analyze
    ("analyze", "worktrees"): "analyze_worktrees.py",
    ("analyze", "trajectories"): "analyze_trajectories.py",
    ("analyze", "stories"): "analyze_stories.py",
    ("analyze", "session-routing"): "retro_session_routing.py",
    ("analyze", "cascade-retrospective"): "cap_cascade_retrospective.py",
    ("analyze", "coverage-routing-impact"): "cap_coverage_routing_impact.py",
    # data
    ("data", "build"): "build_data.py",
    ("data", "sync"): "sync_data.py",
    ("data", "manifest"): "generate_manifest.py",
    ("data", "inventory"): "inventory.py",
    ("data", "bundle"): "bundle_artifacts.py",
    # knowledge
    ("knowledge", "ingest"): "kb_produce.py",
    ("knowledge", "sources"): "kb_produce_sources.py",
    ("knowledge", "facts"): "kb_produce_facts.py",
    ("knowledge", "campaign-evidence"): "kb_produce_campaign_evidence.py",
    ("data", "site-census"): "site_census_check.py",
    ("knowledge", "worker"): "kb_worker.py",
    ("knowledge", "context-report"): "context_snapshot_report.py",
    ("knowledge", "shadow-report"): "shadow_decision_report.py",
    ("knowledge", "arm-comparison"): "decision_arm_comparison.py",
    # review
    ("review", "all"): "review_all.py",
    ("review", "stories"): "review_stories.py",
    ("review", "trigger"): "trigger_reviews.py",
    ("review", "enqueue"): "enqueue_reviews.py",
    ("review", "finalize"): "finalize_reviews.py",
    # spec
    ("spec", "status"): "spec_status.py",
    ("spec", "pipeline"): "pipeline.py",
    # validate
    ("validate", "session"): "validate_session.py",
    ("validate", "tests"): "verify_tests.py",
    ("validate", "prereq"): "evidence_prereq_gate.py",
    # supervise
    ("supervise",): "supervise.py",
    ("supervise", "claude-agents"): "claude_agents_supervisor.py",
    ("supervise", "orphans"): "orphan_sweep.py",
    # release
    ("release", "check-protection"): "check_branch_protection.py",
    # surfaces (the self-maintenance command — design: system_knowledge_abstraction)
    ("surfaces", "sync"): "sync_surfaces.py",
    ("surfaces", "snapshot"): "system_snapshot.py",
}

#: ``_COMMANDS`` keys ordered longest-first. ``_resolve`` iterates THIS list rather than
#: ``_COMMANDS`` directly: ``_COMMANDS`` is a dict literal whose insertion order happens to
#: register ``("supervise",)`` before ``("supervise", "claude-agents")``, so a first-match
#: walk over it would resolve ``supervise claude-agents`` to ``supervise.py`` (the shorter
#: prefix) — a real command-resolution bug (refactor-repair P1-2). Sorting prefixes by
#: length descending makes the FIRST matching prefix necessarily the LONGEST one, which is
#: the documented longest-prefix semantics. The sort is stable, so equal-length prefixes
#: (which can never both match the same argv) keep insertion order.
_SORTED_PREFIXES: list[tuple[str, ...]] = sorted(_COMMANDS, key=len, reverse=True)

#: ``registry`` subcommands, all backed by ``registry.py`` (its first positional arg).
_REGISTRY_SUBCOMMANDS = {"query", "show", "lineage"}

_HELP = """\
agentic-dynamics — one entry point over the maintained scripts/ surface.

Subcommands (each forwards to its backing script):

  experiment run|sweep-parallel|sweep-silent|batch|remaining|multi-phase|cap-grit-grid|cap-grit-measure|cap-2c-grid|cap-2c-score|cap-2d-grid|cap-2d-score|cap-2e-grid|cap-2e-score|cap-2f-grid|cap-2f-score
  story       run|batch
  workflow    run|discard-tree
  queue       enqueue|worker|monitor|reinterleave|analysis-enqueue|analysis-worker
  analyze     worktrees|trajectories|stories|session-routing|lab <name>
  data        build|sync|manifest|inventory|bundle
  knowledge   ingest|sources|facts|worker|context-report|shadow-report|arm-comparison
  registry    query|show|lineage
  review      all|stories|trigger|enqueue|finalize
  spec        status|pipeline
  validate    session|tests|prereq
  supervise   [claude-agents|orphans]
  release     check-protection
  surfaces    sync|snapshot

Run `agentic-dynamics <subcommand> --help` for the backing script's own options.

Checkout-only: this CLI is a thin dispatcher — every subcommand forwards to a script in the
repository's ``scripts/`` directory, so it only works from a git checkout (``pip install -e .``).
An installed wheel carries no ``scripts/`` and can only print this help.
"""

#: Message emitted when a real command is attempted from an installed distribution that has no
#: ``scripts/`` sibling. The CLI is checkout-only (refactor-repair P1-2 packaging): it forwards
#: to repo-level scripts rather than shipping them in the wheel, so a wheel install can print
#: help but cannot dispatch a command. This text is the machine-checkable contract the CI wheel
#: smoke test greps for.
CHECKOUT_REQUIRED = (
    "agentic-dynamics: checkout required — this CLI forwards each command to the repository's "
    "scripts/ directory, which is not present here (installed wheel?). Install from a git "
    "checkout with `pip install -e .`, or run the backing script directly."
)


def _forward(script: str, argv: list[str]) -> int:
    """Run a backing script as a subprocess, forwarding argv."""
    return subprocess.call([sys.executable, str(_SCRIPTS_DIR / script), *argv])


def _resolve(argv: list[str]) -> tuple[str | None, list[str]]:
    """Resolve argv to ``(backing_script, forwarded_args)`` or ``(None, [])`` if unresolved."""
    # True longest-prefix match over the static command table (longest prefixes first).
    for prefix in _SORTED_PREFIXES:
        if tuple(argv[: len(prefix)]) == prefix:
            return _COMMANDS[prefix], argv[len(prefix):]
    # ``registry query|show|lineage`` -> registry.py <subcommand> ...
    if argv[0] == "registry" and len(argv) >= 2 and argv[1] in _REGISTRY_SUBCOMMANDS:
        return "registry.py", argv[1:]
    # ``analyze lab <name>`` -> lab_<name>.py ...
    if len(argv) >= 3 and argv[:2] == ["analyze", "lab"]:
        return f"lab_{argv[2]}.py", argv[3:]
    return None, []


def main(argv: list[str] | None = None) -> int:
    """CLI entry point (also the ``console_scripts`` target)."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(_HELP)
        return 0
    script, rest = _resolve(argv)
    if script is None:
        print(f"agentic-dynamics: unknown command {' '.join(argv)}", file=sys.stderr)
        return 2
    # Checkout-only guard: without a scripts/ sibling (e.g. an installed wheel) the dispatcher
    # has nothing to forward to. Placed AFTER resolution so ``--help`` (handled above) still
    # works from a wheel, but any real command explains the checkout requirement.
    if not _SCRIPTS_DIR.is_dir():
        print(CHECKOUT_REQUIRED, file=sys.stderr)
        return 2
    if not (_SCRIPTS_DIR / script).exists():
        print(f"agentic-dynamics: no such command {' '.join(argv)}", file=sys.stderr)
        return 2
    return _forward(script, rest)


if __name__ == "__main__":
    raise SystemExit(main())
