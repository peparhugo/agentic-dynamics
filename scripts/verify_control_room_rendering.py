#!/usr/bin/env python3
"""verify_control_room_rendering.py — the Control Room facelift render gate.

The gate is the executable form of ``docs/research/control_room_ia.md`` §10: it serves the real
Flask shell, intercepts every ``/api/*`` request with a committed fixture, captures screenshots
at the three claimed breakpoints (1440x900, 1024x768, 390x844), and asserts the canonical glance
contract — all seven ``ON-G1..G7`` answers present, unique, inside their one canonical region,
above the fold, with no page or region scroll, on WCAG-AA contrast, and with the bounded row /
item / marginal counts per viewport.

Classes implemented (p5 IA8: a screenshot must not be asked to prove what only the network can):
  * G geometry     — present/unique, in-viewport, non-zero box, no scroll, contrast, schemas
  * fixtures       — deterministic F-0..F-7 payloads, no live Redis/clock/network (waiver W2)

The blind-comprehension (B), browser/a11y (A) and event/state (E) classes are named in the IA;
this gate implements the geometry + fixture classes it can automate deterministically. The
adversaries (``docs/reviews/control_room_facelift_{design,ia}.md``) read the screenshots this
gate writes.

Usage:
  python3 scripts/verify_control_room_rendering.py                 # full gate (needs Chromium)
  python3 scripts/verify_control_room_rendering.py --check-fixtures  # no browser: validate fixtures
  python3 scripts/verify_control_room_rendering.py --out DIR --json PATH --report PATH
  python3 scripts/verify_control_room_rendering.py --fixtures F-0,F-5 --no-screenshot

Exit code 0 = PASS, 1 = FAIL, 2 = browser unavailable.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import threading
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FIXTURE_DIR = ROOT / "apps" / "control_room" / "verification" / "fixtures"
REPORT_DIR_DEFAULT = ROOT / "apps" / "control_room" / "verification"

#: The three claimed resting breakpoints (docs/research/control_room_ia.md §3.2).
VIEWPORTS = {"desktop": (1440, 900), "narrow": (1024, 768), "mobile": (390, 844)}
THEMES = ("dark", "light", "forced-colors")

REGIONS = ["R0", "R1", "R2", "R3a", "R3b", "R3c"]
ANSWER_REGION = {
    "ON-G1": "R0",
    "ON-G2": "R2",
    "ON-G3": "R1",
    "ON-G4": "R3a",
    "ON-G5": "R1",
    "ON-G6": "R0",
    "ON-G7": "R3c",
}
FIELDS = {
    "ON-G1": {"system.browser", "system.control", "system.workers", "system.projections"},
    "ON-G2": {"runs.running", "runs.queued", "runs.failed", "runs.live"},
    "ON-G3": {"risk.identity", "risk.state", "risk.action"},
    "ON-G4": {"money.spend", "money.burn", "money.quota", "money.wallet", "money.leases"},
    "ON-G5": {
        "decision.state",
        "decision.target",
        "decision.kind",
        "decision.epoch",
        "decision.authority",
        "decision.eligibility",
    },
    "ON-G6": {
        "trust.epoch",
        "trust.worst_age",
        "trust.projection_state",
        "trust.degraded_count",
        "trust.stale_count",
        "trust.partial_count",
        "trust.unknown_count",
    },
}
ROW_FIELDS = {
    "session.identity", "terminal.target", "command.current", "model.provider", "attempt.number",
    "phase.progress", "lifecycle.state", "run.live", "source.commit", "cost.provenance",
    "attention.state", "evidence.advisory", "evidence.measured", "evidence.source",
    "decision.eligibility", "decision.receipt",
}
EXPECTED_BOXES = {
    "desktop": {"R0": (16, 0, 1408, 72), "R1": (16, 84, 300, 800),
                "R2": (328, 84, 744, 800), "R3a": (1084, 84, 340, 220),
                "R3b": (1084, 312, 340, 180), "R3c": (1084, 500, 340, 140)},
    "narrow": {"R0": (12, 0, 1000, 60), "R1": (12, 68, 224, 692),
               "R2": (244, 68, 472, 692), "R3a": (724, 68, 288, 160),
               "R3b": (724, 236, 288, 132), "R3c": (724, 376, 288, 116)},
    "mobile": {"R0": (12, 0, 366, 72), "R1": (12, 80, 366, 144),
               "R2": (12, 232, 366, 284), "R3a": (12, 524, 366, 92),
               "R3b": (12, 624, 366, 68), "R3c": (12, 700, 366, 60)},
}
ROW_COUNT = {"desktop": 8, "narrow": 7, "mobile": 3}
ATTENTION_COUNT = {"desktop": 5, "narrow": 4, "mobile": 3}

#: The committed fixture deltas (§10.6). Applied to a deep copy of F-0 by the loader so the
#: forcing states stay exact and reviewable rather than duplicated.
FIXTURE_DELTAS: dict[str, dict[str, Any]] = {
    "F-1": {
        "inbox_overflow": 20,
    },
    "F-2": {
        "run_counts": {"running": 80, "queued": 60, "failed": 40, "live": 20},
    },
    "F-3": {
        "cost": {"spend": "$48.10", "burn": "$2.40/h", "quota": "96%", "wallet": "$1.60",
                 "leases": "$9.90", "money_risk": True},
    },
    "F-4": {
        "provider_unknown": True,
    },
    "F-5": {
        "stale_projection": True,
    },
    "F-6": {
        "browser_down": True,
    },
    "F-7": {
        "empty_queues": True,
    },
}


# ── Fixture loading + expansion ──────────────────────────────────────────────────────────────


def load_seed() -> dict[str, Any]:
    """Load the committed F-0 seed object (the exact §10.6 payload)."""
    return json.loads((FIXTURE_DIR / "F-0.json").read_text(encoding="utf-8"))


def _apply_delta(seed: dict[str, Any], fixture_id: str) -> dict[str, Any]:
    """Apply one fixture's forcing delta to a copy of the seed."""
    payload = copy.deepcopy(seed)
    delta = FIXTURE_DELTAS.get(fixture_id, {})
    if "run_counts" in delta:
        payload["run_counts"] = delta["run_counts"]
    if "cost" in delta:
        payload["cost"] = delta["cost"]
    if delta.get("inbox_overflow"):
        payload["attention"]["items"] = [
            {
                "id": f"adv-{index:02d}",
                "state": "active",
                "action": "inspect",
                "authority": "heuristic",
                "severity": "low",
                "identity": f"advisory-{index:02d}",
            }
            for index in range(1, int(delta["inbox_overflow"]) + 1)
        ]
    if delta.get("provider_unknown"):
        payload["composition"]["provider"] = {"top": "openai 5", "other": "0", "unknown": "2"}
        payload["trust"]["unknown_count"] = 2
        payload["cost"] = {key: "unknown" for key in
                           ("spend", "burn", "quota", "wallet", "leases")}
        payload["cost"]["money_risk"] = False
    if delta.get("stale_projection"):
        payload["system"]["projections"] = {"state": "degraded", "age_seconds": 901}
        payload["trust"]["projection_state"] = "stale"
        payload["trust"]["worst_age"] = 901
        payload["trust"]["degraded_count"] = 1
        payload["trust"]["stale_count"] = 1
    if delta.get("browser_down"):
        payload["system"]["browser"] = {"state": "down", "age_seconds": 7}
    if delta.get("empty_queues"):
        payload["attention"]["decision"] = {
            "state": "none", "target": "none", "kind": "none", "epoch": 42,
            "authority": "none", "eligibility": "none",
        }
        payload["attention"]["risk"] = {"identity": "none", "state": "all-clear", "action": "none"}
    return payload


