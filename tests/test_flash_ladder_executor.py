"""Pure-logic tests for the flash-ladder executor (no docker, no cells)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location(
    "run_flash_ladder", _REPO_ROOT / "scripts" / "run_flash_ladder.py"
)
assert _SPEC is not None and _SPEC.loader is not None
mod = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = mod  # dataclasses resolve the defining module by name
_SPEC.loader.exec_module(mod)


def test_assignment_table_is_the_preregistered_4x3_order():
    plan = mod.build_cell_plan()
    assert [p.cell_id for p in plan] == [
        "C0-r1", "C0-r2", "C0-r3",
        "C1-r1", "C1-r2", "C1-r3",
        "C2-r1", "C2-r2", "C2-r3",
        "C3-r1", "C3-r2", "C3-r3",
    ]
    assert all(p.condition == p.cell_id.split("-")[0] for p in plan)


def test_conditions_carry_the_registered_treatment():
    plan = {p.cell_id: p for p in mod.build_cell_plan()}
    assert plan["C0-r1"].goal == mod.BRIEF
    assert "three materially different internal designs" in plan["C1-r1"].goal
    assert plan["C2-r1"].thinking_budget == 32000
    assert plan["C3-r1"].spec.endswith("flash_ladder_kb.yaml")
    assert plan["C0-r1"].spec.endswith("flash_ladder_bare.yaml")


def test_cell_command_is_sequential_dispatch_with_rails(tmp_path):
    plan = mod.build_cell_plan()[0]
    cmd = mod.cell_command(plan, workdir=tmp_path, deploy_repo=tmp_path)
    assert cmd[:2] == ["docker-compose", "-f"]
    assert "--orchestrator" in cmd
    assert "--no-fact-emit" in cmd
    assert str(tmp_path) in cmd
    assert "--thinking-budget-tokens" not in cmd
    budget = mod.cell_command(
        next(p for p in mod.build_cell_plan() if p.cell_id == "C2-r1"),
        workdir=tmp_path,
        deploy_repo=tmp_path,
    )
    assert budget[budget.index("--thinking-budget-tokens") + 1] == "32000"
