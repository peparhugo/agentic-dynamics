"""Browser-free structural verification for the vanilla Control Room client.

The repository intentionally has no JavaScript runtime dependency. These tests
therefore lock down the DOM and source-level invariants that connect the pure
core helpers to the page, while behavioral telemetry parsing is covered by the
shared event fixtures in ``test_admin_server.py``.
"""

from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "admin" / "static"


def test_control_room_shell_exposes_all_required_operational_regions():
    """The initial HTML must be useful before Redis or JavaScript responds."""
    html = (STATIC / "index.html").read_text()

    for required in (
        'id="reported-spend"',
        'id="burn-rate"',
        'id="fleet-grid"',
        'id="transcript-feed"',
        'role="log"',
        'id="control-session"',
        "READ ONLY",
        "Watching does not send input or control the experiment.",
        'id="routing-drawer"',
    ):
        assert required in html
    assert '<script src="/static/control-room-core.js"></script>' in html
    assert '<script src="/static/app.js"></script>' in html


def test_client_keeps_one_status_source_and_replaces_selected_source():
    """Stream ownership is explicit and the old cell stream closes first."""
    core = (STATIC / "control-room-core.js").read_text()
    app = (STATIC / "app.js").read_text()

    close_position = core.index("if (current) current.close()")
    construct_position = core.index("return new EventSourceClass(url)")
    assert close_position < construct_position
    assert 'if (state.statusSource) return' in app
    assert 'new EventSource("/api/status")' in app
    assert "core.replaceEventSource(" in app
    assert 'source.addEventListener("replay_complete"' in app


def test_client_bounds_transcript_and_preserves_empty_error_states():
    """Local rendering has a hard cap and named recovery copy."""
    app = (STATIC / "app.js").read_text()
    core = (STATIC / "control-room-core.js").read_text()

    assert "const MAX_TRANSCRIPT_ROWS = 500" in app
    assert "return current.concat(additions).slice(-limit)" in core
    for message in (
        "No cells are queued or retained",
        "No retained events observed for this cell.",
        "Redis unavailable",
        "Routing unavailable. Live workspace remains connected.",
        "Session identity not observed yet",
    ):
        assert message in app or message in (STATIC / "index.html").read_text()


def test_styles_cover_narrow_screens_focus_and_reduced_motion():
    """Responsive and accessible states remain part of the no-build asset."""
    css = (STATIC / "style.css").read_text()

    assert "@media (max-width: 759px)" in css
    assert "min-height: 55vh" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert ":focus-visible" in css
    assert ".cell-card.status-running" in css
