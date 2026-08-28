#!/usr/bin/env python3
"""Artifact-governance bundle planner (external review P2).

Implements the retention policy in ``docs/designs/proposed/artifact_retention_policy.md``:
the logical append-only model of ``experiments/results/`` stays; the PHYSICAL retention
model changes. This script is the planner for the Tier-2 artifact release — it never
moves anything by default.

Three modes:

- **dry-run (the default):** scans ``experiments/results/`` and prints every bundle
  candidate (path, size, sha256, age, reference-check verdict) plus a summary.
  Nothing is written, moved, or deleted.
- ``--bundle-out <dir>``: writes a content-addressed tar (``artifacts_<sha>.tar.gz``)
  + a committed-manifest JSON (``bundle_<sha>.manifest.json``, member -> sha256) into
  ``<dir>``. Still removes nothing from the working tree.
- ``--bundle-out <dir> --prune``: removes bundled members from the working tree AFTER
  re-verifying (a) the manifest is git-tracked (committed before removal), (b) every
  member's current sha256 matches the manifest, (c) no member is referenced by the
  current registry index / data manifest, (d) no member is younger than the in-flight
  window. Operator-only; the default invocation never prunes.

The reference check: any file referenced by ``experiments/results/registry_index.jsonl``
(kb ``knowledge_id`` -> ``kb/<id>.json``) or ``experiments/data_manifest.json`` (registry
rows + every ``files`` array path) is NOT a candidate. ``experiments/results/workflows/``
is never a candidate (the live campaign-ledger surface — the 2d campaign writes ledgers
there now). Files younger than ``--min-age-days`` (default 7) are skipped as in-flight.

Usage::

    python3 scripts/bundle_artifacts.py                     # dry-run candidate inventory
    python3 scripts/bundle_artifacts.py --min-age-days 30   # tighter cut line
    python3 scripts/bundle_artifacts.py --bundle-out experiments/artifacts/manifests/
    python3 scripts/bundle_artifacts.py --bundle-out experiments/artifacts/manifests/ --prune
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tarfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "experiments" / "results"

REGISTRY_INDEX = "registry_index.jsonl"
DATA_MANIFEST = "data_manifest.json"

#: Bundle-eligible top-level subdirectories of ``experiments/results/``. Historical
#: campaign dirs (``cap_*``) are discovered dynamically; ``workflows/`` is protected
#: outright — the in-flight campaign writes its ledgers there.
ELIGIBLE_ROOTS = [
    "kb",
    "reports",
    "stories",
    "artifacts",
    "analysis",
    "reviews",
    "reviews_blind",
    "supervisor",
    "orphans",
    "legacy_labs",
    "proposals",
]

#: Never bundle these even if every gate passes (the retention line's own sources).
PROTECTED = {"workflows", REGISTRY_INDEX, DATA_MANIFEST}

MANIFEST_SCHEMA = "artifact-bundle-manifest/v1"


@dataclass(frozen=True)
class Candidate:
    """One scanned file with its bundle-eligibility verdict."""

    relpath: str  # repo-root-relative posix path
    size_bytes: int
    sha256: str
    age_days: float
    reference: str  # "referenced" | "unreferenced"
    status: str  # "candidate" | "skipped"
    reason: str  # empty for candidates


@dataclass(frozen=True)
class ReferenceIndex:
    """The retention-line reference set: what the current manifests still point at."""

    kb_ids: frozenset[str]  # <knowledge_id>.json names referenced by either manifest
    manifest_paths: frozenset[str]  # paths recorded in data_manifest.json's files arrays

    def is_referenced(self, relpath: str, name: str) -> bool:
        """True when ``relpath``/``name`` is pinned by the current registry or manifest."""
        if name in self.kb_ids:
            return True
        return any(p in (relpath, name) for p in self.manifest_paths)


def sha256_file(path: Path) -> str:
    """Return the hex sha256 of ``path`` (chunked read — members can be large)."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_reference_index(results_dir: Path) -> ReferenceIndex:
    """Load the reference set from registry_index.jsonl + data_manifest.json."""
    kb_ids: set[str] = set()
    manifest_paths: set[str] = set()

    registry = results_dir / REGISTRY_INDEX
    if registry.is_file():
        for line in registry.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                kid = json.loads(line).get("knowledge_id")
            except json.JSONDecodeError:
                continue
            if kid:
                kb_ids.add(f"{kid}.json")

    manifest = results_dir.parent / DATA_MANIFEST
    if manifest.is_file():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        for row in data.get("registry", []):
            kid = row.get("knowledge_id")
            if kid:
                kb_ids.add(f"{kid}.json")
        for section in data.get("files", {}).values():
            for path in section:
                manifest_paths.add(str(path))

    return ReferenceIndex(frozenset(kb_ids), frozenset(manifest_paths))


