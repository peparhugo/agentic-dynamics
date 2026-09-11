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

#: The four catalog-derived charts (facelift a1). Each must render inside its budget at every
#: breakpoint, with an explicit empty/error state, never a blank panel.
CHART_IDS = ("spend", "throughput", "failure", "dependency")
#: Max chart-body height (px) per viewport, matching the CSS `--chart-body-h` budget + tolerance.
CHART_BODY_MAX = {"desktop": 98, "narrow": 90, "mobile": 74}

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


#: When set (by ``--base URL``), every gate renders against this already-running portal instead
#: of starting its own. A caller that supplies its own server is responsible for its lifecycle,
#: so the gates never shut it down.
_BASE_OVERRIDE: str | None = None


def _serve() -> tuple[str, Any | None]:
    """Return ``(base_url, httpd_or_None)`` — the injected base, or a freshly served app."""
    if _BASE_OVERRIDE:
        return _BASE_OVERRIDE, None
    return serve_app()


def _ensure_paint(page: Any) -> None:
    """Wait (briefly) for the browser to record a first paint before probing paint timing.

    Headless Chromium occasionally reports no paint entry at the instant a probe runs even
    though the page is ready. Waiting for the entry — and forcing two animation frames if it is
    slow — makes the first-paint check deterministic instead of flaky. A genuine no-paint page
    still times out here and is then reported by the caller's paint assertion.
    """
    try:
        page.wait_for_function(
            "() => performance.getEntriesByType('paint').length > 0", timeout=3000
        )
    except Exception:  # noqa: BLE001 — a missing paint is a finding, not a crash
        page.evaluate(
            "() => new Promise((resolve) => requestAnimationFrame(()"
            " => requestAnimationFrame(resolve)))"
        )


def _attach_console(page: Any) -> list[str]:
    """Listen for console errors and uncaught page errors; return the growing message list.

    A loaded page must be console-clean (the website gate's CONSOLE class). The list is mutated
    by the listeners, so the caller reads it after the page has settled.
    """
    errors: list[str] = []
    page.on("console", lambda message: errors.append(message.text)
            if message.type == "error" else None)
    page.on("pageerror", lambda error: errors.append(str(error)))
    return errors


def serve_app() -> tuple[str, Any]:
    """Run the real Control Room Flask app on an ephemeral port; return (base_url, server)."""
    from werkzeug.serving import make_server

    from apps.control_room import server as portal

    # Threaded on purpose: the live class holds a long-lived SSE stream open, and a
    # single-threaded server would block the very static requests the page needs to load. This
    # mirrors the documented production launch (`app.run(threaded=True)`).
    httpd = make_server("127.0.0.1", 0, portal.app, threaded=True)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return f"http://127.0.0.1:{httpd.server_port}", httpd


# ── Browser geometry checks ──────────────────────────────────────────────────────────────────

#: The HTML contrast walker. It reuses the SVG gate's parse/lin/lum/ratio math, then walks text
#: nodes under every resting region with a TreeWalker, compositing the effective ancestor
#: background. A non-`none` background-image behind required text is a failure (never a guess).
CONTRAST_JS = r"""
([selector, minNormal, minLarge]) => {
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
  document.querySelectorAll(selector).forEach((region) => {
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
    // First-paint evidence: the browser's own paint timing, plus the document lifecycle stage.
    paints: performance.getEntriesByType('paint').map((entry) => entry.name),
    readyState: document.readyState,
  };
}
"""

#: The IA-core probe for the live (unfixtured) portal: the acceptance contract's structural
#: checks that do not depend on any particular data — every anchor present, in viewport, a
#: non-zero box, no page/region scroll, and a recorded first paint.
IA_CORE_JS = r"""
() => {
  const rect = (el) => { const r = el.getBoundingClientRect();
    return {x: r.x, y: r.y, width: r.width, height: r.height,
            top: r.top, bottom: r.bottom, left: r.left, right: r.right}; };
  const visible = (el) => {
    for (let n = el; n; n = n.parentElement) {
      const cs = getComputedStyle(n);
      if (n.hidden || n.getAttribute('aria-hidden') === 'true' || cs.display === 'none' ||
          cs.visibility === 'hidden') return false;
    }
    return true;
  };
  const regions = {}, answers = {};
  document.querySelectorAll('[data-region]').forEach((el) => {
    regions[el.dataset.region] = {rect: rect(el), visible: visible(el),
      scrollH: el.scrollHeight, clientH: el.clientHeight,
      scrollW: el.scrollWidth, clientW: el.clientWidth};
  });
  document.querySelectorAll('[data-answer]').forEach((el) => {
    const parent = el.closest('[data-region]');
    answers[el.dataset.answer] = {region: parent ? parent.dataset.region : null,
      rect: rect(el), visible: visible(el)};
  });
  const page = document.scrollingElement;
  return {
    innerWidth: window.innerWidth, innerHeight: window.innerHeight,
    scrollWidth: page.scrollWidth, scrollHeight: page.scrollHeight,
    regions, answers,
    paints: performance.getEntriesByType('paint').map((entry) => entry.name),
    readyState: document.readyState,
  };
}
"""


