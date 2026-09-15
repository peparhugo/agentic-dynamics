"""Session capacity — the installed runtime's OWN usable-context calculation.

The AIO's context policy is CAPACITY-DERIVED, never a universal constant: the session is
judged against the usable context of its ACTIVE resolved model, using the same calculation
the installed opencode runtime itself uses to decide when to compact.

Sources of truth, in order:

1. **The runtime's own CLI resolution** (preferred): ``opencode models <provider> --verbose``
   emits the RESOLVED models with their limits, after opencode's full config load
   (global config dir → ``OPENCODE_CONFIG`` → project config, which is the runtime's own
   order). The helper consumes that output rather than re-deriving it; a model the runtime
   does not resolve falls back to (2).
2. **Catalog + config overlay** (documented fallback when the runtime CLI is unavailable,
   e.g. in a container without the binary): the installed catalog cache (``models.json``)
   overlaid with the ``provider.<id>.models.<model>.limit`` fields from the runtime config
   files, merged FILE-BY-FILE and FIELD-BY-FIELD in the runtime's order (global → explicit →
   project), with JSONC comments and trailing commas tolerated.

The formula and constants are a faithful port of opencode **1.18.15** (extracted 2026-09-15
from the installed binary's bundled source):

    OUTPUT_TOKEN_MAX = 32000                         # be.OUTPUT_TOKEN_MAX
    maxOutputTokens(model, outputTokenMax) = min(model.limit.output, outputTokenMax ?? 32000) || 32000
    COMPACTION_RESERVED_CAP = 20000                  # `zd`
    reserved = cfg.compaction.reserved ?? min(20000, maxOutputTokens(...))
    usable   = model.limit.input ? max(0, input - reserved)
                                 : max(0, context - maxOutputTokens(...))
    overflow = (tokens.total || input + output + cache.read + cache.write) >= usable

The token measure deliberately EXCLUDES ``reasoning`` in the missing-``total`` case — the
runtime's expression does; adding it over-counts (a reproduced 955K-native vs 975K-local
divergence) and would demand compaction the runtime will not trigger.

The operator override ``FINOPS_SESSION_CTX_LIMIT`` is a LOCAL POLICY cap, not a native
trigger: it is clamped to the native usable limit (it can only move the boundary EARLIER),
it never claims that compaction will engage, and crossing it is a policy close — native
compaction still starts at its own threshold. (Returning ``COMPACT`` would not initiate
compaction; only the runtime does that, at its native boundary.)

An unresolvable model or missing metadata is ``UNJUDGED`` (never a fabricated capacity,
never ``OK``). The post-compaction boundary is handled by the budget check
(``scripts/session_budget.py``): the runtime skips its overflow check when the last assistant
message is a compaction summary, and so does the check.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

#: The formula's provenance — re-derive the three constants when this changes.
FORMULA_RUNTIME = "opencode"
FORMULA_VERSION = "1.18.15"

#: ``be.OUTPUT_TOKEN_MAX`` (opencode 1.18.15): the default response-token ceiling.
OUTPUT_TOKEN_MAX_DEFAULT = 32000

#: ``zd`` (opencode 1.18.15): the cap on the compaction reserve when the model declares an
#: input limit.
COMPACTION_RESERVED_CAP = 20000

#: The advisory fraction: at/above this share of the operative limit the verdict is WARN —
#: advisory only, never a stopping condition (the operator's 2026-09-15 context-policy change).
WARN_FRACTION = 0.8

#: Explicit, cross-surface LOCAL POLICY cap. Read by the shared resolver, so the CLI, the
#: capsule, and the exec-boundary gate judge identically. Clamped to the native usable limit;
#: a policy cap never masquerades as native compaction.
EFFECTIVE_LIMIT_ENV = "FINOPS_SESSION_CTX_LIMIT"

#: The runtime's response-token-ceiling override (opencode ``OPENCODE_EXPERIMENTAL_OUTPUT_TOKEN_MAX``).
OUTPUT_TOKEN_MAX_ENV = "OPENCODE_EXPERIMENTAL_OUTPUT_TOKEN_MAX"

#: The installed catalog cache override (the fallback source; tests point this at a fixture).
MODELS_CACHE_ENV = "FINOPS_OPENCODE_MODELS_CACHE"

#: The runtime config location override (opencode's own ``OPENCODE_CONFIG``).
OPENCODE_CONFIG_ENV = "OPENCODE_CONFIG"

#: The runtime binary override for the preferred limit resolution. An explicit EMPTY value
#: disables the CLI path (the fallback then applies); unset searches PATH and ~/.opencode/bin.
RUNTIME_BIN_ENV = "FINOPS_OPENCODE_BIN"

#: The limit-source selector: ``auto`` (default — runtime CLI, then catalog fallback) or
#: ``catalog`` (skip the CLI; deterministic for tests/hermetic environments).
CAPACITY_SOURCE_ENV = "FINOPS_SESSION_CAPACITY_SOURCE"

#: The runtime's project-config disable switch (opencode ``OPENCODE_DISABLE_PROJECT_CONFIG``).
DISABLE_PROJECT_CONFIG_ENV = "OPENCODE_DISABLE_PROJECT_CONFIG"

#: Bound on the runtime CLI call and its output (a hung/babbling child never hangs the check).
RUNTIME_CLI_TIMEOUT_S = 15.0
RUNTIME_CLI_MAX_OUTPUT_BYTES = 8_000_000

#: The verdict vocabulary the CLI/capsule/gate share.
VERDICTS = ("OK", "WARN", "COMPACT", "CLOSE", "UNJUDGED")

_TRUTHY = {"1", "true", "True", "yes", "on"}


@dataclass(frozen=True)
class ModelRef:
    """The ACTIVE session model, as resolved from the session store."""

    provider_id: str
    model_id: str
    variant: str | None = None
    source: str = "session.model"  # session.model | message.model


@dataclass(frozen=True)
class SessionCapacity:
    """The resolved capacity of one session's active model.

    ``native_effective_limit`` is the runtime's own usable boundary (where ITS compaction
    starts). ``effective_limit`` is the OPERATIVE boundary the judgment uses: the native limit,
    or the operator's policy cap when one is set and lower. ``policy_limit`` names the cap.
    """

    model: ModelRef
    context_limit: int | None
    input_limit: int | None
    output_limit: int | None
    response_headroom_tokens: int
    compaction_reserved_tokens: int
    native_effective_limit: int
    effective_limit: int
    hard_limit: int
    policy_limit: int | None = None
    warn_fraction: float = WARN_FRACTION
    compaction_enabled: bool = True
    provenance: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """The machine shape embedded in the budget report and the capsule."""
        return {
            "effective_limit": self.effective_limit,
            "native_effective_limit": self.native_effective_limit,
            "policy_limit": self.policy_limit,
            "hard_limit": self.hard_limit,
            "context_limit": self.context_limit,
            "input_limit": self.input_limit,
            "output_limit": self.output_limit,
            "response_headroom_tokens": self.response_headroom_tokens,
            "compaction_reserved_tokens": self.compaction_reserved_tokens,
            "warn_fraction": self.warn_fraction,
            "compaction_enabled": self.compaction_enabled,
        }


# ── the runtime's own calculation (opencode 1.18.15, ported) ────────────────────


def max_output_tokens(output_limit: int | None, output_token_max: int | None = None) -> int:
    """``min(model.limit.output, outputTokenMax ?? 32000) || 32000`` — opencode's headroom.

    The ``||`` is deliberate fidelity: a missing or zero output limit yields the default
    ceiling, never zero.
    """
    ceiling = (
        output_token_max
        if isinstance(output_token_max, int) and not isinstance(output_token_max, bool)
        and output_token_max > 0
        else OUTPUT_TOKEN_MAX_DEFAULT
    )
    limit = output_limit if isinstance(output_limit, int) and not isinstance(output_limit, bool) else 0
    return min(limit, ceiling) or ceiling


def effective_limit(
    *,
    context_limit: int | None,
    input_limit: int | None,
    output_limit: int | None,
    output_token_max: int | None = None,
    reserved: int | None = None,
) -> int:
    """opencode's usable-context boundary — ``SessionCompaction.isOverflow``'s threshold.

    ``0`` means the runtime would DISABLE its overflow check (``limit.context === 0``): the
    capacity is unresolvable and the caller must refuse to judge, never treat it as infinite.
    """
    context = context_limit if isinstance(context_limit, int) and context_limit > 0 else 0
    if context == 0:
        return 0
    headroom = max_output_tokens(output_limit, output_token_max)
    reserve = (
        reserved
        if isinstance(reserved, int) and not isinstance(reserved, bool) and reserved >= 0
        else min(COMPACTION_RESERVED_CAP, headroom)
    )
    if isinstance(input_limit, int) and not isinstance(input_limit, bool) and input_limit > 0:
        return max(0, input_limit - reserve)
    return max(0, context - headroom)


def usage_context_tokens(tokens: dict[str, Any] | None) -> int | None:
    """The runtime's overflow measure for one usage sample: ``total``, else the component sum.

    ``Dl``'s expression verbatim: ``tokens.total || input + output + cache.read + cache.write``
    — ``reasoning`` is NOT in the sum (adding it over-counts; the runtime would not compact
    where the local check would). Returns ``None`` when the sample carries no non-zero value —
    the pending/unfinished shape, which must never read as a measured zero.
    """
    tokens = tokens or {}
    cache = tokens.get("cache") or {}
    values = (
        tokens.get("input", 0) or 0,
        tokens.get("output", 0) or 0,
        cache.get("read", 0) or 0,
        cache.get("write", 0) or 0,
    )
    try:
        values = tuple(int(v) for v in values)
    except (TypeError, ValueError):
        return None
    total = tokens.get("total")
    has_total = isinstance(total, (int, float)) and not isinstance(total, bool) and total > 0
    if not any(v > 0 for v in values) and not has_total:
        return None
    if has_total:
        return int(total)
    return values[0] + values[1] + values[2] + values[3]


def classify(context_tokens: int, capacity: SessionCapacity) -> str:
    """The verdict for a measured context against a resolved capacity.

    * ``CLOSE``   — at/over the model's HARD context limit (the next request cannot be
      processed), at/over the native boundary when compaction is disabled, or at/over a LOCAL
      POLICY cap below the native boundary (a policy cap is not a native trigger — nothing
      will reduce the context there, so the session closes and hands off).
    * ``COMPACT`` — at/over the NATIVE usable boundary: the installed runtime compacts on the
      next request and the SAME session/task continues; re-evaluate after.
    * ``WARN``    — at/over ``warn_fraction`` of the operative limit: ADVISORY only.
    * ``OK``      — below the advisory fraction.
    """
    if context_tokens >= capacity.hard_limit:
        return "CLOSE"
    if context_tokens >= capacity.native_effective_limit:
        return "COMPACT" if capacity.compaction_enabled else "CLOSE"
    if capacity.policy_limit is not None and context_tokens >= capacity.policy_limit:
        return "CLOSE"
    if context_tokens >= capacity.warn_fraction * capacity.effective_limit:
        return "WARN"
    return "OK"


# ── identity: the ACTIVE session model (never a repository/child default) ───────


def _read_session_row(db_path: Path, session_id: str) -> dict[str, Any] | None:
    """The session row as a dict (schema-tolerant: missing columns simply do not appear)."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cur = con.cursor()
        row = cur.execute("SELECT * FROM session WHERE id=?", (session_id,)).fetchone()
        if row is None:
            return None
        columns = [d[0] for d in cur.description]
        return dict(zip(columns, row, strict=False))
    finally:
        con.close()


