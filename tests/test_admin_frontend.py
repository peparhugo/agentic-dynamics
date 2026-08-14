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


def test_design_session_shell_has_distinct_launch_and_interactive_controls():
    """Design controls are explicit while the existing read-only panel remains."""
    html = (STATIC / "index.html").read_text()

    for required in (
        'id="new-workflow-design"',
        'id="new-experiment-design"',
        'id="design-start-form"',
        'id="validation-errors"',
        'id="matrix-preview"',
        'id="save-spec-button"',
        'id="run-workflow-button"',
        'id="send-design-input"',
        'id="steer-design-input"',
        'id="interrupt-design"',
        'id="detach-design"',
        'id="recent-design-list"',
    ):
        assert required in html
    assert "Enqueue" not in html[html.index('id="design-control-panel"'):html.index('class="recent-designs"')]


def test_design_client_reuses_one_stream_and_server_capability_gates():
    """Selection and validation extend, rather than fork, established machinery."""
    app = (STATIC / "app.js").read_text()

    assert "function selectDesignSession(portalId, attach)" in app
    assert "if (state.eventSource) state.eventSource.close()" in app
    assert "connectSelectedStream()" in app
    assert "!state.draftFresh || !draft?.capabilities?.save" in app
    assert "!state.draftFresh || !draft?.capabilities?.run" in app
    assert 'fetch(`/api/design-sessions/${encodeURIComponent(selectedAtRequest)}/spec`)' in app
    assert 'delivery === "steer" ? $("#steer-design-input")' in app
    assert "/interrupt`, {})" in app
    assert "detachSelectedStream" in app
    assert 'headers: { "Content-Type": "application/json", "Idempotency-Key": mutationKey() }' in app


def test_design_styles_keep_artifacts_bounded_on_narrow_screens():
    """YAML and action groups remain usable without page-level overflow."""
    css = (STATIC / "style.css").read_text()

    for selector in (
        ".design-launcher-grid",
        ".validation-panel",
        ".row-yaml",
        ".row-validate-pass",
        ".row-validate-error",
        ".recent-design",
        ".design-control-panel > .mobile-anchor",
    ):
        assert selector in css
    mobile = css[css.index("@media (max-width: 420px)"):]
    assert ".design-stream-actions" in mobile
    assert "grid-template-columns: minmax(0, 1fr)" in mobile


def test_spend_rail_surfaces_retained_window_truncation():
    """The spend rail labels a truncated retained window instead of hiding it."""
    app = (STATIC / "app.js").read_text()

    assert "history_capped" in app
    assert "RETAINED WINDOW · TRUNCATED" in app
    assert "#spend-provenance" in app


def test_supervisor_surface_preserves_human_action_and_single_terminal_boundaries():
    """The no-build client exposes deliberate controls without a second terminal."""
    html = (STATIC / "index.html").read_text()
    app = (STATIC / "app.js").read_text()
    css = (STATIC / "style.css").read_text()

    for required in (
        'id="supervisor-rail"',
        'id="supervisor-flag-list"',
        'id="supervisor-control-panel"',
        'id="supervisor-steer-form"',
        'id="supervisor-interrupt-door"',
        'id="confirm-supervisor-interrupt"',
        "Supervisor flags. You decide.",
    ):
        assert required in html
    assert html.count('id="transcript-feed"') == 1
    assert 'fetch("/api/flags?limit=50")' in app
    assert "selectSupervisorFlag" in app
    assert "delivery" not in app[app.index("async function submitSupervisorSteer"):app.index("function openSupervisorInterruptDoor")]
    assert "confirmation !== `INTERRUPT ${flag.session_id}`" in app
    assert "grid-template-areas:" in css
    assert '"attention"' in css