#: Probe the open trends lens: per-chart body box, mark count, and empty/error state.
CHART_PROBE_JS = r"""
() => {
  const rect = (el) => { const r = el.getBoundingClientRect();
    return {x: r.x, y: r.y, width: r.width, height: r.height}; };
  const lens = document.querySelector('[data-chart-lens]');
  const charts = [];
  document.querySelectorAll('[data-chart]').forEach((card) => {
    const body = card.querySelector('[data-chart-body]');
    const svg = body ? body.querySelector('svg') : null;
    charts.push({
      id: card.getAttribute('data-chart'),
      body: body ? rect(body) : null,
      hasSvg: Boolean(svg),
      viewBox: svg ? svg.getAttribute('viewBox') : null,
      aria: svg ? (svg.getAttribute('aria-label') || '') : '',
      marks: body ? body.querySelectorAll('polyline,path,circle,rect,line').length : 0,
      gauges: body ? body.querySelectorAll('.chart-gauge').length : 0,
      statusCells: body ? body.querySelectorAll('.chart-status-cell').length : 0,
      empty: body ? Boolean(body.querySelector('[data-chart-empty]')) : false,
      error: body ? Boolean(body.querySelector('[data-chart-error]')) : false,
      table: Boolean(card.querySelector('[data-chart-table]')),
    });
  });
  const page = document.scrollingElement;
  return {
    open: Boolean(lens && !lens.hidden),
    lens: lens ? rect(lens) : null,
    charts: charts,
    innerHeight: window.innerHeight,
    scrollHeight: page.scrollHeight,
  };
}
"""


def _chart_history(base: dict[str, Any]) -> list[dict[str, Any]]:
    """Six deterministic samples for the non-empty chart case (varying counts and cost)."""
    counts = [
        {"running": 2, "queued": 4, "failed": 0, "live": 1},
        {"running": 3, "queued": 3, "failed": 1, "live": 2},
        {"running": 5, "queued": 1, "failed": 1, "live": 3},
        {"running": 4, "queued": 2, "failed": 2, "live": 3},
        {"running": 6, "queued": 0, "failed": 1, "live": 4},
        {"running": 5, "queued": 1, "failed": 1, "live": 3},
    ]
    costs = [
        {"spend": "$8.00", "burn": "$0.40/h", "quota": "44%", "wallet": "$11.00",
         "leases": "$1.00", "money_risk": False},
        {"spend": "$9.10", "burn": "$0.55/h", "quota": "50%", "wallet": "$10.10",
         "leases": "$1.20", "money_risk": False},
        {"spend": "$10.20", "burn": "$0.70/h", "quota": "55%", "wallet": "$9.00",
         "leases": "$1.50", "money_risk": False},
        {"spend": "$11.10", "burn": "$0.78/h", "quota": "58%", "wallet": "$8.20",
         "leases": "$1.80", "money_risk": False},
        {"spend": "$12.00", "burn": "$0.80/h", "quota": "60%", "wallet": "$7.80",
         "leases": "$2.00", "money_risk": False},
        {"spend": "$12.40", "burn": "$0.82/h", "quota": "61%", "wallet": "$7.60",
         "leases": "$2.10", "money_risk": False},
    ]
    samples = []
    for index in range(6):
        payload = copy.deepcopy(base)
        payload["control_epoch"] = 40 + index
        payload["run_counts"] = counts[index]
        payload["cost"] = costs[index]
        samples.append(payload)
    return samples


def _sse_frames(payloads: list[dict[str, Any]], *, with_transitions: bool) -> str:
    """Build snapshot → replay_complete (→ epoch transitions) SSE frames from payloads."""
    first = payloads[0]
    frames = (
        "event: snapshot\n"
        + "data: " + json.dumps({"control_epoch": first["control_epoch"]}, separators=(",", ":"))
        + "\n\n"
        + "event: replay_complete\n"
        + "data: " + json.dumps({"control_epoch": first["control_epoch"]}, separators=(",", ":"))
        + "\n\n"
    )
    if with_transitions:
        for payload in payloads[1:]:
            frames += (
                "event: transition\n"
                + "data: " + json.dumps({"control_epoch": payload["control_epoch"],
                                         "glance": payload}, separators=(",", ":")) + "\n\n"
            )
    return frames