def expand_wire(payload: dict[str, Any]) -> dict[str, Any]:
    """Expand ``run_defaults`` into each run and copy epoch/source/observed_at into nested blocks.

    This is the deterministic transform §10.6 specifies: the fixture loader turns the compact
    seed into the exact wire JSON the static UI consumes, so every row has the complete schema.
    """
    wire = copy.deepcopy(payload)
    wire.pop("id", None)
    wire.pop("label", None)
    defaults = wire.pop("run_defaults", {}) or {}
    expanded_rows = []
    for row in wire.get("run_sample", []):
        merged = dict(defaults)
        merged.update(row)
        merged.setdefault("session.identity", row.get("id", "unknown"))
        expanded_rows.append(merged)
    wire["run_sample"] = expanded_rows

    epoch = wire.get("control_epoch", 0)
    source = wire.get("source", "")
    observed_at = wire.get("observed_at", "")

    def fill(node: Any) -> None:
        if isinstance(node, dict):
            node.setdefault("control_epoch", epoch)
            node.setdefault("source", source)
            node.setdefault("observed_at", observed_at)
            for child in node.values():
                fill(child)
        elif isinstance(node, list):
            for child in node:
                fill(child)

    fill(wire)
    return wire


def build_fixture(fixture_id: str) -> dict[str, Any]:
    """Build the expanded wire payload for one fixture id."""
    return expand_wire(_apply_delta(load_seed(), fixture_id))


