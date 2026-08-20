"""Signal-registry reconciliation tests (refactor-repair Debt-3).

Before the registry, "measured" was split-brained: ``experiment_spec.py`` declared ``confidence``
measured [H] while the routing vocabulary (``step_routing.py``/``signal_store.py``) still
described it as "unmeasured". The registry is now the single source of truth, and these tests
pin (a) the registry's own facts, (b) that the routing vocabulary *derives* from it — so the two
sides can never disagree again — and (c) that no reconciliation site calls a measured signal
"unmeasured".
"""

from __future__ import annotations

from pathlib import Path

from agentic_dynamics.experiment.experiment_spec import LEDGER_FIELDS
from agentic_dynamics.measurement import signal_registry
from agentic_dynamics.measurement.signal_registry import (
    CASCADE,
    ROUTING,
    is_measured,
    measured_signals,
    reserved_for_other,
    signals_for,
)
from agentic_dynamics.runtime import routing as routing_mod
from agentic_dynamics.runtime.routing import RoutingPreferences, validate_preferences

ROOT = Path(__file__).resolve().parent.parent

#: The four formerly-missing signals the ledger now produces (instrumentation step 3).
FORMERLY_MISSING = (
    "confidence",
    "perturbation_strength",
    "test_executed_success",
    "tokens_answer",
    "tokens_explanation",
)


def test_registry_marks_the_formerly_missing_signals_measured():
    """Every formerly-missing signal is registered as measured (no split-brain)."""
    for name in FORMERLY_MISSING:
        assert signal_registry.get(name) is not None, f"{name} is not registered"
        assert is_measured(name), f"{name} must be registered measured"


def test_confidence_vocabulary_is_the_reconciled_one():
    """The review's exact vocabulary: measured [H], no routing, reserved for cascade."""
    conf = signal_registry.get("confidence")
    assert conf is not None
    assert conf.measured is True
    assert conf.evidence_class == "[H]"
    assert ROUTING not in conf.permitted_consumers
    assert CASCADE in conf.permitted_consumers


def test_registry_is_consistent_with_the_ledger():
    """The formerly-missing measured signals are actual ledger fields."""
    for name in FORMERLY_MISSING:
        assert name in LEDGER_FIELDS, f"{name} is a measured signal but not a ledger field"


def test_routing_vocabulary_derives_from_the_registry():
    """``runtime.routing`` consults the registry — never hand-lists the vocabulary."""
    assert signals_for(ROUTING) == routing_mod.MEASURED_SIGNALS
    assert reserved_for_other(ROUTING) == routing_mod.FORBIDDEN_SIGNALS
    assert frozenset({"confidence"}) == routing_mod.FORBIDDEN_SIGNALS
    assert "confidence" not in routing_mod.MEASURED_SIGNALS
    assert "edge_case_coverage" not in routing_mod.MEASURED_SIGNALS


def test_validate_preferences_calls_confidence_reserved_not_unmeasured():
    """A confidence objective is refused as *reserved*, never as *unmeasured*."""
    prefs = RoutingPreferences.from_dict(
        {"objectives": [{"signal": "confidence", "direction": "minimize", "weight": 1.0}]}
    )
    errors = validate_preferences(prefs)
    assert any("confidence" in e and "reserved" in e for e in errors)
    assert all("unmeasured" not in e for e in errors)


def test_edge_case_coverage_is_genuinely_unmeasured():
    """The one genuinely-unmeasured signal is registered as such."""
    assert signal_registry.get("edge_case_coverage").measured is False
    assert "edge_case_coverage" in signal_registry.unmeasured_signals()
    assert "confidence" not in signal_registry.unmeasured_signals()


def test_no_module_calls_a_measured_signal_unmeasured():
    """No reconciliation site describes a registry-measured signal as "unmeasured".

    The split-brain lived in the routing vocabulary + the signal store; both now derive from
    the registry. This scan asserts the residual is clean: no line in those surfaces names a
    measured signal and calls it "unmeasured" (the value convention "``None`` = unmeasured"
    lives elsewhere and is not a signal-status claim).
    """
    measured = measured_signals()
    sites = [
        ROOT / "src/agentic_dynamics/runtime/routing.py",
        ROOT / "src/agentic_dynamics/control/step_routing.py",
        ROOT / "src/agentic_dynamics/control/signal_store.py",
    ]
    offenders: list[str] = []
    for path in sites:
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "unmeasured" not in line:
                continue
            for name in measured:
                if name in line:
                    offenders.append(f"{path.relative_to(ROOT)}:{lineno}: {name}")
    assert not offenders, (
        "a reconciliation site still calls a measured signal 'unmeasured':\n"
        + "\n".join(sorted(offenders))
    )
