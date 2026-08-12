"""Agent economics measurement instrument — AI FinOps Dynamics.

Success isn't value. Measures how coding-agent cost, correctness,
and outcome value change as specification quality degrades. Uses
controlled perturbation to turn specification quality into an
experimental independent variable, then observes agent behavior,
cost, and correctness under degraded input.

v0.6: Multi-language analysis via tree-sitter. Flash V4 mutation compiler.
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
from .opencode import run_opencode_agentic, AgenticResult, normalize_opencode_event
from .streaming import stream_subprocess, StreamResult
from .claude_adapter import run_claude_agentic, ClaudeStreamAdapter, adapt_usage
from .backends import get_backend_for_model, resolve_backend, run_agentic
from .live import LivePublisher, make_publisher
from .routing import compute_routing, normalize_task, recommend_route, simulate_strategies

# v0.6: Multi-language analysis + mutation compiler + story orchestrator
from .language import (
    LanguageProfile,
    CodebaseAST,
    detect_language,
    parse_codebase,
    get_parser,
    collect_functions,
    collect_imports,
)
from .mutation import (
    MutationArtifact,
    compile_mutation,
    apply_mutation,
    ALL_OPERATORS,
    SPECIFICATION_OPERATORS,
    CODEBASE_OPERATORS,
)
from .story import (
    StoryConfig,
    StoryResult,
    SessionSpec,
    SessionResult,
    run_story,
    save_story_result,
    load_story_result,
    BUILTIN_STORIES,
    PerturbationCondition,
    condition_to_mutations,
)
from .commit_analysis import (
    CommitAnalysis,
    StoryAnalysis,
    analyze_commit,
    analyze_story_worktree,
    compute_ast_diff,
    score_conventions,
)
from .review import (
    CommitReview,
    StoryReview,
    review_commit,
    review_story,
    generate_tests,
    compare_implementations,
)
from .entropy import (
    EntropyProfile,
    compute_entropy,
    entropy_delta,
    entropy_delta_detailed,
)
from .codebase_graph import (
    CodebaseGraph,
    ModuleNode,
    GraphMetrics,
    GraphDelta,
    build_graph,
    compute_metrics,
    compute_graph_delta,
)
from .lsp_diagnostics import (
    LSPDiagnostic,
    LSPReport,
    run_diagnostics,
    diagnostics_delta,
    available_tools,
)

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
    "run_opencode_agentic", "AgenticResult", "normalize_opencode_event",
    "stream_subprocess", "StreamResult",
    "run_claude_agentic", "ClaudeStreamAdapter", "adapt_usage",
    "get_backend_for_model", "resolve_backend", "run_agentic",
    "LivePublisher", "make_publisher",
    "compute_routing", "normalize_task", "recommend_route", "simulate_strategies",
    # v0.6
    "LanguageProfile", "CodebaseAST", "detect_language", "parse_codebase",
    "get_parser", "collect_functions", "collect_imports",
    "MutationArtifact", "compile_mutation", "apply_mutation",
    "ALL_OPERATORS", "SPECIFICATION_OPERATORS", "CODEBASE_OPERATORS",
    "StoryConfig", "StoryResult", "SessionSpec", "SessionResult",
    "run_story", "save_story_result", "load_story_result", "BUILTIN_STORIES",
    "PerturbationCondition", "condition_to_mutations",
    "CommitAnalysis", "StoryAnalysis", "analyze_commit",
    "analyze_story_worktree", "compute_ast_diff", "score_conventions",
    "CommitReview", "StoryReview", "review_commit", "review_story",
    "generate_tests", "compare_implementations",
    "EntropyProfile", "compute_entropy", "entropy_delta", "entropy_delta_detailed",
    "CodebaseGraph", "ModuleNode", "GraphMetrics", "GraphDelta",
    "build_graph", "compute_metrics", "compute_graph_delta",
    "LSPDiagnostic", "LSPReport", "run_diagnostics",
    "diagnostics_delta", "available_tools",
]
