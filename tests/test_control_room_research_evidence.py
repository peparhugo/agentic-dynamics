"""Regression guards for Control Room research provenance artifacts.

The taxonomy is the source-proof layer for downstream catalogs and skills. These
tests keep a support count inseparable from its verbatim, technique-stating quote.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "experiments" / "research" / "control_room"


def _load_builder():
    """Load the deterministic builder without making the research directory a package."""
    spec = importlib.util.spec_from_file_location(
        "control_room_taxonomy_builder", RESEARCH / "build_taxonomy.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _walk_supports(value: object, path: str = "$"):
    """Yield every positive support/support-max evidence block in an artifact."""
    if isinstance(value, dict):
        support = value.get("support", value.get("support_max"))
        if isinstance(support, int) and support > 0:
            yield path, support, value
        for key, child in value.items():
            yield from _walk_supports(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_supports(child, f"{path}[{index}]")


def test_every_positive_support_has_complete_stored_quote_proof() -> None:
    """Every reported support count has one stored evidence record per source."""
    for name in ("taxonomy.json", "catalogs.json", "skills.json"):
        artifact = json.loads((RESEARCH / name).read_text(encoding="utf-8"))
        for path, support, block in _walk_supports(artifact):
            quote_shas = {
                quote.get("sha256")
                for quote in block.get("evidence_quotes", [])
                if isinstance(quote, dict) and quote.get("sha256")
            }
            assert len(quote_shas) == support, f"{name}:{path} support={support} quotes={len(quote_shas)}"


def test_taxonomy_quotes_are_verbatim_and_technique_stating() -> None:
    """A current leaf is PASS only when every counted quote matches its own pattern."""
    builder = _load_builder()
    taxonomy = json.loads((RESEARCH / "taxonomy.json").read_text(encoding="utf-8"))
    for node in taxonomy["nodes"]:
        if "technique" not in node.get("facet", {}):
            continue
        assert node["semantic_verdict"] == "PASS"
        pattern = builder.EVIDENCE_PATTERNS[node["id"]]
        for quote in node["evidence_quotes"]:
            source = json.loads(
                (RESEARCH / "sources" / f"{quote['sha256']}.json").read_text(encoding="utf-8")
            )
            text = quote["quote"]
            assert text in source.get("text", "") or text == source.get("title", "")
            assert builder.re.search(pattern, text, builder.re.I), node["id"]


def test_excluded_techniques_are_not_active_or_downstream_backing() -> None:
    """A technique without a qualifying sentence cannot re-enter a recommendation."""
    taxonomy = json.loads((RESEARCH / "taxonomy.json").read_text(encoding="utf-8"))
    catalogs = json.loads((RESEARCH / "catalogs.json").read_text(encoding="utf-8"))
    skills = json.loads((RESEARCH / "skills.json").read_text(encoding="utf-8"))
    active = {node["id"] for node in taxonomy["nodes"]}
    excluded = {
        entry["node"] for entry in taxonomy["semantic_review"]["excluded_nodes"]
    }
    assert not active & excluded
    backing = {
        row["id"]
        for catalog in catalogs["catalogs"]
        for item in catalog["items"]
        for row in item.get("evidence", {}).get("taxonomy_nodes", [])
    }
    backing.update(
        row["id"]
        for skill in skills["skills"]
        for row in skill.get("evidence", {}).get("backing_nodes", [])
    )
    assert not backing & excluded
