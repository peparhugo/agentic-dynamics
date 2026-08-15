"""Token recovery analysis — distinguish exploration from recovery.

When a model is perturbed into unfamiliar reasoning territory, some
of its output tokens represent genuine exploration while others
represent a return journey back to familiar patterns. This module
classifies trajectory segments and computes the ratio.

The key insight: models trained on imitation-heavy objectives tend
to burn tokens rationalizing their way back to known patterns. Models
trained with outcome-oriented RL are more willing to stay in novel
territory. The recovery ratio quantifies this difference.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .trajectory import ReasoningTrajectory


class SegmentClass(str, Enum):
    """Classification of a trajectory segment."""

    EXPLORATION = "exploration"
    RECOVERY = "recovery"
    STABLE = "stable"
    UNKNOWN = "unknown"


@dataclass
class SegmentClassification:
    """Classification of a single step in a trajectory."""

    step_index: int
    classification: SegmentClass = SegmentClass.UNKNOWN
    confidence: float = 0.0
    reason: str = ""
    tokens: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_index": self.step_index,
            "classification": self.classification.value,
            "confidence": round(self.confidence, 4),
            "reason": self.reason,
            "tokens": self.tokens,
        }


def classify_trajectory_segments(
    baseline: ReasoningTrajectory,
    perturbed: ReasoningTrajectory,
    *,
    recovery_markers: list[str] | None = None,
) -> list[SegmentClassification]:
    """Classify each step of a perturbed trajectory.

    Segments are classified as:
    - EXPLORATION: moving away from baseline, exploring novel territory
    - RECOVERY: moving back toward baseline, using recovery patterns
    - STABLE: at distance equilibrium, productively using position

    Args:
        baseline: The unperturbed trajectory for comparison.
        perturbed: The perturbed trajectory to classify.
        recovery_markers: Text patterns that indicate recovery behavior.
                          Uses default markers if None.

    Returns:
        List of SegmentClassification, one per step.

    Recovery detection uses multiple signals:
    1. Surface markers: rationalization phrases ("let me explain",
       "here's why", "to clarify", qualification language, etc.)
    2. Behavioral convergence: tool calls returning to baseline patterns
    3. Qualification/hedging: language markers indicating uncertainty
    4. Tech term convergence: matching technology vocabulary from baseline
    5. Step length convergence: response length approaching baseline
    6. Structural pattern convergence: same section headers/numbering
    7. Trajectory distance: Jaccard distance of tool-call sets from baseline
    """
    markers = recovery_markers or _default_recovery_markers()
    baseline_tools_set = set(baseline.tool_call_sequence())
    baseline.tool_call_sequence()
    perturbed_tool_seq = perturbed.tool_call_sequence()

    # Build index maps: for each step index, what position in the filtered tool sequence?
    perturbed_step_to_tool_idx: dict[int, int] = {}
    _tool_pos = 0
    for _i, _s in enumerate(perturbed.steps):
        if _s.tool_name:
            perturbed_step_to_tool_idx[_i] = _tool_pos
            _tool_pos += 1

    # Tool-sequence-position matching (not step-index matching).
    # Agentic transcripts naturally have variable step counts between
    # tool calls. Matching by tool occurrence order (0th tool vs 0th tool)
    # is more robust than matching by step index.
    # Map tool-sequence-position → tool_name for baseline.
    baseline_tool_by_pos: list[str] = []
    for _s in baseline.steps:
        if _s.tool_name:
            baseline_tool_by_pos.append(_s.tool_name)

    classifications: list[SegmentClassification] = []

    for i, step in enumerate(perturbed.steps):
        signals: list[tuple[float, str]] = []

        # Signal 1: surface recovery markers in thought/action text
        text = (step.thought + " " + step.action).lower()
        marker_hits = sum(1 for m in markers if m.lower() in text)
        if marker_hits > 0:
            confidence = min(marker_hits * 0.3, 0.9)
            signals.append((confidence, f"recovery markers found: {marker_hits}"))

        # Signal 2: behavioral convergence — using same tools as baseline
        if step.tool_name and step.tool_name in baseline_tools_set:
            pt_idx = perturbed_step_to_tool_idx.get(i)
            # Match by tool occurrence order, not step index
            baseline_match = (
                pt_idx is not None
                and pt_idx < len(perturbed_tool_seq)
                and pt_idx < len(baseline_tool_by_pos)
                and perturbed_tool_seq[pt_idx] == baseline_tool_by_pos[pt_idx]
            )
            if not baseline_match:
                signals.append((0.4, f"tool '{step.tool_name}' converges toward baseline"))

        # Signal 3: step text contains qualification/hedging
        qualifiers = [
            "however", "on the other hand", "that said", "nevertheless",
            "alternatively", "in contrast", "to be fair", "actually,",
            "upon reflection", "reconsidering", "upon further thought",
        ]
        qualifier_hits = sum(1 for q in qualifiers if q in text)
        if qualifier_hits > 0:
            signals.append((min(qualifier_hits * 0.2, 0.5), f"qualification markers: {qualifier_hits}"))

        # Signal 4: structural convergence — matching technology terms from baseline
        if i < len(baseline.steps):
            baseline_text = (baseline.steps[i].thought + " " + baseline.steps[i].action).lower()
            tech_terms = _extract_tech_terms(baseline_text)
            if tech_terms:
                matched = sum(1 for t in tech_terms if t in text)
                ratio = matched / len(tech_terms)
                if ratio >= 0.5:
                    signals.append((min(ratio, 0.9), f"tech convergence: {matched}/{len(tech_terms)} terms match baseline"))

        # Signal 5: step length convergence — response length approaching baseline
        if i < len(baseline.steps):
            baseline_len = len(baseline.steps[i].action) if baseline.steps[i].action else 1
            perturbed_len = len(step.action) if step.action else 1
            len_ratio = min(perturbed_len, baseline_len) / max(perturbed_len, baseline_len, 1)
            if len_ratio >= 0.8:
                signals.append((0.2, f"length convergence: ratio={len_ratio:.2f}"))

        # Signal 6: pattern convergence — same section headers as baseline
        if i < len(baseline.steps):
            baseline_patterns = _extract_patterns(baseline.steps[i].action)
            perturbed_patterns = _extract_patterns(step.action)
            if baseline_patterns and perturbed_patterns:
                overlap = len(baseline_patterns & perturbed_patterns)
                ratio = overlap / max(len(baseline_patterns), 1)
                if ratio >= 0.4:
                    signals.append((min(ratio, 0.7), f"pattern convergence: {overlap}/{len(baseline_patterns)} structures match"))

        # Signal 7: reasoning trajectory distance
        # Measures how far the perturbed trajectory has diverged from baseline
        # by comparing tool-occurrence Jaccard distance within each window
        baseline_tools = {s.tool_name for s in baseline.steps[:i+1] if s.tool_name}
        perturbed_tools = {s.tool_name for s in perturbed.steps[:i+1] if s.tool_name}
        union = baseline_tools | perturbed_tools
        if union:
            jaccard = len(baseline_tools & perturbed_tools) / len(union)
            trajectory_distance = 1.0 - jaccard
            if trajectory_distance > 0.3:
                signals.append((min(trajectory_distance, 0.8),
                                f"trajectory distance: {trajectory_distance:.2f}"))

        # Classify based on strongest signal
        if signals:
            best_confidence, best_reason = max(signals, key=lambda x: x[0])
            classification = SegmentClass.RECOVERY if best_confidence >= 0.3 else SegmentClass.EXPLORATION
            classifications.append(SegmentClassification(
                step_index=i,
                classification=classification,
                confidence=best_confidence,
                reason=best_reason,
                tokens=step.tokens_used,
            ))
        else:
            # Default: if no recovery signals, assume exploration
            classifications.append(SegmentClassification(
                step_index=i,
                classification=SegmentClass.EXPLORATION,
                confidence=0.5,
                reason="no recovery signals detected",
                tokens=step.tokens_used,
            ))

    return classifications


def recovery_token_ratio(
    classifications: list[SegmentClassification],
) -> tuple[int, int, float]:
    """Compute the recovery token ratio from step classifications.

    Returns:
        (exploration_tokens, recovery_tokens, recovery_ratio)
    """
    exploration = sum(s.tokens for s in classifications if s.classification == SegmentClass.EXPLORATION)
    recovery = sum(s.tokens for s in classifications if s.classification == SegmentClass.RECOVERY)
    total = exploration + recovery
    ratio = recovery / max(total, 1)
    return exploration, recovery, ratio


def _default_recovery_markers() -> list[str]:
    """Default surface markers for recovery/rationalization detection."""
    return [
        "let me explain",
        "here's why",
        "first, let's understand",
        "i'll break this down",
        "let me walk through",
        "to clarify",
        "in other words",
        "what this means is",
        "the reason for this",
        "this is because",
        "allow me to elaborate",
        "let me rephrase",
        "to put it simply",
        "let's step back",
        "perhaps i should",
        "actually, i think",
        "on second thought",
        "let me reconsider",
    ]


def _extract_tech_terms(text: str) -> set[str]:
    """Extract technology/architecture terms from text for convergence detection."""
    common_tech = {
        "flask", "django", "fastapi", "postgresql", "mysql", "sqlite",
        "redis", "mongodb", "postgres", "sqlalchemy", "docker",
        "kubernetes", "nginx", "aws", "gcp", "azure", "lambda",
        "rest", "graphql", "grpc", "websocket", "crud", "api",
        "crdt", "ot", "raft", "paxos", "event sourcing", "caching",
        "rate limiting", "token bucket", "jwt", "oauth", "cors",
        "orm", "migration", "serializer", "middleware", "blueprint",
        "celery", "rabbitmq", "kafka", "pubsub", "microservice",
        "monolith", "serverless", "container", "load balancer",
    }
    text_lower = text.lower()
    return {t for t in common_tech if t in text_lower}


def _extract_patterns(text: str) -> set[str]:
    """Extract structural patterns from text (headers, prefixes, code markers)."""
    patterns = set()
    # Markdown headers
    for match in re.finditer(r'^#{1,4}\s+(.+)$', text, re.MULTILINE):
        patterns.add(match.group(0)[:60])
    # Numbered/tagged sections
    for match in re.finditer(r'(?:(?:Step|Phase|Section|Part)\s*\d+|###\s*\w+|^\d+\.\s)', text, re.MULTILINE):
        patterns.add(match.group(0)[:40])
    # Technology/protocol mentions in all-caps
    for match in re.finditer(r'\b[A-Z]{2,}(?:\s*\([^)]+\))?\b', text):
        patterns.add(match.group(0)[:30])
    return patterns
