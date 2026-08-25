"""Evidence-integrity e6 — the concrete phase-boundary analyzer (design §5.7).

The implementation of the runtime-owned :class:`ChangeAnalyzer` protocol, injected at the
composition root (opt-in, OFF by default). It composes the evidence loop for one change:

    change -> CodeSnapshot/CodeDelta -> versioned-graph update
           -> code_change_facts/v1 emit -> executor neighborhood supplied

The concrete flow (control tier, which may see both ``runtime`` and ``control.reducers``):

1. **Graph update** — ``populate_versioned_graph`` for the after-snapshot (additive; a
   ``graph_client`` is duck-typed, so the analyzer is hermetic-testable with a store double and
   never requires a live Neo4j).
2. **Executor neighborhood** — the ACL-scoped 1-2 hop reachable set, seeded from the changed
   symbols' ``version_id``\\ s (``expand_candidates`` with ``repository_id`` + ``acl_scope``);
   the returned symbol qualified names ARE the bounded context the executor gets, and their
   count is the ``impacted_symbol_count`` fact's input.
3. **Facts emit** — ``code_change_facts_v1`` over the delta + analyzer statuses + impacted
   count, de-typed to plain dicts so ``runtime`` stays free of ``control`` imports.

The analyzer is a pure-ish composition: the only I/O is the duck-typed ``graph_client``
(``populate_versioned_graph`` / ``expand_candidates``); everything else is deterministic.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from agentic_dynamics.control.facts import EvidenceItem, ReducerInput
from agentic_dynamics.control.reducers.code_change_facts import code_change_facts_v1
from agentic_dynamics.core.language import (
    symbol_entity_id,
    symbol_version_id,
)
from agentic_dynamics.runtime.change_analyzer import (
    ChangeAnalysis,
    ChangeAnalyzer,
    ChangeInput,
)


def _seed_version_ids(change: ChangeInput) -> list[str]:
    """The version_ids of the change's added/changed/removed symbols (two-ID contract)."""
    delta = change.delta
    if delta is None:
        return []
    seeds: list[str] = []
    for sym in delta.added_symbols + delta.changed_symbols:
        ent = symbol_entity_id(change.repository_id, sym.file_path, sym.qualified_name, sym.kind)
        seeds.append(symbol_version_id(ent, change.revision, sym.content_hash))
    for sym in delta.removed_symbols:
        ent = symbol_entity_id(change.repository_id, sym.file_path, sym.qualified_name, sym.kind)
        seeds.append(symbol_version_id(ent, change.before.revision, sym.content_hash))
    return seeds


class EvidenceChangeAnalyzer(ChangeAnalyzer):
    """The concrete evidence loop — injected at the composition root when a run opts in.

    ``graph_client`` is duck-typed: any object exposing ``populate_versioned_graph(snapshot, *,
    revision, repository_id, acl_scope)`` and ``expand_candidates(seed_ids, *, max_depth,
    max_neighbors, max_nodes, timeout_ms, repository_id, acl_scope)`` (the ``Neo4jClient``
    surface from e4). ``None`` skips the graph step (the loop still emits facts + neighborhood
    from the delta alone — hermetically testable).
    """

    def __init__(self, graph_client: Any = None) -> None:
        self.graph_client = graph_client

    def analyze(self, change: ChangeInput) -> ChangeAnalysis:
        graph_updated = False
        if self.graph_client is not None and change.after is not None:
            counts = self.graph_client.populate_versioned_graph(
                change.after,
                revision=change.revision,
                repository_id=change.repository_id,
                acl_scope=change.acl_scope,
            )
            graph_updated = bool(counts.get("symbol_versions", 0))

        neighborhood, impacted = self._neighborhood(change)

        facts = code_change_facts_v1(self._reducer_input(change, impacted))
        return ChangeAnalysis(
            facts=tuple(
                {
                    "predicate": fact.predicate,
                    "value": fact.value,
                    "value_type": fact.value_type,
                    "evidence_ids": fact.evidence_ids,
                }
                for fact in facts
            ),
            neighborhood=tuple(neighborhood),
            graph_updated=graph_updated,
            impacted_count=impacted,
        )

    def _neighborhood(self, change: ChangeInput) -> tuple[list[str], int | None]:
        """The ACL-scoped 1-2 hop reachable set from the changed symbols.

        Returns (symbol qualified names for the executor, impacted count). When no graph client
        or no seeds, the neighborhood is empty and the impacted count is None (unknown, never 0).
        """
        if self.graph_client is None or change.delta is None:
            return [], None
        seeds = _seed_version_ids(change)
        if not seeds:
            return [], None
        expanded = self.graph_client.expand_candidates(
            seeds,
            max_depth=2,
            max_neighbors=8,
            max_nodes=40,
            timeout_ms=300,
            repository_id=change.repository_id,
            acl_scope=change.acl_scope,
        )
        seed_set = set(seeds)
        neighbors: set[str] = set()
        for node in expanded:
            props = node.get("properties") or {}
            vid = props.get("version_id") or props.get("knowledge_id") or ""
            if vid in seed_set:
                continue  # the seeds themselves are not the impacted set
            qname = props.get("qualified_name")
            if qname:
                neighbors.add(str(qname))
        return sorted(neighbors), len(neighbors)

    @staticmethod
    def _reducer_input(change: ChangeInput, impacted: int | None) -> ReducerInput:
        evidence: list[EvidenceItem] = []
        if change.delta is not None:
            evidence.append(
                EvidenceItem(source_type="code_delta", evidence_id=f"delta:{change.revision}", payload=change.delta)
            )
        if change.sonar is not None:
            evidence.append(
                EvidenceItem(source_type="sonar_analysis", evidence_id="sonar:phase", payload=change.sonar)
            )
        if change.lsp is not None:
            evidence.append(
                EvidenceItem(source_type="lsp_analysis", evidence_id="lsp:phase", payload=change.lsp)
            )
        if impacted is not None:
            evidence.append(
                EvidenceItem(source_type="impacted_symbols", evidence_id="impacted:phase", payload={"count": impacted})
            )
        return ReducerInput(
            scope_path=f"org:{change.repository_id}/job:{change.repository_id}",
            scope_type="job",
            scope_id=change.repository_id,
            repository_id=change.repository_id,
            evidence=tuple(evidence),
            facts=(),
            now="",
            source_revision=change.revision,
        )