def check_fixtures() -> int:
    """Validate every fixture deterministically without a browser (CI-safe smoke check)."""
    problems = []
    for fixture_id in ("F-0", "F-1", "F-2", "F-3", "F-4", "F-5", "F-6", "F-7"):
        try:
            wire = build_fixture(fixture_id)
        except Exception as error:  # noqa: BLE001 - report, do not crash
            problems.append(f"{fixture_id}: {error}")
            continue
        if not {"running", "queued", "failed", "live"} <= set(wire["run_counts"]):
            problems.append(f"{fixture_id}: run_counts schema")
        if len(wire["run_sample"]) < 8:
            problems.append(f"{fixture_id}: needs at least 8 sample rows")
        for row in wire["run_sample"]:
            missing = ROW_FIELDS - set(row)
            if missing:
                problems.append(f"{fixture_id}: row {row.get('id')} missing {sorted(missing)}")
        for name in ("model", "condition", "provider", "lifecycle"):
            marginal = wire["composition"][name]
            if not {"top", "other", "unknown"} <= set(marginal):
                problems.append(f"{fixture_id}: {name} marginal schema")
    if problems:
        print("fixture check FAIL")
        for problem in problems:
            print("  ", problem)
        return 1
    print("fixture check PASS (F-0..F-7)")
    return 0


# ── The Flask shell (the production app; /api/* is intercepted by Playwright) ────────────────


def serve_app() -> tuple[str, Any]:
    """Run the real Control Room Flask app on an ephemeral port; return (base_url, server)."""
    from werkzeug.serving import make_server

    from apps.control_room import server as portal

    httpd = make_server("127.0.0.1", 0, portal.app)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return f"http://127.0.0.1:{httpd.server_port}", httpd


# ── Browser geometry checks ──────────────────────────────────────────────────────────────────

