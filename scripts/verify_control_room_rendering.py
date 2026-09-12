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
  * semantics      — every ON-G1..G7 answer's RENDERED value/state/enum vs FIXTURE truth, plus the
                     B-class carriers: presence is not proof, so the gate compares content
  * fixtures       — deterministic F-0..F-7 payloads, no live Redis/clock/network (waiver W2)
  * A a11y         — accessible names/roles, true hidden state, and the keyboard open/close path
                     with focus containment (``--a11y``)
  * E state        — epoch consistency and saturated-inbox reservation (folded into semantics)
  * P feature-parity (u5) — every ``parity_inventory.json`` surface placed on the closed palette;
                     each workbench lens requests its endpoint (wired) and renders non-empty data;
                     the R4b per-worker event stream + action band and the R4d step timings are
                     present, non-empty and structurally legal (``--parity``)

The event/state E class is otherwise named in the IA; this gate implements what it can automate
deterministically. The adversaries (``docs/reviews/control_room_facelift_{design,ia}.md``) read
the screenshots this gate writes.

Usage:
  python3 scripts/verify_control_room_rendering.py                 # full gate (needs Chromium)
  python3 scripts/verify_control_room_rendering.py --check-fixtures  # no browser: validate fixtures
  python3 scripts/verify_control_room_rendering.py --a11y             # + accessibility class
  python3 scripts/verify_control_room_rendering.py --parity           # + feature-parity class
  python3 scripts/verify_control_room_rendering.py --out DIR --json PATH --report PATH
  python3 scripts/verify_control_room_rendering.py --fixtures F-0,F-5 --no-screenshot

Exit code 0 = PASS, 1 = FAIL, 2 = browser unavailable.
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import json
import sys
import threading
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

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
    "session.identity", "spec.cell", "terminal.target", "command.current", "model.provider",
    "attempt.number", "phase.progress", "lifecycle.state", "run.live", "source.commit",
    "cost.provenance", "attention.state", "evidence.advisory", "evidence.measured",
    "evidence.source", "decision.eligibility", "decision.receipt",
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

#: Legal value domains (IA §10.2). A rendered value outside its domain is a semantic failure, not
#: a copy nit: the answer claims a state the system cannot legally be in.
SYSTEM_STATES = {"up", "degraded", "down", "unknown"}
PROJECTION_STATES = {"current", "lagging", "stale", "failing", "unknown"}
DECISION_STATES = {"pending", "none"}
RISK_STATES = {"active", "all-clear"}
ELIGIBILITY_STATES = {"observe", "inspect", "approve", "promote", "cancel", "retire", "none"}
GOVERNED_STATES = {"approve", "promote", "cancel", "retire"}
#: The severity ranks the R1 work queue orders by (IA §2 R1: severity × actionability).
SEVERITY_RANKS = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}

#: The four catalog-derived charts (facelift a1). Each must render inside its budget at every
#: breakpoint, with an explicit empty/error state, never a blank panel.
CHART_IDS = ("spend", "throughput", "failure", "dependency")
#: Max chart-body height (px) per viewport, matching the CSS `--chart-body-h` budget + tolerance.
CHART_BODY_MAX = {"desktop": 98, "narrow": 90, "mobile": 74}

# ── Feature-parity (u5) ──────────────────────────────────────────────────────────────────────
#
# The facelift dropped the old room's operational surfaces; u4 re-housed them behind the workbench
# lenses and the R4 dock. This class proves that re-housing is real: every surface placed by the
# u2 parity inventory is present, every endpoint it names is actually requested when its lens
# opens (wired), and the lens is NON-EMPTY with data (never a stub). The parity inventory is the
# enumeration; this class is the executable form of `docs/research/control_room_ia.md` §15.3.

#: The u2 parity inventory (the authoritative placement of every old panel/control/feed).
PARITY_INVENTORY = ROOT / "experiments" / "research" / "control_room" / "parity_inventory.json"
#: Deterministic payloads for the old-room endpoints (the non-empty-data contract).
PARITY_FIXTURE = FIXTURE_DIR / "parity_endpoints.json"

#: panel id -> the endpoint paths its loader MUST request when the lens opens (wired).
PARITY_PANEL_ENDPOINTS: dict[str, list[str]] = {
    "fleet": ["/api/matrix"],
    "attention": ["/api/flags"],
    "money": ["/api/subscription-usage"],
    "registry": ["/api/registry"],
    "sessions": ["/api/design-sessions", "/api/claude-agents", "/api/claude-agents/daemon"],
    "queue": ["/api/matrix"],
    "routing": ["/api/routing"],
    "docs": ["/api/docs-health"],
    "audit": ["/api/recording-audit"],
    "health": ["/api/projections"],
    "workforce": ["/api/matrix"],
}

