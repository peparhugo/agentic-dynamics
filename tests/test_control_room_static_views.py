"""Structural guards for the restored room's board surfaces (Operations + Surfaces).

The 2026-09-18 restoration (PR #84) made the seven destination boards the room the server
actually serves; the single-screen workbench (``parity.js``) is parked in-tree but unloaded.
The suite has no JS runtime, so these checks keep the LOADED surfaces honest structurally:
every board names a destination and a section in ``index.html``, and every assertion derives
its inputs from the scripts ``index.html`` actually loads. That derivation is the point of the
2026-09-18 review finding: a test that reads a parked module can pass while the served page has
lost the feature — the safe-actions assertion survived the restoration that way.

Parked-module guards (``parity.js`` / ``charts.js`` / ``visuals.js`` stay in-tree until the
restored room proves replacement) live in the suites that name them as parked
(``test_control_room_glance_integrity.py`` / ``test_admin_frontend.py``); nothing here reads a
script the page does not load.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
STATIC = _ROOT / "apps" / "control_room" / "static"

#: The step-5/6/7 read routes the views render (fetch targets present in the client scripts).
READ_ROUTES = (
    "/api/operations",
    "/api/runs/",
    "/api/quality",
    "/api/value",
    "/api/arms/compare",
    "/api/queue/sla",
    "/api/escalations",
    "/api/batch",
    "/api/energy",
    "/api/stories/",
)

#: The restored room's seven read boards (the destination-board equivalent of the lenses).
READ_BOARDS = ("fleet", "status", "flags", "sessions", "routing", "operations", "surfaces")


def _index_text() -> str:
    return (STATIC / "index.html").read_text(encoding="utf-8")


def _loaded_script_names() -> tuple[str, ...]:
    """The scripts ``index.html`` actually loads, in document order.

    Derived from the markup, never a second roster: a script the page does not load is not
    part of the served surface, and a test that reads it proves nothing about the page.
    """
    srcs = re.findall(r'<script[^>]+src="([^"]+)"', _index_text())
    return tuple(Path(src.strip()).name for src in srcs if src.strip().endswith(".js"))


def _loaded_scripts() -> str:
    """The text of every script the restored page actually loads."""
    return "\n".join((STATIC / name).read_text(encoding="utf-8") for name in _loaded_script_names())


def test_every_read_board_has_exactly_one_destination_and_section():
    """The restored room's contract (2026-09-18): one destination entry and one section per
    read board — the equivalent of the workbench's one-panel-per-lens rule."""
    index = _index_text()
    for board in READ_BOARDS:
        assert len(re.findall(rf'<button[^>]*data-board="{board}"', index)) == 1, (
            f"{board} must have exactly one destination entry"
        )
        assert len(re.findall(rf'id="board-{board}"', index)) == 1, (
            f"{board} must have exactly one board section"
        )


def test_the_loaded_shell_board_roster_matches_the_markup():
    """The loaded shell's own BOARDS list and the markup's destinations are one roster."""
    shell = (STATIC / "shell.js").read_text(encoding="utf-8")
    match = re.search(r"const BOARDS = \[(.*?)\]", shell, re.S)
    assert match, "shell.js must declare the board roster it activates"
    names = re.findall(r'"([^"]+)"', match.group(1))
    assert names == list(READ_BOARDS), (
        f"shell.js BOARDS {names} drifted from the seven restored boards {list(READ_BOARDS)}"
    )
    index = _index_text()
    for board in names:
        assert f'data-board="{board}"' in index, (
            f"shell.js activates {board}, but the markup has no destination for it"
        )


def test_the_views_fetch_every_read_route_they_claim():
    source = _loaded_scripts()
    for route in READ_ROUTES:
        assert route in source, f"the loaded client never fetches {route}"


def test_the_operations_view_renders_the_packet_states_verbatim():
    """No fabricated values: the loaded renderer keys off the payload's own state blocks."""
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "function stateText(" in app
    assert "unknown" in app and "reason" in app  # the state vocabulary is read, not guessed
    assert "dataset.runId = runId" in app  # run rows carry the packet's identifier


def test_operations_board_renders_the_packet_fields_it_claims():
    """The restored Operations board renders the packet fields it actually reads: the summary
    source, server-owned summaries, active runs, attention, degraded surfaces, projection lag,
    workers, safe actions, and the complete state-screen roster.
    """
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    for anchor in (
        "data.source",
        "active_runs",
        "promotable_runs",
        "data.attention",
        "data.degraded",
        "projection_lag",
        "summaryData.active_runs",
        "worker_health",
        "safe_actions",
        "state_screens",
        "State screens",
    ):
        assert anchor in app, f"the restored Operations renderer does not read {anchor}"


