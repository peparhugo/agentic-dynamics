"""Evidence-integrity e6 — the concrete phase-boundary analyzer (design §5.7).

The implementation of the runtime-owned :class:`ChangeAnalyzer` protocol, injected at the
composition root (opt-in, OFF by default). It composes the evidence loop for one change:

    change -> CodeSnapshot/CodeDelta -> versioned-graph update
           -> code_change_facts/v2 emit -> executor neighborhood supplied

The concrete flow (control tier, which may see both ``runtime`` and ``control.reducers``):

1. **Graph update** — ``populate_versioned_graph`` for the after-snapshot (additive; a
   ``graph_client`` is duck-typed, so the analyzer is hermetic-testable with a store double and
   never requires a live Neo4j).
2. **Executor neighborhood** — the ACL-scoped 1-2 hop reachable set, seeded from the changed
   symbols' ``version_id``\\ s (``expand_candidates`` with ``repository_id`` + ``acl_scope``);
   the returned symbol qualified names ARE the bounded context the executor gets, and their
   count is the ``impacted_symbol_count`` fact's input.
3. **Facts emit** — ``code_change_facts_v2`` over the delta + analyzer statuses + impacted
   count, de-typed to plain dicts so ``runtime`` stays free of ``control`` imports.

The analyzer is a pure-ish composition: the only I/O is the duck-typed ``graph_client``
(``populate_versioned_graph`` / ``expand_candidates``); everything else is deterministic.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any

from agentic_dynamics.control.facts import EvidenceItem, ReducerInput
from agentic_dynamics.control.reducers.code_change_facts import code_change_facts_v2
from agentic_dynamics.core.language import (
    symbol_entity_id,
    symbol_version_id,
)
from agentic_dynamics.knowledge.graph import IMPACT_EXPANSION_RELS
from agentic_dynamics.runtime.change_analyzer import (
    ChangeAnalysis,
    ChangeAnalyzer,
    ChangeInput,
)


def _seed_scope_names(change: ChangeInput) -> list[str]:
    """The change's OWN symbols (added/changed/removed qualified names) — the executor's
    delta-only scope. The cap_2a_rerun2 scope-miss fix: a proposal's scope must contain the
    symbols the rework would target, or the fixed hit rule can never score a rework leg."""
    names: list[str] = []
    if change.delta is None:
        return names
    for sym in (
        change.delta.added_symbols + change.delta.changed_symbols + change.delta.removed_symbols
    ):
        if sym.qualified_name not in names:
            names.append(sym.qualified_name)
    return sorted(names)


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
    surface from e4; ``expand_candidates`` additionally accepts the optional ``rels`` allowlist,
    and the analyzer passes ``IMPACT_EXPANSION_RELS`` so version history (SUPERSEDES) is never
    counted as an impact edge). ``None`` skips the graph step (the loop still emits facts +
    neighborhood from the delta alone — hermetically testable).

    Graph resilience (cap_2a p1): a graph error — a downed server, a timeout, a malformed
    response — NEVER escapes ``analyze``. The graph leg degrades to delta-only facts with an
    explicit ``graph_status`` (``available`` / ``unavailable`` / ``not_requested``) on the
    returned :class:`ChangeAnalysis`; the impacted count is then omitted (None), never a
    fabricated zero. Only the two graph calls are guarded — a reducer error still propagates.

    HARD DEADLINE (cap_2a p1, found live during the campaign's p2 cell): the graph leg runs
    under ``GRAPH_LEG_TIMEOUT_SECONDS`` — a stalled driver (unreachable server, hung
    connection-acquisition retry, a Bolt peer that never answers) BLOCKS the phase forever
    otherwise, which would violate the phase-boundary seam's never-block guarantee. On
    timeout the leg degrades exactly like any other graph failure: delta-only facts +
    ``graph_status=unavailable``. The abandoned worker thread keeps waiting in the background;
    the driver is closed by the composition root's ``finally`` regardless.
    """

    #: Client-side deadline for the whole graph leg (populate parent + after, then the impact
    #: expansion). A healthy local Neo4j answers each call in well under a second; 30s is a
    #: generous envelope that still guarantees a hung server can never stall a phase.
    GRAPH_LEG_TIMEOUT_SECONDS = 30.0

    def __init__(self, graph_client: Any = None, *, graph_requested: bool | None = None) -> None:
        self.graph_client = graph_client
        # A requested graph whose client could not be constructed is different from the
        # deliberate delta-only mode. The composition root uses this bit to keep that loss of
        # evidence visible in the ledger instead of mislabeling it as "not_requested".
        self.graph_requested = graph_client is not None if graph_requested is None else graph_requested

    def analyze(self, change: ChangeInput) -> ChangeAnalysis:
        graph_status = "unavailable" if self.graph_requested and self.graph_client is None else "not_requested"
        graph_updated = False
        neighborhood: list[str] = []
        impacted: int | None = None

        # Graph leg — populate first, then the impact expansion. Best-effort under a hard
        # client-side deadline: a failure (raised OR timed-out — a stalled driver never
        # returns) degrades to delta-only facts + an explicit graph_status, never an escaping
        # exception and never a hung phase (the runner records the analysis as a phase-boundary
        # evidence product; a graph-down cell must be FLAGGED, not crash the phase).
        if self.graph_client is not None:
            graph_failed = False
            pool = ThreadPoolExecutor(max_workers=1)
            try:
                graph_updated = pool.submit(self._populate_graph, change).result(
                    timeout=self.GRAPH_LEG_TIMEOUT_SECONDS
                )
            except FuturesTimeout:
                graph_failed = True
            except Exception:
                graph_failed = True
            finally:
                pool.shutdown(wait=False)
            graph_status = "unavailable" if graph_failed else "available"

        if graph_status == "available":
            pool = ThreadPoolExecutor(max_workers=1)
            try:
                neighborhood, impacted = pool.submit(self._neighborhood, change).result(
                    timeout=self.GRAPH_LEG_TIMEOUT_SECONDS
                )
            except (FuturesTimeout, Exception):
                # The impact leg failed — flag the cell so downstream scoring never mistakes
                # the delta-only facts for a full-fact analysis.
                neighborhood, impacted = [], None
                graph_status = "unavailable"
            finally:
                pool.shutdown(wait=False)
        else:
            # No graph (or a failed one): the executor scope is the change's OWN symbols —
            # the cap_2a_rerun2 scope-miss fix, delta-only. Impacted stays unknown.
            neighborhood, impacted = _seed_scope_names(change), None

        facts = code_change_facts_v2(self._reducer_input(change, impacted))
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
            graph_status=graph_status,
            revision=change.revision,
            repository_id=change.repository_id,
            phase_id=change.phase_id,
            observed_at=change.observed_at,
        )

    def _populate_graph(self, change: ChangeInput) -> bool:
        """Populate the parent and after revisions; True when the after revision got versions.

        Runs under the analyzer's client-side deadline (see ``analyze``). Each snapshot is
        populated independently — one failure does not stop the other.
        """
        graph_updated = False
        # Populate the parent as well as the after revision. Removed symbols are seeded from
        # the parent; without its revision in the graph, their impact neighborhood is
        # silently unresolvable on a fresh graph.
        for snapshot, revision in (
            (change.before, getattr(change.before, "revision", "")),
            (change.after, change.revision),
        ):
            if snapshot is None or not revision:
                continue
            try:
                counts = self.graph_client.populate_versioned_graph(
                    snapshot,
                    revision=revision,
                    repository_id=change.repository_id,
                    acl_scope=change.acl_scope,
                )
            except Exception:  # noqa: BLE001 — a failing graph is a state, not a crash
                continue
            if snapshot is change.after:
                graph_updated = bool((counts or {}).get("symbol_versions", 0))
        return graph_updated

    def _neighborhood(self, change: ChangeInput) -> tuple[list[str], int | None]:
        """The change's OWN symbols UNION their ACL-scoped 1-2 hop reachable set.

        The returned set is the executor's scope surface: the changed symbols FIRST (the
        delta's added/changed/removed qualified names — the cap_2a_rerun2 scope miss was
        structural: the neighborhood returned only the reachable dependents, so a rework
        proposal's scope EXCLUDED the very symbol the rework targets, and the fixed hit rule
        could never score a rework leg), then the 1-2 hop dependents when a graph is
        available. Without a graph the changed symbols still form a usable (delta-only)
        scope, and the impacted count is None (unknown, never 0). Traversal is bounded to
        ``IMPACT_EXPANSION_RELS`` — version history (SUPERSEDES) is not an impact edge.
        """
        seed_names = _seed_scope_names(change)
        if self.graph_client is None or change.delta is None:
            return seed_names, None
        seeds = _seed_version_ids(change)
        if not seeds:
            return seed_names, None
        expanded = self.graph_client.expand_candidates(
            seeds,
            max_depth=2,
            max_neighbors=8,
            max_nodes=40,
            timeout_ms=300,
            repository_id=change.repository_id,
            acl_scope=change.acl_scope,
            rels=IMPACT_EXPANSION_RELS,
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
        # The changed symbols themselves are NOT the impacted set (that is the dependents'
        # count), but they ARE part of the executor scope — the cap_2a_rerun2 scope-miss fix.
        return sorted(set(seed_names) | neighbors), len(neighbors)

    @staticmethod
    def _reducer_input(change: ChangeInput, impacted: int | None) -> ReducerInput:
        evidence: list[EvidenceItem] = []
        evidence_prefix = f"{change.repository_id}:{change.phase_id or 'phase'}:{change.revision}"
        if change.delta is not None:
            evidence.append(
                EvidenceItem(
                    source_type="code_delta",
                    evidence_id=f"delta:{evidence_prefix}",
                    payload=change.delta,
                )
            )
        if change.sonar is not None:
            evidence.append(
                EvidenceItem(
                    source_type="sonar_analysis",
                    evidence_id=f"sonar:{evidence_prefix}",
                    payload=change.sonar,
                )
            )
        if change.lsp is not None:
            evidence.append(
                EvidenceItem(
                    source_type="lsp_analysis",
                    evidence_id=f"lsp:{evidence_prefix}",
                    payload=change.lsp,
                )
            )
        if impacted is not None:
            evidence.append(
                EvidenceItem(
                    source_type="impacted_symbols",
                    evidence_id=f"impacted:{evidence_prefix}",
                    payload={"count": impacted},
                )
            )
        job_id = change.repository_id or "unscoped"
        return ReducerInput(
            scope_path=f"org:{change.repository_id}/job:{job_id}",
            scope_type="job",
            scope_id=job_id,
            repository_id=change.repository_id,
            evidence=tuple(evidence),
            facts=(),
            now=change.observed_at,
            source_revision=change.revision,
        )
