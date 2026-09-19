"""Neo4j-native vector store for the dense retrieval leg — replaces the Chroma service.

Operator decision, 2026-09-19: after the second root-caused outage class (a per-record HTTP
session leak to EMFILE; a persistence path that silently lived in the container layer; a
python server whose image carries no health tooling), the dense leg moves into the store the
pipeline already runs and trusts. The embeddings ride the SAME ``Knowledge`` nodes the
lexical leg reads, so one projection keeps both legs current and one connection pool serves
both — there is no second server left to stall independently.

Interface parity with the retired store: ``upsert`` / ``search`` / ``count`` / ``inventory``
return the same shapes the fusion and selection code consumed from ``ChromaStore``, so the
retrieval pipeline is untouched beyond the construction site.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import sys
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

#: The properties returned for a hit, mirrored into the Chroma-shaped metadata dict.
_HIT_FIELDS = (
    "repository_id",
    "acl_scope",
    "commit_sha",
    "authority",
    "source_type",
    "evidence_class",
    "logical_locator",
)


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
                # ``{"field": {"$eq": v}}`` arrives as key=field, value={"$eq": v}
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
    ):
        self._client = client or Neo4jClient()
        self._embedder = embedder or EmbeddingClient()
        self.dimensions = int(dimensions)
        self._index_ready = False

    # ── lifecycle ───────────────────────────────────────────────────────────────────────────

    def ensure_index(self) -> None:
        """Create the vector index if absent (idempotent; safe on every process start)."""
        if self._index_ready:
            return
        with self._client._driver.session() as s:
            s.run(
                "CREATE VECTOR INDEX "
                + VECTOR_INDEX
                + " IF NOT EXISTS FOR (k:Knowledge) ON (k."
                + EMBEDDING_PROP
                + ") OPTIONS {indexConfig: {`vector.dimensions`: $dims, "
                "`vector.similarity_function`: 'cosine'}}",
                dims=self.dimensions,
            )
        self._index_ready = True

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self._client.close()

    # ── writes ──────────────────────────────────────────────────────────────────────────────

    def upsert(
        self,
        ids: list[str],
        documents: list[str] | None = None,
        metadatas: list[dict[str, Any]] | None = None,
        embeddings: list[list[float]] | None = None,
    ) -> int:
        """Set ``embedding`` on each ``Knowledge`` node identified by ``knowledge_id``.

        The nodes are created by the lexical projection (kb-neo4j-v1); a missing node is
        MERGEd with the id and (when provided) the text, so the dense leg can also run
        standalone on a fresh database. Idempotent: the same id always converges to the same
        vector for the same text.
        """
        if not ids:
            return 0
        self.ensure_index()
        docs = list(documents or ["" for _ in ids])
        vectors = embeddings if embeddings is not None else [self._embedder.embed(d) for d in docs]
        if len(vectors) != len(ids):
            raise Neo4jVectorStoreError(f"embedding count {len(vectors)} != id count {len(ids)}")
        rows = [
            {"id": kid, "vec": vec, "text": docs[i] if i < len(docs) else ""}
            for i, (kid, vec) in enumerate(zip(ids, vectors, strict=True))
        ]
        with self._client._driver.session() as s:
            for start in range(0, len(rows), DEFAULT_BATCH):
                s.run(
                    "UNWIND $rows AS row "
                    "MERGE (k:Knowledge {knowledge_id: row.id}) "
                    "SET k." + EMBEDDING_PROP + " = row.vec, "
                    "k.text = coalesce(k.text, row.text)",
                    rows=rows[start : start + DEFAULT_BATCH],
                )
        return len(ids)

    def delete(self, ids: list[str]) -> None:
        """Remove the embeddings (the Knowledge nodes themselves belong to the lexical leg)."""
        if not ids:
            return
        with self._client._driver.session() as s:
            s.run(
                "UNWIND $ids AS id MATCH (k:Knowledge {knowledge_id: id}) "
                "REMOVE k." + EMBEDDING_PROP,
                ids=list(ids),
            )

    # ── reads ───────────────────────────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        top_k: int = 10,
        filter_model: str | None = None,
        filter_strategy: str | None = None,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Semantic search over the Knowledge embeddings, with the hard scope pre-filters.

        ``where`` is the pipeline's constrained vocabulary (see :func:`_predicate`); a
        filtered query over-fetches before filtering so the caller still receives up to
        ``top_k`` scoped hits.
        """
        merged: dict[str, Any] = dict(where) if where else {}
        if filter_model:
            merged["model"] = filter_model
        if filter_strategy:
            merged["strategy"] = filter_strategy
        self.ensure_index()
        vector = self._embedder.embed(query)
        params: dict[str, Any] = {"index": VECTOR_INDEX, "vec": vector}
        pred = _predicate(merged, params)
        params["k"] = int(top_k) * 4 if pred else int(top_k)
        cypher = (
            "CALL db.index.vector.queryNodes($index, $k, $vec) YIELD node, score "
            + (f"WHERE {pred} " if pred else "")
            + "RETURN node.knowledge_id AS id, node.text AS document, score, "
            + ", ".join(f"node.{field} AS {field}" for field in _HIT_FIELDS)
            + " ORDER BY score DESC LIMIT $limit"
        )
        params["limit"] = int(top_k)
        try:
            with self._client._driver.session() as s:
                records = list(s.run(cypher, **params))
        except Exception as exc:  # noqa: BLE001 — the caller names the leg failure
            raise Neo4jVectorStoreError(f"vector search failed: {exc}") from exc
        return [
            {
                "id": str(rec["id"] or ""),
                "document": str(rec["document"] or ""),
                "metadata": {
                    field: (rec[field] if rec[field] is not None else "") for field in _HIT_FIELDS
                },
                "distance": 1.0 - float(rec["score"] or 0.0),
            }
            for rec in records
        ]

    def count(self) -> int:
        with self._client._driver.session() as s:
            row = s.run(
                "MATCH (k:Knowledge) WHERE k." + EMBEDDING_PROP + " IS NOT NULL "
                "RETURN count(k) AS n"
            ).single()
        return int(row["n"]) if row else 0

    def inventory(self) -> dict[str, Any]:
        with self._client._driver.session() as s:
            ids = [
                str(rec["id"])
                for rec in s.run(
                    "MATCH (k:Knowledge) WHERE k." + EMBEDDING_PROP + " IS NOT NULL "
                    "RETURN k.knowledge_id AS id"
                )
            ]
        return {"count": len(ids), "ids": ids, "checkpoint": _checkpoint(ids)}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def backfill(
    *, limit: int = 0, batch: int = 16, source_type: str = "", log: Any = print
) -> dict[str, int]:
    """Embed Knowledge nodes that lack an embedding — bounded, resumable, idempotent.

    The forward projection (the kb-chroma-v1 consumer's handler, re-pointed at this store)
    keeps new records current; this pass repairs the backlog from the canonical nodes.
    """
    store = Neo4jVectorStore()
    embedded = 0
    skipped = 0
    where = "WHERE k." + EMBEDDING_PROP + " IS NULL AND k.text IS NOT NULL AND k.text <> ''"
    params: dict[str, Any] = {}
    if source_type:
        where += " AND k.source_type = $stype"
        params["stype"] = source_type
    with store._client._driver.session() as s:
        while True:
            if limit and embedded >= limit:
                break
            take = min(batch, limit - embedded) if limit else batch
            rows = list(
                s.run(
                    "MATCH (k:Knowledge) " + where + " RETURN k.knowledge_id AS id, k.text AS text "
                    "LIMIT $n",
                    n=take,
                    **params,
                )
            )
            if not rows:
                break
            ids = [str(r["id"]) for r in rows]
            texts = [str(r["text"]) for r in rows]
            try:
                store.upsert(ids, documents=texts)
                embedded += len(ids)
                log(f"[backfill] embedded {embedded} (batch {len(ids)}) at {_now()}")
            except Exception as exc:  # noqa: BLE001 — report and stop; the pass is resumable
                log(f"[backfill] batch failed after {embedded}: {exc}")
                skipped += len(ids)
                break
    return {"embedded": embedded, "skipped": skipped, "total": store.count()}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Neo4j vector store maintenance (dense leg)")
    ap.add_argument("--backfill", action="store_true", help="embed nodes lacking an embedding")
    ap.add_argument("--limit", type=int, default=0, help="cap this pass (0 = all)")
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--source-type", default="", help="restrict the pass to one source_type")
    ap.add_argument("--count", action="store_true", help="print the embedded-node count")
    ap.add_argument("--search", default="", help="run one semantic search and print the hits")
    args = ap.parse_args(argv)

    if args.backfill:
        result = backfill(limit=args.limit, batch=args.batch, source_type=args.source_type)
        print(
            f"backfill: embedded={result['embedded']} skipped={result['skipped']} "
            f"with_embedding={result['total']}"
        )
        return 0
    store = Neo4jVectorStore()
    if args.count:
        print(f"nodes with embedding: {store.count()}")
        return 0
    if args.search:
        for hit in store.search(args.search, top_k=5):
            print(
                f"{hit['distance']:.4f}  {hit['id'][:16]}  "
                f"{hit['metadata'].get('source_type')}  {hit['id']}"
            )
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