#: The HTML contrast walker. It reuses the SVG gate's parse/lin/lum/ratio math, then walks text
#: nodes under every resting region with a TreeWalker, compositing the effective ancestor
#: background. A non-`none` background-image behind required text is a failure (never a guess).
CONTRAST_JS = r"""
(minNormal, minLarge) => {
  const parseColor = (str) => {
    if (!str) return null;
    str = String(str).trim().toLowerCase();
    if (!str || str === 'none') return null;
    if (str === 'transparent') return [0,0,0,0];
    let m;
    if ((m = str.match(/^rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:[,\s/]+([\d.]+))?\s*\)$/)))
      return [+m[1], +m[2], +m[3], m[4] === undefined ? 1 : Math.min(1, +m[4])];
    if ((m = str.match(/^#([0-9a-f]{6})$/)))
      return [parseInt(m[1].slice(0,2),16), parseInt(m[1].slice(2,4),16), parseInt(m[1].slice(4,6),16), 1];
    if ((m = str.match(/^#([0-9a-f]{3})$/)))
      return [parseInt(m[1][0]+m[1][0],16), parseInt(m[1][1]+m[1][1],16), parseInt(m[1][2]+m[1][2],16), 1];
    return null;
  };
  const lin = (c) => { c /= 255; return c <= 0.03928 ? c/12.92 : Math.pow((c+0.055)/1.055, 2.4); };
  const lum = (c) => 0.2126*lin(c[0]) + 0.7152*lin(c[1]) + 0.0722*lin(c[2]);
  const ratio = (a, b) => { const x = lum(a), y = lum(b); const hi = Math.max(x,y), lo = Math.min(x,y);
    return (hi + 0.05) / (lo + 0.05); };
  const blend = (fg, a, bg) => fg.slice(0,3).map((c,i) => a*c + (1-a)*bg[i]);
  const bgFor = (el) => {
    let cur = el, acc = null;
    while (cur && cur.nodeType === 1) {
      const cs = getComputedStyle(cur);
      if (cs.backgroundImage && cs.backgroundImage !== 'none') return { image: true };
      const c = parseColor(cs.backgroundColor);
      if (c && c[3] > 0) {
        if (!acc) acc = c;
        else acc = [c[0]*c[3] + acc[0]*(1-c[3]), c[1]*c[3] + acc[1]*(1-c[3]),
                    c[2]*c[3] + acc[2]*(1-c[3]), 1];
        if (acc[3] >= 1 || (c[3] >= 1)) return acc.slice(0,3);
      }
      cur = cur.parentElement;
    }
    return acc ? acc.slice(0,3) : parseColor('#0d1014').slice(0,3);
  };
  const fails = [];
  document.querySelectorAll('[data-region]').forEach((region) => {
    const walker = document.createTreeWalker(region, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      const label = (node.textContent || '').trim();
      if (!label) continue;
      const parent = node.parentElement;
      if (!parent) continue;
      const rect = parent.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) continue;
      const cs = getComputedStyle(parent);
      const fg = parseColor(cs.color);
      if (!fg) continue;
      const bg = bgFor(parent);
      if (bg && bg.image) { fails.push({region: region.dataset.region, text: label.slice(0,40),
        reason: 'background-image'}); continue; }
      const fgA = (fg[3] === undefined ? 1 : fg[3]);
      const eff = blend(fg, fgA, bg);
      const size = parseFloat(cs.fontSize) || 16;
      const weight = parseInt(cs.fontWeight, 10) || 400;
      const large = size >= 24 || (size >= 18.66 && weight >= 700);
      const need = large ? minLarge : minNormal;
      const r = ratio(eff, bg);
      if (r < need) fails.push({region: region.dataset.region, text: label.slice(0,40),
        ratio: Math.round(r*100)/100, need: need});
    }
  });
  return fails;
}
"""