def eligible_roots(results_dir: Path) -> list[str]:
    """Static eligible roots + discovered top-level ``cap_*`` campaign dirs."""
    roots = list(ELIGIBLE_ROOTS)
    roots += sorted(
        p.name for p in results_dir.iterdir() if p.is_dir() and p.name.startswith("cap_")
    )
    return roots


def scan_candidates(
    results_dir: Path,
    ref: ReferenceIndex,
    *,
    repo_root: Path,
    min_age_days: float,
    now: float,
) -> list[Candidate]:
    """Scan every eligible root and return candidates + skipped files with reasons."""
    found: list[Candidate] = []
    for root_name in eligible_roots(results_dir):
        root = results_dir / root_name
        if root_name in PROTECTED or not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.is_symlink() or not path.is_file():
                continue
            relpath = path.relative_to(repo_root).as_posix()
            stat = path.stat()
            age_days = (now - stat.st_mtime) / 86_400.0
            digest = sha256_file(path)
            if ref.is_referenced(relpath, path.name):
                found.append(
                    Candidate(relpath, stat.st_size, digest, age_days, "referenced",
                              "skipped", "referenced by registry/manifest")
                )
            elif age_days < min_age_days:
                found.append(
                    Candidate(relpath, stat.st_size, digest, age_days, "unreferenced",
                              "skipped", f"in-flight (mtime {age_days:.1f}d < {min_age_days:.0f}d)")
                )
            else:
                found.append(
                    Candidate(relpath, stat.st_size, digest, age_days, "unreferenced",
                              "candidate", "")
                )
    return found


def print_candidates(candidates: list[Candidate], min_age_days: float) -> int:
    """Print the candidate inventory (the dry-run default); returns 0."""
    picks = [c for c in candidates if c.status == "candidate"]
    skipped_ref = sum(1 for c in candidates if c.status == "skipped" and c.reference == "referenced")
    skipped_fresh = sum(1 for c in candidates if c.status == "skipped" and "in-flight" in c.reason)
    print(f"bundle candidates ({min_age_days:.0f}-day in-flight window) — "
          f"experiments/results/, repo root {REPO_ROOT}")
    print()
    for c in sorted(picks, key=lambda c: c.relpath):
        print(f"{c.relpath:<76} {c.size_bytes:>10,} B  {c.age_days:>6.1f}d  {c.sha256[:12]}")
    print()
    total = sum(c.size_bytes for c in picks)
    print(f"candidates: {len(picks)} files, {total / 1e6:.1f} MB")
    print(f"skipped (referenced by registry/manifest): {skipped_ref}")
    print(f"skipped (in-flight, mtime < {min_age_days:.0f}d): {skipped_fresh}")
    print("dry-run — nothing was written, moved, or deleted")
    return 0


def _git_head(repo_root: Path) -> str:
    """Current HEAD sha (fallback "unknown" when the repo cannot be read)."""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    return out.stdout.strip() if out.returncode == 0 else "unknown"


def _git_tracked(repo_root: Path, path: Path) -> bool:
    """True when ``path`` is tracked by the repo's index."""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files", "--error-unmatch", "--", str(path)],
            capture_output=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return out.returncode == 0


def _bundle_manifest(members: dict[str, str], repo_root: Path) -> tuple[str, str, str]:
    """Canonical manifest JSON -> (json_text, bundle_sha256, total_bytes)."""
    total = 0
    for relpath in members:
        total += (repo_root / relpath).stat().st_size
    payload = {
        "schema_version": MANIFEST_SCHEMA,
        "bundle_sha256": "",  # self-hash filled below
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_head(repo_root),
        "member_count": len(members),
        "total_bytes": total,
        "members": members,
    }
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    bundle_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    payload["bundle_sha256"] = bundle_sha
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    return text, bundle_sha, total


