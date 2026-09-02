"""Agent-config rendering tests (refactor-repair P0-1).

Replaces the former byte-equality drift guard. The old guard asserted ``agent_config/`` is copied
verbatim into both ``.opencode/`` and ``.claude/`` — which guaranteed text drift would be caught
but left schema drift undetected: the two platforms do not share frontmatter schemas (opencode
agents use ``mode``/``model``/``permission``; Claude agents use ``name``/``description`` and hold
permissions at the project level) and index positional command args differently (opencode 1-indexed,
Claude 0-indexed). A byte-equal copy emits invalid Claude config while the test stayed green.

The new guard asserts instead:

1. **Per-target schema validity** — ``validate_root()``/``validate_opencode()``/``validate_claude()``
   return no problems, including the explicit rejection of opencode-only keys
   (``mode``/``permission``/``temperature``/``hidden`` on agents; ``agent``/``subtask`` on commands)
   in the Claude output.
2. **Meaning equivalence where platforms permit** — descriptions and body prose are preserved
   across the renderings (only the schema projection and argument-index renumbering differ).
3. **Committed files match the renderers** — every surface is regenerated from the semantic
   source, never hand-edited.

``control_db_publication`` p5 added the ROOT surface to all three concerns. ``AGENTS.md`` and
``CLAUDE.md`` are now renderer outputs, so the tests below cover them exactly as they cover the
platform trees, plus the two properties that are specific to the root:

* the root document's body IS ``agent_config/rules.md`` byte for byte, and the rules reach each
  platform through that root document ONLY (no duplicate ``rules.md`` under ``.claude/rules/``,
  which Claude Code would load a second time beside ``CLAUDE.md``'s ``@AGENTS.md`` import) — the
  drift that motivated the change was a root file telling the agent to use a corpus the neutral
  source had already retired;
* ``--check`` fails on a stale surface and passes on a fresh one. Both directions are asserted,
  because a gate that never fails is indistinguishable from no gate at all.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from scripts import _gen_instructions as gen

pytestmark = pytest.mark.fast

ROOT = Path(__file__).resolve().parent.parent


def _render_opencode() -> dict[str, str]:
    return gen.render_opencode()


def _render_claude() -> dict[str, str]:
    return gen.render_claude()


def _body(content: str) -> str:
    """The document body (frontmatter stripped)."""
    _, body = gen._split_frontmatter(content)
    return body


def _description(fields: list[str]) -> str | None:
    return gen._scalar(fields, "description")


def _reindex_up(body: str) -> str:
    """Reverse the renderer's 1→0 arg reindex (Claude ``$N`` → opencode ``$N+1``)."""
    return re.sub(r"\$([0-9]+)", lambda m: "$" + str(int(m.group(1)) + 1), body)


# --- 1. per-target schema validity -------------------------------------------


def test_opencode_rendering_is_schema_valid():
    """The opencode rendering satisfies the opencode schema (required fields present)."""
    assert gen.validate_opencode(_render_opencode()) == []


def test_claude_rendering_is_schema_valid():
    """The Claude rendering satisfies the Claude schema (required fields present)."""
    assert gen.validate_claude(_render_claude()) == []


def test_claude_agents_reject_opencode_only_keys():
    """No opencode-only frontmatter key survives into a Claude agent (explicit check)."""
    for path, content in _render_claude().items():
        if not path.startswith(".claude/agents/"):
            continue
        fields, _ = gen._split_frontmatter(content)
        for key in ("mode", "permission", "temperature", "hidden"):
            assert not gen._has_top_level_key(fields, key), (
                f"{path}: opencode-only key {key!r} present in Claude agent"
            )
        model = gen._scalar(fields, "model")
        assert model is None or "/" not in model, (
            f"{path}: provider/model id {model!r} leaked into Claude agent"
        )


def test_claude_commands_reject_opencode_only_keys():
    """No opencode-only command frontmatter key survives into a Claude command."""
    for path, content in _render_claude().items():
        if not path.startswith(".claude/commands/"):
            continue
        fields, _ = gen._split_frontmatter(content)
        for key in ("agent", "subtask"):
            assert not gen._has_top_level_key(fields, key), (
                f"{path}: opencode-only key {key!r} present in Claude command"
            )


# --- 2. meaning equivalence where platforms permit ---------------------------


