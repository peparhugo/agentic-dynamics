#!/usr/bin/env python3
"""Freeze ONE explicitly selected OpenCode session into a fork checkpoint.

The supported operation for the native-conversation fork experiment: select a live
``aio-control`` (or any) session by ID, extract ONLY its conversation (session + messages +
parts + the project rows it references) into a fresh standalone database, verify it, and
publish it into the workflow checkpoint store in the SAME receipt format the fleet's fork
transport consumes (``opencode-checkpoint/v1`` + ``latest.json``). Credential/account tables
are never copied: the cell's isolated launch contract keeps managing its own credentials.

Privacy: the extract keeps the conversation in the store's data plane (host-persisted, AIO
readable); the command prints only identities, counts and hashes — never transcript content.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_DB = Path.home() / ".local/share/opencode/opencode.db"
DEFAULT_STORE = REPO / "experiments" / "results" / "opencode"

#: Credential/account material is EXCLUDED by construction: only these tables travel.
SESSION_TABLES = ("session", "message", "part", "project", "project_directory", "workspace")
#: Migration bookkeeping travels as ROWS (schema-state), never as credentials.
MIGRATION_TABLE = "data_migration"


def _connect_ro(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def _stream_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write(directory: Path, name: str, payload: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(directory), prefix=f".{name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, directory / name)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def _session_identity(db: Path, session_id: str) -> str:
    """Stable identity of the extracted conversation: message count for the session."""
    con = _connect_ro(db)
    try:
        n = con.execute(
            "select count(*) from message where session_id = ?", (session_id,)
        ).fetchone()[0]
    finally:
        con.close()
    return hashlib.sha256(f"{session_id}:{n}".encode()).hexdigest()


def extract_session(src_db: Path, session_id: str, dest_db: Path) -> dict:
    """Extract ONLY ``session_id``'s conversation into a fresh standalone database."""
    if not src_db.is_file():
        raise RuntimeError(f"source database missing at {src_db}")
    src = _connect_ro(src_db)
    dest_db.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(dest_db.parent), prefix=dest_db.name + ".")
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        dest = sqlite3.connect(str(tmp))
        try:
            dest.execute("PRAGMA journal_mode=DELETE")
            src.execute("BEGIN")  # one consistent read view across the SELECTs
            row = src.execute(
                "select id from session where id = ?", (session_id,)
            ).fetchone()
            if not row:
                raise RuntimeError(f"session {session_id} not found in {src_db}")
            # FULL schema (tables/indexes/triggers) so OpenCode opens a structurally complete
            # store; ROWS only for the selected conversation (+ its project) and migrations.
            ddl = [
                r[0]
                for r in src.execute(
                    "select sql from sqlite_master where sql is not null order by type desc"
                ).fetchall()
            ]
            for statement in ddl:
                with contextlib.suppress(sqlite3.Error):
                    dest.execute(statement)
            project_id = src.execute(
                "select project_id from session where id = ?", (session_id,)
            ).fetchone()[0]
            copies = [
                ("session", "select * from session where id = ?", (session_id,)),
                ("message", "select * from message where session_id = ?", (session_id,)),
                (
                    "part",
                    "select * from part where message_id in "
                    "(select id from message where session_id = ?)",
                    (session_id,),
                ),
                (MIGRATION_TABLE, f"select * from {MIGRATION_TABLE}", ()),
                ("project", "select * from project where id = ?", (project_id,)),
                (
                    "project_directory",
                    "select * from project_directory where project_id = ?",
                    (project_id,),
                ),
                (
                    "workspace",
                    "select * from workspace where id in "
                    "(select workspace_id from session where id = ? and workspace_id is not null)",
                    (session_id,),
                ),
            ]
            counts: dict[str, int] = {}
            for table, sql, args in copies:
                try:
                    rows = src.execute(sql, args).fetchall()
                except sqlite3.OperationalError:
                    counts[table] = 0
                    continue
                if not rows:
                    counts[table] = 0
                    continue
                placeholders = ",".join("?" for _ in rows[0])
                dest.executemany(
                    f"insert or replace into {table} values ({placeholders})", rows
                )
                counts[table] = len(rows)
            src.execute("COMMIT")
            check = dest.execute("PRAGMA integrity_check").fetchone()
            if not check or check[0] != "ok":
                raise RuntimeError(f"extracted database failed integrity_check: {check}")
            dest.commit()
        finally:
            dest.close()
            src.close()
        os.replace(tmp, dest_db)
        return counts
    finally:
        if tmp.exists():
            tmp.unlink()