def write_bundle(
    candidates: list[Candidate],
    out_dir: Path,
    repo_root: Path,
) -> int:
    """Write the content-addressed tar + committed manifest; removes nothing."""
    picks = sorted((c for c in candidates if c.status == "candidate"), key=lambda c: c.relpath)
    if not picks:
        print("no bundle candidates — nothing to write")
        return 0
    out_dir.mkdir(parents=True, exist_ok=True)
    members = {c.relpath: c.sha256 for c in picks}
    manifest_text, bundle_sha, total_bytes = _bundle_manifest(members, repo_root)
    tar_path = out_dir / f"artifacts_{bundle_sha}.tar.gz"
    manifest_path = out_dir / f"bundle_{bundle_sha}.manifest.json"

    with tarfile.open(tar_path, "w:gz") as tar:
        for relpath in members:
            tar.add(repo_root / relpath, arcname=relpath)
    manifest_path.write_text(manifest_text, encoding="utf-8")

    with tarfile.open(tar_path, "r:gz") as tar:
        names = sorted(m.name for m in tar.getmembers() if m.isfile())
    assert names == sorted(members), "tar member set drifted from the manifest"

    print(f"bundle written: {tar_path} ({total_bytes / 1e6:.1f} MB, {len(members)} members)")
    print(f"manifest written: {manifest_path}")
    print(f"bundle_sha256: {bundle_sha}")
    print()
    print("next steps (operator):")
    print("  1. commit the manifest (it is the reproducibility anchor — the tar is")
    print("     reproducible from it alone), then move the tar to the artifact release store")
    print("  2. run --prune to remove bundled members from the working tree")
    print("nothing was removed from the working tree")
    return 0


def prune_bundled(
    bundle_dir: Path,
    ref: ReferenceIndex,
    *,
    repo_root: Path,
    min_age_days: float,
    now: float,
) -> int:
    """Remove bundled members after re-verification (operator-only; never the default)."""
    manifests = sorted(bundle_dir.glob("bundle_*.manifest.json"))
    if not manifests:
        print("no bundle_*.manifest.json found in the bundle dir", file=sys.stderr)
        return 1
    manifest_path = manifests[-1]
    if not _git_tracked(repo_root, manifest_path):
        print(
            "refusing to prune: the bundle manifest is not tracked by git — commit it "
            "first (invariant: the bundle manifest is committed before removal)",
            file=sys.stderr,
        )
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    members: dict[str, str] = manifest["members"]
    print(f"prune plan: {len(members)} members from {manifest_path.name}")

    for relpath, expected in sorted(members.items()):
        path = repo_root / relpath
        if not path.is_file():
            print(f"  MISSING  {relpath} (already gone) — skipping")
            continue
        if ref.is_referenced(relpath, path.name):
            print(f"  REFUSED  {relpath} — now referenced by the registry/manifest (re-bundle)", file=sys.stderr)
            return 1
        if (now - path.stat().st_mtime) / 86_400.0 < min_age_days:
            print(f"  REFUSED  {relpath} — younger than the {min_age_days:.0f}-day in-flight window", file=sys.stderr)
            return 1
        if sha256_file(path) != expected:
            print(f"  REFUSED  {relpath} — sha256 drifted from the manifest (re-bundle)", file=sys.stderr)
            return 1
        path.unlink()
        print(f"  REMOVED  {relpath}")

    print(f"pruned {len(members)} members; git status shows the deletions — commit deliberately")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        default=REPO_ROOT,
        type=Path,
        help=f"repository root (default: {REPO_ROOT})",
    )
    parser.add_argument(
        "--results-dir",
        default=None,
        type=Path,
        help="experiments/results dir (default: <repo-root>/experiments/results)",
    )
    parser.add_argument(
        "--min-age-days",
        default=7.0,
        type=float,
        help="in-flight window: skip files younger than this (default: 7)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the candidate inventory and exit (the default with no --bundle-out)",
    )
    parser.add_argument(
        "--bundle-out",
        default=None,
        type=Path,
        help="write the content-addressed tar + committed manifest into this dir",
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="after bundling, remove bundled members from the working tree (operator-only)",
    )
    args = parser.parse_args()

    results_dir = args.results_dir or args.repo_root / "experiments" / "results"
    now = time.time()
    ref = load_reference_index(results_dir)
    candidates = scan_candidates(
        results_dir, ref, repo_root=args.repo_root, min_age_days=args.min_age_days, now=now
    )

    if args.prune:
        if not args.bundle_out:
            parser.error("--prune requires --bundle-out <dir>")
        return prune_bundled(
            args.bundle_out, ref, repo_root=args.repo_root,
            min_age_days=args.min_age_days, now=now,
        )
    if args.dry_run or not args.bundle_out:
        return print_candidates(candidates, args.min_age_days)
    return write_bundle(candidates, args.bundle_out, args.repo_root)


if __name__ == "__main__":
    raise SystemExit(main())