def run_chart_gate(out: Path, screenshots: bool) -> tuple[list[dict[str, Any]], list[str]]:
    """Open the trends lens and assert the four charts at every viewport in three states.

    Cases: ``history`` (six samples → marks), ``empty`` (one sample → explicit empty state),
    ``error`` (failed projection → explicit error state). Each chart body must be non-zero and
    inside its per-viewport budget, and the page must not scroll while the lens is open.
    """
    from playwright.sync_api import sync_playwright

    fixture = build_fixture("F-0")
    history = _chart_history(fixture)
    url, httpd = _serve()
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    cases = (
        ("history", history, True, history[0]),
        ("empty", [fixture], False, fixture),
    )
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(args=["--no-sandbox"])
            for case, payloads, with_transitions, glance_payload in cases:
                frames = _sse_frames(payloads, with_transitions=with_transitions)
                for name, (width, height) in VIEWPORTS.items():
                    label = f"{name}/{case}"
                    context = browser.new_context(
                        viewport={"width": width, "height": height}, timezone_id="UTC",
                        locale="en-US", reduced_motion="reduce", color_scheme="dark",
                    )
                    context.add_init_script(
                        "try{localStorage.setItem('control-room-theme','dark')}catch(e){}"
                    )
                    page = context.new_page()
                    page.route("**/api/**", lambda route: route.abort())
                    page.route("**/api/glance", _glance_handler(glance_payload))
                    page.route("**/api/events", _events_handler(frames))
                    page.goto(url, wait_until="domcontentloaded")
                    page.locator('[data-render-state="ready"]').wait_for(timeout=15000)
                    if case == "history":
                        # The transitions are a separate SSE batch; wait for the ring to fill so
                        # the probe sees measured marks rather than a mid-stream empty state.
                        page.wait_for_function(
                            "() => window.ControlRoomCharts"
                            " && window.ControlRoomCharts.getState().history >= 2",
                            timeout=5000,
                        )
                    page.click("#lens-open")
                    page.locator('[data-chart-lens]:not([hidden])').wait_for(timeout=5000)
                    probe = page.evaluate(CHART_PROBE_JS)
                    _check_charts(label, name, case, probe, errors)
                    contrast_failures = page.evaluate(
                        CONTRAST_JS, ["[data-chart-lens]", 4.5, 3.0]
                    )
                    for failure in contrast_failures:
                        _row(errors, label, case, "chart-contrast", json.dumps(failure))
                    if screenshots and case == "history":
                        shot = out / f"charts_{name}_dark_{width}x{height}.png"
                        page.screenshot(path=str(shot), full_page=False)
                        results.append({"case": case, "viewport": name, "screenshot": str(shot)})
                    context.close()

            # Error case: the glance fetch is refused and the stream never carries a payload.
            frames = _sse_frames([fixture], with_transitions=False)
            for name, (width, height) in VIEWPORTS.items():
                context = browser.new_context(
                    viewport={"width": width, "height": height}, timezone_id="UTC",
                    locale="en-US", reduced_motion="reduce", color_scheme="dark",
                )
                page = context.new_page()
                page.route("**/api/glance", lambda route: route.abort())
                page.route("**/api/events", _events_handler(frames))
                page.goto(url, wait_until="domcontentloaded")
                page.wait_for_timeout(2500)  # the 2s ready fallback when no replay boundary
                page.click("#lens-open")
                page.locator('[data-chart-lens]:not([hidden])').wait_for(timeout=5000)
                probe = page.evaluate(CHART_PROBE_JS)
                _check_charts(f"{name}/error", name, "error", probe, errors)
                context.close()
            browser.close()
    finally:
        if httpd is not None:
            httpd.shutdown()
    return results, errors


def _check_charts(label: str, viewport: str, case: str, probe: dict[str, Any],
                  errors: list[str]) -> None:
    """Assert one lens probe: presence, budget, marks/empty/error, a11y name, no page scroll."""
    if not probe.get("open"):
        _row(errors, label, case, "chart", "lens did not open")
        return
    ids = [chart["id"] for chart in probe["charts"]]
    if sorted(ids) != sorted(CHART_IDS):
        _row(errors, label, case, "chart", f"charts {ids} want {list(CHART_IDS)}")
    max_height = CHART_BODY_MAX[viewport]
    for chart in probe["charts"]:
        body = chart.get("body") or {}
        if not body or body.get("width", 0) <= 0 or body.get("height", 0) <= 0:
            _row(errors, label, case, "chart", f"{chart['id']} body {body}")
            continue
        if body["height"] > max_height + 2:
            _row(errors, label, case, "chart-budget",
                 f"{chart['id']} body height {body['height']:.0f} > {max_height}")
        if not chart.get("table"):
            _row(errors, label, case, "chart-table", f"{chart['id']} missing textual equivalent")
        if case == "history":
            if chart["id"] == "dependency":
                # Dependency health is gauges + a status grid, not a time-series SVG.
                if chart.get("gauges", 0) < 2 or chart.get("statusCells", 0) < 4:
                    _row(errors, label, case, "chart-blank",
                         f"dependency gauges={chart.get('gauges')} "
                         f"status={chart.get('statusCells')}")
            elif not chart.get("hasSvg") or not chart.get("viewBox") or not chart.get("aria"):
                _row(errors, label, case, "chart-svg",
                     f"{chart['id']} svg/viewBox/aria incomplete")
            elif chart.get("marks", 0) <= 0:
                _row(errors, label, case, "chart-blank", f"{chart['id']} has no marks")
            if chart.get("empty") or chart.get("error"):
                _row(errors, label, case, "chart-state", f"{chart['id']} wrong state")
        elif case == "empty":
            if not chart.get("empty"):
                _row(errors, label, case, "chart-empty", f"{chart['id']} lacks empty state")
        elif case == "error":
            if not chart.get("error"):
                _row(errors, label, case, "chart-error", f"{chart['id']} lacks error state")
    if probe["scrollHeight"] > probe["innerHeight"] + 1:
        _row(errors, label, case, "chart-page-scroll",
             f"page scrollHeight {probe['scrollHeight']} > {probe['innerHeight']}")


