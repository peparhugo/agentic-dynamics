"""Browser-free structural verification for the vanilla Control Room client.

The repository intentionally has no JavaScript runtime dependency. These tests
therefore lock down the DOM and source-level invariants that connect the pure
core helpers to the page, while behavioral telemetry parsing is covered by the
shared event fixtures in ``test_admin_server.py``.
"""

from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "apps" / "control_room" / "static"


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
    assert "if (state.statusSource) return" in app
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


def test_subscription_usage_panel_surfaces_cache_and_explicit_states():
    """Usage wiring keeps balances, estimates, cache age, and failures visible."""
    html = (STATIC / "index.html").read_text()
    app = (STATIC / "app.js").read_text()

    assert 'id="usage-refresh"' in html
    assert '"/api/subscription-usage?refresh=1"' in app
    assert "usageRequestInFlight" in app
    assert "cache.age_seconds" in app
    assert "DeepSeek wallet balance" in app
    assert "DeepSeek platform meter · 14d" in app
    assert "DeepSeek lifetime spend" in app
    assert "usageError" in app
    assert "usageEmpty" in app
    assert "data-usage-refresh-error" in app


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
    assert (
        "Enqueue"
        not in html[html.index('id="design-control-panel"') : html.index('class="recent-designs"')]
    )


def test_design_client_reuses_one_stream_and_server_capability_gates():
    """Selection and validation extend, rather than fork, established machinery."""
    app = (STATIC / "app.js").read_text()

    assert "function selectDesignSession(portalId, attach)" in app
    assert "if (state.eventSource) state.eventSource.close()" in app
    assert "connectSelectedStream()" in app
    assert "!state.draftFresh || !draft?.capabilities?.save" in app
    assert "!state.draftFresh || !draft?.capabilities?.run" in app
    assert "fetch(`/api/design-sessions/${encodeURIComponent(selectedAtRequest)}/spec`)" in app
    assert 'delivery === "steer" ? $("#steer-design-input")' in app
    assert "/interrupt`, {})" in app
    assert "detachSelectedStream" in app
    assert (
        'headers: { "Content-Type": "application/json", "Idempotency-Key": mutationKey() }' in app
    )


def test_enqueue_client_sends_idempotency_key():
    """F1: the enqueue mutation carries the shared Idempotency-Key convention."""
    app = (STATIC / "app.js").read_text()

    enqueue_block = app[app.index('fetch("/api/experiments"') : app.index("function mutationKey()")]
    assert (
        'headers: { "Content-Type": "application/json", "Idempotency-Key": mutationKey() }'
        in enqueue_block
    )
    assert "body: JSON.stringify({ action })" in enqueue_block


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
    mobile = css[css.index("@media (max-width: 420px)") :]
    assert ".design-stream-actions" in mobile
    assert "grid-template-columns: minmax(0, 1fr)" in mobile


def test_spend_rail_surfaces_retained_window_truncation():
    """The spend rail labels a truncated retained window instead of hiding it."""
    app = (STATIC / "app.js").read_text()

    assert "history_capped" in app
    assert "RETAINED WINDOW · TRUNCATED" in app
    assert "#spend-provenance" in app


def test_workflow_phase_badge_rendered_on_fleet_cards():
    """The live phase ({index}/{total} {name}) is drawn as a badge on each fleet card."""
    app = (STATIC / "app.js").read_text()
    css = (STATIC / "style.css").read_text()

    # The matrix snapshot feeds per-cell phase data into the fleet rendering.
    assert "state.phases" in app
    assert "data.phases" in app
    assert 'element("span", "phase-badge"' in app
    assert ".phase-badge" in css


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
    assert (
        "delivery"
        not in app[
            app.index("async function submitSupervisorSteer") : app.index(
                "function openSupervisorInterruptDoor"
            )
        ]
    )
    assert "confirmation !== `INTERRUPT ${flag.session_id}`" in app
    assert "grid-template-areas:" in css
    assert '"attention"' in css


