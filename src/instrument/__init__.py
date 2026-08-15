"""Agent economics measurement instrument — AI FinOps Dynamics.

Success isn't value. Measures how coding-agent cost, correctness,
and outcome value change as specification quality degrades. Uses
controlled perturbation to turn specification quality into an
experimental independent variable, then observes agent behavior,
cost, and correctness under degraded input.

v0.6: Multi-language analysis via tree-sitter. Flash V4 mutation compiler.
"""

# Deprecated: Perturbation, PerturbationOperator — only build_operators/perturb_prompt used by current scripts
from .backends import get_backend_for_model, resolve_backend, run_agentic

# Deprecated: ReasoningTrajectory, TrajectoryStep, compute_trajectory_distance — not used by current scripts
from .basin import BasinMetrics, measure_basin_escape
from .claude_adapter import ClaudeStreamAdapter, adapt_usage, run_claude_agentic
from .codebase_graph import (
    CodebaseGraph,
    GraphDelta,
    GraphMetrics,
    ModuleNode,
    build_graph,
    compute_graph_delta,
    compute_metrics,
)
from .commit_analysis import (
    CommitAnalysis,
    StoryAnalysis,
    analyze_commit,
    analyze_story_worktree,
    compute_ast_diff,
    compute_deep_metrics,
    score_conventions,
)

# v1.0: the compiler — spec → DAG
from .compile_experiment import (
    DAG,
    MEASUREMENT_RULES,
    Phase,
    RuleResult,
    SpecError,
    compare_arms,
    compile_spec,
    evaluate_rules,
    experiment_matrix,
    first_pass_quality,
)

# Deprecated: ConstraintDetection, DetectionReport, detection_summary — not used by current scripts
from .constraint_detection import detect_constraints
from .efficiency import EfficiencyMetrics, compute_cost_estimate, compute_efficiency

# Deprecated: EmbeddingClient, extract_session_text — not used by current scripts
from .embeddings import ChromaStore, ChromaStoreError, extract_session_steps, step_doc_id
from .entropy import (
    EntropyProfile,
    compute_entropy,
    entropy_delta,
    entropy_delta_detailed,
)

# v1.0: ExperimentSpec — declarative specs + the requires/produces validator
from .experiment_spec import (
    LEDGER_FIELDS,
    AdaptSpec,
    ComparisonSpec,
    ExperimentSpec,
    Factor,
    MetricSpec,
    RuleSpec,
    StopSpec,
    Workflow,
    WriteupSpec,
    load_spec,
    validate_rules,
    validate_spec,
)
from .game_report import GameReport

# Deprecated: InstrumentedAdapter, InvokeTimeoutError — old pipeline; run_opencode_agentic replaces adapter.py
# Deprecated: ExperimentConfig, ExperimentRun, ExperimentResult, run_experiment — old pipeline; not used by current scripts
# Deprecated: build_hypothesis, build_methodology, persist_to_lab_book — lab scripts bypass this module
from .graph import ALLOWED_EXPANSION_RELS, Neo4jClient

# v1.0: canonical identity + authority contract for the runtime-RAG knowledge base
from .knowledge import (
    EVIDENCE_CLASSES,
    OPERATIONS,
    SCHEMA_VERSION,
    Authority,
    KnowledgeEvent,
    KnowledgeRecord,
    compute_content_hash,
    compute_entity_id,
    compute_knowledge_id,
)

# v0.6: Multi-language analysis + mutation compiler + story orchestrator
from .language import (
    CodebaseAST,
    LanguageProfile,
    collect_functions,
    collect_imports,
    detect_language,
    get_parser,
    parse_codebase,
)
from .live import LivePublisher, make_publisher
from .lsp_diagnostics import (
    LSPDiagnostic,
    LSPReport,
    available_tools,
    diagnostics_delta,
    run_diagnostics,
)
from .mutation import (
    ALL_OPERATORS,
    CODEBASE_OPERATORS,
    SPECIFICATION_OPERATORS,
    MutationArtifact,
    apply_mutation,
    compile_mutation,
)
from .ollama_analyzer import OllamaAnalyzer, load_summary_data
from .opencode import AgenticResult, normalize_opencode_event, run_opencode_agentic
from .opencode_analyzer import REPORTS_DIR, OpencodeAnalyzer
from .perturb import PERTURBATION_CLASSES, build_operators, perturb_prompt, perturbation_class_for

# Deprecated: RecoveryCost, recovery_summary_table — not used by current scripts
from .recovery_cost import compute_recovery_cost
from .review import (
    CommitReview,
    StoryReview,
    compare_implementations,
    generate_tests,
    review_commit,
    review_story,
)
from .routing import compute_routing, normalize_task, recommend_route, simulate_strategies

# Deprecated: analyze_escape, MarkerProfile, marker_validation_summary — not used by current scripts
from .semantic_validation import analyze_ast, analyze_markers

# v1.0: the signal store — measured per-model signals derived from _results_summary.json
from .signal_store import (
    MODEL_ALIASES,
    build_signal_store,
    derive_cache_hit_rate,
    derive_constraint_score,
    load_results,
    normalize_model_id,
)

