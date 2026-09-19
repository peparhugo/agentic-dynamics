"""Neo4j-native vector store for the dense retrieval leg — replaces the Chroma service.

Operator decision, 2026-09-19: after the second root-caused outage class (a per-record HTTP
session leak to EMFILE; a persistence path that silently lived in the container layer; a
python server whose image carries no health tooling), the dense leg moves into the store the
pipeline already runs and trusts. The embeddings ride the SAME ``Knowledge`` nodes the
lexical leg reads, so one projection keeps both legs current and one connection pool serves
both — there is no second server left to stall independently.

Review round 2026-09-19 (post-#89): scoped recall is fixed by BOUNDED CANDIDATE EXPANSION with
an explicit incomplete state (Neo4j 5.26 has no filtered vector procedure); the write path
persists the canonical scope metadata it acknowledges; the returned fields keep the timestamps
and identities the fusion/freshness rules consume; every database call carries an explicit
transaction timeout; and the backfill reports timing and fails loudly.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any

from agentic_dynamics.knowledge.embeddings import EmbeddingClient
from agentic_dynamics.knowledge.graph import Neo4jClient

#: The one vector index over ``Knowledge.embedding`` (created lazily, idempotent).
VECTOR_INDEX = "knowledge_embeddings_v1"
#: The node property carrying the embedding vector.
EMBEDDING_PROP = "embedding"
#: bge-m3's output dimension.
DEFAULT_DIMENSIONS = 1024
#: Nodes embedded per upsert round trip.
DEFAULT_BATCH = 32
#: Embedding input clip (bge-m3's context is 8192 tokens; ~4 chars/token with margin). An
#: oversized record must be clipped and embedded — not abort the migration (observed live:
#: one long document 500'd the batch AND the old pass exited 0).
EMBED_MAX_CHARS = 6000
#: Per-database-call transaction timeout (seconds). ``FINOPS_NEO4J_TIMEOUT_S`` overrides.
DEFAULT_TIMEOUT_S = 10.0
TIMEOUT_ENV = "FINOPS_NEO4J_TIMEOUT_S"
#: Candidate-expansion bounds (review P1): the vector index returns the GLOBAL nearest k and
#: the scope predicate filters afterwards, so a scope dominated by other tenants can crowd
#: out every valid hit. k grows by ``EXPANSION_FACTOR`` until the scoped set is full, the
#: index is exhausted, or ``EXPANSION_CAP`` global rows were scanned — the cap leaves
#: ``last_search_incomplete`` true rather than silently returning nothing.
EXPANSION_FACTOR = 4
EXPANSION_CAP = 4096

#: The properties returned for a hit, mirrored into the Chroma-shaped metadata dict. The
#: fusion and freshness rules consume timestamps and content identity, so they travel too.
_HIT_FIELDS = (
    "repository_id",
    "acl_scope",
    "commit_sha",
    "authority",
    "source_type",
    "evidence_class",
    "logical_locator",
    "observed_at",
    "content_hash",
    "pattern_payload",
)

#: The canonical metadata an acknowledged vector write persists (review P2): the separate
#: graph consumer may lag or fail, so a record the vector worker accepts must already be
#: scoped-retrievable by itself.
_METADATA_KEYS = (
    "repository_id",
    "acl_scope",
    "authority",
    "source_type",
    "evidence_class",
    "logical_locator",
    "commit_sha",
    "observed_at",
    "content_hash",
    "source_uri",
    "entity_id",
)

_ENSURED_LOCK = threading.Lock()
_ENSURED_INDEXES: set[tuple[str, int]] = set()


class Neo4jVectorStoreError(RuntimeError):
    """Raised when the vector store cannot serve a request."""


def _predicate(where: dict[str, Any] | None, params: dict[str, Any], start: int = 0) -> str:
    """Translate the constrained Chroma-style ``where`` dict into a Cypher predicate.

    The retrieval pipeline builds exactly this vocabulary (``_dense_filter``): equality on
    scalar fields, ``$and``/``$or`` combinators, and ``$eq`` leaves. Anything else is
    refused loudly — a filter silently dropped would widen the scope of a scoped read.
    """

    def walk(node: Any) -> str:
        if not isinstance(node, dict):
            raise Neo4jVectorStoreError(f"unsupported where node: {node!r}")
        clauses: list[str] = []
        for key, value in node.items():
            if key == "$and":
                clauses.append("(" + " AND ".join(walk(item) for item in value) + ")")
            elif key == "$or":
                clauses.append("(" + " OR ".join(walk(item) for item in value) + ")")
            elif key == "$eq":
                raise Neo4jVectorStoreError("$eq must wrap a field, not stand alone")
            else:
                if isinstance(value, dict):
                    if set(value) != {"$eq"}:
                        raise Neo4jVectorStoreError(f"unsupported operator on {key!r}: {value!r}")
                    value = value["$eq"]
                name = f"p{len(params) + start}"
                params[name] = value
                clauses.append(f"node.{key} = ${name}")
        if not clauses:
            raise Neo4jVectorStoreError("empty where clause")
        return " AND ".join(clauses)

    if not where:
        return ""
    return walk(where)


def _checkpoint(ids: list[str]) -> str:
    return hashlib.sha256("\x1f".join(sorted(ids)).encode("utf-8")).hexdigest()


class Neo4jVectorStore:
    """The dense leg's store: embeddings as node properties, kNN via Neo4j's vector index."""

    def __init__(
        self,
        client: Neo4jClient | None = None,
        *,
        embedder: EmbeddingClient | None = None,
        dimensions: int = DEFAULT_DIMENSIONS,
        timeout_s: float | None = None,
        ensure_index: bool = True,
    ):
        self._client = client or Neo4jClient()
        self._embedder = embedder or EmbeddingClient()
        self.dimensions = int(dimensions)
        self.timeout_s = (
            float(timeout_s)
            if timeout_s is not None
            else float(os.environ.get(TIMEOUT_ENV, DEFAULT_TIMEOUT_S))
        )
        #: The last search's expansion state — ``incomplete`` is the explicit signal that the
        #: scope may hold more valid hits beyond the scanned cap (review P1).
        self.last_search_stats: dict[str, Any] = {}
        self.last_search_incomplete = False
        self._corpus_count = -1  # lazily fetched for filtered searches (see search)
        if ensure_index:
            # Index DDL happens OUTSIDE ordinary queries (review: perf), once per process.
            self.ensure_index()

    # ── lifecycle ───────────────────────────────────────────────────────────────────────────

    def ensure_index(self) -> None:
        """Create the vector index if absent (idempotent, once per process)."""
        key = (VECTOR_INDEX, self.dimensions)
        with _ENSURED_LOCK:
            if key in _ENSURED_INDEXES:
                return
        self._run_write(
            "CREATE VECTOR INDEX "
            + VECTOR_INDEX
            + " IF NOT EXISTS FOR (k:Knowledge) ON (k."
            + EMBEDDING_PROP
            + ") OPTIONS {indexConfig: {`vector.dimensions`: $dims, "
            "`vector.similarity_function`: 'cosine'}}",
            {"dims": self.dimensions},
        )
        with _ENSURED_LOCK:
            _ENSURED_INDEXES.add(key)

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self._client.close()

    def _run_read(self, cypher: str, params: dict[str, Any]) -> list[Any]:
        """One auto-commit-free read with an EXPLICIT transaction timeout (review: perf)."""
        try:
            with self._client._driver.session() as s:
                tx = s.begin_transaction(timeout=self.timeout_s)
                try:
                    return list(tx.run(cypher, **params))
                finally:
                    tx.close()
        except Exception as exc:  # noqa: BLE001 — the caller names the leg failure
            raise Neo4jVectorStoreError(f"vector read failed: {exc}") from exc

    def _run_write(self, cypher: str, params: dict[str, Any]) -> None:
        try:
            with self._client._driver.session() as s:
                tx = s.begin_transaction(timeout=self.timeout_s)
                try:
                    tx.run(cypher, **params)
                    tx.commit()
                finally:
                    tx.close()
        except Exception as exc:  # noqa: BLE001 — the caller names the write failure
            raise Neo4jVectorStoreError(f"vector write failed: {exc}") from exc

    # ── writes ──────────────────────────────────────────────────────────────────────────────

    def upsert(
        self,
        ids: list[str],
        documents: list[str] | None = None,
        metadatas: list[dict[str, Any]] | None = None,
        embeddings: list[list[float]] | None = None,
    ) -> int:
        """Set ``embedding`` (and the acknowledged canonical metadata) on each record's node.

        The nodes are created by the lexical projection; a missing node is MERGEd with the id
        and text so the dense leg also works standalone. Every metadata field the caller
        provides from :data:`_METADATA_KEYS` is persisted with the vector — a lagging or
        failed graph consumer can no longer leave an acknowledged record unscoped (review
        P2). ``pattern_payload`` maps are stored as canonical JSON (Neo4j properties are
        scalar).
        """
        if not ids:
            return 0
        docs = list(documents or ["" for _ in ids])
        vectors = embeddings if embeddings is not None else [self._embedder.embed(d) for d in docs]
        if len(vectors) != len(ids):
            raise Neo4jVectorStoreError(
                f"embedding count {len(vectors)} != id count {len(ids)}"
            )
        rows = []
        for i, (kid, vec) in enumerate(zip(ids, vectors, strict=True)):
            row: dict[str, Any] = {"id": kid, "vec": vec, "text": docs[i] if i < len(docs) else ""}
            meta = (metadatas[i] if metadatas and i < len(metadatas) else {}) or {}
            for keep in _METADATA_KEYS:
                value = meta.get(keep)
                row[keep] = value if value not in (None, "") else None
            payload = meta.get("pattern_payload")
            if isinstance(payload, dict):
                row["pattern_payload"] = json.dumps(payload, sort_keys=True)
            elif isinstance(payload, str) and payload:
                row["pattern_payload"] = payload
            else:
                row["pattern_payload"] = None
            rows.append(row)
        set_parts = [f"k.{EMBEDDING_PROP} = row.vec", "k.text = coalesce(k.text, row.text)"]
        for keep in _METADATA_KEYS + ("pattern_payload",):
            set_parts.append(f"k.{keep} = coalesce(row.{keep}, k.{keep})")
        cypher = (
            "UNWIND $rows AS row "
            "MERGE (k:Knowledge {knowledge_id: row.id}) "
            "SET " + ", ".join(set_parts)
        )
        for start in range(0, len(rows), DEFAULT_BATCH):
            self._run_write(cypher, {"rows": rows[start : start + DEFAULT_BATCH]})
        return len(ids)

    def delete(self, ids: list[str]) -> None:
        """Remove the embeddings (the Knowledge nodes themselves belong to the lexical leg)."""
        if not ids:
            return
        self._run_write(
            "UNWIND $ids AS id MATCH (k:Knowledge {knowledge_id: id}) REMOVE k."
            + EMBEDDING_PROP,
            {"ids": list(ids)},
        )

    # ── reads ───────────────────────────────────────────────────────────────────────────────

    def _search_cypher(self, pred: str) -> str:
        return (
            "CALL db.index.vector.queryNodes($index, $k, $vec) YIELD node, score "
            + (f"WHERE {pred} " if pred else "")
            + "RETURN node.knowledge_id AS id, node.text AS document, score, "
            + ", ".join(f"node.{field} AS {field}" for field in _HIT_FIELDS)
            + " ORDER BY score DESC LIMIT $limit"
        )

    def search(
        self,
        query: str,
        top_k: int = 10,
        filter_model: str | None = None,
        filter_strategy: str | None = None,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Semantic search, scope-aware by BOUNDED CANDIDATE EXPANSION.

        Each round asks the vector index for the global nearest ``k``; the scope predicate
        filters them. ``k`` grows by ``EXPANSION_FACTOR`` until the scoped set is full, the
        index is exhausted (fewer rows than requested), or ``EXPANSION_CAP`` global rows were
        scanned. A capped search with fewer than ``top_k`` scoped hits sets
        ``last_search_incomplete`` — the caller can tell "no relevant evidence" from "the
        scan bound was reached" (review P1).
        """
        merged: dict[str, Any] = dict(where) if where else {}
        if filter_model:
            merged["model"] = filter_model
        if filter_strategy:
            merged["strategy"] = filter_strategy
        vector = self._embedder.embed(query)
        params: dict[str, Any] = {"index": VECTOR_INDEX, "vec": vector, "limit": int(top_k)}
        pred = _predicate(merged, params)
        cypher = self._search_cypher(pred)
        limit = int(top_k)
        # A FILTERED search cannot judge exhaustion from a short page: the WHERE hides the
        # global rows behind the filter, so "3 scoped hits from k=64" does not mean the
        # index is empty at this scope. The corpus total is the only sound bound (fetched
        # once per store instance; embedding counts move slowly).
        if pred and self._corpus_count < 0:
            self._corpus_count = self.count()
        total = self._corpus_count if pred else 0
        k = max(limit, EXPANSION_FACTOR)
        scanned = 0
        hits: list[dict[str, Any]] = []
        full = False
        while True:
            params["k"] = min(k, EXPANSION_CAP)
            rows = self._run_read(cypher, params)
            hits = [self._hit(rec) for rec in rows]
            scanned = params["k"]
            if len(hits) >= limit:
                full = True
                break
            if scanned >= EXPANSION_CAP or (total and scanned >= total):
                break  # the cap — or the whole embedded corpus — is scanned
            if not pred and len(rows) < scanned:
                break  # unfiltered: a short page is the index's own exhaustion
            k = min(scanned * EXPANSION_FACTOR, EXPANSION_CAP)
        self.last_search_stats = {
            "scanned": scanned,
            "returned": len(hits),
            "limit": limit,
            "corpus": total or None,
            # Explicit incomplete state (review P1): the scan hit the cap while the corpus
            # may still hold scoped candidates deeper in the ranking.
            "incomplete": (not full) and scanned >= EXPANSION_CAP and (not total or total > scanned),
        }
        self.last_search_incomplete = bool(self.last_search_stats["incomplete"])
        return hits[:limit]

    @staticmethod
    def _hit(rec: Any) -> dict[str, Any]:
        return {
            "id": str(rec["id"] or ""),
            "document": str(rec["document"] or ""),
            "metadata": {
                field: (rec[field] if rec[field] is not None else "") for field in _HIT_FIELDS
            },
            "distance": 1.0 - float(rec["score"] or 0.0),
        }

    def count(self) -> int:
        rows = self._run_read(
            "MATCH (k:Knowledge) WHERE k." + EMBEDDING_PROP + " IS NOT NULL RETURN count(k) AS n",
            {},
        )
        return int(rows[0]["n"]) if rows else 0

    def eligible_remaining(self) -> int:
        """Nodes eligible for embedding that still lack one (the migration's remainder)."""
        rows = self._run_read(
            "MATCH (k:Knowledge) WHERE k." + EMBEDDING_PROP
            + " IS NULL AND k.text IS NOT NULL AND k.text <> '' RETURN count(k) AS n",
            {},
        )
        return int(rows[0]["n"]) if rows else 0

    def inventory(self) -> dict[str, Any]:
        rows = self._run_read(
            "MATCH (k:Knowledge) WHERE k." + EMBEDDING_PROP + " IS NOT NULL "
            "RETURN k.knowledge_id AS id",
            {},
        )
        ids = [str(rec["id"]) for rec in rows]
        return {"count": len(ids), "ids": ids, "checkpoint": _checkpoint(ids)}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def backfill(*, limit: int = 0, batch: int = 16, source_type: str = "", log: Any = print) -> dict[str, Any]:
    """Embed Knowledge nodes that lack an embedding — bounded, resumable, measurable.

    Embedding and write time are measured separately (review: perf) because the database
    choice does not remove the embedder cost. A batch failure stops the pass and is
    REPORTED (the CLI exits nonzero), so automation cannot read an incomplete migration as
    success (review P2).
    """
    store = Neo4jVectorStore()
    embedded = 0
    skipped = 0
    failed = False
    embed_s = 0.0
    write_s = 0.0
    where = "WHERE k." + EMBEDDING_PROP + " IS NULL AND k.text IS NOT NULL AND k.text <> ''"
    params: dict[str, Any] = {}
    if source_type:
        where += " AND k.source_type = $stype"
        params["stype"] = source_type
    while True:
        if limit and embedded >= limit:
            break
        take = min(batch, limit - embedded) if limit else batch
        rows = store._run_read(
            "MATCH (k:Knowledge) " + where + " RETURN k.knowledge_id AS id, k.text AS text "
            "LIMIT $n",
            {"n": take, **params},
        )
        if not rows:
            break
        ids = [str(r["id"]) for r in rows]
        texts = [str(r["text"]) for r in rows]
        clipped = sum(1 for text in texts if len(text) > EMBED_MAX_CHARS)
        try:
            t0 = time.monotonic()
            vectors = store._embedder.embed_batch(
                [text[:EMBED_MAX_CHARS] for text in texts], batch_size=len(texts)
            )
            t1 = time.monotonic()
            store.upsert(ids, documents=texts, embeddings=vectors)
            t2 = time.monotonic()
            embed_s += t1 - t0
            write_s += t2 - t1
            embedded += len(ids)
            log(
                f"[backfill] embedded {embedded} (batch {len(ids)}; clipped {clipped}; "
                f"embed {t1 - t0:.2f}s, write {t2 - t1:.2f}s) at {_now()}"
            )
        except Exception as exc:  # noqa: BLE001 — a bad record must not stop the pass
            log(f"[backfill] batch failed after {embedded}: {exc} — retrying per record")
            recovered = 0
            for kid, text in zip(ids, texts, strict=True):
                try:
                    vector = store._embedder.embed(text[:EMBED_MAX_CHARS])
                    store.upsert([kid], documents=[text], embeddings=[vector])
                    recovered += 1
                except Exception as one:  # noqa: BLE001 — named and counted
                    log(f"[backfill] skipped {kid[:12]}: {one}")
            embedded += recovered
            skipped += len(ids) - recovered
            if recovered == 0:
                # Nothing in the batch could be embedded: infrastructure, not data. Stop and
                # let the CLI report failure (never a silent zero).
                failed = True
                break
    remaining = store.eligible_remaining()
    log(
        f"[backfill] done: embedded={embedded} skipped={skipped} with_embedding={store.count()} "
        f"eligible_remaining={remaining} embed_s={embed_s:.1f} write_s={write_s:.1f}"
    )
    return {
        "embedded": embedded,
        "skipped": skipped,
        "total": store.count(),
        "remaining": remaining,
        "failed": failed,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Neo4j vector store maintenance (dense leg)")
    ap.add_argument("--backfill", action="store_true", help="embed nodes lacking an embedding")
    ap.add_argument("--limit", type=int, default=0, help="cap this pass (0 = all)")
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--source-type", default="", help="restrict the pass to one source_type")
    ap.add_argument("--count", action="store_true", help="print the embedded-node count")
    ap.add_argument("--search", action="store_true", help="run one semantic search")
    ap.add_argument("--query", default="", help="the search query text")
    args = ap.parse_args(argv)

    if args.backfill:
        result = backfill(limit=args.limit, batch=args.batch, source_type=args.source_type)
        if result["failed"]:
            print(f"BACKFILL FAILED: {result['skipped']} records unprocessed; "
                  f"eligible_remaining={result['remaining']}")
            return 1
        if not args.limit and result["remaining"] > 0:
            print(f"BACKFILL INCOMPLETE: eligible_remaining={result['remaining']} "
                  "(re-run to continue)")
            return 1
        print(f"backfill: embedded={result['embedded']} "
              f"with_embedding={result['total']} eligible_remaining={result['remaining']} "
              + ("(requested batch completed)" if args.limit else "(all eligible indexed)"))
        return 0
    store = Neo4jVectorStore()
    if args.count:
        print(f"nodes with embedding: {store.count()} | eligible_remaining: {store.eligible_remaining()}")
        return 0
    if args.search:
        hits = store.search(args.query, top_k=5, where={"repository_id": "agentic-dynamics", "acl_scope": "public"})
        for hit in hits:
            print(f"{hit['distance']:.4f}  {hit['id'][:16]}  "
                  f"{hit['metadata'].get('source_type')}  {hit['id']}")
        print(f"search stats: {store.last_search_stats}")
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
