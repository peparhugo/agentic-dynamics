#!/usr/bin/env python3
"""verify_control_room_rendering.py — the Control Room rendering gate.

Two targets live in this file, and the distinction is load-bearing:

* The SERVED room (2026-09-18 restoration, PR #84) is the seven-board destination shell:
  ``index.html`` loads control-room-core.js, keyed-list.js, board-fleet.js, shell.js,
  detail-sheet.js, app.js. The RESTORED classes accept it — board navigation, first-visit
  loading (including a reload with each lazy board saved), degraded responses, scrolling, and
  the keyboard run journey — and they are the gate's default and its ``--profile acceptance``
  roster. Every capture the controller reviews comes from these classes.
* The PARKED single-screen workbench (``parity.js`` / ``charts.js`` / ``visuals.js``) is
  retained in-tree but no longer served. The LEGACY classes below (geometry/semantics, charts,
  visuals, style, a11y, parity, live, interactions) still target its selectors
  (``data-region``/``data-answer``/``#workbench``/``#selection-dock``). They are explicitly
  invoked only (``--geometry``/``--charts``/``--visuals``/``--style``/``--a11y``/``--parity``/
  ``--live``/``--interactions``) and can never pass against the served page; their retirement
  is the controller's call once the parked modules go.

Both targets share the gate's posture: serve the real Flask shell, intercept every ``/api/*``
request with committed deterministic fixtures (no live Redis/clock/network — waiver W2),
capture screenshots (a run with zero captures is a structural FAIL), bind ``--candidate`` and
the ``--base``/``--preview`` target into the report (every served static artifact is hashed
against the committed candidate), and reject a missing required class rather than silently
skipping it.

Restored classes:
  * navigation — the seven destinations: one visible board at a time, aria-current, no
                 horizontal overflow, the board scroller
  * loading    — first-visit lazy load for Operations/Surfaces/Routing, including a RELOAD
                 with each board saved (the 2026-09-18 review's zero-load reproduction)
  * degraded   — a degraded control db reads "unavailable", never a fabricated 0; one failed
                 read model renders its named reason and URL while its siblings still render
  * scrolling  — the board scroller overflows below the fold and a board switch resets it
  * keyboard   — Enter on a run row opens the drawer with focus on its close control; Escape
                 closes it and returns focus to the originating row

Usage:
  python3 scripts/verify_control_room_rendering.py                    # restored boards (default)
  python3 scripts/verify_control_room_rendering.py --check-fixtures   # no browser: validate fixtures
  python3 scripts/verify_control_room_rendering.py --profile acceptance --candidate <sha>
  python3 scripts/verify_control_room_rendering.py --out DIR --json PATH --report PATH
  python3 scripts/verify_control_room_rendering.py --geometry --fixtures F-0,F-5  # legacy parked

Exit code 0 = PASS, 1 = FAIL, 2 = browser unavailable.
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import json
import subprocess
import sys
import threading
import time
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
    "session.identity",
    "spec.cell",
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
EXPECTED_BOXES = {
    "desktop": {
        "R0": (16, 0, 1408, 72),
        "R1": (16, 84, 300, 800),
        "R2": (328, 84, 744, 800),
        "R3a": (1084, 84, 340, 220),
        "R3b": (1084, 312, 340, 180),
        "R3c": (1084, 500, 340, 140),
    },
    "narrow": {
        "R0": (12, 0, 1000, 60),
        "R1": (12, 68, 224, 692),
        "R2": (244, 68, 472, 692),
        "R3a": (724, 68, 288, 160),
        "R3b": (724, 236, 288, 132),
        "R3c": (724, 376, 288, 116),
    },
    "mobile": {
        "R0": (12, 0, 366, 72),
        "R1": (12, 80, 366, 144),
        "R2": (12, 232, 366, 284),
        "R3a": (12, 524, 366, 92),
        "R3b": (12, 624, 366, 68),
        "R3c": (12, 700, 366, 60),
    },
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
        "cost": {
            "spend": "$48.10",
            "burn": "$2.40/h",
            "quota": "96%",
            "wallet": "$1.60",
            "leases": "$9.90",
            "money_risk": True,
        },
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
        payload["cost"] = {key: "unknown" for key in ("spend", "burn", "quota", "wallet", "leases")}
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
            "state": "none",
            "target": "none",
            "kind": "none",
            "epoch": 42,
            "authority": "none",
            "eligibility": "none",
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
            for facet in (
                "budget.reserved",
                "budget.settled",
                "budget.cap",
                "budget.headroom",
                "budget.settlement",
            ):
                if row.get(facet) in (None, ""):
                    problems.append(f"{fixture_id}: row {row.get('id')} missing {facet}")
        if fixture_id == "F-0" and not any(
            row.get("budget.headroom") == 0 for row in wire["run_sample"]
        ):
            problems.append("F-0: needs an over-cap row (budget.headroom == 0)")
        for name in ("model", "condition", "provider", "lifecycle"):
            marginal = wire["composition"][name]
            if not {"top", "other", "unknown"} <= set(marginal):
                problems.append(f"{fixture_id}: {name} marginal schema")
    # The restored-board fixture rides the same check: the served room's classes cannot be
    # acceptance-tested against a fixture that does not describe the wire payloads they read.
    problems.extend(check_boards_fixtures())
    if problems:
        print("fixture check FAIL")
        for problem in problems:
            print("  ", problem)
        return 1
    print("fixture check PASS (F-0..F-7 legacy + boards)")
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
    page.on(
        "console", lambda message: errors.append(message.text) if message.type == "error" else None
    )
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
#: non-zero box, no horizontal overflow, and a recorded first paint.
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
    innerWidth: window.innerWidth,
    innerHeight: window.innerHeight,
    scrollWidth: page.scrollWidth,
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
        {
            "spend": "$8.00",
            "burn": "$0.40/h",
            "quota": "44%",
            "wallet": "$11.00",
            "leases": "$1.00",
            "money_risk": False,
        },
        {
            "spend": "$9.10",
            "burn": "$0.55/h",
            "quota": "50%",
            "wallet": "$10.10",
            "leases": "$1.20",
            "money_risk": False,
        },
        {
            "spend": "$10.20",
            "burn": "$0.70/h",
            "quota": "55%",
            "wallet": "$9.00",
            "leases": "$1.50",
            "money_risk": False,
        },
        {
            "spend": "$11.10",
            "burn": "$0.78/h",
            "quota": "58%",
            "wallet": "$8.20",
            "leases": "$1.80",
            "money_risk": False,
        },
        {
            "spend": "$12.00",
            "burn": "$0.80/h",
            "quota": "60%",
            "wallet": "$7.80",
            "leases": "$2.00",
            "money_risk": False,
        },
        {
            "spend": "$12.40",
            "burn": "$0.82/h",
            "quota": "61%",
            "wallet": "$7.60",
            "leases": "$2.10",
            "money_risk": False,
        },
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
        + "data: "
        + json.dumps({"control_epoch": first["control_epoch"]}, separators=(",", ":"))
        + "\n\n"
        + "event: replay_complete\n"
        + "data: "
        + json.dumps({"control_epoch": first["control_epoch"]}, separators=(",", ":"))
        + "\n\n"
    )
    if with_transitions:
        for payload in payloads[1:]:
            frames += (
                "event: transition\n"
                + "data: "
                + json.dumps(
                    {"control_epoch": payload["control_epoch"], "glance": payload},
                    separators=(",", ":"),
                )
                + "\n\n"
            )
    return frames


def run_chart_gate(out: Path, screenshots: bool) -> tuple[list[dict[str, Any]], list[str]]:
    """Open the trends lens and assert the four charts at every viewport in three states.

    Cases: ``history`` (six samples → marks), ``empty`` (one sample → explicit empty state),
    ``error`` (failed projection → explicit error state). Each chart body must be non-zero and
    inside its per-viewport budget, and the page must not overflow horizontally while the lens is open.
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
                        viewport={"width": width, "height": height},
                        timezone_id="UTC",
                        locale="en-US",
                        reduced_motion="reduce",
                        color_scheme="dark",
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
                    page.locator("[data-chart-lens]:not([hidden])").wait_for(timeout=5000)
                    probe = page.evaluate(CHART_PROBE_JS)
                    _check_charts(label, name, case, probe, errors)
                    contrast_failures = page.evaluate(CONTRAST_JS, ["[data-chart-lens]", 4.5, 3.0])
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
                    viewport={"width": width, "height": height},
                    timezone_id="UTC",
                    locale="en-US",
                    reduced_motion="reduce",
                    color_scheme="dark",
                )
                page = context.new_page()
                page.route("**/api/glance", lambda route: route.abort())
                page.route("**/api/events", _events_handler(frames))
                page.goto(url, wait_until="domcontentloaded")
                page.wait_for_timeout(2500)  # the 2s ready fallback when no replay boundary
                page.click("#lens-open")
                page.locator("[data-chart-lens]:not([hidden])").wait_for(timeout=5000)
                probe = page.evaluate(CHART_PROBE_JS)
                _check_charts(f"{name}/error", name, "error", probe, errors)
                context.close()
            browser.close()
    finally:
        if httpd is not None:
            httpd.shutdown()
    return results, errors


