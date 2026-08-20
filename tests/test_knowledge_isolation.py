"""Scope-isolation pinning tests — the per-cell retrieval filter must never leak across cells.

The whole feature exists so one cell's knowledge (scope ``self-<worktree>``) can never
surface in another cell's augmented prompt. These tests pin that contract at the
:func:`instrument.retrieval.retrieve` level using store doubles that carry each finding's
``repository_id``, so no live Chroma/Neo4j is required.
"""

from agentic_dynamics.knowledge.knowledge import Authority
from agentic_dynamics.knowledge.retrieval import retrieve, scope_excluded

TEXT = "build a task manager api with create/read/update/delete endpoints"


def _dense_hit(knowledge_id: str, repository_id: str) -> dict:
    """A dense-leg hit carrying the finding's repository scope (near-identical text)."""
    return {
        "id": knowledge_id,
        "document": TEXT,
        "metadata": {
            "authority": "measured",
            "content_hash": f"hash:{knowledge_id}",
            "repository_id": repository_id,
            "logical_locator": repository_id,
        },
        "distance": 0.1,
    }


def _lexical_hit(knowledge_id: str, repository_id: str) -> dict:
    """A lexical-leg hit carrying the finding's repository scope."""
    return {
        "id": f"elem:{knowledge_id}",
        "properties": {
            "knowledge_id": knowledge_id,
            "entity_id": f"ent:{knowledge_id}",
            "text": TEXT,
            "authority": "measured",
            "content_hash": f"hash:{knowledge_id}",
            "repository_id": repository_id,
            "logical_locator": repository_id,
            "commit_sha": "",
        },
        "score": 0.9,
    }


class _DenseStore:
    """Scripted dense store: returns every hit regardless of ``where`` (the post-filter isolates)."""

    def __init__(self, hits):
        self._hits = list(hits)

    def search(self, query, *, top_k=40, where=None):
        return list(self._hits)


class _GraphClient:
    """Scripted graph client: returns every lexical hit; expansion is empty for these tests."""

    def __init__(self, hits):
        self._hits = list(hits)

    def search_knowledge_fulltext(self, query, *, limit=10, commit=None):
        return list(self._hits)

    def expand_candidates(self, seeds, **kwargs):
        return []


def _scopes(attempt) -> set:
    return {c.repository_id for c in attempt.candidates}


def test_scope_excluded_contract():
    assert scope_excluded("self-b", "self-a") is True     # other cell → excluded
    assert scope_excluded("self-a", "self-a") is False    # same cell → eligible
    assert scope_excluded("", "self-a") is False          # unscoped/legacy → eligible
    assert scope_excluded("self-b", "") is False          # no requested scope → no filter


def test_retrieval_scoped_to_self_a_excludes_self_b():
    # Both scopes hold near-identical findings on BOTH legs; the scoped retrieval must
    # surface only the requested scope's candidates.
    dense = _DenseStore([
        _dense_hit("ka", "self-a"),
        _dense_hit("kb", "self-b"),
    ])
    graph = _GraphClient([
        _lexical_hit("kax", "self-a"),
        _lexical_hit("kbx", "self-b"),
    ])

    attempt_a = retrieve(
        "build a task manager api",
        dense_store=dense,
        graph_client=graph,
        repository_id="self-a",
    )
    scopes_a = _scopes(attempt_a)
    assert "self-a" in scopes_a          # the requested scope's findings survived ...
    assert "self-b" not in scopes_a      # ... and the other cell's never leaked.
    assert scopes_a <= {"self-a"}

    attempt_b = retrieve(
        "build a task manager api",
        dense_store=dense,
        graph_client=graph,
        repository_id="self-b",
    )
    scopes_b = _scopes(attempt_b)
    assert "self-b" in scopes_b
    assert "self-a" not in scopes_b
    assert scopes_b <= {"self-b"}


def test_retrieval_without_scope_is_back_compatible():
    # No requested scope → no isolation filter (historical behavior): all scopes surface.
    # Distinct text per hit so the embedding-based collapse (which drops near-duplicates)
    # cannot mask the absence of a scope filter.
    dense = _DenseStore([
        _dense_hit("ka", "self-a"),
        _dense_hit("kb", "self-b"),
    ])
    dense._hits[0]["document"] = "alpha topic one"
    dense._hits[1]["document"] = "beta topic two"
    graph = _GraphClient([
        _lexical_hit("kax", "self-a"),
        _lexical_hit("kbx", "self-b"),
    ])
    graph._hits[0]["properties"]["text"] = "gamma topic three"
    graph._hits[1]["properties"]["text"] = "delta topic four"

    attempt = retrieve("a query", dense_store=dense, graph_client=graph)
    scopes = _scopes(attempt)
    assert "self-a" in scopes
    assert "self-b" in scopes


def test_retrieval_scope_isolates_across_collapse_noise():
    # Two same-scope near-identical findings plus a cross-scope one: even if embedding-based
    # collapse runs, the cross-scope candidate must already be gone (filtered before fusion).
    dense = _DenseStore([
        _dense_hit("k1", "self-a"),
        _dense_hit("k2", "self-a"),
        _dense_hit("k3", "self-b"),
    ])
    attempt = retrieve(
        "build a task manager api",
        dense_store=dense,
        graph_client=_GraphClient([]),
        repository_id="self-a",
    )
    assert _scopes(attempt) == {"self-a"}
    assert all(c.authority is Authority.MEASURED for c in attempt.candidates)
