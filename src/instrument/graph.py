"""Neo4j knowledge graph population for the experiment ecosystem.

Models experiments as an interconnected graph: models, configs, runs,
perturbation operators, strategies, and basin topologies.
"""

from __future__ import annotations

import contextlib
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


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

    def __init__(self, uri: str = "bolt://localhost:7687", user: str = "neo4j",
                 password: str = "password123"):  # local dev only — override via ENV for prod
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
            self._run("""
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
            """, {
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
            })

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

            self._run("""
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
            """, props)

    def link_runs(self) -> None:
        queries = [
            "MATCH (r:ExperimentRun) MATCH (m:Model {model_id: r.model}) "
            "MERGE (r)-[:RUN_ON]->(m)",
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
        if basin_path is None:
            basin_path = PROJECT_ROOT / "experiments" / "results" / "lab_basin_topology.json"
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

            self._run("""
                MERGE (bt:BasinTopology {model_id: $model_id})
                SET bt.model_label = $label,
                    bt.total_sessions = $total_sessions,
                    bt.valid_sessions = $valid_sessions,
                    bt.flail_count = $flail_count,
                    bt.flail_rate = $flail_rate,
                    bt.overall_escape = $overall_escape,
                    bt.overall_correctness = $overall_correctness,
                    bt.overall_cost = $overall_cost
            """, {
                "model_id": model_id,
                "label": model_label,
                "total_sessions": profile.get("total_sessions", 0),
                "valid_sessions": profile.get("valid_sessions", 0),
                "flail_count": profile.get("flail_count", 0),
                "flail_rate": profile.get("flail_rate", 0),
                "overall_escape": profile.get("overall_escape", 0),
                "overall_correctness": profile.get("overall_correctness", 0),
                "overall_cost": profile.get("overall_cost", 0),
            })

            self._run(
                "MATCH (m:Model {model_id: $model_id}) "
                "MATCH (bt:BasinTopology {model_id: $model_id}) "
                "MERGE (m)-[:HAS_BASIN]->(bt)",
                {"model_id": model_id},
            )

            for pclass, bp in profile.get("basin_profiles", {}).items():
                profile_id = f"{model_id}_{pclass}"
                self._run("""
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
                """, {
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
                })

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
            self._run("""
                MERGE (c:ExperimentConfig {name: $name})
                SET c.task = $task,
                    c.model = $model,
                    c.constraints_count = $constraints_count,
                    c.operator_count = $operator_count,
                    c.standardized = $standardized
            """, {
                "name": name,
                "task": cfg.get("task", "")[:500],
                "model": cfg.get("model", ""),
                "constraints_count": len(cfg.get("constraints", [])),
                "operator_count": len(cfg.get("operators", [])),
                "standardized": cfg.get("standardized", {}).get("enabled", False),
            })

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

    def build_step_graph(self, chroma_collection: str = "session_embeddings",
                         max_steps: int = 0) -> dict[str, int]:
        """Create Step nodes and relationships from session.jsonl files.

        Reads reasoning steps directly from session files using extract_session_steps,
        avoiding ChromaDB dependency. Each step becomes a :Step node with
        :HAS_STEP and :NEXT relationships.
        """
        sys.path.insert(0, str(PROJECT_ROOT / "src"))
        from instrument.embeddings import extract_session_steps

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
                self._run("""
                    MERGE (st:Step {step_id: $step_id})
                    SET st.session_id = $sid,
                        st.step_index = $step_index,
                        st.tool_after = $tool_after,
                        st.doc_id = ''
                """, {
                    "step_id": step_id,
                    "sid": sid,
                    "step_index": si,
                    "tool_after": step.get("tool_after", ""),
                })
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