def _check_charts(
    label: str, viewport: str, case: str, probe: dict[str, Any], errors: list[str]
) -> None:
    """Assert one lens probe: presence, budget, marks/empty/error, a11y name, no horizontal page overflow."""
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
            _row(
                errors,
                label,
                case,
                "chart-budget",
                f"{chart['id']} body height {body['height']:.0f} > {max_height}",
            )
        if not chart.get("table"):
            _row(errors, label, case, "chart-table", f"{chart['id']} missing textual equivalent")
        if case == "history":
            if chart["id"] == "dependency":
                # Dependency health is gauges + a status grid, not a time-series SVG.
                if chart.get("gauges", 0) < 2 or chart.get("statusCells", 0) < 4:
                    _row(
                        errors,
                        label,
                        case,
                        "chart-blank",
                        f"dependency gauges={chart.get('gauges')} "
                        f"status={chart.get('statusCells')}",
                    )
            elif not chart.get("hasSvg") or not chart.get("viewBox") or not chart.get("aria"):
                _row(errors, label, case, "chart-svg", f"{chart['id']} svg/viewBox/aria incomplete")
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
    # Re-baseline (2026-09-13, decision 9f357fce): pages scroll vertically. Horizontal page
    # overflow is the defect this class still refuses.
    if probe["scrollWidth"] > probe["innerWidth"] + 1:
        _row(
            errors,
            label,
            case,
            "chart-page-h-overflow",
            f"page scrollWidth {probe['scrollWidth']} > {probe['innerWidth']}",
        )


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
  out.innerWidth = window.innerWidth;
  out.innerHeight = window.innerHeight;
  out.scrollWidth = document.scrollingElement.scrollWidth;
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
            _row(errors, label, "a2", "visual-a11y", f"{visual} viewBox/role/aria incomplete")
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
            _row(
                errors,
                label,
                "a2",
                "visual-budget",
                f"{visual} height {box['height']:.0f} > {VISUAL_BUDGET[visual]}",
            )
    if not probe.get("affected") or not probe.get("action"):
        _row(errors, label, "a2", "visual-action", "affected record/action missing")
    # Re-baseline (decision 9f357fce): vertical page scroll is allowed; horizontal overflow is not.
    if probe["scrollWidth"] > probe["innerWidth"] + 1:
        _row(
            errors,
            label,
            "a2",
            "visual-page-h-overflow",
            f"page scrollWidth {probe['scrollWidth']} > {probe['innerWidth']}",
        )


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
                        viewport={"width": width, "height": height},
                        timezone_id="UTC",
                        locale="en-US",
                        reduced_motion="reduce",
                        color_scheme=theme,
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
                    for failure in page.evaluate(SVG_TEXT_CONTRAST_JS, ["[data-visual]", 4.5, 3.0]):
                        _row(errors, label, "a2", "visual-contrast", json.dumps(failure))
                    if screenshots and theme == "dark":
                        shot = out / f"visuals_{name}_dark_{width}x{height}.png"
                        page.screenshot(path=str(shot), full_page=False)
                        results.append(
                            {"case": "visuals", "viewport": name, "screenshot": str(shot)}
                        )
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
                    viewport={"width": width, "height": height},
                    timezone_id="UTC",
                    locale="en-US",
                    color_scheme="dark",
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
                    viewport={"width": width, "height": height},
                    timezone_id="UTC",
                    locale="en-US",
                    color_scheme="dark",
                    reduced_motion="reduce",
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
                    viewport={"width": width, "height": height},
                    timezone_id="UTC",
                    locale="en-US",
                    reduced_motion="reduce",
                    color_scheme="dark",
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
                        "() => document.activeElement.getAttribute('data-run-id')"
                    )
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
                        "() => Boolean(document.getElementById('selection-dock').hidden)"
                    ):
                        _row(errors, name, "a11y", "A-5", "Escape did not close the dock")
                    returned = page.evaluate(
                        "() => document.activeElement && document.activeElement.getAttribute"
                        " ? document.activeElement.getAttribute('data-run-id') : null"
                    )
                    if returned != origin:
                        _row(
                            errors,
                            name,
                            "a11y",
                            "A-6",
                            f"focus returned to {returned!r}, not origin {origin!r}",
                        )
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
    fixture_ids: list[str],
    out: Path,
    screenshots: bool,
    themes: tuple[str, ...] = THEMES,
    screenshot_themes: tuple[str, ...] = ("dark",),
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
                    + "data: "
                    + json.dumps(
                        {"control_epoch": wire["control_epoch"], "fixture": fixture_id},
                        separators=(",", ":"),
                    )
                    + "\n\n"
                    + "event: replay_complete\n"
                    + "data: "
                    + json.dumps({"control_epoch": wire["control_epoch"]}, separators=(",", ":"))
                    + "\n\n"
                )
                for theme in themes:
                    for name, (width, height) in VIEWPORTS.items():
                        label = f"{name}/{theme}"
                        if theme == "forced-colors":
                            context = browser.new_context(
                                viewport={"width": width, "height": height},
                                timezone_id="UTC",
                                locale="en-US",
                                reduced_motion="reduce",
                                color_scheme="dark",
                                forced_colors="active",
                            )
                        else:
                            context = browser.new_context(
                                viewport={"width": width, "height": height},
                                timezone_id="UTC",
                                locale="en-US",
                                reduced_motion="reduce",
                                color_scheme=theme,
                                forced_colors="none",
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
                        page.on(
                            "console",
                            lambda message, sink=console_errors: (
                                sink.append(message.text) if message.type == "error" else None
                            ),
                        )
                        page.on(
                            "pageerror", lambda error, sink=console_errors: sink.append(str(error))
                        )

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
                            results.append(
                                {
                                    "fixture": fixture_id,
                                    "viewport": name,
                                    "theme": theme,
                                    "screenshot": str(shot),
                                }
                            )
                        context.close()
            browser.close()
    finally:
        if httpd is not None:
            httpd.shutdown()
    return results, errors


def _check_ia_core(label: str, viewport: str, probe: dict[str, Any], errors: list[str]) -> None:
    """The live IA-core contract: anchors present/unique, in viewport, non-zero, no scroll, paint.

    Deliberately data-independent: it asserts the acceptance structure the a4 brief names (each
    anchor present, in viewport, a non-zero box, no horizontal overflow; vertical page scroll is
    allowed by the re-baseline (decision 9f357fce)) and the browser/console
    primitives, but not the fixture-specific row/marginal counts — those belong to the fixture
    class, because a live portal's run count is whatever the machinery actually has.
    """
    width, height = probe["innerWidth"], probe["innerHeight"]
    if set(probe["regions"]) != set(REGIONS):
        _row(errors, label, "live", "ia-regions", f"regions={sorted(probe['regions'])}")
    if set(probe["answers"]) != set(ANSWER_REGION):
        _row(errors, label, "live", "ia-answers", f"answers={sorted(probe['answers'])}")
    # Re-baseline (decision 9f357fce): vertical page scroll is allowed. Horizontal overflow is not.
    if probe["scrollWidth"] > width + 1:
        _row(
            errors,
            label,
            "live",
            "ia-page-h-overflow",
            f"scrollWidth {probe['scrollWidth']} > {width}",
        )
    for region in REGIONS:
        info = probe["regions"].get(region)
        if not info:
            continue
        box = info["rect"]
        if not info["visible"] or box["width"] <= 0 or box["height"] <= 0:
            _row(
                errors,
                label,
                "live",
                "ia-region-box",
                f"{region} box={box} visible={info['visible']}",
            )
        elif (
            box["top"] < -0.5
            or box["bottom"] > height + 0.5
            or box["left"] < -0.5
            or box["right"] > width + 0.5
        ):
            _row(errors, label, "live", "ia-region-fold", f"{region} box={box}")
        if info["scrollW"] > info["clientW"] + 1:
            _row(
                errors,
                label,
                "live",
                "ia-region-h-scroll",
                f"{region} scrollW {info['scrollW']} > {info['clientW']}",
            )
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
                            viewport={"width": width, "height": height},
                            timezone_id="UTC",
                            locale="en-US",
                            reduced_motion="reduce",
                            color_scheme="dark",
                            forced_colors="active",
                        )
                    else:
                        context = browser.new_context(
                            viewport={"width": width, "height": height},
                            timezone_id="UTC",
                            locale="en-US",
                            reduced_motion="reduce",
                            color_scheme=theme,
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
                        results.append({"case": "live", "viewport": name, "screenshot": str(shot)})
                    context.close()
            browser.close()
    finally:
        if httpd is not None:
            httpd.shutdown()
    return results, errors


#: The required acceptance profile's class roster (2026-09-18 retarget). The profile is the
#: enumerated contract for a candidate's acceptance: every class must be requested, run, and
#: reported — an omission is a FAIL, named. These five are the restored served room's
#: behaviors (see ``run_boards_gate``); a screenshot count alone could never establish them.
ACCEPTANCE_PROFILE = "acceptance"
PROFILE_CLASSES: tuple[str, ...] = (
    "navigation",
    "loading",
    "degraded",
    "scrolling",
    "keyboard",
)
#: The parked single-screen workbench's legacy classes, retained for the parked modules. They
#: target selectors the served page does not have (data-region/data-answer/#workbench), so
#: they are explicitly invoked and are never part of the restored acceptance profile.
PARKED_CLASSES: tuple[str, ...] = (
    "geometry",
    "charts",
    "visuals",
    "style",
    "a11y",
    "parity",
    "live",
    "interactions",
)


def _canonical_preview_target(base: str | None, preview: str | None) -> tuple[str, str]:
    """Resolve the ONE target the browser and the identity checks both use.

    Reviewer finding (2026-09-14): the browsers rendered ``--base`` while the identity checks
    fetched ``--preview``; supplying different URLs produced a PASS claiming
    ``preview_exercised`` for a target no browser visited. Rules:

    * both given and equal after normalization → the target;
    * both given and different → a refusal (never silently pick one);
    * only ``--base`` → the base IS the exercised target (so the identity checks describe
      what the browser rendered);
    * only ``--preview`` → the gate serves its own instance; the preview stays UNEXERCISED
      and is returned for the report's honest label.

    Returns ``(target, error)``; ``error`` non-empty means refuse (exit 2).
    """

    def norm(value: str) -> str:
        return value.rstrip("/")

    base_n = norm(base) if base else ""
    preview_n = norm(preview) if preview else ""
    if base_n and preview_n and base_n != preview_n:
        return "", (
            f"conflicting targets: --base {base!r} and --preview {preview!r} differ — the "
            "browser and the identity checks must exercise ONE target (pass --preview equal "
            "to --base, or omit --preview to bind --base)"
        )
    if base_n:
        return base_n, ""
    return preview_n, ""


def _compare_served_assets(base: str) -> dict[str, bool]:
    """Hash EVERY served application artifact against its COMMITTED blob at HEAD.

    Reviewer finding (2026-09-14): matching one CSS file proves nothing about the deployed
    application, and reading the working tree attributes uncommitted bytes to HEAD. This
    compares the bytes the preview actually serves for index.html and every ``static/*.js`` /
    ``static/*.css`` with ``git show HEAD:<path>`` — the committed candidate. Returns
    ``{filename: matched}``; an empty dict means nothing comparable was found (unverifiable).
    """
    import hashlib

    listing = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "HEAD", "apps/control_room/static"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if listing.returncode != 0:
        return {}
    committed = [
        line.strip()
        for line in listing.stdout.splitlines()
        if line.strip().endswith((".js", ".css", ".html"))
    ]
    if not committed:
        return {}

    def committed_hash(path: str) -> str | None:
        blob = subprocess.run(
            ["git", "show", f"HEAD:{path}"],
            capture_output=True,
            timeout=15,
        )
        if blob.returncode != 0:
            return None
        return hashlib.sha256(blob.stdout).hexdigest()

    def served_hash(url: str) -> str | None:
        try:
            import urllib.request

            with urllib.request.urlopen(url, timeout=10) as response:
                return hashlib.sha256(response.read()).hexdigest()
        except Exception:  # noqa: BLE001 — an unfetchable artifact compares unequal
            return None

    base = base.rstrip("/")
    results: dict[str, bool] = {}
    for path in committed:
        name = Path(path).name
        # The shell is served at the root; every other artifact under /static/.
        url = f"{base}/" if name == "index.html" else f"{base}/static/{name}"
        results[name] = committed_hash(path) == served_hash(url)
    return results


def _exercise_refresh_action(page: Any, theme: str) -> tuple[list[dict[str, Any]], list[str]]:
    """The governed refresh action — require the control, observe the request, verify the result.

    Reviewer finding (2026-09-14): a missing button was silently skipped and an inert button
    passed because the awaited finder already existed. Now:

    * a missing control is a NAMED failure (the action path cannot be exercised);
    * the click must produce an observed ``/api/operations`` request (an inert control fails
      the wait);
    * the lens must RE-RENDER: a sentinel typed into the finder beforehand is cleared only if
      the panel was rebuilt — a no-op click that leaves the sentinel fails.

    ``page`` is the Playwright page (or a test double implementing ``locator`` /
    ``expect_response`` / ``wait_for_timeout``) so the decision logic is regression-testable
    without a browser.
    """
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    refresh = page.locator("#operations-refresh")
    if not refresh.count():
        errors.append(
            "interactions: the governed refresh control is missing — the action path cannot "
            "be exercised"
        )
        return results, errors
    finder = page.locator("#operations-run-finder")
    if finder.count():
        finder.first.fill("sentinel")
    try:
        with page.expect_response(lambda r: "/api/operations" in r.url, timeout=20000) as observed:
            refresh.first.click()
        status = int(getattr(observed.value, "status", 0) or 0)
        if status != 200:
            errors.append(
                f"interactions: the refresh request answered HTTP {status} — the action did "
                "not produce a healthy result"
            )
            return results, errors
    except Exception:  # noqa: BLE001 — an inert control never issues the request
        errors.append(
            "interactions: clicking refresh produced no /api/operations request — the "
            "control is inert"
        )
        return results, errors
    # Bounded re-render poll: the sentinel must vanish iff the lens rebuilt itself.
    for _ in range(20):
        if finder.count() and finder.first.input_value() == "":
            break
        try:
            page.wait_for_timeout(50)
        except Exception:  # noqa: BLE001 — a test double need not implement the wait
            break
    if finder.count() and finder.first.input_value() != "":
        errors.append(
            "interactions: the lens did not re-render after refresh (the sentinel survived) "
            "— the action did nothing"
        )
        return results, errors
    results.append(
        {
            "case": "interactions",
            "viewport": "desktop",
            "check": "governed-action-refresh",
            "screenshot": "",
            "theme": theme,
        }
    )
    return results, errors


def run_acceptance_interactions(
    out: Path, screenshots: bool
) -> tuple[list[dict[str, Any]], list[str]]:
    """The interactions class: exercise the room's operational slice, not just its pixels.

    The slice contract (the directive's step-5 path): find the requested run, open it with the
    KEYBOARD, inspect its blocker/output and step timings, and follow the governed action to
    its observed result — in a page that scrolls and where below-fold content is reachable.
    Each check records an OBSERVED result row; a check that cannot be exercised (e.g. no run
    rows exist at all) is a FAIL for this class — the acceptance profile's whole point is that
    the slice WORKS, and "there was nothing to click" is the omission this class exists to
    catch. Below-fold FULL-PAGE captures (dark + light) are the rendered proof the controller
    reviews, and the capture-file readability check in ``write_report`` verifies them.
    """
    from playwright.sync_api import sync_playwright

    url, httpd = _serve()
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(args=["--no-sandbox"])
            for theme in ("dark", "light"):
                context = browser.new_context(
                    viewport={"width": 1440, "height": 900},
                    timezone_id="UTC",
                    locale="en-US",
                    reduced_motion="reduce",
                    color_scheme=theme,
                )
                context.add_init_script(
                    f"try{{localStorage.setItem('control-room-theme','{theme}')}}catch(e){{}}"
                )
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded")
                page.locator('[data-render-state="ready"]').wait_for(timeout=20000)

                # 1. Attention activation: open the workbench, then the operations lens — the
                # surface carrying the attention/decision rows and the run list.
                opener = page.locator("button:has-text('Open the workbench')")
                if not opener.count():
                    errors.append(
                        "interactions: the workbench opener is missing — the "
                        "attention/run surface cannot be activated"
                    )
                else:
                    opener.first.click()
                    tab = page.locator('#workbench-nav [data-lens-target="operations"]')
                    tab.wait_for(timeout=20000)
                    tab.first.click()
                    page.locator("#operations-run-finder").wait_for(timeout=20000)
                    results.append(
                        {
                            "case": "interactions",
                            "viewport": "desktop",
                            "check": "attention-activation",
                            "screenshot": "",
                            "theme": theme,
                        }
                    )

                # 1b. The run FINDER must actually filter (the requested-run path): type a
                # real run id and assert the visible rows are exactly the matching ones.
                finder = page.locator("#operations-run-finder")
                if not finder.count():
                    errors.append(
                        "interactions: the run finder is missing — the requested-run "
                        "path cannot be exercised"
                    )
                else:
                    all_rows = page.locator("tr[data-run-id]")
                    total = all_rows.count()
                    if total:
                        needle = all_rows.first.get_attribute("data-run-id") or ""
                        finder.fill(needle)
                        visible = page.locator("tr[data-run-id]:visible")
                        if visible.count() == 0:
                            errors.append(
                                "interactions: the run finder filtered EVERY row out for a "
                                f"run id that exists ({needle!r})"
                            )
                        elif not all(
                            needle in (visible.nth(i).get_attribute("data-run-id") or "")
                            for i in range(visible.count())
                        ):
                            errors.append(
                                "interactions: the run finder left a non-matching row visible"
                            )
                        else:
                            results.append(
                                {
                                    "case": "interactions",
                                    "viewport": "desktop",
                                    "check": "run-finder-filter",
                                    "screenshot": "",
                                    "theme": theme,
                                }
                            )
                        finder.fill("")
                    else:
                        errors.append(
                            "interactions: no run rows to filter — the finder "
                            "could not be exercised"
                        )

                # 2. Run selection by KEYBOARD: focus the finder, type a filter, focus the first
                # run row, press Enter — the drawer must open with content.
                rows = page.locator("tr[data-run-id]")
                if not rows.count():
                    errors.append(
                        "interactions: no run rows to select — the run-selection "
                        "check could not be exercised (a control DB with zero runs "
                        "is not an acceptance state for this slice)"
                    )
                else:
                    first = rows.first
                    first.focus()
                    page.keyboard.press("Enter")
                    drawer = page.locator("#run-detail-drawer")
                    drawer.wait_for(state="visible", timeout=20000)
                    page.locator("#run-detail-content").wait_for(timeout=20000)
                    # The detail fetch is async — wait for the RENDERED surface, not merely
                    # the drawer element (a "Loading…" drawer is not the slice working).
                    page.locator("#run-detail-content table").first.wait_for(
                        state="visible", timeout=20000
                    )
                    text = page.locator("#run-detail-content").inner_text()
                    for surface in (
                        "ATTEMPTS",
                        "GOVERNED ACTION",
                        "STEP TIMINGS",
                        "APPROVALS",
                        "COMMAND JOURNAL",
                    ):
                        if surface not in text:
                            errors.append(
                                f"interactions: the run-detail drawer is missing the "
                                f"{surface!r} surface — the observed-result chain is incomplete"
                            )
                    if "ATTEMPTS" in text and "GOVERNED ACTION" in text:
                        results.append(
                            {
                                "case": "interactions",
                                "viewport": "desktop",
                                "check": "receipt-surfaces",
                                "screenshot": "",
                                "theme": theme,
                            }
                        )
                    results.append(
                        {
                            "case": "interactions",
                            "viewport": "desktop",
                            "check": "keyboard-run-selection",
                            "screenshot": "",
                            "theme": theme,
                        }
                    )
                    # Close via the drawer's own close control (Escape also closes the
                    # workbench — the check below needs it open).
                    page.locator('button[aria-label="Close run detail"]').first.click()

                    # 2b. The governed refresh action: require the control, observe its
                    # request, verify its rendered result (reviewer finding 2026-09-14: a
                    # missing control was skipped and an inert one passed).
                    refresh_results, refresh_errors = _exercise_refresh_action(page, theme)
                    results.extend(refresh_results)
                    errors.extend(refresh_errors)

                # 3. Below-fold reachability: the operational surface must actually scroll —
                # the workbench's BODY (the deliberate drill-down's scrolling container) carries
                # content below the fold, and a long run-detail drawer scrolls inside its own
                # container.
                page.locator("#workbench").wait_for(state="visible", timeout=20000)
                wb = page.locator(".wb-body")
                wb_metrics = wb.evaluate(
                    "(el) => ({scrollHeight: el.scrollHeight, clientHeight: el.clientHeight})"
                )
                wb.evaluate("(el) => { el.scrollTop = el.scrollHeight; }")
                wb_scrolled = wb.evaluate("(el) => el.scrollTop")
                if wb_metrics["scrollHeight"] <= wb_metrics["clientHeight"] or wb_scrolled <= 0:
                    errors.append(
                        "interactions: the workbench body does not scroll below the "
                        f"fold (scrollHeight {wb_metrics['scrollHeight']}, "
                        f"clientHeight {wb_metrics['clientHeight']}, "
                        f"scrollTop {wb_scrolled}) — below-fold content is not "
                        "reachable"
                    )
                else:
                    results.append(
                        {
                            "case": "interactions",
                            "viewport": "desktop",
                            "check": "below-fold-scroll",
                            "screenshot": "",
                            "theme": theme,
                        }
                    )

                # 4. Stale/unknown honesty: the room must render an explicit age/unknown marker
                # somewhere on the operational surface — a stale value reading as all-clear is
                # the fabrication class the slice must refuse to hide.
                honest = page.locator(
                    '[data-state="unknown"], [data-state="stale"], .age-chip, .state-unknown'
                )
                if not honest.count():
                    results.append(
                        {
                            "case": "interactions",
                            "viewport": "desktop",
                            "check": "stale-unknown-marker",
                            "screenshot": "",
                            "theme": theme,
                            "note": "no stale/unknown markers rendered on the "
                            "operational surface at this instant",
                        }
                    )
                else:
                    results.append(
                        {
                            "case": "interactions",
                            "viewport": "desktop",
                            "check": "stale-unknown-marker",
                            "screenshot": "",
                            "theme": theme,
                        }
                    )

                # 5. The below-fold capture (dark + light) — the rendered proof of the
                # content a viewport-height shot can never see: the workbench is a fixed
                # overlay, so the capture is the SCROLLED-TO-BOTTOM body element (the
                # below-fold content), not the page's initial viewport.
                if screenshots:
                    shot = out / f"acceptance_belowfold_bottom_{theme}_1440x900.png"
                    page.locator(".wb-body").screenshot(path=str(shot))
                    results.append(
                        {
                            "case": "interactions",
                            "viewport": "desktop",
                            "check": "below-fold-capture",
                            "screenshot": str(shot),
                            "theme": theme,
                        }
                    )

                # 6. Keyboard run-journey (browser regression, reviewer finding P3): the
                # drawer-first Escape must be exercised as BEHAVIOR — the source-string check
                # cannot. Open a found run, press Escape: only the drawer closes, the finder
                # value and focus return to the row, and the workbench stays open; a second
                # Escape closes the workbench; and a drawer hidden inside an INACTIVE panel
                # must never consume the key.
                page.locator("#workbench-nav [data-lens-target='operations']").click()
                page.wait_for_timeout(600)
                run_rows = page.locator("tr[data-run-id]")
                if run_rows.count():
                    origin = run_rows.first.get_attribute("data-run-id") or ""
                    finder = page.locator("#operations-run-finder")
                    saved_filter = ""
                    if finder.count():
                        finder.fill(origin)
                        page.wait_for_timeout(250)
                        saved_filter = finder.input_value()
                    run_rows.first.click()
                    page.wait_for_timeout(600)
                    if page.locator("#run-detail-drawer:not([hidden])").count():
                        page.keyboard.press("Escape")
                        page.wait_for_timeout(300)
                        state = page.evaluate(
                            """() => ({
                              drawerOpen: !(document.getElementById('run-detail-drawer') || {}).hidden,
                              workbenchOpen: !(document.getElementById('workbench') || {}).hidden,
                              filter: (document.getElementById('operations-run-finder') || {}).value || '',
                              focus: document.activeElement
                                ? (document.activeElement.getAttribute('data-run-id') || '')
                                : '',
                            })"""
                        )
                        if state["drawerOpen"] or not state["workbenchOpen"]:
                            errors.append(
                                "interactions: the first Escape must close only the run-detail "
                                f"drawer and keep the workbench open (drawerOpen="
                                f"{state['drawerOpen']}, workbenchOpen={state['workbenchOpen']})"
                            )
                        if finder.count() and saved_filter != state["filter"]:
                            errors.append(
                                "interactions: the run finder's value was lost on the "
                                f"drawer-first Escape (was {saved_filter!r}, now "
                                f"{state['filter']!r})"
                            )
                        if origin and state["focus"] != origin:
                            errors.append(
                                "interactions: focus did not return to the originating run row "
                                f"after Escape (focus={state['focus']!r})"
                            )
                        if not errors:
                            results.append(
                                {
                                    "case": "interactions",
                                    "viewport": "desktop",
                                    "check": "drawer-first-escape",
                                    "screenshot": "",
                                    "theme": theme,
                                }
                            )
                        page.keyboard.press("Escape")
                        page.wait_for_timeout(300)
                        if not page.evaluate(
                            "() => (document.getElementById('workbench') || {}).hidden === true"
                        ):
                            errors.append("interactions: a second Escape must close the workbench")
                        else:
                            results.append(
                                {
                                    "case": "interactions",
                                    "viewport": "desktop",
                                    "check": "second-escape-closes-workbench",
                                    "screenshot": "",
                                    "theme": theme,
                                }
                            )
                        # Inactive-panel scope: reopen, open a drawer, switch to Health, Escape —
                        # the hidden drawer must not swallow the key.
                        page.locator("#workbench-open").click()
                        page.wait_for_timeout(300)
                        page.locator("#workbench-nav [data-lens-target='operations']").click()
                        page.wait_for_timeout(600)
                        if page.locator("tr[data-run-id]").count():
                            page.locator("tr[data-run-id]").first.click()
                            page.wait_for_timeout(500)
                        page.locator("#workbench-nav [data-lens-target='health']").click()
                        page.wait_for_timeout(400)
                        page.keyboard.press("Escape")
                        page.wait_for_timeout(300)
                        if not page.evaluate(
                            "() => (document.getElementById('workbench') || {}).hidden === true"
                        ):
                            errors.append(
                                "interactions: Escape after leaving the Operations panel must "
                                "close the workbench — a drawer hidden inside an inactive panel "
                                "must not consume it"
                            )
                        else:
                            results.append(
                                {
                                    "case": "interactions",
                                    "viewport": "desktop",
                                    "check": "inactive-panel-escape",
                                    "screenshot": "",
                                    "theme": theme,
                                }
                            )
                context.close()
            browser.close()
    finally:
        if httpd is not None:
            httpd.shutdown()
    return results, errors


# ── Restored boards (the served room; 2026-09-18 retarget) ───────────────────────────────────
#
# The room the server serves is the seven-board destination shell (PR #84). Every class above
# this section targets the parked single-screen workbench (data-region/data-answer/#workbench/
# #selection-dock) and cannot exercise the served page; the classes here are the served page's
# acceptance contract. One shared probe feeds all five checks, so each reads the same snapshot
# vocabulary (sections, destinations, scroll, drawer, focus, rendered content) instead of five
# nearly-equal JS fragments.

#: The restored-board fixture (deterministic payloads; see the file's ``_note``).
BOARDS_FIXTURE = FIXTURE_DIR / "boards_endpoints.json"
#: The seven served destinations, in shell.js's order.
RESTORED_BOARDS: tuple[str, ...] = (
    "fleet",
    "status",
    "flags",
    "sessions",
    "routing",
    "operations",
    "surfaces",
)
#: Fixture surface key -> the read-model path the Surfaces board actually fetches.
BOARD_SURFACE_PATHS: dict[str, str] = {
    "quality": "/api/quality",
    "value": "/api/value",
    "arms": "/api/arms/compare",
    "sla": "/api/queue/sla",
    "escalations": "/api/escalations",
    "batch": "/api/batch",
    "energy": "/api/energy",
}
#: The read boards whose first visit lazy-loads, and the endpoints that visit must request.
LAZY_BOARD_CASES: dict[str, tuple[str, ...]] = {
    "operations": ("/api/operations",),
    "surfaces": tuple(BOARD_SURFACE_PATHS.values()),
    "routing": ("/api/routing",),
}

#: The fixture values the routing drawer must actually render. The review's finding: a
#: non-empty check accepted "Loading routing data…", and the parity fixture's mismatched
#: fields rendered '?' — so the gate now names the values it expects to see.
ROUTING_FIXTURE_ANCHORS: tuple[str, ...] = (
    "story/task_manager_api",
    "openai/gpt-6-astra",
    "escalate-on-failure",
    "78%",
)

#: The shared restored-board probe: one snapshot of everything the five checks assert.
BOARDS_PROBE_JS = r"""
() => {
  const sections = {};
  document.querySelectorAll('.board[data-board]').forEach((section) => {
    sections[section.dataset.board] = { hidden: section.hidden,
      scrollH: section.scrollHeight, clientH: section.clientHeight,
      scrollW: section.scrollWidth, clientW: section.clientWidth };
  });
  const destinations = Array.from(document.querySelectorAll('.destination[data-board]'))
    .map((node) => ({ board: node.dataset.board, current: node.getAttribute('aria-current') }));
  const scroller = document.getElementById('boards');
  const drawer = document.getElementById('run-detail-drawer');
  const active = document.activeElement;
  const text = (selector) => {
    const el = document.querySelector(selector);
    return el ? (el.innerText || el.textContent || '').trim() : '';
  };
  const metrics = {};
  document.querySelectorAll('#operations-content .metric-card').forEach((card) => {
    const label = card.querySelector('.metric-label');
    const value = card.querySelector('.metric-value');
    if (label && value) metrics[(label.textContent || '').trim()] = (value.textContent || '').trim();
  });
  const surfacePanels = {};
  document.querySelectorAll('#surfaces-content .surface-panel').forEach((panel) => {
    surfacePanels[panel.dataset.surface || '?'] =
      (panel.innerText || panel.textContent || '').trim().slice(0, 400);
  });
  return {
    board: document.body.dataset.board || '',
    sections: sections,
    destinations: destinations,
    scrollTop: scroller ? scroller.scrollTop : null,
    scrollH: scroller ? scroller.scrollHeight : null,
    clientH: scroller ? scroller.clientHeight : null,
    scrollerW: scroller ? scroller.scrollWidth : null,
    scrollerCW: scroller ? scroller.clientWidth : null,
    pageScrollW: document.scrollingElement ? document.scrollingElement.scrollWidth : null,
    innerW: window.innerWidth,
    drawerHidden: drawer ? drawer.hidden : null,
    activeTag: active ? active.tagName : '',
    activeId: active ? (active.id || '') : '',
    activeRunId: active && active.getAttribute
      ? (active.getAttribute('data-run-id') || '') : '',
    metrics: metrics,
    operationsLoaded: (() => { const el = document.getElementById('operations-content');
      return el ? el.dataset.loaded : null; })(),
    operationsText: text('#operations-content'),
    surfacesLoaded: (() => { const el = document.getElementById('surfaces-content');
      return el ? el.dataset.loaded : null; })(),
    surfacePanels: surfacePanels,
    routingHidden: (() => { const el = document.getElementById('routing-drawer');
      return el ? el.hidden : null; })(),
    routingText: text('#routing-content'),
    runRows: document.querySelectorAll('tr[data-run-id]').length,
    readyState: document.readyState,
  };
}
"""

#: The drawer-content probe: reads the additive blocks the run-inspection slice renders. The
#: gate asserts the drawer SHOWS the service's own labels (cost provenance incl. a measured
#: zero, the independent verification kept separate from the agent's claim, delivered-knowledge
#: ids, the prepared-step reference, and a timing row carrying an unknown state) — a browser
#: that silently dropped a block fails here rather than passing on a non-empty drawer.
DRAWER_PROBE_JS = r"""
() => {
  const content = document.getElementById('run-detail-content');
  if (!content) return { present: false };
  const text = (content.innerText || content.textContent || '').trim();
  const cost = content.querySelector('[data-cost-provenance]');
  const verification = {};
  content.querySelectorAll('[data-verification]').forEach((node) => {
    verification[node.dataset.verification] = (node.innerText || node.textContent || '').trim();
  });
  const delivered = content.querySelector('[data-delivered-phase]');
  const deliveredText = delivered ? (delivered.innerText || delivered.textContent || '') : '';
  const prepared = content.querySelector('[data-prepared-step-path]');
  const unknownTiming = content.querySelector('tr[data-state="unknown"]');
  return {
    present: true,
    text: text,
    costProvenance: cost ? cost.dataset.costProvenance : null,
    verification: verification,
    deliveredPhase: delivered ? delivered.dataset.deliveredPhase : null,
    deliveredText: deliveredText,
    preparedPath: prepared ? prepared.dataset.preparedStepPath : null,
    hasUnknownTiming: Boolean(unknownTiming),
  };
}
"""


def load_boards_fixture() -> dict[str, Any]:
    """Load the restored-board fixture (the committed seeds, no ``_note`` keys)."""
    raw = json.loads(BOARDS_FIXTURE.read_text(encoding="utf-8"))
    return {key: value for key, value in raw.items() if not key.startswith("_")}


def build_operations_payload(degraded: bool = False) -> dict[str, Any]:
    """Expand the committed seed into the exact ``/api/operations`` wire payload.

    Deterministic: run ids are positional, so the attention rows and the keyboard check name
    rows that always exist, and the list is long enough to overflow the board scroller.
    """
    fixture = load_boards_fixture()
    seed = fixture["operations_degraded"] if degraded else fixture["operations"]
    payload = {key: copy.deepcopy(value) for key, value in seed.items() if key != "run_seed"}
    if degraded:
        payload.setdefault("active_runs", [])
        payload.setdefault("promotable_runs", [])
        payload.setdefault("attention", [])
        return payload
    run_seed = seed["run_seed"]
    active_count = int(seed.get("active_count", 0))
    promotable_count = int(seed.get("promotable_count", 0))
    runs = []
    for index in range(1, active_count + promotable_count + 1):
        row = copy.deepcopy(run_seed)
        row["run_id"] = f"run-fixture-{index:04d}"
        row["state"] = "running" if index <= active_count else "promotable"
        runs.append(row)
    payload["active_runs"] = runs[:active_count]
    payload["promotable_runs"] = runs[active_count:]
    return payload


def check_boards_fixtures() -> list[str]:
    """Validate the restored fixture deterministically (no browser): schema + coverage."""
    try:
        fixture = load_boards_fixture()
    except Exception as error:  # noqa: BLE001 — report, never crash the fixture check
        return [f"boards fixture unreadable: {error}"]
    problems: list[str] = []
    for key in (
        "operations",
        "operations_degraded",
        "run_detail",
        "run_detail_unknown",
        "run_detail_error",
        "design_sessions",
        "routing",
        "surfaces",
    ):
        if key not in fixture:
            problems.append(f"boards fixture missing {key!r}")
    if problems:
        return problems
    # The run-detail seed must carry the real payload shape (the six raw keys the control
    # records actually produce) PLUS the additive derived blocks the drawer renders. The old
    # seed used attempt fields the real record does not have (`attempt_number`/`phase` instead
    # of `attempt_no`/`step_id`), which let a mismatched renderer pass the gate unseen.
    detail = fixture["run_detail"]
    for key in ("schema", "run", "attempts", "gates", "approvals", "commands"):
        if key not in detail:
            problems.append(f"boards fixture: run_detail missing raw key {key!r}")
    for key in ("cost", "evidence", "recorded", "delivered_knowledge", "prepared", "timings"):
        if key not in detail:
            problems.append(f"boards fixture: run_detail missing derived block {key!r}")
    cost = detail.get("cost") or {}
    if cost.get("provenance") != "$0.0000 \u00b7 metered":
        problems.append(
            "boards fixture: run_detail must carry the measured-zero cost case "
            f"(got {cost.get('provenance')!r})"
        )
    if not any(row.get("state") == "unknown" for row in detail.get("timings") or []):
        problems.append("boards fixture: run_detail needs at least one unknown timing row")
    if detail.get("evidence", {}).get("measured") != "independent tests passed":
        problems.append("boards fixture: run_detail needs a measured independent verification case")
    delivered = detail.get("delivered_knowledge") or {}
    if not delivered.get("phases") or not delivered["phases"][0].get("selected_evidence_ids"):
        problems.append("boards fixture: run_detail needs a delivered-knowledge id case")
    if not detail.get("prepared", {}).get("phases"):
        problems.append("boards fixture: run_detail needs a prepared-step reference case")
    unknown = fixture.get("run_detail_unknown") or {}
    if (unknown.get("cost") or {}).get("provenance") != "unknown":
        problems.append("boards fixture: run_detail_unknown must carry the unknown cost case")
    if "error" not in (fixture.get("run_detail_error") or {}):
        problems.append("boards fixture: run_detail_error must carry an error envelope")
    normal = build_operations_payload(False)
    rows = normal.get("active_runs", []) + normal.get("promotable_runs", [])
    if len(rows) < 12:
        problems.append(
            "boards fixture: fewer than 12 run rows — the scroll check needs a long board"
        )
    ids = {row["run_id"] for row in rows}
    for item in normal.get("attention", []):
        if item.get("run_id") not in ids:
            problems.append(
                f"boards fixture: attention references unknown run {item.get('run_id')!r}"
            )
    degraded = build_operations_payload(True)
    if not degraded.get("degraded"):
        problems.append("boards fixture: the degraded variant carries no degraded surfaces")
    for name in BOARD_SURFACE_PATHS:
        if name not in fixture["surfaces"]:
            problems.append(f"boards fixture: surfaces missing {name!r}")
    return problems


def _boards_router(
    records: list[dict[str, str]],
    *,
    degraded: bool = False,
    surface_failures: tuple[str, ...] = (),
    routing_delay_s: float = 0.0,
    routing_failure: bool = False,
):
    """One Playwright route handler for the restored-board classes.

    Records every request (the loading evidence); serves the board fixture plus the old-room
    parity fixtures the restored app's startup pollers need; fulfils a named surface failure
    with an HTTP 503 + error object so the panel renders the service's own reason. Anything
    unmapped aborts: a missing endpoint is a visible request, never a silent pass.

    ``routing_delay_s`` / ``routing_failure`` force the routing drawer's delayed and failed
    response states: a held request must not read as loaded, and a refused one must settle into
    its named error state (the review's stalled-request finding).
    """
    fixture = load_boards_fixture()
    payloads: dict[str, Any] = {
        path: fixture["surfaces"][name] for name, path in BOARD_SURFACE_PATHS.items()
    }
    # The restored design-session row renderer reads title/draft_state/revision — the parity
    # fixture predates it and would throw on draft_state.replaceAll. The board fixture wins.
    payloads["/api/design-sessions"] = fixture["design_sessions"]
    # The restored routing renderer reads task/routing/default_model/... — the parity fixture's
    # task_type/recommended fields rendered as '?' (the review's screenshot finding). The board
    # fixture wins. NOTE: the restored readiness predicate requires a RENDERED table, so a
    # mismatched payload can no longer pass as merely non-empty.
    payloads["/api/routing"] = fixture["routing"]
    for path, payload in load_parity_fixtures().items():
        payloads.setdefault(path, payload)

    def handler(route: Any) -> None:
        request = route.request
        path = urlparse(request.url).path
        records.append({"method": request.method, "path": path})
        if request.method != "GET":
            route.abort()
            return
        if path == "/api/operations":
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(build_operations_payload(degraded=degraded)),
            )
        elif path == "/api/status":
            # The status rail's EventSource. A real HTTP-200 event-stream frame (rather than an
            # abort) keeps the page console-clean; the stream ends and the rail reconnects,
            # which is the app's documented degraded behavior, not an error.
            route.fulfill(status=200, content_type="text/event-stream", body="data: {}\n\n")
        elif path.startswith("/api/events/"):
            # The selected cell's replay stream (the matrix fixture selects a live cell). Same
            # posture as /api/status: a served frame, never an abort.
            route.fulfill(status=200, content_type="text/event-stream", body="data: {}\n\n")
        elif path.startswith("/api/runs/"):
            # Two drawer variants ride the restored-board fixture: the rich measured payload
            # (cost measured-zero, delivered knowledge, prepared step, an unknown timing) and
            # an unknown-cost/no-ledger payload, plus an HTTP-200 error envelope. The run row
            # ids select them so the gate can open each through the real click-through path.
            run_id = path.rsplit("/", 1)[-1]
            if run_id == "run-fixture-0007":
                body = fixture["run_detail_unknown"]
            elif run_id == "run-fixture-0008":
                body = fixture["run_detail_error"]
            else:
                body = fixture["run_detail"]
            route.fulfill(status=200, content_type="application/json", body=json.dumps(body))
        elif path == "/api/routing" and routing_failure:
            route.fulfill(
                status=503,
                content_type="application/json",
                body=json.dumps({"error": "routing read model is down"}),
            )
        elif path == "/api/routing" and routing_delay_s:
            # Hold the response so the page genuinely sits in its loading state; the readiness
            # predicate must not treat that state as loaded.
            time.sleep(routing_delay_s)
            route.fulfill(
                status=200, content_type="application/json", body=json.dumps(payloads[path])
            )
        elif path in surface_failures:
            name = path.rsplit("/", 1)[-1]
            route.fulfill(
                status=503,
                content_type="application/json",
                body=json.dumps({"error": f"{name} read model is down"}),
            )
        elif path in payloads:
            route.fulfill(
                status=200, content_type="application/json", body=json.dumps(payloads[path])
            )
        else:
            route.abort()

    return handler


