"""Command-resolution tests for the ``agentic-dynamics`` CLI (refactor-repair P1-2).

The CLI's ``_resolve`` must implement TRUE longest-prefix matching over its static command
table. The bug this pins: ``_COMMANDS`` was iterated in insertion order, which registered
``("supervise",)`` before ``("supervise", "claude-agents")`` — so ``agentic-dynamics supervise
claude-agents`` resolved to ``supervise.py`` instead of ``claude_agents_supervisor.py``. A
second latent bug is pinned alongside it: the bare-supervise key was written ``("supervise")``
(a bare string, not a 1-tuple), so ``agentic-dynamics supervise`` silently never resolved at all.

The expectation table below is hand-authored from the DOCUMENTED surface — the ``_HELP``
subcommand block and ``.opencode/instructions/mental-model.md`` §"CLI surface" — deliberately
NOT read from ``cli._COMMANDS``: the whole point is that a drift between the dispatcher table
and what users are told must fail here, not be masked by deriving both sides from the same source.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agentic_dynamics import cli

ROOT = Path(__file__).resolve().parent.parent

#: Hand-authored (argv prefix, backing script, forwarded argv) for every documented leaf
#: command. Sourced from ``cli._HELP`` + the CLI-surface tree, not from ``cli._COMMANDS``.
DOCUMENTED_RESOLUTIONS: list[tuple[tuple[str, ...], str, tuple[str, ...]]] = [
    # experiment
    (("experiment", "run"), "run.py", ()),
    (("experiment", "sweep-parallel"), "sweep_parallel.py", ()),
    (("experiment", "sweep-silent"), "sweep_silent_mode.py", ()),
    (("experiment", "batch"), "batch_run.py", ()),
    (("experiment", "remaining"), "remaining_batch.py", ()),
    (("experiment", "multi-phase"), "multi_phase.py", ()),
    # story
    (("story", "run"), "run_story.py", ()),
    (("story", "batch"), "batch_stories.py", ()),
    # workflow
    (("workflow", "run"), "run_workflow.py", ()),
    # queue
    (("queue", "enqueue"), "enqueue.py", ()),
    (("queue", "worker"), "worker.py", ()),
    (("queue", "monitor"), "monitor.py", ()),
    (("queue", "reinterleave"), "reinterleave_queue.py", ()),
    (("queue", "analysis-enqueue"), "enqueue_analysis.py", ()),
    (("queue", "analysis-worker"), "analysis_worker.py", ()),
    # analyze
    (("analyze", "worktrees"), "analyze_worktrees.py", ()),
    (("analyze", "trajectories"), "analyze_trajectories.py", ()),
    (("analyze", "stories"), "analyze_stories.py", ()),
    # data
    (("data", "build"), "build_data.py", ()),
    (("data", "sync"), "sync_data.py", ()),
    (("data", "manifest"), "generate_manifest.py", ()),
    (("data", "inventory"), "inventory.py", ()),
    # knowledge
    (("knowledge", "ingest"), "kb_produce.py", ()),
    (("knowledge", "sources"), "kb_produce_sources.py", ()),
    (("knowledge", "worker"), "kb_worker.py", ()),
    # registry — special-cased: argv[1] is forwarded to registry.py as its first positional
    (("registry", "query"), "registry.py", ("query",)),
    (("registry", "show"), "registry.py", ("show",)),
    (("registry", "lineage"), "registry.py", ("lineage",)),
    # review
    (("review", "all"), "review_all.py", ()),
    (("review", "stories"), "review_stories.py", ()),
    (("review", "trigger"), "trigger_reviews.py", ()),
    (("review", "enqueue"), "enqueue_reviews.py", ()),
    (("review", "finalize"), "finalize_reviews.py", ()),
    # spec
    (("spec", "status"), "spec_status.py", ()),
    (("spec", "pipeline"), "pipeline.py", ()),
    # validate
    (("validate", "session"), "validate_session.py", ()),
    (("validate", "tests"), "verify_tests.py", ()),
    # supervise — the P1-2 regression: the two forms MUST resolve to different scripts.
    (("supervise",), "supervise.py", ()),
    (("supervise", "claude-agents"), "claude_agents_supervisor.py", ()),
]


def _documented_leaf_commands() -> set[tuple[str, ...]]:
    """Extract every documented leaf command from the CLI's own help text.

    The help block lists one family per line as ``family leaf|leaf|...``; three lines need
    special handling: ``registry`` (dynamic-first-positional, still a leaf per subcommand),
    ``analyze ... lab <name>`` (dynamic leaf — tested separately, not a static table row),
    and ``supervise [claude-agents]`` (bare supervise + the optional subcommand).
    """
    lines = cli._HELP.splitlines()
    start = next(i for i, line in enumerate(lines) if "Subcommands" in line)
    end = next(i for i in range(start, len(lines)) if lines[i].startswith("Run `"))

    leaves: set[tuple[str, ...]] = set()
    for raw in lines[start + 1 : end]:
        line = raw.strip()
        if not line:
            continue
        family, _, rest = line.partition(" ")
        rest = rest.strip()
        if family == "analyze":
            for leaf in rest.split("|"):
                if leaf != "lab <name>":  # dynamic leaf, not a static table row
                    leaves.add((family, leaf))
        elif family == "supervise":
            leaves.add((family,))
            leaves.add((family, "claude-agents"))
        else:
            for leaf in rest.split("|"):
                leaves.add((family, leaf))
    return leaves


@pytest.mark.parametrize(
    ("argv", "expected_script", "expected_rest"),
    DOCUMENTED_RESOLUTIONS,
    ids=[" ".join(a) for a, _, _ in DOCUMENTED_RESOLUTIONS],
)
def test_documented_command_resolves(argv, expected_script, expected_rest) -> None:
    """Every documented leaf command resolves to its documented backing script."""
    script, rest = cli._resolve(list(argv))
    assert script == expected_script
    assert rest == list(expected_rest)
    # The documented script must actually exist on disk (not just match the table).
    assert (cli._SCRIPTS_DIR / script).exists(), f"{script} does not exist under scripts/"


def test_supervise_claude_agents_is_not_shadowed_by_bare_supervise() -> None:
    """Regression: the longer prefix wins, so ``supervise claude-agents`` is not misrouted."""
    script, rest = cli._resolve(["supervise", "claude-agents"])
    assert script == "claude_agents_supervisor.py"
    assert rest == []


def test_bare_supervise_still_resolves() -> None:
    """Regression: the bare-supervise key must be a real 1-tuple (``("supervise",)``)."""
    assert cli._resolve(["supervise"]) == ("supervise.py", [])


def test_forwarded_args_are_preserved() -> None:
    """Arguments after the matched prefix are forwarded verbatim to the backing script."""
    script, rest = cli._resolve(["experiment", "run", "--model", "deepseek/deepseek-v4-pro"])
    assert script == "run.py"
    assert rest == ["--model", "deepseek/deepseek-v4-pro"]
    # Optional flags after a bare leaf command are forwarded, not treated as subcommands.
    script, rest = cli._resolve(["supervise", "--once"])
    assert script == "supervise.py"
    assert rest == ["--once"]


def test_unknown_command_returns_none() -> None:
    """A command outside the documented surface resolves to ``(None, [])``."""
    assert cli._resolve(["does", "not", "exist"]) == (None, [])
    assert cli._resolve(["experiment", "bogus"]) == (None, [])


def test_analyze_lab_is_dynamic() -> None:
    """``analyze lab <name>`` is a dynamic leaf -> ``lab_<name>.py``.

    Uses ``grit`` because it names a real, canonical lab (``scripts/lab_grit.py``); the
    example used to be ``grit_matrix``, which s4 renamed out of existence.
    """
    script, rest = cli._resolve(["analyze", "lab", "grit"])
    assert script == "lab_grit.py"
    assert rest == []
    assert (ROOT / "scripts" / script).exists(), "the example must name a lab that exists"


def test_registry_forwards_subcommand() -> None:
    """``registry <sub>`` forwards the subcommand as registry.py's first positional arg."""
    assert cli._resolve(["registry", "lineage"]) == ("registry.py", ["lineage"])


