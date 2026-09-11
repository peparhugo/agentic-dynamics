"""Schema + evidence-integrity gate for the distilled stack skills (stack_knowledge_seed).

Skips outside the seeding workflow's clone (the skills are produced there and committed); in
the workflow's test phase the files MUST exist and every cited evidence URI MUST resolve to a
record in the frozen corpus.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.fast

_REPO = Path(__file__).resolve().parent.parent
_SKILLS = _REPO / "experiments" / "stack_knowledge" / "skills"
_SOURCES = _REPO / "experiments" / "stack_knowledge" / "sources"
_EXPECTED = {
    "python", "flask", "celery-redis", "sqlite", "redis-streams", "neo4j-cypher",
    "chroma", "docker-compose", "playwright", "firebase-hosting", "web-svg-css", "systemd",
}


def _corpus_uris() -> set[str]:
    uris: set[str] = set()
    for record in _SOURCES.glob("*.json"):
        uris.add(json.loads(record.read_text())["uri"])
    return uris


def test_stack_skills_schema_and_evidence():
    skill_files = sorted(_SKILLS.glob("*.json")) if _SKILLS.is_dir() else []
    if not skill_files:
        pytest.skip("stack skills not distilled in this checkout")
    corpus = _corpus_uris()
    assert len(skill_files) >= 10, f"expected the full subject set, found {len(skill_files)}"
    seen: set[str] = set()
    for path in skill_files:
        skill = json.loads(path.read_text())
        for key in (
            "subject", "claim", "population", "conditions", "support", "uncertainty",
            "source_experiment", "evidence", "notes",
        ):
            assert key in skill, f"{path.name}: missing {key}"
        assert skill["subject"].startswith("skill/stack/"), skill["subject"]
        seen.add(skill["subject"].split("/")[-1])
        assert len(skill["claim"]) >= 80, f"{path.name}: claim too thin"
        assert isinstance(skill["support"], int) and skill["support"] >= 1
        assert 0.0 <= float(skill["uncertainty"]) <= 1.0
        assert skill["evidence"], f"{path.name}: no evidence"
        for ref in skill["evidence"]:
            assert ref.startswith("uri:"), ref
            assert ref[4:] in corpus, f"{path.name}: evidence not in corpus: {ref[4:]}"
        assert skill["notes"].strip(), f"{path.name}: no notes"
    missing = _EXPECTED - seen
    assert not missing, f"missing subjects: {sorted(missing)}"
