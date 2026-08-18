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
# canonical-state round 2 (step 1): ACTUATION_TYPES/OBSERVATION_TYPES/message_family added
from .knowledge import (
    ACTUATION_TYPES,
    EVIDENCE_CLASSES,
    OBSERVATION_TYPES,
    OPERATIONS,
    SCHEMA_VERSION,
    Authority,
    KnowledgeEvent,
    KnowledgeRecord,
    compute_content_hash,
    compute_entity_id,
    compute_knowledge_id,
    message_family,
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
from .perturb import PERTURBATION_CLASSES, build_operators, derive_seed, perturb_prompt, perturbation_class_for
from .pipeline_status import STAGE_KEYS, stage_summary
from .prompt_perturbation import (
    FLASH_MODEL,
    PromptPerturbation,
    compile_prompt_perturbation,
    resolve_perturbed_prompt,
)
from .queue_reinterleave import (
    connect,
    provider_of,
    provider_summary,
    read_queue,
    reinterleave_cells,
    write_queue,
)

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

# v1.0: deterministic retrieval + evidence cards for the runtime-RAG layer
from .retrieval import (
    AUTHORITY_MULTIPLIER,
    RELATIONSHIP_WEIGHTS,
    WEIGHTS_VERSION,
    Candidate,
    EvidenceCard,
    FallbackMode,
    QueryPlan,
    RetrievalAttempt,
    build_evidence_cards,
    build_query_plan,
    collapse_redundant,
    compute_fused_score,
    compute_token_budget,
    deduplicate,
    exact_identifier_hit,
    freshness_multiplier,
    graph_boost,
    render_evidence_packet,
    resolve_fallback_mode,
    retrieve,
    rrf_base,
    select_evidence,
)

# v1.0: the prompt-constructor agent (typed plan, validator, deterministic renderer)
from .prompt_constructor import (
    DEFAULT_CONSTRUCTOR_MODEL,
    SCHEMA_VERSION as PROMPT_PLAN_SCHEMA_VERSION,
    AcceptanceCheck,
    AugmentedPrompt,
    ConstructionRequest,
    EvidenceClaim,
    EvidenceUnit,
    HardConstraint,
    ModelPromptConstructor,
    PromptConstructor,
    PromptPlan,
    RelevantTarget,
    build_constructor_prompt,
    build_deterministic_plan,
    construction_cache_key,
    hash_work_item,
    render_prompt,
    validate_plan,
)

# v1.0: producer-side measured-finding derivation (richer extractor over the summary)
from .knowledge_ingestion import (
    ACL_SCOPE,
    ARTIFACT_DIR,
    EXTRACTOR_VERSION,
    PHASE_EXTRACTOR_VERSION,
    PHASE_SOURCE_URI,
    REPOSITORY_ID,
    RESULT_VERSION,
    SOURCE_TYPE,
    SOURCE_URI,
    artifact_uri,
    build_record,
    derive_phase_record,
    derive_records,
    emit_phase_finding,
    extract_record,
    record_to_artifact,
    record_to_event,
)

# v1.0: producer-side code-structure derivation (source_type=code records + graph wiring)
from .code_ingestion import (
    ACL_SCOPE as CODE_ACL_SCOPE,
    EXTRACTOR_VERSION as CODE_EXTRACTOR_VERSION,
    SOURCE_TYPE as CODE_SOURCE_TYPE,
    build_code_record,
    derive_code_records,
    ingest_codebase_graph,
)

# v1.0: producer-side code-quality derivation (source_type=report records)
from .quality_ingestion import (
    ACL_SCOPE as QUALITY_ACL_SCOPE,
    EXTRACTOR_VERSION as QUALITY_EXTRACTOR_VERSION,
    SOURCE_TYPE as QUALITY_SOURCE_TYPE,
    build_quality_record,
    derive_quality_records,
)

# v1.0: producer-side policy ingestion (authority=POLICY records)
from .policy_ingestion import (
    ACL_SCOPE as POLICY_ACL_SCOPE,
    EXTRACTOR_VERSION as POLICY_EXTRACTOR_VERSION,
    SOURCE_TYPE as POLICY_SOURCE_TYPE,
    build_policy_record,
    derive_policy_records,
    discover_policy_paths,
)

# canonical-state round 2: producer-side story derivation (source_type=story records)
from .story_ingestion import (
    ACL_SCOPE as STORY_ACL_SCOPE,
    EXTRACTOR_VERSION as STORY_EXTRACTOR_VERSION,
    SOURCE_TYPE as STORY_SOURCE_TYPE,
    build_story_record,
    derive_story_records,
    derive_story_records_from_run_output,
)

# canonical-state round 2: producer-side review derivation (source_type=review records)
from .review_ingestion import (
    ACL_SCOPE as REVIEW_ACL_SCOPE,
    EXTRACTOR_VERSION as REVIEW_EXTRACTOR_VERSION,
    SOURCE_TYPE as REVIEW_SOURCE_TYPE,
    build_review_record,
    derive_review_records,
)

# canonical-state round 2: producer-side ledger derivation (ledger_job / ledger_attempt /
# meta_session records — closes gap (a) no-session fallback and gap (b) meta_* pollution)
from .ledger_ingestion import (
    EXTRACTOR_VERSION as LEDGER_EXTRACTOR_VERSION,
    FALLBACK_EXTRACTOR_VERSION as LEDGER_FALLBACK_EXTRACTOR_VERSION,
    SOURCE_TYPE_ATTEMPT as LEDGER_SOURCE_TYPE_ATTEMPT,
    SOURCE_TYPE_JOB as LEDGER_SOURCE_TYPE_JOB,
    SOURCE_TYPE_META as LEDGER_SOURCE_TYPE_META,
    build_attempt_record,
    build_job_record,
    classify_session,
    derive_ledger_records,
)

# canonical-state round 2: producer-side observation/flag derivation (every supervisor
# verdict is now registrable, not only flagged ones — closes round 1's OQ6a audit gap)
from .observation_ingestion import (
    ACL_SCOPE as OBSERVATION_ACL_SCOPE,
    EXTRACTOR_VERSION as OBSERVATION_EXTRACTOR_VERSION,
    SOURCE_TYPE_FLAG,
    SOURCE_TYPE_OBSERVATION,
    build_flag_record,
    build_observation_record,
    derive_flag_record,
    derive_observation_record,
)

# canonical-state round 2, Delta 3: producer-side actuation derivation (authority=POLICY,
# built + unit-tested with ZERO call sites — see actuation_ingestion.py's module docstring)
from .actuation_ingestion import (
    ACL_SCOPE as ACTUATION_ACL_SCOPE,
    ACTUATION_KINDS,
    EXTRACTOR_VERSION as ACTUATION_EXTRACTOR_VERSION,
    SOURCE_TYPE as ACTUATION_SOURCE_TYPE,
    derive_actuation_record,
)

# v1.0: durable ingestion over Redis Streams (DB 2, pointer-only events)
from .knowledge_stream import (
    CONSUMER_GROUPS,
    DEAD_LETTER_KEY,
    STREAM_KEY,
    StreamEntry,
    acknowledge,
    claim_pending,
    connect,
    create_consumer_group,
    dead_letter,
    decode_event,
    default_extract,
    delivery_count,
    pending_count,
    process_entry,
    publish_event,
    read_artifact,
    read_events,
    reconcile_missing,
    verify_content_hash,
)

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
    AugmentationOutcome,
    PhaseResult,
    WorkflowRunResult,
    run_workflow,
)

