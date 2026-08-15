"""Lab book integration — persist experiment results as YAML-frontmatter markdown."""

from __future__ import annotations

import warnings
from pathlib import Path

from .experiment import ExperimentConfig, ExperimentResult

warnings.warn(
    "instrument.lab_book is deprecated. Lab scripts bypass this module; "
    "use instrument.opencode_analyzer for current pipeline.",
    DeprecationWarning, stacklevel=2,
)

_MANIFOLD_OPS = {"inject_alien_vocab", "shift_framing", "reverse_causality", "force_abandonment"}


def build_hypothesis(config: ExperimentConfig) -> tuple[dict, dict]:
    h0 = {"text": f"Under perturbation at strengths {config.strengths}, no systematic difference in trajectory deviation between manifold and semantic perturbation classes.", "status": "untested"}
    h1 = {"text": "Manifold perturbations produce higher trajectory deviation and slower recovery than semantic perturbations because semantic perturbations operate within the model's existing concept manifold."}
    return h0, h1


def build_methodology(config: ExperimentConfig) -> dict:
    return {
        "design": f"Multi-turn experiment with {len(config.operators)} operators at strengths {config.strengths}. Content-based trajectory distance measured per turn.",
        "variables": {"independent": "perturbation class and strength", "dependent": "escape score, recovery ratio", "controlled": "model, task, turns, seed"},
        "sample_size": len(config.operators) * len(config.strengths),
        "limitations": ["Single-model tested", "Heuristic distance metric", "Single run per cell"],
    }


def persist_to_lab_book(result: ExperimentResult, output_dir: Path | None = None) -> Path:
    import yaml

    dest = output_dir or Path("experiments/results")
    dest.mkdir(parents=True, exist_ok=True)

    eid = result.config.name
    h0, h1 = build_hypothesis(result.config)
    build_methodology(result.config)

    by_cls = {"manifold": [], "semantic": []}
    for r in result.runs:
        cls = "manifold" if r.operator in _MANIFOLD_OPS else "semantic"
        by_cls[cls].append(r.basin.escape_score)

    m_avg = sum(by_cls["manifold"]) / len(by_cls["manifold"]) if by_cls["manifold"] else 0
    s_avg = sum(by_cls["semantic"]) / len(by_cls["semantic"]) if by_cls["semantic"] else 0

    conclusion = {"null_status": "rejected" if m_avg > s_avg + 0.15 else "not_rejected", "reasoning": f"Manifold avg: {m_avg:.3f}, Semantic avg: {s_avg:.3f}, Delta: {m_avg-s_avg:+.3f}."}

    fm = {
        "experiment_id": eid, "timestamp": result.started_at, "model": result.config.model,
        "task": result.config.task[:200], "operators": result.config.operators, "strengths": result.config.strengths,
        "total_tokens": result.total_tokens, "total_cost_usd": round(result.total_cost_usd, 6),
        "null_hypothesis": h0["text"], "alternative_hypothesis": h1["text"],
        "null_status": conclusion["null_status"], "conclusion_reasoning": conclusion["reasoning"],
    }

    body = [f"# Experiment: {eid}", "", f"**Model:** {result.config.model} | **Cost:** {result.total_tokens} tokens, ${result.total_cost_usd:.4f}", "",
            "## Results", "", "| Operator | Strength | Escape | Recovery | Class | Verdict |",
            "|----------|----------|--------|----------|-------|---------|"]

    for r in result.runs:
        cls = "manifold" if r.operator in _MANIFOLD_OPS else "semantic"
        try:
            rr = getattr(r, "recovery_ratio", r.basin.thinking_ratio)
        except Exception:
            rr = 0.0
        body.append(f"| {r.operator} | {r.strength} | {r.basin.escape_score:.3f} | {rr:.3f} | {cls} | {r.basin.get_verdict()[:50]} |")

    body += ["", f"**Manifold avg escape:** {m_avg:.3f}  **Semantic avg escape:** {s_avg:.3f}  **Delta:** {m_avg-s_avg:+.3f}",
             "", "## Conclusion", f"**Null hypothesis:** {conclusion['null_status']}", f"**Reasoning:** {conclusion['reasoning']}"]

    content = f"---\n{yaml.dump(fm, default_flow_style=False, sort_keys=False, allow_unicode=True)}---\n\n" + "\n".join(body)
    fp = dest / f"{eid}.md"
    fp.write_text(content)
    return fp
