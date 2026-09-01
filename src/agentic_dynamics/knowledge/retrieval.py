"""Deterministic retrieval and evidence-card derivation for the runtime-RAG layer.

The retrieval pipeline is deterministic from the raw work item up to the prompt
constructor call — no LLM query-rewriting in v1, because rewriting would entangle
candidate *recall* with constructor *quality* and add latency before any evidence
exists. The flow:

    raw work item ── planner ──▶ dense (Chroma) + lexical (Neo4j full-text) legs
        │                            (parallel, top-40 each)
        ▼
    rank fusion (RRF base × authority × freshness × exact-id × conflict)
        │
        ▼
    bounded graph expansion (decayed boost, NOT a third ranked peer)
        │
        ▼
    deduplicate + retain conflicts
        │
        ▼
    token-budgeted whole-chunk selection  ──▶ RetrievalAttempt (recorded BEFORE any LLM)

The math constants are *policy* constants, not learned truths: they are versioned
via ``WEIGHTS_VERSION`` and tagged ``[H]`` so a future ablation (the six-arm grid
in the design) can swap them.

Design: ``code_reviews/2026-08-15_rag-knowledge-base-proposal-review.md`` §7 and the
companion ``docs/rag_design.md`` §2.
"""

from __future__ import annotations

import json
import math
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from agentic_dynamics.knowledge.knowledge import Authority

# ── Versioned weights (policy constants, [H]) ───────────────────

WEIGHTS_VERSION = "retrieval-weights/v1"  # [H]

RRF_K = 60.0  # [H] rank-smoothing constant in the RRF base.
LEXICAL_LEG_WEIGHT = 1.2  # [H] lexical leg is weighted above dense in the base.
DENSE_LEG_WEIGHT = 1.0  # [H]
EXACT_IDENTIFIER_MULTIPLIER = 1.15  # [H] quoted path/symbol/error/test-name match.
CONFLICT_MULTIPLIER = 0.70  # [H] unresolved contradictory evidence penalty.
EXACT_COMMIT_MULTIPLIER = 1.10  # [H] freshness bonus for the exact commit.

GRAPH_DECAY = 0.7  # [H] 0.7 ** depth — a structural neighbor is categorically weaker.

DEFAULT_TOP_K = 40
DEFAULT_SEED_COUNT = 12
DEFAULT_RAG_TOKEN_LIMIT = 8000
DEFAULT_EXECUTOR_RAG_RATIO = 0.20
REDUNDANCY_THRESHOLD = 0.92
DENSE_QUERY_MAX_TOKENS = 512  # [H] truncate the dense query at a recorded limit.

#: Authority trust multipliers for *retrieval fusion* (not a ranking of relevance).
#: POLICY is absent — pinned policy is read directly from the checkout, never
#: probabilistically retrieved, so it never appears in a candidate.
AUTHORITY_MULTIPLIER: dict[Authority, float] = {
    Authority.SOURCE: 1.15,
    Authority.MEASURED: 1.05,
    Authority.DERIVED: 1.00,
    Authority.ADVISORY: 0.80,
}

#: Freshness multipliers for advisory evidence by observed age.
ADVISORY_FRESH_30D = 0.90  # [H]
ADVISORY_FRESH_90D = 0.75  # [H] older advisory evidence is excluded entirely.

#: Graph-expansion relationship weights ([H]). CONTRADICTS always carries a conflict label.
#: CONTAINS + AFFECTS (design §5.5) let the executor traverse the versioned graph
#: (module/symbol containment, issue→symbol).
RELATIONSHIP_WEIGHTS: dict[str, float] = {
    "TESTED_BY": 1.0,
    "DEFINES": 1.0,
    "SUPERSEDES": 1.0,
    "CONTAINS": 0.9,
    "IMPORTS": 0.8,
    "CALLS": 0.8,
    "PRODUCED_BY": 0.8,
    "PRECEDES": 0.7,
    "AFFECTS": 0.7,
    "CONTRADICTS": 0.6,
}

CONFLICT_RELATIONSHIPS = frozenset({"CONTRADICTS"})


class FallbackMode(str, Enum):
    """Named degradation modes — a degraded run must never silently pool with full-RAG."""

    FULL = "full"
    LEXICAL_GRAPH_ONLY = "lexical_graph_only"
    DENSE_LOCAL_EXACT = "dense_local_exact"
    NO_RAG = "no_rag"


# ── The deterministic query planner ─────────────────────────────

_QUOTED_RE = re.compile(r'["\'`]([^"\'`]+)["\'`]')
_FILE_PATH_RE = re.compile(r"(?<![\w])(?:\.{0,2}/)?[\w.-]+(?:/[\w.-]+)+\.\w+")
_STACK_FRAME_RE = re.compile(r'File\s+"([^"]+)",\s*line\s+(\d+)|at\s+([\w./-]+\.\w+):(\d+)')
_TEST_NAME_RE = re.compile(r"\b(?:test[a-zA-Z0-9_]*|[a-zA-Z0-9_]+_test)\b")
_TEST_FILE_RE = re.compile(r"\b(?:test_[a-zA-Z0-9_-]*|[a-zA-Z0-9_-]*_test)\.py\b")
_PYTEST_NODE_RE = re.compile(r"([\w./-]+\.py)::([\w\[\]-]+)")
_CLI_LONG_RE = re.compile(r"(?<![\w-])--[a-zA-Z][a-zA-Z0-9_-]*")
_CLI_SHORT_RE = re.compile(r"(?<![\w-])-[a-zA-Z]\b")
_DOTTED_IDENT_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+\b")
# CamelCase with an internal lower→upper transition (excludes sentence-leading
# capitalised words like "Fix"); ALL_CAPS constants; snake_case symbols.
_CAMEL_SYMBOL_RE = re.compile(r"\b[A-Z][a-zA-Z0-9]*[a-z][A-Z][a-zA-Z0-9]*\b")
_CAPS_SYMBOL_RE = re.compile(r"\b[A-Z][A-Z0-9_]{2,}\b")
_SNAKE_SYMBOL_RE = re.compile(r"\b[a-z][a-z0-9]*_[a-z0-9_]+\b")
_CODE_EXT_RE = re.compile(r"\.(py|ts|js|jsx|tsx|rs|go|java|rb|c|h|cpp|yaml|yml|json|toml|md|txt)$")