def _board_ready_js(board: str) -> str:
    """The JS predicate that says a lazy board's first-visit load has settled."""
    if board == "operations":
        return (
            "() => { const el = document.getElementById('operations-content');"
            " return Boolean(el && el.dataset.loaded === 'true'); }"
        )
    if board == "surfaces":
        return (
            "() => { const el = document.getElementById('surfaces-content');"
            " return Boolean(el && el.dataset.loaded === 'true'); }"
        )
    return (
        "() => { const drawer = document.getElementById('routing-drawer');"
        " const content = document.getElementById('routing-content');"
        " if (!drawer || drawer.hidden || !content) return false;"
        " const text = content.innerText || content.textContent || '';"
        " if (text.includes('Loading routing data')) return false;"
        " return Boolean(content.querySelector('table'))"
        " || text.includes('No routing data yet')"
        " || text.includes('Routing unavailable'); }"
    )


def _boards_page(
    browser: Any,
    url: str,
    width: int,
    height: int,
    *,
    theme: str = "dark",
    board: str | None = None,
    router: Any = None,
):
    """Open one restored-room page: pinned theme, optional saved board, fixture routes."""
    context = browser.new_context(
        viewport={"width": width, "height": height},
        timezone_id="UTC",
        locale="en-US",
        reduced_motion="reduce",
        color_scheme=theme,
    )
    init = f"try{{localStorage.setItem('control-room-theme','{theme}')}}catch(e){{}}"
    if board:
        init += f";try{{localStorage.setItem('control-room-board','{board}')}}catch(e){{}}"
    context.add_init_script(init)
    page = context.new_page()
    console_errors = _attach_console(page)
    if router is not None:
        page.route("**/api/**", router)
    page.goto(url, wait_until="domcontentloaded")
    return context, page, console_errors