GEOMETRY_JS = r"""
() => {
  const rect = (el) => { const r = el.getBoundingClientRect();
    return {x: r.x, y: r.y, width: r.width, height: r.height, top: r.top, bottom: r.bottom,
            left: r.left, right: r.right}; };
  const visible = (el) => {
    for (let n = el; n; n = n.parentElement) {
      const cs = getComputedStyle(n);
      if (n.hidden || n.getAttribute('aria-hidden') === 'true' || cs.display === 'none' ||
          cs.visibility === 'hidden') return false;
    }
    return true;
  };
  const regions = {};
  document.querySelectorAll('[data-region]').forEach((el) => {
    regions[el.dataset.region] = {rect: rect(el), visible: visible(el),
      scrollH: el.scrollHeight, clientH: el.clientHeight,
      scrollW: el.scrollWidth, clientW: el.clientWidth};
  });
  const answers = {};
  document.querySelectorAll('[data-answer]').forEach((el) => {
    const parent = el.closest('[data-region]');
    answers[el.dataset.answer] = {region: parent ? parent.dataset.region : null,
      rect: rect(el), visible: visible(el), scrollH: el.scrollHeight, clientH: el.clientHeight};
  });
  const rows = [];
  document.querySelectorAll('[data-region="R2"] [data-run-id]').forEach((el) => {
    const fields = Array.from(el.querySelectorAll('[data-field]')).map((f) => f.dataset.field);
    const out = {}; el.querySelectorAll('[data-field]').forEach((f) => {
      const v = f.querySelector(':scope > [data-value]');
      out[f.dataset.field] = v ? v.innerText.trim() : ''; });
    rows.push({fields, values: out});
  });
  // Exact field sets per answer, and every required value's text/size.
  const answerFields = {};
  const valueTexts = {};       // "answer:field" -> visible value text
  const valueSizes = [];       // {size, region} for every value in a resting region
  const labelSizes = [];       // {size, region} for every label in a resting region
  document.querySelectorAll('[data-answer]').forEach((answer) => {
    answerFields[answer.dataset.answer] = Array.from(answer.querySelectorAll('[data-field]'))
      .map((f) => f.dataset.field);
  });
  document.querySelectorAll('[data-region]').forEach((region) => {
    const regionName = region.dataset.region;
    region.querySelectorAll('[data-value]').forEach((value) => {
      valueSizes.push({size: parseFloat(getComputedStyle(value).fontSize) || 0, region: regionName});
    });
    region.querySelectorAll('[data-label]').forEach((label) => {
      labelSizes.push({size: parseFloat(getComputedStyle(label).fontSize) || 0, region: regionName});
    });
    region.querySelectorAll('[data-field]').forEach((field) => {
      const value = field.querySelector(':scope > [data-value]');
      const answer = field.closest('[data-answer]');
      if (value && answer) {
        valueTexts[answer.dataset.answer + ':' + field.dataset.field] = value.innerText.trim();
      }
    });
  });
  const marginals = [];
  document.querySelectorAll('[data-answer="ON-G7"] [data-marginal]').forEach((m) => {
    const buckets = [];
    m.querySelectorAll('[data-bucket]').forEach((b) => {
      const value = b.querySelector('[data-value]');
      buckets.push({bucket: b.dataset.bucket, category: b.getAttribute('data-category') || '',
        value: value ? value.innerText.trim() : ''});
    });
    marginals.push({name: m.dataset.marginal, buckets});
  });
  const moneyRiskCount = document.querySelectorAll('[data-answer="ON-G4"] [data-money-risk]').length;
  const noEllipsisMissing = Array.from(
    document.querySelectorAll('[data-region] [data-value]:not([data-identifier])')
  ).filter((v) => !v.hasAttribute('data-no-ellipsis')).length;
  // Count the actually-rendered text lines of an element by the distinct vertical positions of
  // its text-node rects (robust for flex rows, unlike height / line-height).
  const renderedLines = (el) => {
    // Cluster overlapping text rects into lines: same-line fragments (different font sizes)
    // overlap vertically, so a new line is a rect that starts below the current cluster.
    const rects = [];
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      if (!node.textContent.trim()) continue;
      const range = document.createRange();
      range.selectNodeContents(node);
      Array.from(range.getClientRects()).forEach((rect) => {
        if (rect.height > 0) rects.push({top: rect.top, bottom: rect.bottom});
      });
    }
    rects.sort((a, b) => a.top - b.top);
    let lines = 0, clusterBottom = -Infinity;
    rects.forEach((rect) => {
      if (rect.top >= clusterBottom - 2) { lines += 1; clusterBottom = rect.bottom; }
      else { clusterBottom = Math.max(clusterBottom, rect.bottom); }
    });
    return lines;
  };
  const lineBearing = [];
  document.querySelectorAll('[data-max-lines]').forEach((el) => {
    const where = el.className + (el.dataset.field ? ':' + el.dataset.field : '');
    lineBearing.push({max: parseInt(el.dataset.maxLines, 10) || 0, lines: renderedLines(el),
      where: where});
  });
  const count = (selector) => document.querySelectorAll(selector).length;
  const page = document.scrollingElement;
  return {
    innerWidth: window.innerWidth, innerHeight: window.innerHeight,
    scrollWidth: page.scrollWidth, scrollHeight: page.scrollHeight,
    regions, answers, rows, answerFields, valueTexts, valueSizes, labelSizes, marginals,
    moneyRiskCount, noEllipsisMissing, lineBearing,
    attentionItems: count('[data-region="R1"] [data-attention-class]'),
    attentionLines: count('[data-region="R1"] [data-item-line]'),
    rowLines: count('[data-region="R2"] [data-row-line]'),
    detailLines: count('[data-region="R3b"] [data-detail-line]'),
  };
}
"""


def _glance_handler(payload: dict[str, Any]):
    """Return a one-argument Playwright route handler serving the expanded fixture JSON."""

    def handler(route: Any) -> None:
        route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))

    return handler


def _events_handler(frames: str):
    """Return a one-argument Playwright route handler serving the committed SSE frames."""

    def handler(route: Any) -> None:
        route.fulfill(status=200, content_type="text/event-stream", body=frames)

    return handler


def _row(errors: list[str], viewport: str, fixture: str, check: str, detail: str) -> None:
    errors.append(f"[{viewport}/{fixture}] {check}: {detail}")