@dataclass
class QueryPlan:
    """The deterministic extraction of structured terms from a raw work item.

    Produced by :func:`build_query_plan` with regexes only — never an LLM — so the
    plan is reproducible and auditable.
    """

    raw: str
    quoted_strings: list[str]
    file_paths: list[str]
    stack_frames: list[str]
    test_names: list[str]
    cli_flags: list[str]
    dotted_identifiers: list[str]
    symbols: list[str]
    dense_query: str
    lexical_query: str
    pattern_projection: bool = False

    @property
    def exact_terms(self) -> list[str]:
        """All exact-identifier terms, in deterministic order, for exact-match scoring."""
        return _dedupe_in_order(
            self.quoted_strings
            + self.file_paths
            + self.test_names
            + self.cli_flags
            + self.dotted_identifiers
            + self.symbols
        )


def _dedupe_in_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out


def _estimate_tokens(text: str) -> int:
    """Deterministic token estimate (whitespace tokens). [H]."""
    return max(1, len(text.split()))


def build_query_plan(
    raw_work_item: str,
    phase_objective: str = "",
    *,
    pattern_projection: bool = False,
) -> QueryPlan:
    """Extract a deterministic query plan from a raw work item (no LLM).

    Extracts quoted strings, file paths, stack frames, test names, CLI flags,
    dotted identifiers, and language symbols, then builds the dense and lexical
    queries. The dense query is the raw item plus the phase objective truncated at
    ``DENSE_QUERY_MAX_TOKENS``; the lexical query ORs the exact terms followed by
    the remaining normalized (lower-cased) terms.
    """
    quoted = _QUOTED_RE.findall(raw_work_item)
    file_paths = _FILE_PATH_RE.findall(raw_work_item)
    test_names = _TEST_NAME_RE.findall(raw_work_item) + _TEST_FILE_RE.findall(raw_work_item)
    test_names += [f"{m[0]}::{m[1]}" for m in _PYTEST_NODE_RE.findall(raw_work_item)]
    cli_flags = _CLI_LONG_RE.findall(raw_work_item) + _CLI_SHORT_RE.findall(raw_work_item)
    dotted = [d for d in _DOTTED_IDENT_RE.findall(raw_work_item) if not _CODE_EXT_RE.search(d)]
    camel = _CAMEL_SYMBOL_RE.findall(raw_work_item)
    caps = _CAPS_SYMBOL_RE.findall(raw_work_item)
    snake = _SNAKE_SYMBOL_RE.findall(raw_work_item)

    # Normalize stack frames into strings; also lift their file paths.
    frames: list[str] = []
    for m in _STACK_FRAME_RE.finditer(raw_work_item):
        if m.group(1):
            frames.append(f'File "{m.group(1)}", line {m.group(2)}')
        else:
            frames.append(f"{m.group(3)}:{m.group(4)}")
    # Remove the file/line of a frame from the bare file-path list to avoid double count.
    bare_file_paths = [p for p in file_paths if not any(p in f for f in frames)]

    # Symbols: camel/caps/snake identifiers that are not already captured as a dotted
    # identifier, test name, or file path (a dotted identifier's trailing symbol is
    # already carried by the dotted term).
    symbols = _dedupe_in_order(camel + caps + snake)
    captured = set(dotted) | set(test_names) | set(bare_file_paths)
    symbols = [s for s in symbols if s not in captured and not any(s in d for d in dotted)]

    quoted = _dedupe_in_order(quoted)
    bare_file_paths = _dedupe_in_order(bare_file_paths)
    frames = _dedupe_in_order(frames)
    test_names = _dedupe_in_order(test_names)
    cli_flags = _dedupe_in_order(cli_flags)
    dotted = _dedupe_in_order(dotted)
    symbols = _dedupe_in_order(symbols)

    # Dense query: raw item + objective, truncated at the recorded token limit.
    dense_query = f"{raw_work_item}\n{phase_objective}".strip()
    dense_query = " ".join(dense_query.split()[:DENSE_QUERY_MAX_TOKENS])

    # Lexical query: exact terms first (OR semantics upstream), then normalized tail.
    exact_terms = quoted + bare_file_paths + test_names + cli_flags + dotted + symbols
    exact_set = {t.lower() for t in exact_terms}
    normalized = [
        w
        for w in re.findall(r"[A-Za-z][A-Za-z0-9_-]*", raw_work_item.lower())
        if w not in exact_set
    ]
    lexical_query = " ".join(_dedupe_in_order(exact_terms + normalized))

    return QueryPlan(
        raw=raw_work_item,
        quoted_strings=quoted,
        file_paths=bare_file_paths,
        stack_frames=frames,
        test_names=test_names,
        cli_flags=cli_flags,
        dotted_identifiers=dotted,
        symbols=symbols,
        dense_query=dense_query,
        lexical_query=lexical_query,
        pattern_projection=pattern_projection,
    )


# ── Candidate + fusion ──────────────────────────────────────────


@dataclass
class Candidate:
    """One fused retrieval candidate, carrying the raw leg signals and provenance."""

    id: str  # canonical knowledge_id (or step_doc_id) — the cross-store key.
    text: str
    content_hash: str
    authority: Authority
    locator: str  # durable source locator (for the citation).
    commit_sha: str = ""
    repository_id: str = ""  # the cell scope a candidate belongs to ("" = unscoped/legacy).
    observed_at: str | None = None
    lexical_rank: int | None = None  # None = absent from the lexical leg.
    dense_rank: int | None = None  # None = absent from the dense leg.
    lexical_score: float | None = None
    dense_score: float | None = None
    exact_identifier_match: bool = False
    conflict: bool = False
    graph_depth: int = 0
    graph_path: list[str] = field(default_factory=list)
    relationship_weight: float = 1.0
    token_count: int = 0
    provenance: list[str] = field(default_factory=list)  # merged provenance on dedupe.
    fused_score: float = 0.0
    source_type: str = ""  # knowledge surface; "pattern" is the opt-in I9 projection.
    pattern_payload: dict[str, Any] | None = None
    evidence_class: str = ""

    @property
    def is_pattern(self) -> bool:
        """Whether this candidate is the reducer-minted pattern projection surface."""
        return self.source_type == "pattern" or self.pattern_payload is not None

    def citation(self) -> str:
        """Render the audit citation ``[K:<id>@<commit>:<locator>]``."""
        return f"[K:{self.id}@{self.commit_sha}:{self.locator}]"


