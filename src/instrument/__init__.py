"""Reasoning topology instrument — stochastic perturbation as measurement.

The apparatus for probing how language models explore unfamiliar
reasoning trajectories. Unlike a benchmark (which measures outputs),
this instrument measures *search dynamics*: basin escape rates,
recovery ratios, and attractor strength.

H0: Perturbation type has no effect on exploration behavior.
H1: Manifold perturbations produce systematically higher trajectory
    deviation than semantic perturbations.
"""

from .perturb import Perturbation, PerturbationOperator, build_operators, perturb_prompt
from .trajectory import ReasoningTrajectory, TrajectoryStep, compute_trajectory_distance
from .basin import BasinMetrics, measure_basin_escape
from .recovery import SegmentClassification, classify_trajectory_segments, recovery_token_ratio
from .adapter import InstrumentedAdapter, InvokeTimeoutError
from .experiment import ExperimentConfig, ExperimentRun, ExperimentResult, run_experiment
from .lab_book import build_hypothesis, build_methodology, persist_to_lab_book
from .solution import SolutionMetrics, evaluate_solution
from .efficiency import EfficiencyMetrics, compute_efficiency
from .strategy import StrategyReport, StrategyType, classify_strategy
from .game_report import GameReport
from .recovery_cost import RecoveryCost, compute_recovery_cost, recovery_summary_table
from .constraint_detection import ConstraintDetection, DetectionReport, detect_constraints, detection_summary

__all__ = [
    "Perturbation", "PerturbationOperator", "build_operators", "perturb_prompt",
    "ReasoningTrajectory", "TrajectoryStep", "compute_trajectory_distance",
    "BasinMetrics", "measure_basin_escape",
    "SegmentClassification", "classify_trajectory_segments", "recovery_token_ratio",
    "InstrumentedAdapter", "InvokeTimeoutError",
    "ExperimentConfig", "ExperimentRun", "ExperimentResult", "run_experiment",
    "build_hypothesis", "build_methodology", "persist_to_lab_book",
    "SolutionMetrics", "evaluate_solution",
    "EfficiencyMetrics", "compute_efficiency",
    "StrategyReport", "StrategyType", "classify_strategy",
    "GameReport",
    "RecoveryCost", "compute_recovery_cost", "recovery_summary_table",
]