#: The resting regions every inventory item is placed on (present at rest, one each).
PARITY_RESTING_REGIONS = ["R0", "R1", "R2", "R3a", "R3b", "R3c"]
#: The reconciled R4 dock sub-regions (per-worker event/action + step timings live here).
PARITY_DOCK_REGIONS = ["address", "worker", "evidence", "timing"]
#: The legal `data-state` on a step-timing row (interaction model §3.3: unknown is explicit).
PARITY_TIMING_STATES = {"measured", "unknown"}


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
            # Facelift repair A5-D2: every actionable row must carry the lease/cost facets, so a
            # stranger can identify spend against a hard budget from the row alone (the F-0 seed
            # supplies a known $5.00 cap and an over-cap row).
            for facet in ("budget.reserved", "budget.settled", "budget.cap",
                          "budget.headroom", "budget.settlement"):
                if row.get(facet) in (None, ""):
                    problems.append(f"{fixture_id}: row {row.get('id')} missing {facet}")
        if fixture_id == "F-0" and not any(row.get("budget.headroom") == 0
                                           for row in wire["run_sample"]):
            problems.append("F-0: needs an over-cap row (budget.headroom == 0)")
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

#: The semantic probe (IA §10 "prove the glance contract"): it reads each `ON-G1..G7` answer's
#: rendered content — values, states, ages, bucket labels, attention classes, row budget facets —
#: so the gate can compare RENDERED truth to FIXTURE truth, not merely assert that some text
#: exists. Paired with `_check_semantics`, it makes every answer literally self-sufficient.
SEMANTIC_JS = r"""
() => {
  const text = (el) => el ? (el.innerText || el.textContent || "").trim() : "";
  const answerRoot = (a) => document.querySelector('[data-answer="' + a + '"]');
  const collectFields = (a) => {
    const out = {};
    const root = answerRoot(a);
    if (!root) return out;
    root.querySelectorAll('[data-field]').forEach((f) => {
      const v = f.querySelector(':scope > [data-value]');
      out[f.dataset.field] = text(v);
    });
    return out;
  };
  const systemDims = [];
  {
    const root = answerRoot('ON-G1');
    if (root) root.querySelectorAll('[data-field]').forEach((f) => {
      const v = f.querySelector(':scope > [data-value]');
      systemDims.push({ field: f.dataset.field, value: text(v),
        state: v ? v.getAttribute('data-state') : null,
        age: v && v.hasAttribute('data-age-seconds')
          ? Number(v.getAttribute('data-age-seconds')) : null });
    });
  }
  const rows = [];
  document.querySelectorAll('[data-region="R2"] [data-run-id]').forEach((r) => {
    const values = {};
    r.querySelectorAll('[data-field]').forEach((f) => {
      const v = f.querySelector(':scope > [data-value]');
      values[f.dataset.field] = text(v);
    });
    const lease = r.querySelector('.row-lease');
    rows.push({ id: r.getAttribute('data-run-id'), values,
      budget: lease ? {
        state: lease.getAttribute('data-budget-state'),
        reserved: lease.getAttribute('data-budget-reserved'),
        cap: lease.getAttribute('data-budget-cap'),
        headroom: lease.getAttribute('data-budget-headroom'),
        settlement: lease.getAttribute('data-budget-settlement') } : null,
      hasAuthority: Boolean(r.querySelector('[data-authority="controller"]')),
      decision: r.getAttribute('data-decision') });
  });
  const attention = [];
  document.querySelectorAll('[data-region="R1"] [data-attention-class]').forEach((it) => {
    attention.push({ cls: it.getAttribute('data-attention-class'),
      key: it.getAttribute('data-item-key'),
      kind: text(it.querySelector('.item-kind')),
      ariaLabel: it.getAttribute('aria-label') || '' });
  });
  const marginals = [];
  {
    const root = answerRoot('ON-G7');
    if (root) root.querySelectorAll('[data-marginal]').forEach((m) => {
      const buckets = [];
      m.querySelectorAll('[data-bucket]').forEach((b) => {
        buckets.push({ bucket: b.getAttribute('data-bucket'),
          label: text(b.querySelector('.bucket-label')),
          value: text(b.querySelector('[data-value]')),
          category: b.getAttribute('data-category') || '' });
      });
      marginals.push({ name: m.getAttribute('data-marginal'), buckets });
    });
  }
  const answerBoxes = {};
  ['ON-G1', 'ON-G2', 'ON-G3', 'ON-G4', 'ON-G5', 'ON-G6', 'ON-G7'].forEach((a) => {
    const el = answerRoot(a);
    if (!el) { answerBoxes[a] = null; return; }
    const box = el.getBoundingClientRect();
    let visible = true;
    for (let n = el; n; n = n.parentElement) {
      const cs = getComputedStyle(n);
      if (n.hidden || cs.display === 'none' || cs.visibility === 'hidden') { visible = false; }
    }
    answerBoxes[a] = { visible, x: box.x, y: box.y, width: box.width, height: box.height,
      top: box.top, bottom: box.bottom, left: box.left, right: box.right,
      scrollH: el.scrollHeight, clientH: el.clientHeight,
      scrollW: el.scrollWidth, clientW: el.clientWidth };
  });
  const shell = document.querySelector('[data-glance-shell]');
  return {
    innerWidth: window.innerWidth, innerHeight: window.innerHeight,
    systemDims, runCounts: collectFields('ON-G2'), decision: collectFields('ON-G5'),
    risk: collectFields('ON-G3'), money: collectFields('ON-G4'),
    moneyRisk: document.querySelectorAll('[data-answer="ON-G4"] [data-money-risk]').length,
    moneyProv: text(document.getElementById('cost-prov')),
    trust: collectFields('ON-G6'), marginals, rows, attention, answerBoxes,
    shellEpoch: shell ? shell.getAttribute('data-control-epoch') : null,
    liveRegions: document.querySelectorAll('[aria-live]').length,
    dockHidden: (() => { const d = document.getElementById('selection-dock');
      return Boolean(d && d.hidden); })(),
    lensHidden: (() => { const l = document.getElementById('chart-lens');
      return Boolean(l && l.hidden); })(),
    // B-class carriers (IA §10.4): the exact element each blind statement points to.
    carriers: {
      b1: Boolean(document.querySelector('[data-answer="ON-G1"] [data-field="system.browser"]')),
      b2: Boolean(document.querySelector('[data-answer="ON-G2"] [data-field="runs.running"]')),
      b3: Boolean(document.querySelector('[data-attention-class="risk"] [data-answer="ON-G3"]')),
      b4: Boolean(document.querySelector('[data-answer="ON-G4"] [data-field="money.spend"]')),
      b5: Boolean(document.querySelector('[data-attention-class="decision"] [data-answer="ON-G5"]')),
      b6: Boolean(document.querySelector('[data-answer="ON-G6"] [data-field="trust.epoch"]')),
      b7: document.querySelectorAll('[data-answer="ON-G7"] [data-marginal]').length === 4,
      b8: Boolean(document.querySelector('[data-answer="ON-G5"] [data-field="decision.eligibility"]')),
      b9: Boolean(document.querySelector('[data-region="R2"] .session-band [data-field="session.identity"]')),
      b10: Boolean(document.querySelector('[data-region="R2"] [data-evidence-class="advisory"]'))
        && Boolean(document.querySelector('[data-region="R2"] [data-evidence-class="measured"]')),
      b11: Boolean(document.querySelector('[data-region="R2"] [data-field="decision.eligibility"]'))
        && Boolean(document.querySelector('[data-region="R2"] [data-field="decision.receipt"]')),
    },
  };
}
"""