# v1.0: shared post-hoc job shapes + enqueue primitives (execute -> analyze -> review)
from .posthoc import (
    ANALYSIS_QUEUE,
    ANALYSIS_STATUS,
    REVIEW_QUEUE,
    REVIEW_STATUS,
    DEFAULT_REVIEW_MODEL,
    analysis_job_from_result,
    build_analysis_job,
    build_commit_review_job,
    build_review_jobs,
    build_story_review_job,
    enqueue_job,
    trigger_analysis,
    trigger_reviews,
    worktree_commits,
)

__all__ = [
    "build_operators", "perturb_prompt", "PERTURBATION_CLASSES", "perturbation_class_for", "derive_seed",
    "stage_summary", "STAGE_KEYS",
    "compile_prompt_perturbation", "resolve_perturbed_prompt", "PromptPerturbation", "FLASH_MODEL",
    "reinterleave_cells", "read_queue", "write_queue", "provider_summary", "provider_of", "connect",
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
    "PhaseResult", "WorkflowRunResult", "run_workflow", "AugmentationOutcome",
    # v1.0 knowledge identity + authority contract
    "Authority", "KnowledgeRecord", "KnowledgeEvent",
    "compute_entity_id", "compute_knowledge_id", "compute_content_hash",
    "SCHEMA_VERSION", "OPERATIONS", "EVIDENCE_CLASSES",
    # v1.0 retrieval + evidence cards
    "QueryPlan", "Candidate", "EvidenceCard", "RetrievalAttempt", "FallbackMode",
    "build_query_plan", "retrieve", "build_evidence_cards",
    "rrf_base", "compute_fused_score", "graph_boost", "exact_identifier_hit",
    "freshness_multiplier", "compute_token_budget", "select_evidence",
    "deduplicate", "collapse_redundant", "resolve_fallback_mode",
    "render_evidence_packet", "WEIGHTS_VERSION", "RELATIONSHIP_WEIGHTS",
    "AUTHORITY_MULTIPLIER",
    # v1.0 prompt-constructor
    "PromptConstructor", "ModelPromptConstructor",
    "ConstructionRequest", "AugmentedPrompt", "PromptPlan", "EvidenceUnit",
    "HardConstraint", "RelevantTarget", "EvidenceClaim", "AcceptanceCheck",
    "build_constructor_prompt", "build_deterministic_plan", "validate_plan",
    "render_prompt", "construction_cache_key", "hash_work_item",
    "DEFAULT_CONSTRUCTOR_MODEL", "PROMPT_PLAN_SCHEMA_VERSION",
    # v1.0 durable ingestion (Redis Streams, DB 2)
    "StreamEntry", "connect", "publish_event", "create_consumer_group",
    "read_events", "acknowledge", "pending_count", "delivery_count",
    "claim_pending", "dead_letter", "decode_event", "default_extract",
    "process_entry", "read_artifact", "verify_content_hash", "reconcile_missing",
    "CONSUMER_GROUPS", "STREAM_KEY", "DEAD_LETTER_KEY",
    # v1.0 producer-side measured-finding derivation
    "build_record", "record_to_event", "derive_records",
    "record_to_artifact", "extract_record", "artifact_uri",
    "derive_phase_record", "emit_phase_finding",
    "EXTRACTOR_VERSION", "RESULT_VERSION", "SOURCE_URI", "SOURCE_TYPE",
    "REPOSITORY_ID", "ACL_SCOPE", "ARTIFACT_DIR",
    "PHASE_EXTRACTOR_VERSION", "PHASE_SOURCE_URI",
    # v1.0 code ingestion
    "derive_code_records", "build_code_record", "ingest_codebase_graph",
    "CODE_EXTRACTOR_VERSION", "CODE_SOURCE_TYPE", "CODE_ACL_SCOPE",
    # v1.0 quality ingestion
    "derive_quality_records", "build_quality_record",
    "QUALITY_EXTRACTOR_VERSION", "QUALITY_SOURCE_TYPE", "QUALITY_ACL_SCOPE",
    # v1.0 policy ingestion
    "derive_policy_records", "build_policy_record", "discover_policy_paths",
    "POLICY_EXTRACTOR_VERSION", "POLICY_SOURCE_TYPE", "POLICY_ACL_SCOPE",
    # canonical-state round 2: story ingestion
    "derive_story_records", "build_story_record", "derive_story_records_from_run_output",
    "STORY_EXTRACTOR_VERSION", "STORY_SOURCE_TYPE", "STORY_ACL_SCOPE",
    # canonical-state round 2: review ingestion
    "derive_review_records", "build_review_record",
    "REVIEW_EXTRACTOR_VERSION", "REVIEW_SOURCE_TYPE", "REVIEW_ACL_SCOPE",
    # canonical-state round 2: ledger ingestion (gaps a, b)
    "derive_ledger_records", "build_job_record", "build_attempt_record", "classify_session",
    "LEDGER_EXTRACTOR_VERSION", "LEDGER_FALLBACK_EXTRACTOR_VERSION",
    "LEDGER_SOURCE_TYPE_JOB", "LEDGER_SOURCE_TYPE_ATTEMPT", "LEDGER_SOURCE_TYPE_META",
    # canonical-state round 2: observation/flag ingestion (OQ6a closure)
    "derive_observation_record", "build_observation_record",
    "derive_flag_record", "build_flag_record",
    "OBSERVATION_EXTRACTOR_VERSION", "OBSERVATION_ACL_SCOPE",
    "SOURCE_TYPE_OBSERVATION", "SOURCE_TYPE_FLAG",
    # canonical-state round 2, Delta 3: actuation ingestion (zero call sites)
    "derive_actuation_record",
    "ACTUATION_EXTRACTOR_VERSION", "ACTUATION_SOURCE_TYPE", "ACTUATION_ACL_SCOPE",
    "ACTUATION_KINDS",
    # canonical-state round 2, step 1: message-family classification
    "OBSERVATION_TYPES", "ACTUATION_TYPES", "message_family",
    "run_suite", "suite_succeeded",
    "SUPERVISOR_FLAGS_KEY", "SUPERVISOR_SESSION_CELLS_KEY",
    "normalize_flag", "register_session_mapping",
    # v1.0 post-hoc job shapes + enqueue primitives
    "ANALYSIS_QUEUE", "ANALYSIS_STATUS", "REVIEW_QUEUE", "REVIEW_STATUS",
    "DEFAULT_REVIEW_MODEL",
    "build_analysis_job", "analysis_job_from_result",
    "build_commit_review_job", "build_story_review_job", "build_review_jobs",
    "worktree_commits", "enqueue_job", "trigger_analysis", "trigger_reviews",
]
