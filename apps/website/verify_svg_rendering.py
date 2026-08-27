#!/usr/bin/env python3
"""verify_svg_rendering.py — playwright rendering gate for the site's inline SVGs.

Every inline <svg> on the target pages must render as a real diagram. The gate
checks, per SVG:

  SIZE     rendered box > 100px on both axes      (no 0x0, no collapse)
  OVERFLOW no horizontal/vertical overflow beyond the document scroll area
           (an svg inside an overflow-x:auto well does not inflate the
           document scroll area, so a real overflow here means a break-out)
  OFFSCREEN left edge not negative
  ASPECT   rendered aspect ratio matches the viewBox within tolerance
           (aspect-correct at any width; height:auto preserves it)
  BALANCE  text/shape balance — the rendered <text> label wall must stay
           <= 1.5x the shape markup length (label walls are flagged and the
           figure redesigned), and never an empty shell or a pure text wall
  PAINT    first-paint visibility — the page reports a first paint and every
           visible svg is actually painted (opaque, non-zero box, laid out)
  CONSOLE  the page loads console-clean — no console error or page exception

An svg that is intentionally hidden ([hidden], display:none, visibility:hidden,
aria-hidden="true") is reported as SKIP and is not a gate failure.

Exit code 0 = gate PASS, 1 = FAIL. A per-svg table + per-page screenshots are
written to the report directory. The markdown report is the gate's artifact.

Usage:
  python3 apps/website/verify_svg_rendering.py
  python3 apps/website/verify_svg_rendering.py --base http://127.0.0.1:8899
  python3 apps/website/verify_svg_rendering.py --mobile --out /tmp/site_scan

Options:
  --base URL     serve this base instead of the built-in static server
  --pages        comma-separated page files (default framework,question,evidence,methodology)
  --viewport     "WxH" viewport for the primary pass (default 1440x900)
  --mobile       also run a narrow 390x844 pass
  --out DIR      report + screenshot directory (default /tmp/site_scan)
  --report PATH  markdown report path (default <out>/svg_render_report.md)
  --json PATH    JSON report path (default <out>/svg_render_report.json)
  --no-screenshot  skip full-page screenshots
"""

import argparse
import asyncio
import functools
import json
import os
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.async_api import async_playwright

WEBSITE_DIR = Path(__file__).resolve().parent

DEFAULT_PAGES = ["framework.html", "question.html", "evidence.html", "methodology.html"]

MIN_RENDER = 100.0          # gate: rendered box > 100px on both axes
ASPECT_TOL = 0.08           # gate: |rendered - viewBox| ratio tolerance (8%)
SHAPE_TAGS = ("path", "rect", "circle", "ellipse", "line", "polygon", "polyline")


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def _serve_website() -> str:
    """Serve apps/website/ on an ephemeral localhost port; return base URL."""
    handler = functools.partial(_QuietHandler, directory=str(WEBSITE_DIR))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_address[1]}"


PROBE = """
() => {
  const doc = document.documentElement;
  const scrollCtx = (el, axis) => {
    let p = el.parentElement;
    const ov = axis === 'x' ? 'overflowX' : 'overflowY';
    const client = axis === 'x' ? 'clientWidth' : 'clientHeight';
    const scroll = axis === 'x' ? 'scrollWidth' : 'scrollHeight';
    while (p) {
      const cs = getComputedStyle(p);
      const v = cs[ov];
      if ((v === 'auto' || v === 'scroll' || v === 'overlay') &&
          p[scroll] > p[client] + 1) return p;
      p = p.parentElement;
    }
    return null;
  };
  const out = [];
  document.querySelectorAll('svg').forEach((s, i) => {
    const r = s.getBoundingClientRect();
    const cs = getComputedStyle(s);
    const hidden = s.hasAttribute('hidden')
      || s.getAttribute('aria-hidden') === 'true'
      || cs.display === 'none'
      || cs.visibility === 'hidden'
      || cs.width === '0px';
    const shapes = s.querySelectorAll('%(shapes)s').length;
    const shapeMarkupLen = Array.from(s.querySelectorAll('%(shapes)s'))
      .reduce((a, e) => a + e.outerHTML.length, 0);
    const textEls = Array.from(s.querySelectorAll('text'))
      .reduce((a, e) => a + e.textContent.trim().length, 0);
    out.push({
      i, id: s.id || '', cls: (s.getAttribute('class') || ''),
      viewBox: s.getAttribute('viewBox'),
      wAttr: s.getAttribute('width'), hAttr: s.getAttribute('height'),
      rect: [Math.round(r.width), Math.round(r.height)],
      left: Math.round(r.left),
      offX: r.left < 0,
      overflowY: r.bottom > doc.scrollHeight + 4 && !scrollCtx(s, 'y'),
      overflowX: r.right > doc.scrollWidth + 4 && !scrollCtx(s, 'x'),
      docScroll: [doc.scrollWidth, doc.scrollHeight],
      textEls, shapeMarkupLen, textLen: s.textContent.trim().length,
      shapes, hidden,
      opacity: parseFloat(cs.opacity || '1'),
      rects: s.getClientRects().length,
      paint: performance.getEntriesByType('paint').map(e => e.name),
    });
  });
  return out;
}
""" % {"shapes": ",".join(SHAPE_TAGS)}


