"""Browser-free structural verification for the Claude background-session UI.

Mirrors ``tests/test_admin_frontend.py``'s approach: the repository has no
JavaScript runtime dependency, so these tests lock down the DOM and
source-level invariants that connect the new fleet section to the existing
selection/SSE machinery, without executing the client.
"""

from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "admin" / "static"


def test_claude_agents_shell_exposes_roster_daemon_and_control_regions():
    """The initial HTML must render the new section before JavaScript responds."""
    html = (STATIC / "index.html").read_text()

    for required in (
        'id="claude-agents"',
        'id="claude-agent-grid"',
        'id="claude-agent-total"',
        'id="new-claude-agent"',
        'id="claude-agent-start-form"',
        'id="claude-agent-task"',
        'id="claude-agent-workdir"',
        'id="claude-agent-daemon-panel"',
        'id="daemon-status"',
        'id="daemon-stop-button"',
        'id="daemon-end-sessions"',
        'id="claude-agent-control-panel"',
        'id="claude-agent-control-id"',
        'id="claude-agent-owned-controls"',
        'id="claude-agent-steer-form"',
        'id="claude-agent-steer-prompt"',
        'id="claude-agent-steer"',
        'id="claude-agent-stop"',
        'id="claude-agent-respawn"',
        'id="claude-agent-rm"',
        'id="claude-agent-detach"',
        'id="claude-agent-external-controls"',
        'id="claude-agent-fetch-logs"',
        'id="claude-agent-detach-external"',
        'id="claude-agent-external-log"',
    ):
        assert required in html, f"missing {required}"


def test_claude_agent_control_panel_has_steer_but_no_send_or_interrupt_affordance():
    """Steering exists (owned-only); there is no separate send or interrupt control."""
    html = (STATIC / "index.html").read_text()
    panel = html[html.index('id="claude-agent-control-panel"') : html.index('id="recent-designs-title"')]

    assert "Steer" in panel
    assert 'id="claude-agent-steer-prompt"' in panel
    for forbidden in ("Send", "Interrupt", 'type="text"'):
        assert forbidden not in panel


def test_steer_form_is_owned_only_and_client_gated():
    app = (STATIC / "app.js").read_text()
    assert '$("#claude-agent-steer-form").hidden = !entry.owned' in app

    block = app[app.index('$("#claude-agent-steer-form").addEventListener') :]
    block = block[: block.index("})\n") + 3]
    assert "!entry.owned" in block
    assert "!prompt" in block


def test_claude_agent_grid_reuses_the_shared_selection_and_stream_machinery():
    """Selecting an owned card must hand off through the existing single EventSource."""
    app = (STATIC / "app.js").read_text()

    assert 'const CLAUDE_AGENT_CELL_PREFIX = "claude_bg_"' in app
    assert "function selectClaudeAgent(id, attach)" in app
    assert "if (state.eventSource) state.eventSource.close()" in app
    assert "if (entry.owned && attach && !state.attached) connectSelectedStream()" in app
    assert "`${CLAUDE_AGENT_CELL_PREFIX}${id}`" in app


def test_external_cards_never_attach_the_live_stream_and_use_one_shot_logs():
    """External sessions get a one-shot ``/logs`` fetch instead of the SSE pane."""
    app = (STATIC / "app.js").read_text()

    assert 'fetch(`/api/claude-agents/${encodeURIComponent(entry.id)}/logs`)' in app
    assert "if (!entry || entry.owned) return" in app
    assert '$("#claude-agent-owned-controls").hidden = !entry.owned' in app
    assert '$("#claude-agent-external-controls").hidden = entry.owned' in app


def test_owned_external_badge_is_rendered_per_roster_entry():
    app = (STATIC / "app.js").read_text()

    assert 'entry.owned ? "OWNED" : "EXTERNAL"' in app
    assert '`ownership-chip ${entry.owned ? "owned" : "external"}`' in app


