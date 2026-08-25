"""Executable guardrails for the cap_2a shadow-calibration workflow spec.

The generic compiler intentionally does not interpret arbitrary phase prose. These assertions keep
the campaign's load-bearing operational contract from being weakened while the YAML is edited.
"""

from pathlib import Path

from agentic_dynamics.control.context_compiler import validate_spec_fact_contracts
from agentic_dynamics.experiment.compile_experiment import compile_spec
from agentic_dynamics.experiment.experiment_spec import load_spec

ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = ROOT / "workflows" / "repository" / "cap_2a_shadow_calibration.yaml"


def _phase_prompts(spec):
    return {
        str(phase["name"]): str(phase.get("prompt", ""))
        for phase in spec.workflow.params["phases"]
    }


def test_cap_2a_compiles_and_passes_the_real_fact_contract_gate():
    spec = load_spec(SPEC_PATH)
    assert compile_spec(spec).topological_order()
    assert validate_spec_fact_contracts(spec) == []
    assert spec.comparison is None  # 2a is counterfactual; 2b owns the randomized arm compare.


def test_cap_2a_declares_all_phases_and_contract_facts():
    spec = load_spec(SPEC_PATH)
    phases = _phase_prompts(spec)
    assert list(phases) == [
        "p1_wire_graph_client",
        "p2_measure_one_cell",
        "p3_run_shadow_cells",
        "p4_score_hit_rate",
        "p5_verdict",
        "p6_adversarial",
    ]

    gate = next(rule for rule in spec.rules if rule.name == "cap_2a_verifier_gate")
    contract_facts = {req.fact for req in gate.requires_facts}
    assert contract_facts == {
        "sonar_analysis_status",
        "lsp_analysis_status",
        "analysis_revision_matches",
        "changed_symbol_count",
        "ast_parse_coverage",
        "code_change_risk",
        "new_sonar_critical_count",
        "new_lsp_error_count",
        "impacted_symbol_count",
        "changed_symbols_with_tests_ratio",
    }


def test_cap_2a_prompts_preserve_stability_guardrails():
    prompts = _phase_prompts(load_spec(SPEC_PATH))
    assert "graph_status=unavailable" in prompts["p1_wire_graph_client"]
    assert "applied=false" in prompts["p1_wire_graph_client"]
    assert "candidate manifest FIRST" in prompts["p2_measure_one_cell"]
    assert "FORECAST, not measured" in prompts["p2_measure_one_cell"]
    assert "outcome=unknown" in prompts["p3_run_shadow_cells"]
    assert "n_scored" in prompts["p4_score_hit_rate"]
    assert "Wilson 95%" in prompts["p5_verdict"]
    assert "docs/reviews/cap_2a_shadow_calibration_adversary.md" in prompts["p6_adversarial"]
    assert "docs/reviews/cap_2a_shadow_calibration_known_safe.md" in prompts["p6_adversarial"]