def test_pipeline_stages_surface_three_stage_view():
    """The shell renders execute → analyze → review and the client parses them."""
    html = (STATIC / "index.html").read_text()
    app = (STATIC / "app.js").read_text()
    core = (STATIC / "control-room-core.js").read_text()
    css = (STATIC / "style.css").read_text()

    # The shell exposes a dedicated pipeline region named for the three stages.
    assert 'id="pipeline-stages"' in html
    assert 'class="pipeline-stages"' in html
    for stage in ("EXECUTE", "ANALYZE", "REVIEW"):
        assert stage in html

    # The client holds the stage snapshot and renders it from the matrix payload.
    assert "stages: {}," in app
    assert "state.stages = data.stages" in app
    assert "function renderPipelineStages()" in app
    assert "renderPipelineStages()" in app

    # The core status vocabulary recognizes the review worker's retry_N states.
    assert 'status.startsWith("retry_")' in core
    assert "retry: 1" in core

    # Stage cards have their own presentation styles.
    assert ".pipeline-stages" in css
    assert ".pipeline-stage" in css
    assert ".stage-counts" in css


def test_docs_health_panel_renders_three_states_and_never_colour_alone():
    """The docs-drift rail's panel is mounted, and every state carries a word, not just a hue.

    Structural, like the rest of this module — the repo has no JS runtime dependency, so the
    guard is that the page and the client carry the affordances the design requires. The
    behavioural half (which state resolves to which colour, and what the approve button does)
    is covered by ``tests/test_docs_health.py`` against the real route.
    """
    html = (STATIC / "index.html").read_text()
    css = (STATIC / "style.css").read_text()
    app = (STATIC / "app.js").read_text()

    # The panel is mounted in the fleet board, beside the pipeline-stage strip.
    for required in (
        'id="docs-health"',
        'id="docs-health-word"',
        'id="docs-health-glyph"',
        'id="docs-health-headline"',
        'id="docs-health-axes"',
        'id="docs-health-inventory"',
        'id="docs-health-proposal"',
        'id="docs-health-approve-form"',
    ):
        assert required in html, required
    assert html.index('id="pipeline-stages"') < html.index('id="docs-health"')

    # All four conditions have a colour rule, and the two red ones are told apart by their word.
    for condition in ("clean", "findings", "warranted", "unmeasured"):
        assert f'.docs-health[data-condition="{condition}"]' in css, condition
    assert "#docs-health-word" in css

    # The client obeys the server's verdict rather than deriving a colour from a drift count.
    assert "panel.dataset.condition = String(data.condition" in app
    assert "word.textContent = String(data.word" in app
    # The approve affordance is hidden unless the server says the proposal is approvable.
    assert "form.hidden = !proposal.approvable" in app


def test_docs_health_approve_goes_through_the_mutation_trust_gate():
    """The approve affordance posts JSON with an Idempotency-Key derived from the proposal.

    Deriving the key (rather than minting a fresh UUID like the other portal mutations) is what
    makes a double-click replay the first answer instead of reaching the gate twice. The fresh
    key is reserved for the retryable case, where the gate rolled its claim back and the rail is
    genuinely dispatchable again.
    """
    app = (STATIC / "app.js").read_text()

    assert '"/api/docs-health/approve"' in app
    assert "`docs-approve:${proposalId}`" in app
    assert "`docs-approve:${proposalId}:${mutationKey()}`" in app
    assert '"Idempotency-Key": key' in app
    # A poll landing mid-approval must not repaint the form under the operator's hands.
    assert "if (state.docsHealthApprovePending) return" in app
    # An unattributed approval is refused client-side too, so the operator sees why immediately.
    assert "an unattributed approval is not an approval" in app


def test_docs_health_panel_never_falls_back_to_green_on_failure():
    """A fetch failure paints the unmeasured state, not a clean one."""
    app = (STATIC / "app.js").read_text()

    unavailable = app[app.index("function renderDocsHealthUnavailable") :]
    unavailable = unavailable[: unavailable.index("\n  }\n")]
    assert 'condition: "unmeasured"' in unavailable
    assert 'health: "red"' in unavailable
    assert "green" not in unavailable


