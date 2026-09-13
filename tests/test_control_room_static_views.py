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


# ── R3 (build step 6): the constraint ledger, measured health, composition bars ──────────────


def test_r3_cost_is_a_labelled_ledger_with_provenance_not_money_cards():
    """R3a: the five ``ON-G4`` values render as a RULED constraint ledger.

    Synthesis v2 §5.5 corrects v1's "call-centre KPI treatment": R3a is a bounded constraint
    ledger attached to the roster, not money cards. Each of the five values is one labelled row
    carrying the packet's own source + age, and the visible block provenance (`#cost-prov`) the
    render gate reads stays filled. Unknowns stay labelled.
    """
    client = (STATIC / "app.js").read_text(encoding="utf-8")
    css = (STATIC / "style.css").read_text(encoding="utf-8")

    assert "function renderCost(" in client
    for field in ("money.spend", "money.burn", "money.quota", "money.wallet", "money.leases"):
        assert f'"{field}"' in client, field
    # A ledger row with per-value provenance (source + age travel with the value).
    assert "cost-row" in client
    assert '"data-source"' in client
    assert '"data-age-seconds"' in client
    assert "cost-prov-row" in client
    assert 'document.getElementById("cost-prov")' in client
    # The old 3-column money-card grid is gone; the ledger is a ruled single-column list.
    assert "grid-template-columns: repeat(3, 1fr); grid-auto-rows: 32px" not in css
    assert ".cost-grid .field.cost-row" in css
    assert ".cost-grid .cost-prov-row" in css


def test_r3_health_reads_measured_statuses_not_a_composite_score():
    """R3b: the health detail mirrors the packet's MEASURED state + worst age.

    Synthesis v2 §5.4 retires v1's "one computed health score" (it has no measured source).
    The two bounded lines read ``health_detail``/``system``/``trust`` verbatim and expose the
    state, worst age and projector lag as evidence — the renderer computes no aggregate.
    """
    client = (STATIC / "app.js").read_text(encoding="utf-8")

    assert "function renderHealth(" in client
    for anchor in (
        "glance.health_detail",
        "glance.trust",
        "projection_state",
        '"data-measure"',
        '"data-state"',
        '"data-age-seconds"',
        '"data-lag"',
    ):
        assert anchor in client, anchor
    # No client-derived vanity score over the health fields.
    assert "healthScore" not in client
    assert "function healthScore" not in client
    assert "data-health-score" not in client


def test_r3_composition_states_buckets_in_words_plus_bounded_token_split_bars():
    """R3c: the marginals keep full bucket words and add a packet-derived stacked bar.

    The bar is a NON-FIELD affordance: its proportions come only from the packet's parsed bucket
    counts, and a split the packet cannot state degrades to ONE explicit unknown segment rather
    than a fabricated full bar.
    """
    client = (STATIC / "app.js").read_text(encoding="utf-8")
    css = (STATIC / "style.css").read_text(encoding="utf-8")

    assert "function renderComposition(" in client
    assert "function compositionBar(" in client
    assert "function bucketCount(" in client
    assert '"data-composition-bar": ""' in client
    assert '"data-seg": name' in client
    assert 'bar.setAttribute("data-bar-state", "unknown")' in client
    # Buckets stay full words (never t/o/u shorthand).
    assert '["top", "other", "unknown"]' in client
    # The bar is styled, and the unknown split keeps a shape in forced colors.
    assert ".marginal-bar" in css
    assert ".marginal-seg" in css
    assert '.marginal-seg[data-seg="unknown"]' in css


# ── R4 (build step 7): the selection dock's transcript / tools / diff affordances ────────────
#
# The synthesis turns R4 into a real session surface: a list+detail split whose DETAIL pane offers
# the selected run's transcript, its tool calls, and its change evidence. The suite has no JS
# runtime, so these keep the AFFORDANCES honest structurally — the three views exist, they read
# only routes the server already registers, and none of them fabricates a value it did not read.


def test_r4_dock_exposes_transcript_tools_diff_views():
    """The dock carries exactly the three detail views, and starts on the transcript.

    The switcher is a `role="tablist"` of `data-dock-tab` buttons (never `data-region` /
    `data-answer`), so it cannot disturb the resting contract; the worker region defaults to
    `data-dock-view="transcript"` and the recorded-change pane shares its `data-dock-region`.
    """
    html = (STATIC / "index.html").read_text(encoding="utf-8")

    assert 'data-dock-region="worker"' in html
    assert 'data-dock-view="transcript"' in html
    for view in ("transcript", "tools", "diff"):
        assert f'data-dock-tab="{view}"' in html, view
    # The diff pane is app-owned and exists inside the worker region (no new sub-region).
    assert 'id="dock-change"' in html and "data-dock-change" in html
    # The switcher is tabs of real buttons, never links that would navigate the roster.
    assert 'role="tablist"' in html
    tools_tab = html.split('data-dock-tab="tools"', 1)[1].split(">", 1)[0]
    assert "href" not in tools_tab


def test_r4_tools_view_narrows_the_one_transcript_feed():
    """TOOLS is a filter over the SAME worker stream — no second stream, no second endpoint.

    A tool frame is marked with `data-tool` and carries an expandable recorded input/output; the
    tools view hides the non-tool rows via `data-dock-view`, and an empty tools view says so
    explicitly instead of rendering a blank pane.
    """
    client = (STATIC / "parity.js").read_text(encoding="utf-8")
    css = (STATIC / "style.css").read_text(encoding="utf-8")

    assert "function appendToolDetail(" in client
    assert '"data-tool"' in client
    assert '"data-tool-toggle"' in client
    assert 'data-dock-view="tools"' in css
    assert ".feed-entry:not([data-tool])" in css
    # The empty state is a real (hidden) line, shown only when the view has no tool frames.
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert "No tool calls recorded for this run." in html
    # The same EventSource helper still opens the one selected stream.
    assert "new window.EventSource(\"/api/events/" in client


def test_r4_diff_view_reads_the_existing_run_route_and_never_fabricates_a_patch():
    """DIFF is the run's recorded CHANGE evidence over the EXISTING per-run read model.

    The portal owns no git-patch endpoint and step 7 adds none, so the view states what it
    renders (recorded change receipts) and degrades to a named unavailable state; it never
    draws a patch it did not read.
    """
    client = (STATIC / "parity.js").read_text(encoding="utf-8")

    assert "function loadChangeEvidence(" in client
    assert '"/api/runs/"' in client  # the existing route only
    assert '"data-change-candidate"' in client
    assert "recorded change receipts" in client
    # The failure modes are named, never blank and never a fabricated all-clear.
    assert "Change evidence unavailable" in client
    assert "no recorded run binding" in client


def test_r4_detail_views_switch_without_leaving_the_dock():
    """The three views are a switch on ONE selected run; the roster is never navigated away.

    `setDockView` flips `data-dock-view` and the tabs' `aria-selected`; it calls no navigation
    and opens no new window, so list+detail holds (the list stays behind the dock).
    """
    client = (STATIC / "parity.js").read_text(encoding="utf-8")

    assert "function setDockView(" in client
    assert '"data-dock-view"' in client
    assert "aria-selected" in client
    assert "window.location" not in client
    assert "window.open(" not in client
