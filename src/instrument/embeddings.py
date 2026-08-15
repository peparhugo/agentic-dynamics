"""Text embedding and vector search via Ollama (bge-m3) + ChromaDB.

Provides embedding generation and semantic search over the experiment corpus.
Replaces the trigram heuristic in trajectory.py with real cosine distance.
"""

from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
from typing import Any

import ollama

# ── Endpoint configuration (mirrors live.py's FINOPS_REDIS_* pattern) ──
# The store is no longer hardcoded to localhost:8000 — which collides with
# ``admin/server.py`` — because CHROMA_HOST / CHROMA_PORT override it. The
# default values are read once at import (as in live.py), but ``ChromaStore.__init__``
# re-checks the environment so a test or a forked worker can still override them.
CHROMA_HOST = os.environ.get("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.environ.get("CHROMA_PORT", "8000"))


def step_doc_id(session_id: str, step_index: int) -> str:
    """Return the canonical Chroma document id for one reasoning step.

    Single source of truth for the step-document id scheme. Both
    ``ChromaStore.index_session_steps`` (dense index) and
    ``graph.Neo4jClient.build_step_graph`` (graph index) must use it so the
    Chroma ``doc_id`` and the Neo4j ``Step.doc_id`` agree — that shared value is
    the cross-store join between the two indexes.
    """
    return f"{session_id}_step_{step_index:04d}"


class EmbeddingClient:
    """Generate text embeddings via local Ollama model."""

    def __init__(self, model: str = "bge-m3:latest", host: str | None = None):
        self.model = model
        self._client = ollama.Client(host=host) if host else ollama

    def embed(self, text: str) -> list[float]:
        r = self._client.embeddings(model=self.model, prompt=text)
        return r.embedding

    def embed_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            for t in batch:
                embeddings.append(self.embed(t))
        return embeddings

    def cosine_distance(self, a: list[float], b: list[float]) -> float:
        if not a or not b:
            return 1.0
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x * x for x in a))
        mag_b = math.sqrt(sum(y * y for y in b))
        if mag_a == 0 or mag_b == 0:
            return 1.0
        cos_sim = dot / (mag_a * mag_b)
        return (1.0 - cos_sim) / 2.0

    def embedding_distance(
        self, baseline_texts: list[str], perturbed_texts: list[str],
    ) -> float:
        n = min(len(baseline_texts), len(perturbed_texts))
        if n == 0:
            return 0.0
        all_texts = []
        for i in range(n):
            if baseline_texts[i].strip():
                all_texts.append(baseline_texts[i])
            if perturbed_texts[i].strip():
                all_texts.append(perturbed_texts[i])
        if not all_texts:
            return 0.0

        embeds = self.embed_batch(all_texts)
        per_step_dists: list[float] = []
        ei = 0
        for i in range(n):
            if not baseline_texts[i].strip() or not perturbed_texts[i].strip():
                continue
            be = embeds[ei] if ei < len(embeds) else None
            pe = embeds[ei + 1] if (ei + 1) < len(embeds) else None
            ei += 2
            if be and pe:
                per_step_dists.append(self.cosine_distance(be, pe))
        if not per_step_dists:
            return 0.0
        return sum(per_step_dists) / len(per_step_dists)


class ChromaStoreError(RuntimeError):
    """Raised when a Chroma store operation fails.

    The canonical methods (``upsert`` / ``delete`` / ``search`` / ``inventory``)
    propagate this explicitly instead of swallowing failures and returning a
    partial count — an index outage must be visible, not silently masked.
    """