def test_rules_are_identical_across_surfaces():
    """Instruction docs are schema-free — the two surfaces carry byte-identical content."""
    oc = _render_opencode()
    cl = _render_claude()
    for name in gen.INSTRUCTIONS:
        assert oc[f".opencode/instructions/{name}"] == cl[f".claude/rules/{name}"], name


def test_skills_are_identical_across_surfaces():
    """Skills share a name/description schema — the two surfaces are byte-identical."""
    oc = _render_opencode()
    cl = _render_claude()
    for name in gen.SKILLS:
        assert (
            oc[f".opencode/skills/{name}/SKILL.md"] == cl[f".claude/skills/{name}/SKILL.md"]
        ), name


def test_agent_bodies_and_descriptions_are_equivalent():
    """Agents differ only in frontmatter projection; the prose and description are preserved."""
    oc = _render_opencode()
    cl = _render_claude()
    for name in gen.AGENTS:
        oc_fields, oc_body = gen._split_frontmatter(oc[f".opencode/agents/{name}.md"])
        cl_fields, cl_body = gen._split_frontmatter(cl[f".claude/agents/{name}.md"])
        assert oc_body == cl_body, f"{name}: agent body diverged between surfaces"
        assert _description(oc_fields) == _description(cl_fields), (
            f"{name}: agent description diverged between surfaces"
        )
        # The Claude name is the filename (derived), satisfying its required `name` field.
        assert gen._scalar(cl_fields, "name") == name, f"{name}: Claude agent name mismatch"


def test_command_descriptions_and_bodies_are_equivalent():
    """Commands differ only in arg renumbering; descriptions and prose are preserved."""
    oc = _render_opencode()
    cl = _render_claude()
    for name in gen.COMMANDS:
        oc_fields, oc_body = gen._split_frontmatter(oc[f".opencode/commands/{name}.md"])
        cl_fields, cl_body = gen._split_frontmatter(cl[f".claude/commands/{name}.md"])
        assert _description(oc_fields) == _description(cl_fields), (
            f"{name}: command description diverged between surfaces"
        )
        # Reversing the renderer's 1→0 reindex must recover the opencode body byte-for-byte.
        assert _reindex_up(cl_body) == oc_body, (
            f"{name}: command body diverged beyond positional-arg reindexing"
        )


# --- 3. the root surface (control_db_publication p5) --------------------------


def _render_root() -> dict[str, str]:
    return gen.render_root()


def test_root_rendering_is_schema_valid():
    """The root rendering satisfies the root-document contract (status + banner + import)."""
    assert gen.validate_root(_render_root()) == []


def test_root_documents_are_generated_for_every_declared_source():
    """Every entry in ``ROOT_SOURCES`` renders, and nothing else claims to be a root surface."""
    rendered = _render_root()
    assert set(rendered) == set(gen.ROOT_SOURCES), (
        "the root rendering does not match ROOT_SOURCES"
    )


def test_root_documents_declare_themselves_generated():
    """Each root document names its source and warns that a hand-edit is overwritten.

    The root files sit next to hand-authored documents, so — unlike the platform trees, whose
    directories are documented as generated — they must say so on their own face or the next
    editor will reasonably assume they are the source.
    """
    for target, source in gen.ROOT_SOURCES.items():
        content = _render_root()[target]
        assert f"agent_config/{source}" in content, f"{target}: does not name its source"
        assert "a hand-edit is overwritten" in content, f"{target}: no hand-edit warning"


def test_agents_md_body_is_exactly_the_neutral_rules_source():
    """AGENTS.md's body is ``agent_config/rules.md``, byte for byte.

    This is the assertion the p5 change exists for. The root file previously held a hand-copied,
    months-stale variant of the rules — it still pointed research at a retired corpus that
    ``agent_config/rules.md`` had already corrected. Comparing bodies (frontmatter and banner
    stripped) makes that class of drift impossible: there is one rules text, and the root document
    is a rendering of it rather than a copy maintained beside it.
    """
    agents_body = _body(_render_root()["AGENTS.md"])
    # Strip the generated banner line the root renderer prepends; the remainder is the source.
    rules_text = agents_body.split("-->", 1)[1].lstrip("\n")
    assert rules_text == (ROOT / "agent_config" / "rules.md").read_text(encoding="utf-8")