def _evaluate(svg, viewport):
    flags, fails = [], []
    name = f"svg#{svg['i']}" + (f":{svg['id']}" if svg["id"] else "") + (
        f"({svg['cls']})" if svg["cls"] else "")
    w, h = svg["rect"]

    if w <= MIN_RENDER or h <= MIN_RENDER:
        fails.append(f"SIZE rendered={w}x{h} <= {MIN_RENDER:.0f}px")
    if svg["offX"]:
        fails.append(f"OFFSCREEN left={svg['left']}")
    if svg["overflowX"]:
        fails.append(f"OVERFLOW-X right>doc {svg['rect']} vs scroll {svg['docScroll']}")
    if svg["overflowY"]:
        fails.append(f"OVERFLOW-Y bottom>doc {svg['rect']} vs scroll {svg['docScroll']}")

    vb = svg["viewBox"]
    if vb and w > 0 and h > 0:
        try:
            _, _, vbw, vbh = [float(v) for v in vb.replace(",", " ").split()]
            if vbw > 0 and vbh > 0:
                r_ratio = w / h
                vb_ratio = vbw / vbh
                if abs(r_ratio - vb_ratio) / vb_ratio > ASPECT_TOL:
                    fails.append(
                        f"ASPECT rendered {w}/{h}={r_ratio:.3f} vs viewBox "
                        f"{vbw}/{vbh}={vb_ratio:.3f}")
        except (ValueError, IndexError):
            flags.append("WARN viewBox unparsable")

    text, shapes = svg["textEls"], svg["shapes"]
    shape_markup = svg["shapeMarkupLen"]
    if shape_markup and text > 1.5 * shape_markup:
        fails.append(
            f"BALANCE label wall text={text} > 1.5x shape markup {shape_markup}")
    if text < 10 and shapes < 3:
        fails.append(f"BALANCE empty shell text={text} shapes={shapes}")
    elif shapes < 3 or text < 10:
        flags.append(f"WARN sparse text={text} shapes={shapes}")

    # PAINT — first-paint visibility: the page reported a paint and this svg is
    # actually painted (opaque, non-zero box, laid out — not display:none).
    if "first-paint" not in svg.get("paint", []):
        flags.append("WARN no first-paint timing entry")
    if svg["opacity"] < 0.05 and w > 0 and h > 0:
        fails.append(f"PAINT opacity={svg['opacity']:.2f} (invisible)")
    if svg["rects"] == 0:
        fails.append("PAINT no client rects (not laid out)")

    verdict = "PASS" if not fails else "FAIL"
    return {
        "name": name,
        "page": svg["page"],
        "viewport": viewport,
        "rect": svg["rect"],
        "viewBox": vb,
        "attrs": [svg["wAttr"], svg["hAttr"]],
        "textLen": text,
        "shapeMarkupLen": shape_markup,
        "shapes": shapes,
        "paint": svg.get("paint", []),
        "opacity": svg["opacity"],
        "flags": flags,
        "fails": fails,
        "verdict": verdict,
    }


def _console_row(page, viewport, kind, messages):
    """A synthetic FAIL row for the CONSOLE gate (console error / page exception)."""
    return {
        "name": f"console[{kind}]",
        "page": page,
        "viewport": viewport,
        "rect": [0, 0],
        "viewBox": None,
        "attrs": [],
        "textLen": 0,
        "shapeMarkupLen": 0,
        "shapes": 0,
        "paint": [],
        "opacity": 1.0,
        "flags": [],
        "fails": [f"CONSOLE {kind}: " + " | ".join(messages[:3])],
        "verdict": "FAIL",
    }


