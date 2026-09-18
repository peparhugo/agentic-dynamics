"""Text embedding and vector search via Ollama (bge-m3) + ChromaDB.

Provides embedding generation and semantic search over the experiment corpus.
Replaces the trigram heuristic in trajectory.py with real cosine distance.
"""

from __future__ import annotations

import hashlib
import math
import os
import threading
import time
from pathlib import Path
from typing import Any

# ── Endpoint configuration (mirrors live.py's FINOPS_REDIS_* pattern) ──
# The store is no longer hardcoded to localhost:8000 — which collides with
# ``apps/control_room/server.py`` — because CHROMA_HOST / CHROMA_PORT override it. The
# default values are read once at import (as in live.py), but ``ChromaStore.__init__``
# re-checks the environment so a test or a forked worker can still override them.
CHROMA_HOST = os.environ.get("CHROMA_HOST", "localhost")
# TWO distinct endpoints exist and neither implies the other (review fix P1):
#   * the HOST checkout reaches the PUBLISHED loopback port (127.0.0.1:8100 — the kb-chroma
#     unit and the reachability probe both declare it);
#   * the ladder's containers reach the service BY NAME on its INTERNAL port
#     (chromadb:8000) — ``x-ladder-env`` declares CHROMA_HOST=chromadb AND CHROMA_PORT=8000.
# The default below is the HOST endpoint. A non-loopback CHROMA_HOST WITHOUT an explicit port
# is a configuration error and ``resolve_chroma_endpoint`` refuses it rather than silently
# pairing the by-name host with the host's published port.
CHROMA_PORT = int(os.environ.get("CHROMA_PORT", "8100"))
#: The service's in-network port (what ``chromadb`` listens on inside the container). Named
#: here so the refusal message and the compose declaration share one documented value.
CHROMA_CONTAINER_PORT = 8000

# Bounded-operation defaults (delivery-simplification Units 4-5): chromadb's HTTP session is
# constructed ``timeout=None`` with no settings hook, and ollama's default client also waits
# forever — so every layer we own declares its own deadline. Env-overridable.
EMBED_TIMEOUT_ENV = "FINOPS_EMBED_TIMEOUT_S"
DEFAULT_EMBED_TIMEOUT_S = 15.0
CHROMA_TIMEOUT_ENV = "FINOPS_CHROMA_TIMEOUT_S"
DEFAULT_CHROMA_TIMEOUT_S = 10.0


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

    def __init__(
        self,
        model: str = "bge-m3:latest",
        host: str | None = None,
        *,
        timeout_s: float | None = None,
    ):
        import ollama

        self.model = model
        self.timeout_s = (
            float(timeout_s)
            if timeout_s is not None
            else float(os.environ.get(EMBED_TIMEOUT_ENV, DEFAULT_EMBED_TIMEOUT_S))
        )
        # A dedicated client with an explicit deadline — the module-level default client
        # inherits ollama's own ``timeout=None`` (wait forever), which is how a stalled
        # embedding provider used to block retrieval and the chroma projector indefinitely.
        self._client = ollama.Client(
            host=host or os.environ.get("OLLAMA_HOST") or "http://127.0.0.1:11434",
            timeout=self.timeout_s,
        )

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
        dot = sum(x * y for x, y in zip(a, b, strict=False))
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


def resolve_chroma_endpoint(
    host: str | None = None, port: int | None = None
) -> tuple[str, int]:
    """Resolve the chroma endpoint for THIS environment — explicitly, never by implication.

    Precedence: explicit arguments > environment (``CHROMA_HOST``/``CHROMA_PORT``) > the host
    defaults (``localhost:8100``). A non-loopback ``CHROMA_HOST`` REQUIRES an explicit port:
    the service answers on its internal port inside the ladder network while the host
    publishes a different one, so defaulting the port for a named host silently targets the
    wrong endpoint (review finding P1). One resolver — the store and its tests share it.
    """
    resolved_host = (
        str(host) if host is not None else os.environ.get("CHROMA_HOST", CHROMA_HOST)
    )
    if port is not None:
        return resolved_host, int(port)
    env_port = os.environ.get("CHROMA_PORT")
    if env_port:
        return resolved_host, int(env_port)
    if resolved_host not in ("localhost", "127.0.0.1", "::1"):
        raise ChromaStoreError(
            f"CHROMA_HOST={resolved_host!r} names a service endpoint but no CHROMA_PORT is "
            f"declared: the by-name container port is {CHROMA_CONTAINER_PORT} while the "
            f"host's published port is {CHROMA_PORT} — declare CHROMA_PORT explicitly "
            "(see x-ladder-env)"
        )
    return resolved_host, CHROMA_PORT


