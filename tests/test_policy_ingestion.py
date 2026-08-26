"""Tests for policy ingestion (policy_ingestion).

Covers the extractor contract constants, one-record-per-policy-file derivation, the
``Authority.POLICY`` / ``source_type=policy`` / ``[P]`` provenance, the first-meaningful-block
text (comment/frontmatter skipping, truncation — never the whole file), the injected revision,
the reused artifact/event round-trip, and policy-surface discovery.
"""

import hashlib
import tempfile
from pathlib import Path

from agentic_dynamics.knowledge import policy_ingestion as pi
from agentic_dynamics.knowledge.knowledge import Authority, compute_knowledge_id
from agentic_dynamics.knowledge.knowledge_ingestion import (
    extract_record,
    record_to_artifact,
    record_to_event,
)

REPO = "test-repo"
REVISION = "abc1234"


def _write_policy_surface(root: Path) -> Path:
    """Write the canonical policy surface into a temp repo root."""
    (root / "AGENTS.md").write_text(
        "# Rules for this project\n\nSome rule body.\n\nMore rules.\n"
    )
    (root / "experiments" / "definitions").mkdir(parents=True, exist_ok=True)
    (root / "experiments" / "definitions" / "foo.yaml").write_text(
        "name: foo\nquestion: >-\n  What does foo measure?\n"
    )
    (root / "conventions").mkdir(parents=True, exist_ok=True)
    (root / "conventions" / "python.yaml").write_text(
        "# Python convention rules\n# Used by commit_analysis.py\n\nlanguage: python\n\nnaming_patterns:\n  - name: x\n"
    )
    (root / ".opencode" / "instructions").mkdir(parents=True, exist_ok=True)
    (root / ".opencode" / "instructions" / "mental-model.md").write_text(
        "# File map, signatures, and dependencies.\n\nThis repo is an information-acquisition machine.\n"
    )
    return root


def test_extractor_constants():
    assert pi.EXTRACTOR_VERSION == "policy/v1"
    assert pi.SOURCE_TYPE == "policy"
    assert pi.ACL_SCOPE == "public"


# ── One record per policy file ──────────────────────────────────


def test_one_record_per_policy_file():
    with tempfile.TemporaryDirectory() as d:
        root = _write_policy_surface(Path(d))
        paths = pi.discover_policy_paths(root)
        records = pi.derive_policy_records(paths, repository_id=REPO, revision=REVISION, repo_root=root)
    assert len(records) == len(paths) == 4
    assert all(rec.source_type == "policy" for rec in records)
    assert all(rec.authority is Authority.POLICY for rec in records)
    assert all(rec.evidence_class == "[P]" for rec in records)


def test_record_metadata():
    with tempfile.TemporaryDirectory() as d:
        root = _write_policy_surface(Path(d))
        records = pi.derive_policy_records(
            [root / "AGENTS.md"], repository_id=REPO, revision=REVISION, repo_root=root
        )
    rec = records[0]
    assert rec.authority is Authority.POLICY
    assert rec.source_type == "policy"
    assert rec.evidence_class == "[P]"
    assert rec.commit_sha == REVISION
    assert rec.language == ""
    assert rec.symbols == []


# ── First-meaningful-block text ─────────────────────────────────


def test_text_is_first_meaningful_block_not_whole_file():
    # A title, blank line, then a long body: the block is just the title (blank ends it).
    block = pi._first_meaningful_block("# Rules for this project\n\n" + ("line\n" * 5000))
    assert block == "# Rules for this project"


def test_yaml_comment_header_skipped():
    # Leading `#` comment lines are skipped; content starts at the first non-comment line.
    block = pi._first_meaningful_block("# comment one\n# comment two\n\nlanguage: python\n\nx: 1\n", yaml_like=True)
    assert block == "language: python"


def test_frontmatter_skipped():
    text = "---\ntitle: frontmatter\ntags: [a]\n---\n\n# Real content\n"
    block = pi._first_meaningful_block(text)
    assert block == "# Real content"


def test_markdown_heading_not_skipped():
    # In markdown, `#` is a heading (meaningful), not a comment.
    block = pi._first_meaningful_block("# Heading\n", yaml_like=False)
    assert block == "# Heading"


