"""sync_data parity tests (public-truth review "smaller").

``scripts/sync_data.py`` normalizes the canonical story payloads to parquet. The review's
"smaller" issue: ``--check`` only counted rows (a stale file passes), and the writes were
non-atomic with no source-identity sidecar. These tests lock in the correction:

1. an empty canonical source writes an EMPTY parquet (never leaves a stale table in place);
2. the identity sidecar records the resolver identity that produced the tables;
3. ``check()`` proves the parquet matches the current resolver output (0 when current, 1
   when the sidecar identity is stale).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pyarrow.parquet as pq
import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import sync_data  # noqa: E402


def test_atomic_write_writes_an_empty_table(tmp_path):
    """An empty canonical source writes an EMPTY parquet — never leaves a stale table."""
    final = tmp_path / "sessions.parquet"
    sync_data._write_parquet_atomic([], sync_data.SESSION_SCHEMA, final)

    assert final.exists()
    assert pq.read_table(final).num_rows == 0


def test_atomic_write_leaves_no_tmp_behind(tmp_path):
    """The temp file is renamed away, so a partial write can never be mistaken for output."""
    final = tmp_path / "stories.parquet"
    sync_data._write_parquet_atomic([{"story_name": "x"}], sync_data.STORY_SCHEMA, final)
    assert final.exists()
    assert not final.with_suffix(final.suffix + ".tmp").exists()


def test_identity_sidecar_records_the_resolver_identity(tmp_path, monkeypatch):
    """The sidecar records WHICH canonical source produced the tables + content hashes."""

    class _Identity:
        registry_identity_sha256 = "a" * 64

    class _FakeTables:
        identity = _Identity()
        resolved_input_sha256 = "b" * 64

    monkeypatch.setattr(sync_data, "SYNC_IDENTITY_PATH", tmp_path / "sync_identity.json")
    sync_data._write_identity_sidecar(_FakeTables(), {"sessions": 1, "stories": 2}, [], [])

    sidecar = json.loads((tmp_path / "sync_identity.json").read_text(encoding="utf-8"))
    assert sidecar["schema_version"] == "sync-identity/v2"
    assert sidecar["registry_identity_sha256"] == "a" * 64
    assert sidecar["resolved_input_sha256"] == "b" * 64
    assert sidecar["rows"] == {"sessions": 1, "stories": 2}
    # m4 content hashes: the row digests, the transform source hash, and the schema hash.
    assert len(sidecar["sessions_rows_sha256"]) == 64
    assert len(sidecar["stories_rows_sha256"]) == 64
    assert len(sidecar["sync_transform_sha256"]) == 64
    assert len(sidecar["schema_sha256"]) == 64


def test_content_hashes_are_deterministic_and_sensitive():
    """The row content hash is deterministic, and changes when the rows change."""
    assert sync_data._content_sha256([{"a": 1}]) == sync_data._content_sha256([{"a": 1}])
    assert sync_data._content_sha256([{"a": 1}]) != sync_data._content_sha256([{"a": 2}])
    # the transform + schema hashes are stable across calls
    assert sync_data._transform_sha256() == sync_data._transform_sha256()
    assert sync_data._schema_sha256() == sync_data._schema_sha256()


def test_check_returns_zero_when_current():
    """``check()`` proves the committed parquet matches the current canonical source."""
    if not (sync_data.DATA_DIR / "sessions.parquet").exists():  # pragma: no cover
        pytest.skip("no parquet files — run scripts/sync_data.py first")
    assert sync_data.check() == 0


def test_check_detects_a_stale_sidecar(tmp_path, monkeypatch):
    """A stale sidecar identity makes ``check()`` return non-zero (real parity, not a row
    count that a stale file would also pass)."""
    bad_sidecar = {
        "schema_version": "sync-identity/v1",
        "registry_identity_sha256": "0" * 64,
        "resolved_input_sha256": "0" * 64,
        "rows": {"sessions": 0, "stories": 0},
    }
    path = tmp_path / "sync_identity.json"
    path.write_text(json.dumps(bad_sidecar), encoding="utf-8")
    monkeypatch.setattr(sync_data, "SYNC_IDENTITY_PATH", path)

    assert sync_data.check() == 1