def rrf_base(lexical_rank: int | None, dense_rank: int | None) -> float:
    """Reciprocal-rank-fusion base; a missing leg contributes zero."""
    score = 0.0
    if lexical_rank is not None:
        score += LEXICAL_LEG_WEIGHT / (RRF_K + lexical_rank)
    if dense_rank is not None:
        score += DENSE_LEG_WEIGHT / (RRF_K + dense_rank)
    return score


def freshness_multiplier(
    *,
    authority: Authority,
    commit_sha: str,
    observed_at: str | None,
    current_commit: str,
    now: datetime | None = None,
) -> float | None:
    """Return the freshness multiplier, or ``None`` to *exclude* the candidate.

    POLICY is never retrieved (returns None). When ``current_commit`` is known, a
    SOURCE/MEASURED/DERIVED candidate carrying a *different, non-empty*
    ``commit_sha`` is a HARD exclusion — the worktree and commit are hard filters:
    another branch's code can be semantically similar and operationally wrong. A
    candidate with an *empty* ``commit_sha`` is treated as current/unknown and stays
    eligible. The exact-commit boost (``EXACT_COMMIT_MULTIPLIER``) is preserved.
    Advisory freshness windows (30/90-day) are unchanged.
    """
    if authority is Authority.POLICY:
        return None
    # Hard commit pre-filter (the safety rationale). Only enforced when the current
    # commit is known AND the candidate names a *different*, non-empty commit; an
    # empty commit_sha is unknown/current and therefore eligible.
    if (
        current_commit
        and authority in (Authority.SOURCE, Authority.MEASURED, Authority.DERIVED)
        and commit_sha
        and commit_sha != current_commit
    ):
        return None
    # Exact-commit match remains a soft boost (eligible, scored above current).
    if current_commit and commit_sha and commit_sha == current_commit:
        return EXACT_COMMIT_MULTIPLIER
    # Current/unknown source/measured/derived evidence is neutral (1.00).
    if authority in (Authority.SOURCE, Authority.MEASURED, Authority.DERIVED):
        return 1.00
    if authority is Authority.ADVISORY:
        if observed_at is None:
            return ADVISORY_FRESH_90D
        observed = _parse_timestamp(observed_at)
        if observed is None:
            return ADVISORY_FRESH_90D
        age_days = ((now or datetime.now(timezone.utc)) - observed).days
        if age_days <= 30:
            return ADVISORY_FRESH_30D
        if age_days <= 90:
            return ADVISORY_FRESH_90D
        return None  # stale advisory — excluded from online retrieval
    return 1.00


def _parse_timestamp(value: str) -> datetime | None:
    """Parse an ISO-8601 timestamp, tolerating a trailing 'Z'."""
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def compute_fused_score(
    *,
    lexical_rank: int | None,
    dense_rank: int | None,
    authority: Authority,
    freshness: float,
    exact_identifier_match: bool,
    conflict: bool,
    pattern_uncertainty: float | None = None,
) -> float:
    """Fuse ranks and multiply by the trust factors.

    ``score = base * authority * freshness * exact_identifier * conflict`` where the
    base is the RRF of the two legs. ``authority``/``freshness``/``exact``/``conflict``
    are already the numeric multipliers (computed by the callers).
    """
    base = rrf_base(lexical_rank, dense_rank)
    multiplier = AUTHORITY_MULTIPLIER.get(authority, 1.00)
    multiplier *= freshness
    if exact_identifier_match:
        multiplier *= EXACT_IDENTIFIER_MULTIPLIER
    if conflict:
        multiplier *= CONFLICT_MULTIPLIER
    # ``uncertainty`` is a measured interval width in [0, 1]. A low-uncertainty pattern
    # therefore receives more of the same RRF/authority/freshness score at equal relevance;
    # an absent interval remains neutral because it means "not estimable", not "certain".
    multiplier *= pattern_uncertainty_multiplier(pattern_uncertainty)
    return base * multiplier


def pattern_uncertainty_multiplier(uncertainty: Any) -> float:
    """Convert a measured interval width into a pattern-only ranking multiplier.

    ``None`` is neutral because an unestimable interval is unknown, not evidence of certainty.
    Values are clamped defensively to the reducer's proportion domain so malformed index metadata
    cannot produce a score inversion or a negative rank.
    """
    if uncertainty is None:
        return 1.0
    try:
        value = float(uncertainty)
    except (TypeError, ValueError):
        return 1.0
    if not math.isfinite(value):
        return 1.0
    return max(0.0, 1.0 - min(1.0, max(0.0, value)))


def exact_identifier_hit(candidate: Candidate, exact_terms: list[str]) -> bool:
    """True when a quoted path/symbol/error/test name matches the candidate exactly.

    Compares lower-cased exact terms against the candidate's locator, id, and text
    (substring for paths/symbols, so ``graph.py`` matches ``src/instrument/graph.py``).
    """
    lowered_text = candidate.text.lower()
    lowered_locator = candidate.locator.lower()
    lowered_id = candidate.id.lower()
    for term in exact_terms:
        t = term.lower()
        if not t:
            continue
        if t in (lowered_locator, lowered_id, lowered_text):
            return True
        # allow exact path/symbol containment (never a bare word substring)
        if ("/" in t or "." in t or "_" in t) and (t in lowered_locator or t in lowered_text):
            return True
    return False


def scope_excluded(candidate_repository_id: str, requested_scope: str) -> bool:
    """Return True when a candidate is hard-excluded by the requested repository scope.

    Mirrors the commit pre-filter: the requested scope is the cell's ``repository_id``. A
    candidate carrying a *different, non-empty* scope is excluded — another cell's knowledge
    must never surface, even when its text is near-identical. An *empty* candidate scope is
    treated as unknown/legacy and stays eligible (back-compatible): it is unscoped data, not
    "global". An empty requested scope disables the filter (no exclusion).
    """
    return bool(
        requested_scope and candidate_repository_id and candidate_repository_id != requested_scope
    )


def graph_boost(seed_score: float, depth: int, relationship: str) -> float:
    """Decayed boost for a graph-expanded node: ``seed_score * weight * 0.7**depth``."""
    weight = RELATIONSHIP_WEIGHTS.get(relationship, 0.0)
    return seed_score * weight * (GRAPH_DECAY**depth)