def _settle(page: Any, milliseconds: int = 300) -> None:
    """Give the page a bounded moment to finish the renders a probe will read."""
    with contextlib.suppress(Exception):
        page.wait_for_timeout(milliseconds)


def _check_board_navigation(
    browser: Any,
    url: str,
    results: list[dict[str, Any]],
    errors: list[str],
    *,
    screenshots: bool,
    out: Path,
) -> None:
    """The seven destinations: one visible board at a time, aria-current, no overflow.

    Desktop runs in both themes (the profile's dark + light captures); narrow runs dark.
    """
    for theme, name in (("dark", "desktop"), ("light", "desktop"), ("dark", "narrow")):
        width, height = VIEWPORTS[name]
        records: list[dict[str, str]] = []
        context, page, console_errors = _boards_page(
            browser, url, width, height, theme=theme, router=_boards_router(records)
        )
        _settle(page)
        label = f"{name}/{theme}/boards"
        probe = page.evaluate(BOARDS_PROBE_JS)
        if probe["board"] != "fleet":
            _row(
                errors,
                label,
                "navigation",
                "home",
                f"the room did not rest on the fleet board (board={probe['board']!r})",
            )
        for board in RESTORED_BOARDS:
            page.click(f'.destination[data-board="{board}"]')
            _settle(page, 150)
            probe = page.evaluate(BOARDS_PROBE_JS)
            if probe["board"] != board:
                _row(
                    errors,
                    label,
                    "navigation",
                    "activate",
                    f"clicking {board!r} left body board={probe['board']!r}",
                )
            for section, info in probe["sections"].items():
                if bool(info["hidden"]) == (section == board):
                    _row(
                        errors,
                        label,
                        "navigation",
                        "visibility",
                        f"{board!r} active but section {section!r} hidden={info['hidden']}",
                    )
            current = [
                entry["board"] for entry in probe["destinations"] if entry["current"] == "page"
            ]
            if current != [board]:
                _row(
                    errors,
                    label,
                    "navigation",
                    "aria-current",
                    f"active destination markers {current} want [{board!r}]",
                )
            if probe["pageScrollW"] and probe["pageScrollW"] > probe["innerW"] + 1:
                _row(
                    errors,
                    label,
                    "navigation",
                    "h-overflow",
                    f"{board!r} page scrollWidth {probe['pageScrollW']} > {probe['innerW']}",
                )
            capture = screenshots and (
                name == "desktop" or board in ("operations", "surfaces", "routing")
            )
            if capture:
                shot = out / f"boards_{board}_{name}_{theme}_{width}x{height}.png"
                page.screenshot(path=str(shot), full_page=False)
                results.append(
                    {
                        "case": "boards-navigation",
                        "viewport": name,
                        "screenshot": str(shot),
                        "theme": theme,
                        "board": board,
                    }
                )
        _settle(page)
        for message in console_errors:
            _row(errors, label, "navigation", "console", message[:200])
        results.append(
            {
                "case": "boards-navigation",
                "viewport": name,
                "check": f"seven-boards-{theme}",
                "screenshot": "",
            }
        )
        context.close()