def test_the_rules_text_is_loaded_exactly_once_per_platform():
    """No platform's default context carries the rules twice.

    Claude Code loads BOTH ``CLAUDE.md`` (which imports ``@AGENTS.md``) and every unscoped
    ``.claude/rules/*.md``. Rendering ``rules.md`` into that directory as well would put the same
    ~9 KB of text into every session's context twice — the opposite of the slimming this phase is
    for. So ``rules.md`` reaches each platform through its ROOT document only.
    """
    assert "rules.md" not in gen.INSTRUCTIONS
    rendered = gen.render_all()
    assert ".claude/rules/rules.md" not in rendered
    assert ".opencode/instructions/rules.md" not in rendered
    # …and the rules must still actually arrive, via the root documents.
    assert "**THE LOAD-BEARING RULE:**" in rendered["AGENTS.md"]


def test_claude_md_imports_agents_md_rather_than_copying_it():
    """CLAUDE.md carries the ``@AGENTS.md`` import and NOT a second copy of the rules body."""
    claude_md = _render_root()["CLAUDE.md"]
    assert "@AGENTS.md" in claude_md
    # A telltale line from the rules text: if it appears here, the rules were copied, not imported.
    assert "**THE LOAD-BEARING RULE:**" not in claude_md


def test_default_context_excludes_the_point_in_time_snapshot():
    """The L0 game board is not rendered into the always-on instruction surfaces.

    ``system_snapshot.md`` is a dump of run state, branch ownership, spec-lifecycle counts and
    deployment history. Rendering it into the unconditional context meant every session opened on
    state that was stale before the first token — and an actor acts on stale state. It is served
    on demand by ``agentic-dynamics control status --json`` instead. The file itself is still
    generated for the controller's permanence decision; only the always-on rendering is gone.
    """
    assert "system_snapshot.md" not in gen.INSTRUCTIONS
    rendered = gen.render_all()
    assert not [rel for rel in rendered if rel.endswith("system_snapshot.md")]
    for stale in (".opencode/instructions/system_snapshot.md", ".claude/rules/system_snapshot.md"):
        assert not (ROOT / stale).exists(), f"{stale}: the retired render is still committed"
    # The board itself must still exist — this test is about context injection, not deletion.
    assert (ROOT / "agent_config" / "system_snapshot.md").exists()


def test_instruction_surfaces_route_to_the_control_packet_for_dynamic_state():
    """Having removed the snapshot, the surfaces must say where current state comes from."""
    rules = gen.render_all()["AGENTS.md"]
    assert "agentic-dynamics control status --json" in rules
    assert "control-status/v1" in rules


def test_every_renderer_reads_only_agent_config_and_uses_all_of_it():
    """One source tree, three renderers, no unused source and no source outside it.

    Both halves matter. A declared source that does not exist fails the render outright; a source
    file that NO renderer reads is the quieter bug — it looks authoritative, someone edits it, and
    nothing happens. ``system_snapshot.md`` is the deliberate exception and is named as such: it is
    generated INTO ``agent_config/`` by ``scripts/system_snapshot.py`` for on-demand reading, not
    rendered OUT of it into any session's context.
    """
    declared = (
        set(gen.ROOT_SOURCES.values())
        | set(gen.INSTRUCTIONS)
        | {f"skills/{name}.md" for name in gen.SKILLS}
        | {f"agents/{name}.md" for name in gen.AGENTS}
        | {f"commands/{name}.md" for name in gen.COMMANDS}
    )
    agent_config = ROOT / "agent_config"

    missing = [rel for rel in sorted(declared) if not (agent_config / rel).is_file()]
    assert not missing, f"declared sources that do not exist: {missing}"

    on_disk = {
        str(path.relative_to(agent_config))
        for path in agent_config.rglob("*.md")
        if path.is_file()
    }
    unused = sorted(on_disk - declared - {"system_snapshot.md"})
    assert not unused, (
        "agent_config files no renderer reads (they look authoritative but reach nobody): "
        f"{unused}"
    )


# --- 4. committed files match the renderers (drift guard) ---------------------


def test_committed_surfaces_match_renderers():
    """Every committed surface file matches its renderer (regenerate on failure).

    Covers stale, missing AND orphan files in one assertion, via the same
    :func:`~scripts._gen_instructions.find_drift` the ``--check`` CI gate calls — so the test and
    the gate can never disagree about what drift is.
    """
    drift = gen.find_drift()
    assert not drift, (
        "generated surfaces drifted — regenerate with "
        "`python3 scripts/_gen_instructions.py`:\n" + "\n".join(drift)
    )