def publish_checkpoint(
    snapshot: Path, *, workflow: str, attempt_id: str, session_id: str,
    store: Path = DEFAULT_STORE, session_identity: str = "",
) -> dict:
    """Publish ``snapshot`` into the store with the fleet's receipt format (immutable)."""
    import shutil

    dest_rel = f"snapshots/{attempt_id}.db"
    dest = store / workflow / dest_rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        if _stream_sha256(dest) != _stream_sha256(snapshot):
            raise RuntimeError(
                f"checkpoint {workflow}/{attempt_id} already published with different bytes"
            )
    else:
        shutil.copy2(snapshot, dest)
    digest = _stream_sha256(dest)
    receipt = {
        "schema": "opencode-checkpoint/v1",
        "workflow": workflow,
        "attempt_id": attempt_id,
        "run_id": "host-freeze",
        "phase": "freeze",
        "attempt": 1,
        "snapshot": dest_rel,
        "sha256": digest,
        "session_identity": session_identity or "",
        "session_id": session_id,
        "forked_from": "",
        "prepared_prompt_sha256": "",
        "runtime": {"opencode": "1.18.15"},
        "source": {"kind": "live-session-freeze"},
        "persisted_at": datetime.now(timezone.utc).isoformat(),
    }
    payload = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    _atomic_write(store / workflow / "receipts", f"{attempt_id}.json", payload)
    _atomic_write(store / workflow, "latest.json", payload)
    return receipt


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--session", required=True, help="the explicitly selected session id")
    ap.add_argument("--workflow", default="aio_session", help="checkpoint workflow/scope name")
    ap.add_argument("--attempt-id", default="", help="receipt attempt id (default: stamped)")
    ap.add_argument("--db", default=str(DEFAULT_DB), help="source opencode database")
    ap.add_argument("--store", default=str(DEFAULT_STORE), help="checkpoint store root")
    ap.add_argument("--dry-run", action="store_true", help="extract + verify, publish nothing")
    args = ap.parse_args(argv)

    src_db = Path(args.db)
    store = Path(args.store)
    attempt_id = args.attempt_id or f"{args.session}-freeze{int(time.time())}"
    work = Path(tempfile.mkdtemp(prefix="session_checkpoint_"))
    snapshot = work / f"{attempt_id}.db"
    try:
        counts = extract_session(src_db, args.session, snapshot)
        identity = _session_identity(snapshot, args.session)
        digest = _stream_sha256(snapshot)
        print(json.dumps({
            "schema": "session-checkpoint/v1", "session_id": args.session,
            "snapshot_sha256": digest, "session_identity": identity,
            "counts": counts, "bytes": snapshot.stat().st_size,
            "workflow": args.workflow, "attempt_id": attempt_id, "dry_run": args.dry_run,
        }, indent=2))
        if not args.dry_run:
            receipt = publish_checkpoint(snapshot, workflow=args.workflow, attempt_id=attempt_id,
                                        session_id=args.session, store=store,
                                        session_identity=identity)
            print(f"[session-checkpoint] published {args.workflow}/{attempt_id} "
                  f"(sha {receipt['sha256'][:16]})", file=sys.stderr)
        return 0
    finally:
        import shutil as _sh
        _sh.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