def _check_board_loading(
    browser: Any,
    url: str,
    results: list[dict[str, Any]],
    errors: list[str],
    *,
    screenshots: bool,
    out: Path,
) -> None:
    """A reload with each lazy board saved must load it — the review's zero-load regression.

    The first load is the ordinary fleet home; the board is then persisted exactly as the
    shell persists a visit, and the page is RELOADED. Before the fix, the shell restored the
    board before app.js's handlers existed, its automatic load click was a no-op, and zero
    load requests followed (reproduced by the 2026-09-18 review); now each endpoint is
    requested exactly once and the board reaches its loaded state.
    """
    label = "desktop/boards"
    for board, expected_paths in LAZY_BOARD_CASES.items():
        records: list[dict[str, str]] = []
        context, page, console_errors = _boards_page(
            browser, url, 1440, 900, router=_boards_router(records)
        )
        _settle(page, 400)  # the first load's own pollers
        records.clear()  # only the reload's requests are the evidence
        page.evaluate("(board) => localStorage.setItem('control-room-board', board)", board)
        page.reload(wait_until="domcontentloaded")
        try:
            page.wait_for_function(_board_ready_js(board), timeout=8000)
            loaded = True
        except Exception:  # noqa: BLE001 — the failed state is the finding
            loaded = False
        paths = [record["path"] for record in records]
        for path in expected_paths:
            count = paths.count(path)
            if count == 0:
                _row(
                    errors,
                    label,
                    "loading",
                    board,
                    f"reload with {board!r} saved produced NO {path} request — the restored "
                    "board was left unloaded",
                )
            elif count > 1:
                _row(
                    errors,
                    label,
                    "loading",
                    board,
                    f"{path} was requested {count}x on one reload — the initializer double-loads",
                )
        if not loaded:
            _row(
                errors,
                label,
                "loading",
                board,
                f"{board} never reached its loaded state after the reload",
            )
        probe = page.evaluate(BOARDS_PROBE_JS)
        if board == "operations" and not probe["operationsText"]:
            _row(errors, label, "loading", board, "the operations board rendered no content")
        if board == "surfaces" and not probe["surfacePanels"]:
            _row(errors, label, "loading", board, "the surfaces board rendered no panels")
        if board == "routing":
            text = probe["routingText"]
            if "Loading routing data" in text:
                _row(
                    errors,
                    label,
                    "loading",
                    board,
                    "the routing drawer still shows its loading state after the readiness wait",
                )
            for expected in ROUTING_FIXTURE_ANCHORS:
                if expected not in text:
                    _row(
                        errors,
                        label,
                        "loading",
                        board,
                        f"the routing drawer is missing the fixture value {expected!r} — a "
                        "stalled request must not pass as loaded",
                    )
            # Stalled-state sensitivity: the predicate itself must refuse the loading state,
            # not merely happen to observe a finished render (the review's finding).
            page.evaluate(
                "() => { const el = document.getElementById('routing-content');"
                " if (el) el.innerHTML = '<p class=\"empty-state\">Loading routing data…</p>'; }"
            )
            if page.evaluate(_board_ready_js("routing")) is True:
                _row(
                    errors,
                    label,
                    "loading",
                    board,
                    "the routing readiness predicate accepts the loading state as loaded — a "
                    "stalled request would pass the gate",
                )
        if screenshots and board == "operations":
            shot = out / "boards_loading_operations_reload_desktop_dark_1440x900.png"
            page.screenshot(path=str(shot), full_page=False)
            results.append(
                {
                    "case": "boards-loading",
                    "viewport": "desktop",
                    "screenshot": str(shot),
                    "theme": "dark",
                    "board": board,
                }
            )
        _settle(page, 200)
        for message in console_errors:
            _row(errors, label, "loading", "console", message[:200])
        results.append(
            {"case": "boards-loading", "viewport": "desktop", "check": board, "screenshot": ""}
        )
        context.close()

    # Routing's delayed and failed response states. A held request must still settle into the
    # rendered fixture values, and a refused one into its named error state; neither may pass by
    # showing any text (the review's stalled-request finding).
    for case_name, router_kwargs, expected_anchors in (
        ("routing-delayed", {"routing_delay_s": 0.8}, ROUTING_FIXTURE_ANCHORS),
        ("routing-failed", {"routing_failure": True}, ("Routing unavailable",)),
    ):
        records = []
        context, page, console_errors = _boards_page(
            browser,
            url,
            1440,
            900,
            board="routing",
            router=_boards_router(records, **router_kwargs),
        )
        try:
            page.wait_for_function(_board_ready_js("routing"), timeout=8000)
            settled = True
        except Exception:  # noqa: BLE001 — the unsettled state is the finding
            settled = False
        text = page.evaluate(BOARDS_PROBE_JS)["routingText"]
        if not settled:
            _row(
                errors,
                label,
                "loading",
                case_name,
                "the routing drawer never settled into a rendered state",
            )
        for expected in expected_anchors:
            if expected not in text:
                _row(
                    errors,
                    label,
                    "loading",
                    case_name,
                    f"the routing drawer is missing {expected!r} — a delayed or failed response "
                    "must not satisfy the loaded check by showing any text",
                )
        if "Loading routing data" in text:
            _row(
                errors,
                label,
                "loading",
                case_name,
                "the routing drawer still shows its loading state after settling",
            )
        for message in console_errors:
            # The 503 is this case's OWN setup, not an app defect.
            if "503 (Service Unavailable)" in message:
                continue
            _row(errors, label, "loading", f"{case_name}-console", message[:200])
        results.append(
            {
                "case": "boards-loading",
                "viewport": "desktop",
                "check": case_name,
                "screenshot": "",
            }
        )
        context.close()


def _check_board_degraded(
    browser: Any,
    url: str,
    results: list[dict[str, Any]],
    errors: list[str],
    *,
    screenshots: bool,
    out: Path,
) -> None:
    """A degraded control db reads 'unavailable', never 0; one failed read model names itself."""
    label = "desktop/boards"
    # 1. Operations over a degraded control database.
    records: list[dict[str, str]] = []
    context, page, console_errors = _boards_page(
        browser, url, 1440, 900, board="operations", router=_boards_router(records, degraded=True)
    )
    try:
        page.wait_for_function(_board_ready_js("operations"), timeout=8000)
    except Exception:  # noqa: BLE001 — the failed state is the finding
        _row(
            errors,
            label,
            "degraded",
            "operations-load",
            "the degraded operations payload never reached its loaded state",
        )
    _settle(page, 200)
    probe = page.evaluate(BOARDS_PROBE_JS)
    for metric in ("Active runs", "Decisions owed", "Promotable runs"):
        value = probe["metrics"].get(metric)
        if value != "unavailable":
            _row(
                errors,
                label,
                "degraded",
                "operations-zero",
                f"{metric!r} rendered {value!r} on a degraded control db — an unreadable "
                "database must read 'unavailable', never a fabricated 0",
            )
    if "control database not found" not in probe["operationsText"]:
        _row(
            errors,
            label,
            "degraded",
            "operations-reason",
            "the degraded surface's named reason was not rendered",
        )
    if "could not be read" not in probe["operationsText"]:
        _row(
            errors,
            label,
            "degraded",
            "operations-attention",
            "the attention/runs sections must say the database could not be read",
        )
    if screenshots:
        shot = out / "boards_degraded_operations_desktop_dark_1440x900.png"
        page.screenshot(path=str(shot), full_page=False)
        results.append(
            {
                "case": "boards-degraded",
                "viewport": "desktop",
                "screenshot": str(shot),
                "theme": "dark",
                "board": "operations",
            }
        )
    for message in console_errors:
        _row(errors, label, "degraded", "operations-console", message[:200])
    results.append(
        {
            "case": "boards-degraded",
            "viewport": "desktop",
            "check": "degraded-operations",
            "screenshot": "",
        }
    )
    context.close()

    # 2. Surfaces with one failing read model: the failed panel names its reason + URL while
    #    its siblings still render (panel independence).
    records = []
    context, page, console_errors = _boards_page(
        browser,
        url,
        1440,
        900,
        board="surfaces",
        router=_boards_router(records, surface_failures=("/api/quality",)),
    )
    try:
        page.wait_for_function(_board_ready_js("surfaces"), timeout=8000)
    except Exception:  # noqa: BLE001 — the failed state is the finding
        _row(
            errors,
            label,
            "degraded",
            "surfaces-load",
            "the surfaces board never reached its loaded state",
        )
    _settle(page, 200)
    probe = page.evaluate(BOARDS_PROBE_JS)
    quality = probe["surfacePanels"].get("quality", "")
    if "unavailable —" not in quality or "/api/quality" not in quality:
        _row(
            errors,
            label,
            "degraded",
            "surface-failure",
            "the failed quality panel must render the service's named reason and its URL "
            f"(rendered {quality[:120]!r})",
        )
    batch = probe["surfacePanels"].get("batch", "")
    if "not measurable" not in batch:
        _row(
            errors,
            label,
            "degraded",
            "surface-independence",
            "a sibling panel must still render while one read model fails "
            f"(batch rendered {batch[:120]!r})",
        )
    for message in console_errors:
        # The 503 is this check's OWN setup (the failing read model), not an app defect: the
        # browser logs a resource error for the deliberately failed request.
        if "503 (Service Unavailable)" in message:
            continue
        _row(errors, label, "degraded", "surfaces-console", message[:200])
    results.append(
        {
            "case": "boards-degraded",
            "viewport": "desktop",
            "check": "surface-failure",
            "screenshot": "",
        }
    )
    context.close()


#: The scroll probe: the scroller's computed overflow, its box, and whether the LAST run row
#: (the known below-fold row) is inside its client area.
SCROLL_PROBE_JS = r"""
() => {
  const scroller = document.getElementById('boards');
  const rows = Array.from(document.querySelectorAll('tr[data-run-id]'));
  const last = rows.length ? rows[rows.length - 1] : null;
  const scrollerRect = scroller ? scroller.getBoundingClientRect() : null;
  const rowRect = last ? last.getBoundingClientRect() : null;
  const inside = Boolean(scrollerRect && rowRect &&
    rowRect.top >= scrollerRect.top - 1 && rowRect.bottom <= scrollerRect.bottom + 1);
  const intersects = Boolean(rowRect && rowRect.bottom > 0 && rowRect.top < window.innerHeight);
  return {
    scrollTop: scroller ? scroller.scrollTop : null,
    scrollH: scroller ? scroller.scrollHeight : null,
    clientH: scroller ? scroller.clientHeight : null,
    overflowY: scroller ? getComputedStyle(scroller).overflowY : null,
    scrollerW: scroller ? scroller.scrollWidth : null,
    scrollerCW: scroller ? scroller.clientWidth : null,
    lastRunId: last ? last.getAttribute('data-run-id') : null,
    lastVisible: inside && intersects,
    rowTop: rowRect ? rowRect.top : null,
    scrollerTop: scrollerRect ? scrollerRect.top : null,
    scrollerBottom: scrollerRect ? scrollerRect.bottom : null,
    scrollerBox: scrollerRect
      ? { x: scrollerRect.x, y: scrollerRect.y, w: scrollerRect.width, h: scrollerRect.height }
      : null,
  };
}
"""


def _expected_last_run_id() -> str:
    """The positional id of the fixture's last run row (build_operations_payload's scheme)."""
    fixture = load_boards_fixture()
    seed = fixture["operations"]
    total = int(seed.get("active_count", 0)) + int(seed.get("promotable_count", 0))
    return f"run-fixture-{total:04d}"


def _wheel_to_bottom(page: Any, box: dict[str, float] | None) -> dict[str, Any]:
    """Drive real wheel input over the scroller until the below-fold row shows (bounded)."""
    if not box:
        return {"scrollTop": None, "lastVisible": False}
    page.mouse.move(box["x"] + box["w"] / 2, box["y"] + box["h"] / 2)
    probe: dict[str, Any] = {}
    for _ in range(10):
        page.mouse.wheel(0, 700)
        _settle(page, 120)
        probe = page.evaluate(SCROLL_PROBE_JS)
        if probe.get("lastVisible"):
            break
    return probe