def run_browser_gate(
    fixture_ids: list[str], out: Path, screenshots: bool,
    themes: tuple[str, ...] = THEMES, screenshot_themes: tuple[str, ...] = ("dark",),
) -> tuple[list[dict[str, Any]], list[str]]:
    """Render every fixture at every viewport in every theme; run the geometry class.

    Returns ``(screenshot_results, errors)``. The theme loop is part of the acceptance contract:
    contrast must hold in dark, light, and forced-colors (docs/research/control_room_ia.md §10.3
    G-4). Light/dark are pinned via localStorage so the page's pre-paint resolver can't race the
    screenshot; forced-colors uses the browser's post-emulation computed colors.
    """
    from playwright.sync_api import sync_playwright

    base, httpd = serve_app()
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(args=["--no-sandbox"])
            for fixture_id in fixture_ids:
                wire = build_fixture(fixture_id)
                frames = (
                    "event: snapshot\n"
                    + "data: " + json.dumps({"control_epoch": wire["control_epoch"],
                                             "fixture": fixture_id}, separators=(",", ":")) + "\n\n"
                    + "event: replay_complete\n"
                    + "data: " + json.dumps({"control_epoch": wire["control_epoch"]},
                                            separators=(",", ":")) + "\n\n"
                )
                for theme in themes:
                    for name, (width, height) in VIEWPORTS.items():
                        label = f"{name}/{theme}"
                        if theme == "forced-colors":
                            context = browser.new_context(
                                viewport={"width": width, "height": height},
                                timezone_id="UTC", locale="en-US", reduced_motion="reduce",
                                color_scheme="dark", forced_colors="active",
                            )
                        else:
                            context = browser.new_context(
                                viewport={"width": width, "height": height},
                                timezone_id="UTC", locale="en-US", reduced_motion="reduce",
                                color_scheme=theme, forced_colors="none",
                            )
                            context.add_init_script(
                                f"try{{localStorage.setItem('control-room-theme', '{theme}')}}"
                                "catch(e){}"
                            )
                        page = context.new_page()
                        console_errors: list[str] = []
                        page.on("console", lambda message: console_errors.append(message.text)
                                if message.type == "error" else None)
                        page.on("pageerror", lambda error: console_errors.append(str(error)))

                        # Playwright resolves the LAST matching handler first, so the catch-all
                        # abort must be registered BEFORE the two fixture routes it must not
                        # shadow. Handlers take exactly one argument (the handler that owns the
                        # response); a second parameter would be the Request object.
                        page.route("**/api/**", lambda route: route.abort())
                        page.route("**/api/glance", _glance_handler(wire))
                        page.route("**/api/events", _events_handler(frames))
                        page.goto(base, wait_until="domcontentloaded")
                        page.locator('[data-render-state="ready"]').wait_for(timeout=15000)

                        geometry = page.evaluate(GEOMETRY_JS)
                        _check_geometry(fixture_id, name, theme, geometry, errors)
                        # A console error is a loaded-page defect even when geometry is intact.
                        for message in console_errors:
                            _row(errors, label, fixture_id, "console", message[:200])
                        contrast_failures = page.evaluate(CONTRAST_JS, [4.5, 3.0])
                        for failure in contrast_failures:
                            _row(errors, label, fixture_id, "contrast", json.dumps(failure))

                        if screenshots and theme in screenshot_themes:
                            shot = out / f"{fixture_id}_{name}_{theme}_{width}x{height}.png"
                            page.screenshot(path=str(shot), full_page=False)
                            results.append({"fixture": fixture_id, "viewport": name,
                                            "theme": theme, "screenshot": str(shot)})
                        context.close()
            browser.close()
    finally:
        httpd.shutdown()
    return results, errors