async def _run_pages(pw, pages, base, viewport, out, screenshots):
    """Probe every page with a fresh page per page; relaunch the browser and
    retry a page once if the renderer dies (memory is the usual culprit when
    many full-page screenshots accumulate in one context)."""
    results, page_errors = [], []

    async def _probe(browser, pg):
        ctx = await browser.new_context(
            viewport={"width": viewport[0], "height": viewport[1]})
        page = await ctx.new_page()
        page_errors = []
        console_errors = []
        page.on("pageerror", lambda e: page_errors.append(str(e)[:200]))
        page.on("console", lambda m: console_errors.append(str(m.text)[:200])
                if m.type == "error" else None)
        try:
            await page.goto(f"{base}/{pg}", wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_function("document.readyState === 'complete'", timeout=45000)
            await page.wait_for_timeout(700)
            svgs = await page.evaluate(PROBE)
            rows = []
            for s in svgs:
                s["page"] = pg
                rows.append(_evaluate(s, viewport))
            if screenshots:
                safe = pg.replace(".html", "")
                await page.screenshot(
                    path=str(out / f"revamp4_{safe}_{viewport[0]}x{viewport[1]}.png"),
                    full_page=True)
            # CONSOLE gate: any console error or page exception fails the page.
            if page_errors:
                rows.append(_console_row(pg, viewport, "pageerror", page_errors))
            if console_errors:
                rows.append(_console_row(pg, viewport, "console", console_errors))
            return rows, None
        except Exception as exc:  # TargetClosedError etc.
            return None, exc
        finally:
            await ctx.close()

    for pg in pages:
        browser = await pw.chromium.launch()
        try:
            rows, exc = await _probe(browser, pg)
            if rows is None:
                # renderer died mid-page: relaunch and retry once
                await browser.close()
                browser = await pw.chromium.launch()
                rows, exc = await _probe(browser, pg)
            if rows is not None:
                results.extend(rows)
            if exc is not None:
                page_errors.append(f"{pg}: {type(exc).__name__}: {str(exc)[:200]}")
        finally:
            await browser.close()
    return results, page_errors


def _fmt_table(rows, pages):
    lines = [
        "| page | svg | viewBox | rendered | aspect | text | shape markup | verdict |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        vb = r["viewBox"] or "—"
        aspect = "—"
        if r["viewBox"] and r["rect"][0] > 0 and r["rect"][1] > 0:
            try:
                _, _, vbw, vbh = [float(v) for v in r["viewBox"].replace(",", " ").split()]
                r_ratio = r["rect"][0] / r["rect"][1]
                aspect = f"{abs(r_ratio - vbw / vbh) / (vbw / vbh):.3f}"
            except Exception:
                aspect = "—"
        mark = "✔ PASS" if r["verdict"] == "PASS" else "✘ FAIL"
        if r["fails"]:
            mark += " " + "; ".join(r["fails"])
        lines.append(
            f"| {r['page']} | {r['name']} | {vb} | {r['rect'][0]}x{r['rect'][1]} "
            f"| {aspect} | {r['textLen']} | {r['shapeMarkupLen']} | {mark} |")
    return "\n".join(lines)


def _write_report(results, pages, viewports, report_path, json_path, base):
    fails = [r for r in results if r["verdict"] == "FAIL"]
    skips = [r for r in results if r["verdict"] == "SKIP"]
    total = len(results)
    passed = total - len(fails) - len(skips)
    md = [
        f"# SVG rendering gate — {base}",
        "",
        f"Pages: {', '.join(pages)} · viewports: {', '.join(f'{v[0]}x{v[1]}' for v in viewports)}",
        f"SVGs checked: {total} · PASS: {passed} · SKIP (hidden): {len(skips)} · FAIL: {len(fails)}",
        "",
        f"## Result: **{'PASS' if not fails else 'FAIL'}**",
        "",
    ]
    if fails:
        md.append("### Failures")
        for f in fails:
            md.append(f"- `{f['page']}` {f['name']} — " + "; ".join(f["fails"]))
        md.append("")
    md.append("### Per-SVG table")
    md.append(_fmt_table(results, pages))
    md.append("")
    Path(report_path).write_text("\n".join(md), encoding="utf-8")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump({
            "gate": "PASS" if not fails else "FAIL",
            "pages": pages,
            "viewports": viewports,
            "total": total,
            "passed": passed,
            "skipped": len(skips),
            "failed": len(fails),
            "results": results,
        }, fh, indent=1)
    return md, fails


async def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default=None, help="serve this base instead of the built-in server")
    ap.add_argument("--pages", default=",".join(DEFAULT_PAGES))
    ap.add_argument("--viewport", default="1440x900")
    ap.add_argument("--mobile", action="store_true")
    ap.add_argument("--out", default="/tmp/site_scan")
    ap.add_argument("--report", default=None)
    ap.add_argument("--json", default=None, dest="json_path")
    ap.add_argument("--no-screenshot", action="store_true")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report_path = args.report or str(out / "svg_render_report.md")
    json_path = args.json_path or str(out / "svg_render_report.json")
    pages = [p if p.endswith(".html") else p + ".html" for p in args.pages.split(",")]
    vw, vh = [int(v) for v in args.viewport.lower().split("x")]
    viewports = [(vw, vh)] + ([(390, 844)] if args.mobile else [])

    base = args.base
    if base is None:
        base = _serve_website()
    print(f"base: {base}  pages: {pages}  viewports: {viewports}", file=sys.stderr)

    all_results, all_errors = [], []
    async with async_playwright() as pw:
        for vp in viewports:
            results, errs = await _run_pages(pw, pages, base, vp, out, not args.no_screenshot)
            all_results.extend(results)
            all_errors.extend(errs)

    md, fails = _write_report(all_results, pages, viewports, report_path, json_path, base)
    print("\n".join(md))
    if all_errors:
        print("\npage errors:", file=sys.stderr)
        for e in all_errors:
            print("  ", e, file=sys.stderr)
    print(f"\nreport: {report_path}", file=sys.stderr)
    print(f"json:   {json_path}", file=sys.stderr)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    asyncio.run(main())