def test_every_documented_leaf_is_covered_by_the_table() -> None:
    """The hand-authored table and the help text describe exactly the same command set.

    Guards both directions: a leaf documented in ``_HELP`` but missing from the table (or a
    table row for a command the help text no longer documents) fails here, so the table can
    never silently drift from what users are told.
    """
    documented = _documented_leaf_commands()
    table = {argv for argv, _, _ in DOCUMENTED_RESOLUTIONS}
    assert documented == table


# --- P1-2 packaging: the CLI is checkout-only (forwards to repo scripts/, not the wheel) ---


def test_help_documents_checkout_only() -> None:
    """The help text declares the checkout-only constraint (the packaging decision)."""
    assert "checkout-only" in cli._HELP.lower()
    assert "scripts/" in cli._HELP


def test_command_from_installed_wheel_emits_checkout_required(
    tmp_path, monkeypatch, capsys
) -> None:
    """Without a scripts/ sibling (an installed wheel), a command explains the requirement."""
    monkeypatch.setattr(cli, "_SCRIPTS_DIR", tmp_path / "scripts")  # deliberately nonexistent
    rc = cli.main(["experiment", "run"])
    captured = capsys.readouterr()
    assert rc == 2
    assert "checkout required" in captured.err


def test_help_still_works_from_installed_wheel(tmp_path, monkeypatch, capsys) -> None:
    """``--help`` remains usable from a wheel — only command dispatch needs the checkout."""
    monkeypatch.setattr(cli, "_SCRIPTS_DIR", tmp_path / "scripts")  # deliberately nonexistent
    rc = cli.main(["--help"])
    assert rc == 0
    assert "checkout-only" in capsys.readouterr().out.lower()
