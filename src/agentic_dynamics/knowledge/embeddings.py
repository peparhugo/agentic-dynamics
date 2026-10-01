"""Text embedding and vector search via Ollama (bge-m3) + ChromaDB.

Provides embedding generation and semantic search over the experiment corpus.
Replaces the trigram heuristic in trajectory.py with real cosine distance.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
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

# ── Embedder transport (cell-viability: base deps only) ──
# The embedder talks to an Ollama-compatible REST service. The DEFAULT transport is the
# standard library (``urllib.request``), so a cell with base deps only can CONSTRUCT the
# client — there is no import-time optional dependency. The ``ollama`` package is an
# OPTIONAL transport, selected explicitly via ``transport="ollama"`` (or the env override);
# it is imported only when that transport is actually used. A missing optional package is
# a NAMED, TYPED failure (:class:`EmbedderModuleAbsent`), DISTINCT from an unreachable
# endpoint and from a clean-empty result.
OLLAMA_HOST_ENV = "OLLAMA_HOST"
DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"
#: The only schemes an Ollama REST endpoint may declare. Anything else is a CONFIGURATION
#: fault (a typed :class:`EmbedderConfigurationError`), never misreported as unreachable.
SUPPORTED_OLLAMA_SCHEMES = ("http", "https")
EMBED_TRANSPORT_ENV = "FINOPS_EMBED_TRANSPORT"
#: The stdlib transport: ``POST {host}/api/embeddings`` ``{model, prompt}`` -> ``{embedding}``.
TRANSPORT_HTTP = "http"
#: The optional transport backed by the ``ollama`` package (imported only when selected).
TRANSPORT_OLLAMA = "ollama"
EMBED_TRANSPORTS = (TRANSPORT_HTTP, TRANSPORT_OLLAMA)


def step_doc_id(session_id: str, step_index: int) -> str:
    """Return the canonical Chroma document id for one reasoning step.

    Single source of truth for the step-document id scheme. Both
    ``ChromaStore.index_session_steps`` (dense index) and
    ``graph.Neo4jClient.build_step_graph`` (graph index) must use it so the
    Chroma ``doc_id`` and the Neo4j ``Step.doc_id`` agree — that shared value is
    the cross-store join between the two indexes.
    """
    return f"{session_id}_step_{step_index:04d}"


class EmbedderError(RuntimeError):
    """Base class for every typed embedder failure.

    Every embedder failure carries a stable ``token`` so the retrieval seam can record a
    NAMED diagnostic instead of a raw traceback — the three states the spec requires
    (module absent, endpoint unreachable, clean empty) must stay DISTINCT.
    """

    #: Stable machine-readable token for the failure class (see the subclasses).
    token = "embedder-error"


class EmbedderUnreachable(EmbedderError):  # noqa: N818 — the spec pins this exact name
    """The embedding endpoint could not be reached (refused, timed out, DNS, transport).

    This is the transport-failure state: the service is configured but no live endpoint
    answered. It is deliberately distinct from :class:`EmbedderModuleAbsent` (the
    explicitly-selected optional package is not installed) and from a clean empty pass
    (an endpoint answered and returned nothing to embed).
    """

    token = "embedder-unreachable"


class EmbedderResponseError(EmbedderError):
    """The endpoint answered but the payload was not a usable embedding vector."""

    token = "embedder-response-error"


class EmbedderModuleAbsent(EmbedderError):  # noqa: N818 — mirrors EmbedderUnreachable's family
    """The explicitly-selected optional transport's package is not installed.

    A cell-provisioning gap, not a network outage: the stdlib HTTP transport is the
    default precisely so this state can never arise on the base-deps path.
    """

    token = "embedder-module-absent"


class EmbedderConfigurationError(EmbedderError):
    """The embedder endpoint is MISCONFIGURED (e.g. an unsupported URL scheme).

    A configuration fault is neither a missing package nor an unreachable endpoint: folding
    a bad ``OLLAMA_HOST`` form into :class:`EmbedderUnreachable` would tell an operator the
    network is down when the truth is the value they set is wrong (the R3 repair). The
    distinct token is what lets the retrieval seam name the real state.
    """

    token = "embedder-config-error"


def normalize_ollama_host(value: str) -> str:
    """Normalize an ``OLLAMA_HOST`` value to a scheme-qualified base URL.

    ``OLLAMA_HOST`` is conventionally set like ``host:port`` (the Ollama CLI accepts
    ``127.0.0.1:11434``, ``ollama:11434``) with no scheme. A scheme-less form is assumed
    ``http`` — but ONLY when the value is not already a ``scheme://`` URL, and an UNSUPPORTED
    declared scheme (:data:`SUPPORTED_OLLAMA_SCHEMES`) is refused with a typed
    :class:`EmbedderConfigurationError` rather than being handed onward as an unreachable
    endpoint. A trailing slash is stripped so ``{host}/api/embeddings`` never doubles it.

    Handled forms::

        "host:port"        -> "http://host:port"
        "host"             -> "http://host"
        "[::1]:port"       -> "http://[::1]:port"
        "http://host:port/"-> "http://host:port"
        "https://host"     -> "https://host"      (preserved)

    Uses only :mod:`urllib.parse` (no new dependency).
    """
    text = value.strip()
    if not text:
        return DEFAULT_OLLAMA_HOST
    if "://" in text:
        parts = urllib.parse.urlsplit(text)
        scheme = parts.scheme.lower()
        if scheme not in SUPPORTED_OLLAMA_SCHEMES:
            raise EmbedderConfigurationError(
                f"unsupported OLLAMA_HOST scheme {parts.scheme!r} in {value!r}: "
                f"expected one of {SUPPORTED_OLLAMA_SCHEMES}"
            )
        # urlunsplit drops a bare "/" path, so the base URL comes back without a trailing
        # slash; rstrip defends against a doubled one.
        normalized = urllib.parse.urlunsplit((scheme, parts.netloc, parts.path.rstrip("/"), "", ""))
        return normalized.rstrip("/")
    # Scheme-less: the conventional Ollama form. Assume http, never httpS (the CLI default).
    return f"http://{text.rstrip('/')}"


def resolve_ollama_host(host: str | None = None) -> str:
    """Resolve the Ollama endpoint: explicit argument > ``OLLAMA_HOST`` > localhost default.

    The chosen value is normalized by :func:`normalize_ollama_host` (scheme added where the
    conventional ``host:port`` form omits it, an unsupported declared scheme refused with a
    typed configuration error, a trailing slash stripped). The env is read at call time
    (not import time) so a cell, test, or forked worker can override it.
    """
    value = host or os.environ.get(OLLAMA_HOST_ENV) or DEFAULT_OLLAMA_HOST
    return normalize_ollama_host(str(value))


def resolve_embed_transport(transport: str | None = None) -> str:
    """Resolve the embed transport: explicit argument > ``FINOPS_EMBED_TRANSPORT`` > stdlib HTTP.

    An unknown value is a LOUD refusal (never a silent fallback): a typo'd transport must not
    quietly disable the embedder.
    """
    value = transport or os.environ.get(EMBED_TRANSPORT_ENV) or TRANSPORT_HTTP
    normalized = str(value).strip().lower()
    if normalized not in EMBED_TRANSPORTS:
        raise ValueError(f"unknown embed transport {value!r}: expected one of {EMBED_TRANSPORTS}")
    return normalized


def _parse_embedding(body: Any, host: str) -> list[float]:
    """Validate an Ollama embeddings payload and return its float vector.

    Both the stdlib transport (a JSON dict) and the optional ``ollama`` transport (an
    object with an ``embedding`` attribute) funnel through here so the response contract is
    defined once. A malformed or empty payload is a named :class:`EmbedderResponseError`,
    never a silent empty vector.
    """
    embedding = (
        body.get("embedding") if isinstance(body, dict) else getattr(body, "embedding", None)
    )
    if not isinstance(embedding, list) or not embedding:
        raise EmbedderResponseError(f"embedding endpoint {host} returned no 'embedding' vector")
    try:
        return [float(x) for x in embedding]
    except (TypeError, ValueError) as exc:
        raise EmbedderResponseError(
            f"embedding endpoint {host} returned a non-numeric vector: {exc}"
        ) from exc


class EmbeddingClient:
    """Generate text embeddings via an Ollama-compatible REST service.

    CELL-VIABLE by construction: the DEFAULT transport is the standard library
    (``urllib.request``) against ``POST {OLLAMA_HOST}/api/embeddings``, so importing this
    module and constructing the client never requires an optional package. The ``ollama``
    package remains available as an OPTIONAL transport, selected explicitly with
    ``transport="ollama"``; only that path touches the package, and if it is missing the
    failure is the typed :class:`EmbedderModuleAbsent`.

    A transport failure at ``embed()`` time raises the typed
    :class:`EmbedderUnreachable` (endpoint refused/timed out), so the retrieval seam can
    record a NAMED ``embedder-unreachable`` diagnostic rather than a module traceback.
    """

    def __init__(
        self,
        model: str = "bge-m3:latest",
        host: str | None = None,
        *,
        timeout_s: float | None = None,
        transport: str | None = None,
    ):
        self.model = model
        self.timeout_s = (
            float(timeout_s)
            if timeout_s is not None
            else float(os.environ.get(EMBED_TIMEOUT_ENV, DEFAULT_EMBED_TIMEOUT_S))
        )
        # Endpoint + transport are resolved ONCE here (env is read at construction, like
        # live.py's FINOPS_REDIS_* pattern); construction performs NO I/O, so it can never
        # hang or fail on a missing endpoint.
        self.host = resolve_ollama_host(host)
        self.transport = resolve_embed_transport(transport)
        # The optional ollama client is built LAZILY on first use of the ollama transport —
        # the default (stdlib HTTP) path never imports the package at all.
        self._ollama_client: Any = None

    # ── transports ──────────────────────────────────────────────────────────────

    def _http_embed(self, text: str) -> list[float]:
        """Embed via the stdlib HTTP transport against the Ollama REST API.

        This is the default, dependency-free path: ``POST {host}/api/embeddings`` with
        ``{"model": ..., "prompt": ...}`` returning ``{"embedding": [...]}``. The declared
        ``timeout_s`` bounds ``urlopen``; a refused/timed-out/unreachable endpoint becomes
        the typed :class:`EmbedderUnreachable`, and a malformed payload becomes the typed
        :class:`EmbedderResponseError`. No exception is swallowed into an empty vector.
        """
        payload = json.dumps({"model": self.model, "prompt": text}).encode("utf-8")
        request = urllib.request.Request(
            f"{self.host}/api/embeddings",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            # The endpoint answered but rejected the request — a response failure, not a
            # transport outage. HTTPError subclasses URLError, so it MUST be caught first.
            raise EmbedderResponseError(
                f"embedding endpoint {self.host} answered HTTP {exc.code}"
            ) from exc
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            # URLError wraps ConnectionRefusedError/DNS failures; OSError/TimeoutError cover
            # a bare socket timeout. All are the SAME named state: the endpoint is unreachable.
            raise EmbedderUnreachable(
                f"embedding endpoint {self.host} unreachable: {type(exc).__name__}: {exc}"
            ) from exc
        try:
            body = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise EmbedderResponseError(
                f"embedding endpoint {self.host} returned a non-JSON payload: {exc}"
            ) from exc
        return _parse_embedding(body, self.host)

    def _ensure_ollama_client(self) -> Any:
        """Build (once) the optional ``ollama`` client, or raise the typed module-absent error.

        The import lives HERE — never at module import and never on the default path — so
        the optional dependency is genuinely optional.
        """
        try:
            import ollama
        except ImportError as exc:
            raise EmbedderModuleAbsent(
                "embed transport 'ollama' requires the optional 'ollama' package, which is "
                f"not installed: {exc}"
            ) from exc
        if self._ollama_client is None:
            self._ollama_client = ollama.Client(host=self.host, timeout=self.timeout_s)
        return self._ollama_client

    def _ollama_embed(self, text: str) -> list[float]:
        """Embed via the OPTIONAL ``ollama`` package transport (explicitly selected only)."""
        client = self._ensure_ollama_client()
        try:
            result = client.embeddings(model=self.model, prompt=text)
        except EmbedderError:
            raise
        except Exception as exc:  # noqa: BLE001 — transport failures are typed below
            raise EmbedderUnreachable(
                f"ollama transport to {self.host} failed: {type(exc).__name__}: {exc}"
            ) from exc
        return _parse_embedding(result, self.host)

    def embed(self, text: str) -> list[float]:
        """Embed one text; raises a TYPED :class:`EmbedderError` on any failure."""
        if self.transport == TRANSPORT_OLLAMA:
            return self._ollama_embed(text)
        return self._http_embed(text)

    def embed_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
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
        self,
        baseline_texts: list[str],
        perturbed_texts: list[str],
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


def resolve_chroma_endpoint(host: str | None = None, port: int | None = None) -> tuple[str, int]:
    """Resolve the chroma endpoint for THIS environment — explicitly, never by implication.

    Precedence: explicit arguments > environment (``CHROMA_HOST``/``CHROMA_PORT``) > the host
    defaults (``localhost:8100``). A non-loopback ``CHROMA_HOST`` REQUIRES an explicit port:
    the service answers on its internal port inside the ladder network while the host
    publishes a different one, so defaulting the port for a named host silently targets the
    wrong endpoint (review finding P1). One resolver — the store and its tests share it.
    """
    resolved_host = str(host) if host is not None else os.environ.get("CHROMA_HOST", CHROMA_HOST)
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


def _bounded_get(url: str, deadline: float) -> int:
    """One GET whose TOTAL elapsed time is bounded by the absolute ``deadline``.

    httpx's timeout bounds INACTIVITY, not elapsed time: a server dribbling one byte at a
    time can extend a request indefinitely, and a fresh timeout per probe multiplies the
    overrun (review finding P1). Here the client timeout is the REMAINING time (so no single
    blocking read can exceed the deadline) AND the streamed body is checked against the
    deadline per chunk (so a slow stream is cut at the deadline too). Raises
    :class:`ChromaStoreError` on deadline exhaustion or transport failure; returns the HTTP
    status otherwise.
    """
    import httpx

    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ChromaStoreError(f"chroma init deadline exhausted before GET {url}")
    try:
        with (
            httpx.Client(timeout=httpx.Timeout(max(0.001, remaining))) as client,
            client.stream("GET", url) as response,
        ):
            status = response.status_code
            for _chunk in response.iter_bytes():
                if time.monotonic() > deadline:
                    raise ChromaStoreError(f"GET {url} exceeded the chroma initialization deadline")
            return status
    except ChromaStoreError:
        raise
    except Exception as exc:
        raise ChromaStoreError(
            f"GET {url} failed within the chroma init deadline: {type(exc).__name__}: {exc}"
        ) from exc


def _probe_chroma(host: str, port: int, deadline: float) -> None:
    """Readiness gate sharing ONE absolute deadline with construction.

    chromadb's FastAPI transport builds ``httpx.Client(timeout=None, ...)`` and its
    constructor performs network calls (server version, identity, tenant/database) over it —
    an unresponsive server would block construction forever. This gate probes the liveness
    contract (heartbeat, must be 2xx) and the exact endpoints the constructor will hit (must
    merely answer), with every request cut at ``deadline`` — no probe receives fresh time
    (review finding P1).
    """
    base = f"http://{host}:{port}"
    last = ""
    for path in ("/api/v2/heartbeat", "/api/v1/heartbeat"):
        try:
            status = _bounded_get(f"{base}{path}", deadline)
        except ChromaStoreError as exc:
            last = str(exc)
            continue
        if status == 200:
            break
        last = f"{path}: HTTP {status}"
    else:
        raise ChromaStoreError(
            f"chroma server not answerable at {base} within the initialization deadline ({last})"
        )
    for path in (
        "/api/v2/version",
        "/api/v2/auth/identity",
        "/api/v2/tenants/default_tenant/databases/default_database",
    ):
        _bounded_get(f"{base}{path}", deadline)


#: How long an endpoint stays refused after an initialization that FAILED TO COMPLETE within
#: its deadline. Combined with the atomic capacity reservation below, this keeps repeated
#: outages from piling up attempts (review finding P2).
CHROMA_CONSTRUCTION_COOLDOWN_S = 60.0
#: Bounded capacity for chromadb initialization in this process. A reservation is taken
#: ATOMICALLY before a worker starts and released only when the operation actually ends, so
#: concurrent callers cannot stack constructors against a stalled endpoint.
CHROMA_INIT_SLOTS = 2
_CHROMA_INIT_CAPACITY = threading.BoundedSemaphore(CHROMA_INIT_SLOTS)
_CHROMA_CONSTRUCTION_LOCK = threading.Lock()
_CHROMA_CONSTRUCTION_REFUSED_UNTIL: dict[tuple[str, int], float] = {}


def _initialize_chroma(host: str, port: int, timeout_s: float) -> Any:
    """Construct the chromadb client under ONE absolute deadline and a bounded reservation.

    The whole initialization — readiness probes AND the constructor's own identity/tenant
    calls — runs inside a single daemon worker awaited ONCE against ``timeout_s``; the
    deadline starts before the first probe, so no phase can borrow fresh time (review finding
    P1). The capacity reservation is acquired atomically BEFORE the worker starts and
    released only when the operation actually ends — a timed-out caller cannot free capacity
    that a still-stuck constructor holds, so concurrent and retried calls cannot accumulate
    constructors (review finding P2). A completed-but-failed initialization releases its slot
    immediately; only deadline overruns set the cooldown.
    """
    import chromadb

    key = (str(host), int(port))
    with _CHROMA_CONSTRUCTION_LOCK:
        until = _CHROMA_CONSTRUCTION_REFUSED_UNTIL.get(key, 0.0)
    now = time.monotonic()
    if now < until:
        raise ChromaStoreError(
            f"chromadb initialization suppressed for {until - now:.0f}s more "
            f"(a recent attempt at {host}:{port} did not complete within its deadline)"
        )
    if not _CHROMA_INIT_CAPACITY.acquire(blocking=False):
        raise ChromaStoreError(
            f"chromadb initialization refused: {CHROMA_INIT_SLOTS} initializations are in "
            "flight (a stalled endpoint holds this process's capacity)"
        )
    # Capture the reservation OBJECT: the worker must release exactly the capacity its
    # reservation was taken from, even if the module attribute is later replaced (tests).
    capacity = _CHROMA_INIT_CAPACITY
    deadline = time.monotonic() + timeout_s
    result: dict[str, Any] = {}
    done = threading.Event()

    def _worker() -> None:
        try:
            _probe_chroma(str(host), int(port), deadline)
            result["client"] = chromadb.HttpClient(host=str(host), port=int(port))
        except BaseException as exc:  # noqa: BLE001 — delivered to the caller below
            result["error"] = exc
        finally:
            done.set()
            capacity.release()  # held until the operation ACTUALLY ends

    try:
        threading.Thread(target=_worker, name="chroma-init", daemon=True).start()
    except BaseException:
        capacity.release()
        raise
    if not done.wait(timeout_s):
        with _CHROMA_CONSTRUCTION_LOCK:
            _CHROMA_CONSTRUCTION_REFUSED_UNTIL[key] = (
                time.monotonic() + CHROMA_CONSTRUCTION_COOLDOWN_S
            )
        raise ChromaStoreError(
            f"chromadb initialization exceeded {timeout_s:g}s at {host}:{port} "
            "(the server stalled during the readiness probe or identity/tenant validation)"
        )
    error = result.get("error")
    if error is not None:
        if isinstance(error, ChromaStoreError):
            raise error
        raise ChromaStoreError(f"chromadb initialization failed at {host}:{port}: {error!r}")
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
        # Bounded initialization, in order (review findings P1/P2): ONE absolute deadline
        # covers the readiness probes AND the constructor's own I/O, inside a single daemon
        # worker under an atomic capacity reservation; only then is the shared session's
        # timeout applied for every subsequent request.
        self._client = _initialize_chroma(resolved_host, resolved_port, self.timeout_s)
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
            metas.append(
                {
                    **meta,
                    "embedding_source": "reasoning_step",
                    "step_index": step_idx,
                    "tool_after": step.get("tool_after", ""),
                    "tool_input_summary": step.get("tool_input_summary", "")[:200],
                }
            )

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
                hits.append(
                    {
                        "id": doc_id,
                        "document": results["documents"][0][i] if results["documents"] else "",
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "distance": results["distances"][0][i] if results["distances"] else 0.0,
                    }
                )
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
                    steps.append(
                        {
                            "text": text,
                            "step_index": step_idx,
                            "tool_after": last_tool,
                            "tool_input_summary": last_tool_input,
                        }
                    )
                    step_idx += 1
                    last_tool = ""
                    last_tool_input = ""

            elif event.get("type") == "text":
                if not first_text_skipped:
                    first_text_skipped = True
                    continue
                text = event.get("text", "").strip()
                if text and len(text) > 20:
                    steps.append(
                        {
                            "text": text,
                            "step_index": step_idx,
                            "tool_after": last_tool,
                            "tool_input_summary": last_tool_input,
                        }
                    )
                    step_idx += 1
                    last_tool = ""
                    last_tool_input = ""

            elif event.get("type") == "tool":
                last_tool = event.get("tool", "")
                inp = event.get("state", {}).get("input", {})
                if isinstance(inp, dict):
                    content = (
                        inp.get("content", "") or inp.get("command", "") or inp.get("pattern", "")
                    )
                    last_tool_input = str(content)[:200]

    return steps