#: Probe the SVG visuals inside the open R4 dock.
VISUAL_PROBE_JS = r"""
() => {
  const rect = (el) => { const r = el.getBoundingClientRect();
    return {x: r.x, y: r.y, width: r.width, height: r.height}; };
  const out = {};
  ['evidence-ladder', 'dependency-flow'].forEach((id) => {
    const el = document.querySelector('[data-visual="' + id + '"]');
    if (!el) { out[id] = {present: false}; return; }
    out[id] = {
      present: true,
      viewBox: el.getAttribute('viewBox'),
      role: el.getAttribute('role'),
      aria: el.getAttribute('aria-label') || '',
      hasTitle: Boolean(el.querySelector('title')),
      hasDesc: Boolean(el.querySelector('desc')),
      textNodes: el.querySelectorAll('text').length,
      marks: el.querySelectorAll('path,rect,circle,line,polyline').length,
      box: rect(el),
    };
  });
  out.affected = Boolean(document.querySelector('[data-visual-affected]'));
  out.action = Boolean(document.querySelector('[data-visual-action]'));
  out.dockOpen = Boolean(document.getElementById('selection-dock')
    && !document.getElementById('selection-dock').hidden);
  out.innerHeight = window.innerHeight;
  out.scrollHeight = document.scrollingElement.scrollHeight;
  return out;
}
"""

#: SVG `<text>` contrast: the same parse/luminance math as the HTML walker, but the foreground
#: is the computed `fill` (SVG text has no `color`) against the composited ancestor background.
SVG_TEXT_CONTRAST_JS = r"""
([selector, minNormal, minLarge]) => {
  const parseColor = (str) => {
    if (!str) return null;
    str = String(str).trim().toLowerCase();
    if (!str || str === 'none') return null;
    if (str === 'transparent') return [0,0,0,0];
    let m;
    if ((m = str.match(/^rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:[,\s/]+([\d.]+))?\s*\)$/)))
      return [+m[1], +m[2], +m[3], m[4] === undefined ? 1 : Math.min(1, +m[4])];
    return null;
  };
  const lin = (c) => { c /= 255; return c <= 0.03928 ? c/12.92 : Math.pow((c+0.055)/1.055, 2.4); };
  const lum = (c) => 0.2126*lin(c[0]) + 0.7152*lin(c[1]) + 0.0722*lin(c[2]);
  const ratio = (a, b) => { const x = lum(a), y = lum(b); const hi = Math.max(x,y), lo = Math.min(x,y);
    return (hi + 0.05) / (lo + 0.05); };
  const bgFor = (el) => {
    let cur = el.parentElement, acc = null;
    while (cur && cur.nodeType === 1) {
      const c = parseColor(getComputedStyle(cur).backgroundColor);
      if (c && c[3] > 0) {
        if (!acc) acc = c;
        else acc = [c[0], c[1], c[2], 1];
        if (c[3] >= 1) return acc.slice(0,3);
      }
      cur = cur.parentElement;
    }
    return acc ? acc.slice(0,3) : [13,16,20];
  };
  const fails = [];
  document.querySelectorAll(selector + ' text').forEach((t) => {
    const label = (t.textContent || '').trim();
    if (!label) return;
    const cs = getComputedStyle(t);
    const fg = parseColor(cs.fill);
    if (!fg || fg[3] < 0.5) { fails.push({text: label.slice(0,30), fill: cs.fill, ratio: 0}); return; }
    const bg = bgFor(t);
    const r = ratio(fg, bg);
    const size = parseFloat(cs.fontSize) || 9;
    const need = size >= 24 ? minLarge : minNormal;
    if (r < need) fails.push({text: label.slice(0,30), fill: cs.fill, ratio: Math.round(r*100)/100});
  });
  return fails;
}
"""

#: Max rendered SVG box (px) per visual at desktop; the mobile dock stacks and may scroll, so
#: only the desktop/narrow box budgets are binding.
VISUAL_BUDGET = {"evidence-ladder": 226, "dependency-flow": 96}


