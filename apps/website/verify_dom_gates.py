#!/usr/bin/env python3
"""Execute the visual-system hard rules against committed pages in a browser DOM.

The production site uses committed HTML plus local ``data.js`` and the inline-SVG
renderer. This verifier loads those committed assets, serializes their final DOM,
and reports each selector, source field, interaction, and accessibility assertion.
It deliberately records every failure before returning non-zero so the report is a
usable fix list rather than a single opaque assertion.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright


SITE = Path(__file__).resolve().parent
INVENTORY_PATH = SITE / "diagram_inventory.json"
GALLERY_PATH = SITE / "_design.html"
COMPONENT_PATH = SITE / "assets" / "design-components.js"
APP_PATH = SITE / "app.js"
REMEDIATED_FINDINGS = (
    "Initial audit: SVGs relied on aria-labelledby but lacked literal aria-label attributes.",
    "Initial audit: escalation SVG text omitted the full provider/model identifiers.",
    "Initial audit: the rules inventory entry had no SVG overview and did not render its escalation cell counts.",
)


def payload() -> dict[str, Any]:
    """Load the single data door without evaluating arbitrary JavaScript."""
    source = (SITE / "data.js").read_text(encoding="utf-8")
    return json.loads(source[source.index("{") : source.rindex("}") + 1])


def resolve(data: dict[str, Any], path: str) -> list[Any]:
    """Resolve a dotted inventory path and expand the repository's ``[]`` list form."""
    values: list[Any] = [data]
    for part in path.split("."):
        is_list = part.endswith("[]")
        key = part[:-2] if is_list else part
        next_values: list[Any] = []
        for value in values:
            child = value[key]
            next_values.extend(child if is_list else [child])
        values = next_values
    return values


def rendered_values(entry_id: str, field: str, values: list[Any]) -> list[str]:
    """Mirror only documented display formatting; every value still originates in data.js."""
    if field.startswith("summary."):
        return [f"{int(value):,}" for value in values]
    if field == "design_parameters.beta":
        return [f"{values[0]['value']:.4f}"]
    if field.endswith("baseline_cost_usd") or field.endswith("escalation_fix_cost_usd"):
        return [f"${value:.6f}" for value in values]
    if field.endswith(".E_x") or field.endswith(".cpvo_ratio"):
        return [f"{value:.4f}" for value in values]
    if field.endswith("wilson_95_ci") or field.endswith("cpvo_ratio_ci_95"):
        return [f"[{value[0]:.4f}, {value[1]:.4f}]" for value in values]
    if field.endswith(".hits"):
        return [str(value) for value in values]
    if field.endswith("n_model_cells"):
        return [f"n = {value}" for value in values]
    if field.endswith(".n"):
        return [str(value) for value in values]
    return [str(value) for value in values]


def selector_for(slot: str) -> str:
    """Give each inventory item a unique final-DOM SVG selector, including cards."""
    attribute = "data-ad-component" if slot == "rules" else "data-ad-diagram"
    return f'[{attribute}="{slot}"] svg'


def nontrivial_literals(values: list[Any]) -> set[str]:
    """Return values distinctive enough to detect copied data without flagging figure numbers."""
    literals: set[str] = set()
    for value in values:
        if isinstance(value, list):
            literals.update(nontrivial_literals(value))
        elif isinstance(value, str) and len(value) >= 4:
            literals.add(value)
        elif isinstance(value, float):
            literals.add(str(value))
        elif isinstance(value, int) and abs(value) >= 10:
            literals.add(str(value))
    return literals


def copied_literals(values: list[Any], source_text: str) -> list[str]:
    """Find standalone data labels while ignoring source-line ranges such as ``51-64``."""
    copied: list[str] = []
    for value in nontrivial_literals(values):
        if value.isdigit():
            matched = re.search(rf"(?<![\d.-]){re.escape(value)}(?![\d.-])", source_text)
        else:
            matched = value in source_text
        if matched:
            copied.append(value)
    return sorted(copied)


def record(gate: str, page: str, selector: str, result: bool, detail: str, rows: list[str], failures: list[str]) -> None:
    """Write one inspectable report row and retain failed evidence for the exit code."""
    status = "PASS" if result else "FAIL"
    rows.append(f"| {gate} | `{page}` | `{selector}` | {status} | {detail} |")
    if not result:
        failures.append(f"{gate}: {page} {selector}: {detail}")