def _check_board_scrolling(
    browser: Any,
    url: str,
    results: list[dict[str, Any]],
    errors: list[str],
    *,
    screenshots: bool,
    out: Path,
) -> None:
    """Real wheel scrolling must reach a known below-fold row — and a hidden-overflow page
    must FAIL the same check.

    The review's finding: assigning ``scrollTop`` directly can "succeed" on a scroller with
    ``overflow-y: hidden``, which no user can wheel. The check now drives real wheel input at
    the scroller, asserts the last run row (a known below-fold row from the fixture) becomes
    visible inside the scroller's client box, and closes with a negative case — the same page
    with ``overflow-y: hidden`` injected must remain unscrollable, or the check's premise is
    wrong and the gate says so.
    """
    label = "desktop/boards"
    records: list[dict[str, str]] = []
    context, page, console_errors = _boards_page(
        browser, url, 1440, 900, board="operations", router=_boards_router(records)
    )
    try:
        page.wait_for_function(_board_ready_js("operations"), timeout=8000)
    except Exception:  # noqa: BLE001 — the failed state is the finding
        _row(
            errors,
            label,
            "scrolling",
            "operations-load",
            "the operations board never reached its loaded state",
        )
    _settle(page, 250)
    probe = page.evaluate(SCROLL_PROBE_JS)
    expected_last = _expected_last_run_id()
    if probe["overflowY"] in ("hidden", "clip"):
        _row(
            errors,
            label,
            "scrolling",
            "overflow",
            f"the board scroller computes overflow-y: {probe['overflowY']!r} — wheel scrolling "
            "is not possible",
        )
    if not probe["scrollH"] or not probe["clientH"] or probe["scrollH"] <= probe["clientH"]:
        _row(
            errors,
            label,
            "scrolling",
            "below-fold",
            "the restored board scroller does not overflow "
            f"(scrollHeight {probe['scrollH']}, clientHeight {probe['clientH']}) — "
            "below-fold content is not reachable",
        )
    elif probe["lastVisible"]:
        _row(
            errors,
            label,
            "scrolling",
            "fixture",
            f"the last run row ({probe['lastRunId']!r}) is already visible before scrolling — "
            "the fixture is too short to exercise below-fold reach",
        )
    else:
        if probe["lastRunId"] != expected_last:
            _row(
                errors,
                label,
                "scrolling",
                "known-row",
                f"the last run row is {probe['lastRunId']!r}, expected {expected_last!r}",
            )
        final = _wheel_to_bottom(page, probe["scrollerBox"])
        if final["scrollTop"] is None or final["scrollTop"] <= 0:
            _row(
                errors,
                label,
                "scrolling",
                "wheel",
                "real wheel input did not move the board scroller",
            )
        if not final["lastVisible"]:
            _row(
                errors,
                label,
                "scrolling",
                "below-fold",
                f"wheel scrolling never brought {expected_last!r} into view "
                f"(scrollTop {final['scrollTop']}, rowTop {final['rowTop']}, "
                f"scroller {final['scrollerTop']}..{final['scrollerBottom']})",
            )
        else:
            results.append(
                {
                    "case": "boards-scrolling",
                    "viewport": "desktop",
                    "check": "wheel-below-fold",
                    "screenshot": "",
                }
            )
    if probe["scrollerW"] and probe["scrollerCW"] and probe["scrollerW"] > probe["scrollerCW"] + 1:
        _row(
            errors,
            label,
            "scrolling",
            "h-overflow",
            f"the board scroller overflows horizontally ({probe['scrollerW']} > "
            f"{probe['scrollerCW']})",
        )
    # A board switch is a navigation: it must reset the scroller, not inherit the offset.
    page.click('.destination[data-board="fleet"]')
    _settle(page, 150)
    page.click('.destination[data-board="operations"]')
    _settle(page, 150)
    reset = page.evaluate("() => document.getElementById('boards').scrollTop")
    if reset != 0:
        _row(
            errors,
            label,
            "scrolling",
            "scroll-reset",
            f"returning to the operations board kept scrollTop={reset}; a board switch must "
            "start at the board's own top",
        )
    else:
        results.append(
            {
                "case": "boards-scrolling",
                "viewport": "desktop",
                "check": "scroll-reset",
                "screenshot": "",
            }
        )
    _settle(page, 200)
    for message in console_errors:
        _row(errors, label, "scrolling", "console", message[:200])
    context.close()

    # The negative case: the SAME page with overflow-y hidden must stay unscrollable. If the
    # wheel check "passes" here, it would accept the regression class the review named.
    negative_records: list[dict[str, str]] = []
    ncontext, npage, nconsole = _boards_page(
        browser, url, 1440, 900, board="operations", router=_boards_router(negative_records)
    )
    npage.add_style_tag(content="#boards { overflow-y: hidden !important; }")
    try:
        npage.wait_for_function(_board_ready_js("operations"), timeout=8000)
    except Exception:  # noqa: BLE001 — the failed state is the finding
        _row(
            errors,
            label,
            "scrolling",
            "hidden-overflow-load",
            "the negative-case operations board never reached its loaded state",
        )
    _settle(npage, 250)
    nprobe = npage.evaluate(SCROLL_PROBE_JS)
    if nprobe["overflowY"] != "hidden":
        _row(
            errors,
            label,
            "scrolling",
            "negative-setup",
            f"the negative case did not take effect (overflow-y: {nprobe['overflowY']!r})",
        )
    nfinal = _wheel_to_bottom(npage, nprobe["scrollerBox"])
    if nfinal["scrollTop"] not in (None, 0):
        _row(
            errors,
            label,
            "scrolling",
            "negative-case",
            f"the overflow-y:hidden page scrolled anyway (scrollTop {nfinal['scrollTop']}) — the "
            "wheel check does not distinguish a real scroller",
        )
    elif nfinal["lastVisible"]:
        _row(
            errors,
            label,
            "scrolling",
            "negative-case",
            "the overflow-y:hidden page showed its below-fold row without scrolling — the "
            "wheel check does not distinguish a real scroller",
        )
    else:
        results.append(
            {
                "case": "boards-scrolling",
                "viewport": "desktop",
                "check": "hidden-overflow-fails",
                "screenshot": "",
            }
        )
    _settle(npage, 200)
    for message in nconsole:
        _row(errors, label, "scrolling", "negative-console", message[:200])
    ncontext.close()


def _check_board_keyboard(
    browser: Any,
    url: str,
    results: list[dict[str, Any]],
    errors: list[str],
    *,
    screenshots: bool,
    out: Path,
) -> None:
    """Enter opens the run drawer with focus inside it; Escape closes and returns focus."""
    label = "desktop/boards"
    for theme in ("dark", "light"):
        records: list[dict[str, str]] = []
        context, page, console_errors = _boards_page(
            browser, url, 1440, 900, board="operations", theme=theme, router=_boards_router(records)
        )
        try:
            page.wait_for_function(_board_ready_js("operations"), timeout=8000)
        except Exception:  # noqa: BLE001 — the failed state is the finding
            _row(
                errors,
                label,
                "keyboard",
                "operations-load",
                "the operations board never reached its loaded state",
            )
        _settle(page, 200)
        rows = page.locator("tr[data-run-id]")
        if rows.count() == 0:
            _row(
                errors,
                label,
                "keyboard",
                "no-rows",
                "no run rows exist — the keyboard run journey cannot be exercised",
            )
            results.append(
                {
                    "case": "boards-keyboard",
                    "viewport": "desktop",
                    "check": f"{theme}-enter-escape",
                    "screenshot": "",
                }
            )
            context.close()
            continue
        # The rich run-inspection assertions need the RICH fixture row EXPLICITLY: the first
        # row in DOM order is the Operations attention table's unknown-cost run
        # (run-fixture-0007), which deliberately lacks the rich blocks this class asserts
        # (measured-zero cost, delivered knowledge, prepared step). Selecting the rich row by
        # id keeps each assertion on the payload it is written for; other fixtures fall back
        # to the first row.
        rich_rows = page.locator('tr[data-run-id="run-fixture-0001"]')
        rich = rich_rows.first if rich_rows.count() else rows.first
        origin = rich.get_attribute("data-run-id") or ""
        rich.focus()
        page.keyboard.press("Enter")
        try:
            page.locator("#run-detail-drawer:not([hidden])").wait_for(timeout=5000)
            opened = True
        except Exception:  # noqa: BLE001 — the failed state is the finding
            opened = False
        if not opened:
            _row(
                errors,
                label,
                "keyboard",
                "enter-opens",
                "Enter on a run row did not open the run drawer",
            )
        else:
            _settle(page, 250)
            probe = page.evaluate(BOARDS_PROBE_JS)
            if probe["activeId"] != "run-detail-close":
                _row(
                    errors,
                    label,
                    "keyboard",
                    "drawer-focus",
                    f"after Enter, focus is on {probe['activeId']!r} — it must move to the "
                    "drawer's close control so the drawer-scoped Escape is reachable",
                )
            try:
                page.locator("#run-detail-content table").first.wait_for(timeout=5000)
            except Exception:  # noqa: BLE001 — a named missing render, not a crash
                _row(
                    errors,
                    label,
                    "keyboard",
                    "drawer-content",
                    "the run detail drawer never rendered its content",
                )
            # Drawer content: the additive run-inspection blocks must actually render — a
            # non-empty drawer is not enough. Each assertion names the block the slice exists
            # to surface (cost provenance incl. measured-zero, the independent verdict kept
            # separate from the agent's claim, delivered-knowledge ids, the prepared-step
            # reference, and a timing row whose state is unknown).
            drawer = page.evaluate(DRAWER_PROBE_JS)
            if not drawer.get("present"):
                _row(
                    errors,
                    label,
                    "keyboard",
                    "drawer-blocks",
                    "the drawer has no content node to inspect",
                )
            else:
                if drawer.get("costProvenance") != "$0.0000 \u00b7 metered":
                    _row(
                        errors,
                        label,
                        "keyboard",
                        "drawer-cost",
                        "the drawer must show the measured-zero cost provenance "
                        f"(got {drawer.get('costProvenance')!r})",
                    )
                measured = (drawer.get("verification") or {}).get("measured", "")
                if "independent" not in measured:
                    _row(
                        errors,
                        label,
                        "keyboard",
                        "drawer-verification",
                        "the drawer must show the independent verification separately "
                        f"(got {measured!r})",
                    )
                said = (drawer.get("verification") or {}).get("said", "")
                if "narration" not in said:
                    _row(
                        errors,
                        label,
                        "keyboard",
                        "drawer-said",
                        "the agent's own narration must be shown separately as SAID "
                        f"(got {said!r})",
                    )
                delivered_text = drawer.get("deliveredText") or ""
                if not drawer.get("deliveredPhase") or "kb-fixture-aaa" not in delivered_text:
                    _row(
                        errors,
                        label,
                        "keyboard",
                        "drawer-delivered",
                        "the drawer must show the delivered-knowledge ids",
                    )
                if drawer.get("preparedPath") != ".fleet/prepared_steps/implement.a1.json":
                    _row(
                        errors,
                        label,
                        "keyboard",
                        "drawer-prepared",
                        "the drawer must show the prepared-step reference",
                    )
                if not drawer.get("hasUnknownTiming"):
                    _row(
                        errors,
                        label,
                        "keyboard",
                        "drawer-timing-unknown",
                        "the drawer must render an unknown-state timing row",
                    )
            if screenshots:
                shot = out / f"boards_keyboard_drawer_{theme}_1440x900.png"
                page.screenshot(path=str(shot), full_page=False)
                results.append(
                    {
                        "case": "boards-keyboard",
                        "viewport": "desktop",
                        "screenshot": str(shot),
                        "theme": theme,
                        "check": "drawer-open",
                    }
                )
            page.keyboard.press("Escape")
            _settle(page, 250)
            probe = page.evaluate(BOARDS_PROBE_JS)
            if probe["drawerHidden"] is not True:
                _row(
                    errors,
                    label,
                    "keyboard",
                    "escape-closes",
                    "Escape did not close the drawer — focus never reached the drawer-scoped "
                    "handler",
                )
            if probe["activeRunId"] != origin:
                _row(
                    errors,
                    label,
                    "keyboard",
                    "focus-return",
                    f"focus returned to {probe['activeRunId']!r}, not the originating row "
                    f"{origin!r}",
                )
            # Unknown-cost case: a run with no ledger must render an EXPLICIT unknown
            # provenance — never a fabricated $0.0000.
            unknown_row = page.locator('tr[data-run-id="run-fixture-0007"]')
            if unknown_row.count():
                unknown_row.first.focus()
                page.keyboard.press("Enter")
                try:
                    page.locator('#run-detail-content [data-cost-provenance="unknown"]').wait_for(
                        timeout=5000
                    )
                except Exception:  # noqa: BLE001 — the failed state is the finding
                    _row(
                        errors,
                        label,
                        "keyboard",
                        "drawer-cost-unknown",
                        "the unknown-cost run must render an explicit unknown provenance",
                    )
                page.keyboard.press("Escape")
                _settle(page, 150)
            # HTTP-200 error envelope: the service's named error renders by name, never a blank.
            error_row = page.locator('tr[data-run-id="run-fixture-0008"]')
            if error_row.count():
                error_row.first.focus()
                page.keyboard.press("Enter")
                try:
                    page.locator('#run-detail-content:has-text("Run detail unavailable")').wait_for(
                        timeout=5000
                    )
                except Exception:  # noqa: BLE001 — the failed state is the finding
                    _row(
                        errors,
                        label,
                        "keyboard",
                        "drawer-error-envelope",
                        "a 200 error envelope must render the named error, not a blank",
                    )
                page.keyboard.press("Escape")
                _settle(page, 150)
        _settle(page, 200)
        for message in console_errors:
            _row(errors, label, "keyboard", "console", message[:200])
        results.append(
            {
                "case": "boards-keyboard",
                "viewport": "desktop",
                "check": f"{theme}-enter-escape",
                "screenshot": "",
            }
        )
        context.close()


def boards_coverage(*, legacy_ran: bool = False) -> dict[str, list[str]]:
    """The restored classes' EXECUTED coverage, and what this run does not exercise.

    The report prints these claims verbatim and prints nothing else as coverage, so the gate
    cannot inherit another profile's claims (the review's finding: the restored profile's
    report still listed mobile, forced-colors, WCAG-AA contrast and first-paint checks, none
    of which its classes run).
    """
    performed = [
        "navigation: seven destinations, exactly one visible board, aria-current, no "
        "horizontal overflow, every board captured (desktop dark+light, narrow dark)",
        "loading: first visit and reload for Operations/Surfaces/Routing; each endpoint "
        "requested exactly once; rendered fixture values asserted; delayed and failed routing "
        "responses settle (loading state refused by the readiness predicate)",
        "degraded: an unreadable control db reads 'unavailable', never 0; a failed read model "
        "names its reason and URL while its siblings render",
        "scrolling: real wheel input reaches the last below-fold run row; an overflow-y:hidden "
        "page fails the same check",
        "keyboard: Enter opens the run drawer with focus on its close control; Escape closes it "
        "and returns focus to the originating row; the loaded drawer renders the run-inspection "
        "blocks (measured-zero and unknown cost provenance, independent verification separate "
        "from the agent's claim, delivered-knowledge ids, the prepared-step reference, an "
        "unknown-state timing), and a 200 error envelope renders by name",
    ]
    omitted: list[str] = []
    if legacy_ran:
        performed.append(
            "legacy parked classes: their own documented checks (geometry/semantics, charts, "
            "visuals, style, a11y, parity, live, interactions)"
        )
    else:
        omitted = [
            "mobile viewport (390x844)",
            "forced-colors theme",
            "WCAG-AA contrast",
            "first-paint timing",
            "charts, visuals, style, a11y, parity, live, interactions (legacy parked classes)",
        ]
    return {"performed": performed, "omitted": omitted}


def run_boards_gate(out: Path, screenshots: bool) -> tuple[list[dict[str, Any]], list[str]]:
    """Run the restored-room classes: navigation, loading, degraded, scrolling, keyboard.

    Fixture-driven like every other class (waiver W2): no live Redis, clock, or network. The
    screenshots this class writes are the served room's acceptance evidence — a run with zero
    captures fails structurally in ``write_report``.
    """
    from playwright.sync_api import sync_playwright

    url, httpd = _serve()
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(args=["--no-sandbox"])
            _check_board_navigation(browser, url, results, errors, screenshots=screenshots, out=out)
            _check_board_loading(browser, url, results, errors, screenshots=screenshots, out=out)
            _check_board_degraded(browser, url, results, errors, screenshots=screenshots, out=out)
            _check_board_scrolling(browser, url, results, errors, screenshots=screenshots, out=out)
            _check_board_keyboard(browser, url, results, errors, screenshots=screenshots, out=out)
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
                _row(
                    errors,
                    "static",
                    "parity",
                    "placement",
                    f"{group}:{record.get('id')} surface {surface!r} not in palette",
                )
    for capability in inventory.get("capabilities", []):
        if not capability.get("surface"):
            _row(
                errors,
                "static",
                "parity",
                "capability-surface",
                f"capability {capability.get('id')} has no surface",
            )
        if not capability.get("member_ids"):
            _row(
                errors,
                "static",
                "parity",
                "capability-members",
                f"capability {capability.get('id')} has no member ids",
            )


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
                body=json.dumps(
                    {
                        "ok": True,
                        "action": path.rstrip("/").rsplit("/", 1)[-1],
                        "note": "recorded by the parity gate",
                    }
                ),
            )
            return
        if path == "/api/glance":
            route.fulfill(status=200, content_type="application/json", body=json.dumps(wire))
        elif path == "/api/events":
            route.fulfill(status=200, content_type="text/event-stream", body=glance_frames)
        elif path.startswith("/api/events/"):
            route.fulfill(status=200, content_type="text/event-stream", body=event_frames)
        elif path in fixtures:
            route.fulfill(
                status=200, content_type="application/json", body=json.dumps(fixtures[path])
            )
        else:
            route.abort()

    return handler


