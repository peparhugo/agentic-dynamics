"""Structural guards for the room's step-5/6/7 read views (Operations + Surfaces lenses).

The facelift supersedes the old destination-board portal: main's step-5/6/7 read views are
re-housed as workbench lenses inside the refreshed presentation (``parity.js``), while the
routes they render stay registered on the server. The suite has no JS runtime, so these checks
keep the SURFACES honest structurally: every read view names a panel in ``index.html`` and a
lens in ``parity.js``'s PANELS registry, and the client actually fetches every read-model
route it claims to render — a view that ships without its fetch (or a route that ships without
a view) fails here rather than in the operator's browser.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
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

#: The step-5/6/7 read lenses re-housed into the workbench (index.html panel + parity.js).
READ_LENSES = ("operations", "surfaces")


class _Workbench(HTMLParser):
    """Collect the workbench lens panels from index.html."""

    def __init__(self) -> None:
        super().__init__()
        self.lenses: list[str] = []
        self.hidden: dict[str, bool] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        lens = values.get("data-lens")
        if tag == "section" and lens:
            self.lenses.append(str(lens))
            self.hidden[str(lens)] = "hidden" in values


def _parse_index():
    parser = _Workbench()
    parser.feed((STATIC / "index.html").read_text(encoding="utf-8"))
    return parser


def _presentation_scripts() -> str:
    """The refreshed client scripts; the read views live in ``parity.js``, the glance in app.js."""
    return "\n".join(
        (STATIC / name).read_text(encoding="utf-8") for name in ("app.js", "parity.js")
    )


def test_every_read_lens_has_exactly_one_workbench_panel():
    parsed = _parse_index()
    # duplicates would mean two sections claiming one lens
    assert len(set(parsed.lenses)) == len(parsed.lenses)
    for lens in READ_LENSES:
        assert lens in parsed.lenses, f"{lens} missing its workbench panel"
        assert parsed.hidden.get(lens) is True, f"{lens} must start hidden (lazy-loaded at rest)"


def test_the_read_lenses_are_registered_in_the_workbench_panels():
    parity = (STATIC / "parity.js").read_text(encoding="utf-8")
    match = re.search(r"var PANELS = \[(.*?)\];", parity, re.S)
    assert match, "parity.js must keep a PANELS registry"
    names = re.findall(r'id: "([^"]+)"', match.group(1))
    for lens in READ_LENSES:
        assert lens in names, f"{lens} missing from the workbench PANELS"


def test_the_views_fetch_every_read_route_they_claim():
    source = _presentation_scripts()
    for route in READ_ROUTES:
        assert route in source, f"the client never fetches {route}"


def test_the_operations_view_renders_the_packet_states_verbatim():
    """No fabricated values: the state renderer keys off the payload's own state blocks."""
    parity = (STATIC / "parity.js").read_text(encoding="utf-8")
    assert "function stateText(" in parity
    assert "unknown" in parity and "reason" in parity  # the state vocabulary is read, not guessed
    assert "data-run-id" in parity  # run rows carry the packet's identifier for click-through


def test_the_read_panels_start_hidden_so_the_workbench_lazy_loads():
    """The lens panels are hidden at rest; the workbench nav opens one on demand."""
    parsed = _parse_index()
    for lens in READ_LENSES:
        assert parsed.hidden.get(lens) is True


# ── wave A7: availability handling + the shell guard ─────────────────────────


def test_shell_never_queries_an_empty_selector():
    """The review's small shell failure: `$("")` throws and skips persistence/scroll-reset."""
    shell = (STATIC / "shell.js").read_text(encoding="utf-8")
    assert 'loaders[board] || ""' not in shell
    assert "if (!selector) return" in shell


def test_unavailable_payloads_render_their_names_not_blanks():
    """200-with-error objects and `degraded` lists are rendered, never shown as empty truth."""
    source = _presentation_scripts()
    # the run detail surfaces the service's named error object
    assert "Run detail unavailable:" in source
    # SLA + batch + quality panels all render their degraded list
    assert source.count("data.degraded || []") >= 3
    # operations treats a degraded control db as unavailable, not zero, and offers no
    # fabricated all-clear
    assert "dbDegraded" in source
    assert "could not be read — decisions owed cannot be listed" in source


def test_operations_renders_the_packet_safe_actions():
    source = _presentation_scripts()
    assert "data.safe_actions" in source
    assert "Safe actions" in source