def _check_visuals(label: str, viewport: str, probe: dict[str, Any], errors: list[str]) -> None:
    """Assert the R4 visuals: presence, a11y, real text, marks, and box budget."""
    if not probe.get("dockOpen"):
        _row(errors, label, "a2", "visual", "selection dock did not open")
        return
    for visual in ("evidence-ladder", "dependency-flow"):
        info = probe.get(visual) or {}
        if not info.get("present"):
            _row(errors, label, "a2", "visual", f"{visual} not rendered")
            continue
        if not info.get("viewBox") or info.get("role") != "img" or not info.get("aria"):
            _row(errors, label, "a2", "visual-a11y",
                 f"{visual} viewBox/role/aria incomplete")
        if not info.get("hasTitle") or not info.get("hasDesc"):
            _row(errors, label, "a2", "visual-a11y", f"{visual} missing title/desc")
        if info.get("textNodes", 0) <= 0:
            _row(errors, label, "a2", "visual-text", f"{visual} has no real <text>")
        if info.get("marks", 0) <= 0:
            _row(errors, label, "a2", "visual-marks", f"{visual} has no marks")
        box = info.get("box") or {}
        if box.get("width", 0) <= 0 or box.get("height", 0) <= 0:
            _row(errors, label, "a2", "visual-box", f"{visual} zero box {box}")
        elif viewport != "mobile" and box["height"] > VISUAL_BUDGET[visual] + 4:
            _row(errors, label, "a2", "visual-budget",
                 f"{visual} height {box['height']:.0f} > {VISUAL_BUDGET[visual]}")
    if not probe.get("affected") or not probe.get("action"):
        _row(errors, label, "a2", "visual-action", "affected record/action missing")
    if probe["scrollHeight"] > probe["innerHeight"] + 1:
        _row(errors, label, "a2", "visual-page-scroll",
             f"page scrollHeight {probe['scrollHeight']} > {probe['innerHeight']}")


def run_visual_gate(out: Path, screenshots: bool) -> tuple[list[dict[str, Any]], list[str]]:
    """Select the first run, open R4, and assert the a2 SVG visuals at every viewport/theme.

    Also asserts the visuals are NOT shown at rest (brief §10: no static diagram in the
    resting room) and that the SVG `<text>` meets WCAG-AA contrast.
    """
    from playwright.sync_api import sync_playwright

    fixture = build_fixture("F-0")
    frames = _sse_frames([fixture], with_transitions=False)
    url, httpd = _serve()
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(args=["--no-sandbox"])
            for theme in ("dark", "light"):
                for name, (width, height) in VIEWPORTS.items():
                    label = f"{name}/{theme}"
                    context = browser.new_context(
                        viewport={"width": width, "height": height}, timezone_id="UTC",
                        locale="en-US", reduced_motion="reduce", color_scheme=theme,
                    )
                    context.add_init_script(
                        f"try{{localStorage.setItem('control-room-theme','{theme}')}}catch(e){{}}"
                    )
                    page = context.new_page()
                    page.route("**/api/**", lambda route: route.abort())
                    page.route("**/api/glance", _glance_handler(fixture))
                    page.route("**/api/events", _events_handler(frames))
                    page.goto(url, wait_until="domcontentloaded")
                    page.locator('[data-render-state="ready"]').wait_for(timeout=15000)
                    # No topology in the resting room: the dock (and its visuals) stays hidden.
                    if page.evaluate(
                        "() => { const d=document.getElementById('selection-dock');"
                        " return !!(d && !d.hidden); }"
                    ):
                        _row(errors, label, "a2", "visual-resting", "dock visible at rest")
                    page.locator('[data-region="R2"] [data-run-id]').first.click()
                    page.locator("#selection-dock:not([hidden])").wait_for(timeout=5000)
                    page.wait_for_function(
                        "() => document.querySelector('[data-visual=\"evidence-ladder\"]')",
                        timeout=5000,
                    )
                    probe = page.evaluate(VISUAL_PROBE_JS)
                    _check_visuals(label, name, probe, errors)
                    for failure in page.evaluate(
                        SVG_TEXT_CONTRAST_JS, ["[data-visual]", 4.5, 3.0]
                    ):
                        _row(errors, label, "a2", "visual-contrast", json.dumps(failure))
                    if screenshots and theme == "dark":
                        shot = out / f"visuals_{name}_dark_{width}x{height}.png"
                        page.screenshot(path=str(shot), full_page=False)
                        results.append({"case": "visuals", "viewport": name,
                                        "screenshot": str(shot)})
                    context.close()
            browser.close()
    finally:
        if httpd is not None:
            httpd.shutdown()
    return results, errors