def test_non_home_boards_start_hidden_so_one_board_shows_at_rest():
    """One board visible at rest; every other board starts hidden (the room's lazy-load rule)."""
    index = _index_text()
    for board in READ_BOARDS:
        match = re.search(rf'<section id="board-{board}"[^>]*>', index)
        assert match, f"{board}: board section missing"
        hidden = "hidden" in match.group(0)
        if board == "fleet":
            assert not hidden, "the home board must be visible at rest"
        else:
            assert hidden, f"{board} must start hidden (exactly one board at rest)"


def test_shell_never_queries_an_empty_selector():
    """The review's small shell failure: `$("")` throws and skips persistence/scroll-reset."""
    shell = (STATIC / "shell.js").read_text(encoding="utf-8")
    assert 'loaders[board] || ""' not in shell
    assert "if (!selector) return" in shell


def test_restored_board_load_is_initialized_after_its_handlers():
    """shell.js boots before app.js, so its automatic first-visit load must be re-run after the
    data layer binds the board controls. A reload on Operations/Surfaces/Routing otherwise
    restores the board with no load request at all until the operator revisits it (the
    2026-09-18 review's reproduction)."""
    shell = (STATIC / "shell.js").read_text(encoding="utf-8")
    assert "function initializeBoard(" in shell
    assert "initializeBoard," in shell.split("const shell = {", 1)[1], (
        "initializeBoard must be on the shell's public surface"
    )
    assert "autoLoadBoard(document.body.dataset.board" in shell
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    bound = app.index("bindSurfaceViews()")
    initialized = app.index("ControlRoomShell")
    assert initialized > bound, (
        "the active board must be initialized only after its handlers are bound"
    )


def test_run_drawer_focus_enters_on_open_and_returns_to_the_row():
    """The restored drawer keeps #83's keyboard contract: Enter opens the drawer and focus
    moves to its close control (so the drawer-scoped Escape is reachable immediately); closing
    returns focus to the originating row."""
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    open_start = app.index("async function openRunDetail")
    open_end = app.index("function closeRunDetail")
    open_body = app[open_start:open_end]
    saved = open_body.index("state.runDetailReturnFocus = document.activeElement")
    focused = open_body.index('$("#run-detail-close").focus()')
    assert saved < focused, "the originating row must be saved before focus moves into the drawer"
    close_body = app[open_end : app.index("function objectTable")]
    assert "state.runDetailReturnFocus?.focus?.()" in close_body, (
        "closing the drawer must restore focus to the originating row"
    )


def test_unavailable_payloads_render_their_names_not_blanks():
    """200-with-error objects and `degraded` lists are rendered, never shown as empty truth."""
    source = _loaded_scripts()
    # the run detail surfaces the service's named error object
    assert "Run detail unavailable:" in source
    # operations treats a degraded control db as unavailable, not zero, and offers no
    # fabricated all-clear
    assert "dbDegraded" in source
    assert "could not be read" in source
    # the quality panel renders the degraded list it is handed (A7), never an all-clear
    assert "data.degraded.map((d) => d.surface)" in source
    # a failed surface panel names its reason and URL
    assert "unavailable — " in source


def test_run_drawer_renders_the_run_inspection_blocks():
    """The loaded drawer renders the additive run-inspection slice.

    The drawer must show the cost's provenance, the independent verification SEPARATE from the
    agent's own claim (SAID vs MEASURED), the delivered knowledge, the prepared-step reference,
    and timings carrying a measured/unknown state — the anchors the render gate then exercises
    behaviorally.
    """
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    for anchor in (
        "Delivered knowledge",
        "Prepared step",
        "Timings",
        "Verification",
        "renderDeliveredKnowledge",
        "renderPreparedStep",
        "renderTimings",
        "verificationLine",
        "dataset.costProvenance",
        "dataset.verification",
        "dataset.deliveredPhase",
        "dataset.preparedStepPath",
        "selected — use not established",
        "tr.dataset.state",
    ):
        assert anchor in app, anchor


def test_run_drawer_renders_the_job_log_blocks():
    """The drawer's Logs block: the job's recorded tail renders as entries, an unbound read is
    NAMED (never an empty success), and the live follow reuses the room's /api/events stream."""
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    for anchor in (
        "renderRunLogs",
        "dataset.logState",
        "dataset.logEntry",
        "Follow live",
        "api/events/",
        "closeRunLogStream",
        "run-log",
        "normalizeRunLogEvent",
        "run-log-timestamp",
        "run-log-id",
        "run-log-tool",
        "run-log-tool-input",
        "run-log-tool-output",
        "run-log-part-id",
        "run-log-child-session-id",
        "run-log-malformed",
        "runLogEntry(event, { live: true })",
        "renderActivityMetadata",
        "data-activity-surface",
        "childActivityState",
        "cellIds",
        "resolutionBasis",
        'source.addEventListener("replay_complete"',
    ):
        assert anchor in app, anchor


