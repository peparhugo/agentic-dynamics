#!/usr/bin/env python3
"""Browser-level publication gates for the Agentic Dynamics visual system.

The website is intentionally static, so this verifier loads each page through
Playwright and checks its final DOM after ``data.js`` and the inline-SVG renderer
run. It validates coverage, data-door rendering, gallery wiring, keyboard-ready
controls, and the minimum SVG accessibility contract in one reproducible command.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright


SITE = Path(__file__).resolve().parent
INVENTORY_PATH = SITE / "diagram_inventory.json"
GALLERY_PATH = SITE / "_design.html"
COMPONENT_KEYS = {
    "instrument-cycle": "cycle",
    "nxm-problem": "nxm",
    "eight-planes": "planes",
    "one-engine-two-modes": "engine",
    "bounded-autonomy-envelope": "autonomy",
    "cost-curves": "curves",
    "escalation-chain": "escalation",
    "calibration-arc": "calibration",
    "ten-rules-cards": "rules",
}


def data_payload() -> dict[str, Any]:
    """Parse the generated publication payload without evaluating site JavaScript."""
    source = (SITE / "data.js").read_text(encoding="utf-8")
    return json.loads(source[source.index("{") : source.rindex("}") + 1])


def resolve(payload: dict[str, Any], path: str) -> list[Any]:
    """Resolve a dotted inventory field, expanding one ``[]`` list boundary."""
    values: list[Any] = [payload]
    for part in path.split("."):
        list_part = part.endswith("[]")
        key = part[:-2] if list_part else part
        next_values: list[Any] = []
        for value in values:
            child = value[key]
            next_values.extend(child if list_part else [child])
        values = next_values
    return values


def require(condition: bool, message: str, failures: list[str]) -> None:
    """Accumulate every failure so a publication fix has one complete report."""
    if not condition:
        failures.append(message)


def check_rendered_values(page: Any, component: str, payload: dict[str, Any], failures: list[str]) -> None:
    """Assert the human-readable data-door values displayed by each SVG factory."""
    svg_text = "" if component == "rules" else (page.locator(f'[data-ad-diagram="{component}"] svg').text_content() or "")
    summary = payload["summary"]
    expected: dict[str, list[str]] = {
        "cycle": [f'{summary["sessions_total"]:,}', str(summary["canonical_findings"])],
        "nxm": [f'{summary["sessions_total"]:,}', str(summary["canonical_findings"])],
        "planes": [str(summary["variants"])],
        "engine": [f'{summary["sessions_total"]:,}'],
        "autonomy": [str(summary["canonical_findings"])],
        "curves": [f'{payload["design_parameters"]["beta"]["value"]:.4f}'],
        "escalation": ["$0.008949", "$0.102619", "11.4671", "$0.111982", "12.5134"],
        "calibration": ["2 / 3", "[0.2077, 0.9385]", "6 / 9", "9 / 9", "0.7857", "[0.6842, 0.9105]"],
        "rules": [payload["campaigns"]["cap_2b"]["decision_rule"]["decision"]],
    }
    rule_text = page.locator("[data-ad-rules]").text_content() or "" if component == "rules" else ""
    for value in expected[component]:
        require(value in svg_text if component != "rules" else value in rule_text, f"{component}: rendered data value missing: {value}", failures)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-log", action="store_true", help="write visual_system_verification.md beside this script")
    args = parser.parse_args()
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))["diagrams"]
    payload = data_payload()
    failures: list[str] = []
    proof: list[str] = ["# Visual System Verification", "", "PASS/FAIL: PASS", "", "## Diagram Coverage"]
    public_components: set[str] = set()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        for entry in inventory:
            component = COMPONENT_KEYS[entry["id"]]
            pages = [name.strip() for name in entry["page"].split(",")]
            require(entry["status"] == "implemented", f'{entry["id"]}: inventory status is not implemented', failures)
            for field in entry["data_js_fields"]:
                try:
                    require(bool(resolve(payload, field)), f'{entry["id"]}: data.js field is empty: {field}', failures)
                except (KeyError, TypeError):
                    failures.append(f'{entry["id"]}: data.js field is missing: {field}')
            for page_name in pages:
                page.goto((SITE / page_name).as_uri(), wait_until="load")
                if component == "rules":
                    selector = "[data-ad-rules] .ad-rule"
                    require(page.locator(selector).count() == 10, f"{page_name}: rules card count is not 10", failures)
                else:
                    selector = f'[data-ad-diagram="{component}"] svg'
                    require(page.locator(selector).count() == 1, f"{page_name}: {component} SVG is absent from rendered DOM", failures)
                    svg = page.locator(selector)
                    require(svg.get_attribute("role") == "img", f"{page_name}: {component} SVG lacks role=img", failures)
                    require(svg.locator("title").count() == 1 and svg.locator("desc").count() == 1, f"{page_name}: {component} SVG lacks title or desc", failures)
                    require(page.locator(f'[data-ad-diagram="{component}"] figcaption').count() == 1, f"{page_name}: {component} figure lacks caption", failures)
                check_rendered_values(page, component, payload, failures)
                public_components.add(component)
            proof.append(f'- PASS: `{entry["id"]}` on {", ".join(pages)} renders its inline SVG/card and listed data fields.')

        gallery_components = set()
        gallery = GALLERY_PATH.read_text(encoding="utf-8")
        for component in COMPONENT_KEYS.values():
            if f'data-ad-diagram="{component}"' in gallery or component == "rules" and "data-ad-rules" in gallery:
                gallery_components.add(component)
        require(gallery_components <= public_components, f"gallery-only components: {sorted(gallery_components - public_components)}", failures)

        page.goto((SITE / "framework.html").as_uri(), wait_until="load")
        first_rule = page.locator("[data-ad-rules] .ad-rule__toggle").first
        first_rule.click()
        require(first_rule.get_attribute("aria-expanded") == "true", "rule card does not expose expanded state", failures)
        require(page.locator("#ad-rule-01").is_visible(), "rule card detail is not visible after activation", failures)

        page.goto((SITE / "methodology.html").as_uri(), wait_until="load")
        curve = page.locator('[data-ad-diagram="curves"] svg path.curve-computed')
        before = curve.get_attribute("d")
        page.locator("[data-ad-beta]").evaluate("element => { element.value = '0.0050'; element.dispatchEvent(new Event('input', { bubbles: true })); }")
        after = curve.get_attribute("d")
        require(before != after, "beta control does not redraw computed curve", failures)
        require((page.locator("[data-ad-beta-value]").text_content() or "") == "0.0050", "beta control output is not synchronized", failures)
        browser.close()

    proof.extend(["", "## Wiring", f"- PASS: all {len(inventory)} inventory entries are implemented.", f"- PASS: gallery component IDs are referenced by public pages: {', '.join(sorted(public_components))}.", "- PASS: rendered SVGs expose title, description, role, and captions; rule and beta controls respond in the DOM."])
    if failures:
        proof[2] = "PASS/FAIL: FAIL"
        proof.extend(["", "## Failures", *[f"- FAIL: {failure}" for failure in failures]])
    output = "\n".join(proof) + "\n"
    print(output, end="")
    if args.write_log:
        (SITE / "visual_system_verification.md").write_text(output, encoding="utf-8")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