#: Probe the styling/a11y contract: tabular numerals, motion, landmarks, recognizability
#: carriers (the §4.2 sentences' screenshot elements).
STYLE_PROBE_JS = r"""
() => {
  const cs = (sel, prop) => { const el = document.querySelector(sel);
    return el ? getComputedStyle(el)[prop] : null; };
  const value = document.querySelector('[data-region="R2"] [data-value]');
  const regions = Array.from(document.querySelectorAll('[data-region]')).map((el) => ({
    role: el.getAttribute('role'), label: el.getAttribute('aria-label') || '' }));
  return {
    numeric: value ? getComputedStyle(value).fontVariantNumeric : '',
    rowTransition: cs('.run-row', 'transitionDuration'),
    regions: regions,
    liveRegion: Boolean(document.querySelector('[aria-live="polite"]')),
    carriers: {
      session: Boolean(document.querySelector('[data-field="session.identity"]')),
      eligibility: Boolean(document.querySelector('[data-field="decision.eligibility"]')),
      receipt: Boolean(document.querySelector('[data-field="decision.receipt"]')),
      advisory: Boolean(document.querySelector('[data-evidence-class="advisory"]')),
      measured: Boolean(document.querySelector('[data-evidence-class="measured"]')),
      cost: Boolean(document.querySelector('[data-field="cost.provenance"]')),
      authority: Boolean(document.querySelector('[data-authority="controller"]'))
        || Boolean(document.querySelector('[data-answer="ON-G5"] [data-field="decision.authority"]')),
    },
  };
}
"""

#: Read the focus ring of whatever Tab landed on.
FOCUS_PROBE_JS = r"""
() => {
  const el = document.activeElement;
  if (!el || el === document.body) return {focusable: false};
  const cs = getComputedStyle(el);
  return {
    focusable: true,
    id: el.id || '',
    cls: el.className || '',
    outlineStyle: cs.outlineStyle,
    outlineWidth: parseFloat(cs.outlineWidth) || 0,
  };
}
"""


def _check_style(label: str, viewport: str, probe: dict[str, Any], errors: list[str]) -> None:
    """Assert the shape of the styling/a11y contract for one rendered page."""
    if "tabular-nums" not in str(probe.get("numeric", "")):
        _row(errors, label, "a3", "tabular-numerals", f"numeric={probe.get('numeric')!r}")
    for region in probe.get("regions", []):
        if region.get("role") != "region" or not region.get("label"):
            _row(errors, label, "a3", "landmark", f"region {region}")
    if not probe.get("liveRegion"):
        _row(errors, label, "a3", "live-region", "no polite live region")
    for carrier, present in (probe.get("carriers") or {}).items():
        if not present:
            _row(errors, label, "a3", "recognizability", f"missing carrier: {carrier}")
    # The motion token must be inside the brief's 100-240ms budget.
    for prop in ("rowTransition",):
        value = str(probe.get(prop, "") or "")
        for part in value.split(","):
            seconds = part.strip().rstrip("s")
            try:
                ms = float(seconds) * 1000
            except ValueError:
                continue
            if ms > 240.5:
                _row(errors, label, "a3", "motion-budget", f"{prop} {value}")


def run_style_gate(out: Path, screenshots: bool) -> tuple[list[dict[str, Any]], list[str]]:
    """Run the a3 styling/a11y class: tokens, focus rings, reduced motion, recognizability.

    Two contexts per viewport: a normal one (motion budget + focus rings via real Tab presses)
    and a reduced-motion one (every transition/animation must collapse).
    """
    from playwright.sync_api import sync_playwright

    fixture = build_fixture("F-0")
    frames = _sse_frames([fixture], with_transitions=False)
    url, httpd = _serve()
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(args=["--no-sandbox"])
            for name, (width, height) in VIEWPORTS.items():
                context = browser.new_context(
                    viewport={"width": width, "height": height}, timezone_id="UTC",
                    locale="en-US", color_scheme="dark",
                )
                context.add_init_script(
                    "try{localStorage.setItem('control-room-theme','dark')}catch(e){}"
                )
                page = context.new_page()
                page.route("**/api/**", lambda route: route.abort())
                page.route("**/api/glance", _glance_handler(fixture))
                page.route("**/api/events", _events_handler(frames))
                page.goto(url, wait_until="domcontentloaded")
                page.locator('[data-render-state="ready"]').wait_for(timeout=15000)
                _check_style(name, name, page.evaluate(STYLE_PROBE_JS), errors)

                # Focus rings: real keyboard Tab presses so :focus-visible actually applies.
                page.locator("body").click(position={"x": 2, "y": 2})
                for _ in range(5):
                    page.keyboard.press("Tab")
                    focus = page.evaluate(FOCUS_PROBE_JS)
                    if focus.get("focusable") and (
                        focus.get("outlineStyle") == "none" or focus.get("outlineWidth", 0) <= 0
                    ):
                        _row(errors, name, "a3", "focus-ring", json.dumps(focus))
                if screenshots:
                    shot = out / f"style_{name}_dark_{width}x{height}.png"
                    page.screenshot(path=str(shot), full_page=False)
                    results.append({"case": "style", "viewport": name, "screenshot": str(shot)})
                context.close()

                reduced = browser.new_context(
                    viewport={"width": width, "height": height}, timezone_id="UTC",
                    locale="en-US", color_scheme="dark", reduced_motion="reduce",
                )
                rpage = reduced.new_page()
                rpage.route("**/api/**", lambda route: route.abort())
                rpage.route("**/api/glance", _glance_handler(fixture))
                rpage.route("**/api/events", _events_handler(frames))
                rpage.goto(url, wait_until="domcontentloaded")
                rpage.locator('[data-render-state="ready"]').wait_for(timeout=15000)
                motion = rpage.evaluate(
                    "() => { const el=document.querySelector('.run-row');"
                    " const cs=el?getComputedStyle(el):null;"
                    " return {transition: cs?cs.transitionDuration:'',"
                    " animation: cs?cs.animationDuration:''}; }"
                )
                for key, value in motion.items():
                    if not value:
                        continue
                    # Every part must collapse to (near) zero: 0s, or the global rule's
                    # 0.001ms !important. A positive duration is a reduced-motion failure.
                    for part in str(value).split(","):
                        seconds = float(part.strip().rstrip("s") or "0")
                        if seconds > 0.01:
                            _row(errors, name, "a3", "reduced-motion", f"{key}={value}")
                reduced.close()
            browser.close()
    finally:
        if httpd is not None:
            httpd.shutdown()
    return results, errors


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

    base, httpd = _serve()
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

                        _ensure_paint(page)
                        geometry = page.evaluate(GEOMETRY_JS)
                        _check_geometry(fixture_id, name, theme, geometry, errors)
                        # A console error is a loaded-page defect even when geometry is intact.
                        for message in console_errors:
                            _row(errors, label, fixture_id, "console", message[:200])
                        contrast_failures = page.evaluate(CONTRAST_JS, ["[data-region]", 4.5, 3.0])
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
        if httpd is not None:
            httpd.shutdown()
    return results, errors