def _parse_model_json(raw: Any) -> dict[str, str]:
    if isinstance(raw, dict):
        payload = raw
    elif isinstance(raw, str) and raw.strip():
        try:
            payload = json.loads(raw)
        except ValueError:
            return {}
    else:
        return {}
    if not isinstance(payload, dict):
        return {}
    provider = str(payload.get("providerID") or payload.get("provider") or "").strip()
    model = str(payload.get("id") or payload.get("modelID") or "").strip()
    if not provider or not model:
        return {}
    variant = payload.get("variant")
    out = {"provider_id": provider, "model_id": model}
    if variant:
        out["variant"] = str(variant)
    return out


def _newest_message_model(db_path: Path, session_id: str) -> dict[str, str]:
    """Fallback identity: the newest assistant message's ``providerID``/``modelID``."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cur = con.cursor()
        rows = cur.execute(
            "SELECT data FROM message WHERE session_id=? ORDER BY time_created DESC",
            (session_id,),
        ).fetchall()
        for (blob,) in rows:
            try:
                data = json.loads(blob)
            except (TypeError, ValueError):
                continue
            if data.get("role") != "assistant":
                continue
            provider = str(data.get("providerID") or "").strip()
            model = str(data.get("modelID") or "").strip()
            if provider and model:
                return {"provider_id": provider, "model_id": model}
        return {}
    finally:
        con.close()


def resolve_session_model(
    db_path: Path | str, session_id: str
) -> tuple[ModelRef | None, str, str]:
    """``(model, source, runtime_version)`` for the session's ACTIVE model.

    The session row's ``model`` field is authoritative (opencode rewrites it on a model
    switch); the newest assistant message is the documented fallback. ``(None, reason, …)``
    means the model cannot be resolved — the caller must NOT substitute the repository
    default or a workflow model.
    """
    path = Path(db_path)
    sid = (session_id or "").strip()
    if not sid:
        return None, "no session identity supplied", ""
    row = _read_session_row(path, sid)
    if row is None:
        return None, f"session {sid!r} does not exist in {path}", ""
    runtime_version = str(row.get("version") or "")
    parsed = _parse_model_json(row.get("model"))
    if parsed:
        return ModelRef(
            provider_id=parsed["provider_id"],
            model_id=parsed["model_id"],
            variant=parsed.get("variant"),
            source="session.model",
        ), "", runtime_version
    fallback = _newest_message_model(path, sid)
    if fallback:
        return ModelRef(
            provider_id=fallback["provider_id"],
            model_id=fallback["model_id"],
            source="message.model",
        ), "", runtime_version
    return None, f"session {sid!r} carries no resolved model (session.model and messages are silent)", runtime_version


def _session_directory(db_path: Path, session_id: str) -> str | None:
    """The session's project directory (for the project config lookup) — best effort."""
    try:
        row = _read_session_row(db_path, session_id)
    except Exception:  # noqa: BLE001 — the lookup is optional metadata
        return None
    directory = str((row or {}).get("directory") or "").strip()
    return directory or None