def _check_geometry(
    fixture_id: str, name: str, theme: str, geometry: dict[str, Any], errors: list[str]
) -> None:
    """Assert the §10.7 geometry primitives for one rendered page.

    ``name`` selects the viewport budget table; ``theme`` is only a label for the report (the
    geometry is theme-independent, the contrast check is not).
    """
    label = f"{name}/{theme}"
    width = geometry["innerWidth"]
    height = geometry["innerHeight"]

    # G-1 present/unique/in-viewport/non-zero for regions and answers.
    assert set(geometry["regions"]) == set(REGIONS), (
        f"[{name}/{fixture_id}] regions {sorted(geometry['regions'])}"
    )
    assert set(geometry["answers"]) == set(ANSWER_REGION), (
        f"[{name}/{fixture_id}] answers {sorted(geometry['answers'])}"
    )
    for answer, region in ANSWER_REGION.items():
        got = geometry["answers"][answer]["region"]
        if got != region:
            _row(errors, label, fixture_id, "G-15", f"{answer} in {got}, want {region}")
    for region in REGIONS:
        box = geometry["regions"][region]["rect"]
        if not (box["width"] > 0 and box["height"] > 0):
            _row(errors, label, fixture_id, "G-1", f"{region} zero box {box}")

    # G-2 page must not scroll.
    if geometry["scrollHeight"] > height + 1:
        _row(errors, label, fixture_id, "G-2", f"page scrollHeight {geometry['scrollHeight']}")
    if geometry["scrollWidth"] > width + 1:
        _row(errors, label, fixture_id, "G-2", f"page scrollWidth {geometry['scrollWidth']}")

    # G-3 no region/answer internal scroll.
    for region in REGIONS:
        info = geometry["regions"][region]
        if info["scrollH"] > info["clientH"] + 1:
            _row(errors, label, fixture_id, "G-3", f"{region} scrollH {info['scrollH']}")
        if info["scrollW"] > info["clientW"] + 1:
            _row(errors, label, fixture_id, "G-3", f"{region} scrollW {info['scrollW']}")

    # G-7/G-8/G-12 fixed boxes.
    expected = EXPECTED_BOXES[name]
    for region, want in expected.items():
        box = geometry["regions"][region]["rect"]
        got = (box["x"], box["y"], box["width"], box["height"])
        if any(abs(a - b) > 1 for a, b in zip(got, want)):
            _row(errors, label, fixture_id, "G-7",
                 f"{region} box {tuple(round(v,1) for v in got)} want {want}")

    # G-13 row schema; G-14 row count + line clamps + fixed capacities.
    row_count = ROW_COUNT[name]
    if len(geometry["rows"]) != row_count:
        _row(errors, label, fixture_id, "G-14", f"{len(geometry['rows'])} rows want {row_count}")
    for index, row in enumerate(geometry["rows"]):
        if set(row["fields"]) != ROW_FIELDS:
            _row(errors, label, fixture_id, "G-13",
                 f"row {index} fields {sorted(set(row['fields']) ^ ROW_FIELDS)}")
    attention = ATTENTION_COUNT[name]
    if geometry["attentionItems"] != attention:
        _row(errors, label, fixture_id, "G-14",
             f"{geometry['attentionItems']} attention items want {attention}")
    if geometry["attentionLines"] != attention * 2:
        _row(errors, label, fixture_id, "G-14",
             f"{geometry['attentionLines']} item-lines want {attention * 2}")
    if geometry["rowLines"] != row_count * 3:
        _row(errors, label, fixture_id, "G-14",
             f"{geometry['rowLines']} row-lines want {row_count * 3}")
    if geometry["detailLines"] != 2:
        _row(errors, label, fixture_id, "G-14", f"{geometry['detailLines']} detail-lines want 2")
    for entry in geometry["lineBearing"]:
        if entry["lines"] > entry["max"]:
            _row(errors, label, fixture_id, "G-14",
                 f"{entry['where']} renders {entry['lines']} lines > max {entry['max']}")

    # G-5 type floors; G-6 non-empty required values; no missing data-no-ellipsis.
    value_floor = 12.0 if name == "mobile" else 13.0
    for entry in geometry["valueSizes"]:
        if entry["size"] < value_floor - 0.01:
            _row(errors, label, fixture_id, "G-5",
                 f"{entry['region']} value font {entry['size']} < {value_floor}")
    for entry in geometry["labelSizes"]:
        if entry["size"] < 11.0 - 0.01:
            _row(errors, label, fixture_id, "G-5",
                 f"{entry['region']} label font {entry['size']} < 11")
    for key, value in geometry["valueTexts"].items():
        if not value:
            _row(errors, label, fixture_id, "G-6", f"empty value {key}")
    if geometry["noEllipsisMissing"]:
        _row(errors, label, fixture_id, "G-6",
             f"{geometry['noEllipsisMissing']} required values lack data-no-ellipsis")

    # Exact schemas: answer field sets, money risk marker, bounded composition.
    for answer, expected in FIELDS.items():
        actual = geometry["answerFields"].get(answer, [])
        if len(actual) != len(set(actual)) or set(actual) != expected:
            _row(errors, label, fixture_id, "schema",
                 f"{answer} fields {sorted(set(actual) ^ expected)}")
    expected_risk = 1 if fixture_id == "F-3" else 0
    if geometry["moneyRiskCount"] != expected_risk:
        _row(errors, label, fixture_id, "G-10",
             f"money-risk markers {geometry['moneyRiskCount']} want {expected_risk}")
    marginals = geometry["marginals"]
    names = [entry["name"] for entry in marginals]
    if sorted(names) != ["condition", "lifecycle", "model", "provider"]:
        _row(errors, label, fixture_id, "G-11", f"marginals {names}")
    for entry in marginals:
        buckets = [b["bucket"] for b in entry["buckets"]]
        if sorted(buckets) != ["other", "top", "unknown"]:
            _row(errors, label, fixture_id, "G-11", f"{entry['name']} buckets {buckets}")
        top = next((b for b in entry["buckets"] if b["bucket"] == "top"), None)
        if not top or not top["category"] or not top["value"]:
            _row(errors, label, fixture_id, "G-11", f"{entry['name']} top bucket incomplete")