def _check_ia_core(label: str, viewport: str, probe: dict[str, Any], errors: list[str]) -> None:
    """The live IA-core contract: anchors present/unique, in viewport, non-zero, no scroll, paint.

    Deliberately data-independent: it asserts the acceptance structure the a4 brief names (each
    anchor present, in viewport, a non-zero box, no page/region scroll) and the browser/console
    primitives, but not the fixture-specific row/marginal counts — those belong to the fixture
    class, because a live portal's run count is whatever the machinery actually has.
    """
    width, height = probe["innerWidth"], probe["innerHeight"]
    if set(probe["regions"]) != set(REGIONS):
        _row(errors, label, "live", "ia-regions", f"regions={sorted(probe['regions'])}")
    if set(probe["answers"]) != set(ANSWER_REGION):
        _row(errors, label, "live", "ia-answers", f"answers={sorted(probe['answers'])}")
    if probe["scrollHeight"] > height + 1:
        _row(errors, label, "live", "ia-page-scroll",
             f"scrollHeight {probe['scrollHeight']} > {height}")
    if probe["scrollWidth"] > width + 1:
        _row(errors, label, "live", "ia-page-scroll",
             f"scrollWidth {probe['scrollWidth']} > {width}")
    for region in REGIONS:
        info = probe["regions"].get(region)
        if not info:
            continue
        box = info["rect"]
        if not info["visible"] or box["width"] <= 0 or box["height"] <= 0:
            _row(errors, label, "live", "ia-region-box", f"{region} box={box} visible={info['visible']}")
        elif (box["top"] < -0.5 or box["bottom"] > height + 0.5
              or box["left"] < -0.5 or box["right"] > width + 0.5):
            _row(errors, label, "live", "ia-region-fold", f"{region} box={box}")
        if info["scrollH"] > info["clientH"] + 1 or info["scrollW"] > info["clientW"] + 1:
            _row(errors, label, "live", "ia-region-scroll", f"{region} scroll")
    for answer, region in ANSWER_REGION.items():
        info = probe["answers"].get(answer)
        if not info:
            continue
        if info["region"] != region:
            _row(errors, label, "live", "ia-answer-region", f"{answer} in {info['region']}")
        box = info["rect"]
        if not info["visible"] or box["width"] <= 0 or box["height"] <= 0:
            _row(errors, label, "live", "ia-answer-box", f"{answer} box={box}")
        elif box["top"] < -0.5 or box["bottom"] > height + 0.5:
            _row(errors, label, "live", "ia-answer-fold", f"{answer} box={box}")
    paints = probe.get("paints") or []
    if not any(name_ in paints for name_ in ("first-paint", "first-contentful-paint")):
        _row(errors, label, "live", "first-paint", f"paints={paints}")


