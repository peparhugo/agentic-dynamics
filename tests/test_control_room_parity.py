"""Feature-parity guard (UX-repair wave, phase ``u5_gate_semantic_parity``).

The browser class ``scripts/verify_control_room_rendering.py --parity`` proves in a real DOM that
every re-housed surface is present, wired to its endpoint, and non-empty. That run needs Chromium,
so CI also needs a fast, browser-free guard that the *inventory* and the *gate's panel map* cannot
drift apart:

1. every record in ``experiments/research/control_room/parity_inventory.json`` is placed on a
   surface in the inventory's own closed palette (the "no silent drops" contract);
2. the gate's ``_check_parity_inventory`` accepts the committed inventory and REJECTS a tampered
   one (so the check is sensitive, not a no-op);
3. every endpoint the gate expects a workbench lens to request is a registered inventory endpoint;
4. the committed parity fixtures supply a payload for every GET endpoint a lens requests, so the
   browser class cannot pass by silently aborting a missing route.

These four invariants are the executable form of ``docs/research/control_room_ia.md`` §14/§15.3.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.fast

ROOT = Path(__file__).resolve().parent.parent
INVENTORY_PATH = ROOT / "experiments" / "research" / "control_room" / "parity_inventory.json"
GATE_PATH = ROOT / "scripts" / "verify_control_room_rendering.py"
PARITY_FIXTURE_PATH = (
    ROOT / "apps" / "control_room" / "verification" / "fixtures" / "parity_endpoints.json"
)


def _load_inventory() -> dict:
    """Load the committed parity inventory (the placement enumeration)."""
    return json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))


def _load_gate():
    """Import the render-gate module by path (it is a script, not a package module)."""
    spec = importlib.util.spec_from_file_location("verify_control_room_rendering", GATE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _normalise(path: str) -> str:
    """Normalise a route/path so ``<session_id>`` and ``<...>`` compare equal."""
    return re.sub(r"<[^>]+>", "<...>", path)


def test_inventory_places_every_record_on_a_palette_surface() -> None:
    """Every item, endpoint and capability names a surface in the closed palette."""
    inventory = _load_inventory()
    palette = set(inventory["surface_palette"])
    for group in ("items", "endpoints", "capabilities"):
        for record in inventory[group]:
            assert record["surface"] in palette, (group, record.get("id"), record["surface"])
    # The inventory's own counts must agree with its arrays (a drift guard).
    assert inventory["summary"]["old_unique_ids"] == len(inventory["items"])
    assert inventory["summary"]["old_routes"] == len(inventory["endpoints"])


def test_gate_inventory_check_is_clean_and_sensitive() -> None:
    """The gate accepts the real inventory and catches a tampered surface."""
    module = _load_gate()
    errors: list[str] = []
    module._check_parity_inventory(_load_inventory(), errors)
    assert errors == [], errors

    tampered = _load_inventory()
    tampered["items"][0]["surface"] = "NOT-A-REAL-SURFACE"
    errors = []
    module._check_parity_inventory(tampered, errors)
    assert errors, "the parity placement check did not detect a bad surface"


def test_every_panel_endpoint_is_a_registered_inventory_endpoint() -> None:
    """A lens may only be expected to call an endpoint the inventory actually lists."""
    module = _load_gate()
    inventory = _load_inventory()
    registered = {
        _normalise(record["id"].split(" ", 1)[1])
        for record in inventory["endpoints"]
        if " " in record["id"]
    }
    missing = sorted(
        path
        for paths in module.PARITY_PANEL_ENDPOINTS.values()
        for path in paths
        if _normalise(path) not in registered
    )
    assert not missing, f"panel endpoints absent from the inventory: {missing}"


def test_parity_fixture_supplies_every_get_lens_endpoint() -> None:
    """The browser parity class has a payload for every GET a lens requests (never a 404 stub)."""
    module = _load_gate()
    raw = json.loads(PARITY_FIXTURE_PATH.read_text(encoding="utf-8"))
    supplied = {key for key in raw if not key.startswith("_")}
    required = {
        path
        for paths in module.PARITY_PANEL_ENDPOINTS.values()
        for path in paths
    }
    missing = sorted(path for path in required if path not in supplied)
    assert not missing, f"parity fixtures missing lens endpoints: {missing}"