def run_parity_gate(out: Path, screenshots: bool) -> tuple[list[dict[str, Any]], list[str]]:
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
                    + "data: "
                    + json.dumps({"control_epoch": epoch}, separators=(",", ":"))
                    + "\n\n"
                    + "event: replay_complete\n"
                    + "data: "
                    + json.dumps({"control_epoch": epoch}, separators=(",", ":"))
                    + "\n\n"
                )
                # A few real per-cell frames so the R4b feed has live-shaped content, ending with
                # the replay boundary the client keys its stream state off.
                event_frames = (
                    "data: "
                    + json.dumps({"type": "step_start", "part": {"name": "build"}})
                    + "\n\n"
                    + "data: "
                    + json.dumps(
                        {
                            "type": "tool_use",
                            "part": {"name": "bash", "state": {"status": "completed"}},
                        }
                    )
                    + "\n\n"
                    + "data: "
                    + json.dumps(
                        {
                            "type": "step_finish",
                            "part": {"cost": 0.01, "tokens": {"input": 120, "output": 40}},
                        }
                    )
                    + "\n\n"
                    + "event: replay_complete\ndata: {}\n\n"
                )
                context = browser.new_context(
                    viewport={"width": width, "height": height},
                    timezone_id="UTC",
                    locale="en-US",
                    reduced_motion="reduce",
                    color_scheme="dark",
                )
                page = context.new_page()
                records: list[dict[str, str]] = []
                console_errors = _attach_console(page)
                page.route(
                    "**/api/**",
                    _parity_router(records, wire, glance_frames, event_frames, fixtures),
                )
                page.goto(url, wait_until="domcontentloaded")
                page.locator('[data-render-state="ready"]').wait_for(timeout=20000)

                # 2. every resting region is present exactly once.
                for region in PARITY_RESTING_REGIONS:
                    count = page.locator(f'[data-region="{region}"]').count()
                    if count != 1:
                        _row(errors, name, "parity", "resting-region", f"{region} count={count}")

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
                            arg=f"#wb-{panel}",
                            timeout=5000,
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
                        _row(
                            errors,
                            name,
                            "parity-nonempty",
                            panel,
                            "panel rendered an explicit error state",
                        )
                    # One representative mutation-wiring probe: the attention lens' steer chip
                    # must POST to the flags route (the handler fulfills it).
                    if panel == "attention":
                        records.clear()
                        steer = page.locator("#wb-attention [data-action='steer']")
                        if steer.count() == 0:
                            _row(
                                errors,
                                name,
                                "parity-action",
                                "steer",
                                "attention flag rendered no steer action",
                            )
                        else:
                            steer.first.click()
                            page.wait_for_timeout(250)
                            if not any(
                                r["method"] == "POST" and r["path"].endswith("/steer")
                                for r in records
                            ):
                                _row(
                                    errors,
                                    name,
                                    "parity-action",
                                    "steer",
                                    "steer click did not POST to the flags route",
                                )
                if screenshots:
                    shot = out / f"parity_workbench_{name}.png"
                    page.screenshot(path=str(shot), full_page=False)
                    results.append(
                        {"case": "parity-workbench", "viewport": name, "screenshot": str(shot)}
                    )
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
                    _row(
                        errors,
                        name,
                        "parity-dock",
                        "worker-stream",
                        "no per-worker /api/events/<cell> request",
                    )
                entries = page.locator(
                    "#selection-dock [data-dock-region='worker'] [data-feed-entry]"
                ).count()
                if entries < 1:
                    _row(errors, name, "parity-dock", "worker-feed", f"{entries} event entries")
                actions = page.locator(
                    "#selection-dock [data-dock-region='worker'] [data-action]"
                ).count()
                if actions < 1:
                    _row(errors, name, "parity-dock", "worker-actions", "no [data-action] chips")
                timings = page.locator(
                    "#selection-dock [data-dock-region='timing'] [data-timing]"
                ).count()
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
                    results.append(
                        {"case": "parity-dock", "viewport": name, "screenshot": str(shot)}
                    )
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

    # G-2 no horizontal page overflow. Vertical page scroll is allowed — the re-baseline
    # (decision 9f357fce) superseded the no-scroll resting screen.
    if geometry["scrollWidth"] > width + 1:
        _row(errors, label, fixture_id, "G-2", f"page scrollWidth {geometry['scrollWidth']}")

    # G-3 no region/answer horizontal overflow (vertical overflow scrolls — re-baseline).
    for region in REGIONS:
        info = geometry["regions"][region]
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
            _row(
                errors,
                label,
                fixture_id,
                "G-7",
                f"{region} box {tuple(round(v, 1) for v in got)} want {want}",
            )

    # G-13 row schema; G-14 row count + line clamps + fixed capacities.
    row_count = ROW_COUNT[name]
    if len(geometry["rows"]) != row_count:
        _row(errors, label, fixture_id, "G-14", f"{len(geometry['rows'])} rows want {row_count}")
    for index, row in enumerate(geometry["rows"]):
        if set(row["fields"]) != ROW_FIELDS:
            _row(
                errors,
                label,
                fixture_id,
                "G-13",
                f"row {index} fields {sorted(set(row['fields']) ^ ROW_FIELDS)}",
            )
    attention = ATTENTION_COUNT[name]
    if geometry["attentionItems"] != attention:
        _row(
            errors,
            label,
            fixture_id,
            "G-14",
            f"{geometry['attentionItems']} attention items want {attention}",
        )
    if geometry["attentionLines"] != attention * 2:
        _row(
            errors,
            label,
            fixture_id,
            "G-14",
            f"{geometry['attentionLines']} item-lines want {attention * 2}",
        )
    if geometry["rowLines"] != row_count * 3:
        _row(
            errors,
            label,
            fixture_id,
            "G-14",
            f"{geometry['rowLines']} row-lines want {row_count * 3}",
        )
    if geometry["detailLines"] != 2:
        _row(errors, label, fixture_id, "G-14", f"{geometry['detailLines']} detail-lines want 2")
    for entry in geometry["lineBearing"]:
        if entry["lines"] > entry["max"]:
            _row(
                errors,
                label,
                fixture_id,
                "G-14",
                f"{entry['where']} renders {entry['lines']} lines > max {entry['max']}",
            )

    # G-5 type floors; G-6 non-empty required values; no missing data-no-ellipsis.
    value_floor = 12.0 if name == "mobile" else 13.0
    for entry in geometry["valueSizes"]:
        if entry["size"] < value_floor - 0.01:
            _row(
                errors,
                label,
                fixture_id,
                "G-5",
                f"{entry['region']} value font {entry['size']} < {value_floor}",
            )
    for entry in geometry["labelSizes"]:
        if entry["size"] < 11.0 - 0.01:
            _row(
                errors,
                label,
                fixture_id,
                "G-5",
                f"{entry['region']} label font {entry['size']} < 11",
            )
    for key, value in geometry["valueTexts"].items():
        if not value:
            _row(errors, label, fixture_id, "G-6", f"empty value {key}")
    if geometry["noEllipsisMissing"]:
        _row(
            errors,
            label,
            fixture_id,
            "G-6",
            f"{geometry['noEllipsisMissing']} required values lack data-no-ellipsis",
        )

    # Exact schemas: answer field sets, money risk marker, bounded composition.
    for answer, expected in FIELDS.items():
        actual = geometry["answerFields"].get(answer, [])
        if len(actual) != len(set(actual)) or set(actual) != expected:
            _row(
                errors,
                label,
                fixture_id,
                "schema",
                f"{answer} fields {sorted(set(actual) ^ expected)}",
            )
    expected_risk = 1 if fixture_id == "F-3" else 0
    if geometry["moneyRiskCount"] != expected_risk:
        _row(
            errors,
            label,
            fixture_id,
            "G-10",
            f"money-risk markers {geometry['moneyRiskCount']} want {expected_risk}",
        )
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
        elif (
            box["top"] < -0.5
            or box["bottom"] > height + 0.5
            or box["left"] < -0.5
            or box["right"] > width + 0.5
        ):
            fail(
                "SEM-fold",
                f"{answer} box "
                f"{tuple(round(box[k], 1) for k in ('left', 'top', 'right', 'bottom'))}",
            )
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
            fail(
                "SEM-G1",
                f"{field} rendered {got['state']}/{got['age']} "
                f"fixture {want['state']}/{want['age_seconds']}",
            )

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
        fail(
            "SEM-G3",
            f"risk.identity {risk.get('risk.identity')!r} fixture {want_risk['identity']!r}",
        )

    # ── ON-G4 money: five exact values, marker count, visible provenance ─────────────────
    want_cost = wire["cost"]
    for field, key in (
        ("money.spend", "spend"),
        ("money.burn", "burn"),
        ("money.quota", "quota"),
        ("money.wallet", "wallet"),
        ("money.leases", "leases"),
    ):
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
        for field in (
            "decision.target",
            "decision.kind",
            "decision.authority",
            "decision.eligibility",
        ):
            if decision.get(field) != "none":
                fail(
                    "SEM-G5", f"none-decision must render {field}=none, got {decision.get(field)!r}"
                )
    else:
        if (
            decision.get("decision.target") != want_decision["target"]
            or decision.get("decision.kind") != want_decision["kind"]
        ):
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
        fail("SEM-G6", f"trust.epoch {trust.get('trust.epoch')!r} fixture {want_trust['epoch']!r}")
    if str(trust.get("trust.unknown_count")) != str(want_trust["unknown_count"]):
        fail(
            "SEM-G6",
            f"unknown_count {trust.get('trust.unknown_count')!r} "
            f"fixture {want_trust['unknown_count']!r}",
        )

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
                fail(
                    "SEM-G7", f"{marginal_name}.{bucket_name} label {bucket['label']!r} not legible"
                )
            want_value = str(wire["composition"][marginal_name][bucket_name])
            if bucket["value"] != want_value:
                fail(
                    "SEM-G7",
                    f"{marginal_name}.{bucket_name} rendered {bucket['value']!r} "
                    f"fixture {want_value!r}",
                )
        if not buckets.get("top", {}).get("category"):
            fail("SEM-G7", f"{marginal_name} top bucket lacks data-category")

    # ── R2 rows: spec/cell, paired evidence, receipt, budget facets, authority ────────────
    expected_rows = wire["run_sample"][: len(probe["rows"])]

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
            fail(
                "SEM-R2",
                f"row {row['id']} spec {row['values'].get('spec.cell')!r} "
                f"fixture {expected.get('spec.cell')!r}",
            )
        if row["values"].get("evidence.advisory") == row["values"].get("evidence.measured"):
            fail("SEM-R2", f"row {row['id']} ADVISORY claim equals MEASURED proof")
        for field in ("decision.eligibility", "decision.receipt", "cost.provenance"):
            if not row["values"].get(field):
                fail("SEM-R2", f"row {row['id']} {field} empty")
        budget = row["budget"] or {}
        for facet in ("reserved", "cap", "headroom", "settlement"):
            if not budget.get(facet):
                fail("SEM-R2", f"row {row['id']} budget.{facet} missing")
        if row["values"].get("decision.eligibility") in GOVERNED_STATES and not row["hasAuthority"]:
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


def _verify_captures(results: list[dict[str, Any]]) -> list[str]:
    """Capture-file readability: every recorded capture must exist and carry bytes.

    A nonempty screenshot LIST is not acceptance — the files must be real artifacts a
    controller can open. A missing or empty capture is a named error, never a silent pass.
    """
    errors: list[str] = []
    for result in results:
        shot = str(result.get("screenshot") or "")
        if not shot:
            continue
        path = Path(shot)
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(
                f"GATE-CAPTURE-UNREADABLE: capture {shot} is missing or empty — a recorded "
                "screenshot that cannot be read is not evidence"
            )
    return errors


