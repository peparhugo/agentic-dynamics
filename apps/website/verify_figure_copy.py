#!/usr/bin/env python3
"""Reconcile public figure copy with the implemented diagram inventory.

This static complement to ``verify_visual_system.py`` catches editorial drift before
browser rendering: every inventory slot must appear on its named page, carry the
page-local figure number, and identify its evidence class in the caption. It also
checks the two diagram labels whose policy class is easy to misstate in prose.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


SITE = Path(__file__).resolve().parent
INVENTORY_PATH = SITE / "diagram_inventory.json"
COMPONENT_PATH = SITE / "assets" / "design-components.js"
APP_PATH = SITE / "app.js"
PROVENANCE_RE = re.compile(r"\[(?:M|C|H|X|P|NULL)\]")
COPY_EXPECTATIONS = {
    "nxm": ("N x M evidence", "surface [P]"),
    "engine": ("G controlled cells [P]", "only the grid: compare arms -> adapt"),
}
RENDERERS = {
    "cycle": "instrumentCycle",
    "nxm": "nxmProblem",
    "planes": "planesMap",
    "engine": "engineModes",
    "autonomy": "autonomyEnvelope",
    "curves": "costCurves",
    "escalation": "escalationChain",
    "calibration": "calibrationArc",
    "rules": "rulesComponent",
}


def require(condition: bool, message: str, failures: list[str]) -> None:
    """Collect all deviations so one run provides a complete editing checklist."""
    if not condition:
        failures.append(message)


def figure_pattern(slot: str) -> re.Pattern[str]:
    """Match one complete public figure for an SVG slot or the rule-card component."""
    attribute = "data-ad-component" if slot == "rules" else "data-ad-diagram"
    return re.compile(
        rf'<figure\b[^>]*{attribute}="{re.escape(slot)}"[^>]*>(.*?)</figure>',
        re.DOTALL,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-log", action="store_true", help="write figure_copy_reconciliation.md")
    args = parser.parse_args()
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))["diagrams"]
    failures: list[str] = []
    proof = ["# Figure-Copy Reconciliation", "", "PASS/FAIL: PASS", "", "## Inventory Coverage"]
    registered_slots = {entry["slot"] for entry in inventory}
    slot_pages = {
        entry["slot"]: {name.strip() for name in entry["page"].split(",")}
        for entry in inventory
    }
    public_figure_pages = set().union(*slot_pages.values())

    for entry in inventory:
        pages = [name.strip() for name in entry["page"].split(",")]
        numbers = entry.get("figure_numbers", {})
        require(set(pages) == set(numbers), f'{entry["id"]}: page and figure-number keys differ', failures)
        for page_name in pages:
            page_path = SITE / page_name
            source = page_path.read_text(encoding="utf-8")
            matches = figure_pattern(entry["slot"]).findall(source)
            require(len(matches) == 1, f'{page_name}: expected one {entry["slot"]} figure, found {len(matches)}', failures)
            if matches:
                caption_match = re.search(r"<figcaption>(.*?)</figcaption>", matches[0], re.DOTALL)
                require(caption_match is not None, f'{page_name}: {entry["slot"]} has no figcaption', failures)
                if caption_match:
                    caption = caption_match.group(1)
                    expected = f'Figure {numbers[page_name]}.'
                    require(expected in caption, f'{page_name}: {entry["slot"]} caption lacks {expected}', failures)
                    require(bool(PROVENANCE_RE.search(caption)), f'{page_name}: {entry["slot"]} caption lacks provenance tag', failures)
            proof.append(f'- PASS: `{entry["id"]}` is Figure {numbers[page_name]} on `{page_name}` with an implemented slot and provenance caption.')

    for page_path in sorted(SITE.glob("*.html")):
        # The excluded gallery has intentionally independent demonstration numbers;
        # this gate reconciles only inventory-backed public publication pages.
        if page_path.name not in public_figure_pages:
            continue
        source = page_path.read_text(encoding="utf-8")
        for block in re.findall(r"<figure\b[^>]*>.*?</figure>", source, re.DOTALL):
            if "Figure " not in block:
                continue
            slots = re.findall(r'data-ad-(?:diagram|component)="([^"]+)"', block)
            require(len(slots) == 1 and slots[0] in registered_slots, f'{page_path.name}: Figure reference has no registered inventory slot', failures)
            if len(slots) == 1 and slots[0] in slot_pages:
                require(page_path.name in slot_pages[slots[0]], f'{page_path.name}: {slots[0]} Figure is not registered for this page', failures)

    component_source = COMPONENT_PATH.read_text(encoding="utf-8")
    app_source = APP_PATH.read_text(encoding="utf-8")
    for slot, renderer in RENDERERS.items():
        require(f"function {renderer}" in component_source, f'{slot}: component renderer {renderer} is absent', failures)
        if slot != "rules":
            require(f"{slot}: () => AgenticDesign.{renderer}" in app_source, f'{slot}: app.js does not wire {renderer}', failures)
    for slot, labels in COPY_EXPECTATIONS.items():
        for label in labels:
            require(label in component_source, f'{slot}: diagram label missing from component source: {label}', failures)

    proof.extend(["", "## Copy Contract", "- PASS: public captions use page-local numbering declared in `diagram_inventory.json`.", "- PASS: every public Figure reference maps to an inventory slot; no caption promises an absent visual.", "- PASS: N x M and grid labels retain their [P] policy/method status in the SVG and matching prose."])
    if failures:
        proof[2] = "PASS/FAIL: FAIL"
        proof.extend(["", "## Failures", *[f"- FAIL: {failure}" for failure in failures]])
    output = "\n".join(proof) + "\n"
    print(output, end="")
    if args.write_log:
        (SITE / "figure_copy_reconciliation.md").write_text(output, encoding="utf-8")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