def is_conflict_relationship(relationship: str) -> bool:
    return relationship in CONFLICT_RELATIONSHIPS


# ── Fusion + dedupe + selection (pure, testable) ────────────────


def fuse_candidates(
    candidates: list[Candidate],
    *,
    exact_terms: list[str],
    current_commit: str = "",
    now: datetime | None = None,
) -> list[Candidate]:
    """Score every candidate and drop excluded (stale/policy) ones.

    Sets ``fused_score`` and ``exact_identifier_match``; returns only candidates
    with a valid freshness multiplier, in descending score order.
    """
    scored: list[Candidate] = []
    for c in candidates:
        freshness = freshness_multiplier(
            authority=c.authority,
            commit_sha=c.commit_sha,
            observed_at=c.observed_at,
            current_commit=current_commit,
            now=now,
        )
        if freshness is None:
            continue
        exact = exact_identifier_hit(c, exact_terms)
        score = compute_fused_score(
            lexical_rank=c.lexical_rank,
            dense_rank=c.dense_rank,
            authority=c.authority,
            freshness=freshness,
            exact_identifier_match=exact,
            conflict=c.conflict,
            pattern_uncertainty=(
                c.pattern_payload.get("uncertainty")
                if c.is_pattern and c.pattern_payload is not None
                else None
            ),
        )
        scored.append(replace(c, fused_score=score, exact_identifier_match=exact))
    scored.sort(key=lambda c: c.fused_score, reverse=True)
    return scored


def deduplicate(candidates: list[Candidate]) -> list[Candidate]:
    """Collapse exact content-hash duplicates, keeping the best and merging provenance.

    Two candidates with the same ``content_hash`` (identical bytes) are the same
    knowledge; the higher-authority one wins (tie-broken by freshness), and the
    dropped candidate's locators are merged into the survivor's provenance.
    """
    groups: dict[str, list[Candidate]] = {}
    order: list[str] = []
    for c in candidates:
        key = c.content_hash or c.id
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(c)

    out: list[Candidate] = []
    for key in order:
        group = groups[key]
        if len(group) == 1:
            out.append(group[0])
            continue
        survivor = max(group, key=lambda c: (c.authority, c.observed_at or ""))
        merged_provenance = _dedupe_in_order(
            [p for c in group for p in ([c.locator] if c.locator else []) + c.provenance]
        )
        out.append(replace(survivor, provenance=merged_provenance))
    return out


def collapse_redundant(
    candidates: list[Candidate],
    similarities: dict[tuple[str, str], float],
    *,
    threshold: float = REDUNDANCY_THRESHOLD,
) -> list[Candidate]:
    """Collapse near-duplicates (cosine > threshold), but retain both sides of a conflict.

    ``similarities`` maps ``(id_a, id_b)`` to a cosine similarity in [0, 1]. A pair
    above ``threshold`` collapses to the higher-authority/fresher one — *unless*
    either side is ``conflict=True``, because deleting the lower-ranked side of a
    genuine contradiction would hide uncertainty from the executor.
    """
    dropped: set[str] = set()
    for i, a in enumerate(candidates):
        if a.id in dropped:
            continue
        for j in range(i + 1, len(candidates)):
            b = candidates[j]
            if b.id in dropped:
                continue
            sim = similarities.get((a.id, b.id), similarities.get((b.id, a.id), 0.0))
            if sim > threshold:
                if a.conflict or b.conflict:
                    continue  # keep both sides of a contradiction
                if (a.authority, a.observed_at or "") >= (b.authority, b.observed_at or ""):
                    dropped.add(b.id)
                else:
                    dropped.add(a.id)
    return [c for c in candidates if c.id not in dropped]


def _pairwise_similarities(
    candidates: list[Candidate], embedder: Any = None
) -> tuple[dict[tuple[str, str], float], str]:
    """Compute pairwise cosine similarities among candidates (or degrade to a no-op).

    Returns ``(similarities, path)``. ``similarities`` maps ``(id_a, id_b)`` to a
    similarity in ``[0, 1]`` (``1.0`` = identical) computed as ``1 - cosine_distance``
    over the embedder's vectors. When no embedder is supplied, fewer than two
    candidates survive, or embedding fails, returns ``({}, "none")`` so
    :func:`collapse_redundant` degrades to a no-op. ``path`` is ``"embedding"`` or
    ``"none"`` and is recorded on the attempt for audit (which dedupe leg actually
    ran).
    """
    if len(candidates) < 2 or embedder is None:
        return {}, "none"
    try:
        embeddings = [embedder.embed(c.text) for c in candidates]
        sims: dict[tuple[str, str], float] = {}
        for i in range(len(candidates)):
            for j in range(i + 1, len(candidates)):
                dist = embedder.cosine_distance(embeddings[i], embeddings[j])
                sims[(candidates[i].id, candidates[j].id)] = 1.0 - dist
        return sims, "embedding"
    except Exception:
        # Embedding infra unavailable (Ollama down, embedder missing, etc.) — the
        # collapse must degrade to a no-op, never crash the phase.
        return {}, "none"


def compute_token_budget(
    *,
    executor_context_tokens: int = 200_000,
    remaining_input_tokens: int = 200_000,
    rag_token_limit: int = DEFAULT_RAG_TOKEN_LIMIT,
) -> int:
    """Evidence budget = min(rag limit, 8000 default, 20% executor context, remaining input)."""
    return max(
        0,
        min(
            rag_token_limit,
            int(executor_context_tokens * DEFAULT_EXECUTOR_RAG_RATIO),
            remaining_input_tokens,
        ),
    )


def select_evidence(
    candidates: list[Candidate],
    *,
    token_budget: int,
    max_chunks_per_source: int | None = None,
) -> list[Candidate]:
    """Greedily select whole chunks under a token budget; never split a chunk.

    Candidates are already score-ordered; a chunk that does not fit is skipped, not
    truncated (splitting a symbol or dropping a citation would make the evidence
    unauditable). ``max_chunks_per_source`` bounds how many chunks one source may
    contribute, enforcing source diversity.
    """
    selected: list[Candidate] = []
    remaining = token_budget
    source_counts: dict[str, int] = {}
    for c in candidates:
        if c.token_count <= 0 or c.token_count > remaining:
            continue
        source = c.locator or c.id
        if (
            max_chunks_per_source is not None
            and source_counts.get(source, 0) >= max_chunks_per_source
        ):
            continue
        selected.append(c)
        remaining -= c.token_count
        source_counts[source] = source_counts.get(source, 0) + 1
    return selected


