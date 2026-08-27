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
  CONTRAST WCAG AA — every text fill vs its computed background >= 4.5:1
           (gradient/pattern fills resolve to their stops/paint; a paint-order
           stroke halo counts as the background; the site's default dark theme
           is the review surface)
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
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.async_api import async_playwright

WEBSITE_DIR = Path(__file__).resolve().parent

DEFAULT_PAGES = ["framework.html", "question.html", "evidence.html", "methodology.html"]

MIN_RENDER = 100.0          # gate: rendered box > 100px on both axes
ASPECT_TOL = 0.08           # gate: |rendered - viewBox| ratio tolerance (8%)
CONTRAST_MIN = 4.5          # gate: WCAG AA text fill vs background (every text)
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


PROBE = r"""
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
  // --- CONTRAST machinery (WCAG AA: text fill vs background >= 4.5:1) ---
  const parseColor = (str) => {
    if (!str) return null;
    str = str.trim().toLowerCase();
    if (!str || str === 'none') return null;
    if (str === 'transparent') return [0, 0, 0, 0];
    let m;
    if ((m = str.match(/^rgba?\\(\\s*([\\d.]+)[,\\s]+([\\d.]+)[,\\s]+([\\d.]+)(?:[,\\s/]+([\\d.]+))?\\s*\\)$/))) {
      return [+m[1], +m[2], +m[3], m[4] === undefined ? 1 : Math.min(1, +m[4])];
    }
    if ((m = str.match(/^#([0-9a-f]{6})$/))) {
      return [parseInt(m[1].slice(0,2),16), parseInt(m[1].slice(2,4),16), parseInt(m[1].slice(4,6),16), 1];
    }
    if ((m = str.match(/^#([0-9a-f]{3})$/))) {
      return [parseInt(m[1][0]+m[1][0],16), parseInt(m[1][1]+m[1][1],16), parseInt(m[1][2]+m[1][2],16), 1];
    }
    return null;
  };
  const lin = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
  const lum = (c) => 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2]);
  const ratio = (c1, c2) => {
    const a = lum(c1), b = lum(c2), hi = Math.max(a, b), lo = Math.min(a, b);
    return (hi + 0.05) / (lo + 0.05);
  };
  const blend = (fg, alpha, bg) => fg.slice(0,3).map((c, i) => alpha * c + (1 - alpha) * bg[i]);
  const effectiveAlpha = (el) => {
    let a = 1, cur = el;
    while (cur && cur.nodeType === 1) {
      const cs = getComputedStyle(cur);
      a *= (parseFloat(cs.opacity) || 1);
      const tag = cur.tagName.toLowerCase();
      if (tag === 'text' || tag === 'tspan') a *= (parseFloat(cs.fillOpacity) || 1);
      if (tag === 'svg') break;
      cur = cur.parentElement;
    }
    return Math.min(1, a);
  };
    const resolvePaint = (el) => {
      const cs = getComputedStyle(el);
      let fill = (cs.fill || (el.getAttribute && el.getAttribute('fill')) || '').trim();
      let alpha = (parseFloat(cs.fillOpacity) || 1) * (parseFloat(cs.opacity) || 1);
      if (!fill || fill === 'none') return null;
      if (fill === 'currentColor') {
        const c = parseColor(cs.color);
        return c ? { colors: [c.slice(0, 3)], alphas: [alpha * (c[3] || 1)] } : null;
      }
      const m = fill.match(/url\\(\\s*["']?#([^)"']+)/);
      if (m) {
        const ref = document.getElementById(m[1]);
        if (ref) {
          const tag = ref.tagName.toLowerCase();
          if (tag === 'lineargradient' || tag === 'radialgradient') {
            const colors = [], alphas = [];
            ref.querySelectorAll('stop').forEach(s => {
              let sc = getComputedStyle(s).stopColor || s.getAttribute('stop-color') || '';
              if (sc === 'currentColor') sc = cs.color;
              const c = parseColor(sc);
              if (!c) return;
              const stopA = (parseFloat(getComputedStyle(s).stopOpacity) || 1) * (c[3] || 1);
              colors.push(c.slice(0, 3));
              alphas.push(alpha * stopA);
            });
            if (colors.length) return { colors, alphas };
            return null;
          }
          if (tag === 'pattern') {
            const ln = ref.querySelector('line,path,rect,circle,ellipse');
            if (ln) {
              const lcs = getComputedStyle(ln);
              const sc = lcs.stroke !== 'none' && lcs.stroke && lcs.stroke !== 'currentColor'
                ? parseColor(lcs.stroke) : null;
              const fc = lcs.fill && lcs.fill !== 'none' && lcs.fill !== 'currentColor'
                ? parseColor(lcs.fill) : null;
              const c = sc || fc;
              if (c) {
                const strokeA = parseFloat(lcs.strokeOpacity) || 1;
                const fillA = parseFloat(lcs.fillOpacity) || 1;
                const paintA = (sc ? strokeA : fillA) * (parseFloat(lcs.opacity) || 1);
                return { colors: [c.slice(0, 3)], alphas: [alpha * paintA] };
              }
            }
            return null;
          }
        }
        return null;
      }
      const c = parseColor(fill);
      return c ? { colors: [c.slice(0, 3)], alphas: [alpha * (c[3] || 1)] } : null;
    };
  const svgBg = (svg) => {
    const bg = getComputedStyle(svg).backgroundColor;
    let c = parseColor(bg);
    if (c && c[3] > 0) return c;
    const pbg = getComputedStyle(document.body).backgroundColor;
    c = parseColor(pbg);
    if (c && c[3] > 0) return c;
    return parseColor('#070A0F');
  };
  const bgBehind = (text) => {
    // paint-order stroke halo: the glyphs sit on the halo colour
    const cs = getComputedStyle(text);
    const po = (cs.paintOrder || '');
    if (po.split(/\\s+/)[0] === 'stroke' && cs.stroke && cs.stroke !== 'none') {
      const sw = parseFloat(cs.strokeWidth || '0');
      const sc = parseColor(cs.stroke);
      if (sc && sw > 0) return { paint: { colors: [sc], alpha: 1 } };
    }
    // nearest shape that paints behind the text: previous siblings first,
    // then ancestors' previous siblings.
    let cur = text;
    while (cur) {
      let sib = cur.previousElementSibling;
      while (sib) {
        const tag = sib.tagName && sib.tagName.toLowerCase();
        const isShape = tag && ['rect','ellipse','circle','path','polygon','polyline'].indexOf(tag) >= 0;
        if (isShape) {
          const p = resolvePaint(sib);
          if (p && p.alpha > 0.1) return { paint: p };
        }
        sib = sib.previousElementSibling;
      }
      const parent = cur.parentElement;
      const tag = parent && parent.tagName ? parent.tagName.toLowerCase() : '';
      const isShape = tag && ['rect','ellipse','circle','path','polygon','polyline'].indexOf(tag) >= 0;
      if (isShape) {
        const p = resolvePaint(parent);
        if (p && p.alpha > 0.1) return { paint: p };
      }
      if (!parent || parent.tagName.toLowerCase() === 'svg') break;
      cur = parent;
    }
    return null;
  };
  const textColor = (t) => {
    const cs = getComputedStyle(t);
    let fill = (cs.fill || t.getAttribute('fill') || '').trim();
    if (fill === 'currentColor') fill = cs.color;
    return parseColor(fill);
  };
  const contrastFor = (svg) => {
    const base = svgBg(svg);
    const fails = [];
    let min = Infinity, n = 0;
    const texts = Array.from(svg.querySelectorAll('text'));
    const extra = Array.from(svg.querySelectorAll('tspan')).filter(s => {
      const a = (s.getAttribute('fill') || '');
      const st = (s.getAttribute('style') || '');
      return a || /fill\\s*:/.test(st);
    });
    texts.concat(extra).forEach(t => {
      const label = t.textContent.trim().slice(0, 32) || '(empty)';
      if (label === '(empty)') return;
      const fg = textColor(t);
      const tAlpha = effectiveAlpha(t);
      if (!fg || fg[3] < 0.5) { fails.push({ t: label, ratio: 0, fg: 'none', bg: '—' }); return; }
      const behind = bgBehind(t);
      const paint = behind ? behind.paint : null;
      const bgCands = [];
      if (paint) {
        (paint.colors || []).forEach((c, i) => {
          bgCands.push(blend(c, (paint.alphas || [1])[i], base));
        });
      } else {
        bgCands.push(base);
      }
      bgCands.forEach(bg => {
        const eff = blend(fg, tAlpha, bg);
        const r = ratio(eff, bg);
        if (r < min) min = r;
        if (r < %(contrast_min)f) fails.push({ t: label, ratio: r, fg: fg.slice(0,3), bg: bg.map(v => Math.round(v)) });
        n++;
      });
    });
    return { min: isFinite(min) ? min : null, fails, n };
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
    const contrast = contrastFor(s);
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
      contrast: { min: contrast.min ? Math.round(contrast.min * 100) / 100 : null,
                  fails: contrast.fails.slice(0, 6), checked: contrast.n },
    });
  });
  return out;
}
""" % {"shapes": ",".join(SHAPE_TAGS), "contrast_min": CONTRAST_MIN}


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

    # CONTRAST — every text fill vs its computed background must clear WCAG AA.
    contrast = svg.get("contrast") or {}
    cfails = contrast.get("fails") or []
    if cfails:
        parts = []
        for f in cfails[:4]:
            parts.append(f"{f['t'][:28]!r}@"
                         + (f"{f['ratio']:.2f}:1" if f["ratio"] else "invisible"))
        fails.append("CONTRAST " + "; ".join(parts))
    elif contrast.get("min") is not None and contrast["min"] < CONTRAST_MIN:
        fails.append(f"CONTRAST min {contrast['min']:.2f}:1 < {CONTRAST_MIN:.1f}:1")

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
        "contrast": contrast.get("min"),
        "contrastChecked": contrast.get("checked"),
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
        "contrast": None,
        "contrastChecked": 0,
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
        "| page | svg | viewBox | rendered | aspect | text | shape markup | contrast | verdict |",
        "|---|---|---|---|---|---|---|---|---|",
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
        contrast = "—" if r["contrast"] is None else f"{r['contrast']:.2f}:1"
        mark = "✔ PASS" if r["verdict"] == "PASS" else "✘ FAIL"
        if r["fails"]:
            mark += " " + "; ".join(r["fails"])
        lines.append(
            f"| {r['page']} | {r['name']} | {vb} | {r['rect'][0]}x{r['rect'][1]} "
            f"| {aspect} | {r['textLen']} | {r['shapeMarkupLen']} | {contrast} | {mark} |")
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