def test_run_drawer_follow_gate_exercises_the_server_bound_cell():
    """The acceptance gate must click the drawer and inspect its emitted EventSource request.

    The fixture's run id and log cell id are different. Requiring the gate to compare the actual
    request with the fixture's ``logs.cell_id`` prevents a source-only or dataset-only assertion
    from silently accepting a requested-id fallback.
    """
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    gate = (_ROOT / "scripts" / "verify_control_room_rendering.py").read_text(encoding="utf-8")
    render_start = app.index("function renderRunLogs(logs)")
    render_end = app.index("/** Toggle the drawer's live follow", render_start)
    render_body = app[render_start:render_end]
    assert 'follow.dataset.logFollow = logs.cell_id || ""' in render_body
    assert "toggleRunLogStream(follow.dataset.logFollow, follow)" in render_body
    assert "with page.expect_request(" in gate
    assert "follow_button.click()" in gate
    assert 'load_boards_fixture()["run_detail"]["logs"]["cell_id"]' in gate
    assert "urlparse(follow_request.value.url).path" in gate
    assert '"drawer-logs-follow"' in gate


def test_run_drawer_fixture_carries_rich_event_evidence():
    """The acceptance fixture names every rich field the drawer and live feed must preserve."""
    fixture = json.loads(
        (_ROOT / "apps/control_room/verification/fixtures/boards_endpoints.json").read_text(
            encoding="utf-8"
        )
    )
    event = fixture["run_detail"]["logs"]["events"][2]
    assert event == {
        "ts": "2026-09-18T19:19:00Z",
        "timestamp": "2026-09-18T19:19:00Z",
        "class": "step_finish",
        "text": "phase verify ok",
        "id": "event-fixture-0003",
        "part_id": "part-fixture-0003",
        "tool": "pytest",
        "tool_input": "tests/test_control_room_static_views.py",
        "tool_output": "3 passed",
        "child_session_id": "child-fixture-0003",
        "malformed": False,
    }


def test_run_detail_fixture_carries_server_owned_child_activity_scope():
    """The acceptance fixture binds the same child scope to drawer and transcript surfaces."""
    fixture = json.loads(
        (_ROOT / "apps/control_room/verification/fixtures/boards_endpoints.json").read_text(
            encoding="utf-8"
        )
    )
    logs = fixture["run_detail"]["logs"]
    activity = logs["child_activity"]
    assert logs["cell_ids"] == ["fixture-job-0001"]
    assert logs["resolution_basis"] == "by_run_id"
    assert activity["state"] == "recorded"
    assert activity["cell_ids"] == logs["cell_ids"]
    assert activity["resolution_basis"] == logs["resolution_basis"]
    assert activity["slice_bound"] == logs["slice_bound"]


def test_transcript_liveness_uses_recorded_age_and_names_unknown_timestamp():
    """Replay receipt time cannot turn an old or untimestamped event into LIVE evidence."""
    core = (STATIC / "control-room-core.js").read_text(encoding="utf-8")
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "function recordedAgeSeconds(value, now = Date.now())" in core
    assert "function recordedLiveness(value, now = Date.now(), liveWindowSeconds = 600)" in core
    assert 'state: "unknown", age_seconds: null, label: "age unknown"' in core
    assert '"stale"' in core
    assert 'timestamp: "timestamp unavailable"' in core
    assert "state.lastEventAt = Date.now()" not in app
    receive_start = app.index("function receiveEvent(raw)")
    receive_end = app.index("/** Append one browser-generated artifact row", receive_start)
    receive_body = app[receive_start:receive_end]
    assert "row.recorded_state" in receive_body
    assert "state.streamState = row.recorded_state" in receive_body
    assert "Date.now()" not in receive_body
    assert 'run-log-age", "recorded age"' in app
    assert 'if (normalized.recorded_state === "live") entry.dataset.logLive = "true"' in app
    assert "if (options.live) normalized.live = true" not in app


def test_child_absence_is_validated_against_the_displayed_bound():
    """The client consumes server-owned bounded metadata and never scans a broader event tail."""
    core = (STATIC / "control-room-core.js").read_text(encoding="utf-8")
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "function boundedActivity(source)" in core
    assert "absence evidence is not bounded to the displayed slice" in core
    metadata_start = app.index("function renderActivityMetadata(metadata, surface)")
    metadata_end = app.index("/** Build one terminal row", metadata_start)
    metadata_body = app[metadata_start:metadata_end]
    assert "core.boundedActivity(source)" in metadata_body
    assert "source.events" not in metadata_body
    assert "activity.slice_bound ?? source.slice_bound" in metadata_body
