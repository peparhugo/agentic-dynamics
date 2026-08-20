"""Manifest-registry service — the cached read of the compacted registry array.

Extracted from ``server.py`` (refactor-repair Debt-1). ``_load_registry_cached`` caches the
parsed ``data_manifest.json`` registry on the file's ``(path, mtime_ns, size)`` identity; the
cache dict is ``server._REGISTRY_CACHE`` so the tests can clear it.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from apps.control_room import server
from scripts import registry as registry_cli


def _load_registry_cached(manifest_path: Path) -> list[dict[str, Any]]:
    """Return the parsed manifest registry, cached on the file's identity.

    Replaces a per-request ``registry_cli.load_registry`` (review F4). The file
    only changes when ``generate_manifest.py`` rewrites it, so caching on
    ``(path, mtime_ns, size)`` avoids a full-file ``json.loads`` for every
    registry/lineage request while still noticing a rewrite immediately. A
    missing file caches the empty-list result under a ``(path, None, None)`` key;
    when the file later appears its key changes and the cache misses.
    """
    try:
        stat = manifest_path.stat()
        key = (str(manifest_path), stat.st_mtime_ns, stat.st_size)
    except FileNotFoundError:
        key = (str(manifest_path), None, None)
    cached = server._REGISTRY_CACHE.get(key)
    if cached is None:
        cached = registry_cli.load_registry(manifest_path)
        server._REGISTRY_CACHE[key] = cached
    return cached
