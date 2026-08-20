"""Tests for Flash V4 mutation compiler."""

import tempfile
from pathlib import Path

import pytest

from agentic_dynamics.measurement.mutation import (
    ALL_OPERATORS,
    CODEBASE_OPERATORS,
    SPECIFICATION_OPERATORS,
    MutationArtifact,
    apply_mutation,
    compile_mutation,
)


class TestMutationArtifact:
    def test_creates_with_auto_id(self):
        m = MutationArtifact(
            mutation_id="",
            operator="inject_false_premise",
            operator_class="specification",
            strength=0.5,
            original_spec="Build a REST API.",
            mutated_spec="Build a REST API with false premise.",
        )
        assert m.mutation_id.startswith("mut_")
        assert len(m.hash) == 16

    def test_serialization_roundtrip(self):
        m = MutationArtifact(
            mutation_id="",
            operator="inject_bug",
            operator_class="codebase",
            strength=0.7,
            original_spec="Fix the login bug.",
            codebase_patch="--- a/app.py\n+++ b/app.py\n@@ -1,3 +1,3 @@\n-x=1\n+x=2\n",
        )
        json_str = m.to_json()
        m2 = MutationArtifact.from_json(json_str)
        assert m2.operator == "inject_bug"
        assert m2.strength == 0.7
        assert m2.codebase_patch == m.codebase_patch

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            m = MutationArtifact(
                mutation_id="",
                operator="remove_constraint",
                operator_class="specification",
                strength=0.3,
                original_spec="Add logging.",
                mutated_spec="Add logging (no constraint).",
            )
            m.save(dp / "mut.json")
            m2 = MutationArtifact.load(dp / "mut.json")
            assert m2.operator == m.operator
            assert m2.mutated_spec == m.mutated_spec

    def test_hash_changes_with_content(self):
        m1 = MutationArtifact(
            mutation_id="",
            operator="inject_false_premise",
            operator_class="specification",
            strength=0.5,
            original_spec="Spec A.",
        )
        m2 = MutationArtifact(
            mutation_id="",
            operator="inject_false_premise",
            operator_class="specification",
            strength=0.5,
            original_spec="Spec B.",
        )
        assert m1.hash != m2.hash

    def test_would_produce_changes(self):
        m = MutationArtifact(
            mutation_id="",
            operator="clean",
            operator_class="specification",
            strength=0.0,
            original_spec="Build API.",
        )
        assert not m.would_produce_changes()

        m.mutated_spec = "Build API with twist."
        assert m.would_produce_changes()


class TestCompileMutation:
    def test_raises_on_unknown_operator(self):
        with pytest.raises(ValueError, match="Unknown operator"):
            compile_mutation("Build API.", "not_a_real_operator")

    def test_raises_on_invalid_strength(self):
        with pytest.raises(ValueError, match="Strength must be"):
            compile_mutation("Build API.", "inject_false_premise", strength=1.5)

    def test_raises_on_codebase_without_path(self):
        with pytest.raises(ValueError, match="codebase_path"):
            compile_mutation("Build API.", "inject_bug", codebase_path=None)

    def test_spec_mutation_returns_artifact(self, monkeypatch):
        monkeypatch.setattr(
            "instrument.mutation._call_opencode",
            lambda prompt, *, model, timeout: "Mutated spec.",
        )
        result = compile_mutation(
            "Create a to-do app with user authentication.",
            "remove_constraint",
            strength=0.5,
        )
        assert isinstance(result, MutationArtifact)
        assert result.operator == "remove_constraint"
        assert result.operator_class == "specification"
        assert result.mutated_spec == "Mutated spec."

    def test_cache_writes_and_hits(self, monkeypatch, tmp_path):
        calls = {"n": 0}

        def fake_call(prompt, *, model, timeout):
            calls["n"] += 1
            return "Mutated spec."

        monkeypatch.setattr("instrument.mutation._call_opencode", fake_call)
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        a1 = compile_mutation(
            "Create a to-do app.", "inject_false_premise", strength=0.3, cache_dir=cache_dir
        )
        a2 = compile_mutation(
            "Create a to-do app.", "inject_false_premise", strength=0.3, cache_dir=cache_dir
        )
        assert calls["n"] == 1  # second call hit the cache, no re-compile
        assert a1.mutated_spec == a2.mutated_spec == "Mutated spec."

    def test_raises_on_compiler_failure(self, monkeypatch):
        monkeypatch.setattr(
            "instrument.mutation._call_opencode",
            lambda prompt, *, model, timeout: None,
        )
        with pytest.raises(ValueError, match="compilation failed"):
            compile_mutation("Create a to-do app.", "inject_false_premise", strength=0.3)


class TestApplyMutation:
    def test_spec_mutation_writes_file(self):
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            m = MutationArtifact(
                mutation_id="",
                operator="inject_false_premise",
                operator_class="specification",
                strength=0.7,
                original_spec="Build a login page.",
                mutated_spec="Build a login page (assume OAuth is already configured).",
            )
            apply_mutation(m, dp)
            spec_file = dp / "specification.txt"
            assert spec_file.exists()
            assert "assume OAuth" in spec_file.read_text()

    def test_custom_spec_path(self):
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            m = MutationArtifact(
                mutation_id="",
                operator="remove_constraint",
                operator_class="specification",
                strength=0.5,
                original_spec="Add rate limiting.",
                mutated_spec="Add rate limiting (no constraint).",
            )
            apply_mutation(m, dp, spec_path="prompts/task.txt")
            assert (dp / "prompts" / "task.txt").exists()
            assert "rate limiting" in (dp / "prompts" / "task.txt").read_text()

    def test_noop_when_no_mutated_spec(self):
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            m = MutationArtifact(
                mutation_id="",
                operator="clean",
                operator_class="specification",
                strength=0.0,
                original_spec="Build API.",
            )
            apply_mutation(m, dp)
            assert not (dp / "specification.txt").exists()


class TestOperatorRegistry:
    def test_spec_operators_count(self):
        assert len(SPECIFICATION_OPERATORS) == 10

    def test_codebase_operators_count(self):
        assert len(CODEBASE_OPERATORS) == 10

    def test_all_operators_are_unique(self):
        assert len(ALL_OPERATORS) == 20
        assert len(set(ALL_OPERATORS)) == 20