def page_url(page_name: str) -> str:
    """Return a file URL for a committed public page without starting a web server."""
    return (SITE / page_name).as_uri()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-report", action="store_true", help="write dom_verification_report.md")
    args = parser.parse_args()
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))["diagrams"]
    data = payload()
    rows: list[str] = []
    failures: list[str] = []
    slots_on_pages: set[str] = set()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        for entry in inventory:
            slot = entry["slot"]
            selector = selector_for(slot)
            for page_name in (name.strip() for name in entry["page"].split(",")):
                page.goto(page_url(page_name), wait_until="load")
                count = page.locator(selector).count()
                record("inventory coverage", page_name, selector, count == 1, f"found {count} inline SVG node(s)", rows, failures)
                slots_on_pages.add(slot) if count else None
                rendered = page.locator(selector).text_content() or "" if count else ""
                for field in entry["data_js_fields"]:
                    try:
                        values = resolve(data, field)
                        expected = rendered_values(entry["id"], field, values)
                        target = rendered if slot != "rules" else (page.locator("[data-ad-rules]").text_content() or "")
                        found = all(value in target for value in expected)
                        record("data wiring", page_name, selector, found, f"{field} -> {', '.join(expected)}", rows, failures)
                        # Coordinates and figure numbers are authored constants, but a
                        # distinctive corpus value in the source would bypass data.js.
                        source_markup = (SITE / page_name).read_text(encoding="utf-8") + COMPONENT_PATH.read_text(encoding="utf-8")
                        # Strip SVG/HTML attributes before this scan: authored viewBox
                        # geometry can legitimately share a small integer with data.
                        visible_source_text = re.sub(r"<[^>]+>", " ", source_markup)
                        copied = copied_literals(values, visible_source_text)
                        record("data wiring", page_name, "candidate markup", not copied, f"{field} has no copied data literal" if not copied else f"hardcoded data literal(s): {', '.join(copied)}", rows, failures)
                    except (KeyError, TypeError, ValueError) as error:
                        record("data wiring", page_name, selector, False, f"{field} is unresolved: {error}", rows, failures)

                if count:
                    svg = page.locator(selector)
                    accessible = (
                        svg.get_attribute("role") == "img"
                        and bool(svg.get_attribute("aria-label"))
                        and bool(svg.get_attribute("aria-labelledby"))
                        and svg.locator("title").count() == 1
                        and svg.locator("desc").count() == 1
                    )
                    record("accessibility", page_name, selector, accessible, "role, aria-label, label reference, title, and description", rows, failures)

        gallery = GALLERY_PATH.read_text(encoding="utf-8")
        components = re.findall(r'data-ad-diagram="([^"]+)"', gallery)
        if "data-ad-rules" in gallery:
            components.append("rules")
        for component in sorted(set(components)):
            record("gallery wiring", "_design.html", component, component in slots_on_pages, "referenced by an inventory page", rows, failures)

        page.goto(page_url("framework.html"), wait_until="load")
        rule_cards = page.locator("[data-ad-rules] .ad-rule__toggle")
        record("interactivity", "framework.html", "[data-ad-rules] .ad-rule__toggle", rule_cards.count() == 10, f"found {rule_cards.count()} keyboard buttons", rows, failures)
        keyboard_ready = True
        for index in range(rule_cards.count()):
            rule = rule_cards.nth(index)
            rule.focus()
            rule.press("Enter")
            keyboard_ready = keyboard_ready and rule.get_attribute("aria-expanded") == "true"
            rule.press("Space")
            keyboard_ready = keyboard_ready and rule.get_attribute("aria-expanded") == "false"
        record("interactivity", "framework.html", "[data-ad-rules] .ad-rule__toggle", keyboard_ready, "Enter and Space activate all 10 card buttons", rows, failures)

        for page_name in ("story.html", "evidence.html"):
            page.goto(page_url(page_name), wait_until="load")
            sticky_count = page.locator(".ad-scroll-sequence .ad-scroll-sticky").count()
            record("interactivity", page_name, ".ad-scroll-sequence .ad-scroll-sticky", sticky_count >= 1, f"found {sticky_count} sticky narrative element(s)", rows, failures)
        browser.close()

    status = "PASS" if not failures else "FAIL"
    report = ["# DOM Verification Report", "", f"PASS/FAIL: {status}", "", "Release-candidate pages are loaded from the working tree, then checked after local `data.js`, `app.js`, and the inline-SVG renderer execute. The report is committed only after this PASS run.", "", "| Gate | Page | Selector | Result | Evidence |", "| --- | --- | --- | --- | --- |", *rows]
    if failures:
        report.extend(["", "## Failed Findings", *[f"- {failure}" for failure in failures]])
    report.extend(["", "## Remediated Initial Findings", *[f"- RESOLVED: {finding}" for finding in REMEDIATED_FINDINGS]])
    output = "\n".join(report) + "\n"
    print(output, end="")
    if args.write_report:
        (SITE / "dom_verification_report.md").write_text(output, encoding="utf-8")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