def test_truncation_to_max_chars():
    block = pi._first_meaningful_block("x" * 5000, max_chars=10)
    assert block == "xxxxxxxxxx…"
    assert len(block) <= 11


# ── Graceful skip of missing / unreadable paths ─────────────────


def test_missing_files_skipped():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "real.md").write_text("# real\n")
        records = pi.derive_policy_records(
            [root / "real.md", root / "missing.md"], repository_id=REPO, revision=REVISION
        )
    assert len(records) == 1
    assert records[0].logical_locator == str(root / "real.md")


# ── Identity / provenance ───────────────────────────────────────


def test_revision_folds_into_knowledge_id():
    with tempfile.TemporaryDirectory() as d:
        root = _write_policy_surface(Path(d))
        records = pi.derive_policy_records(
            [root / "AGENTS.md"], repository_id=REPO, revision=REVISION, repo_root=root
        )
    rec = records[0]
    assert rec.commit_sha == REVISION
    assert compute_knowledge_id(rec.entity_id, REVISION, rec.content_hash, pi.EXTRACTOR_VERSION) == rec.knowledge_id


def test_logical_locator_relative_to_repo_root():
    with tempfile.TemporaryDirectory() as d:
        root = _write_policy_surface(Path(d))
        records = pi.derive_policy_records(
            [root / "experiments" / "definitions" / "foo.yaml"], repository_id=REPO, revision=REVISION, repo_root=root
        )
    assert records[0].logical_locator == "experiments/definitions/foo.yaml"


def test_distinct_entities_per_file():
    with tempfile.TemporaryDirectory() as d:
        root = _write_policy_surface(Path(d))
        records = pi.derive_policy_records(
            pi.discover_policy_paths(root), repository_id=REPO, revision=REVISION, repo_root=root
        )
    assert len({rec.entity_id for rec in records}) == len(records)


# ── Reused artifact/event round-trip ────────────────────────────


def test_artifact_round_trip_preserves_policy_record():
    with tempfile.TemporaryDirectory() as d:
        root = _write_policy_surface(Path(d))
        records = pi.derive_policy_records(
            [root / "AGENTS.md"], repository_id=REPO, revision=REVISION, repo_root=root
        )
    rec = records[0]
    artifact = record_to_artifact(rec)
    event = record_to_event(rec)

    assert rec.content_hash == hashlib.sha256(artifact).hexdigest()
    assert event.content_hash == rec.content_hash

    extracted = extract_record(event, artifact)
    assert extracted.source_type == "policy"
    assert extracted.authority is Authority.POLICY
    assert extracted.evidence_class == "[P]"
    assert extracted.logical_locator == "AGENTS.md"
    assert extracted.text == rec.text
    assert extracted.knowledge_id == rec.knowledge_id
    assert extracted.content_hash == rec.content_hash


# ── Policy-surface discovery ────────────────────────────────────


def test_discover_policy_paths_returns_existing_surface():
    with tempfile.TemporaryDirectory() as d:
        root = _write_policy_surface(Path(d))
        paths = pi.discover_policy_paths(root)
    rel = sorted(str(p.relative_to(root)) for p in paths)
    assert rel == [
        ".opencode/instructions/mental-model.md",
        "AGENTS.md",
        "conventions/python.yaml",
        "experiments/definitions/foo.yaml",
    ]


def test_discover_policy_paths_empty_when_no_files():
    with tempfile.TemporaryDirectory() as d:
        assert pi.discover_policy_paths(Path(d)) == []


# ── Determinism ─────────────────────────────────────────────────


def test_deterministic_across_timestamps():
    from datetime import datetime, timezone

    with tempfile.TemporaryDirectory() as d:
        root = _write_policy_surface(Path(d))
        a = pi.derive_policy_records(pi.discover_policy_paths(root), repository_id=REPO, revision=REVISION, repo_root=root,
                                     now=datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc))
        b = pi.derive_policy_records(pi.discover_policy_paths(root), repository_id=REPO, revision=REVISION, repo_root=root,
                                     now=datetime(2026, 8, 16, 9, 30, 0, tzinfo=timezone.utc))
    assert [r.knowledge_id for r in a] == [r.knowledge_id for r in b]
    assert [r.content_hash for r in a] == [r.content_hash for r in b]
