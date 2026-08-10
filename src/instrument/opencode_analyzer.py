"""Qualitative experiment analysis via opencode harness with DeepSeek.

Spawns recorded opencode sessions (like the experiments themselves) but
with analysis prompts instead of coding tasks. Each analysis run produces
a full session.jsonl trace — making it a meta-experiment: the model
analyzing the model's own behavior, measured by the same instrument.

Uses deepseek/deepseek-v4-flash by default for speed and cost efficiency.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .opencode import run_opencode_agentic, AgenticResult

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS_DIR = PROJECT_ROOT / "experiments" / "results"
REPORTS_DIR = RESULTS_DIR / "reports"
SUMMARY_PATH = RESULTS_DIR / "_results_summary.json"


def _load_summary() -> list[dict[str, Any]]:
    if not SUMMARY_PATH.exists():
        return []
    return json.loads(SUMMARY_PATH.read_text()).get("entries", [])


def _load_session_jsonl(worktree_name: str) -> str | None:
    session_path = REPORTS_DIR / worktree_name / "session.jsonl"
    if not session_path.exists():
        return None
    return session_path.read_text()


def _resolve_worktree(name_or_id: str) -> str:
    candidate = REPORTS_DIR / name_or_id
    if candidate.is_dir() and (candidate / "session.jsonl").exists():
        return name_or_id
    entries = _load_summary()
    for e in entries:
        if e.get("worktree_name") == name_or_id:
            return name_or_id
        if e.get("experiment", "").startswith(name_or_id):
            return e["worktree_name"]
    return name_or_id


def _build_session_prompt(worktree_name: str) -> str:
    metrics = {}
    entries = _load_summary()
    for e in entries:
        if e.get("worktree_name") == worktree_name:
            metrics = e
            break

    session_text = _load_session_jsonl(worktree_name) or "(no session trace available)"

    return f"""Analyze this experiment session from an AI inference cost measurement framework.

## Session: {worktree_name}
- Model: {metrics.get('model', 'unknown')}
- Experiment: {metrics.get('experiment', 'unknown')}
- Operator: {metrics.get('operator', 'unknown')}
- Perturbation class: {metrics.get('perturbation_class', 'unknown')}
- Cost: ${metrics.get('cost', 0):.4f}
- Correctness: {metrics.get('correctness', 0):.2f}
- Strategy: {metrics.get('strategy', '?')}
- Escape: {metrics.get('escape', 0):.2f}
- Code lines: {metrics.get('code_lines', 0)}
- Tokens: {metrics.get('tokens', 0)}
- Thinking ratio: {metrics.get('thinking_ratio', 0):.2f}
- Constraints met: {metrics.get('constraints_met', 0)}/{metrics.get('constraints_total', 0)}

## Session Transcript (session.jsonl)
```
{session_text[:8000]}
```

Write your analysis to a file called analysis.md in the current directory.
Include:
1. Problem-solving approach assessment
2. Efficiency analysis (was token usage appropriate?)
3. Notable patterns in tool usage and reasoning
4. Overall verdict (conservative/exploratory/wasteful/efficient — or your own assessment)

Be concise and data-driven. Reference specific metrics when possible."""


def _build_comparison_prompt(baseline_name: str, perturbed_name: str) -> str:
    entries = _load_summary()
    bm = next((e for e in entries if e.get("worktree_name") == baseline_name), {})
    pm = next((e for e in entries if e.get("worktree_name") == perturbed_name), {})

    b_session = _load_session_jsonl(baseline_name) or "(no trace)"
    p_session = _load_session_jsonl(perturbed_name) or "(no trace)"

    return f"""Compare two AI inference experiment sessions — a baseline and a perturbed run.

## Baseline: {baseline_name}
- Cost: ${bm.get('cost', 0):.4f}
- Correctness: {bm.get('correctness', 0):.2f}
- Strategy: {bm.get('strategy', '?')}
- Tokens: {bm.get('tokens', 0)}

## Perturbed: {perturbed_name}
- Operator: {pm.get('operator', '?')}
- Perturbation class: {pm.get('perturbation_class', '?')}
- Cost: ${pm.get('cost', 0):.4f}
- Correctness: {pm.get('correctness', 0):.2f}
- Escape: {pm.get('escape', 0):.2f}
- Strategy: {pm.get('strategy', '?')}
- Tokens: {pm.get('tokens', 0)}