# Deprecated: SegmentClassification, classify_trajectory_segments, recovery_token_ratio — not used by current scripts
from .solution import SolutionMetrics, evaluate_solution
from .sonar import SonarMetrics, compute_sonar_diff, run_sonar_analysis, sonar_quality_score

# v1.0: per-step routing — preference-scored, cache-aware model selection per workflow step
from .step_routing import (
    FORBIDDEN_SIGNALS,
    MEASURED_SIGNALS,
    ModelSignals,
    Objective,
    RouteState,
    RoutingPreferences,
    StepSelector,
    cache_switch_penalty,
    parse_step_selector,
    resolve_pool,
    route_step,
    validate_preferences,
    validate_step_selector,
    validate_workflow_routing,
)
from .story import (
    BUILTIN_STORIES,
    PerturbationCondition,
    SessionResult,
    SessionSpec,
    StoryConfig,
    StoryResult,
    condition_to_mutations,
    load_story_result,
    run_story,
    save_story_result,
)

# Deprecated: StrategyType — not used by current scripts
from .strategy import StrategyReport, classify_strategy
from .streaming import StreamResult, stream_subprocess
from .supervisor import (
    SUPERVISOR_FLAGS_KEY,
    SUPERVISOR_SESSION_CELLS_KEY,
    normalize_flag,
    register_session_mapping,
)
from .test_runner import run_suite, suite_succeeded

# v1.0: the execute phase — run an agent_task workflow in a worktree
from .workflow_runner import (
    PhaseResult,
    WorkflowRunResult,
    run_workflow,
)

__all__ = [
    "build_operators", "perturb_prompt", "PERTURBATION_CLASSES", "perturbation_class_for",
    "BasinMetrics", "measure_basin_escape",
    "SolutionMetrics", "evaluate_solution",
    "EfficiencyMetrics", "compute_efficiency", "compute_cost_estimate",
    "StrategyReport", "classify_strategy",
    "GameReport",
    "SonarMetrics", "run_sonar_analysis", "compute_sonar_diff", "sonar_quality_score",
    "compute_recovery_cost",
    "detect_constraints",
    "analyze_markers", "analyze_ast",
    "ChromaStore", "extract_session_steps",
    "ChromaStoreError", "step_doc_id",
    "Neo4jClient", "ALLOWED_EXPANSION_RELS",
    "OllamaAnalyzer", "load_summary_data",
    "OpencodeAnalyzer", "REPORTS_DIR",
    "run_opencode_agentic", "AgenticResult", "normalize_opencode_event",
    "stream_subprocess", "StreamResult",
    "run_claude_agentic", "ClaudeStreamAdapter", "adapt_usage",
    "get_backend_for_model", "resolve_backend", "run_agentic",
    "LivePublisher", "make_publisher",
    "compute_routing", "normalize_task", "recommend_route", "simulate_strategies",
    # v1.0 per-step routing
    "route_step", "ModelSignals", "RouteState", "RoutingPreferences", "Objective",
    "StepSelector", "MEASURED_SIGNALS", "FORBIDDEN_SIGNALS",
    "parse_step_selector", "validate_step_selector", "validate_preferences",
    "validate_workflow_routing", "resolve_pool", "cache_switch_penalty",
    # v1.0 signal store
    "build_signal_store", "load_results", "derive_cache_hit_rate",
    "derive_constraint_score", "normalize_model_id", "MODEL_ALIASES",
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
    "compute_deep_metrics",
    "CommitReview", "StoryReview", "review_commit", "review_story",
    "generate_tests", "compare_implementations",
    "EntropyProfile", "compute_entropy", "entropy_delta", "entropy_delta_detailed",
    "CodebaseGraph", "ModuleNode", "GraphMetrics", "GraphDelta",
    "build_graph", "compute_metrics", "compute_graph_delta",
    "LSPDiagnostic", "LSPReport", "run_diagnostics",
    "diagnostics_delta", "available_tools",
    # v1.0 spec/compiler
    "ExperimentSpec", "Workflow", "Factor", "RuleSpec", "MetricSpec",
    "ComparisonSpec", "WriteupSpec", "StopSpec", "AdaptSpec",
    "LEDGER_FIELDS", "load_spec", "validate_rules", "validate_spec",
    "DAG", "Phase", "SpecError", "RuleResult", "MEASUREMENT_RULES",
    "compile_spec", "experiment_matrix", "compare_arms", "evaluate_rules",
    "first_pass_quality",
    "PhaseResult", "WorkflowRunResult", "run_workflow",
    # v1.0 knowledge identity + authority contract
    "Authority", "KnowledgeRecord", "KnowledgeEvent",
    "compute_entity_id", "compute_knowledge_id", "compute_content_hash",
    "SCHEMA_VERSION", "OPERATIONS", "EVIDENCE_CLASSES",
    "run_suite", "suite_succeeded",
    "SUPERVISOR_FLAGS_KEY", "SUPERVISOR_SESSION_CELLS_KEY",
    "normalize_flag", "register_session_mapping",
]