#: The accessibility probe (IA §10.5 A-4/A-5/A-6): roles, accessible names, true hidden state and
#: the keyboard open/close path. Run against the fixtured page at both required viewports.
A11Y_JS = r"""
() => {
  const rows = Array.from(document.querySelectorAll('[data-region="R2"] [data-run-id]')).map((r) => ({
    role: r.getAttribute('role'), label: r.getAttribute('aria-label') || '' }));
  const decisions = Array.from(
    document.querySelectorAll('[data-region="R1"] [data-attention-class="decision"]')
  ).map((r) => ({ role: r.getAttribute('role'), label: r.getAttribute('aria-label') || '',
    tabindex: r.getAttribute('tabindex') }));
  const risks = Array.from(
    document.querySelectorAll('[data-region="R1"] [data-attention-class="risk"]')
  ).map((r) => ({ role: r.getAttribute('role'), label: r.getAttribute('aria-label') || '' }));
  const dock = document.getElementById('selection-dock');
  const lens = document.getElementById('chart-lens');
  return {
    rows, decisions, risks,
    dockHidden: Boolean(dock && dock.hidden),
    dockDisplay: dock ? getComputedStyle(dock).display : null,
    lensHidden: Boolean(lens && lens.hidden),
    lensDisplay: lens ? getComputedStyle(lens).display : null,
    shellPresent: Boolean(document.querySelector('[data-glance-shell]')),
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


def _check_a11y(name: str, probe: dict[str, Any], errors: list[str]) -> None:
    """Assert the IA §10.5 A-class: names/roles (A-4) and true hidden state (A-5)."""
    for row in probe.get("rows", []):
        if row.get("role") != "button" or not row.get("label"):
            _row(errors, name, "a11y", "A-4", f"run row role/label {row}")
    for item in probe.get("decisions", []):
        if item.get("role") != "button" or not item.get("label"):
            _row(errors, name, "a11y", "A-4", f"decision item role/label {item}")
    for item in probe.get("risks", []):
        if not item.get("label"):
            _row(errors, name, "a11y", "A-4", f"risk item lacks accessible name {item}")
    # A-5: inactive surfaces are truly hidden (the `hidden` attribute), not CSS-only.
    if not probe.get("dockHidden") or probe.get("dockDisplay") != "none":
        _row(errors, name, "a11y", "A-5", "selection dock is not truly hidden at rest")
    if not probe.get("lensHidden") or probe.get("lensDisplay") != "none":
        _row(errors, name, "a11y", "A-5", "chart lens is not truly hidden at rest")


def run_a11y_gate(out: Path, screenshots: bool) -> tuple[list[dict[str, Any]], list[str]]:
    """Run the IA §10.5 A-class against the fixtured page at desktop and mobile.

    A-4 (accessible names/roles), A-5 (true hidden state), A-6 (keyboard Enter opens / Escape
    closes), and A-1 (focus is contained in the modal dock and returns to the opening control).
    Screenshots are optional: the class records its evidence as pass/fail rows, not pixels.
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
            for name, (width, height) in (("desktop", (1440, 900)), ("mobile", (390, 844))):
                context = browser.new_context(
                    viewport={"width": width, "height": height}, timezone_id="UTC",
                    locale="en-US", reduced_motion="reduce", color_scheme="dark",
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
                _check_a11y(name, page.evaluate(A11Y_JS), errors)

                # A-6 + A-1: reach a run row by keyboard alone, open with Enter, contain focus,
                # then Escape and confirm focus returns to the opening row.
                page.locator("body").click(position={"x": 2, "y": 2})
                reached = False
                for _ in range(12):
                    page.keyboard.press("Tab")
                    if page.evaluate(
                        "() => { const el = document.activeElement;"
                        " return !!(el && el.matches('[data-region=\"R2\"] [data-run-id]')); }"
                    ):
                        reached = True
                        break
                if not reached:
                    _row(errors, name, "a11y", "A-6", "could not reach a run row by keyboard")
                else:
                    origin = page.evaluate(
                        "() => document.activeElement.getAttribute('data-run-id')")
                    page.keyboard.press("Enter")
                    try:
                        page.locator("#selection-dock:not([hidden])").wait_for(timeout=3000)
                    except Exception:  # noqa: BLE001 - a failed open is a finding, not a crash
                        _row(errors, name, "a11y", "A-6", "Enter did not open the dock")
                    for _ in range(6):
                        page.keyboard.press("Tab")
                    if not page.evaluate(
                        "() => { const d = document.getElementById('selection-dock');"
                        " return Boolean(d && d.contains(document.activeElement)); }"
                    ):
                        _row(errors, name, "a11y", "A-1", "focus escaped the selection dock")
                    page.keyboard.press("Escape")
                    if not page.evaluate(
                        "() => Boolean(document.getElementById('selection-dock').hidden)"):
                        _row(errors, name, "a11y", "A-5", "Escape did not close the dock")
                    returned = page.evaluate(
                        "() => document.activeElement && document.activeElement.getAttribute"
                        " ? document.activeElement.getAttribute('data-run-id') : null")
                    if returned != origin:
                        _row(errors, name, "a11y", "A-6",
                             f"focus returned to {returned!r}, not origin {origin!r}")
                if screenshots:
                    shot = out / f"a11y_{name}_dark_{width}x{height}.png"
                    page.screenshot(path=str(shot), full_page=False)
                    results.append({"case": "a11y", "viewport": name, "screenshot": str(shot)})
                context.close()
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
                        # Bind the sink into each handler (B023): the loop rebinds
                        # ``console_errors`` every iteration, and a closure over the bare
                        # name would append into whatever list the cell points at LATER.
                        page.on("console", lambda message, sink=console_errors: sink.append(message.text)
                                if message.type == "error" else None)
                        page.on("pageerror", lambda error, sink=console_errors: sink.append(str(error)))

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
                        # Semantic layer (IA §10): rendered values vs fixture truth, per answer.
                        _check_semantics(fixture_id, name, wire, page.evaluate(SEMANTIC_JS), errors)
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


def load_parity_inventory() -> dict[str, Any]:
    """Load the u2 parity inventory (the enumeration this class checks)."""
    return json.loads(PARITY_INVENTORY.read_text(encoding="utf-8"))


def load_parity_fixtures() -> dict[str, Any]:
    """Load the deterministic old-room endpoint payloads (parseable data, not a stub)."""
    raw = json.loads(PARITY_FIXTURE.read_text(encoding="utf-8"))
    return {key: value for key, value in raw.items() if not key.startswith("_")}


def _check_parity_inventory(inventory: dict[str, Any], errors: list[str]) -> None:
    """Static placement: every inventory record names a surface in the closed palette.

    This is the build-time contract the inventory generator already enforces; the gate re-checks
    it so a hand-edited inventory cannot smuggle a surface the IA never defined. It also asserts
    every named capability carries a surface and at least one member, so the "no silent drops"
    claim is auditable from the gate's own artifact.
    """
    palette = set(inventory.get("surface_palette") or {})
    if not palette:
        _row(errors, "static", "parity", "palette", "parity_inventory has no surface_palette")
        return
    for group in ("items", "endpoints", "capabilities"):
        for record in inventory.get(group, []):
            surface = record.get("surface")
            if surface not in palette:
                _row(errors, "static", "parity", "placement",
                     f"{group}:{record.get('id')} surface {surface!r} not in palette")
    for capability in inventory.get("capabilities", []):
        if not capability.get("surface"):
            _row(errors, "static", "parity", "capability-surface",
                 f"capability {capability.get('id')} has no surface")
        if not capability.get("member_ids"):
            _row(errors, "static", "parity", "capability-members",
                 f"capability {capability.get('id')} has no member ids")


def _parity_router(
    records: list[dict[str, str]],
    wire: dict[str, Any],
    glance_frames: str,
    event_frames: str,
    fixtures: dict[str, Any],
):
    """One Playwright route handler for the whole parity class.

    A single catch-all (rather than many patterns) avoids handler-ordering surprises: it records
    every request (the "wired" evidence), serves the glance/per-cell SSE and each mapped endpoint
    from fixtures, fulfills mutations with a stub success so action chips render their receipts,
    and aborts anything unmapped so a missing endpoint is a visible request, never a silent pass.
    """

    def handler(route: Any) -> None:
        request = route.request
        path = urlparse(request.url).path
        records.append({"method": request.method, "path": path})
        if request.method == "POST":
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"ok": True, "action": path.rstrip("/").rsplit("/", 1)[-1],
                                 "note": "recorded by the parity gate"}),
            )
            return
        if path == "/api/glance":
            route.fulfill(status=200, content_type="application/json", body=json.dumps(wire))
        elif path == "/api/events":
            route.fulfill(status=200, content_type="text/event-stream", body=glance_frames)
        elif path.startswith("/api/events/"):
            route.fulfill(status=200, content_type="text/event-stream", body=event_frames)
        elif path in fixtures:
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps(fixtures[path]))
        else:
            route.abort()

    return handler


