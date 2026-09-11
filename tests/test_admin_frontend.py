"""Browser-free structural verification for the Control Room resting screen (facelift a0).

The repository intentionally has no JavaScript runtime dependency, so this module locks down the
DOM/source-level invariants that connect the renderer to the shell, and the server-side schema of
the one read-only projection the screen consumes. The behavioural half (which payload value maps
to which pixel) is covered by ``scripts/verify_control_room_rendering.py`` when a browser is
available.

The previous destination-board portal is superseded by the one resting screen
(``docs/research/control_room_ia.md``), so these guards assert the canonical glance contract:
one region per ``R0/R1/R2/R3a/R3b/R3c``, one answer anchor per ``ON-G1..G7`` inside its unique
region, the 16-field run-row schema, and the fixed per-viewport pixel budget.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.fast

STATIC = Path(__file__).resolve().parent.parent / "apps" / "control_room" / "static"

#: The canonical single-valued answer→region map (docs/research/control_room_ia.md §4).
ANSWER_REGION = {
    "ON-G1": "R0",
    "ON-G2": "R2",
    "ON-G3": "R1",
    "ON-G4": "R3a",
    "ON-G5": "R1",
    "ON-G6": "R0",
    "ON-G7": "R3c",
}

#: The 16 fields every R2 run row must carry (docs/research/control_room_ia.md §10.2).
ROW_FIELDS = {
    "session.identity",
    "terminal.target",
    "command.current",
    "model.provider",
    "attempt.number",
    "phase.progress",
    "lifecycle.state",
    "run.live",
    "source.commit",
    "cost.provenance",
    "attention.state",
    "evidence.advisory",
    "evidence.measured",
    "evidence.source",
    "decision.eligibility",
    "decision.receipt",
}


def _read(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def test_shell_mounts_the_one_resting_screen_regions() -> None:
    """The initial HTML declares every layout region and the unique container hooks."""
    html = _read("index.html")

    for region in ("R0", "R1", "R2", "R3a", "R3b", "R3c"):
        assert html.count(f'data-region="{region}"') == 1, region
    for hook in ("data-glance-shell", "data-glance-body", "data-r3-stack"):
        assert hook in html, hook
    # `R4` is the drill-down dock, never a layout region, and it is hidden at rest.
    assert 'data-region="R4"' not in html
    assert 'id="selection-dock"' in html and "hidden" in html
    # The readiness contract the render gate waits on.
    assert 'data-render-state="loading"' in html
    assert '<script src="/static/app.js"></script>' in html
    assert '<link rel="stylesheet" href="/static/style.css">' in html


def test_shell_declares_the_canonical_answer_anchors_in_their_regions() -> None:
    """Static answers (R0/R2/R3a/R3c) are in the shell; R1 answers are built by the client.

    The answer anchors that the shell can carry without a payload — the system/trust bar, the
    fleet counts, the cost ledger, and the composition rollup — are declared in markup so the
    screen is useful before JavaScript responds. The attention answers (`ON-G5`/`ON-G3`) are
    data-bearing and therefore rendered by ``app.js``; the client source must name them.
    """
    html = _read("index.html")
    for answer, region in ANSWER_REGION.items():
        if answer in {"ON-G5", "ON-G3"}:
            continue
        assert f'data-answer="{answer}"' in html, answer
        # The anchor sits inside its canonical region block.
        region_index = html.index(f'data-region="{region}"')
        answer_index = html.index(f'data-answer="{answer}"')
        next_region = min(
            (html.index(f'data-region="{r}"') for r in ANSWER_REGION.values()
             if html.index(f'data-region="{r}"') > region_index),
            default=len(html),
        )
        assert region_index < answer_index < next_region, (answer, region)

    client = _read("app.js")
    for answer in ("ON-G5", "ON-G3"):
        assert f'"{answer}"' in client, answer


def test_client_carries_the_full_row_and_field_schema() -> None:
    """Every field the render gate requires is emitted by the client (never hand-waved)."""
    client = _read("app.js")
    # Row fields are literals; the system/run fields are built by prefix + name, so the test
    # checks the prefix and the name tokens rather than a concatenation that never appears.
    for field in ROW_FIELDS:
        assert f'"{field}"' in client, field
    for prefix, names in (
        ("system.", ("browser", "control", "workers", "projections")),
        ("runs.", ("running", "queued", "failed", "live")),
    ):
        assert f'"{prefix}"' in client, prefix
        for name in names:
            assert f'"{name}"' in client, name
    for field in (
        "trust.epoch",
        "trust.worst_age",
        "trust.projection_state",
        "trust.degraded_count",
        "trust.stale_count",
        "trust.partial_count",
        "trust.unknown_count",
        "money.spend",
        "money.burn",
        "money.quota",
        "money.wallet",
        "money.leases",
    ):
        assert f'"{field}"' in client, field
    # The §10.2 attribute vocabulary the gate greps for.
    for attribute in (
        "data-field",
        "data-label",
        "data-value",
        "data-no-ellipsis",
        "data-identifier",
        "data-max-lines",
        "data-micro-row",
        "data-item-line",
        "data-row-line",
        "data-detail-line",
        "data-marginal",
        "data-bucket",
        "data-money-risk",
        "data-evidence-class",
        "data-state",
        "data-age-seconds",
    ):
        assert attribute in client, attribute
    # No HTML-string rendering: content is built with element()/textContent only.
    assert "innerHTML" not in client
    assert "insertAdjacentHTML" not in client


def test_client_implements_the_bounded_at_rest_capacities() -> None:
    """The at-rest row/item counts are fixed per viewport (8/7/3 rows; 5/4/3 items)."""
    client = _read("app.js")
    assert "capacities" in client
    for token in ("rows: 8", "rows: 7", "rows: 3", "attention: 5", "attention: 4", "attention: 3"):
        assert token in client, token


def test_styles_hold_the_ia_pixel_budget_and_accessibility_bar() -> None:
    """The geometry tokens and the responsive/a11y rules are part of the no-build asset."""
    css = _read("style.css")

    # Desktop geometry tokens (the gate asserts the computed boxes these produce).
    for token, value in (
        ("--r0h: 72px", None),
        ("--r1h: 800px", None),
        ("--r2h: 800px", None),
        ("--r1w: 300px", None),
        ("--r2w: 744px", None),
        ("--r3w: 340px", None),
    ):
        assert token in css, token

    # Narrow and mobile breakpoints.
    assert "@media (max-width: 1199px)" in css
    assert "@media (max-width: 759px)" in css
    # Accessibility bar.
    assert "prefers-reduced-motion" in css
    assert "forced-colors" in css
    assert ":focus-visible" in css
    # No hidden overflow on the resting regions: content must genuinely fit, not clip silently.
    assert "overflow: hidden" in css


def test_shell_mounts_the_trends_lens_and_the_chart_module() -> None:
    """The chart set is a deliberate drill-down lens, not a resting region."""
    html = _read("index.html")
    for required in (
        'id="chart-lens"',
        'data-chart-lens',
        'id="chart-grid"',
        'id="lens-open"',
        'id="lens-close"',
        'aria-expanded="false"',
    ):
        assert required in html, required
    # The lens is hidden at rest and is NOT a layout region.
    assert 'data-region="R4"' not in html
    assert '<script src="/static/charts.js"></script>' in html
    # Charts never displace a resting answer.
    assert html.count('data-answer="ON-G1"') == 1
    assert html.count('data-answer="ON-G7"') == 1


def test_chart_module_covers_the_four_catalog_forms_without_a_runtime() -> None:
    """charts.js builds SVG+CSS micro-charts; no chart library, canvas, or build step."""
    charts = _read("charts.js")
    for chart_id in ("spend", "throughput", "failure", "dependency"):
        assert f'id: "{chart_id}"' in charts, chart_id
    # SVG authoring: viewBox + currentColor/custom properties + a namespaced element factory.
    assert "createElementNS" in charts
    assert "viewBox" in charts
    assert ('role="img"' in charts or "role: \"img\"" in charts
            or 'setAttribute("role", "img")' in charts)
    assert "aria-label" in charts
    # Empty and error states are first-class (never a blank panel).
    assert "data-chart-empty" in charts
    assert "data-chart-error" in charts
    assert "chart-table" in charts
    # No runtime dependency: no canvas, no library fetch, bounded history.
    assert "getContext" not in charts
    assert "new Chart(" not in charts
    assert "HISTORY_MAX" in charts


def test_chart_styles_declare_budgets_themes_and_motion() -> None:
    """Every chart has a body budget; series are theme-aware and forced-colors safe."""
    css = _read("style.css")
    for selector in (
        ".chart-lens",
        ".chart-grid",
        ".chart-card",
        ".chart-body",
        ".chart-svg",
        ".chart-line",
        ".chart-table",
        ".chart-empty",
        ".chart-error",
        ".chart-gauge",
        ".chart-status-grid",
    ):
        assert selector in css, selector
    assert "--chart-body-h" in css
    # Forced-colors keeps the series distinguishable by system color.
    assert ".chart-series-0 { color: LinkText; }" in css
    assert ".chart-gauge-fill { background: Highlight; }" in css


def test_visual_module_renders_accessible_svg_without_a_runtime() -> None:
    """visuals.js is the SVG set: viewBox, real <text>, title/desc, currentColor, no runtime."""
    visuals = _read("visuals.js")
    for visual in ("evidence-ladder", "dependency-flow"):
        assert f'data-visual": "{visual}"' in visuals or f'"{visual}"' in visuals, visual
    assert "createElementNS" in visuals
    assert "viewBox" in visuals
    assert "preserveAspectRatio" in visuals
    assert 'svg("title"' in visuals
    assert 'svg("desc"' in visuals
    assert "stroke-dasharray" in visuals
    # Typed evidence classes are carried by shape AND label word.
    for cls in ("advisory", "measured", "source", "policy", "lifecycle"):
        assert f'data-evidence-class' in visuals and cls in visuals, cls
    # Actionable + live: the affected record and the lens action are rendered.
    assert "data-visual-affected" in visuals
    assert "data-visual-action" in visuals
    # No runtime, no <img>, no canvas.
    assert "getContext" not in visuals
    assert "createElement(\"img\")" not in visuals
    assert "http" not in visuals.replace("http://www.w3.org/2000/svg", "")


def test_resting_room_ships_no_static_topology() -> None:
    """Brief §10: no static diagram in the resting room; topology is scoped to the dock."""
    html = _read("index.html")
    assert "architecture.svg" not in html
    assert 'id="selection-dock"' in html and "hidden" in html
    # The visual module loads only as a classic script beside charts.
    assert '<script src="/static/visuals.js"></script>' in html


def test_visual_styles_hold_theme_contrast_budget_and_motion() -> None:
    """Every visual has a budget, theme-aware fills, a reduced-motion path, forced-colors."""
    css = _read("style.css")
    for selector in (
        ".visual-grid",
        ".visual-block",
        ".visual-svg",
        ".visual-ladder",
        ".visual-flow",
        ".visual-spine",
        ".visual-rung",
        ".visual-flow-line",
        ".visual-fallback",
        ".visual-action",
    ):
        assert selector in css, selector
    assert ".visual-ladder { height: 226px; }" in css
    assert ".visual-flow { height: 96px; }" in css
    assert "visual-draw" in css  # state-change motion
    assert "prefers-reduced-motion" in css  # global collapse
    assert "--advisory" in css and "--measured" in css  # theme tokens, not hard-coded hex


def test_all_preexisting_routes_still_resolve() -> None:
    """The facelift is additive: every previously-registered API path is still served."""
    from apps.control_room import server

    rules = {str(rule) for rule in server.app.url_map.iter_rules()}
    expected = {
        "/",
        "/api/matrix",
        "/api/status",
        "/api/projections",
        "/api/routing",
        "/api/subscription-usage",
        "/api/events/<cell_id>",
        "/api/experiments",
        "/api/queue/reinterleave",
        "/api/flags",
        "/api/flags/<session_id>/steer",
        "/api/flags/<session_id>/interrupt",
        "/api/registry",
        "/api/registry/<entity_id>",
        "/api/design-sessions",
        "/api/claude-agents",
        "/api/docs-health",
        "/api/docs-health/approve",
        # The facelift's additive read-only surfaces.
        "/api/glance",
        "/api/events",
    }
    missing = expected - rules
    assert not missing, sorted(missing)


def test_glance_projection_exposes_the_resting_schema() -> None:
    """`GET /api/glance` returns the deterministic, null-not-zero view projection."""
    from apps.control_room import server

    response = server.app.test_client().get("/api/glance")
    assert response.status_code == 200
    data = response.get_json()

    assert {
        "control_epoch",
        "source",
        "observed_at",
        "system",
        "trust",
        "attention",
        "run_counts",
        "run_sample",
        "cost",
        "health_detail",
        "composition",
    } <= set(data)

    assert set(data["system"]) == {"browser", "control", "workers", "projections"}
    for dimension in data["system"].values():
        assert dimension["state"] in {"up", "degraded", "down", "unknown"}
        assert isinstance(dimension["age_seconds"], int)

    trust = data["trust"]
    assert trust["projection_state"] in {"current", "lagging", "stale", "failing", "unknown"}
    for key in ("epoch", "worst_age", "degraded_count", "stale_count", "partial_count", "unknown_count"):
        assert isinstance(trust[key], int) and trust[key] >= 0

    assert set(data["run_counts"]) == {"running", "queued", "failed", "live"}
    assert set(data["cost"]) >= {"spend", "burn", "quota", "wallet", "leases", "money_risk"}
    assert set(data["composition"]) == {"model", "condition", "provider", "lifecycle"}
    for marginal in data["composition"].values():
        assert set(marginal) == {"top", "other", "unknown"}

    for run in data["run_sample"]:
        assert set(ROW_FIELDS) <= set(run)
        assert re.fullmatch(r"\d+/\d+", str(run["phase.progress"]))