def resolve_fallback_mode(*, dense_ok: bool, lexical_ok: bool, graph_ok: bool) -> FallbackMode:
    """Map surviving leg sets to a named degradation mode (monotonic).

    Degradation is monotonic: full → lexical+graph → dense-only → no-RAG. A run
    that degrades is *named*, never silently pooled with full-RAG.
    """
    if dense_ok and lexical_ok and graph_ok:
        return FallbackMode.FULL
    if lexical_ok and graph_ok:
        return FallbackMode.LEXICAL_GRAPH_ONLY
    if dense_ok:
        return FallbackMode.DENSE_LOCAL_EXACT
    return FallbackMode.NO_RAG


# ── RetrievalAttempt (recorded before any LLM call) ─────────────


@dataclass
class RetrievalAttempt:
    """The full, auditable record of one retrieval pass — persisted before any LLM call."""

    query: str
    query_plan: QueryPlan
    filters: dict[str, Any]
    candidates: list[Candidate]
    ranks: dict[str, dict[str, int | None]]
    raw_scores: dict[str, dict[str, float | None]]
    graph_paths: dict[str, list[str]]
    selected_evidence: list[Candidate]
    token_count: int
    latency_ms: float
    cache_status: str
    fallback_mode: str
    dedup_path: str = ""  # "embedding" | "none" — which redundancy-collapse leg ran
    weights_version: str = WEIGHTS_VERSION
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "filters": self.filters,
            "ranks": self.ranks,
            "raw_scores": self.raw_scores,
            "graph_paths": self.graph_paths,
            "selected_evidence": [
                {
                    "id": c.id,
                    "citation": c.citation(),
                    "authority": c.authority.name,
                    "score": c.fused_score,
                    "token_count": c.token_count,
                    "conflict": c.conflict,
                    "graph_path": c.graph_path,
                    **({"source_type": c.source_type} if c.source_type else {}),
                    **(
                        {"pattern_payload": c.pattern_payload}
                        if c.pattern_payload is not None
                        else {}
                    ),
                }
                for c in self.selected_evidence
            ],
            "token_count": self.token_count,
            "latency_ms": self.latency_ms,
            "cache_status": self.cache_status,
            "dedup_path": self.dedup_path,
            "fallback_mode": self.fallback_mode,
            "weights_version": self.weights_version,
            "timestamp": self.timestamp,
        }


# ── Evidence cards (DeepSeek's unit — derived offline) ──────────


@dataclass
class EvidenceCard:
    """A derived one-line finding, precomputed offline — never synthesized at query time.

    The measured vector is (correctness, cost, flail); the three ledger signals
    (``confidence`` [H], ``test_executed_success`` [M], ``perturbation_strength`` [M])
    are ``None`` when unmeasured, so a card can distinguish "measured" from "absent"
    without ever fabricating a number.
    """

    run_id: str
    model: str
    operator: str
    perturbation_class: str
    strategy: str
    correctness: float
    cost: float
    flail: float
    confidence: float | None = None  # [H] execution-confidence; None = unmeasured
    test_executed_success: bool | None = None  # [M] independent suite; False = unverified
    perturbation_strength: float | None = None  # [M] strength axis (0.0 = baseline)
    text: str = ""  # the rendered one-line finding
    source_type: str = ""
    pattern_payload: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data = {
            "run_id": self.run_id,
            "model": self.model,
            "operator": self.operator,
            "perturbation_class": self.perturbation_class,
            "strategy": self.strategy,
            "correctness": self.correctness,
            "cost": self.cost,
            "flail": self.flail,
            "confidence": self.confidence,
            "test_executed_success": self.test_executed_success,
            "perturbation_strength": self.perturbation_strength,
            "text": self.text,
        }
        if self.source_type:
            data["source_type"] = self.source_type
        if self.pattern_payload is not None:
            data["pattern_payload"] = self.pattern_payload
        return data


def _finite_float(value: Any) -> float | None:
    """Coerce ``value`` to a finite float, or ``None`` when missing/NaN/infinite.

    A ``_results_summary.json`` run dict marks an unmeasured dimension with ``None``
    or ``NaN`` (see ``analyze_worktrees.py``); neither may leak into a card as a
    fabricated number. Mirrors ``signal_store._as_float`` so the card layer and the
    routing signal store agree on what "measured" means.
    """
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f):  # NaN and +/-inf are "unmeasured", never a number
        return None
    return f


def _derive_flail(run: dict[str, Any]) -> float:
    """Return the run's flail signal.

    Prefer an explicit ``flail`` column; when absent (the current ``load_results``
    vector has none), fall back to the basin escape rate — the per-run
    search-dynamics signal the lab books already treat as flail. NaN-safe: an
    unmeasured value falls through to ``0.0`` rather than rendering ``"flail nan"``.
    """
    flail = _finite_float(run.get("flail"))
    if flail is not None:
        return flail
    return _finite_float(run.get("escape")) or 0.0