def _probe_chroma(host: str, port: int, timeout_s: float) -> None:
    """Bounded readiness gate before the chromadb client constructor performs any I/O.

    chromadb's FastAPI transport builds ``httpx.Client(timeout=None, ...)`` and its
    constructor performs network calls (server version, identity, tenant/database) over it —
    so an unresponsive server blocks construction forever. This gate probes, with our bounded
    client, BOTH the liveness contract (heartbeat, must be 2xx) AND the exact endpoints the
    constructor will hit (must merely ANSWER — any HTTP status proves the endpoint is not
    stalled). Review repro that this closes: heartbeat 200 + identity stall used to block
    construction past the declared timeout.
    """
    import httpx

    base = f"http://{host}:{port}"
    last = ""
    for path in ("/api/v2/heartbeat", "/api/v1/heartbeat"):
        try:
            response = httpx.get(f"{base}{path}", timeout=timeout_s)
        except Exception as exc:  # noqa: BLE001 — the probe reports, never raises
            last = f"{path}: {type(exc).__name__}: {exc}"
            continue
        if response.status_code == 200:
            break
        last = f"{path}: HTTP {response.status_code}"
    else:
        raise ChromaStoreError(
            f"chroma server not answerable at {base} within {timeout_s:g}s ({last})"
        )
    for path in (
        "/api/v2/version",
        "/api/v2/auth/identity",
        "/api/v2/tenants/default_tenant/databases/default_database",
    ):
        try:
            httpx.get(f"{base}{path}", timeout=timeout_s)
        except Exception as exc:
            raise ChromaStoreError(
                f"chroma construction endpoint not answering at {base}{path} within "
                f"{timeout_s:g}s ({type(exc).__name__}: {exc})"
            ) from exc


#: How long an endpoint stays refused after a construction that failed to complete within its
#: deadline. Bounds outstanding construction work across repeated outages (review finding P2).
CHROMA_CONSTRUCTION_COOLDOWN_S = 60.0
_CHROMA_CONSTRUCTION_LOCK = threading.Lock()
_CHROMA_CONSTRUCTION_REFUSED_UNTIL: dict[tuple[str, int], float] = {}


def _construct_chroma_bounded(host: str, port: int, timeout_s: float) -> Any:
    """Construct the chromadb client under a hard deadline, with a failure cooldown.

    The constructor performs network I/O in a session it creates ``timeout=None``; the
    preflight probes the same endpoints, but construction itself must still be bounded so a
    server that stalls mid-construction cannot block the caller (review finding P1). The wait
    runs on a DAEMON thread: on timeout the caller raises, a short cooldown suppresses
    repeated attempts against the same endpoint, and an abandoned constructor can never block
    process shutdown. The client is returned only after the constructor completed.
    """
    import chromadb

    key = (str(host), int(port))
    with _CHROMA_CONSTRUCTION_LOCK:
        until = _CHROMA_CONSTRUCTION_REFUSED_UNTIL.get(key, 0.0)
    now = time.monotonic()
    if now < until:
        raise ChromaStoreError(
            f"chromadb client construction suppressed for {until - now:.0f}s more "
            f"(a recent attempt at {host}:{port} did not complete within {timeout_s:g}s)"
        )
    result: dict[str, Any] = {}
    done = threading.Event()

    def _construct() -> None:
        try:
            result["client"] = chromadb.HttpClient(host=str(host), port=int(port))
        except BaseException as exc:  # noqa: BLE001 — delivered to the caller below
            result["error"] = exc
        finally:
            done.set()

    threading.Thread(target=_construct, name="chroma-construct", daemon=True).start()
    if not done.wait(timeout_s):
        with _CHROMA_CONSTRUCTION_LOCK:
            _CHROMA_CONSTRUCTION_REFUSED_UNTIL[key] = (
                time.monotonic() + CHROMA_CONSTRUCTION_COOLDOWN_S
            )
        raise ChromaStoreError(
            f"chromadb client construction exceeded {timeout_s:g}s at {host}:{port} "
            "(the server stalled during identity/tenant validation)"
        )
    if "error" in result:
        raise ChromaStoreError(
            f"chromadb client construction failed at {host}:{port}: {result['error']!r}"
        )
    return result["client"]


def _bound_chroma_session(client: Any, timeout_s: float) -> bool:
    """Apply the declared deadline to chromadb's shared HTTP session.

    chromadb 1.x exposes no settings hook for the session timeout (it is constructed
    ``timeout=None``); this is a version-tolerant private-attribute poke. Returns False
    when the session cannot be reached — the construction pre-flight is then the only
    bound, so a caller that needs a hard guarantee should keep its own deadline too.
    """
    session = getattr(getattr(client, "_server", None), "_session", None)
    if session is None:
        return False
    try:
        import httpx

        session.timeout = httpx.Timeout(timeout_s)
        return True
    except Exception:  # noqa: BLE001 — an unbounded library session is reported, not fatal
        return False


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
        *,
        timeout_s: float | None = None,
    ):
        # One resolver for both environments (review fix P1): explicit args > env > host
        # defaults, with a LOUD refusal when a named host carries no port.
        resolved_host, resolved_port = resolve_chroma_endpoint(host, port)
        self.host = resolved_host
        self.port = resolved_port
        self.timeout_s = (
            float(timeout_s)
            if timeout_s is not None
            else float(os.environ.get(CHROMA_TIMEOUT_ENV, DEFAULT_CHROMA_TIMEOUT_S))
        )
        # Bounded construction, in order (review fix P1): the readiness gate probes the
        # constructor's own endpoints with our deadline, then construction itself runs under
        # a hard deadline, and only then is the shared session's timeout applied for every
        # subsequent request.
        _probe_chroma(resolved_host, resolved_port, self.timeout_s)
        self._client = _construct_chroma_bounded(resolved_host, resolved_port, self.timeout_s)
        self.session_bounded = _bound_chroma_session(self._client, self.timeout_s)
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