def run_live_gate(
    out: Path, screenshots: bool, themes: tuple[str, ...] = THEMES
) -> tuple[list[dict[str, Any]], list[str]]:
    """Run the IA-core + contrast + console + first-paint class against the live portal.

    No request interception: the page talks to the real ``/api/glance`` and ``/api/events``. This
    is the a4 acceptance run — it proves the served screen holds the contract with whatever the
    control plane actually returns, and it is what a `--base URL` invocation checks.
    """
    from playwright.sync_api import sync_playwright

    url, httpd = _serve()
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(args=["--no-sandbox"])
            for theme in themes:
                for name, (width, height) in VIEWPORTS.items():
                    label = f"{name}/{theme}"
                    if theme == "forced-colors":
                        context = browser.new_context(
                            viewport={"width": width, "height": height}, timezone_id="UTC",
                            locale="en-US", reduced_motion="reduce", color_scheme="dark",
                            forced_colors="active",
                        )
                    else:
                        context = browser.new_context(
                            viewport={"width": width, "height": height}, timezone_id="UTC",
                            locale="en-US", reduced_motion="reduce", color_scheme=theme,
                            forced_colors="none",
                        )
                        context.add_init_script(
                            f"try{{localStorage.setItem('control-room-theme','{theme}')}}catch(e){{}}"
                        )
                    page = context.new_page()
                    console_errors = _attach_console(page)
                    page.goto(url, wait_until="domcontentloaded")
                    page.locator('[data-render-state="ready"]').wait_for(timeout=20000)
                    _ensure_paint(page)
                    probe = page.evaluate(IA_CORE_JS)
                    _check_ia_core(label, name, probe, errors)
                    for message in console_errors:
                        _row(errors, label, "live", "console", message[:200])
                    for failure in page.evaluate(CONTRAST_JS, ["[data-region]", 4.5, 3.0]):
                        _row(errors, label, "live", "contrast", json.dumps(failure))
                    if screenshots and theme == "dark":
                        shot = out / f"live_{name}_dark_{width}x{height}.png"
                        page.screenshot(path=str(shot), full_page=False)
                        results.append({"case": "live", "viewport": name,
                                        "screenshot": str(shot)})
                    context.close()
            browser.close()
    finally:
        if httpd is not None:
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

    # First paint: the browser recorded a paint timing entry. `readyState` is reported for the
    # report but is not asserted (a `domcontentloaded` gate could legitimately still be loading).
    paints = geometry.get("paints") or []
    if not any(name_ in paints for name_ in ("first-paint", "first-contentful-paint")):
        _row(errors, label, fixture_id, "first-paint", f"paints={paints}")

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
    """Write the markdown + JSON reports; return the exit code.

    The report is the gate's artifact (the website gate's pattern): status, the classes that
    ran, a per-class screenshot rollup, and the full failure list with the offending selector or
    value, so a failure is actionable without re-running the browser.
    """
    status = "PASS" if not errors and check_fixtures_exit == 0 else "FAIL"
    # Roll the screenshots up by class so the report says what each capture proves.
    by_class: dict[str, int] = {}
    for result in results:
        key = result.get("case") or result.get("fixture") or "resting"
        by_class[key] = by_class.get(key, 0) + 1
    rollup = ", ".join(f"{key} {count}" for key, count in sorted(by_class.items())) or "none"
    lines = [
        "# Control Room render gate",
        "",
        f"**Status:** {status}",
        "**Classes:** geometry (IA §10.3 G-1..G-15) · charts (a1) · visuals (a2) · style (a3) · "
        "live IA-core",
        "**Fixtures:** F-0..F-7 (deterministic; no live Redis/clock/network — waiver W2)",
        f"**Viewports:** {', '.join(f'{k} {w}x{h}' for k, (w, h) in VIEWPORTS.items())}",
        f"**Themes:** {', '.join(THEMES)}",
        "**Primitives:** present/unique · in-viewport · non-zero box · no page/region scroll · "
        "WCAG-AA contrast · first-paint · console-clean",
        "",
        f"**Screenshots:** {len(results)} ({rollup})",
        "",
    ]
    if errors:
        lines.append("## Failures")
        lines.append("")
        lines.extend(f"- {error}" for error in errors)
    else:
        lines.append("No violations.")
    lines.append("")
    lines.append("## Captures")
    lines.append("")
    for result in results:
        rel = result.get("screenshot", "")
        key = result.get("case") or result.get("fixture") or "resting"
        lines.append(f"- `{rel}` — {key}/{result.get('viewport', '?')}")
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
    parser.add_argument("--charts", action="store_true",
                        help="also run the trends-lens chart class (a1)")
    parser.add_argument("--visuals", action="store_true",
                        help="also run the R4 SVG visual class (a2)")
    parser.add_argument("--style", action="store_true",
                        help="also run the styling/a11y class (a3)")
    parser.add_argument("--live", action="store_true",
                        help="run the IA-core class against the live /api/* (no fixtures)")
    parser.add_argument("--base", default=None,
                        help="render an already-running portal at this URL instead of starting one")
    args = parser.parse_args()

    global _BASE_OVERRIDE
    if args.base:
        _BASE_OVERRIDE = args.base.rstrip("/")

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
        if args.charts:
            chart_results, chart_errors = run_chart_gate(out, not args.no_screenshot)
            results, errors = results + chart_results, errors + chart_errors
        if args.visuals:
            visual_results, visual_errors = run_visual_gate(out, not args.no_screenshot)
            results, errors = results + visual_results, errors + visual_errors
        if args.style:
            style_results, style_errors = run_style_gate(out, not args.no_screenshot)
            results, errors = results + style_results, errors + style_errors
        if args.live:
            live_results, live_errors = run_live_gate(out, not args.no_screenshot)
            results, errors = results + live_results, errors + live_errors
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