def test_stop_and_rm_require_window_confirm_but_respawn_does_not():
    app = (STATIC / "app.js").read_text()
    stop_block = app[app.index('$("#claude-agent-stop").addEventListener') : app.index('$("#claude-agent-respawn").addEventListener')]
    respawn_block = app[app.index('$("#claude-agent-respawn").addEventListener') : app.index('$("#claude-agent-rm").addEventListener')]
    rm_block = app[app.index('$("#claude-agent-rm").addEventListener') : app.index('$("#claude-agent-detach").addEventListener')]

    assert "window.confirm(" in stop_block
    assert "conversation is preserved and can be resumed with Respawn" in stop_block
    assert "window.confirm(" not in respawn_block
    assert "window.confirm(" in rm_block
    assert "transcript stays on disk" in rm_block


def test_stop_respawn_rm_are_rejected_client_side_for_external_sessions():
    app = (STATIC / "app.js").read_text()
    for handler in ("claude-agent-stop", "claude-agent-respawn", "claude-agent-rm"):
        block = app[app.index(f'$("#{handler}").addEventListener'):]
        block = block[: block.index("})\n") + 3]
        assert "!entry.owned" in block


def test_daemon_stop_requires_blast_radius_confirm_and_a_second_distinct_confirm():
    """§3.5/AC8: a second, visually distinct confirm/toggle gates keep_workers: false."""
    app = (STATIC / "app.js").read_text()
    block = app[app.index('$("#daemon-stop-button").addEventListener') :]
    block = block[: block.index("\n  }") + 4]

    assert "affects every background session on this machine" in block
    assert 'const keepWorkers = !$("#daemon-end-sessions").checked' in block
    assert "if (!keepWorkers && !window.confirm(" in block
    assert block.count("window.confirm(") == 2
    assert "keep_workers: keepWorkers" in block


def test_daemon_stop_sends_explicit_boolean_never_a_bare_post():
    app = (STATIC / "app.js").read_text()
    assert 'claudeAgentMutation("/api/claude-agents/daemon/stop", { keep_workers: keepWorkers })' in app


def test_daemon_panel_is_always_visible_and_read_only_status_only():
    """The daemon panel shows status; no control lives inside a per-session card."""
    html = (STATIC / "index.html").read_text()
    daemon_panel = html[html.index('id="claude-agent-daemon-panel"') : html.index('id="claude-agent-start-form"')]

    assert "daemon-status" in daemon_panel
    assert "daemon-pid" in daemon_panel
    assert "daemon-stop-button" in daemon_panel
    # The per-card control panel must not also carry a daemon-stop control.
    control_panel_start = html.index('id="claude-agent-control-panel"')
    control_panel_end = html.index('id="recent-designs-title"')
    assert "daemon-stop-button" not in html[control_panel_start:control_panel_end]


def test_start_session_launches_with_skip_permissions_and_no_raw_path():
    """Only an approved workdir key is ever sent, matching the design-session rule."""
    app = (STATIC / "app.js").read_text()
    html = (STATIC / "index.html").read_text()

    assert 'workdir: $("#claude-agent-workdir").value' in app
    assert 'id="claude-agent-workdir" required' in html
    assert "--dangerously-skip-permissions" in html


def test_claude_agent_detach_never_calls_a_lifecycle_endpoint():
    app = (STATIC / "app.js").read_text()

    assert '$("#claude-agent-detach").addEventListener("click", detachSelectedStream)' in app
    assert '$("#claude-agent-detach-external").addEventListener("click", detachSelectedStream)' in app


def test_render_selection_branches_for_claude_agent_without_disturbing_design_branch():
    app = (STATIC / "app.js").read_text()

    assert "const claudeAgent = selectedClaudeAgent()" in app
    assert '$("#cell-control-panel").hidden = Boolean(design) || Boolean(claudeAgent)' in app
    assert '$("#claude-agent-control-panel").hidden = !claudeAgent' in app
    # The pre-existing design branch must remain intact (unchanged behavior).
    assert "renderDesignControls(design)" in app


def test_claude_agent_start_form_and_daemon_panel_use_existing_control_form_styles():
    css = (STATIC / "style.css").read_text()
    for selector in (
        ".claude-agents-pane",
        ".daemon-panel",
        ".daemon-stop-controls",
        ".ownership-chip",
        ".claude-agent-control-panel",
        ".claude-agent-external-log",
    ):
        assert selector in css