## Baseline Session (first 5000 chars)
```
{b_session[:5000]}
```

## Perturbed Session (first 5000 chars)
```
{p_session[:5000]}
```

Write your comparison to comparison.md. Address:
1. How did the perturbation change the model's behavior?
2. Was the cost difference justified?
3. Did correctness degrade meaningfully?
4. What does the escape score tell us about the model's resilience?"""


def _build_batch_prompt(entries: list[dict[str, Any]], question: str) -> str:
    lines = []
    for i, e in enumerate(entries[:25]):
        lines.append(
            f"{i+1}. {e.get('model','?')}/{e.get('experiment','?')}: "
            f"correctness={e.get('correctness',0):.2f}, "
            f"cost=${e.get('cost',0):.4f}, "
            f"strategy={e.get('strategy','?')}, "
            f"escape={e.get('escape',0):.2f}"
        )

    return f"""Analyze these experiment runs from an AI inference cost measurement framework.

{chr(10).join(lines)}

Question: {question}

Write your analysis to analysis.md. Be concise — 3-5 bullet points maximum.
Reference specific runs by number when making claims."""


class OpencodeAnalyzer:
    """Analyze experiment data using opencode harness with DeepSeek.

    Each analysis call spawns a real opencode session — producing a
    measured, costed, traceable result. The analysis itself becomes
    an experiment that can be analyzed by the same pipeline.

    Args:
        model: opencode model ID. Defaults to deepseek-v4-flash for speed.
        timeout: Session timeout in seconds.
    """

    def __init__(self, model: str = "deepseek/deepseek-v4-flash", timeout: int = 300):
        self.model = model
        self.timeout = timeout

    def analyze_session(self, worktree_name: str) -> AgenticResult:
        name = _resolve_worktree(worktree_name)
        prompt = _build_session_prompt(name)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        session_name = f"meta_analyze_{name}_{ts}"
        return run_opencode_agentic(
            prompt,
            model=self.model,
            timeout=self.timeout,
            session_name=session_name,
            standardize=False,
            enforce_pytest=False,
        )

    def compare_sessions(self, baseline: str, perturbed: str) -> AgenticResult:
        bn = _resolve_worktree(baseline)
        pn = _resolve_worktree(perturbed)
        prompt = _build_comparison_prompt(bn, pn)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        session_name = f"meta_compare_{bn}_vs_{pn}_{ts}"
        return run_opencode_agentic(
            prompt,
            model=self.model,
            timeout=self.timeout,
            session_name=session_name,
            standardize=False,
            enforce_pytest=False,
        )

    def batch_analyze(
        self, entries: list[dict[str, Any]], question: str,
    ) -> AgenticResult:
        prompt = _build_batch_prompt(entries, question)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        session_name = f"meta_batch_{ts}"
        return run_opencode_agentic(
            prompt,
            model=self.model,
            timeout=self.timeout,
            session_name=session_name,
            standardize=False,
            enforce_pytest=False,
        )

    def analyze_filtered(
        self, key: str, value: str, question: str = "", limit: int = 25,
    ) -> AgenticResult:
        entries = _load_summary()
        filtered = [e for e in entries if str(e.get(key, "")) == value]
        if not filtered:
            raise ValueError(f"No entries matching {key}={value}")

        q = question or f"What characterizes these {key}={value} runs?"
        prompt = _build_batch_prompt(filtered[:limit], q)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        session_name = f"meta_filter_{key}_{value}_{ts}"
        return run_opencode_agentic(
            prompt,
            model=self.model,
            timeout=self.timeout,
            session_name=session_name,
            standardize=False,
            enforce_pytest=False,
        )

    def analyze_model(self, model_id: str, question: str = "") -> AgenticResult:
        entries = _load_summary()
        model_entries = [e for e in entries if e.get("model") == model_id]
        if not model_entries:
            raise ValueError(f"No entries for model {model_id}")

        q = question or f"What patterns emerge across {model_id} experiments?"
        return self.batch_analyze(model_entries, q)
