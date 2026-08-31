"""The *change analyzer* contract — the injected phase-boundary evidence seam (design §5.7).

``runtime`` owns the protocol so the execution runtime never imports the evidence machinery
(``control``'s reducer, ``knowledge``'s graph). A workflow run MAY hand its post-phase change to
an analyzer; the concrete implementation (``control.evidence_analyzer.EvidenceChangeAnalyzer``)
is injected at the composition root (``scripts/run_workflow.py``), exactly the Debt-2 pattern of
``runtime/routing.py`` / ``runtime/telemetry.py``.

Default no-op: ``default_change_analyzer()`` returns ``NoopChangeAnalyzer``, so a run that does
not opt in behaves byte-identically — the seam changes nothing on its own.

The analyzer input/output are PURE DATA (no ``control.facts.CanonicalFact``, no graph client):
the caller supplies the typed CodeSnapshot/CodeDelta pair + analyzer statuses + scope, and the
analyzer returns the emitted facts as plain dicts plus the executor neighborhood (the bounded,
ACL-scoped symbol set).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ChangeInput:
    """Everything the phase-boundary analyzer may see about ONE change.

    ``before``/``after`` are typed :class:`~agentic_dynamics.core.language.CodeSnapshot`\\ s (or
    ``None`` when the change is not tree-sitter materialized); ``delta`` is the typed
    :class:`~agentic_dynamics.core.language.CodeDelta`. ``sonar``/``lsp`` are the analyzer
    status payloads (``{"status", "revision_matches"|None, "new_critical_count"|None, ...}`` /
    ``{"status", "new_error_count"|None, "tool"}``); ``impacted_count`` is the caller-computed
    1-2 hop ACL-scoped reachable-set size (None when the graph is unavailable). Pure data — a
    reducer-style input, never a live handle.
    """

    before: Any
    after: Any
    delta: Any
    revision: str
    repository_id: str
    acl_scope: str
    sonar: dict[str, Any] | None = None
    lsp: dict[str, Any] | None = None
    impacted_count: int | None = None
    phase_id: str = ""
    observed_at: str = ""


@dataclass(frozen=True)
class ChangeAnalysis:
    """The analyzer's output — the phase-boundary evidence product.

    ``facts`` are plain ``{"predicate", "value", "value_type", "evidence_ids"}`` dicts (the
    control reducer's canonical facts, de-typed so runtime need not import ``control.facts``);
    ``neighborhood`` is the bounded executor context (symbol qualified names); ``graph_updated``
    records whether the versioned graph was populated for this change. ``graph_status`` is the
    explicit graph-leg status — ``"not_requested"`` (no client injected), ``"available"``
    (populate + impact expansion succeeded), or ``"unavailable"`` (a graph error degraded the
    analysis to delta-only facts, impacted count omitted — never a fabricated zero).
    ``revision`` is the full commit SHA the analysis was produced for (provenance).
    ``repository_id``/``phase_id``/``observed_at`` identify the cell boundary that produced the
    facts; they are optional for structural compatibility with existing analyzer doubles.

    The graph-family Part A seam (persistent_code_graph@0.1 p4) adds the DECLARED semantics
    surface: ``impacted_semantics`` is the pinned impacted definition (structural — the 2e
    lesson) and ``impacted_source`` is the computation's provenance ("graph" when the persistent
    graph produced the count, "in_process_walk" when the rollback AST walk did). Both are
    queryable + auditable on the record; an empty ``impacted_source`` means no impacted
    computation was attempted.
    """

    facts: tuple[dict[str, Any], ...] = ()
    neighborhood: tuple[str, ...] = ()
    graph_updated: bool = False
    impacted_count: int | None = None
    impacted_semantics: str = ""
    impacted_source: str = ""
    graph_status: str = "not_requested"
    revision: str | None = None
    repository_id: str = ""
    phase_id: str = ""
    observed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        """The ledger-shaped form (plain data, JSON-safe) the runner records per phase."""
        return {
            "facts": list(self.facts),
            "neighborhood": list(self.neighborhood),
            "graph_updated": self.graph_updated,
            "impacted_count": self.impacted_count,
            "impacted_semantics": self.impacted_semantics,
            "impacted_source": self.impacted_source,
            "graph_status": self.graph_status,
            "revision": self.revision,
            "repository_id": self.repository_id,
            "phase_id": self.phase_id,
            "observed_at": self.observed_at,
        }


class ChangeAnalyzer(Protocol):
    """The phase-boundary evidence protocol (design §5.7).

    Matched structurally by ``control.evidence_analyzer.EvidenceChangeAnalyzer``.
    """

    def analyze(self, change: ChangeInput) -> ChangeAnalysis:
        """Analyze one change into facts + executor neighborhood. Pure (no I/O in v1)."""


class NoopChangeAnalyzer:
    """The DEFAULT analyzer — a strict no-op so existing runs are byte-identical.

    Returns an empty analysis: no facts, no neighborhood, no graph update. A run that never
    injects a real analyzer is indistinguishable from one that has the seam but leaves it off.
    """

    def analyze(self, change: ChangeInput) -> ChangeAnalysis:
        return ChangeAnalysis()


def default_change_analyzer() -> ChangeAnalyzer:
    """The composition root's default: the no-op analyzer (opt-in, OFF by default)."""
    return NoopChangeAnalyzer()


def run_change_analysis(
    change: ChangeInput, analyzer: ChangeAnalyzer | None = None
) -> ChangeAnalysis:
    """The phase-boundary entry point a workflow run calls after a commit.

    ``analyzer`` is injected at the composition root; ``None`` falls back to the no-op, so the
    seam is inert unless a run opts in.
    """
    return (analyzer or default_change_analyzer()).analyze(change)
