"""Solution divergence measurement — did the model produce a different answer?

Replaces text-similarity-based escape with output-based divergence:
did the model build a structurally different solution from baseline?

Grit operational definition:
    Grit(s) = P(test_executed_success | perturbation_strength=s)
    Grit retention: R(s) = G(s) / G(0)
    Grit AUC: area under outcome-retention curve
    Recovery premium: ΔC = C(successful_perturbed) / C(successful_baseline)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BasinMetrics:
    """How did the model's output diverge from baseline under perturbation?

    Basin escape is a behavioral measure — it describes divergence from
    baseline solution patterns. It may or may not correlate with robustness
    (Grit). Escape is explanatory; correctness is the primary endpoint.
    """

    perturbation_strength: float = 0.0
    perturbation_operator: str = ""
    perturbation_class: str = "semantic"

    # Solution divergence (output-based, not text-based)
    architecture_divergence: float = 0.0   # different tech choices?
    structure_divergence: float = 0.0      # different code structure?
    novelty_score: float = 0.0             # overall novelty vs baseline
    escape_score: float = 0.0              # composite divergence

    # Resource cost
    total_tokens: int = 0
    reasoning_tokens: int = 0
    thinking_ratio: float = 0.0
    cost_usd: float = 0.0
    estimated_energy_j: float = 0.0

    # Outcome
    correctness: float = 0.0
    constraints_met: int = 0
    constraints_total: int = 0
    lines_of_code: int = 0

    # Quality metric — the one that matters
    quality_per_dollar: float = 0.0
    quality_per_joule: float = 0.0

    # Sonar differential quality (optional — available when sonar-scanner runs)
    sonar_analyzed: bool = False
    sonar_bugs_delta: int = 0
    sonar_vulnerabilities_delta: int = 0
    sonar_code_smells_delta: int = 0
    sonar_cognitive_complexity_delta: int = 0
    sonar_complexity_delta: int = 0
    sonar_duplication_delta: float = 0.0
    sonar_maintainability_delta: int = 0
    sonar_reliability_delta: int = 0
    sonar_security_delta: int = 0
    sonar_baseline_bugs: int = 0
    sonar_baseline_smells: int = 0
    sonar_perturbed_bugs: int = 0
    sonar_perturbed_smells: int = 0

    # Verdict
    converged_back: bool | None = None
    verdict: str = ""

    model: str = ""
    task: str = ""
    run_id: str = ""

    def get_verdict(self) -> str:
        c = self.perturbation_class
        if self.escape_score > 0.5:
            if c == "semantic":
                return "diverged — semantic perturbation caused unnecessary output variance"
            return "escaped — model produced genuinely novel solution (expected for manifold class)"
        elif self.escape_score > 0.2:
            return "partial — slight output divergence, approach similar to baseline"
        else:
            if c == "semantic":
                return "stable — semantic perturbation handled correctly, output matches baseline"
            return "captured — model returned to baseline output despite unfamiliar perturbation"

    def to_dict(self) -> dict[str, Any]:
        return {
            "perturbation_strength": self.perturbation_strength,
            "perturbation_operator": self.perturbation_operator,
            "perturbation_class": self.perturbation_class,
            "architecture_divergence": round(self.architecture_divergence, 4),
            "structure_divergence": round(self.structure_divergence, 4),
            "novelty_score": round(self.novelty_score, 4),
            "escape_score": round(self.escape_score, 4),
            "total_tokens": self.total_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "thinking_ratio": round(self.thinking_ratio, 4),
            "cost_usd": self.cost_usd,
            "estimated_energy_j": round(self.estimated_energy_j, 2),
            "correctness": round(self.correctness, 4),
            "constraints_met": self.constraints_met,
            "constraints_total": self.constraints_total,
            "lines_of_code": self.lines_of_code,
            "quality_per_dollar": round(self.quality_per_dollar, 2),
            "quality_per_joule": round(self.quality_per_joule, 4),
            "sonar_analyzed": self.sonar_analyzed,
            "sonar_bugs_delta": self.sonar_bugs_delta,
            "sonar_vulnerabilities_delta": self.sonar_vulnerabilities_delta,
            "sonar_code_smells_delta": self.sonar_code_smells_delta,
            "sonar_cognitive_complexity_delta": self.sonar_cognitive_complexity_delta,
            "sonar_complexity_delta": self.sonar_complexity_delta,
            "sonar_duplication_delta": round(self.sonar_duplication_delta, 1),
            "sonar_maintainability_delta": self.sonar_maintainability_delta,
            "sonar_reliability_delta": self.sonar_reliability_delta,
            "sonar_security_delta": self.sonar_security_delta,
            "sonar_baseline_bugs": self.sonar_baseline_bugs,
            "sonar_baseline_smells": self.sonar_baseline_smells,
            "sonar_perturbed_bugs": self.sonar_perturbed_bugs,
            "sonar_perturbed_smells": self.sonar_perturbed_smells,
            "converged_back": self.converged_back,
            "verdict": self.get_verdict(),
            "model": self.model,
            "task": self.task,
            "run_id": self.run_id,
        }


def measure_basin_escape(
    baseline_code: str,
    perturbed_code: str,
    baseline_correctness: float,
    perturbed_correctness: float,
    baseline_constraints_met: int,
    perturbed_constraints_met: int,
    baseline_loc: int,
    perturbed_loc: int,
    *,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    reasoning_tokens: int = 0,
    perturbation_strength: float = 0.5,
    perturbation_operator: str = "",
    perturbation_class: str = "semantic",
    model: str = "",
    task: str = "",
    run_id: str = "",
    cost_usd: float | None = None,
    sonar_diff: dict[str, Any] | None = None,
    constraint_count: int | None = None,
) -> BasinMetrics:
    """Measure how much the model's output diverged from baseline.

    Uses output-based metrics instead of text similarity:
    - Architecture divergence: did the model choose different technologies?
    - Structure divergence: is the code organized differently?
    - Novelty: overall structural difference from baseline output

    Args:
        baseline_code: The unperturbed model's code output.
        perturbed_code: The perturbed model's code output.
        baseline_correctness: Correctness score for baseline.
        perturbed_correctness: Correctness score for perturbed run.
        baseline_constraints_met: Number of constraints baseline satisfied.
        perturbed_constraints_met: Number of constraints perturbed satisfied.
        baseline_loc: Lines of code in baseline.
        perturbed_loc: Lines of code in perturbed run.
        prompt_tokens: Input tokens consumed.
        completion_tokens: Output tokens produced.
        reasoning_tokens: Hidden reasoning tokens.
        perturbation_strength: Perturbation magnitude.
        perturbation_operator: Which operator was applied.
        perturbation_class: "manifold" or "semantic".
        model: Model identifier.
        task: Task description.
        run_id: Run identifier.
    """
    m = BasinMetrics()
    m.perturbation_strength = perturbation_strength
    m.perturbation_operator = perturbation_operator
    m.perturbation_class = perturbation_class
    m.model = model
    m.task = task
    m.run_id = run_id

    # Architecture divergence: detect technology stack differences
    m.architecture_divergence = _architecture_divergence(baseline_code, perturbed_code)

    # Structure divergence: detect code organization differences
    m.structure_divergence = _structure_divergence(baseline_loc, perturbed_loc, baseline_code, perturbed_code)

    # Overall novelty
    m.novelty_score = _compute_novelty(baseline_code, perturbed_code)

    # Composite escape: how much did the output diverge?
    m.escape_score = 0.4 * m.architecture_divergence + 0.3 * m.structure_divergence + 0.3 * m.novelty_score

    if sonar_diff:
        m.sonar_analyzed = True
        m.sonar_bugs_delta = sonar_diff.get("sonar_bugs_delta", 0)
        m.sonar_vulnerabilities_delta = sonar_diff.get("sonar_vulnerabilities_delta", 0)
        m.sonar_code_smells_delta = sonar_diff.get("sonar_code_smells_delta", 0)
        m.sonar_cognitive_complexity_delta = sonar_diff.get("sonar_cognitive_complexity_delta", 0)
        m.sonar_complexity_delta = sonar_diff.get("sonar_complexity_delta", 0)
        m.sonar_duplication_delta = sonar_diff.get("sonar_duplication_delta", 0.0)
        m.sonar_maintainability_delta = sonar_diff.get("sonar_maintainability_delta", 0)
        m.sonar_reliability_delta = sonar_diff.get("sonar_reliability_delta", 0)
        m.sonar_security_delta = sonar_diff.get("sonar_security_delta", 0)
        m.sonar_baseline_bugs = sonar_diff.get("sonar_baseline_bugs", 0)
        m.sonar_baseline_smells = sonar_diff.get("sonar_baseline_smells", 0)
        m.sonar_perturbed_bugs = sonar_diff.get("sonar_perturbed_bugs", 0)
        m.sonar_perturbed_smells = sonar_diff.get("sonar_perturbed_smells", 0)
        nb = min(m.sonar_bugs_delta / max(m.sonar_baseline_bugs, 1), 1.0)
        ns = min(m.sonar_code_smells_delta / max(m.sonar_baseline_smells, 1), 1.0)
        nm = m.sonar_maintainability_delta / 3.0
        sonar_div = 0.4 * nb + 0.3 * ns + 0.3 * nm
        sonar_div = max(0.0, min(sonar_div, 1.0))
        m.escape_score = 0.35 * m.architecture_divergence + 0.25 * m.structure_divergence + 0.20 * m.novelty_score + 0.20 * sonar_div
    m.total_tokens = prompt_tokens + completion_tokens + reasoning_tokens
    m.reasoning_tokens = reasoning_tokens
    m.thinking_ratio = reasoning_tokens / max(m.total_tokens, 1)
    if cost_usd is not None:
        m.cost_usd = cost_usd
    else:
        m.cost_usd = prompt_tokens * 0.27 / 1_000_000 + completion_tokens * 1.10 / 1_000_000 + reasoning_tokens * 0.14 / 1_000_000
    m.estimated_energy_j = (
        prompt_tokens * 0.08 + completion_tokens * 0.23 + reasoning_tokens * 0.47
    )

    m.correctness = perturbed_correctness
    m.constraints_met = perturbed_constraints_met
    m.constraints_total = constraint_count if constraint_count is not None else max(baseline_constraints_met, perturbed_constraints_met)
    m.lines_of_code = perturbed_loc

    # Quality metric — the one that matters
    correctness_ratio = perturbed_correctness / max(baseline_correctness, 0.01)
    m.quality_per_dollar = correctness_ratio / max(m.cost_usd, 0.000001)
    m.quality_per_joule = correctness_ratio / max(m.estimated_energy_j, 0.01)

    m.converged_back = m.escape_score < 0.2

    return m


def _architecture_divergence(baseline: str, perturbed: str) -> float:
    """Detect technology stack differences between two solutions."""
    tech_terms = [
        "react", "vue", "angular", "svelte", "next.js", "nuxt",
        "flask", "django", "fastapi", "express", "spring", "rails",
        "postgresql", "mysql", "mongodb", "redis", "sqlite",
        "docker", "kubernetes", "aws", "gcp", "azure",
        "graphql", "rest", "grpc", "websocket",
        "redis", "kafka", "rabbitmq", "celery",
        "typescript", "javascript", "python", "rust", "go", "java",
        "crdt", "ot", "raft", "paxos",
    ]
    baseline_tech = {t for t in tech_terms if t in baseline.lower()}
    perturbed_tech = {t for t in tech_terms if t in perturbed.lower()}
    union = len(baseline_tech | perturbed_tech)
    if union == 0:
        return 0.0
    intersection = len(baseline_tech & perturbed_tech)
    return 1.0 - (intersection / union)


def _structure_divergence(
    baseline_loc: int, perturbed_loc: int,
    baseline_code: str, perturbed_code: str,
) -> float:
    """Detect code organization differences."""
    scores = []

    # LOC ratio
    if max(baseline_loc, perturbed_loc) > 0:
        loc_ratio = abs(perturbed_loc - baseline_loc) / max(baseline_loc, perturbed_loc, 1)
        scores.append(loc_ratio)

    # Function/class count difference
    def count_defs(code: str) -> int:
        import re
        return len(re.findall(r'^\s*(def |class |func |fn |const |export )', code, re.MULTILINE))
    b_defs = count_defs(baseline_code)
    p_defs = count_defs(perturbed_code)
    if max(b_defs, p_defs) > 0:
        def_ratio = abs(p_defs - b_defs) / max(b_defs, p_defs, 1)
        scores.append(def_ratio)

    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def _compute_novelty(baseline: str, perturbed: str) -> float:
    """Structural novelty via trigram distance."""
    def trigrams(text: str) -> set[str]:
        t = text.lower()
        return {t[i:i + 5] for i in range(len(t) - 4)}
    bt = trigrams(baseline)
    pt = trigrams(perturbed)
    union = len(bt | pt)
    if union == 0:
        return 0.5
    return 1.0 - (len(bt & pt) / union)