def test_docs_health_panel_ids_queried_by_the_client_all_exist_in_the_shell():
    """Every ``$("#docs-health-…")`` the client queries is an id the page actually defines.

    A mismatched id is not a visible error — ``$()`` returns null, the guarded render returns
    early, and the panel silently stops updating that field. Structural assertions on individual
    ids cannot catch it, because both sides look fine in isolation; only the correspondence
    between them does. The repository has no JavaScript runtime dependency, so this cross-check
    is how the wiring gets verified without a browser.

    ``docs-health-title`` is defined but not queried on purpose: it is the ``aria-labelledby``
    target for the panel's section, so it exists for the accessibility tree rather than for the
    client to write into.
    """
    import re

    app = (STATIC / "app.js").read_text()
    html = (STATIC / "index.html").read_text()

    queried = set(re.findall(r'\$\("#(docs-health[a-z-]*)"\)', app))
    defined = set(re.findall(r'id="(docs-health[a-z-]*)"', html))

    assert queried, "the client no longer queries the docs-health panel at all"
    assert queried <= defined, (
        f"client queries ids the page does not define: {sorted(queried - defined)}"
    )
    assert defined - queried == {"docs-health-title"}, sorted(defined - queried)


# ── live board (the phases board distinguishes LIVE runs from history) ──
#
# The four states the spec names — fresh-phase live, old-phase historical with age, no-timestamp
# historical age-unknown, and the live/all filter — are all structural here: the browser-free
# guard is that the shell mounts the LIVE NOW section above the board, the client renders it from
# the API's live dimension, the pure fleet vocabulary handles the live filter + newest-first
# order, and the styles exist. The behavioral half (which timestamp yields which state) is covered
# in ``tests/test_admin_server.py`` against the real route.


def test_live_now_section_mounted_above_the_full_board():
    """LIVE NOW renders above the board: the section precedes the filter controls and grid."""
    html = (STATIC / "index.html").read_text()

    for required in (
        'id="live-now"',
        'id="live-now-title"',
        'id="live-now-count"',
        'id="live-now-list"',
        "window: 10m · last published phase",
        "No runs are live within the window.",
    ):
        assert required in html, required
    assert html.index('id="live-now"') < html.index('class="fleet-controls"')
    assert html.index('class="fleet-controls"') < html.index('id="fleet-grid"')
    # The live/all filter chip joins the existing status chips.
    assert 'data-filter="live"' in html
    assert 'data-filter="all"' in html


def test_client_renders_live_now_from_the_api_live_dimension():
    """app.js consumes the live dimension and renders LIVE NOW + card ages."""
    app = (STATIC / "app.js").read_text()

    # The phase entries now carry the live dimension the API emits.
    assert "age_seconds" in app
    assert "renderLiveNow" in app
    assert "liveNowRows" in app
    assert "fleet.livePhaseEntries" in app
    # The live/all filter passes the live cell set into the fleet facet.
    assert "liveIds" in app
    assert "filter: state.filter" in app
    # Card badges carry their age ("4/7 rerun_contaminated · 2m ago"), and age-unknown is its
    # own word, never a number that could be read as fresh.
    assert "phaseBadgeLabel" in app
    assert "age unknown" in app
    assert "formatAgeSeconds" in app
    # LIVE NOW rows are the same read-only drill-down as fleet cards.
    assert '$("#live-now-list").addEventListener("click"' in app
    assert 'closest(".live-now-row")' in app


def test_board_fleet_handles_live_filter_and_orders_live_newest_first():
    """The pure fleet vocabulary owns the live filter and the newest-first order."""
    fleet = (STATIC / "board-fleet.js").read_text()

    # The live filter consults the phase-liveness set the client passes in the facet.
    assert 'filter === "live"' in fleet
    assert "facet?.liveIds?.has(cellId)" in fleet
    # LIVE NOW content is ordered newest first by the normalized last_phase_ts.
    assert "livePhaseEntries" in fleet
    assert "last_phase_ts" in fleet
    assert "live === true" in fleet


def test_live_now_styles_are_present():
    """The LIVE NOW section and rows have their own presentation."""
    css = (STATIC / "style.css").read_text()

    for selector in (
        ".live-now",
        ".live-now-header",
        ".live-now-count",
        ".live-now-list",
        ".live-now-row",
        ".live-now-row.selected",
        ".live-now-row .live-age",
    ):
        assert selector in css, selector
