"""Reasoning topology instrument — stochastic perturbation as measurement.

The apparatus for probing how language models explore unfamiliar
reasoning trajectories. Unlike a benchmark (which measures outputs),
this instrument measures *search dynamics*: basin escape rates,
recovery ratios, and attractor strength.

H0: Perturbation type has no effect on exploration behavior.
H1: Manifold perturbations produce systematically higher trajectory
    deviation than semantic perturbations.
"""

# Deprecated: Perturbation, PerturbationOperator — only build_operators/perturb_prompt used by current scripts
from .perturb import build_operators, perturb_prompt
# Deprecated: ReasoningTrajectory, TrajectoryStep, compute_trajectory_distance — not used by current scripts
from .basin import BasinMetrics, measure_basin_escape
# Deprecated: SegmentClassification, classify_trajectory_segments, recovery_token_ratio — not used by current scripts
from .solution import SolutionMetrics, evaluate_solution
from .efficiency import EfficiencyMetrics, compute_efficiency
# Deprecated: StrategyType — not used by current scripts
from .strategy import StrategyReport, classify_strategy
from .game_report import GameReport
from .sonar import SonarMetrics, run_sonar_analysis, compute_sonar_diff, sonar_quality_score
# Deprecated: RecoveryCost, recovery_summary_table — not used by current scripts
from .recovery_cost import compute_recovery_cost
# Deprecated: ConstraintDetection, DetectionReport, detection_summary — not used by current scripts
from .constraint_detection import detect_constraints
# Deprecated: analyze_escape, MarkerProfile, marker_validation_summary — not used by current scripts
from .semantic_validation import analyze_markers, analyze_ast
# Deprecated: EmbeddingClient, extract_session_text — not used by current scripts
from .embeddings import ChromaStore, extract_session_steps
# Deprecated: InstrumentedAdapter, InvokeTimeoutError — old pipeline; run_opencode_agentic replaces adapter.py
# Deprecated: ExperimentConfig, ExperimentRun, ExperimentResult, run_experiment — old pipeline; not used by current scripts
# Deprecated: build_hypothesis, build_methodology, persist_to_lab_book — lab scripts bypass this module
from .graph import Neo4jClient
from .ollama_analyzer import OllamaAnalyzer, load_summary_data
from .opencode_analyzer import OpencodeAnalyzer, REPORTS_DIR
from .opencode import run_opencode_agentic, AgenticResult

__all__ = [
    "build_operators", "perturb_prompt",
    "BasinMetrics", "measure_basin_escape",
    "SolutionMetrics", "evaluate_solution",
    "EfficiencyMetrics", "compute_efficiency",
    "StrategyReport", "classify_strategy",
    "GameReport",
    "SonarMetrics", "run_sonar_analysis", "compute_sonar_diff", "sonar_quality_score",
    "compute_recovery_cost",
    "detect_constraints",
    "analyze_markers", "analyze_ast",
    "ChromaStore", "extract_session_steps",
    "Neo4jClient",
    "OllamaAnalyzer", "load_summary_data",
    "OpencodeAnalyzer", "REPORTS_DIR",
    "run_opencode_agentic", "AgenticResult",
]