def run_parity_gate(
    out: Path, screenshots: bool
) -> tuple[list[dict[str, Any]], list[str]]:
    """Run the FEATURE-PARITY + per-worker surface class (u5).

    Deterministic and fixture-driven like the rest of the gate (waiver W2):
      1. static — every parity_inventory record is placed on a palette surface;
      2. resting — every region an item is placed on is present;
      3. workbench — each lens requests its endpoint (wired) and renders non-empty data;
      4. dock — the R4b per-worker stream + action band and R4d step timings are present,
         non-empty, and structurally legal; a representative action click POSTs.
    """
    from playwright.sync_api import sync_playwright

    inventory = load_parity_inventory()
    fixtures = load_parity_fixtures()
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    _check_parity_inventory(inventory, errors)

    url, httpd = _serve()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(args=["--no-sandbox"])
            for name, (width, height) in (("desktop", (1440, 900)), ("mobile", (390, 844))):
                wire = build_fixture("F-0")
                epoch = wire["control_epoch"]
                glance_frames = (
                    "event: snapshot\n"
                    + "data: " + json.dumps({"control_epoch": epoch}, separators=(",", ":")) + "\n\n"
                    + "event: replay_complete\n"
                    + "data: " + json.dumps({"control_epoch": epoch}, separators=(",", ":")) + "\n\n"
                )
                # A few real per-cell frames so the R4b feed has live-shaped content, ending with
                # the replay boundary the client keys its stream state off.
                event_frames = (
                    "data: " + json.dumps({"type": "step_start",
                                           "part": {"name": "build"}}) + "\n\n"
                    + "data: " + json.dumps({"type": "tool_use",
                                             "part": {"name": "bash", "state": {"status": "completed"}}}) + "\n\n"
                    + "data: " + json.dumps({"type": "step_finish",
                                             "part": {"cost": 0.01,
                                                      "tokens": {"input": 120, "output": 40}}}) + "\n\n"
                    + "event: replay_complete\ndata: {}\n\n"
                )
                context = browser.new_context(
                    viewport={"width": width, "height": height}, timezone_id="UTC",
                    locale="en-US", reduced_motion="reduce", color_scheme="dark",
                )
                page = context.new_page()
                records: list[dict[str, str]] = []
                console_errors = _attach_console(page)
                page.route("**/api/**",
                           _parity_router(records, wire, glance_frames, event_frames, fixtures))
                page.goto(url, wait_until="domcontentloaded")
                page.locator('[data-render-state="ready"]').wait_for(timeout=20000)

                # 2. every resting region is present exactly once.
                for region in PARITY_RESTING_REGIONS:
                    count = page.locator(f'[data-region="{region}"]').count()
                    if count != 1:
                        _row(errors, name, "parity", "resting-region",
                             f"{region} count={count}")

                # 3. the workbench lenses: wired + non-empty.
                page.click("#workbench-open")
                page.locator("#workbench:not([hidden])").wait_for(timeout=5000)
                for panel, expected in PARITY_PANEL_ENDPOINTS.items():
                    records.clear()
                    page.click(f'#workbench-nav [data-lens-target="{panel}"]')
                    page.locator(f"#wb-{panel}:not([hidden])").wait_for(timeout=5000)
                    # Wait for the lens loader to leave its loading state; a stuck loader is
                    # caught by the non-empty check below rather than by a timeout here.
                    with contextlib.suppress(Exception):
                        page.wait_for_function(
                            """(sel) => {
                              const el = document.querySelector(sel);
                              return el && !el.querySelector('[data-panel-state="loading"]');
                            }""",
                            arg=f"#wb-{panel}", timeout=5000,
                        )
                    got = {record["path"] for record in records}
                    for path in expected:
                        if path not in got:
                            _row(errors, name, "parity-wire", panel, f"{path} not requested")
                    probe = page.evaluate(
                        """(sel) => {
                          const el = document.querySelector(sel);
                          if (!el) return null;
                          const content = el.querySelectorAll(
                            '.panel-table tbody tr, .panel-item, .kv-row, .wb-action, .section-title'
                          ).length;
                          const state = el.querySelector('[data-panel-state]');
                          return {
                            content,
                            state: state ? state.getAttribute('data-panel-state') : null,
                          };
                        }""",
                        f"#wb-{panel}",
                    )
                    if not probe or probe["content"] == 0:
                        _row(errors, name, "parity-nonempty", panel, f"panel empty: {probe}")
                    elif probe["state"] == "error":
                        _row(errors, name, "parity-nonempty", panel,
                             "panel rendered an explicit error state")
                    # One representative mutation-wiring probe: the attention lens' steer chip
                    # must POST to the flags route (the handler fulfills it).
                    if panel == "attention":
                        records.clear()
                        steer = page.locator("#wb-attention [data-action='steer']")
                        if steer.count() == 0:
                            _row(errors, name, "parity-action", "steer",
                                 "attention flag rendered no steer action")
                        else:
                            steer.first.click()
                            page.wait_for_timeout(250)
                            if not any(r["method"] == "POST" and r["path"].endswith("/steer")
                                       for r in records):
                                _row(errors, name, "parity-action", "steer",
                                     "steer click did not POST to the flags route")
                if screenshots:
                    shot = out / f"parity_workbench_{name}.png"
                    page.screenshot(path=str(shot), full_page=False)
                    results.append({"case": "parity-workbench", "viewport": name,
                                    "screenshot": str(shot)})
                page.click("#workbench-close")

                # 4. the R4 dock: per-worker event/action + step timings.
                records.clear()
                page.locator('[data-region="R2"] [data-run-id]').first.click()
                page.locator("#selection-dock:not([hidden])").wait_for(timeout=5000)
                page.wait_for_timeout(400)
                for sub in PARITY_DOCK_REGIONS:
                    if page.locator(f'#selection-dock [data-dock-region="{sub}"]').count() != 1:
                        _row(errors, name, "parity-dock", sub, "sub-region missing/duplicate")
                got = {record["path"] for record in records}
                if not any(path.startswith("/api/events/") for path in got):
                    _row(errors, name, "parity-dock", "worker-stream",
                         "no per-worker /api/events/<cell> request")
                entries = page.locator(
                    "#selection-dock [data-dock-region='worker'] [data-feed-entry]").count()
                if entries < 1:
                    _row(errors, name, "parity-dock", "worker-feed", f"{entries} event entries")
                actions = page.locator(
                    "#selection-dock [data-dock-region='worker'] [data-action]").count()
                if actions < 1:
                    _row(errors, name, "parity-dock", "worker-actions", "no [data-action] chips")
                timings = page.locator(
                    "#selection-dock [data-dock-region='timing'] [data-timing]").count()
                if timings < 1:
                    _row(errors, name, "parity-dock", "step-timings", "no [data-timing] rows")
                states = page.eval_on_selector_all(
                    "#selection-dock [data-dock-region='timing'] [data-timing]",
                    "els => els.map(e => e.getAttribute('data-state'))",
                )
                illegal = [state for state in states if state not in PARITY_TIMING_STATES]
                if illegal:
                    _row(errors, name, "parity-dock", "step-timing-state", f"illegal {illegal}")
                if screenshots:
                    shot = out / f"parity_dock_{name}.png"
                    page.screenshot(path=str(shot), full_page=False)
                    results.append({"case": "parity-dock", "viewport": name,
                                    "screenshot": str(shot)})
                for message in console_errors:
                    _row(errors, name, "parity", "console", message[:200])
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
        if any(abs(a - b) > 1 for a, b in zip(got, want, strict=True)):
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