def build_evidence_cards(runs: list[dict[str, Any]]) -> list[EvidenceCard]:
    """Derive one-line finding cards offline from ``load_results`` run dicts.

    One card per completed run, keyed off the measured vector (model, operator,
    strategy, correctness, cost, flail). Rows are skipped when ``narration_failure``
    is truthy or ``correctness`` is unmeasured (``None``/NaN) or negative — a flailed
    or unmeasured run must not become a trusted finding. The card text is a pure
    function of the vector, never an LLM.

    Input shape note (field-name confirmation): the run dicts are the
    ``_results_summary.json`` entries returned by :func:`signal_store.load_results`,
    *not* the Neo4j ``load_runs`` node properties. The two disagree on one name that
    matters here — ``cost`` in the summary vs the ``cost_usd`` property ``load_runs``
    copies it to (it likewise renames ``tokens``→``tokens_total``). This function
    reads the summary names, so it must be fed ``load_results()`` output, and it
    reuses that alias layer rather than hitting Neo4j.

    New ledger signals are consumed only when present (absent/NaN → ``None``, never a
    fabricated number):
      - ``confidence`` [H] — always shown, rendered ``"confidence —"`` when unmeasured.
      - ``perturbation_strength`` [M] — the numeric strength axis (0.0 = baseline);
        omitted from the card when unmeasured.
      - ``test_executed_success`` [M] (bool|None) — independent-suite pass/fail. A run
        with ``False`` is flagged ``UNVERIFIED`` in the text so a failed suite can
        never read as a verified finding (and the card's field lets a consumer
        down-weight or filter it).
    """
    cards: list[EvidenceCard] = []
    for run in runs:
        if run.get("narration_failure"):
            continue
        correctness = _finite_float(run.get("correctness"))
        if correctness is None or correctness < 0:
            continue
        model = run.get("model", "unknown")
        operator = run.get("operator", "unknown")
        pclass = run.get("perturbation_class", "")
        strategy = run.get("strategy", "?")
        cost = _finite_float(run.get("cost")) or 0.0
        flail = _derive_flail(run)
        run_id = str(run.get("worktree_name") or run.get("run_id") or "")
        source_type = str(run.get("source_type", "") or "").lower()
        pattern_payload = (
            _pattern_payload(run.get("pattern_payload"), str(run.get("text", "")))
            if source_type == "pattern"
            else None
        )

        # Ledger signals — measured-or-None, so an absent value never renders as 0.00.
        confidence = _finite_float(run.get("confidence"))
        perturbation_strength = _finite_float(run.get("perturbation_strength"))
        test_executed_success = run.get("test_executed_success")
        if not isinstance(test_executed_success, bool):
            test_executed_success = None  # a non-bool value is unmeasured, not a verdict

        operator_label = operator + (f" (class {pclass})" if pclass else "")
        text = (
            f"{model} under {operator_label} -> correctness {correctness:.2f}, "
            f"cost ${cost:.4f}, flail {flail:.2f}"
        )
        # confidence [H] is always present in the card so an absent signal can't be
        # mistaken for a low one — it renders an explicit em-dash placeholder instead.
        text += f", confidence {confidence:.2f}" if confidence is not None else ", confidence —"
        # perturbation_strength [M] only when measured.
        if perturbation_strength is not None:
            text += f", perturb_strength {perturbation_strength:.2f}"
        # test_executed_success [M] gates the verification claim: a failed suite must
        # be flagged so an unverified finding can never look verified.
        if test_executed_success is True:
            text += ", tests pass"
        elif test_executed_success is False:
            text += ", tests FAIL (unverified)"

        cards.append(
            EvidenceCard(
                run_id=run_id,
                model=model,
                operator=operator,
                perturbation_class=pclass,
                strategy=strategy,
                correctness=correctness,
                cost=cost,
                flail=flail,
                confidence=confidence,
                test_executed_success=test_executed_success,
                perturbation_strength=perturbation_strength,
                text=text,
                source_type=source_type,
                pattern_payload=pattern_payload,
            )
        )
    return cards


# ── Orchestration ───────────────────────────────────────────────


def _coerce_authority(value: Any) -> Authority:
    if isinstance(value, Authority):
        return value
    if isinstance(value, str):
        try:
            return Authority[value.upper()]
        except KeyError:
            return Authority.ADVISORY
    if isinstance(value, int):
        try:
            return Authority(value)
        except ValueError:
            return Authority.ADVISORY
    return Authority.ADVISORY


def _canonical_id(properties: dict[str, Any], fallback: str) -> str:
    """Resolve the canonical cross-store id from a node's properties."""
    for key in ("knowledge_id", "doc_id", "step_id", "entity_id"):
        if properties.get(key):
            return str(properties[key])
    return fallback


def _pattern_payload(value: Any, text: str) -> dict[str, Any] | None:
    """Decode the projection's structured payload from index metadata or its body.

    Chroma metadata is intentionally scalar-only in many deployments, so the producer may store
    the payload as JSON text. Neo4j projections already carry the canonical body. Invalid or
    incomplete payloads are not pattern candidates: retrieval must never manufacture a typed
    pattern surface from arbitrary narrative text.
    """
    if isinstance(value, dict):
        data = value
    elif all(
        hasattr(value, field)
        for field in (
            "claim",
            "population",
            "conditions",
            "support",
            "uncertainty",
            "validity_window",
            "source_experiment",
        )
    ):
        data = {
            "claim": value.claim,
            "population": value.population,
            "conditions": list(value.conditions),
            "support": value.support,
            "uncertainty": value.uncertainty,
            "validity_window": value.validity_window,
            "source_experiment": value.source_experiment,
        }
    elif isinstance(value, str) and value:
        try:
            data = json.loads(value)
        except json.JSONDecodeError:
            return None
    else:
        try:
            data = json.loads(text)
        except (TypeError, json.JSONDecodeError):
            return None
    if not isinstance(data, dict):
        return None
    required = {
        "claim",
        "population",
        "conditions",
        "support",
        "uncertainty",
        "validity_window",
        "source_experiment",
    }
    return data if required.issubset(data) else None


def _source_type(metadata: dict[str, Any], text: str = "") -> str:
    """Resolve a lower-case source type, recognizing only an explicit pattern payload fallback."""
    source_type = str(metadata.get("source_type", "") or "").lower()
    if not source_type and metadata.get("pattern_payload") is not None:
        source_type = "pattern"
    return source_type


def _candidate_allowed(
    source_type: str,
    *,
    pattern_projection: bool,
    authority: Authority | None = None,
    evidence_class: str = "",
) -> bool:
    """Apply the two-channel and C5 gates before a hit can become a candidate."""
    if source_type == "fact":
        return False
    if source_type != "pattern":
        return True
    return (
        pattern_projection
        and authority is Authority.DERIVED
        and (not evidence_class or evidence_class == "[C]")
    )


