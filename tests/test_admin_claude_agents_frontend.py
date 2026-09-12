"""No-regression guard for the background-session / design / flags API surface.

The facelift replaces the Control Room's destination-board *client* with one resting screen, but
it is explicitly additive on the server: the background-Claude session, design-session, flags,
routing, registry and docs-health APIs must remain registered with their original HTTP methods so
existing callers (scripts, the supervisor, other operators) keep working. The old client-side
structural assertions lived here; they are superseded by
``tests/test_admin_frontend.py``'s resting-screen contract, and this module now holds the
preserved-API half.

It intentionally checks *methods*, not just paths: a route that still resolves but lost its POST
verb is the kind of silent regression a path-only assertion misses.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.fast


def _rules() -> dict[str, set[str]]:
    from apps.control_room import server

    out: dict[str, set[str]] = {}
    for rule in server.app.url_map.iter_rules():
        methods = set(rule.methods or ()) - {"HEAD", "OPTIONS"}
        # A rule can be registered once per verb under distinct endpoints; union them so the
        # guard sees every method the path actually answers.
        out.setdefault(str(rule), set()).update(methods)
    return out


def test_background_session_and_control_apis_keep_their_methods() -> None:
    """The preserved operational APIs keep the verbs their clients depend on."""
    rules = _rules()
    expected = {
        "/api/claude-agents": {"GET", "POST"},
        "/api/claude-agents/<session_id>/logs": {"GET"},
        "/api/claude-agents/<session_id>/stop": {"POST"},
        "/api/claude-agents/<session_id>/respawn": {"POST"},
        "/api/claude-agents/<session_id>/rm": {"POST"},
        "/api/claude-agents/<session_id>/steer": {"POST"},
        "/api/design-sessions": {"GET", "POST"},
        "/api/design-sessions/<portal_id>/input": {"POST"},
        "/api/design-sessions/<portal_id>/interrupt": {"POST"},
        "/api/design-sessions/<portal_id>/save": {"POST"},
        "/api/design-sessions/<portal_id>/run": {"POST"},
        "/api/flags": {"GET"},
        "/api/flags/<session_id>/steer": {"POST"},
        "/api/flags/<session_id>/interrupt": {"POST"},
        "/api/experiments": {"POST"},
        "/api/queue/reinterleave": {"POST"},
        "/api/docs-health/approve": {"POST"},
    }
    missing = {path: verbs for path, verbs in expected.items() if not verbs <= rules.get(path, set())}
    assert not missing, missing


def test_glance_surface_is_read_only() -> None:
    """The facelift adds read-only projections and no new mutation verb."""
    rules = _rules()
    assert rules["/api/glance"] == {"GET"}
    assert rules["/api/events"] == {"GET"}


def test_client_can_address_typed_objects_from_the_resting_roster() -> None:
    """The dock is opened from a roster row keyed by its stable `data-run-id` (Move 5)."""
    from pathlib import Path

    client = (Path(__file__).resolve().parent.parent / "apps" / "control_room" / "static" / "app.js").read_text()
    assert 'data-run-id' in client
    assert "openDock" in client
    assert "closeDock" in client
    # Selection survives as an identity, not a card: the ladder is re-derived from the run key.
    assert "findRunById" in client