class ChromaStore:
    """Vector store for experiment session embeddings and knowledge chunks.

    ``collection_name`` names the logical collection; it defaults to
    ``session_embeddings`` (the existing contract) so historical callers are
    unchanged, while runtime-RAG instantiates a separate collection
    (``ChromaStore(collection_name="knowledge_chunks_v1")``) for isolation.
    """

    COLLECTION_NAME = "session_embeddings"

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        collection_name: str | None = None,
    ):
        import chromadb

        # Env-driven defaults (re-checked here, not only at import) so a caller or
        # test can override CHROMA_HOST/CHROMA_PORT without reloading the module.
        self._client = chromadb.HttpClient(
            host=host if host is not None else os.environ.get("CHROMA_HOST", CHROMA_HOST),
            port=port if port is not None else int(os.environ.get("CHROMA_PORT", str(CHROMA_PORT))),
        )
        self._embedder = EmbeddingClient()
        # Instance shadow of the class default: ``collection_name`` is the
        # per-instance override while ``COLLECTION_NAME`` stays the documented
        # default. This preserves the historical ``store.COLLECTION_NAME = "x"``
        # mutation used by existing callers.
        self.COLLECTION_NAME = collection_name or self.COLLECTION_NAME
        self._collection = None

    @property
    def collection(self):
        if self._collection is None:
            self._collection = self._client.get_or_create_collection(
                self.COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def upsert(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
        embeddings: list[list[float]] | None = None,
    ) -> int:
        """Idempotently upsert documents keyed by their canonical ids.

        This is the storage-neutral primitive: ids are the canonical
        ``knowledge_id`` (or ``step_doc_id``) values that also key Neo4j nodes and
        Redis stream events. Embeddings are computed via the configured embedder
        when not supplied. Propagates ``ChromaStoreError`` on failure.
        """
        if not ids:
            return 0
        if embeddings is None:
            embeddings = [self._embedder.embed(doc) for doc in documents]
        if metadatas is None:
            metadatas = [{} for _ in ids]
        try:
            self.collection.upsert(
                ids=list(ids),
                documents=list(documents),
                metadatas=list(metadatas),
                embeddings=list(embeddings),
            )
        except Exception as exc:
            raise ChromaStoreError(f"upsert of {len(ids)} docs failed: {exc}") from exc
        return len(ids)

    def delete(self, ids: list[str]) -> None:
        """Delete documents by canonical id. Propagates ``ChromaStoreError``."""
        if not ids:
            return
        try:
            self.collection.delete(ids=list(ids))
        except Exception as exc:
            raise ChromaStoreError(f"delete of {len(ids)} ids failed: {exc}") from exc

    def index_session_steps(
        self,
        session_id: str,
        steps: list[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Index individual reasoning steps from a session.

        Each step gets its own embedding document with position metadata,
        enabling step-level comparison across sessions. Uses the canonical
        ``step_doc_id`` scheme so the dense index joins the graph index on the
        same id. Legacy-resilient: returns 0 (rather than raising) on a store
        failure so batch indexing of many sessions survives a transient outage —
        prefer the explicit ``upsert`` for canonical knowledge writes.
        """
        meta = metadata or {}
        docs: list[str] = []
        ids: list[str] = []
        metas: list[dict[str, Any]] = []

        for step in steps:
            text = step.get("text", "").strip()
            if not text or len(text) < 20:
                continue
            step_idx = step.get("step_index", 0)
            docs.append(text)
            ids.append(step_doc_id(session_id, step_idx))
            metas.append({
                **meta,
                "embedding_source": "reasoning_step",
                "step_index": step_idx,
                "tool_after": step.get("tool_after", ""),
                "tool_input_summary": step.get("tool_input_summary", "")[:200],
            })

        if not docs:
            return 0

        try:
            return self.upsert(ids, docs, metas)
        except ChromaStoreError:
            return 0

    def search(
        self,
        query: str,
        top_k: int = 10,
        filter_model: str | None = None,
        filter_strategy: str | None = None,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Semantic search over the collection, with optional metadata filters.

        ``filter_model`` / ``filter_strategy`` are conveniences merged into the
        raw Chroma ``where`` metadata filter, which is also accepted directly for
        arbitrary filter expressions (e.g. ``{"authority": "source"}``).
        Propagates store failures.
        """
        merged: dict[str, Any] = dict(where) if where else {}
        if filter_model:
            merged["model"] = filter_model
        if filter_strategy:
            merged["strategy"] = filter_strategy

        query_embed = self._embedder.embed(query)
        kwargs: dict[str, Any] = {
            "query_embeddings": [query_embed],
            "n_results": top_k,
        }
        if merged:
            kwargs["where"] = merged

        results = self.collection.query(**kwargs)

        hits: list[dict[str, Any]] = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                hits.append({
                    "id": doc_id,
                    "document": results["documents"][0][i] if results["documents"] else "",
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else 0.0,
                })
        return hits

    def inventory(self) -> dict[str, Any]:
        """Return the collection's id inventory plus a reconciliation checkpoint.

        The checkpoint is a sha256 over the sorted canonical ids, so any
        add/remove changes it — letting a reconciler detect drift between Chroma,
        Neo4j, and the change stream without a server-side cursor. Propagates
        ``ChromaStoreError`` on failure.
        """
        try:
            ids = sorted(self.collection.get(include=[])["ids"])
        except Exception as exc:
            raise ChromaStoreError(f"inventory read failed: {exc}") from exc
        checkpoint = hashlib.sha256("\x1f".join(ids).encode("utf-8")).hexdigest()
        return {"count": len(ids), "ids": ids, "checkpoint": checkpoint}

    def count(self) -> int:
        return self.collection.count()

    def delete_all(self) -> None:
        self._client.delete_collection(self.COLLECTION_NAME)
        self._collection = None


def extract_session_text(session_path: Path) -> tuple[str, str, dict[str, Any]]:
    """Extract reasoning text, tool outputs, and metadata from a session.jsonl file."""
    import json

    reasoning_parts: list[str] = []
    tool_outputs: list[str] = []
    total_cost = 0.0
    session_id = session_path.parent.name

    with open(session_path) as f:
        for line in f:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            if event.get("type") == "reasoning":
                text = event.get("text", "")
                if text.strip():
                    reasoning_parts.append(text)

            elif event.get("type") == "tool":
                output = event.get("state", {}).get("output", "")
                if output.strip():
                    tool_outputs.append(output)

            elif event.get("type") == "step-finish":
                total_cost += float(event.get("cost", 0))

    reasoning_text = "\n".join(reasoning_parts)
    tool_output_text = "\n".join(tool_outputs)

    metadata = {
        "session_id": session_id,
        "cost_usd": total_cost,
    }

    return reasoning_text, tool_output_text, metadata


def extract_session_steps(session_path: Path) -> list[dict[str, Any]]:
    """Extract individual reasoning steps from a session.jsonl file.

    Captures both 'reasoning' events (DeepSeek GRPO thinking) and 'text' events
    (Claude/GPT chain-of-thought). The first text event (prompt) is skipped.
    Each step represents one cognitive event during the model's trajectory.

    Returns a list of step dicts with: text, step_index, tool_after, tool_input_summary.
    """
    import json

    steps: list[dict[str, Any]] = []
    step_idx = 0
    last_tool = ""
    last_tool_input = ""
    first_text_skipped = False

    with open(session_path) as f:
        for line in f:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            if event.get("type") == "reasoning":
                text = event.get("text", "").strip()
                if text and len(text) > 20:
                    steps.append({
                        "text": text,
                        "step_index": step_idx,
                        "tool_after": last_tool,
                        "tool_input_summary": last_tool_input,
                    })
                    step_idx += 1
                    last_tool = ""
                    last_tool_input = ""

            elif event.get("type") == "text":
                if not first_text_skipped:
                    first_text_skipped = True
                    continue
                text = event.get("text", "").strip()
                if text and len(text) > 20:
                    steps.append({
                        "text": text,
                        "step_index": step_idx,
                        "tool_after": last_tool,
                        "tool_input_summary": last_tool_input,
                    })
                    step_idx += 1
                    last_tool = ""
                    last_tool_input = ""

            elif event.get("type") == "tool":
                last_tool = event.get("tool", "")
                inp = event.get("state", {}).get("input", {})
                if isinstance(inp, dict):
                    content = inp.get("content", "") or inp.get("command", "") or inp.get("pattern", "")
                    last_tool_input = str(content)[:200]

    return steps
