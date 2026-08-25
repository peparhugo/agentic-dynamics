"""Neo4j knowledge graph population for the experiment ecosystem.

Models experiments as an interconnected graph: models, configs, runs,
perturbation operators, strategies, and basin topologies.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agentic_dynamics.core.language import (
    module_entity_id,
    module_path_from_test_file,
    module_version_id,
    smallest_containing_symbol,
    symbol_entity_id,
    symbol_version_id,
    tested_symbols,
)

if TYPE_CHECKING:
    from agentic_dynamics.measurement.codebase_graph import CodebaseGraph


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# Allowlisted relationship types for bounded graph expansion. Retrieval may only
# traverse these types; any other relationship (ad-hoc links, ``MENTIONS``, etc.)
# is invisible to expansion, so retrieved evidence cannot sneak in through an
# unvetted edge. ``CONTAINS`` + ``AFFECTS`` (design §5.5) are the versioned-graph
# relations the executor must traverse (module/symbol containment, issue→symbol).
ALLOWED_EXPANSION_RELS = frozenset(
    {
        "DEFINES",
        "IMPORTS",
        "CALLS",
        "TESTED_BY",
        "PRODUCED_BY",
        "PRECEDES",
        "SUPERSEDES",
        "CONTRADICTS",
        "CONTAINS",
        "AFFECTS",
    }
)

#: The impact-traversal allowlist — the executor-impact edges ONLY (design §5.7, cap_2a p1).
#: ``SUPERSEDES`` is version history, not blast radius: a changed symbol's older versions are
#: the same entity's past, so the bounded impact expansion (``control.evidence_analyzer``'s
#: ``_neighborhood``) must never traverse them as impact edges. Retrieval keeps the full
#: ``ALLOWED_EXPANSION_RELS`` (version history stays retrievable); impact expansion narrows it.
IMPACT_EXPANSION_RELS = frozenset(ALLOWED_EXPANSION_RELS - {"SUPERSEDES"})

#: Versioned-graph node labels (design §5.5, two-ID contract). ``ModuleVersion`` /
#: ``SymbolVersion`` nodes carry ``entity_id`` (stable slot) + ``version_id`` (immutable
#: version) and ALWAYS carry ``repository_id`` + ``acl_scope`` — a versioned node missing
#: either fails closed under traversal (see ``expand_candidates``).
MODULE_VERSION_LABEL = "ModuleVersion"
SYMBOL_VERSION_LABEL = "SymbolVersion"
REVISION_LABEL = "Revision"
_VERSIONED_LABELS = (MODULE_VERSION_LABEL, SYMBOL_VERSION_LABEL)

# Knowledge-base schema statements. ``Knowledge.knowledge_id`` is unique (the
# immutable version); ``Knowledge.entity_id`` is indexed but NOT unique (many
# versions share one logical entity). ``Step.doc_id`` and ``Step.text`` repair the
# dense↔graph join documented in the RAG review.
_KNOWLEDGE_CONSTRAINTS = [
    "CREATE CONSTRAINT knowledge_id_unique IF NOT EXISTS "
    "FOR (k:Knowledge) REQUIRE k.knowledge_id IS UNIQUE",
    "CREATE CONSTRAINT step_id_unique IF NOT EXISTS FOR (s:Step) REQUIRE s.step_id IS UNIQUE",
    "CREATE CONSTRAINT code_module_path_unique IF NOT EXISTS "
    "FOR (c:CodeModule) REQUIRE c.module_path IS UNIQUE",
]
_KNOWLEDGE_INDEXES = [
    "CREATE INDEX knowledge_entity_id IF NOT EXISTS FOR (k:Knowledge) ON (k.entity_id)",
    "CREATE INDEX step_doc_id IF NOT EXISTS FOR (s:Step) ON (s.doc_id)",
    "CREATE INDEX code_module_name IF NOT EXISTS FOR (c:CodeModule) ON (c.name)",
]
_KNOWLEDGE_FULLTEXT = [
    "CREATE FULLTEXT INDEX step_text_ft IF NOT EXISTS FOR (s:Step) ON EACH [s.text]",
    "CREATE FULLTEXT INDEX knowledge_text_ft IF NOT EXISTS FOR (k:Knowledge) ON EACH [k.text]",
]

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_identifier(name: str, kind: str) -> None:
    """Reject anything that is not a plain identifier (Cypher injection guard).

    Labels, property names, and index names are interpolated into Cypher (Neo4j
    cannot parameterize them); validating them here keeps the typed helpers safe
    without forcing hand-written Cypher at call sites.
    """
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"invalid {kind} identifier: {name!r}")


def _canonical_id(properties: dict[str, Any], fallback: str) -> str:
    """Resolve the canonical cross-store id from a node's properties.

    Prefers ``knowledge_id`` / ``doc_id`` / ``step_id`` / ``entity_id`` — the same
    order the retrieval leg uses to key candidates — and falls back to the Neo4j
    ``elementId`` when none is present, so nodes without a canonical property (e.g.
    ad-hoc test labels) still get a stable identity for expansion bookkeeping.
    """
    for key in ("knowledge_id", "doc_id", "step_id", "entity_id"):
        if properties.get(key):
            return str(properties[key])
    return fallback


def _acl_params(repository_id: str, acl_scope: str) -> dict[str, str]:
    """The ACL parameters for a scoped traversal (only present when BOTH supplied)."""
    if repository_id and acl_scope:
        return {"repository_id": repository_id, "acl_scope": acl_scope}
    return {}


def _acl_clause(alias: str, repository_id: str, acl_scope: str) -> str:
    """The traversal ACL predicate for ``alias`` (design §5.5, finding 2).

    TRAVERSAL-ENFORCED, never a post-filter: the predicate is interpolated into the Cypher
    WHERE of the seed resolution and every hop.

    * BOTH ``repository_id`` + ``acl_scope`` supplied — the scoped path: only nodes carrying
      that exact tenancy identity pass. Versioned nodes must carry both properties; a versioned
      node missing either fails closed.
    * Either omitted — the LEGACY-ONLY default: versioned nodes (``ModuleVersion`` /
      ``SymbolVersion``) are never traversed (fail closed on missing scope, always); only
      unversioned legacy nodes are reachable.
    """
    if repository_id and acl_scope:
        return (
            f"{alias}.repository_id = $repository_id AND {alias}.acl_scope = $acl_scope"
        )
    versioned = " OR ".join(f"{alias}:{label}" for label in _VERSIONED_LABELS)
    return f"NOT ({versioned})"


class _BufferedResult:
    def __init__(self, records):
        self._records = records

    def single(self):
        if not self._records:
            return None
        return self._records[0]

    def __iter__(self):
        return iter(self._records)

    def __len__(self):
        return len(self._records)


class Neo4jClient:
    """Manage Neo4j graph population and queries."""

    def __init__(
        self, uri: str = "bolt://localhost:7687", user: str = "neo4j", password: str = "password123"
    ):  # local dev only — override via ENV for prod
        from neo4j import GraphDatabase

        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self._driver.close()

    def _run(self, query: str, params: dict[str, Any] | None = None):
        with self._driver.session() as session:
            result = session.run(query, params or {})
            records = list(result)
        return _BufferedResult(records)

    def _run_value(self, query: str, params: dict[str, Any] | None = None):
        with self._driver.session() as session:
            result = session.run(query, params or {})
            record = result.single()
            if record is None:
                return None
            return dict(record)

    def create_schema(self) -> None:
        constraints = [
            "CREATE CONSTRAINT model_id_unique IF NOT EXISTS FOR (m:Model) REQUIRE m.model_id IS UNIQUE",
            "CREATE CONSTRAINT config_name_unique IF NOT EXISTS FOR (c:ExperimentConfig) REQUIRE c.name IS UNIQUE",
            "CREATE CONSTRAINT worktree_unique IF NOT EXISTS FOR (r:ExperimentRun) REQUIRE r.worktree_name IS UNIQUE",
            "CREATE CONSTRAINT operator_name_unique IF NOT EXISTS FOR (o:PerturbationOperator) REQUIRE o.name IS UNIQUE",
            "CREATE CONSTRAINT strategy_name_unique IF NOT EXISTS FOR (s:StrategyArchetype) REQUIRE s.name IS UNIQUE",
        ]
        for c in constraints:
            with contextlib.suppress(Exception):
                self._run(c)

    def clear_all(self) -> None:
        self._run("MATCH (n) DETACH DELETE n")

    def create_knowledge_schema(self) -> None:
        """Create the knowledge-base constraints, indexes, and full-text indexes.

        Idempotent (``IF NOT EXISTS``). Each statement is attempted independently
        so a statement an older server rejects does not abort the rest — mirroring
        ``create_schema()``. Includes the native full-text index over ``Step.text``
        (queried by ``search_fulltext``) and the one over ``Knowledge.text``
        (queried by ``search_knowledge_fulltext``) — the latter is what makes the
        knowledge base retrievable by the lexical leg.
        """
        for stmt in _KNOWLEDGE_CONSTRAINTS + _KNOWLEDGE_INDEXES + _KNOWLEDGE_FULLTEXT:
            with contextlib.suppress(Exception):
                self._run(stmt)

    def load_operators(self) -> None:
        operators = [
            ("inject_alien_vocab", "process_perturbation"),
            ("shift_framing", "process_perturbation"),
            ("reverse_causality", "process_perturbation"),
            ("force_abandonment", "process_perturbation"),
            ("remove_critical_constraint", "specification_corruption"),
            ("invert_constraint", "objective_mutation"),
            ("inject_phantom_success", "specification_corruption"),
            ("inject_competing_goal", "objective_mutation"),
            ("inject_false_premise", "specification_corruption"),
            ("insert_contradiction", "specification_corruption"),
        ]
        for name, cls in operators:
            self._run(
                "MERGE (o:PerturbationOperator {name: $name}) SET o.class = $cls",
                {"name": name, "cls": cls},
            )

        strategy_names = [
            ("conservative", "Low escape, high correctness, moderate cost"),
            ("exploratory", "High escape, moderate-high novelty, varied cost"),
            ("wasteful", "High escape, low correctness, high cost"),
            ("efficient", "Low escape, high correctness, low cost"),
        ]
        for name, desc in strategy_names:
            self._run(
                "MERGE (s:StrategyArchetype {name: $name}) SET s.description = $desc",
                {"name": name, "desc": desc},
            )

    def load_models(self, aggregate_path: Path | None = None) -> None:
        if aggregate_path is None:
            aggregate_path = PROJECT_ROOT / "experiments" / "results" / "_trajectory_aggregate.json"
        if not aggregate_path.exists():
            print(f"Warning: {aggregate_path} not found, skipping model loading")
            return

        data = json.loads(aggregate_path.read_text())
        by_model = data.get("by_model", {})

        for model_id, stats in by_model.items():
            provider = model_id.split("/")[0] if "/" in model_id else "unknown"
            self._run(
                """
                MERGE (m:Model {model_id: $model_id})
                SET m.provider = $provider,
                    m.count = $count,
                    m.avg_steps = $avg_steps,
                    m.avg_tokens_per_session = $avg_tokens,
                    m.avg_output_tokens = $avg_output,
                    m.avg_input_tokens = $avg_input,
                    m.avg_reasoning_tokens = $avg_reasoning,
                    m.avg_cache_read = $avg_cache_read,
                    m.avg_cache_write = $avg_cache_write,
                    m.avg_cost_per_session = $avg_cost,
                    m.avg_git_snapshots = $avg_snapshots,
                    m.avg_read_pct = $avg_read_pct,
                    m.avg_write_pct = $avg_write_pct,
                    m.avg_bash_pct = $avg_bash_pct,
                    m.total_parse_errors = $parse_errors,
                    m.tool_call_distribution = $tool_dist
            """,
                {
                    "model_id": model_id,
                    "provider": provider,
                    "count": stats.get("count", 0),
                    "avg_steps": stats.get("avg_steps", 0),
                    "avg_tokens": stats.get("avg_tokens_per_session", 0),
                    "avg_output": stats.get("avg_output_tokens", 0),
                    "avg_input": stats.get("avg_input_tokens", 0),
                    "avg_reasoning": stats.get("avg_reasoning_tokens", 0),
                    "avg_cache_read": stats.get("avg_cache_read", 0),
                    "avg_cache_write": stats.get("avg_cache_write", 0),
                    "avg_cost": stats.get("avg_cost_per_session", 0),
                    "avg_snapshots": stats.get("avg_git_snapshots", 0),
                    "avg_read_pct": stats.get("avg_read_pct", 0),
                    "avg_write_pct": stats.get("avg_write_pct", 0),
                    "avg_bash_pct": stats.get("avg_bash_pct", 0),
                    "parse_errors": stats.get("total_parse_errors", 0),
                    "tool_dist": json.dumps(stats.get("tool_call_distribution", {})),
                },
            )

    def load_runs(self, summary_path: Path | None = None) -> None:
        if summary_path is None:
            summary_path = PROJECT_ROOT / "experiments" / "results" / "_results_summary.json"
        if not summary_path.exists():
            print(f"Warning: {summary_path} not found, skipping run loading")
            return

        data = json.loads(summary_path.read_text())
        entries = data.get("entries", [])

        for entry in entries:
            wt_name = entry.get("worktree_name", "")
            if not wt_name:
                continue

            model_id = entry.get("model", "unknown")
            strategy_type = entry.get("strategy", "?")
            operator_name = entry.get("operator", "")

            props = {
                "worktree_name": wt_name,
                "experiment": entry.get("experiment", ""),
                "model": model_id,
                "operator": operator_name,
                "perturbation_class": entry.get("perturbation_class", ""),
                "silent_mode": entry.get("silent_mode", ""),
                "narration_failure": entry.get("narration_failure", False),
                "narration_penalty": entry.get("narration_penalty", 0.0),
                "cost_usd": entry.get("cost", 0),
                "tokens_total": entry.get("tokens", 0),
                "tokens_input": entry.get("tokens_input", 0),
                "tokens_output": entry.get("tokens_output", 0),
                "tokens_reasoning": entry.get("tokens_reasoning", 0),
                "tokens_cache_read": entry.get("tokens_cache_read", 0),
                "tokens_cache_write": entry.get("tokens_cache_write", 0),
                "energy_total_j": entry.get("energy_total_j", 0),
                "thinking_ratio": entry.get("thinking_ratio", 0),
                "output_efficiency": entry.get("output_efficiency", 0),
                "correctness": entry.get("correctness", 0),
                "constraints_met": entry.get("constraints_met", 0),
                "constraints_total": entry.get("constraints_total", 0),
                "code_lines": entry.get("code_lines", 0),
                "code_quality_score": entry.get("code_quality_score", 0),
                "novelty_score": entry.get("novelty_score", 0),
                "composite_score": entry.get("composite_score", 0),
                "escape": entry.get("escape", 0),
                "architecture_divergence": entry.get("architecture_divergence", 0),
                "structure_divergence": entry.get("structure_divergence", 0),
                "basin_verdict": entry.get("basin_verdict", ""),
                "converged_back": entry.get("converged_back", False),
                "no_baseline": entry.get("no_baseline", False),
                "strategy": strategy_type,
                "strategy_score": entry.get("strategy_score", 0),
                "exploration_premium": entry.get("exploration_premium", 0),
                "thermal_efficiency": entry.get("thermal_efficiency", 0),
                "strategy_verdict": entry.get("strategy_verdict", ""),
                "is_frontend": entry.get("is_frontend", False),
                "has_tests": entry.get("has_tests", False),
                "cyclomatic_complexity": entry.get("cyclomatic_complexity", 0),
                "comment_ratio": entry.get("comment_ratio", 0),
                "correctness_per_dollar": entry.get("correctness_per_dollar", 0),
                "quality_per_joule": entry.get("quality_per_joule", 0),
            }

            self._run(
                """
                MERGE (r:ExperimentRun {worktree_name: $worktree_name})
                SET r.experiment = $experiment,
                    r.model = $model,
                    r.operator = $operator,
                    r.perturbation_class = $perturbation_class,
                    r.silent_mode = $silent_mode,
                    r.narration_failure = $narration_failure,
                    r.narration_penalty = $narration_penalty,
                    r.cost_usd = $cost_usd,
                    r.tokens_total = $tokens_total,
                    r.tokens_input = $tokens_input,
                    r.tokens_output = $tokens_output,
                    r.tokens_reasoning = $tokens_reasoning,
                    r.tokens_cache_read = $tokens_cache_read,
                    r.tokens_cache_write = $tokens_cache_write,
                    r.energy_total_j = $energy_total_j,
                    r.thinking_ratio = $thinking_ratio,
                    r.output_efficiency = $output_efficiency,
                    r.correctness = $correctness,
                    r.constraints_met = $constraints_met,
                    r.constraints_total = $constraints_total,
                    r.code_lines = $code_lines,
                    r.code_quality_score = $code_quality_score,
                    r.novelty_score = $novelty_score,
                    r.composite_score = $composite_score,
                    r.escape = $escape,
                    r.architecture_divergence = $architecture_divergence,
                    r.structure_divergence = $structure_divergence,
                    r.basin_verdict = $basin_verdict,
                    r.converged_back = $converged_back,
                    r.no_baseline = $no_baseline,
                    r.strategy = $strategy,
                    r.strategy_score = $strategy_score,
                    r.exploration_premium = $exploration_premium,
                    r.thermal_efficiency = $thermal_efficiency,
                    r.strategy_verdict = $strategy_verdict,
                    r.is_frontend = $is_frontend,
                    r.has_tests = $has_tests,
                    r.cyclomatic_complexity = $cyclomatic_complexity,
                    r.comment_ratio = $comment_ratio,
                    r.correctness_per_dollar = $correctness_per_dollar,
                    r.quality_per_joule = $quality_per_joule
            """,
                props,
            )

    def link_runs(self) -> None:
        queries = [
            "MATCH (r:ExperimentRun) MATCH (m:Model {model_id: r.model}) MERGE (r)-[:RUN_ON]->(m)",
            "MATCH (r:ExperimentRun) WHERE r.experiment IS NOT NULL AND r.experiment <> '' "
            "MATCH (c:ExperimentConfig {name: r.experiment}) "
            "MERGE (r)-[:INSTANCE_OF]->(c)",
            "MATCH (r:ExperimentRun) WHERE r.operator IS NOT NULL AND r.operator <> '' "
            "AND r.operator <> 'perturbed' AND r.operator <> 'baseline' "
            "MATCH (o:PerturbationOperator {name: r.operator}) "
            "MERGE (r)-[:USED_OPERATOR]->(o)",
            "MATCH (r:ExperimentRun) WHERE r.strategy IS NOT NULL AND "
            "r.strategy IN ['conservative', 'exploratory', 'wasteful', 'efficient'] "
            "MATCH (s:StrategyArchetype {name: r.strategy}) "
            "MERGE (r)-[:CLASSIFIED_AS]->(s)",
        ]
        for query in queries:
            with contextlib.suppress(Exception):
                self._run(query)

    def load_basin_topology(self, basin_path: Path | None = None) -> None:
        # lab_basin_topology.py is a QUARANTINED lab (it reads the retired
        # _results_summary.json), so its artifact lives in experiments/results/legacy_labs/.
        # This loader is itself part of the summary-derived graph path; the default is
        # re-pointed rather than removed so the historical graph can still be rebuilt by
        # hand. See experiments/results/legacy_labs/README.md.
        if basin_path is None:
            basin_path = (
                PROJECT_ROOT / "experiments" / "results" / "legacy_labs" / "lab_basin_topology.json"
            )
        if not basin_path.exists():
            print(f"Warning: {basin_path} not found, skipping basin topology loading")
            return

        data = json.loads(basin_path.read_text())
        model_profiles = data.get("model_profiles", {})

        for model_label, profile in model_profiles.items():
            if model_label.startswith("_"):
                continue
            model_id = profile.get("model_id", "")
            if not model_id:
                continue

            self._run(
                """
                MERGE (bt:BasinTopology {model_id: $model_id})
                SET bt.model_label = $label,
                    bt.total_sessions = $total_sessions,
                    bt.valid_sessions = $valid_sessions,
                    bt.flail_count = $flail_count,
                    bt.flail_rate = $flail_rate,
                    bt.overall_escape = $overall_escape,
                    bt.overall_correctness = $overall_correctness,
                    bt.overall_cost = $overall_cost
            """,
                {
                    "model_id": model_id,
                    "label": model_label,
                    "total_sessions": profile.get("total_sessions", 0),
                    "valid_sessions": profile.get("valid_sessions", 0),
                    "flail_count": profile.get("flail_count", 0),
                    "flail_rate": profile.get("flail_rate", 0),
                    "overall_escape": profile.get("overall_escape", 0),
                    "overall_correctness": profile.get("overall_correctness", 0),
                    "overall_cost": profile.get("overall_cost", 0),
                },
            )

            self._run(
                "MATCH (m:Model {model_id: $model_id}) "
                "MATCH (bt:BasinTopology {model_id: $model_id}) "
                "MERGE (m)-[:HAS_BASIN]->(bt)",
                {"model_id": model_id},
            )

            for pclass, bp in profile.get("basin_profiles", {}).items():
                profile_id = f"{model_id}_{pclass}"
                self._run(
                    """
                    MERGE (bp:BasinProfile {profile_id: $profile_id})
                    SET bp.perturbation_class = $pclass,
                        bp.n = $n,
                        bp.escape = $escape,
                        bp.correctness = $correctness,
                        bp.cost = $cost,
                        bp.architecture_divergence = $arch_div,
                        bp.structure_divergence = $struct_div,
                        bp.novelty = $novelty,
                        bp.tokens = $tokens,
                        bp.loc = $loc,
                        bp.thinking_ratio = $thinking_ratio,
                        bp.recovery_multiplier = $recovery_mult,
                        bp.basin_volume = $basin_volume,
                        bp.basin_type = $basin_type,
                        bp.basin_description = $basin_desc
                """,
                    {
                        "profile_id": profile_id,
                        "pclass": pclass,
                        "n": bp.get("n", 0),
                        "escape": bp.get("escape", 0),
                        "correctness": bp.get("correctness", 0),
                        "cost": bp.get("cost", 0),
                        "arch_div": bp.get("architecture_divergence", 0),
                        "struct_div": bp.get("structure_divergence", 0),
                        "novelty": bp.get("novelty", 0),
                        "tokens": bp.get("tokens", 0),
                        "loc": bp.get("loc", 0),
                        "thinking_ratio": bp.get("thinking_ratio", 0),
                        "recovery_mult": bp.get("recovery_multiplier", 0),
                        "basin_volume": bp.get("basin_volume", 0),
                        "basin_type": bp.get("basin_type", ""),
                        "basin_desc": bp.get("basin_description", ""),
                    },
                )

                self._run(
                    "MATCH (bt:BasinTopology {model_id: $model_id}) "
                    "MATCH (bp:BasinProfile {profile_id: $profile_id}) "
                    "MERGE (bt)-[:PROFILE_IN]->(bp)",
                    {"model_id": model_id, "profile_id": profile_id},
                )

    def load_configs(self, config_dir: Path | None = None) -> None:
        if config_dir is None:
            config_dir = PROJECT_ROOT / "experiments" / "configs"
        if not config_dir.exists():
            return

        import yaml

        for config_file in config_dir.glob("*.yaml"):
            try:
                with open(config_file) as f:
                    cfg = yaml.safe_load(f)
            except Exception:
                continue

            name = cfg.get("name", config_file.stem)
            self._run(
                """
                MERGE (c:ExperimentConfig {name: $name})
                SET c.task = $task,
                    c.model = $model,
                    c.constraints_count = $constraints_count,
                    c.operator_count = $operator_count,
                    c.standardized = $standardized
            """,
                {
                    "name": name,
                    "task": cfg.get("task", "")[:500],
                    "model": cfg.get("model", ""),
                    "constraints_count": len(cfg.get("constraints", [])),
                    "operator_count": len(cfg.get("operators", [])),
                    "standardized": cfg.get("standardized", {}).get("enabled", False),
                },
            )

    def build(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        self.create_schema()
        self.load_operators()

        self.load_models()
        result = self._run("MATCH (m:Model) RETURN count(m) AS c")
        counts["models"] = result.single()["c"]

        self.load_configs()
        result = self._run("MATCH (c:ExperimentConfig) RETURN count(c) AS c")
        counts["configs"] = result.single()["c"]

        self.load_runs()
        result = self._run("MATCH (r:ExperimentRun) RETURN count(r) AS c")
        counts["runs"] = result.single()["c"]

        self.link_runs()

        result = self._run("MATCH ()-[rel:RUN_ON]->() RETURN count(rel) AS c")
        counts["run_on_rels"] = result.single()["c"]
        result = self._run("MATCH ()-[rel:INSTANCE_OF]->() RETURN count(rel) AS c")
        counts["instance_of_rels"] = result.single()["c"]
        result = self._run("MATCH ()-[rel:USED_OPERATOR]->() RETURN count(rel) AS c")
        counts["operator_rels"] = result.single()["c"]
        result = self._run("MATCH ()-[rel:CLASSIFIED_AS]->() RETURN count(rel) AS c")
        counts["strategy_rels"] = result.single()["c"]

        self.load_basin_topology()
        result = self._run("MATCH (bt:BasinTopology) RETURN count(bt) AS c")
        counts["basin_topologies"] = result.single()["c"]
        result = self._run("MATCH (bp:BasinProfile) RETURN count(bp) AS c")
        counts["basin_profiles"] = result.single()["c"]

        return counts

    def build_step_graph(
        self, chroma_collection: str = "session_embeddings", max_steps: int = 0
    ) -> dict[str, int]:
        """Create Step nodes and relationships from session.jsonl files.

        Reads reasoning steps directly from session files using extract_session_steps,
        avoiding ChromaDB dependency. Each step becomes a :Step node with
        :HAS_STEP and :NEXT relationships.
        """
        sys.path.insert(0, str(PROJECT_ROOT / "src"))
        from agentic_dynamics.knowledge.embeddings import extract_session_steps, step_doc_id

        reports_dir = PROJECT_ROOT / "experiments" / "results" / "reports"
        session_files = sorted(reports_dir.glob("*/session.jsonl"))

        sessions: dict[str, list[dict]] = {}
        step_total = 0

        for sp in session_files:
            sid = sp.parent.name
            steps = extract_session_steps(sp)
            if not steps:
                continue
            if max_steps and step_total + len(steps) > max_steps:
                remaining = max_steps - step_total
                steps = steps[:remaining]
            if not steps:
                break
            sessions[sid] = steps
            step_total += len(steps)
            if max_steps and step_total >= max_steps:
                break

        # Create Session nodes
        for sid in sessions:
            self._run("MERGE (s:Session {session_id: $sid})", {"sid": sid})

        # Create Step nodes and relationships
        step_count = 0
        rel_count = 0
        for sid, steps in sessions.items():
            prev_step_id = None
            for step in steps:
                si = step["step_index"]
                step_id = f"{sid}_s{si:04d}"
                # doc_id MUST equal the canonical Chroma id (step_doc_id) so the
                # dense and graph indexes join on the same value — the previous
                # code hardcoded doc_id='' and never stored text, silently
                # breaking the join. step_id stays the Neo4j-internal key.
                doc_id = step_doc_id(sid, si)
                self._run(
                    """
                    MERGE (st:Step {step_id: $step_id})
                    SET st.session_id = $sid,
                        st.step_index = $step_index,
                        st.tool_after = $tool_after,
                        st.doc_id = $doc_id,
                        st.text = $text
                """,
                    {
                        "step_id": step_id,
                        "sid": sid,
                        "step_index": si,
                        "tool_after": step.get("tool_after", ""),
                        "doc_id": doc_id,
                        "text": step.get("text", ""),
                    },
                )
                step_count += 1

                self._run(
                    "MATCH (s:Session {session_id: $sid}) "
                    "MATCH (st:Step {step_id: $step_id}) "
                    "MERGE (s)-[:HAS_STEP]->(st)",
                    {"sid": sid, "step_id": step_id},
                )
                rel_count += 1

                if prev_step_id:
                    self._run(
                        "MATCH (a:Step {step_id: $a}) "
                        "MATCH (b:Step {step_id: $b}) "
                        "MERGE (a)-[:NEXT]->(b)",
                        {"a": prev_step_id, "b": step_id},
                    )
                    rel_count += 1
                prev_step_id = step_id

        return {"sessions": len(sessions), "steps": step_count, "relationships": rel_count}

    def load_codebase_graph(self, graph: CodebaseGraph, worktree_name: str) -> dict[str, int]:
        """Persist an in-memory import graph as :CodeModule nodes and edges.

        Writes one :CodeModule per module, bidirectional ``IMPORTS`` /
        ``IMPORTED_BY`` edges between them, and links the owning experiment run
        via ``(ExperimentRun)-[:TOUCHED]->(CodeModule)``. Persisting this graph —
        currently thrown away by ``codebase_graph.build_graph`` — lets retrieval
        answer "what else touched this module".
        """
        counts = {"modules": 0, "imports": 0, "imported_by": 0, "touched": 0}

        # Ensure the owning run exists so every TOUCHED edge has a source.
        self._run(
            "MERGE (r:ExperimentRun {worktree_name: $wt})",
            {"wt": worktree_name},
        )

        for path, module in graph.modules.items():
            name = Path(path).name
            self._run(
                """
                MERGE (c:CodeModule {module_path: $path})
                SET c.name = $name,
                    c.language = $language,
                    c.loc = $loc,
                    c.node_type = 'module'
                """,
                {"path": path, "name": name, "language": graph.language, "loc": module.loc},
            )
            counts["modules"] += 1
            self._run(
                "MATCH (r:ExperimentRun {worktree_name: $wt}) "
                "MATCH (c:CodeModule {module_path: $path}) "
                "MERGE (r)-[:TOUCHED]->(c)",
                {"wt": worktree_name, "path": path},
            )
            counts["touched"] += 1

        for path, module in graph.modules.items():
            for target in module.imports_from:
                if target not in graph.modules:
                    continue
                self._run(
                    "MATCH (a:CodeModule {module_path: $a}) "
                    "MATCH (b:CodeModule {module_path: $b}) "
                    "MERGE (a)-[:IMPORTS]->(b)",
                    {"a": path, "b": target},
                )
                counts["imports"] += 1
                self._run(
                    "MATCH (a:CodeModule {module_path: $a}) "
                    "MATCH (b:CodeModule {module_path: $b}) "
                    "MERGE (b)-[:IMPORTED_BY]->(a)",
                    {"a": path, "b": target},
                )
                counts["imported_by"] += 1

        return counts

    def populate_versioned_graph(
        self,
        snapshot: Any,
        *,
        revision: str,
        repository_id: str,
        acl_scope: str,
        issues: list[Any] | None = None,
        diagnostics: list[Any] | None = None,
    ) -> dict[str, int]:
        """Version the graph from a typed CodeSnapshot (design §5.5, e4).

        Creates, for one revision of one repository:

        * a ``Revision`` node (``version_id = f(repository_id, revision)``);
        * one ``ModuleVersion`` per module and one ``SymbolVersion`` per symbol, each with the
          two-ID contract (``entity_id`` stable slot + ``version_id`` immutable version), the
          traversal ACL properties (``repository_id`` + ``acl_scope``) ALWAYS present, and
          ``SUPERSEDES`` edges to every older version of the same entity (deterministic from the
          ids); renames are new entities (no implicit matching);
        * ``CONTAINS`` / ``DEFINES`` / ``IMPORTS`` first, ``CALLS`` / ``TESTED_BY`` / ``AFFECTS``
          next;
        * the **multi-label seed join**: each ``SymbolVersion`` is also ``:Knowledge`` with the
          knowledge-surface properties (``knowledge_id`` = ``version_id``, ``text``,
          ``authority``, ``source_type``), so existing full-text seeds expand directly into
          symbol versions.

        Additive by construction: only versioned nodes/edges are written; existing unversioned
        nodes are untouched. ``issues`` / ``diagnostics`` (optional) create ``SonarIssue`` /
        ``Diagnostic`` nodes and ``AFFECTS`` edges to the smallest containing ``SymbolVersion``.
        """
        counts = {
            "revisions": 0, "module_versions": 0, "symbol_versions": 0,
            "contains": 0, "defines": 0, "imports": 0, "calls": 0,
            "tested_by": 0, "affects": 0, "supersedes": 0,
        }
        rev_version_id = hashlib.sha256(
            f"revision|{repository_id}|{revision}".encode()
        ).hexdigest()
        self._run(
            "MERGE (r:Revision {version_id: $vid}) "
            "SET r.repository_id = $repo, r.acl_scope = $acl, r.commit_sha = $revision",
            {"vid": rev_version_id, "repo": repository_id, "acl": acl_scope, "revision": revision},
        )
        counts["revisions"] = 1

        sym_vids: dict[tuple[str, str, str], str] = {}  # (file, qname, kind) -> version_id
        qname_to_vid: dict[str, str] = {}
        module_vids: dict[str, str] = {}  # module_name -> version_id

        for path in sorted(snapshot.files):
            module_name = snapshot.files[path][0].module_name if snapshot.files[path] else ""
            module_ent = module_entity_id(repository_id, module_name)
            module_hash = snapshot.file_hashes.get(path, "")
            module_vid = module_version_id(module_ent, revision, module_hash)
            module_vids[module_name] = module_vid
            self._run(
                f"MERGE (m:{MODULE_VERSION_LABEL} {{version_id: $vid}}) "
                "SET m.entity_id = $ent, m.module_name = $module_name, m.module_path = $path, "
                "m.repository_id = $repo, m.acl_scope = $acl, m.commit_sha = $revision, "
                "m.content_hash = $hash, m.language = $language",
                {
                    "vid": module_vid, "ent": module_ent, "module_name": module_name,
                    "path": path, "repo": repository_id, "acl": acl_scope,
                    "revision": revision, "hash": module_hash,
                    "language": snapshot.language,
                },
            )
            counts["module_versions"] += 1
            self._run(
                f"MATCH (r:{REVISION_LABEL} {{version_id: $rid}}) "
                f"MATCH (m:{MODULE_VERSION_LABEL} {{version_id: $vid}}) "
                f"MERGE (r)-[:CONTAINS]->(m)",
                {"rid": rev_version_id, "vid": module_vid},
            )
            counts["contains"] += 1

            for sym in snapshot.files[path]:
                sym_ent = symbol_entity_id(
                    repository_id, path, sym.qualified_name, sym.kind
                )
                sym_vid = symbol_version_id(sym_ent, revision, sym.content_hash)
                sym_vids[(path, sym.qualified_name, sym.kind)] = sym_vid
                qname_to_vid[sym.qualified_name] = sym_vid
                self._run(
                    f"MERGE (s:{SYMBOL_VERSION_LABEL} {{version_id: $vid}}) "
                    f"SET s:{'Knowledge'} "
                    "SET s.entity_id = $ent, s.qualified_name = $qname, s.kind = $kind, "
                    "s.file_path = $path, s.module_name = $module_name, "
                    "s.repository_id = $repo, s.acl_scope = $acl, s.commit_sha = $revision, "
                    "s.content_hash = $hash, s.source_span = $span, s.text = $text, "
                    "s.knowledge_id = $vid, s.authority = 'SOURCE', s.source_type = 'code', "
                    "s.logical_locator = $path, s.language = $language",
                    {
                        "vid": sym_vid, "ent": sym_ent, "qname": sym.qualified_name,
                        "kind": sym.kind, "path": path, "module_name": module_name,
                        "repo": repository_id, "acl": acl_scope, "revision": revision,
                        "hash": sym.content_hash,
                        "span": f"{sym.source_span.start_line}:{sym.source_span.end_line}",
                        "text": f"{sym.qualified_name} ({sym.kind}) in {path}",
                        "language": snapshot.language,
                    },
                )
                counts["symbol_versions"] += 1
                self._run(
                    f"MATCH (m:{MODULE_VERSION_LABEL} {{version_id: $mvid}}) "
                    f"MATCH (s:{SYMBOL_VERSION_LABEL} {{version_id: $svid}}) "
                    f"MERGE (m)-[:CONTAINS]->(s) "
                    f"MERGE (m)-[:DEFINES]->(s)",
                    {"mvid": module_vid, "svid": sym_vid},
                )
                counts["contains"] += 1
                counts["defines"] += 1

        # IMPORTS: ModuleVersion -> ModuleVersion (from the snapshot's per-file imports).
        for path in sorted(snapshot.imports):
            from_module = snapshot.files[path][0].module_name if snapshot.files.get(path) else ""
            if not from_module or from_module not in module_vids:
                continue
            for target in snapshot.imports.get(path, []):
                target_module = target.replace("/", ".").replace(".py", "")
                if target_module in module_vids:
                    self._run(
                        f"MATCH (a:{MODULE_VERSION_LABEL} {{version_id: $avid}}) "
                        f"MATCH (b:{MODULE_VERSION_LABEL} {{version_id: $bvid}}) "
                        f"MERGE (a)-[:IMPORTS]->(b)",
                        {"avid": module_vids[from_module], "bvid": module_vids[target_module]},
                    )
                    counts["imports"] += 1

        # CALLS: SymbolVersion -> SymbolVersion (name-based best-effort from sym.calls).
        for (path, qname, _kind), svid in sym_vids.items():
            for sym in snapshot.files.get(path, []):
                if sym.qualified_name != qname:
                    continue
                for callee in sym.calls:
                    if callee in qname_to_vid:
                        self._run(
                            f"MATCH (a:{SYMBOL_VERSION_LABEL} {{version_id: $avid}}) "
                            f"MATCH (b:{SYMBOL_VERSION_LABEL} {{version_id: $bvid}}) "
                            f"MERGE (a)-[:CALLS]->(b)",
                            {"avid": svid, "bvid": qname_to_vid[callee]},
                        )
                        counts["calls"] += 1

        # TESTED_BY: tested symbols -> the symbols of their matching test module (the rule).
        tested = tested_symbols(snapshot)
        for test_file in sorted(snapshot.files):
            module_file = module_path_from_test_file(test_file)
            if module_file is None or module_file not in snapshot.files:
                continue
            for tested_sym in snapshot.files[module_file]:
                if tested_sym.qualified_name not in tested:
                    continue
                tested_vid = sym_vids.get((module_file, tested_sym.qualified_name, tested_sym.kind))
                if tested_vid is None:
                    continue
                for test_sym in snapshot.files[test_file]:
                    test_vid = sym_vids.get((test_file, test_sym.qualified_name, test_sym.kind))
                    if test_vid is None:
                        continue
                    self._run(
                        f"MATCH (a:{SYMBOL_VERSION_LABEL} {{version_id: $avid}}) "
                        f"MATCH (b:{SYMBOL_VERSION_LABEL} {{version_id: $bvid}}) "
                        f"MERGE (a)-[:TESTED_BY]->(b)",
                        {"avid": tested_vid, "bvid": test_vid},
                    )
                    counts["tested_by"] += 1

        # AFFECTS: optional issues/diagnostics -> smallest containing SymbolVersion. The
        # SonarIssue/Diagnostic nodes carry the traversal ACL (``repository_id`` +
        # ``acl_scope``) so a scoped expansion can reach them (and their other AFFECTS
        # targets), and their keys are repository/revision-namespaced so the same issue key
        # in different repositories or revisions never collides (cap_2a p1 hardening).
        for issue in issues or []:
            vid = self._version_id_for_location(snapshot, issue.file_path, issue.line, repository_id, revision)
            if vid is None:
                continue
            issue_key = f"{repository_id}:{revision}:{issue.key}"
            self._run(
                "MERGE (d:SonarIssue {key: $key, repository_id: $repo, acl_scope: $acl}) "
                "SET d.commit_sha = $revision, d.rule = $rule, d.severity = $severity, "
                "d.file_path = $path, d.line = $line "
                f"WITH d MATCH (s:{SYMBOL_VERSION_LABEL} {{version_id: $vid}}) "
                "MERGE (d)-[:AFFECTS]->(s)",
                {
                    "key": issue_key, "repo": repository_id, "acl": acl_scope,
                    "revision": revision, "rule": issue.rule, "severity": issue.severity,
                    "path": issue.file_path, "line": issue.line, "vid": vid,
                },
            )
            counts["affects"] += 1
        for diag in diagnostics or []:
            vid = self._version_id_for_location(snapshot, diag.file, diag.line, repository_id, revision)
            if vid is None:
                continue
            diag_key = f"{repository_id}:{revision}:{diag.file}:{diag.line}:{diag.code}"
            self._run(
                "MERGE (d:Diagnostic {key: $key, repository_id: $repo, acl_scope: $acl}) "
                "SET d.commit_sha = $revision, d.rule = $rule, d.severity = $severity, "
                "d.file_path = $path, d.line = $line "
                f"WITH d MATCH (s:{SYMBOL_VERSION_LABEL} {{version_id: $vid}}) "
                "MERGE (d)-[:AFFECTS]->(s)",
                {
                    "key": diag_key, "repo": repository_id, "acl": acl_scope,
                    "revision": revision, "rule": diag.code, "severity": diag.severity,
                    "path": diag.file, "line": diag.line, "vid": vid,
                },
            )
            counts["affects"] += 1

        # SUPERSEDES: every new version -> every older version of the same entity (deterministic).
        # ``new`` is anchored by version_id (the version just written) so a re-population never
        # cross-links two older versions.
        module_pairs = {
            (module_entity_id(repository_id, name), vid) for name, vid in module_vids.items()
        }
        symbol_pairs = {
            (symbol_entity_id(repository_id, path, qname, kind), vid)
            for (path, qname, kind), vid in sym_vids.items()
        }
        for label, pairs in (
            (MODULE_VERSION_LABEL, module_pairs),
            (SYMBOL_VERSION_LABEL, symbol_pairs),
        ):
            for ent, vid in sorted(pairs):
                self._run(
                    f"MATCH (new:{label} {{version_id: $vid}}) "
                    f"MATCH (old:{label}) "
                    "WHERE old.entity_id = $ent AND old.version_id <> $vid "
                    f"MERGE (new)-[:SUPERSEDES]->(old)",
                    {"ent": ent, "vid": vid},
                )
                counts["supersedes"] += 1

        return counts

    @staticmethod
    def _version_id_for_location(
        snapshot: Any, file_path: str, line: int, repository_id: str, revision: str
    ) -> str | None:
        """The version_id of the smallest containing symbol at ``(file_path, line)``, or None."""
        sym = smallest_containing_symbol(snapshot, file_path, line)
        if sym is None:
            return None
        ent = symbol_entity_id(repository_id, file_path, sym.qualified_name, sym.kind)
        return symbol_version_id(ent, revision, sym.content_hash)

    @staticmethod
    def _node_dict(record: Any, *, with_score: bool = False) -> dict[str, Any]:
        """Normalize a search record into ``{"id", "labels", "properties"}``."""
        out: dict[str, Any] = {
            "id": record["node_id"],
            "labels": list(record["labels"]),
            "properties": dict(record["properties"]),
        }
        if with_score:
            out["score"] = record["score"]
        return out

    def _resolve_node(
        self,
        node_ref: str,
        *,
        repository_id: str = "",
        acl_scope: str = "",
    ) -> dict[str, Any] | None:
        """Resolve a node by canonical id (or ``elementId``) — not elementId alone.

        The retrieval leg seeds expansion with canonical cross-store ids
        (``knowledge_id`` / ``doc_id`` / ``step_id`` / ``entity_id``), so seed
        lookup must match on those properties; ``elementId`` is kept as a fallback
        for callers that still pass an elementId. Returns ``None`` when
        unresolvable so the caller can skip the seed cleanly (never a zero-score
        hit).

        The traversal ACL (``repository_id`` + ``acl_scope``) is enforced HERE — a
        seed outside the scope is unresolvable, never a later post-filter.
        """
        acl = _acl_clause("n", repository_id, acl_scope)
        params: dict[str, Any] = {"id": node_ref}
        params.update(_acl_params(repository_id, acl_scope))
        rec = self._run_value(
            "MATCH (n) WHERE (n.knowledge_id = $id OR n.doc_id = $id "
            "OR n.step_id = $id OR n.entity_id = $id OR elementId(n) = $id) "
            f"AND {acl} "
            "RETURN elementId(n) AS node_id, labels(n) AS labels, properties(n) AS properties",
            params,
        )
        if rec is None:
            return None
        return {
            "id": rec["node_id"],
            "labels": list(rec["labels"]),
            "properties": dict(rec["properties"]),
        }

    def _neighbors(
        self,
        node_id: str,
        rels: str,
        limit: int,
        *,
        repository_id: str = "",
        acl_scope: str = "",
    ) -> list[dict[str, Any]]:
        """Return up to ``limit`` neighbors of ``node_id`` (elementId) over ``rels``.

        ``rels`` is a ``|``-joined allowlist built from ``ALLOWED_EXPANSION_RELS``
        (fixed, safe identifiers), so it is safe to interpolate into the pattern.
        Each neighbor carries the traversed relationship type (``type(r)``) so the
        caller can score the hop with the correct relationship weight.

        The traversal ACL is enforced on EVERY HOP: ``m`` must satisfy
        ``_acl_clause`` inside the Cypher (never a post-filter).
        """
        acl = _acl_clause("m", repository_id, acl_scope)
        params: dict[str, Any] = {"id": node_id, "limit": limit}
        params.update(_acl_params(repository_id, acl_scope))
        records = self._run(
            f"MATCH (n)-[r:{rels}]-(m) WHERE elementId(n) = $id AND {acl} "
            "RETURN DISTINCT elementId(m) AS node_id, labels(m) AS labels, "
            "properties(m) AS properties, type(r) AS rel_type LIMIT $limit",
            params,
        )
        return [
            {
                "id": rec["node_id"],
                "labels": list(rec["labels"]),
                "properties": dict(rec["properties"]),
                "rel_type": rec["rel_type"],
            }
            for rec in records
        ]

    def expand_candidates(
        self,
        seed_ids: list[str],
        *,
        max_depth: int = 2,
        max_neighbors: int = 8,
        max_nodes: int = 40,
        timeout_ms: int = 300,
        repository_id: str = "",
        acl_scope: str = "",
        rels: frozenset[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return the bounded, allowlisted neighborhood of one or more seed nodes.

        BFS over the relationship allowlist (``rels`` or the full ``ALLOWED_EXPANSION_RELS``
        by default), bounded by depth (<= ``max_depth``), neighbors per node per hop
        (<= ``max_neighbors``), total nodes (<= ``max_nodes``), and wall-clock time
        (<= ``timeout_ms``). ``seed_ids`` are canonical cross-store ids (knowledge_id /
        doc_id / step_id / entity_id); a seed that cannot be resolved is skipped cleanly.
        ``rels`` lets a caller narrow the traversal — the impact expansion passes
        ``IMPACT_EXPANSION_RELS`` (version history is not a blast-radius edge) while
        retrieval keeps the full allowlist. Backward compatible: ``None`` (default) is the
        full ``ALLOWED_EXPANSION_RELS``.

        TRAVERSAL ACL (design §5.5, finding 2): when BOTH ``repository_id`` and
        ``acl_scope`` are supplied, the seed resolution AND every Cypher hop
        constrain nodes to those exact tenancy values (fail-closed for versioned
        nodes missing either). When either is omitted, the legacy-only default
        applies: versioned nodes (``ModuleVersion``/``SymbolVersion``) are NEVER
        traversed — only unversioned legacy nodes are reachable. This is enforced
        inside the queries, never as a post-filter.

        Each returned node carries its canonical id (property-derived, elementId
        fallback), the traversed relationship type, the BFS depth, the path of
        canonical ids from its origin seed, and the origin seed's canonical id —
        everything the retrieval leg needs to score the hop as
        ``seed_score * weight * 0.7**depth``. Seeds first (depth 0), then
        breadth-first. Pure read.
        """
        rels = "|".join(sorted(rels or ALLOWED_EXPANSION_RELS))
        deadline = time.monotonic() + timeout_ms / 1000.0

        visited: dict[str, dict[str, Any]] = {}  # keyed by elementId (insertion-ordered)
        frontier: list[str] = []

        for seed in seed_ids:
            if len(visited) >= max_nodes:
                break
            node = self._resolve_node(
                seed, repository_id=repository_id, acl_scope=acl_scope
            )
            if node is None:
                continue  # unresolvable seed → skipped cleanly, never a zero-score hit
            elem = node["id"]
            if elem in visited:
                continue
            cid = _canonical_id(node["properties"], elem)
            visited[elem] = {
                "id": elem,
                "canonical_id": cid,
                "labels": node["labels"],
                "properties": node["properties"],
                "rel_type": "",
                "depth": 0,
                "path": [cid],
                "origin_seed": seed,
            }
            frontier.append(elem)

        for depth in range(1, max_depth + 1):
            if time.monotonic() > deadline or len(visited) >= max_nodes:
                break
            next_frontier: list[str] = []
            for elem in frontier:
                if time.monotonic() > deadline or len(visited) >= max_nodes:
                    break
                parent = visited[elem]
                for neighbor in self._neighbors(
                    elem, rels, max_neighbors, repository_id=repository_id, acl_scope=acl_scope
                ):
                    n_elem = neighbor["id"]
                    if n_elem in visited:
                        continue
                    n_cid = _canonical_id(neighbor["properties"], n_elem)
                    visited[n_elem] = {
                        "id": n_elem,
                        "canonical_id": n_cid,
                        "labels": neighbor["labels"],
                        "properties": neighbor["properties"],
                        "rel_type": neighbor["rel_type"],
                        "depth": depth,
                        "path": parent["path"] + [n_cid],
                        "origin_seed": parent["origin_seed"],
                    }
                    next_frontier.append(n_elem)
                    if len(visited) >= max_nodes:
                        break
            frontier = next_frontier

        return list(visited.values())

    def find_exact(
        self,
        label: str,
        property_name: str,
        value: Any,
        *,
        limit: int = 10,
        commit: str | None = None,
    ) -> list[dict[str, Any]]:
        """Exact-property lookup on a node label (no hand-written Cypher).

        ``label`` and ``property_name`` are validated identifiers; ``value`` is
        parameterized. Returns matching nodes as ``{"id", "labels",
        "properties"}`` dicts.

        ``commit`` is an optional HARD commit pre-filter: when supplied, a matched
        node is returned only if its ``commit_sha`` equals ``commit`` or is absent
        (``IS NULL``). A node with a non-matching, non-null ``commit_sha`` is
        excluded. Omitted → no filter (back-compatible).
        """
        _validate_identifier(label, "label")
        _validate_identifier(property_name, "property")
        params: dict[str, Any] = {"value": value, "limit": limit}
        query = f"MATCH (n:{label}) WHERE n.{property_name} = $value "
        if commit:
            # Hard commit pre-filter: only current (or unknown/absent) commits pass.
            query += "AND (n.commit_sha = $commit OR n.commit_sha IS NULL) "
            params["commit"] = commit
        query += (
            "RETURN elementId(n) AS node_id, labels(n) AS labels, "
            "properties(n) AS properties LIMIT $limit"
        )
        records = self._run(query, params)
        return [self._node_dict(rec) for rec in records]

    def search_fulltext(
        self, index_name: str, query: str, *, limit: int = 10, commit: str | None = None
    ) -> list[dict[str, Any]]:
        """Full-text search against a named native full-text index.

        ``index_name`` references an index created by ``create_knowledge_schema``
        (e.g. ``"step_text_ft"``). Returns matching nodes as ``{"id", "labels",
        "properties", "score"}`` dicts, highest score first.

        ``commit`` is an optional HARD commit pre-filter: when supplied, a matched
        node is returned only if its ``commit_sha`` equals ``commit`` or is absent
        (``IS NULL`` — e.g. ``Step`` nodes carry no commit). A node with a
        non-matching, non-null ``commit_sha`` is excluded. Omitted → no filter
        (back-compatible).
        """
        _validate_identifier(index_name, "index")
        params: dict[str, Any] = {"index": index_name, "query": query, "limit": limit}
        query_str = "CALL db.index.fulltext.queryNodes($index, $query) YIELD node, score "
        if commit:
            # Hard commit pre-filter on the lexical leg — mirrors the dense leg's
            # where filter and the fusion-time exclusion in freshness_multiplier.
            query_str += "WHERE node.commit_sha = $commit OR node.commit_sha IS NULL "
            params["commit"] = commit
        query_str += (
            "RETURN elementId(node) AS node_id, labels(node) AS labels, "
            "properties(node) AS properties, score "
            "LIMIT $limit"
        )
        records = self._run(query_str, params)
        return [self._node_dict(rec, with_score=True) for rec in records]

    def search_knowledge_fulltext(
        self, query: str, *, limit: int = 10, commit: str | None = None
    ) -> list[dict[str, Any]]:
        """Full-text search over ``Knowledge.text`` (the ``knowledge_text_ft`` index).

        The lexical retrieval leg must surface *knowledge* records — findings, code,
        and policy (authority MEASURED / SOURCE / POLICY) — never the reasoning
        ``Step`` nodes (authority ADVISORY) that ``search_fulltext("step_text_ft",
        ...)`` returns. Mirrors :meth:`search_fulltext`'s result shape
        (``{"id", "labels", "properties", "score"}`` dicts, highest score first)
        and its hard commit pre-filter, but scoped to the ``Knowledge`` label so the
        ingested KB (``knowledge_id`` / ``entity_id`` / ``text`` / ``authority`` /
        ``source_type`` / ``commit_sha``) is what the lexical leg actually retrieves.
        """
        return self.search_fulltext("knowledge_text_ft", query, limit=limit, commit=commit)
