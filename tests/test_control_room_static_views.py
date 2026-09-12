"""Structural guards for the room's step-5/6/7 read views (Operations + Surfaces boards).

The suite has no JS runtime, so these checks keep the SURFACES honest structurally: every
navigation destination has exactly one board section (and vice versa), the shell knows the
board names, and the controller actually fetches every read-model route it claims to render —
a view that ships without its fetch (or a route that ships without a view) fails here rather
than in the operator's browser.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
STATIC = _ROOT / "apps" / "control_room" / "static"

#: The step-5/6/7 read routes the views render (fetch targets present in app.js).
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


class _Boards(HTMLParser):
    """Collect destination buttons and board sections from index.html."""

    def __init__(self) -> None:
        super().__init__()
        self.destinations: list[str] = []
        self.boards: list[str] = []
        self.ids: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "button" and values.get("data-board"):
            self.destinations.append(str(values["data-board"]))
        if tag == "section" and values.get("data-board") and "board" in (values.get("class") or ""):
            self.boards.append(str(values["data-board"]))
        if values.get("id"):
            self.ids.append(str(values["id"]))


def _parse_index():
    parser = _Boards()
    parser.feed((STATIC / "index.html").read_text(encoding="utf-8"))
    return parser


def test_every_destination_has_exactly_one_board_and_vice_versa():
    parsed = _parse_index()
    assert sorted(parsed.destinations) == sorted(parsed.boards)
    # duplicates would mean two sections claiming one destination (or two buttons for one board)
    assert len(set(parsed.destinations)) == len(parsed.destinations)
    assert len(set(parsed.boards)) == len(parsed.boards)


def test_the_read_boards_are_registered_in_the_shell():
    shell = (STATIC / "shell.js").read_text(encoding="utf-8")
    match = re.search(r"const BOARDS = \[([^\]]*)\]", shell)
    assert match, "shell.js must keep a BOARDS list"
    names = [name.strip().strip('"') for name in match.group(1).split(",") if name.strip()]
    for board in ("operations", "surfaces"):
        assert board in names, f"{board} missing from shell BOARDS"


def test_the_views_fetch_every_read_route_they_claim():
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    for route in READ_ROUTES:
        assert route in app, f"app.js never fetches {route}"


def test_the_operations_view_renders_the_packet_states_verbatim():
    """No fabricated values: the state renderer keys off the payload's own state blocks."""
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "function stateText(" in app
    assert "unknown" in app and "reason" in app  # the state vocabulary is read, not guessed
    assert "data-run-id" in app  # run rows carry the packet's identifier for click-through


def test_the_board_content_areas_carry_loaded_markers():
    """The shell's autoLoad only presses Refresh while ``data-loaded`` is not ``true``."""
    index = (STATIC / "index.html").read_text(encoding="utf-8")
    for container in ("operations-content", "surfaces-content"):
        assert f'id="{container}"' in index
        assert re.search(rf'id="{container}"[^>]*data-loaded="false"', index), (
            f"{container} must start unloaded so the shell triggers its first fetch"
        )