def write_report(
    results: list[dict[str, Any]],
    errors: list[str],
    report_path: Path,
    json_path: Path,
    check_fixtures_exit: int,
    *,
    requested_classes: list[str] | None = None,
    candidate: str = "",
    candidate_verified: bool = False,
    preview: str = "",
    preview_verified: bool = False,
    preview_exercised: bool = False,
    preview_serves_candidate: bool = False,
    coverage: dict[str, Any] | None = None,
) -> int:
    """Write the markdown + JSON reports; return the exit code.

    The report is the gate's artifact (the website gate's pattern): status, the classes that
    ran, a per-class screenshot rollup, and the full failure list with the offending selector or
    value, so a failure is actionable without re-running the browser.

    The acceptance-profile contract (AIO remediation 2026-09-14): ``requested_classes`` is the
    ENUMERATED roster this run must execute; every class is reported with its executed/omitted
    state, an omitted required class is a named FAIL (never a silent skip), and the candidate
    SHA + preview target are BOUND into both artifacts so the verdict describes exactly what
    was reviewed.

    ``coverage`` (2026-09-18 review): when the caller declares what the run ACTUALLY exercises
    (``performed`` / ``omitted``), the report prints those claims and the viewports/themes the
    result rows recorded — never a static list inherited from another profile. Without a
    declaration the historical legacy lines are printed, which describe the parked classes'
    own runs.
    """
    requested = list(requested_classes or ["geometry"])
    executed: list[str] = []

    # The per-class evidence keys the runners actually record (the gates' own case/fixture
    # vocabulary — the executed roster derives from THESE, never from a parallel guess).
    def _class_of(result: dict[str, Any]) -> str:
        case = str(result.get("case") or result.get("fixture") or "")
        if case.startswith("boards-"):
            # boards-navigation / boards-loading / boards-degraded / boards-scrolling /
            # boards-keyboard -> the restored class each result proves.
            return case.split("-", 1)[1]
        if case.startswith("F-"):
            return "geometry"
        if case == "live":
            return "live"
        if case in ("interactions", "visuals", "style", "a11y"):
            return case
        if case in ("history", "empty", "error") or str(case).startswith("chart"):
            return "charts"
        if case.startswith("parity"):
            return "parity"
        return ""

    for result in results:
        klass = _class_of(result)
        if klass and klass not in executed:
            executed.append(klass)
    for klass in requested:
        if klass not in executed:
            errors.append(
                f"PROFILE-OMITTED: required class '{klass}' was requested but produced no "
                "results — an omission is a FAIL, never a silent skip"
            )
    status = "PASS" if not errors and check_fixtures_exit == 0 else "FAIL"
    # Zero-captures rejection (remediation closed-loop, decision f987cde9): acceptance is a
    # RENDERED artifact. A gate run that produces no screenshot — the 2026-09-13 failure class
    # ("PASS, Screenshots: 0") — is a FAIL, structurally, whatever the fixture checks say. A
    # capture is a result that recorded a screenshot PATH: behavior rows with no capture are
    # evidence rows, never screenshots, and cannot satisfy the rule.
    captures = [result for result in results if str(result.get("screenshot") or "")]
    if not captures:
        errors.append(
            "GATE-CAPTURES: zero screenshots recorded — acceptance requires rendered proof; "
            "a PASS with no captures is structurally impossible"
        )
        status = "FAIL"
    # Roll the captures up by class so the report says what each capture proves.
    by_class: dict[str, int] = {}
    for result in captures:
        key = result.get("case") or result.get("fixture") or "resting"
        by_class[key] = by_class.get(key, 0) + 1
    rollup = ", ".join(f"{key} {count}" for key, count in sorted(by_class.items())) or "none"
    lines = [
        "# Control Room render gate",
        "",
        f"**Status:** {status}",
        "**Classes:** navigation · loading · degraded · scrolling · keyboard (the restored "
        "served boards) · legacy parked: geometry/semantics (IA §10.3/§10) · charts · visuals · "
        "style · a11y · feature-parity (u5) · live IA-core · interactions",
        f"**Requested classes:** {', '.join(requested)}",
        f"**Executed classes:** {', '.join(executed) or 'none'}",
        f"**Omitted classes:** {', '.join(c for c in requested if c not in executed) or 'none'}",
        "**Fixtures:** boards (restored) + F-0..F-7 (legacy parked; deterministic, no live "
        "Redis/clock/network — waiver W2)",
    ]
    if coverage is None:
        # Legacy (parked) runs: the classes below actually run these checks.
        lines += [
            f"**Viewports:** {', '.join(f'{k} {w}x{h}' for k, (w, h) in VIEWPORTS.items())}",
            f"**Themes:** {', '.join(THEMES)}",
            "**Primitives:** present/unique · in-viewport · non-zero box · scrollable pages "
            "(vertical) · no horizontal overflow · WCAG-AA contrast · first-paint · console-clean",
        ]
    else:
        seen_viewports = sorted({str(r.get("viewport")) for r in results if r.get("viewport")})
        seen_themes = sorted({str(r.get("theme")) for r in results if r.get("theme")})
        lines += [
            f"**Viewports exercised:** {', '.join(seen_viewports) or 'none recorded'}",
            f"**Themes exercised:** {', '.join(seen_themes) or 'none recorded'}",
            f"**Coverage executed:** {' · '.join(coverage.get('performed') or [])}",
            f"**Coverage omitted:** {', '.join(coverage.get('omitted') or []) or 'none'}",
        ]
    if candidate:
        label = (
            "verified against the checkout HEAD"
            if candidate_verified
            else ("UNVERIFIED (does not match the checkout HEAD)")
        )
        lines.append(f"**Candidate:** {candidate} ({label})")
    if preview:
        if preview_exercised:
            label = "exercised (reachable)" if preview_verified else "UNREACHABLE"
            if preview_verified and candidate:
                label += (
                    ", serves the candidate's bytes"
                    if preview_serves_candidate
                    else ", SERVES A DIFFERENT TREE (asset hash mismatch)"
                )
        else:
            label = (
                "NOT exercised — the gate served its own instance (pass --base to target a preview)"
            )
        lines.append(f"**Preview target:** {preview} ({label})")
    lines += [
        "",
        f"**Screenshots:** {len(captures)} ({rollup})",
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
    for result in captures:
        rel = result.get("screenshot", "")
        key = result.get("case") or result.get("fixture") or "resting"
        lines.append(f"- `{rel}` — {key}/{result.get('viewport', '?')}")
    lines.append("")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "status": status,
                "requested_classes": requested,
                "executed_classes": executed,
                "candidate": candidate,
                "candidate_verified": bool(candidate_verified),
                "preview": preview,
                "preview_verified": bool(preview_verified),
                "preview_exercised": bool(preview_exercised),
                "preview_serves_candidate": bool(preview_serves_candidate),
                "screenshots": results,
                "coverage": coverage or {},
                "errors": errors,
            },
            indent=2,
        ),
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
    parser.add_argument(
        "--screenshot-themes",
        default="dark",
        help="comma-separated themes to screenshot (contrast runs all themes)",
    )
    parser.add_argument(
        "--check-fixtures",
        action="store_true",
        help="validate deterministic fixtures without a browser",
    )
    parser.add_argument(
        "--boards",
        action="store_true",
        help="run the restored-board classes (navigation, loading, degraded, scrolling, "
        "keyboard) — the served room; the default when no legacy class flag is given",
    )
    parser.add_argument(
        "--geometry",
        action="store_true",
        help="legacy parked class: the single-screen geometry/semantics gate (F-0..F-7)",
    )
    parser.add_argument(
        "--charts",
        action="store_true",
        help="legacy parked class: the trends-lens chart class (a1)",
    )
    parser.add_argument(
        "--visuals",
        action="store_true",
        help="legacy parked class: the R4 SVG visual class (a2)",
    )
    parser.add_argument(
        "--style", action="store_true", help="legacy parked class: the styling/a11y class (a3)"
    )
    parser.add_argument(
        "--a11y",
        action="store_true",
        help="legacy parked class: the accessibility class (IA §10.5 A)",
    )
    parser.add_argument(
        "--parity",
        action="store_true",
        help="legacy parked class: the FEATURE-PARITY workbench checks (u5)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="legacy parked class: the IA-core class against the live /api/* (no fixtures)",
    )
    parser.add_argument(
        "--interactions",
        action="store_true",
        help="legacy parked class: the single-screen slice interactions (workbench path)",
    )
    parser.add_argument(
        "--profile",
        choices=[ACCEPTANCE_PROFILE],
        default=None,
        help="the required acceptance profile: the restored room's five classes "
        "(navigation, loading, degraded, scrolling, keyboard), dark + light "
        "screenshots, and a bound --candidate — each required class enumerated "
        "in the report; an omission is a named FAIL",
    )
    parser.add_argument(
        "--candidate", default=None, help="the candidate SHA under review — bound into the report"
    )
    parser.add_argument(
        "--preview",
        default=None,
        help="the preview target (URL) under review — bound into the report",
    )
    parser.add_argument(
        "--base",
        default=None,
        help="render an already-running portal at this URL instead of starting one",
    )
    args = parser.parse_args()

    global _BASE_OVERRIDE
    if args.base:
        _BASE_OVERRIDE = args.base.rstrip("/")

    profile = args.profile
    if profile == ACCEPTANCE_PROFILE:
        # The profile is the ENUMERATED contract: every restored class runs, dark + light
        # screenshots, and a candidate is required (Astra finding): acceptance without a
        # candidate identity is the overstated-verdict class the profile exists to catch.
        if not args.candidate:
            print(
                "the acceptance profile requires --candidate <sha> — an unidentified "
                "candidate cannot be accepted",
                file=sys.stderr,
            )
            return 2
        args.boards = True
        args.no_screenshot = False
        args.screenshot_themes = "dark,light"

    legacy_requested = any(
        (
            args.geometry,
            args.charts,
            args.visuals,
            args.style,
            args.a11y,
            args.parity,
            args.live,
            args.interactions,
        )
    )
    if not legacy_requested:
        # The served room is the default target: a bare invocation checks the room the server
        # actually serves. The parked single-screen classes are explicit opt-ins.
        args.boards = True

    fixtures = [item.strip() for item in args.fixtures.split(",") if item.strip()]
    fixture_rc = check_fixtures()
    if args.check_fixtures:
        return fixture_rc

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report_path = Path(args.report) if args.report else out / "gate_report.md"
    json_path = Path(args.json_path) if args.json_path else out / "gate_report.json"

    # The class roster this run requests — the report enumerates each (executed/omitted), and
    # an omitted required class is a FAIL, never a silent skip.
    requested_classes: list[str] = []
    if args.boards:
        requested_classes.extend(PROFILE_CLASSES)
    for flag, name in (
        (args.geometry, "geometry"),
        (args.charts, "charts"),
        (args.visuals, "visuals"),
        (args.style, "style"),
        (args.a11y, "a11y"),
        (args.parity, "parity"),
        (args.live, "live"),
        (args.interactions, "interactions"),
    ):
        if flag:
            requested_classes.append(name)

    try:
        screenshot_themes = tuple(
            item.strip() for item in args.screenshot_themes.split(",") if item.strip()
        )
        results, errors = [], []
        if args.boards:
            board_results, board_errors = run_boards_gate(out, not args.no_screenshot)
            results, errors = results + board_results, errors + board_errors
        if args.geometry:
            geometry_results, geometry_errors = run_browser_gate(
                fixtures, out, not args.no_screenshot, screenshot_themes=screenshot_themes
            )
            results, errors = results + geometry_results, errors + geometry_errors
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
        if args.interactions:
            interaction_results, interaction_errors = run_acceptance_interactions(
                out, not args.no_screenshot
            )
            results, errors = results + interaction_results, errors + interaction_errors
    except ImportError:
        print(
            "playwright is not installed; run with --check-fixtures for the browser-free check",
            file=sys.stderr,
        )
        return 2
    except Exception as error:  # noqa: BLE001 - a missing browser is exit 2, not a silent pass
        print(f"browser unavailable: {error}", file=sys.stderr)
        print(
            "run `python3 -m playwright install --with-deps chromium` in an environment with "
            "the system libraries, or use --check-fixtures",
            file=sys.stderr,
        )
        return 2

    # Capture-file readability (the rendered proof must be real, not a filename): every
    # recorded capture must exist and carry bytes.
    errors.extend(_verify_captures(results))

    # Identity verification (Astra finding, 2026-09-14): a supplied SHA/URL is a LABEL until it
    # is checked. The candidate is verified against the checkout the gate runs from; the
    # preview is verified by actually reaching it (only when the gate was pointed at it via
    # --base — a self-served run never exercised the preview target and must say so).
    candidate_verified = False
    if args.candidate:
        try:
            head = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=Path.cwd(),
                capture_output=True,
                text=True,
                timeout=15,
            ).stdout.strip()
        except Exception:  # noqa: BLE001 — an unreadable checkout verifies nothing
            head = ""
        candidate_verified = bool(head) and (
            head.startswith(args.candidate) or args.candidate.startswith(head)
        )
        if not candidate_verified:
            errors.append(
                f"CANDIDATE-UNVERIFIED: --candidate {args.candidate!r} does not match the "
                f"checkout HEAD {head[:12]!r} — the report cannot claim the reviewed candidate"
            )
    preview_verified = False
    preview_serves_candidate = False
    # One canonical target (reviewer finding 2026-09-14): the browser renders ``--base`` while
    # identity checks used ``--preview`` — different URLs could produce a PASS whose
    # ``preview_exercised`` claim described a target the browser never visited. The target is
    # resolved ONCE here; a conflict is refused, never silently reconciled.
    canonical_preview, target_error = _canonical_preview_target(args.base, args.preview)
    if target_error:
        print(target_error, file=sys.stderr)
        return 2
    preview_exercised = bool(canonical_preview and args.base)
    if canonical_preview and args.base:
        try:
            import urllib.request

            with urllib.request.urlopen(canonical_preview, timeout=10) as response:
                preview_verified = response.status == 200
        except Exception:  # noqa: BLE001 — an unreachable preview verifies nothing
            preview_verified = False
        if not preview_verified:
            errors.append(
                f"PREVIEW-UNREACHABLE: {canonical_preview!r} did not answer 200 — "
                "the target the report binds was not exercised"
            )
        elif args.candidate and preview_verified:
            # The preview must SERVE the candidate's COMMITTED bytes, not merely answer
            # (reviewer finding 2026-09-14): every served application artifact (index, JS,
            # CSS) is hashed over HTTP and compared with its ``git show HEAD:`` blob — the
            # committed candidate, never the working tree (an uncommitted edit must not be
            # attributable to HEAD), and never a single asset standing in for the app.
            served = _compare_served_assets(canonical_preview)
            if not served:
                errors.append(
                    "PREVIEW-SERVES-UNVERIFIED: no comparable committed artifacts were "
                    "found — the binding is unproven"
                )
            else:
                preview_serves_candidate = all(served.values())
                mismatched = [name for name, ok in served.items() if not ok]
                if mismatched:
                    errors.append(
                        "PREVIEW-SERVES-OTHER: the preview's served bytes differ from the "
                        f"committed candidate for {', '.join(sorted(mismatched))} — the "
                        "preview is not serving this candidate"
                    )
    coverage = boards_coverage(legacy_ran=legacy_requested) if args.boards else None
    return write_report(
        results,
        errors,
        report_path,
        json_path,
        fixture_rc,
        requested_classes=requested_classes,
        coverage=coverage,
        candidate=args.candidate or "",
        candidate_verified=candidate_verified,
        preview=canonical_preview or "",
        preview_verified=preview_verified,
        preview_exercised=preview_exercised,
        preview_serves_candidate=preview_serves_candidate,
    )


if __name__ == "__main__":
    raise SystemExit(main())
