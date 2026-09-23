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
    source, active/promotable runs, attention, degraded surfaces, projection lag, workers.

    Safe actions and named state screens are served by the same Operations payload and are
    asserted separately below; the served board remains the acceptance target, never the parked
    workbench.
    """
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    for anchor in (
        "data.source",
        "active_runs",
        "promotable_runs",
        "data.attention",
        "data.degraded",
        "projection_lag",
        "unhealthy_workers",
    ):
        assert anchor in app, f"the restored Operations renderer does not read {anchor}"


def test_operations_board_consumes_server_owned_triage_age_and_state_screens():
    """The browser preserves the Operations wire order and does not recreate its decisions."""
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    for anchor in (
        "Array.isArray(data.runs)",
        'entry["attention.state"]',
        'entry["attention.kind"]',
        "run.started_age",
        "state_screens",
        "Safe actions",
        "State screens",
    ):
        assert anchor in app, anchor
    assert "runs.sort(" not in app
    assert "formatAge(entry.started_at)" not in app


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
    ):
        assert anchor in app, anchor
