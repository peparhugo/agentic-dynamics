"""Invariant tests for the Control Room's repo-root and default paths.

Refactor-repair P0-3: after the ``admin/`` → ``apps/control_room/`` move,
``server.ROOT`` was ``Path(__file__).resolve().parent.parent`` — i.e. ``<repo>/apps``
rather than the repo root — so every default path it derived (``data_manifest.json``,
supervisor flags, and the design-session / claude-agent workdir allowlists) silently
resolved under ``apps/experiments/...`` (or defaulted the workdir to ``apps/``).

These tests pin ``server.ROOT == agentic_dynamics.core.paths.PROJECT_ROOT`` and assert
each default resolves inside the repository, so the move can never silently re-home a
path again without failing here.
"""

from __future__ import annotations

from agentic_dynamics.core.paths import PROJECT_ROOT
from apps.control_room import server


def test_root_equals_project_root() -> None:
    """The module's ROOT is the single source of truth, not a sibling-relative guess."""
    assert server.ROOT == PROJECT_ROOT


def test_data_manifest_default_resolves_inside_repo() -> None:
    """The registry manifest default lives at the repo root, not under apps/."""
    assert server.DATA_MANIFEST_PATH == PROJECT_ROOT / "experiments" / "data_manifest.json"
    assert server.DATA_MANIFEST_PATH.is_absolute()


def test_supervisor_flags_default_resolves_inside_repo() -> None:
    """The supervisor flags fallback file lives at the repo root, not under apps/."""
    assert (
        server.SUPERVISOR_FLAGS_FILE
        == PROJECT_ROOT / "experiments" / "results" / "supervisor" / "flags.jsonl"
    )
    assert server.SUPERVISOR_FLAGS_FILE.is_absolute()


def test_claude_agent_workdir_defaults_inside_repo(monkeypatch) -> None:
    """The default approved-workdir allowlist resolves to the repo root, not apps/."""
    monkeypatch.delenv("FINOPS_CLAUDE_AGENT_WORKDIRS", raising=False)
    assert server._claude_agent_workdirs() == {"repository": PROJECT_ROOT}


def test_design_session_workdir_defaults_inside_repo(monkeypatch) -> None:
    """The default design-session workdir resolves to the repo root, not apps/."""
    monkeypatch.delenv("FINOPS_DESIGN_WORKDIRS", raising=False)

    captured: dict[str, object] = {}

    class FakeManager:
        """Capture the workdir allowlist the server hands to the real manager."""

        def __init__(self, *, root, workdirs, **kwargs):
            captured["root"] = root
            captured["workdirs"] = workdirs

    monkeypatch.setattr(server, "DesignSessionManager", FakeManager)
    monkeypatch.setattr(server, "OpenCodeClient", lambda *a, **k: object())

    original = server._design_manager
    server._design_manager = None
    try:
        server._design_sessions()
        assert captured["root"] == PROJECT_ROOT
        assert captured["workdirs"] == {"repository": PROJECT_ROOT}
    finally:
        server._design_manager = original
