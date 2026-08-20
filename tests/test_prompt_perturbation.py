"""Tests for the flash-authored prompt-perturbation path (prompt_perturbation.py)."""

import hashlib

import pytest

import agentic_dynamics.measurement.prompt_perturbation as pp
from agentic_dynamics.measurement.perturb import derive_seed, perturb_prompt


def test_prompt_perturbation_roundtrip():
    a = pp.PromptPerturbation("invert_constraint", 0.5, 2, "Build X", perturbed_prompt="Build Y")
    assert a.sha256 == hashlib.sha256(b"Build Y").hexdigest()
    assert pp.PromptPerturbation.from_dict(a.to_dict()) == a
    b = pp.PromptPerturbation.from_json(a.to_json())
    assert b.id == a.id
    assert b.perturbed_prompt == "Build Y"


def test_id_is_input_derived():
    a = pp.PromptPerturbation("invert_constraint", 0.5, 0, "Build X")
    b = pp.PromptPerturbation("invert_constraint", 0.5, 0, "Build X")
    c = pp.PromptPerturbation("invert_constraint", 0.5, 1, "Build X")
    assert a.id == b.id, "same inputs -> same artifact id"
    assert c.id != a.id, "different variant -> different artifact id"


def test_resolve_deterministic_matches_perturb():
    task = "Build a REST API. The api uses a database server with a cache."
    op = "inject_alien_vocab"
    prompt, sha, prov = pp.resolve_perturbed_prompt(task, op, 0.5, seed_variant=0, mode="deterministic")

    expected, _ = perturb_prompt(task, op, strength=0.5, rng_seed=derive_seed(task, op, 0.5, 0))
    assert prompt == expected
    assert sha == hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    assert prov == "deterministic"


def test_compile_prompt_perturbation_pins_and_caches(tmp_path, monkeypatch):
    calls = []

    def fake_call(prompt, *, model, timeout):
        calls.append(prompt)
        return "MUTATED fake task prompt"

    monkeypatch.setattr(pp, "_call_opencode", fake_call)
    task = "Build a task manager API."

    a1 = pp.compile_prompt_perturbation(task, "invert_constraint", 0.5, seed_variant=0, cache_dir=tmp_path)
    assert a1.perturbed_prompt == "MUTATED fake task prompt"
    assert a1.sha256 == hashlib.sha256(b"MUTATED fake task prompt").hexdigest()
    assert a1.provenance == "flash"
    assert len(calls) == 1

    a2 = pp.compile_prompt_perturbation(task, "invert_constraint", 0.5, seed_variant=0, cache_dir=tmp_path)
    assert a2.perturbed_prompt == "MUTATED fake task prompt"
    assert a2.id == a1.id
    assert len(calls) == 1, "cache hit must not re-author the perturbation"

    a3 = pp.compile_prompt_perturbation(task, "invert_constraint", 0.5, seed_variant=1, cache_dir=tmp_path)
    assert a3.id != a1.id
    assert len(calls) == 2, "a distinct variant must author a new perturbation"


def test_compile_unknown_operator_raises():
    with pytest.raises(ValueError):
        pp.compile_prompt_perturbation("x", "not_an_operator", 0.5)


def test_compile_no_output_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(pp, "_call_opencode", lambda *a, **k: None)
    with pytest.raises(ValueError):
        pp.compile_prompt_perturbation("Build a task manager API.", "invert_constraint", 0.5, cache_dir=tmp_path)


def test_flash_model_is_cheap_default():
    assert pp.FLASH_MODEL.endswith("flash")