# ── source 1: the runtime's own resolved model metadata (preferred) ─────────────


def _opencode_binary(env: dict[str, str]) -> str | None:
    """The installed runtime binary: explicit env, PATH, then the conventional home install.

    An explicit EMPTY ``FINOPS_OPENCODE_BIN`` disables the CLI source (the caller falls back
    to the catalog) — the seam hermetic tests and container shapes use.
    """
    if RUNTIME_BIN_ENV in env:
        explicit = str(env.get(RUNTIME_BIN_ENV) or "").strip()
        return explicit or None
    found = shutil.which("opencode")
    if found:
        return found
    candidate = Path.home() / ".opencode" / "bin" / "opencode"
    return str(candidate) if candidate.is_file() else None


def _parse_models_verbose(text: str) -> dict[tuple[str, str], dict[str, Any]]:
    """Parse ``opencode models --verbose`` output: every JSON body with a provider/model/limit."""
    limits: dict[tuple[str, str], dict[str, Any]] = {}
    decoder = json.JSONDecoder()
    index = 0
    while True:
        start = text.find("{", index)
        if start == -1:
            return limits
        try:
            payload, end = decoder.raw_decode(text, start)
        except ValueError:
            index = start + 1
            continue
        index = end
        if (
            isinstance(payload, dict)
            and payload.get("providerID")
            and payload.get("id")
            and isinstance(payload.get("limit"), dict)
        ):
            limits[(str(payload["providerID"]), str(payload["id"]))] = payload["limit"]
    return limits


