"""Evidence-integrity e6 — the concrete phase-boundary analyzer (design §5.7).

The implementation of the runtime-owned :class:`ChangeAnalyzer` protocol, injected at the
composition root (opt-in, OFF by default). It composes the evidence loop for one change:

    change -> CodeSnapshot/CodeDelta -> versioned-graph update
           -> code_change_facts/v2 emit -> executor neighborhood supplied

The concrete flow (control tier, which may see both ``runtime`` and ``control.reducers``):

1. **Graph update** — ``populate_versioned_graph`` for the after-snapshot (additive; a
   ``graph_client`` is duck-typed, so the analyzer is hermetic-testable with a store double and
   never requires a live Neo4j).
2. **Executor neighborhood** — the graph-first impacted computation (graph-family Part A p4):
   the in-process AST walk (:func:`_in_process_impacted`) is the default posture; a healthy
   persistent graph UPGRADES the answer (the ACL-scoped 1-2 hop reachable set, seeded from the
   changed symbols' ``version_id``\\ s — ``expand_candidates`` with ``repository_id`` +
   ``acl_scope``). Any graph failure (down / empty / timeout) rolls back to the in-process walk —
   additive, never a gate. The returned symbol qualified names ARE the bounded context the
   executor gets; the non-seed dependants' count is the ``impacted_symbol_count`` fact's input,
   with the semantics DECLARED (``impacted_semantics`` / ``impacted_source`` — queryable).
3. **Facts emit** — ``code_change_facts_v2`` over the delta + analyzer statuses + impacted
   count, de-typed to plain dicts so ``runtime`` stays free of ``control`` imports.

The analyzer is a pure-ish composition: the only I/O is the duck-typed ``graph_client``
(``populate_versioned_graph`` / ``expand_candidates``); everything else is deterministic.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from typing import Any

from agentic_dynamics.control.facts import EvidenceItem, ReducerInput
from agentic_dynamics.control.reducers.code_change_facts import (
    IMPACTED_SEMANTICS,
    code_change_facts_v2,
)
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


def _in_process_impacted(change: ChangeInput) -> tuple[list[str], int | None]:
    """The in-process AST walk — the seam's rollback + default posture (graph-family Part A p4).

    Computes the impacted computation WITHOUT the graph: the structural dependants of the
    change's symbols over the AST call graph (the same CALLS semantics the graph uses), bounded
    to 1-2 hops, non-seed only. Pure + deterministic — no I/O, no deadline, no graph. The
    graph NEVER gates a run: this walk produces the impacted set on ANY graph failure
    (down / empty / timeout) and is the default when no graph client is injected. The returned
    ``(scope, impacted)`` matches the graph path's shape (the changed symbols UNION the non-seed
    dependants; impacted = the non-seed dependants' count; None only when the delta is absent).
    """
    delta = change.delta
    if delta is None:
        return [], None
    seed_names = set(_seed_scope_names(change))
    after = change.after
    if after is None:
        return sorted(seed_names), 0

    # The symbol call map: qualified_name -> the qualified names it calls (name-resolved from
    # ``CodeSymbol.calls``, the same extraction the graph's CALLS edges use).
    qname_to_calls: dict[str, set[str]] = {
        sym.qualified_name: set(sym.calls) for sym in after.all_symbols
    }

    # 1 hop: symbols that call a changed symbol directly (non-seed only — the seeds themselves
    # are not the impacted set, the wall's rule).
    dependants: set[str] = set()
    for caller, calls in qname_to_calls.items():
        if caller in seed_names:
            continue
        if calls & seed_names:
            dependants.add(caller)

    # 2 hop: symbols that call the 1-hop dependants (non-seed, non-already-counted).
    second_hop: set[str] = set()
    for caller, calls in qname_to_calls.items():
        if caller in seed_names or caller in dependants:
            continue
        if calls & dependants:
            second_hop.add(caller)
    dependants |= second_hop

    scope = sorted(seed_names | dependants)
    return scope, len(dependants)


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
    neighborhood from the in-process AST walk — hermetically testable).

    Graph-first with the in-process rollback (graph-family Part A p4 — additive, never a gate):
    the impacted computation ALWAYS happens. The in-process AST walk (:func:`_in_process_impacted`)
    is the default posture; a healthy persistent graph UPGRADES the answer (its richer 1-2 hop
    over the module edges). On ANY graph failure — down, timeout, or empty/truncated (the graph
    returns fewer dependants than the AST can see — the 2d/2e wall's exact signature) — the seam
    keeps the in-process walk's answer and records the provenance
    (``impacted_source``/``impacted_semantics``), so the semantics stay declared, queryable,
    auditable. The graph never gates a run.

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

        # The in-process AST walk is the seam's DEFAULT POSTURE (graph-family Part A p4 — the
        # rollback is the default): the impacted computation always happens, purely in-process,
        # and the persistent graph UPGRADES it when healthy. The graph never gates a run.
        neighborhood, impacted = _in_process_impacted(change)
        impacted_source = "in_process_walk"

        # Graph leg — populate first, then the impact expansion. Best-effort under a hard
        # client-side deadline: a failure (raised OR timed-out — a stalled driver never
        # returns) degrades to the in-process walk + an explicit graph_status, never an escaping
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
                graph_neighborhood, graph_impacted = pool.submit(self._graph_neighborhood, change).result(
                    timeout=self.GRAPH_LEG_TIMEOUT_SECONDS
                )
            except (FuturesTimeout, Exception):
                # The impact leg failed — flag the cell so downstream scoring never mistakes
                # the in-process-walk facts for a graph-complete analysis.
                graph_neighborhood, graph_impacted = [], None
                graph_status = "unavailable"
            finally:
                pool.shutdown(wait=False)

            if graph_status == "available" and graph_impacted is not None:
                # Healthy graph: prefer the graph's richer 1-2 hop (module-edge) result UNLESS
                # it under-counts vs the in-process walk — the wall's exact signature (the
                # 300ms/max_nodes truncation or an empty scope returns 0 while the AST's
                # structural dependants exist). That is a graph failure ("empty"), so roll back.
                if graph_impacted >= (impacted or 0):
                    neighborhood, impacted = graph_neighborhood, graph_impacted
                    impacted_source = "graph"
                else:
                    # The graph truncated / was empty — keep the in-process walk's answer.
                    impacted_source = "in_process_walk"
        else:
            # No graph (or a failed one): the in-process walk IS the fallback — the executor
            # scope already carries the change's own symbols + their AST dependants (set above).
            pass

        facts = code_change_facts_v2(self._reducer_input(change, impacted, impacted_source))
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
            impacted_semantics=IMPACTED_SEMANTICS["definition"],
            impacted_source=impacted_source,
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

    def _graph_neighborhood(self, change: ChangeInput) -> tuple[list[str], int | None]:
        """The graph-first impact expansion: the change's OWN symbols UNION their ACL-scoped
        1-2 hop reachable set, queried from the PERSISTENT graph (graph-family Part A p4).

        The returned set is the executor's scope surface: the changed symbols FIRST (the
        delta's added/changed/removed qualified names — the cap_2a_rerun2 scope miss was
        structural: the neighborhood returned only the reachable dependents, so a rework
        proposal's scope EXCLUDED the very symbol the rework targets, and the fixed hit rule
        could never score a rework leg), then the 1-2 hop dependents from the graph. The
        impacted count is the NON-SEED dependants' count (the DECLARED structural definition —
        see :data:`code_change_facts.IMPACTED_SEMANTICS`). Traversal is bounded to
        ``IMPACT_EXPANSION_RELS`` — version history (SUPERSEDES) is not an impact edge. The
        in-process AST walk (:func:`_in_process_impacted`) is the rollback when this graph
        query fails, truncates, or comes back empty.
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
    def _reducer_input(
        change: ChangeInput, impacted: int | None, impacted_source: str = ""
    ) -> ReducerInput:
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
                    # The DECLARED semantics + provenance ride on the evidence payload (the
                    # fact's evidence_ids link back to this audit record — queryable).
                    payload={
                        "count": impacted,
                        "semantics": IMPACTED_SEMANTICS["definition"],
                        "source": impacted_source or "in_process_walk",
                    },
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