def test_generated_trees_are_declared():
    """Every generated tree in ``GENERATED_TREES`` exists (a typo would silently skip orphans)."""
    missing = [tree for tree in gen.GENERATED_TREES if not (ROOT / tree).is_dir()]
    assert not missing, f"GENERATED_TREES names directories that do not exist: {missing}"


# --- 5. the --check gate, in both directions ---------------------------------
#
# A gate is only worth having if it fails. These tests build a throwaway copy of the source tree,
# render it, and then verify that --check passes on the fresh tree and fails on each way a tree
# can drift: stale, missing, orphan. Everything runs against the temporary root (``gen.ROOT`` and
# ``gen.AGENT_CONFIG`` are monkeypatched), so no test can write into the checkout.


@pytest.fixture()
def rendered_tree(tmp_path, monkeypatch):
    """A temporary repo root holding a freshly rendered copy of every surface."""
    shutil.copytree(ROOT / "agent_config", tmp_path / "agent_config")
    monkeypatch.setattr(gen, "ROOT", tmp_path)
    monkeypatch.setattr(gen, "AGENT_CONFIG", tmp_path / "agent_config")
    written, pruned = gen.write_surfaces()
    assert written and not pruned, "a freshly rendered tree cannot have orphans"
    return tmp_path


def test_check_passes_on_a_freshly_rendered_tree(rendered_tree, capsys):
    """The fresh direction: nothing changed since generation, so --check exits 0."""
    assert gen.main(["--check"]) == 0
    assert "surfaces OK" in capsys.readouterr().out


def test_check_fails_when_a_source_changes_without_regenerating(rendered_tree, capsys):
    """The stale direction: touch a source, do not regenerate, and --check must exit nonzero.

    This is the exact scenario the CI gate exists for — and the exact scenario that went undetected
    for months while the root ``AGENTS.md`` was hand-maintained.
    """
    source = rendered_tree / "agent_config" / "rules.md"
    source.write_text(source.read_text(encoding="utf-8") + "\nA NEW RULE.\n", encoding="utf-8")

    assert gen.main(["--check"]) == 1
    out = capsys.readouterr().out
    assert "SURFACE DRIFT" in out
    # rules.md renders to exactly one surface — the root document both platforms read.
    assert "stale:   AGENTS.md" in out, f"AGENTS.md not reported as stale:\n{out}"


def test_check_fails_when_a_generated_file_is_missing(rendered_tree, capsys):
    """The missing direction: a deleted surface is drift, not an absence to shrug at."""
    (rendered_tree / "AGENTS.md").unlink()

    assert gen.main(["--check"]) == 1
    assert "missing: AGENTS.md" in capsys.readouterr().out


def test_check_fails_on_an_orphan_in_a_generated_tree(rendered_tree, capsys):
    """The orphan direction: a file no renderer emits (hand-added, or a removed source's leftover)."""
    orphan = rendered_tree / ".claude" / "rules" / "system_snapshot.md"
    orphan.write_text("a stale render nothing produces any more\n", encoding="utf-8")

    assert gen.main(["--check"]) == 1
    assert "orphan:  .claude/rules/system_snapshot.md" in capsys.readouterr().out


def test_check_never_writes(rendered_tree):
    """--check is safe on a dirty tree: it reports drift and leaves every byte alone."""
    source = rendered_tree / "agent_config" / "rules.md"
    source.write_text("# replaced\n", encoding="utf-8")
    before = {
        path: path.read_bytes()
        for path in sorted(rendered_tree.rglob("*"))
        if path.is_file()
    }

    assert gen.main(["--check"]) == 1

    after = {
        path: path.read_bytes()
        for path in sorted(rendered_tree.rglob("*"))
        if path.is_file()
    }
    assert before == after, "--check modified the tree"


def test_regenerating_prunes_a_retired_render(rendered_tree):
    """Removing a source's render is what ``write_surfaces`` prunes — the p5 case, mechanically.

    Without pruning the generator is not idempotent when a source goes away: the stale render
    survives, still loaded by every session, with --check permanently red and no command to fix it.
    """
    orphan = rendered_tree / ".opencode" / "instructions" / "system_snapshot.md"
    orphan.write_text("retired render\n", encoding="utf-8")

    _written, pruned = gen.write_surfaces()

    assert pruned == [".opencode/instructions/system_snapshot.md"]
    assert not orphan.exists()
    assert gen.find_drift() == []