def _run_models_verbose(
    binary: str, provider_id: str, env: dict[str, str]
) -> dict[tuple[str, str], dict[str, Any]] | None:
    """The runtime's resolved models for one provider. Failure of ANY kind returns ``None``.

    The child inherits the caller's environment (the runtime must see its own config/auth
    env), with the caller's mapping overlaid. Bounded by a timeout and an output cap — a
    hung or babbling runtime never hangs the budget check.
    """
    child_env = {**os.environ, **{k: str(v) for k, v in env.items() if v is not None}}
    try:
        proc = subprocess.run(
            [binary, "models", provider_id, "--verbose"],
            capture_output=True,
            text=True,
            timeout=RUNTIME_CLI_TIMEOUT_S,
            env=child_env,
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    if proc.returncode != 0:
        return None
    stdout = proc.stdout or ""
    if len(stdout) > RUNTIME_CLI_MAX_OUTPUT_BYTES:
        return None
    return _parse_models_verbose(stdout)


# ── source 2: the catalog + config overlay fallback ─────────────────────────────


def default_models_cache(env: dict[str, str] | None = None) -> Path:
    """The installed opencode catalog cache (``models.json``)."""
    source = os.environ if env is None else env
    explicit = str(source.get(MODELS_CACHE_ENV) or "").strip()
    if explicit:
        return Path(explicit).expanduser()
    xdg = str(source.get("XDG_CACHE_HOME") or "").strip()
    base = Path(xdg).expanduser() if xdg else Path.home() / ".cache"
    return base / "opencode" / "models.json"


def _strip_jsonc(text: str) -> str:
    """Drop ``//`` / ``/* */`` comments and trailing commas outside strings (JSONC)."""
    out: list[str] = []
    i = 0
    in_string = False
    escaped = False
    while i < len(text):
        ch = text[i]
        if in_string:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < len(text) and text[i + 1] == "/":
            while i < len(text) and text[i] not in "\r\n":
                i += 1
            continue
        if ch == "/" and i + 1 < len(text) and text[i + 1] == "*":
            end = text.find("*/", i + 2)
            i = len(text) if end == -1 else end + 2
            continue
        if ch == ",":
            # A trailing comma (next non-whitespace is } or ]) is legal JSONC, invalid JSON —
            # the runtime's parser accepts it, so the fallback must too (reviewer finding).
            j = i + 1
            while j < len(text) and text[j] in " \t\r\n":
                j += 1
            if j < len(text) and text[j] in "}]":
                i += 1
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def _load_json_config(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        payload = json.loads(_strip_jsonc(raw))
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _config_candidates(directory: str | None, env: dict[str, str]) -> list[Path]:
    """The config files opencode merges, in ITS order: global dir → explicit → project.

    opencode 1.18.15's loader (``Config.loadInstanceState``) merges the global config dir
    first, then ``OPENCODE_CONFIG`` (tagged global), then the project config — so a project
    setting WINS over the explicit file (reviewer finding; the previous order had it
    backwards). ``OPENCODE_DISABLE_PROJECT_CONFIG`` is honored.
    """
    candidates: list[Path] = []
    xdg = str(env.get("XDG_CONFIG_HOME") or "").strip()
    config_home = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    for name in ("config.json", "opencode.json", "opencode.jsonc"):
        candidates.append(config_home / "opencode" / name)
    explicit = str(env.get(OPENCODE_CONFIG_ENV) or "").strip()
    if explicit:
        candidates.append(Path(explicit).expanduser())
    disabled = str(env.get(DISABLE_PROJECT_CONFIG_ENV) or "") in _TRUTHY
    if directory and not disabled:
        for name in ("opencode.json", "opencode.jsonc"):
            candidates.append(Path(directory) / name)
    return candidates


def load_runtime_config(
    *, directory: str | None = None, env: dict[str, str] | None = None
) -> dict[str, Any]:
    """The merged config subset that shapes capacity: per-model ``limit`` + ``compaction``.

    Returns ``{"limits": {(provider, model): {context, input, output}}, "compaction": {...},
    "sources": [...]}``. Files merge in the runtime's order and limits merge FIELD-BY-FIELD
    across files (a project file overriding only ``output`` keeps the inherited ``context`` —
    reviewer finding). Only the keys the formula consumes are merged; the authoritative
    resolver remains the runtime's own CLI (source 1).
    """
    source = os.environ if env is None else env
    limits: dict[tuple[str, str], dict[str, Any]] = {}
    compaction: dict[str, Any] = {}
    sources: list[str] = []
    for path in _config_candidates(directory, source):
        if not path.is_file():
            continue
        payload = _load_json_config(path)
        if not payload:
            continue
        sources.append(str(path))
        providers = payload.get("provider")
        if isinstance(providers, dict):
            for provider_id, provider in providers.items():
                models = (provider or {}).get("models") if isinstance(provider, dict) else None
                if not isinstance(models, dict):
                    continue
                for model_id, model in models.items():
                    limit = (model or {}).get("limit") if isinstance(model, dict) else None
                    if not isinstance(limit, dict):
                        continue
                    entry = limits.setdefault((str(provider_id), str(model_id)), {})
                    for key in ("context", "input", "output"):
                        value = limit.get(key)
                        if isinstance(value, (int, float)) and not isinstance(value, bool):
                            entry[key] = value
        block = payload.get("compaction")
        if isinstance(block, dict):
            compaction.update(block)
    return {"limits": limits, "compaction": compaction, "sources": sources}


def load_models_cache(path: Path) -> dict[str, Any] | None:
    """The ``models.json`` catalog (``{provider: {models: {model: {...}}}}``) or ``None``."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _catalog_limit(catalog: dict[str, Any], model: ModelRef) -> dict[str, Any] | None:
    provider = catalog.get(model.provider_id)
    if not isinstance(provider, dict):
        return None
    models = provider.get("models")
    if not isinstance(models, dict):
        return None
    entry = models.get(model.model_id)
    if not isinstance(entry, dict):
        return None
    limit = entry.get("limit")
    return limit if isinstance(limit, dict) else None


def _positive_int(value: Any) -> int | None:
    """A positive int from an int/float or a numeric string (env vars arrive as strings)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text.isdigit():
            return None
        value = int(text)
    elif not isinstance(value, (int, float)):
        return None
    value = int(value)
    return value if value > 0 else None


def _merge_limits(*layers: dict[str, Any] | None) -> dict[str, Any]:
    """Field-by-field merge (later layers win per field, never wholesale)."""
    merged: dict[str, Any] = {}
    for layer in layers:
        if not layer:
            continue
        for key in ("context", "input", "output"):
            value = layer.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                merged[key] = value
    return merged


def resolve_capacity(
    db_path: Path | str,
    session_id: str,
    *,
    env: dict[str, str] | None = None,
    cache_path: Path | str | None = None,
) -> tuple[SessionCapacity | None, str, ModelRef | None]:
    """Resolve the session's usable capacity. ``(capacity, reason, model)``.

    ``capacity is None`` means UNJUDGED (with ``reason`` naming the gap): an unresolvable
    model identity, no metadata from the runtime CLI or the catalog+config fallback, or a
    model whose context limit is zero (the runtime disables its overflow check there —
    capacity is unknown, never infinite). The model is returned even on failure so the
    report can name what it saw.
    """
    source = os.environ if env is None else env
    path = Path(db_path)
    model, model_reason, runtime_version = resolve_session_model(path, session_id)
    if model is None:
        return None, model_reason, None

    directory = _session_directory(path, session_id)
    config = load_runtime_config(directory=directory, env=source)

    # Source 1: the runtime's own resolved metadata (preferred). Source 2: the documented
    # catalog + config fallback. Limits merge FIELD-BY-FIELD across both when both exist.
    limit_source = "catalog+config"
    runtime_limits: dict[str, Any] | None = None
    if str(source.get(CAPACITY_SOURCE_ENV) or "auto").strip().lower() != "catalog":
        binary = _opencode_binary(source)
        if binary:
            resolved = _run_models_verbose(binary, model.provider_id, source)
            if resolved is not None:
                runtime_limits = resolved.get((model.provider_id, model.model_id))
                if runtime_limits:
                    limit_source = f"opencode-cli:{binary}"

    catalog_path = Path(cache_path) if cache_path else default_models_cache(source)
    catalog = load_models_cache(catalog_path) if catalog_path else None
    catalog_limits = _catalog_limit(catalog, model) if catalog else None
    overlay = config["limits"].get((model.provider_id, model.model_id)) or {}
    merged = _merge_limits(catalog_limits, overlay, runtime_limits)
    context_limit = _positive_int(merged.get("context"))
    if context_limit is None:
        return (
            None,
            f"no installed metadata for {model.provider_id}/{model.model_id} (runtime CLI "
            f"unavailable or silent; catalog {catalog_path} + runtime config carry no context "
            f"limit) — capacity cannot be resolved",
            model,
        )

    output_token_max = _positive_int(source.get(OUTPUT_TOKEN_MAX_ENV))
    input_limit = _positive_int(merged.get("input"))
    output_limit = _positive_int(merged.get("output"))
    headroom = max_output_tokens(output_limit, output_token_max)
    compaction_block = config["compaction"]
    reserved_cfg = compaction_block.get("reserved")
    reserved = (
        int(reserved_cfg)
        if isinstance(reserved_cfg, (int, float)) and not isinstance(reserved_cfg, bool)
        and reserved_cfg >= 0
        else None
    )
    compaction_enabled = compaction_block.get("auto") is not False

    native = effective_limit(
        context_limit=context_limit,
        input_limit=input_limit,
        output_limit=output_limit,
        output_token_max=output_token_max,
        reserved=reserved,
    )
    override = _positive_int(source.get(EFFECTIVE_LIMIT_ENV))
    policy = min(override, native) if override is not None else None
    effective = policy if policy is not None else native
    if effective <= 0:
        return (
            None,
            f"model {model.provider_id}/{model.model_id} reports context 0 — the runtime "
            f"disables its overflow check and capacity cannot be resolved",
            model,
        )

    provenance: dict[str, Any] = {
        "formula": f"{FORMULA_RUNTIME}@{FORMULA_VERSION}:SessionCompaction.isOverflow",
        "formula_version": FORMULA_VERSION,
        "runtime_version": runtime_version or None,
        "version_match": bool(runtime_version) and runtime_version == FORMULA_VERSION,
        "model_source": model.source,
        "limits_source": limit_source,
        "catalog_source": str(catalog_path) if catalog_path else None,
        "config_sources": config["sources"],
        "output_token_max_source": (
            f"{OUTPUT_TOKEN_MAX_ENV}" if output_token_max is not None else f"default:{OUTPUT_TOKEN_MAX_DEFAULT}"
        ),
        "effective_limit_source": (
            f"{EFFECTIVE_LIMIT_ENV}(policy)" if policy is not None else "resolved-model-capacity"
        ),
        "compaction": {
            "auto": compaction_enabled,
            "reserved": reserved,
            "sources": config["sources"],
        },
    }
    capacity = SessionCapacity(
        model=model,
        context_limit=context_limit,
        input_limit=input_limit,
        output_limit=output_limit,
        response_headroom_tokens=headroom,
        compaction_reserved_tokens=(
            reserved if reserved is not None else min(COMPACTION_RESERVED_CAP, headroom)
        ),
        native_effective_limit=native,
        effective_limit=effective,
        hard_limit=context_limit,
        policy_limit=policy,
        compaction_enabled=compaction_enabled,
        provenance=provenance,
    )
    return capacity, "", model


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "CAPACITY_SOURCE_ENV",
    "COMPACTION_RESERVED_CAP",
    "EFFECTIVE_LIMIT_ENV",
    "FORMULA_VERSION",
    "MODELS_CACHE_ENV",
    "ModelRef",
    "OUTPUT_TOKEN_MAX_DEFAULT",
    "OUTPUT_TOKEN_MAX_ENV",
    "RUNTIME_BIN_ENV",
    "SessionCapacity",
    "VERDICTS",
    "WARN_FRACTION",
    "classify",
    "default_models_cache",
    "effective_limit",
    "load_models_cache",
    "load_runtime_config",
    "max_output_tokens",
    "resolve_capacity",
    "resolve_session_model",
    "usage_context_tokens",
]