def _check_semantics(
    fixture_id: str, name: str, wire: dict[str, Any], probe: dict[str, Any], errors: list[str]
) -> None:
    """Assert RENDERED truth against FIXTURE truth for every `ON-G1..G7` answer (IA §10).

    This is the semantic layer the a6 adversary found missing: presence is not proof. For each
    anchor it checks the value/state/enum the operator actually sees, that the answer's box is
    visible, non-zero, in-viewport and non-scrolling, and (for the B class) that every blind
    statement's carrying element exists. A mismatch here is a glance-contract failure even when
    the geometry is perfect.
    """

    def fail(check: str, detail: str) -> None:
        _row(errors, name, fixture_id, check, detail)

    height = probe["innerHeight"]
    width = probe["innerWidth"]

    # ── per-anchor box: visible, non-zero, in-viewport, no internal scroll ────────────────
    for answer, box in probe["answerBoxes"].items():
        if not box:
            fail("SEM-box", f"{answer} missing")
            continue
        if not box["visible"] or box["width"] <= 0 or box["height"] <= 0:
            fail("SEM-box", f"{answer} box {box['width']}x{box['height']} visible={box['visible']}")
        elif (box["top"] < -0.5 or box["bottom"] > height + 0.5
              or box["left"] < -0.5 or box["right"] > width + 0.5):
            fail("SEM-fold", f"{answer} box "
                 f"{tuple(round(box[k], 1) for k in ('left', 'top', 'right', 'bottom'))}")
        if box["scrollH"] > box["clientH"] + 1 or box["scrollW"] > box["clientW"] + 1:
            fail("SEM-answer-scroll", f"{answer} scrolls")

    # ── ON-G1 system: legal enum, numeric age, exact fixture value ────────────────────────
    dims = {entry["field"]: entry for entry in probe["systemDims"]}
    for key in ("browser", "control", "workers", "projections"):
        field = "system." + key
        got = dims.get(field)
        want = wire["system"][key]
        if not got:
            fail("SEM-G1", f"{field} missing")
            continue
        if got["state"] not in SYSTEM_STATES:
            fail("SEM-G1", f"{field} illegal state {got['state']!r}")
        if got["age"] is None or got["age"] < 0:
            fail("SEM-G1", f"{field} non-numeric age {got['age']!r}")
        if got["state"] != want["state"] or got["age"] != want["age_seconds"]:
            fail("SEM-G1", f"{field} rendered {got['state']}/{got['age']} "
                 f"fixture {want['state']}/{want['age_seconds']}")

    # ── ON-G2 counts: exact fixture equality ──────────────────────────────────────────────
    for key in ("running", "queued", "failed", "live"):
        got = probe["runCounts"].get("runs." + key)
        if got != str(wire["run_counts"][key]):
            fail("SEM-G2", f"runs.{key} rendered {got!r} fixture {wire['run_counts'][key]!r}")

    # ── ON-G3 risk: legal state, reserved identity, explicit all-clear ────────────────────
    risk = probe["risk"]
    want_risk = wire["attention"]["risk"]
    if risk.get("risk.state") not in RISK_STATES:
        fail("SEM-G3", f"illegal risk state {risk.get('risk.state')!r}")
    for field in ("risk.identity", "risk.state", "risk.action"):
        if not risk.get(field):
            fail("SEM-G3", f"{field} empty")
    if want_risk["state"] == "all-clear":
        if risk.get("risk.identity") != "none" or risk.get("risk.action") != "none":
            fail("SEM-G3", f"all-clear must render identity/action none: {risk}")
    elif risk.get("risk.identity") != want_risk["identity"]:
        fail("SEM-G3", f"risk.identity {risk.get('risk.identity')!r} "
             f"fixture {want_risk['identity']!r}")

    # ── ON-G4 money: five exact values, marker count, visible provenance ─────────────────
    want_cost = wire["cost"]
    for field, key in (("money.spend", "spend"), ("money.burn", "burn"), ("money.quota", "quota"),
                       ("money.wallet", "wallet"), ("money.leases", "leases")):
        got = probe["money"].get(field)
        if got != str(want_cost.get(key, "unknown")):
            fail("SEM-G4", f"{field} rendered {got!r} fixture {want_cost.get(key)!r}")
    expected_marker = 1 if want_cost.get("money_risk") else 0
    if probe["moneyRisk"] != expected_marker:
        fail("SEM-G4", f"money-risk markers {probe['moneyRisk']} want {expected_marker}")
    if not probe["moneyProv"]:
        fail("SEM-G4", "money answer lacks visible source+age provenance")

    # ── ON-G5 decision: legal state/eligibility, none-pending consistency ─────────────────
    decision = probe["decision"]
    want_decision = wire["attention"]["decision"]
    if decision.get("decision.state") not in DECISION_STATES:
        fail("SEM-G5", f"illegal decision state {decision.get('decision.state')!r}")
    if decision.get("decision.eligibility") not in ELIGIBILITY_STATES:
        fail("SEM-G5", f"illegal eligibility {decision.get('decision.eligibility')!r}")
    if want_decision["state"] == "none":
        for field in ("decision.target", "decision.kind", "decision.authority",
                      "decision.eligibility"):
            if decision.get(field) != "none":
                fail("SEM-G5", f"none-decision must render {field}=none, got {decision.get(field)!r}")
    else:
        if (decision.get("decision.target") != want_decision["target"]
                or decision.get("decision.kind") != want_decision["kind"]):
            fail("SEM-G5", f"decision rendered {decision} fixture {want_decision}")

    # ── ON-G6 trust: legal enum, integer counts, epoch + unknown-count truth ──────────────
    trust = probe["trust"]
    want_trust = wire["trust"]
    if trust.get("trust.projection_state") not in PROJECTION_STATES:
        fail("SEM-G6", f"illegal projection state {trust.get('trust.projection_state')!r}")
    for key in ("degraded_count", "stale_count", "partial_count", "unknown_count"):
        raw = trust.get("trust." + key)
        try:
            if int(raw) < 0:
                raise ValueError
        except (TypeError, ValueError):
            fail("SEM-G6", f"{key} not a non-negative integer: {raw!r}")
    if str(trust.get("trust.epoch")) != str(want_trust["epoch"]):
        fail("SEM-G6", f"trust.epoch {trust.get('trust.epoch')!r} "
             f"fixture {want_trust['epoch']!r}")
    if str(trust.get("trust.unknown_count")) != str(want_trust["unknown_count"]):
        fail("SEM-G6", f"unknown_count {trust.get('trust.unknown_count')!r} "
             f"fixture {want_trust['unknown_count']!r}")

    # ── ON-G7 composition: four marginals, three explicit legible buckets, fixture truth ──
    marginals = {entry["name"]: entry for entry in probe["marginals"]}
    for marginal_name in ("model", "condition", "provider", "lifecycle"):
        marginal = marginals.get(marginal_name)
        if not marginal:
            fail("SEM-G7", f"marginal {marginal_name} missing")
            continue
        buckets = {bucket["bucket"]: bucket for bucket in marginal["buckets"]}
        if set(buckets) != {"top", "other", "unknown"}:
            fail("SEM-G7", f"{marginal_name} buckets {sorted(buckets)}")
        for bucket_name, bucket in buckets.items():
            # The VISIBLE label must be the full bucket word (never 't'/'o'/'u' shorthand).
            if bucket["label"] != bucket_name:
                fail("SEM-G7", f"{marginal_name}.{bucket_name} label {bucket['label']!r} not legible")
            want_value = str(wire["composition"][marginal_name][bucket_name])
            if bucket["value"] != want_value:
                fail("SEM-G7", f"{marginal_name}.{bucket_name} rendered {bucket['value']!r} "
                     f"fixture {want_value!r}")
        if not buckets.get("top", {}).get("category"):
            fail("SEM-G7", f"{marginal_name} top bucket lacks data-category")

    # ── R2 rows: spec/cell, paired evidence, receipt, budget facets, authority ────────────
    expected_rows = wire["run_sample"][:len(probe["rows"])]

    def unmark(value: Any) -> str:
        """Strip the compact viewport's explicit semantic mark (`spec:` / `cmd:` / `said:`...).

        The density ladder prefixes a mobile value with its field mark so a stranger never infers
        field meaning from order; the underlying value is unchanged, so the semantic layer
        compares the unmarked token against fixture truth.
        """
        text = str(value if value is not None else "")
        head, sep, tail = text.partition(":")
        return tail if sep and head.isalpha() and len(head) <= 5 else text

    for index, row in enumerate(probe["rows"]):
        expected = expected_rows[index] if index < len(expected_rows) else {}
        if not row["values"].get("spec.cell"):
            fail("SEM-R2", f"row {row['id']} missing spec/cell")
        elif unmark(row["values"].get("spec.cell")) != str(expected.get("spec.cell")):
            fail("SEM-R2", f"row {row['id']} spec {row['values'].get('spec.cell')!r} "
                 f"fixture {expected.get('spec.cell')!r}")
        if row["values"].get("evidence.advisory") == row["values"].get("evidence.measured"):
            fail("SEM-R2", f"row {row['id']} ADVISORY claim equals MEASURED proof")
        for field in ("decision.eligibility", "decision.receipt", "cost.provenance"):
            if not row["values"].get(field):
                fail("SEM-R2", f"row {row['id']} {field} empty")
        budget = row["budget"] or {}
        for facet in ("reserved", "cap", "headroom", "settlement"):
            if not budget.get(facet):
                fail("SEM-R2", f"row {row['id']} budget.{facet} missing")
        if (row["values"].get("decision.eligibility") in GOVERNED_STATES
                and not row["hasAuthority"]):
            fail("SEM-R2", f"row {row['id']} governed decision lacks controller authority")

    # ── R1 attention: reserved slots + non-increasing severity ranking ────────────────────
    attention = probe["attention"]
    if not attention:
        fail("SEM-R1", "no attention items rendered")
    else:
        if attention[0]["cls"] != "decision":
            fail("SEM-R1", f"first item is {attention[0]['cls']!r}, want decision")
        if len(attention) > 1 and attention[1]["cls"] != "risk":
            fail("SEM-R1", f"second item is {attention[1]['cls']!r}, want risk")
    previous = 99
    for item in attention[2:]:
        if item["cls"] == "empty":
            continue
        rank = SEVERITY_RANKS.get(item["kind"], 99)
        if rank > previous:
            fail("SEM-R1", f"ranked order breaks: {item['kind']} after rank {previous}")
        previous = min(previous, rank)
    if fixture_id == "F-1" and any(item["cls"] == "empty" for item in attention):
        fail("SEM-R1", "F-1 saturated inbox still shows empty filler")

    # ── E-4: shell, trust share one control epoch ─────────────────────────────────────────
    if str(probe["shellEpoch"]) != str(wire["control_epoch"]):
        fail("SEM-E4", f"shell epoch {probe['shellEpoch']!r} fixture {wire['control_epoch']!r}")
    if str(trust.get("trust.epoch")) != str(probe["shellEpoch"]):
        fail("SEM-E4", f"trust epoch {trust.get('trust.epoch')!r} != shell {probe['shellEpoch']!r}")

    # ── B-class carriers: every blind statement's element is present ──────────────────────
    for carrier, present in (probe.get("carriers") or {}).items():
        if not present:
            fail("SEM-B", f"blind-comprehension carrier {carrier} missing")


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
        "**Classes:** geometry (IA §10.3 G-1..G-15) · semantics (IA §10 G/B: rendered vs fixture) · "
        "charts (a1) · visuals (a2) · style (a3) · a11y (IA §10.5 A) · live IA-core · "
        "feature-parity (u5)",
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
    parser.add_argument("--a11y", action="store_true",
                        help="also run the accessibility class (IA §10.5 A: names/roles/hidden/"
                             "keyboard)")
    parser.add_argument("--parity", action="store_true",
                        help="also run the FEATURE-PARITY class (u5): every parity_inventory "
                             "surface present, endpoints wired, workbench lenses non-empty, and "
                             "the R4b per-worker event/action + R4d step-timing checks")
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
        if args.a11y:
            a11y_results, a11y_errors = run_a11y_gate(out, not args.no_screenshot)
            results, errors = results + a11y_results, errors + a11y_errors
        if args.parity:
            parity_results, parity_errors = run_parity_gate(out, not args.no_screenshot)
            results, errors = results + parity_results, errors + parity_errors
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
