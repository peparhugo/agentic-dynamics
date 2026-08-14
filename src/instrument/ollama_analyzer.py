"""Qualitative experiment analysis via DeepSeek R1 via Ollama.

Feeds game report metrics and session data to deepseek-r1:1.5b
for narrative commentary on experiment patterns.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class OllamaAnalyzer:
    """Analyze experiment data using DeepSeek R1 via Ollama."""

    SYSTEM_PROMPT = (
        "You are an experiment analyst reviewing AI inference cost measurement data. "
        "The data comes from a framework that measures model reasoning dynamics under "
        "perturbation. Analyze the data objectively and concisely."
    )

    def __init__(self, model: str = "deepseek-r1:1.5b"):
        self.model = model
        import ollama
        self._client = ollama

    def _ask(self, prompt: str) -> str:
        """Return visible model output, including reasoning-only Ollama replies."""
        try:
            response = self._client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                options={"temperature": 0.3, "num_predict": 1024},
            )
            content = response.message.content.strip()
            if content:
                return content
            # Reasoning models may exhaust their prediction budget before
            # producing final content while still returning useful thinking.
            thinking = str(getattr(response.message, "thinking", "") or "").strip()
            return thinking or "[Analysis error: Ollama returned an empty response]"
        except Exception as e:
            return f"[Analysis error: {e}]"

    def analyze_session(self, session_jsonl_path: Path) -> str:
        reasoning_text = ""
        total_cost = 0
        step_count = 0
        tool_counts: dict[str, int] = {}

        with open(session_jsonl_path) as f:
            for line in f:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if event.get("type") == "reasoning":
                    t = event.get("text", "")
                    if t.strip():
                        reasoning_text += t[:2000] + "\n---\n"

                elif event.get("type") == "tool":
                    tool_name = event.get("tool", "?")
                    tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1

                elif event.get("type") == "step-finish":
                    total_cost += float(event.get("cost", 0))
                    step_count += 1

        prompt = f"""Analyze this experiment session:

Steps: {step_count}
Cost: ${total_cost:.4f}
Tool usage: {tool_counts}

Reasoning excerpt:
{reasoning_text[:4000]}

Provide a 3-4 sentence analysis of:
1. The model's problem-solving approach
2. Whether it seemed efficient or wasteful
3. Any notable patterns in tool usage"""

        return self._ask(prompt)

    def summarize_experiment(self, metrics: dict[str, Any]) -> str:
        prompt = f"""Summarize this experiment run:

Model: {metrics.get('model', 'unknown')}
Experiment: {metrics.get('experiment', 'unknown')}
Operator: {metrics.get('operator', 'unknown')}
Perturbation class: {metrics.get('perturbation_class', 'unknown')}
Cost: ${metrics.get('cost', 0):.4f}
Correctness: {metrics.get('correctness', 0):.2f}
Strategy: {metrics.get('strategy', '?')}
Escape: {metrics.get('escape', 0):.2f}
Code lines: {metrics.get('code_lines', 0)}
Tokens: {metrics.get('tokens', 0)}
Thinking ratio: {metrics.get('thinking_ratio', 0):.2f}
Constraints met: {metrics.get('constraints_met', 0)}/{metrics.get('constraints_total', 0)}
Architecture divergence: {metrics.get('architecture_divergence', 0):.2f}
Structure divergence: {metrics.get('structure_divergence', 0):.2f}
Novelty: {metrics.get('novelty_score', 0):.2f}

Provide a 2-3 sentence analysis of this run's performance profile."""

        return self._ask(prompt)

    def compare_sessions(
        self, baseline_metrics: dict[str, Any], perturbed_metrics: dict[str, Any],
    ) -> str:
        prompt = f"""Compare two experiment runs:

BASELINE:
Model: {baseline_metrics.get('model', 'unknown')}
Cost: ${baseline_metrics.get('cost', 0):.4f}
Correctness: {baseline_metrics.get('correctness', 0):.2f}
Tokens: {baseline_metrics.get('tokens', 0)}
Strategy: {baseline_metrics.get('strategy', '?')}

PERTURBED:
Model: {perturbed_metrics.get('model', 'unknown')}
Operator: {perturbed_metrics.get('operator', 'unknown')}
Perturbation: {perturbed_metrics.get('perturbation_class', 'unknown')}
Cost: ${perturbed_metrics.get('cost', 0):.4f}
Correctness: {perturbed_metrics.get('correctness', 0):.2f}
Escape: {perturbed_metrics.get('escape', 0):.2f}
Tokens: {perturbed_metrics.get('tokens', 0)}
Strategy: {perturbed_metrics.get('strategy', '?')}

How did the perturbation affect the model's behavior? 2-3 sentences."""

        return self._ask(prompt)

    def batch_analyze(
        self,
        entries: list[dict[str, Any]],
        question: str = "What patterns do you see across these experiment runs?",
    ) -> str:
        summary_lines = []
        for i, e in enumerate(entries[:20]):
            summary_lines.append(
                f"{i+1}. {e.get('model','?')}/{e.get('experiment','?')}: "
                f"correctness={e.get('correctness',0):.2f}, "
                f"cost=${e.get('cost',0):.4f}, "
                f"strategy={e.get('strategy','?')}"
            )

        prompt = f"""Here are {min(len(entries), 20)} experiment runs:

{chr(10).join(summary_lines)}

{question}

Answer in 2-4 sentences."""

        return self._ask(prompt)


def load_summary_data(summary_path: Path | None = None) -> list[dict[str, Any]]:
    if summary_path is None:
        summary_path = PROJECT_ROOT / "experiments" / "results" / "_results_summary.json"
    if not summary_path.exists():
        return []
    data = json.loads(summary_path.read_text())
    return data.get("entries", [])
