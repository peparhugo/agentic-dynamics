"""Game Report — the complete strategic analysis artifact.

Combines reasoning dynamics, solution quality, and resource efficiency
into a single comprehensive report for each experimental run.

Every experiment is a controlled game. The game report records:
- How the model played (strategy)
- What it built (solution)
- What it cost (efficiency)
- What it means (verdict + recommendation)
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from agentic_dynamics.measurement.basin import BasinMetrics
from agentic_dynamics.measurement.efficiency import EfficiencyMetrics
from agentic_dynamics.measurement.solution import SolutionMetrics
from agentic_dynamics.measurement.strategy import StrategyReport


@dataclass
class GameReport:
    """Complete strategic analysis of an experiment.

    This is THE output of the instrument. Everything else —
    escape scores, recovery ratios, token counts — feeds into
    this report.
    """

    # Experiment identity
    experiment_id: str = ""
    model: str = ""
    task: str = ""
    timestamp: str = ""

    # Perturbation
    operator: str = ""
    perturbation_class: str = ""
    perturbation_strength: float = 0.0
    repetitions: int = 1

    # Dimensions
    reasoning: BasinMetrics | None = None
    solution: SolutionMetrics | None = None
    efficiency: EfficiencyMetrics | None = None

    # Strategy
    strategy: StrategyReport | None = None

    # Per-repetition metrics (for multi-rep runs)
    per_repetition: list[dict[str, Any]] = field(default_factory=list)

    # Artifact paths (code + session transcript)
    artifact_dir: str = ""
    has_code: bool = False
    has_session: bool = False

    # Aggregate scores across repetitions
    mean_escape: float = 0.0
    std_escape: float = 0.0
    mean_correctness: float = 0.0
    std_correctness: float = 0.0
    mean_cost: float = 0.0
    mean_energy: float = 0.0
    mean_thinking_ratio: float = 0.0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "model": self.model,
            "task": self.task[:200],
            "timestamp": self.timestamp,
            "operator": self.operator,
            "perturbation_class": self.perturbation_class,
            "perturbation_strength": self.perturbation_strength,
            "repetitions": self.repetitions,
            "mean_escape": round(self.mean_escape, 4),
            "std_escape": round(self.std_escape, 4),
            "mean_correctness": round(self.mean_correctness, 4),
            "std_correctness": round(self.std_correctness, 4),
            "mean_cost": round(self.mean_cost, 6),
            "mean_energy": round(self.mean_energy, 2),
            "mean_thinking_ratio": round(self.mean_thinking_ratio, 4),
            "strategy": self.strategy.to_dict() if self.strategy else None,
            "reasoning": self.reasoning.to_dict() if self.reasoning else None,
            "solution": self.solution.to_dict() if self.solution else None,
            "efficiency": self.efficiency.to_dict() if self.efficiency else None,
            "per_repetition": self.per_repetition,
        }

    def to_markdown(self) -> str:
        """Render the game report as markdown."""
        s = self.strategy
        r = self.reasoning
        sol = self.solution
        e = self.efficiency

        lines = [
            f"# Game Report: {self.experiment_id}",
            "",
            f"**Model:** {self.model}  |  **Task:** {self.task[:80]}...",
            f"**Operator:** {self.operator} ({self.perturbation_class}, strength={self.perturbation_strength})",
            f"**Repetitions:** {self.repetitions}  |  **Timestamp:** {self.timestamp[:19]}",
            "",
            "---",
            "",
            "> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced",
            "",
            "## Strategy [H]",
            f"**Classification:** {s.strategy.value.upper() if s else 'UNKNOWN'}",
            f"**Score:** {self.strategy.strategy_score:.3f}" if s else "",
        ]

        if s:
            lines += ["", f"**Verdict:** {s.verdict}", "", f"**Recommendation:** {s.recommendation}"]

        lines += [
            "",
            "---",
            "",
            "## Reasoning Dynamics",
        ]
        if r:
            lines += [
                "| Metric | Value |",
                "|--------|-------|",
                f"| Escape score [H] | {r.escape_score:.3f} |",
                f"| Architecture div [H] | {r.architecture_divergence:.3f} |",
                f"| Structure div [H] | {r.structure_divergence:.3f} |",
                f"| Thinking ratio [C] | {r.thinking_ratio:.1%} |",
                (f"| Quality/$ [C] | {r.quality_per_dollar:,.0f} |" if r.quality_per_dollar is not None
                 else "| Quality/$ [C] | n/a (cost uncaptured) |"),
                (f"| Quality/J [C] | {r.quality_per_joule:.4f} |" if r.quality_per_joule is not None
                 else "| Quality/J [C] | n/a (energy uncaptured) |"),
                f"| Converged back [H] | {r.converged_back} |",
            ]
            if self.repetitions > 1:
                lines += [
                    f"| Mean escape (±σ) | {self.mean_escape:.3f} ± {self.std_escape:.3f} |",
                ]

        lines += [
            "",
            "---",
            "",
            "## Solution Quality",
        ]
        if sol:
            lines += [
                "| Metric | Value |",
                "|--------|-------|",
                f"| Correctness | {sol.correctness_score:.0%} ({sol.tests_passed}/{sol.tests_total} tests) {'[M]' if sol.evaluator_independent else '[H]'} |",
                f"| Constraint satisfaction [H] | {sol.constraint_score:.0%} ({sol.constraints_met}/{sol.constraints_total} constraints) |",
                f"| Lines of code [M] | {sol.lines_of_code} |",
                f"| Cyclomatic complexity [C] | {sol.cyclomatic_complexity:.1f} |",
                f"| Code quality [H] | {sol.code_quality_score:.3f} |",
                f"| Novelty vs baseline [H] | {sol.novelty_score:.3f} |",
                f"| **Composite [H]** | **{sol.composite_score:.3f}** |",
            ]
            if self.repetitions > 1:
                lines += [
                    f"| Mean correctness (±σ) | {self.mean_correctness:.3f} ± {self.std_correctness:.3f} |",
                ]

        if sol and sol.sonar_analyzed:
            lines += [
                "",
                "---",
                "",
                "## SonarQube Quality [X]",
                "",
                "| Metric | Value |",
                "|--------|-------|",
                f"| Bugs | {sol.sonar_bugs} |",
                f"| Vulnerabilities | {sol.sonar_vulnerabilities} |",
                f"| Code smells | {sol.sonar_code_smells} |",
                f"| Cognitive complexity | {sol.sonar_cognitive_complexity} |",
                f"| Duplications | {sol.sonar_duplicated_lines_density:.1f}% |",
                f"| Lines of code (NCLOC) | {sol.sonar_ncloc} |",
                f"| Maintainability | {sol.sonar_maintainability_rating} |",
                f"| Reliability | {sol.sonar_reliability_rating} |",
                f"| Security | {sol.sonar_security_rating} |",
                f"| Quality gate | {sol.sonar_quality_gate} |",
                f"| Sonar quality score [C] | {sol.sonar_quality_score:.3f} |",
            ]

        if r and r.sonar_analyzed:
            lines += [
                "",
                "---",
                "",
                "## SonarQube Diff Quality [X]",
                "",
                "**Perturbation quality degradation — how much code quality was lost.**",
                "",
                "| Metric | Baseline | Perturbed | Delta |",
                "|--------|----------|-----------|-------|",
                f"| Bugs | {r.sonar_baseline_bugs} | {r.sonar_perturbed_bugs} | +{r.sonar_bugs_delta} |",
                f"| Code smells | {r.sonar_baseline_smells} | {r.sonar_perturbed_smells} | +{r.sonar_code_smells_delta} |",
                f"| Vulnerabilities | — | — | +{r.sonar_vulnerabilities_delta} |",
                f"| Cognitive complexity | — | — | +{r.sonar_cognitive_complexity_delta} |",
                f"| Duplications | — | — | +{r.sonar_duplication_delta:.1f}% |",
                f"| Maintainability rating | — | — | {_rating_delta_str(r.sonar_maintainability_delta)} |",
                f"| Reliability rating | — | — | {_rating_delta_str(r.sonar_reliability_delta)} |",
                f"| Security rating | — | — | {_rating_delta_str(r.sonar_security_delta)} |",
            ]

        lines += [
            "",
            "---",
            "",
            "## Resource Efficiency",
        ]
        if e:
            lines += [
                "| Metric | Value |",
                "|--------|-------|",
                f"| Prompt tokens [M] | {e.prompt_tokens:,} |",
                f"| Completion tokens [M] | {e.completion_tokens:,} |",
                f"| Reasoning tokens [M] | {e.reasoning_tokens:,} |",
                f"| Cache read tokens [M] | {e.cache_read_tokens:,} |",
                f"| Cache write tokens [M] | {e.cache_write_tokens:,} |",
                f"| **Total tokens** | **{e.total_tokens:,}** |",
                f"| Thinking ratio [C] | {e.thinking_ratio:.1%} |",
                f"| Output efficiency [C] | {e.output_efficiency:.1%} |",
            ]
            cost_label = " [C]" if e.cost_is_estimated else " [M]"
            lines += [
                f"| Input cost{cost_label} | ${e.cost_input_usd:.6f} |",
                f"| Output cost{cost_label} | ${e.cost_output_usd:.6f} |",
                f"| Reasoning cost{cost_label} | ${e.cost_reasoning_usd:.6f} |",
                f"| Cache cost{cost_label} | ${e.cost_cache_usd:.6f} |",
                f"| **Total cost** | **${e.total_cost_usd:.6f}** |",
                f"| **Total energy [X]** | **~{e.total_energy_j:.0f} J** |",
                (f"| Solution density [C] | {e.solution_density:.6f} LOC/tok |"
                 if e.solution_density is not None else "| Solution density [C] | n/a (tokens uncaptured) |"),
                (f"| Correctness/$ [C] | {e.correctness_per_dollar:.0f} |"
                 if e.correctness_per_dollar is not None else "| Correctness/$ [C] | n/a (cost uncaptured) |"),
                (f"| Quality/J [C] | {e.quality_per_joule:.6f} |"
                 if e.quality_per_joule is not None else "| Quality/J [C] | n/a (energy uncaptured) |"),
            ]
            if self.repetitions > 1:
                costs = [rep.get('cost', 0) for rep in self.per_repetition if rep.get('cost') is not None]
                if len(costs) >= 2:
                    std_cost = statistics.stdev(costs)
                    mean_cost = statistics.mean(costs)
                    lines.append(f"| Mean cost (±σ) | ${mean_cost:.6f} ± ${std_cost:.6f} |")
                else:
                    lines.append("| Mean cost (±σ) | Insufficient repetitions for cost CI |")

        # Per-repetition table for multi-rep runs
        if self.per_repetition and len(self.per_repetition) > 1:
            lines += [
                "",
                "---",
                "",
                "## Per-Repetition Breakdown",
                "",
                "| Rep | Escape | Correctness | Thinking% | Cost | Energy | Strategy |",
                "|-----|--------|-------------|-----------|------|--------|----------|",
            ]
            for i, rep in enumerate(self.per_repetition):
                lines.append(
                    f"| {i+1} | {rep.get('escape', 0):.3f} | "
                    f"{rep.get('correctness', 0):.0%} | "
                    f"{rep.get('thinking_ratio', 0):.0%} | "
                    f"${rep.get('cost', 0):.4f} | "
                    f"{rep.get('energy', 0):.0f}J | "
                    f"{rep.get('strategy', '?')} |"
                )

        lines += [
            "",
            "---",
            "",
            "## Headline Metric",
        ]
        if sol and e:
            lines.append(
                f"**Strategy:** {s.strategy.value.upper() if s else '?'}  |  "
                f"**Correctness:** {sol.correctness_score:.0%}  |  "
                f"**Cost:** ${e.total_cost_usd:.4f}  |  "
                f"**Energy:** ~{e.total_energy_j:.0f}J  |  "
                f"**Thinking:** {e.thinking_ratio:.0%}"
            )

        # Artifacts — session transcript + generated code
        if self.artifact_dir and (self.has_code or self.has_session):
            lines += [
                "",
                "---",
                "",
                "## Artifacts",
                "",
                "Raw session transcript and generated source code for independent verification.",
                "",
            ]
            if self.has_session:
                lines.append(f"- [Opencode session transcript](./{self.artifact_dir}/session.jsonl)")
            if self.has_code:
                lines.append(f"- [Generated code](./{self.artifact_dir}/code/)")
            if not self.has_code and self.has_session:
                lines.append("")
                lines.append("*No code output — this session was narration-only.*")

        return "\n".join(lines)


def _rating_delta_str(delta: int) -> str:
    if delta == 0:
        return "unchanged"
    if delta > 0:
        return f"degraded by {delta} levels"
    return f"improved by {abs(delta)} levels"
