"""Reasoning trajectory capture and comparison.

Captures step-by-step reasoning traces from model execution and
computes semantic distances between trajectories — the foundation
for measuring basin escape and recovery behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TrajectoryStep:
    """A single step in a model's reasoning trajectory.

    Each step captures what the model thought, what action it took,
    and the result it observed. Together, steps form a complete
    trace of the reasoning process.
    """

    step_index: int
    thought: str = ""
    action: str = ""
    tool_name: str = ""
    tool_input: dict[str, Any] = field(default_factory=dict)
    observation: str = ""
    tokens_used: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_index": self.step_index,
            "thought": self.thought[:500],
            "action": self.action[:500],
            "tool_name": self.tool_name,
            "tool_input": {k: str(v)[:200] for k, v in self.tool_input.items()},
            "observation": self.observation[:500],
            "tokens_used": self.tokens_used,
        }


@dataclass
class ReasoningTrajectory:
    """A complete step-by-step trace of a model's reasoning process.

    Captured from the model's execution — every thought, tool call,
    and observation — forming a record that can be compared against
    baseline trajectories to measure exploration vs recovery behavior.
    """

    run_id: str
    model: str = ""
    task: str = ""
    perturbation_applied: str = ""
    perturbation_strength: float = 0.0

    steps: list[TrajectoryStep] = field(default_factory=list)
    total_tokens: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    cost_usd: float = 0.0
    exit_code: int | None = None
    duration_s: float | None = None

    def add_step(self, step: TrajectoryStep) -> None:
        self.steps.append(step)
        self.total_tokens += step.tokens_used

    def step_count(self) -> int:
        return len(self.steps)

    def tool_call_sequence(self) -> list[str]:
        """Return the sequence of tool names called, in order."""
        return [s.tool_name for s in self.steps if s.tool_name]

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "model": self.model,
            "task": self.task[:200],
            "perturbation_applied": self.perturbation_applied,
            "perturbation_strength": self.perturbation_strength,
            "steps": [s.to_dict() for s in self.steps],
            "step_count": self.step_count(),
            "total_tokens": self.total_tokens,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "cost_usd": self.cost_usd,
            "exit_code": self.exit_code,
            "duration_s": self.duration_s,
        }


def compute_trajectory_distance(
    baseline: ReasoningTrajectory,
    perturbed: ReasoningTrajectory,
) -> float:
    """Compute a semantic distance between two reasoning trajectories.

    v1 uses proxy metrics (no embedding access assumed):
    - Step count ratio
    - Token count ratio
    - Tool call sequence similarity (Levenshtein ratio)
    - Content distance (text length ratio + word overlap)

    Returns a distance in [0.0, 1.0] where:
    - 0.0 = identical trajectories
    - 1.0 = maximally different trajectories

    This is a behavioral proxy, not true embedding distance.
    When embedding access is available, upgrade to cosine distance
    over trajectory embeddings.
    """
    scores: list[float] = []

    # Step count ratio
    if baseline.step_count() > 0:
        step_ratio = abs(perturbed.step_count() - baseline.step_count()) / max(
            baseline.step_count(), perturbed.step_count(), 1
        )
        scores.append(step_ratio)

    # Token count ratio
    if baseline.total_tokens > 0:
        token_ratio = abs(perturbed.total_tokens - baseline.total_tokens) / max(
            baseline.total_tokens, perturbed.total_tokens, 1
        )
        scores.append(token_ratio)

    # Tool call sequence edit distance
    baseline_tools = baseline.tool_call_sequence()
    perturbed_tools = perturbed.tool_call_sequence()
    max_len = max(len(baseline_tools), len(perturbed_tools), 1)
    edit_dist = _levenshtein(baseline_tools, perturbed_tools)
    scores.append(edit_dist / max_len)

    # Content distance — compare actual response text
    content_dist = _content_distance(baseline, perturbed)
    scores.append(content_dist)

    # Average across available metrics
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def _levenshtein(a: list[str], b: list[str]) -> int:
    """Compute Levenshtein edit distance between two sequences."""
    n, m = len(a), len(b)
    if n == 0:
        return m
    if m == 0:
        return n

    prev = list(range(m + 1))
    for i in range(1, n + 1):
        curr = [i] + [0] * m
        for j in range(1, m + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
        prev = curr

    return prev[m]


def _content_distance(
    baseline: ReasoningTrajectory,
    perturbed: ReasoningTrajectory,
) -> float:
    """Compute content-level distance between two trajectories.

    v2: Uses TEI embeddings when available for semantic distance,
    falling back to heuristic trigram overlap when embeddings are
    unavailable (no GPU pod).

    Compares corresponding steps using response length ratio,
    surface overlap, structural similarity, and when available,
    cosine distance between text embeddings.
    """
    n = min(baseline.step_count(), perturbed.step_count())
    if n == 0:
        return 0.0

    # Try embedding-based distance first
    embedding_dist = _embedding_distance(baseline, perturbed, n)
    if embedding_dist is not None:
        return embedding_dist

    # Fallback: heuristic comparison
    per_step_dists = []
    for i in range(n):
        bt = baseline.steps[i].action.strip()
        pt = perturbed.steps[i].action.strip()
        if not bt and not pt:
            continue

        bl, pl = max(len(bt), 1), max(len(pt), 1)
        len_ratio = abs(bl - pl) / max(bl, pl)

        b_words = _char_trigrams(bt.lower())
        p_words = _char_trigrams(pt.lower())
        union = len(b_words | p_words)
        intersection = len(b_words & p_words)
        overlap = intersection / max(union, 1)
        overlap_dist = 1.0 - overlap

        b_is_code = _is_code_like(bt)
        p_is_code = _is_code_like(pt)
        struct_dist = 0.0 if b_is_code == p_is_code else 0.5

        per_step_dists.append((len_ratio + overlap_dist + struct_dist) / 3.0)

    if not per_step_dists:
        return 0.0
    return sum(per_step_dists) / len(per_step_dists)


def _char_trigrams(text: str) -> set[str]:
    """Extract character trigrams for surface similarity."""
    # Also include word bigrams for better content matching
    words = text.split()
    trigrams = set()
    for i in range(len(text) - 2):
        trigrams.add(text[i:i + 3])
    for i in range(len(words) - 1):
        trigrams.add(f"W:{words[i]}_{words[i + 1]}")
    return trigrams


def _is_code_like(text: str) -> bool:
    """Heuristic to detect if text is code (vs prose)."""
    code_indicators = [
        "def ", "class ", "import ", "from ", "return ",
        "func ", "struct ", "fn ", "const ", "let ",
        "@app", "@route", "endpoint",
        "curl", "GET ", "POST ",
    ]
    prose_indicators = [
        "the ", "and ", "for ", "with ", "that ",
        "this ", "have ", "from ", "they ", "what ",
    ]
    code_score = sum(1 for ci in code_indicators if ci in text.lower())
    prose_score = sum(1 for pi in prose_indicators if pi in text.lower())
    return code_score > prose_score


def _embedding_distance(
    baseline: ReasoningTrajectory,
    perturbed: ReasoningTrajectory,
    n: int,
) -> float | None:
    """Compute cosine distance between trajectory steps using bge-m3 embeddings.

    Uses the local EmbeddingClient (Ollama + bge-m3) for true semantic
    distance. Falls back to the heuristic trigram approach in _content_distance
    when embeddings are unavailable.

    Returns distance in [0.0, 1.0], or None if embeddings unavailable.
    """
    baseline_texts = [baseline.steps[i].action.strip() for i in range(n)]
    perturbed_texts = [perturbed.steps[i].action.strip() for i in range(n)]

    try:
        from .embeddings import EmbeddingClient

        client = EmbeddingClient()
        return client.embedding_distance(baseline_texts, perturbed_texts)
    except Exception:
        return None