def retrieve(
    raw_work_item: str,
    *,
    dense_store: Any = None,
    graph_client: Any = None,
    phase_objective: str = "",
    commit_sha: str = "",
    repository_id: str = "",
    acl_scope: str = "",
    executor_context_tokens: int = 200_000,
    remaining_input_tokens: int = 200_000,
    rag_token_limit: int = DEFAULT_RAG_TOKEN_LIMIT,
    top_k: int = DEFAULT_TOP_K,
    seed_count: int = DEFAULT_SEED_COUNT,
    now: datetime | None = None,
    pattern_projection: bool = False,
) -> RetrievalAttempt:
    """Run the deterministic retrieval pipeline and record the attempt.

    Both legs run in parallel (a small thread pool); a leg failure marks that leg
    down rather than failing the pass, and the surviving set selects the named
    fallback mode. Survivors are fused, content-hash deduped, then cosine-collapsed
    (``collapse_redundant``, embeddings optional), graph-expanded, token-budgeted,
    and selected. The ``RetrievalAttempt`` is returned *before* any LLM call so the
    trace survives construction/execution failures.
    """
    t0 = time.monotonic()
    plan = build_query_plan(
        raw_work_item,
        phase_objective=phase_objective,
        pattern_projection=pattern_projection,
    )
    filters: dict[str, Any] = {
        "repository_id": repository_id,
        "commit_sha": commit_sha,
        "acl_scope": acl_scope,
    }

    dense_hits: list[dict[str, Any]] = []
    lexical_hits: list[dict[str, Any]] = []
    dense_ok = dense_store is not None
    lexical_ok = graph_client is not None
    graph_ok = graph_client is not None

    def _dense_leg():
        return dense_store.search(plan.dense_query, top_k=top_k, where=_dense_filter(filters))

    def _lexical_leg():
        # The lexical leg queries the *knowledge* full-text index (Knowledge.text),
        # not the Step index: KB records (findings/code/policy) are what we retrieve,
        # never the reasoning Step nodes. It applies the same hard commit pre-filter
        # as the dense leg: nodes with a non-matching, non-null commit_sha are
        # dropped in the store.
        return graph_client.search_knowledge_fulltext(
            plan.lexical_query, limit=top_k, commit=commit_sha
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {}
        if dense_ok:
            futures["dense"] = pool.submit(_dense_leg)
        if lexical_ok:
            futures["lexical"] = pool.submit(_lexical_leg)
        for name, fut in futures.items():
            try:
                if name == "dense":
                    dense_hits = fut.result()
                else:
                    lexical_hits = fut.result()
            except Exception:
                if name == "dense":
                    dense_ok = False
                else:
                    lexical_ok = False

    candidates: list[Candidate] = []
    ranks: dict[str, dict[str, int | None]] = {}
    raw_scores: dict[str, dict[str, float | None]] = {}
    graph_paths: dict[str, list[str]] = {}

    # Dense leg → candidates keyed by canonical id (already canonical from Chroma).
    dense_rank = 0
    for hit in dense_hits:
        cid = hit.get("id", "")
        meta = hit.get("metadata") or {}
        text = hit.get("document", "")
        source_type = _source_type(meta, text)
        authority = _coerce_authority(meta.get("authority"))
        if not _candidate_allowed(
            source_type,
            pattern_projection=plan.pattern_projection,
            authority=authority,
            evidence_class=str(meta.get("evidence_class", "") or ""),
        ):
            continue
        payload = (
            _pattern_payload(meta.get("pattern_payload"), text)
            if source_type == "pattern"
            else None
        )
        if source_type == "pattern" and payload is None:
            continue
        cand = Candidate(
            id=cid,
            text=text,
            content_hash=meta.get("content_hash", ""),
            authority=authority,
            locator=meta.get("logical_locator", cid),
            commit_sha=meta.get("commit_sha", commit_sha),
            repository_id=meta.get("repository_id", ""),
            observed_at=meta.get("observed_at"),
            dense_rank=dense_rank,
            dense_score=hit.get("distance"),
            token_count=_estimate_tokens(text),
            source_type=source_type,
            pattern_payload=payload,
            evidence_class=str(meta.get("evidence_class", "") or ""),
        )
        candidates.append(cand)
        ranks.setdefault(cid, {})["dense"] = dense_rank
        raw_scores.setdefault(cid, {})["dense"] = hit.get("distance")
        dense_rank += 1

    # Lexical leg → candidates keyed by canonical id (resolved from node properties).
    lexical_rank = 0
    for hit in lexical_hits:
        props = hit.get("properties") or {}
        cid = _canonical_id(props, hit.get("id", ""))
        text = props.get("text", "")
        source_type = _source_type(props, text)
        authority = _coerce_authority(props.get("authority"))
        if not _candidate_allowed(
            source_type,
            pattern_projection=plan.pattern_projection,
            authority=authority,
            evidence_class=str(props.get("evidence_class", "") or ""),
        ):
            continue
        payload = (
            _pattern_payload(props.get("pattern_payload"), text)
            if source_type == "pattern"
            else None
        )
        if source_type == "pattern" and payload is None:
            continue
        existing = next((c for c in candidates if c.id == cid), None)
        if existing is not None:
            existing.lexical_rank = lexical_rank
            existing.lexical_score = hit.get("score")
            if source_type == "pattern":
                existing.source_type = source_type
                existing.pattern_payload = payload
            ranks.setdefault(cid, {})["lexical"] = lexical_rank
            raw_scores.setdefault(cid, {})["lexical"] = hit.get("score")
            lexical_rank += 1
            continue
        candidates.append(
            Candidate(
                id=cid,
                text=text,
                content_hash=props.get("content_hash", ""),
                authority=authority,
                locator=props.get("logical_locator", props.get("doc_id", cid)),
                commit_sha=props.get("commit_sha", commit_sha),
                repository_id=props.get("repository_id", ""),
                observed_at=props.get("observed_at"),
                lexical_rank=lexical_rank,
                lexical_score=hit.get("score"),
                token_count=_estimate_tokens(text),
                source_type=source_type,
                pattern_payload=payload,
                evidence_class=str(props.get("evidence_class", "") or ""),
            )
        )
        ranks.setdefault(cid, {})["lexical"] = lexical_rank
        raw_scores.setdefault(cid, {})["lexical"] = hit.get("score")
        lexical_rank += 1

    # Scope isolation (HARD pre-filter): the cell's repository_id must never leak another
    # cell's knowledge, even when the two scopes hold near-identical text. Applied before
    # fusion so an excluded candidate can never become a graph-expansion seed.
    requested_scope = str(filters.get("repository_id", ""))
    if requested_scope:
        candidates = [c for c in candidates if not scope_excluded(c.repository_id, requested_scope)]

    # Fuse, content-hash dedupe, then cosine-redundancy collapse (conflicts survive).
    fused = fuse_candidates(
        candidates, exact_terms=plan.exact_terms, current_commit=commit_sha, now=now
    )
    fused = deduplicate(fused)

    # Redundancy collapse: cosine > threshold dedupe over the surviving candidates.
    # Embeddings are optional (local Ollama) — when unavailable the similarities dict
    # is empty and collapse_redundant is a no-op; the path is recorded on the attempt.
    embedder: Any = None
    try:
        from agentic_dynamics.knowledge.embeddings import EmbeddingClient

        embedder = EmbeddingClient()
    except Exception:
        embedder = None  # optional dep missing → collapse degrades to a no-op
    similarities, dedup_path = _pairwise_similarities(fused, embedder)
    fused = collapse_redundant(fused, similarities)

    # Then expand the strongest seeds through the graph (decayed boost).
    if graph_client is not None and fused:
        try:
            seeds = [c.id for c in fused[:seed_count]]
            # Seed canonical id → real fused score, for scoring expanded hops below.
            seed_scores = {c.id: c.fused_score for c in fused[:seed_count]}
            expanded = graph_client.expand_candidates(
                seeds,
                max_depth=2,
                max_neighbors=8,
                max_nodes=40,
                timeout_ms=300,
                repository_id=repository_id,
                acl_scope=acl_scope,
            )
            fused_ids = {c.id for c in fused}
            for node in expanded:
                props = node.get("properties") or {}
                # Prefer the canonical id the graph leg already resolved; fall back to
                # deriving it from properties (elementId last) for resilience.
                cid = node.get("canonical_id") or _canonical_id(props, node.get("id", ""))
                if cid in fused_ids:
                    continue  # already a direct seed candidate — never re-added
                source_type = _source_type(props, props.get("text", ""))
                authority = _coerce_authority(props.get("authority"))
                if not _candidate_allowed(
                    source_type,
                    pattern_projection=plan.pattern_projection,
                    authority=authority,
                    evidence_class=str(props.get("evidence_class", "") or ""),
                ):
                    continue
                payload = (
                    _pattern_payload(props.get("pattern_payload"), props.get("text", ""))
                    if source_type == "pattern"
                    else None
                )
                if source_type == "pattern" and payload is None:
                    continue
                if scope_excluded(props.get("repository_id", ""), requested_scope):
                    continue  # another cell's neighbor never surfaces via expansion
                origin = node.get("origin_seed") or ""
                seed_score = seed_scores.get(origin)
                if seed_score is None or seed_score <= 0:
                    # Origin seed unresolvable/zero-scored → skip cleanly, never a
                    # zero-score hit.
                    continue
                depth = int(node.get("depth", 0))
                rel_type = str(node.get("rel_type") or "")
                weight = RELATIONSHIP_WEIGHTS.get(rel_type, 0.0)
                # Real seed score × relationship weight × decay — the boost, not a peer.
                boost = graph_boost(seed_score, depth, rel_type)
                fused.append(
                    Candidate(
                        id=cid,
                        text=props.get("text", ""),
                        content_hash=props.get("content_hash", ""),
                        authority=authority,
                        locator=props.get("logical_locator", cid),
                        commit_sha=props.get("commit_sha", commit_sha),
                        repository_id=props.get("repository_id", ""),
                        observed_at=props.get("observed_at"),
                        graph_depth=depth,
                        graph_path=list(node.get("path", [])),
                        relationship_weight=weight,
                        token_count=_estimate_tokens(props.get("text", "")),
                        fused_score=boost,
                        source_type=source_type,
                        pattern_payload=payload,
                        evidence_class=str(props.get("evidence_class", "") or ""),
                    )
                )
        except Exception:
            graph_ok = False

    # Record any graph traversal paths on the expanded candidates.
    graph_paths = {c.id: c.graph_path for c in fused if c.graph_path}

    budget = compute_token_budget(
        executor_context_tokens=executor_context_tokens,
        remaining_input_tokens=remaining_input_tokens,
        rag_token_limit=rag_token_limit,
    )
    selected = select_evidence(fused, token_budget=budget, max_chunks_per_source=2)

    fallback = resolve_fallback_mode(dense_ok=dense_ok, lexical_ok=lexical_ok, graph_ok=graph_ok)

    attempt = RetrievalAttempt(
        query=raw_work_item,
        query_plan=plan,
        filters=filters,
        candidates=fused,
        ranks=ranks,
        raw_scores=raw_scores,
        graph_paths=graph_paths,
        selected_evidence=selected,
        token_count=sum(c.token_count for c in selected),
        latency_ms=round((time.monotonic() - t0) * 1000.0, 2),
        cache_status="unknown",
        dedup_path=dedup_path,
        fallback_mode=fallback.value,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    return attempt


def _dense_filter(filters: dict[str, Any]) -> dict[str, Any]:
    """Build the Chroma ``where`` metadata filter from hard scope filters.

    Chroma requires a ``where`` dict to carry exactly one top-level key, so multiple
    conditions are combined under ``$and`` (a bare multi-key dict is rejected by
    ``validate_where``). The commit scope is a HARD pre-filter: a stored chunk is
    eligible only when its ``commit_sha`` is empty (unknown/current) or equals the
    worktree's commit — stale-commit docs never surface from the dense leg at all.
    """
    conditions: list[dict[str, Any]] = []
    if filters.get("repository_id"):
        conditions.append({"repository_id": filters["repository_id"]})
    if filters.get("acl_scope"):
        conditions.append({"acl_scope": filters["acl_scope"]})
    commit = filters.get("commit_sha")
    if commit:
        conditions.append(
            {
                "$or": [
                    {"commit_sha": ""},
                    {"commit_sha": commit},
                ]
            }
        )
    if not conditions:
        return {}
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


def render_evidence_packet(selected: list[Candidate]) -> str:
    """Render the selected evidence as a delimited, untrusted evidence packet."""
    if not selected:
        return ""
    lines = []
    for c in selected:
        surface = f" | surface={c.source_type}" if c.source_type else ""
        pattern = (
            f" | pattern={json.dumps(c.pattern_payload, sort_keys=True)}"
            if c.pattern_payload is not None
            else ""
        )
        lines.append(
            f"{c.citation()} | authority={c.authority.name} | score={c.fused_score:.4f}"
            f"{surface}{pattern}\n{c.text}"
        )
    return "\n\n".join(lines)
