"""Feature-parity guard for the Control Room UI/UX refresh (work order a1).

The merge that landed the refresh (``0244f3315``) resolved ``apps/control_room/static/app.js``
to the refresh side *wholesale*: the refreshed one-resting-screen client hydrates from
``GET /api/glance``, and main's step-5/6/7 read views — the Operations board, the Surfaces
board and its A7 unavailability rendering, the step-12 batch lane, the routing board, the
registry board and the subscription-usage board — were re-housed only partially (some in
``parity.js``'s workbench lenses, some not at all). ``tests/test_control_room_static_views.py``
already proves the *lenses* exist; this suite proves the *features inside them* survived.

It is deliberately browser-free and reads the refreshed static modules as text. Anchors are a
mix of function names, identifier strings and DOM ids — the "where it must live post-rework"
column of ``docs/reviews/control_room_refresh_feature_parity.md``. It is EXPECTED TO FAIL on
the pre-rework tree: each failing test names the main-side anchors that have no home yet.

Behaviour is pinned, not snapshots: any implementation that exposes the pinned function/string
and renders the same payload fields passes, regardless of formatting or renaming of private
helpers (``dataTable`` -> ``table`` is already such a rename, so we pin the behaviour).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.fast

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "apps" / "control_room" / "static"

#: The scripts the refreshed index.html actually loads — the refreshed presentation. main's
#: helpers must be ported into one of these (parity.js is the natural host).
REFRESH_MODULES = ("app.js", "charts.js", "visuals.js", "parity.js")


def _module_text(*names: str) -> str:
    """Concatenate the refreshed static modules named."""
    return "\n".join((STATIC / name).read_text(encoding="utf-8") for name in names)


def _refresh_text() -> str:
    """The text of every script the refreshed client loads."""
    return _module_text(*REFRESH_MODULES)


def _index_text() -> str:
    """The refreshed shell markup (the DOM the lenses re-house main's views into)."""
    return (STATIC / "index.html").read_text(encoding="utf-8")


def _surface_text() -> str:
    """The whole refreshed static surface (markup + loaded modules)."""
    return _index_text() + "\n" + _refresh_text()


def _script_srcs() -> list[str]:
    """The ``src`` of every classic script tag the refreshed shell loads, in order."""
    return re.findall(r'<script[^>]+src="([^"]+)"', _index_text())


def _missing(source: str, anchors: tuple[str, ...]) -> list[str]:
    """The anchors absent from ``source`` (a single failure names the whole gap)."""
    return [anchor for anchor in anchors if anchor not in source]


# ── Controls: the refreshed presentation itself must still be present ─────────────────────────


def test_refreshed_workbench_rehouses_both_read_lenses() -> None:
    """The refresh's own lens homes survive (so a failure below is a lost feature, not a move)."""
    index = _index_text()
    missing = _missing(
        index,
        (
            'data-lens="operations"',
            'data-lens="surfaces"',
            'id="wb-operations"',
            'id="wb-surfaces"',
        ),
    )
    assert not missing, f"refreshed workbench lost its lens panels: {missing}"
    parity = (STATIC / "parity.js").read_text(encoding="utf-8")
    assert re.search(r"var PANELS = \[(.*?)\];", parity, re.S), (
        "parity.js must keep a PANELS registry"
    )


# ── 1. Operations board (main step-5/6/7) ─────────────────────────────────────────────────────


def test_operations_board_helpers_are_rehoused() -> None:
    source = _refresh_text()
    missing = _missing(
        source,
        (
            "function loadOperations",
            "function renderOperations",
            "function openRunDetail",
            "function renderRunDetail",
            "function objectTable",
        ),
    )
    assert not missing, f"Operations board lost main's helpers: {missing}"


def test_operations_board_renders_the_packet_sections() -> None:
    source = _refresh_text()
    missing = _missing(
        source,
        (
            "Control epoch",
            "Repo head",
            "Active runs",
            "Decisions owed",
            "Promotable runs",
            "Unhealthy workers",
            "DEGRADED SURFACES",
            "ATTENTION",
            "SAFE ACTIONS",
            "PROJECTION LAG",
            "ATTEMPTS",
            "GATES",
            "APPROVALS",
            "COMMAND JOURNAL",
        ),
    )
    assert not missing, f"Operations board lost main's sections/labels: {missing}"


def test_operations_rows_click_through_to_run_detail() -> None:
    source = _refresh_text()
    missing = _missing(source, ("data-run-id", "Open run", 'role", "button'))
    assert not missing, f"Operations run click-through lost: {missing}"
    assert "stateText" in source, "the packet state renderer must survive"


# ── 2. A7: unavailability is rendered, never blanked ─────────────────────────────────────────


def test_operations_treats_a_degraded_control_db_as_unavailable_not_zero() -> None:
    source = _refresh_text()
    missing = _missing(source, ("dbDegraded", "could not be read", "unavailable"))
    assert not missing, f"A7 operations unavailability lost: {missing}"


def test_run_detail_renders_the_services_named_error_not_a_blank() -> None:
    source = _refresh_text()
    assert "Run detail unavailable" in source, "the 200-with-error run detail must render by name"


def test_surface_failure_renders_the_named_reason_and_its_url() -> None:
    """Main's ``renderSurfaceError(name, url, error)`` — the A7 per-panel failure state."""
    source = _refresh_text()
    missing = _missing(source, ("function renderSurfaceError", "renderSurfaceError("))
    assert not missing, (
        "the Surfaces board inlines a status-only failure; main rendered each failed panel with "
        f"its named reason AND its URL via renderSurfaceError: {missing}"
    )


def test_panels_render_their_degraded_lists() -> None:
    source = _refresh_text()
    assert source.count("data.degraded || []") >= 3, (
        "quality/SLA/batch panels must render their degraded lists (A7), not an all-clear"
    )


# ── 3. Surfaces board (main step-6/7) ─────────────────────────────────────────────────────────


def test_surfaces_board_fetches_every_read_model_and_dispatches_each_panel() -> None:
    source = _refresh_text()
    missing = _missing(
        source,
        (
            "/api/quality",
            "/api/value",
            "/api/arms/compare",
            "/api/queue/sla",
            "/api/escalations",
            "/api/batch",
            "/api/energy",
            "/api/stories/",
            "function renderSurfacePanel",
            "function renderQualityPanel",
            "function renderValuePanel",
            "function renderArmsPanel",
            "function renderSlaPanel",
            "function renderEscalationPanel",
            "function renderEnergyPanel",
            "function renderStoryArcPanel",
            "function renderStoryArcBody",
            "function loadStoryArc",
        ),
    )
    assert not missing, f"Surfaces board lost read models/panels: {missing}"


# ── 4. The step-12 batch lane ────────────────────────────────────────────────────────────────


def test_step12_batch_lane_renders_measurable_and_modeled_states() -> None:
    source = _refresh_text()
    missing = _missing(
        source,
        (
            "function renderBatchPanel",
            "batch_fraction",
            "marked_jobs",
            "not measurable",
            "modeled scenario",
        ),
    )
    assert not missing, f"the step-12 batch lane lost: {missing}"


# ── 5. The routing board (structured, not a KV dump) ─────────────────────────────────────────


def test_routing_board_renders_structured_recommendations() -> None:
    source = _refresh_text()
    missing = _missing(
        source,
        (
            "function routingTable",
            "Per-task routing",
            "Per-task model routing recommendations",
            "Best correctness",
            "Best efficiency",
            "best_correctness_model",
            "best_efficiency_model",
            "Strategy simulation",
            "Routing strategy simulation",
            "Total cost",
            "Avg correctness",
            "No routing data yet",
        ),
    )
    assert not missing, f"routing board degraded to a generic KV dump; lost: {missing}"


# ── 6. The registry board: filters + click-through lineage ────────────────────────────────────


def test_registry_board_keeps_its_filters_and_lineage_view() -> None:
    source = _surface_text()
    missing = _missing(
        source,
        (
            "function renderRegistryTable",
            "function loadRegistryLineage",
            "record_type",
            "registry-filter-type",
            "registry-filter-lifecycle",
            "registry-filter-since",
            "registry-lineage",
        ),
    )
    assert not missing, f"registry board lost its filters/lineage: {missing}"


def test_registry_table_pins_its_canonical_columns() -> None:
    source = _refresh_text()
    missing = _missing(source, ("knowledge_id", "Canonical-state registry entries"))
    assert not missing, f"registry table lost main's columns/caption: {missing}"


# ── 7. The subscription-usage (Money) board ───────────────────────────────────────────────────


def test_subscription_usage_board_renders_providers_and_the_meter() -> None:
    source = _refresh_text()
    missing = _missing(
        source,
        (
            "function loadSubscriptionUsage",
            "function usageUsd",
            "function usageMetrics",
            "function usageEmpty",
            "function usageError",
            "subscription-usage?refresh=1",
            "served_from",
            "refresh_error",
            "showing the last snapshot",
            "Window",
            "Resets (UTC)",
            "deepseek_platform",
            "platform meter",
        ),
    )
    assert not missing, f"subscription-usage board degraded to a generic KV dump; lost: {missing}"


# ── 8. Shared keyed-list reconciliation (calm under poll) ─────────────────────────────────────


def test_polled_lists_use_the_shared_keyed_list_reconciler() -> None:
    """Main loaded ``keyed-list.js`` before app.js and destructured ``root.ControlRoomKeyedList``.

    The refresh may either load the shared module or reference its contract from a loaded script;
    silently dropping keyed reconciliation (rebuilding polled lists) is the regression.
    """
    loaded_shared = any(src.endswith("/keyed-list.js") for src in _script_srcs())
    referenced = "ControlRoomKeyedList" in _refresh_text()
    assert loaded_shared or referenced, (
        "no refreshed script loads keyed-list.js or references ControlRoomKeyedList — polled "
        "lists rebuild and lose focus/scroll instead of reconciling by key"
    )


# ── 9. Read-board refresh affordance (event wiring) ───────────────────────────────────────────


def test_read_boards_keep_their_refresh_affordances() -> None:
    """Main exposed a Refresh control per board; the refreshed workbench lazy-loads once."""
    missing = _missing(
        _surface_text(),
        (
            "operations-refresh",
            "surfaces-refresh",
            "routing-refresh",
            "registry-refresh",
            "usage-refresh",
        ),
    )
    assert not missing, f"read boards lost their refresh wiring: {missing}"


# ── 10. Run-detail drawer control (DOM anchor) ────────────────────────────────────────────────


def test_run_detail_drawer_has_a_close_control() -> None:
    source = _surface_text()
    assert "run-detail-drawer" in source, "the run-detail drawer anchor is missing"
    assert "run-detail-close" in source or "Close run detail" in source, (
        "the run-detail drawer lost its close control"
    )


def test_operations_panel_is_a_workbench_lens_not_the_old_destination_board() -> None:
    """The old destination-board ids are intentionally replaced by the workbench panels."""
    index = _index_text()
    assert 'data-lens="operations"' in index and 'data-lens="surfaces"' in index