# ── Report ───────────────────────────────────────────────────────────────────────────────────


def write_report(results: list[dict[str, Any]], errors: list[str], report_path: Path,
                 json_path: Path, check_fixtures_exit: int) -> int:
    """Write the markdown + JSON reports; return the exit code."""
    status = "PASS" if not errors and check_fixtures_exit == 0 else "FAIL"
    lines = [
        "# Control Room render gate",
        "",
        f"**Status:** {status}",
        "**Fixtures:** F-0..F-7 (deterministic; no live Redis/clock/network — waiver W2)",
        f"**Viewports:** {', '.join(f'{k} {w}x{h}' for k, (w, h) in VIEWPORTS.items())}",
        "",
        f"**Screenshots:** {len(results)}",
        "",
    ]
    if errors:
        lines.append("## Failures")
        lines.append("")
        lines.extend(f"- {error}" for error in errors)
    else:
        lines.append("No geometry violations.")
    lines.append("")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    json_path.write_text(
        json.dumps({"status": status, "screenshots": results, "errors": errors}, indent=2),
        encoding="utf-8",
    )
    print("\n".join(lines))
    return 1 if errors or check_fixtures_exit else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(REPORT_DIR_DEFAULT))
    parser.add_argument("--report", default=None)
    parser.add_argument("--json", default=None, dest="json_path")
    parser.add_argument("--fixtures", default="F-0")
    parser.add_argument("--no-screenshot", action="store_true")
    parser.add_argument("--screenshot-themes", default="dark",
                        help="comma-separated themes to screenshot (contrast runs all themes)")
    parser.add_argument("--check-fixtures", action="store_true",
                        help="validate deterministic fixtures without a browser")
    args = parser.parse_args()

    fixtures = [item.strip() for item in args.fixtures.split(",") if item.strip()]
    fixture_rc = check_fixtures()
    if args.check_fixtures:
        return fixture_rc

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report_path = Path(args.report) if args.report else out / "gate_report.md"
    json_path = Path(args.json_path) if args.json_path else out / "gate_report.json"

    try:
        screenshot_themes = tuple(
            item.strip() for item in args.screenshot_themes.split(",") if item.strip()
        )
        results, errors = run_browser_gate(
            fixtures, out, not args.no_screenshot, screenshot_themes=screenshot_themes
        )
    except ImportError:
        print("playwright is not installed; run with --check-fixtures for the browser-free check",
              file=sys.stderr)
        return 2
    except Exception as error:  # noqa: BLE001 - a missing browser is exit 2, not a silent pass
        print(f"browser unavailable: {error}", file=sys.stderr)
        print("run `python3 -m playwright install --with-deps chromium` in an environment with "
              "the system libraries, or use --check-fixtures", file=sys.stderr)
        return 2
    return write_report(results, errors, report_path, json_path, fixture_rc)


if __name__ == "__main__":
    raise SystemExit(main())
