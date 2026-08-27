#!/usr/bin/env python3
"""Mechanical preservation-gate census checker for apps/website/.

Re-counts the incumbent feature census on the CURRENT committed source and
compares every headline count against the baseline artifact
(experiments/results/cap_site_revamp3/incumbent_census.json).

The counts follow the census method definitions verbatim:
  slider                 -> literal input[type=range]
  canvas_host            -> literal <canvas
  chart_construction_site-> literal "new Chart(" expression
  semantic_table         -> literal <table element
  handler_attachment_site-> literal inline on* attr, addEventListener(...),
                            or .onclick assignment
  theme_toggle           -> the shared app.js persisted light/dark control
  data_stat_attr         -> literal data-stat attribute (any key)
  data_stat_fmt_attr     -> literal data-stat-fmt attribute
  data_anal_attr         -> literal data-anal attribute (evidence analysis cells)

Exit code 0 = preservation PASS on every headline axis; 1 = FAIL.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SITE_ROOT = Path(__file__).resolve().parents[1] / "apps" / "website"
BASELINE = (
    Path(__file__).resolve().parents[1]
    / "experiments" / "results" / "cap_site_revamp3" / "incumbent_census.json"
)

HEADLINE_KEYS = [
    "sliders",
    "canvas_hosts",
    "chart_construction_sites",
    "semantic_tables",
    "handler_attachment_sites",
    "theme_toggles",
    "data_stat_literal_attributes",
    "data_stat_unique_markup_keys",
    "data_stat_fmt_literal_attributes",
    "data_stat_supported_keys",
    "data_anal_literal_attributes",
    "data_anal_unique_keys",
]

SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script>", re.DOTALL)
STYLE_RE = re.compile(r"<style\b[^>]*>.*?</style>", re.DOTALL)

PAGES = [
    "index.html",
    "framework.html",
    "evidence.html",
    "story.html",
    "methodology.html",
    "accelerator.html",
    "databricks.html",
    "glossary.html",
    "question.html",
]

ONATTR_RE = re.compile(r"\son\w+\s*=")
ADDEVENT_RE = re.compile(r"\.addEventListener\s*\(")
ONCLICK_ASSIGN_RE = re.compile(r"\.onclick\s*=")


def count_site() -> dict:
    counts = {
        "sliders": 0,
        "canvas_hosts": 0,
        "chart_construction_sites": 0,
        "semantic_tables": 0,
        "handler_attachment_sites": 0,
        "theme_toggles": 0,
        "data_stat_literal_attributes": 0,
        "data_stat_fmt_literal_attributes": 0,
        "data_anal_literal_attributes": 0,
    }
    stat_keys: set[str] = set()
    anal_keys: set[str] = set()

    for page in PAGES:
        html = (SITE_ROOT / page).read_text(encoding="utf-8")
        counts["sliders"] += len(re.findall(r"<input[^>]*type=[\"']range[\"']", html))
        counts["canvas_hosts"] += html.count("<canvas")
        counts["chart_construction_sites"] += html.count("new Chart(")
        counts["semantic_tables"] += len(re.findall(r"<table\b", html))
        counts["handler_attachment_sites"] += len(ONATTR_RE.findall(html))
        counts["handler_attachment_sites"] += len(ADDEVENT_RE.findall(html))
        counts["handler_attachment_sites"] += len(ONCLICK_ASSIGN_RE.findall(html))
        # data-stat/data-anal: count only literal markup attributes (census method:
        # JS string-template rows such as evidence.html's ci95 cells are reported
        # separately as dynamic wiring, never as literal markup attributes).
        markup = SCRIPT_RE.sub("", html)
        markup = STYLE_RE.sub("", markup)
        counts["data_stat_literal_attributes"] += len(re.findall(r"data-stat=", markup))
        counts["data_stat_fmt_literal_attributes"] += len(re.findall(r"data-stat-fmt=", markup))
        counts["data_anal_literal_attributes"] += len(re.findall(r"data-anal=", markup))
        stat_keys.update(re.findall(r"data-stat=[\"']([^\"']+)", markup))
        anal_keys.update(re.findall(r"data-anal=[\"']([^\"']+)", markup))

    app_js = (SITE_ROOT / "app.js").read_text(encoding="utf-8")
    counts["handler_attachment_sites"] += len(ADDEVENT_RE.findall(app_js))
    counts["handler_attachment_sites"] += len(ONCLICK_ASSIGN_RE.findall(app_js))
    if "ai-finops-theme" in app_js and "classList" in app_js and "localStorage" in app_js:
        counts["theme_toggles"] = 1

    counts["data_stat_unique_markup_keys"] = len(stat_keys)
    counts["data_anal_unique_keys"] = len(anal_keys)
    counts["data_stat_supported_keys"] = len(
        re.findall(r"^\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]:\s*function\b", app_js, re.MULTILINE)
    )
    return counts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--baseline",
        default=str(BASELINE),
        help="path to the incumbent census JSON baseline",
    )
    ap.add_argument(
        "--json", action="store_true", help="emit machine-readable PASS/FAIL JSON"
    )
    ap.add_argument(
        "--label", default="", help="increment label for the log line"
    )
    args = ap.parse_args()

    baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    current = count_site()

    rows = []
    all_pass = True
    for key in HEADLINE_KEYS:
        want = baseline["site_totals"].get(key)
        got = current.get(key, 0)
        ok = want is not None and got >= want
        all_pass = all_pass and ok
        rows.append({"feature": key, "baseline": want, "current": got, "pass": ok})

    if args.json:
        payload = {
            "label": args.label or None,
            "pass": all_pass,
            "baseline_sha": baseline.get("scope", {}).get("current_checkout_sha"),
            "rows": rows,
        }
        print(json.dumps(payload, indent=2))
        return 0 if all_pass else 1

    print(f"site census check — {args.label or 'no label'}")
    for r in rows:
        mark = "PASS" if r["pass"] else "FAIL"
        print(
            f"  {mark:4s} {r['feature']:34s} baseline={r['baseline']!s:>4s} "
            f"current={r['current']!s:>4s}"
        )
    print("RESULT:", "PASS" if all_pass else "FAIL")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
