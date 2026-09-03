"""Generate every instruction surface — root, `.opencode/`, `.claude/` — from `agent_config/`.

Critique rec 6 / refactor-repair P0-1: `.opencode/` and `.claude/` must not both be manually
authoritative, and — crucially — they must not be byte-identical copies of one another. The two
platforms do NOT share a schema: opencode agents use `mode`/`model`/`permission` frontmatter,
Claude Code agents use `name`/`description` (plus a disjoint optional set) and hold per-capability
permissions at the project level (`.claude/settings.json`), not per-agent; and opencode positional
command args are 1-indexed (`$1` = first) while Claude Code's are 0-indexed (`$0` = first). A
verbatim copy emits invalid Claude configuration even while a byte-equality test stays green.

``control_db_publication`` p5 closes the last hole in that argument. The two *platform* trees were
generated, but the two *root* surfaces an agent actually loads first — `AGENTS.md` (opencode's root
instructions, `opencode.json` → `instructions`) and `CLAUDE.md` (Claude Code's project
instructions) — were still hand-authored copies of the same rules. They drifted exactly as a
hand-copy always does: at the time this renderer was written, the root `AGENTS.md` still told the
agent to ground research in `_results_summary.json`, a corpus retired months earlier and already
corrected in `agent_config/rules.md`. Nothing detected it, because no guard covered the root file.

This module is therefore the single writer for ALL of them. It reads the hand-edited NEUTRAL source
`agent_config/` and renders each target's REAL format through three independent renderers:

* ``render_root()`` — the two root documents. `AGENTS.md` is `agent_config/rules.md` plus lifecycle
  frontmatter and a generated banner; `CLAUDE.md` is the platform's `@AGENTS.md` import (Claude-only
  syntax — opencode has no import directive, which is why the renderer, not the source, emits it)
  followed by `agent_config/claude-code.md`, the Claude-port addendum.
* ``render_opencode()`` — opencode format (neutral agent frontmatter is already opencode-shaped:
  ``description``/``mode``/``model``/``permission``; commands keep ``agent``/``subtask``; positional
  args stay 1-indexed).
* ``render_claude()`` — Claude Code format (agents keep only ``name``/``description``; commands keep
  only ``description``; positional args are re-indexed to 0-based).

``validate_root()`` / ``validate_opencode()`` / ``validate_claude()`` assert each rendering against
a per-target schema (required fields present, opencode-only keys rejected in the Claude output), and
``tests/test_agent_config_render.py`` replaces the old byte-equality drift guard with
meaning-equivalence + schema-validity checks.

``--check`` re-renders everything IN MEMORY and exits nonzero on any difference from the committed
tree — stale file, missing file, or orphan file. That is the CI gate (`.github/workflows/pytest.yml`
→ the ``surfaces`` job): a source edited without regenerating is a red build, not a silent drift.
The mode never writes, so it is safe to run against a dirty checkout.

Deterministic by construction: no timestamps, no ordering, no environment dependence.

**Deferred — the neutral-intent schema (semantic-integrity review P1/P2):** the canonical source
is still predominantly OpenCode-shaped; the Claude renderer strips fields and the tests compare
prose, not effective model/tool/permission behavior, so an omission can silently change an
agent's actual capabilities. The deferred correction is a neutral intent schema (``role``,
``capabilities``: read_repository/execute_tests/edit_code:confirm/spawn_subagents, ``model_class``)
with each renderer mapping intent to its platform and *refusing* generation when an important
capability cannot be represented. Sequenced after the lab contract and the context guards
(release phases s2/s5/s6 — now complete) because it re-touches this module's renderers. Pointer:
``docs/review/semantic_integrity_review.md`` § "P1/P2 — The agent configuration is target-specific
but not yet semantically neutral".
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENT_CONFIG = ROOT / "agent_config"

#: Instruction documents (plain markdown, no frontmatter) mapped to both platform surfaces.
#:
#: These load UNCONDITIONALLY — they are the default master context every session pays for on its
#: first token. Only STABLE content belongs here: architecture, the authority rules, the command
#: surface, and how to obtain dynamic state. ``system_snapshot.md`` (the L0 game board) was removed
#: from this tuple by ``control_db_publication`` p5: it is a point-in-time dump of run state,
#: worktree ownership, spec-lifecycle counts and deployment history, so rendering it into the
#: always-on context meant every session started from a snapshot that was stale the moment it was
#: written — and stale run state is worse than no run state, because an actor acts on it. That
#: state now has ONE authoritative reader: ``agentic-dynamics control status --json``
#: (``control-status/v1``). The board itself is still generated to ``agent_config/system_snapshot.md``
#: by ``scripts/system_snapshot.py`` for the controller's permanence decision; it is simply no
#: longer injected into every prompt.
#:
#: ``rules.md`` is absent for a different reason: it is the ROOT document's source (see
#: :data:`ROOT_SOURCES`). Rendering it here as well would put the SAME text in a session's context
#: twice on Claude Code — once via ``CLAUDE.md``'s ``@AGENTS.md`` import and again as an unscoped
#: ``.claude/rules/`` file, both of which load unconditionally. One copy of the rules, loaded once,
#: through the root document each platform already reads.
INSTRUCTIONS = ("mental-model.md", "conventions.md")

#: The root instruction documents, mapped to the ``agent_config/`` source each is rendered from.
#:
#: ``AGENTS.md`` is opencode's root instruction file (``opencode.json`` → ``instructions``) and
#: ``CLAUDE.md`` is Claude Code's. Both are OUTPUTS: hand-editing either one is overwritten by the
#: next generation and reported by ``--check`` in the meantime.
ROOT_SOURCES: dict[str, str] = {
    "AGENTS.md": "rules.md",
    "CLAUDE.md": "claude-code.md",
}

#: Lifecycle frontmatter required on every root markdown document by ``tests/test_doc_lifecycle.py``
#: (the rec-4 status vocabulary). The renderer emits it rather than carrying it in the neutral
#: source, because it is a property of the *published document*, not of the shared rules text.
ROOT_STATUS = "accepted"

#: The banner every generated root document opens with (after its frontmatter). Rendered surfaces
#: under ``.opencode/``/``.claude/`` live in directories whose generated-ness is documented; the
#: root files sit next to hand-authored docs, so they say it on their own face.
ROOT_BANNER = (
    "<!-- GENERATED by scripts/_gen_instructions.py from agent_config/{source} "
    "— a hand-edit is overwritten. Edit the source, then run "
    "`python3 scripts/_gen_instructions.py`. -->"
)

#: The seven skills (name/description frontmatter — the schema is SHARED by both platforms).
SKILLS = ("analyze", "control-room", "instrument", "lab-books", "queue", "review", "run-workflow")

#: The agent definitions (schema DIVERGES between platforms — see the renderers).
#: ``aio-control`` — the AIO Control Agent (Wave-3 a4) — is the controller's delegated
#: hands and, unlike the three domain subagents, is a PRIMARY opencode agent (the human
#: operator's proxy session, per ``agent_config/rules.md``'s vocabulary section).
AGENTS = ("aio-control", "data-analysis", "instrument-dev", "pipeline-ops")

#: The command definitions (schema + positional-arg indexing diverge — see the renderers).
COMMANDS = ("analyze", "lab", "new-exp", "pipeline", "run-exp")

# --- per-target schema (verified field tables — docs/claude_code_port.md §2) ---

#: OpenCode-only agent frontmatter keys. None of these has a Claude subagent-frontmatter
#: equivalent, so a byte-copy leaks them into Claude output as unknown fields.
OPENCODE_ONLY_AGENT_KEYS = frozenset({"mode", "permission", "temperature", "hidden"})

#: OpenCode-only command frontmatter keys (``agent`` names an opencode primary mode; ``subtask``
#: requests subagent execution — neither has a Claude Code equivalent).
OPENCODE_ONLY_COMMAND_KEYS = frozenset({"agent", "subtask"})

#: Claude Code subagent frontmatter field set (required: ``name``, ``description``).
CLAUDE_AGENT_KEYS = frozenset(
    {
        "name",
        "description",
        "tools",
        "disallowedTools",
        "model",
        "permissionMode",
        "maxTurns",
        "skills",
        "mcpServers",
        "hooks",
        "memory",
        "background",
        "effort",
        "isolation",
        "color",
        "initialPrompt",
    }
)

#: Claude Code command frontmatter shares the SKILL field set except ``name`` and ``paths``.
CLAUDE_COMMAND_KEYS = frozenset(
    {
        "description",
        "when_to_use",
        "argument-hint",
        "arguments",
        "disable-model-invocation",
        "user-invocable",
        "allowed-tools",
        "model",
        "effort",
        "context",
        "background",
        "hooks",
        "shell",
    }
)

#: Matches a positional-arg token ``$N`` (``$1``, ``$2``, …) but not ``$ARGUMENTS`` (no digits).
_POSITIONAL_ARG = re.compile(r"\$([1-9][0-9]*)")


# --- frontmatter helpers -----------------------------------------------------


def _split_frontmatter(text: str) -> tuple[list[str], str]:
    """Split a ``---\\n<fields>\\n---\\n<body>`` document into ``(field_lines, body)``.

    ``body`` is the exact bytes after the closing ``---`` line (leading blank line included),
    so a reconstruction ``f"---\\n{...}\\n---\\n{body}"`` reproduces the document losslessly.
    Returns ``([], text)`` when there is no frontmatter (plain-markdown rules files).
    """
    if not text.startswith("---\n"):
        return [], text
    lines = text.splitlines(keepends=True)
    end = None
    for i in range(1, len(lines)):
        if lines[i].rstrip("\n") == "---":
            end = i
            break
    if end is None:
        raise ValueError("unterminated frontmatter block")
    fields = [line.rstrip("\n") for line in lines[1:end]]
    body = "".join(lines[end + 1 :])
    return fields, body


def _scalar(fields: list[str], key: str) -> str | None:
    """Return a top-level scalar frontmatter field's value (``key: value``), else ``None``."""
    prefix = f"{key}:"
    for line in fields:
        if line == prefix:
            return ""
        if line.startswith(prefix + " ") and not line.startswith(" "):
            return line[len(prefix) + 1 :]
    return None


def _has_top_level_key(fields: list[str], key: str) -> bool:
    """True when ``key`` appears as a top-level frontmatter field (incl. nested ``key:`` blocks)."""
    prefix = f"{key}:"
    return any(line == prefix or line.startswith(prefix + " ") for line in fields)


# --- source readers ----------------------------------------------------------


def _read(rel: str) -> str:
    """Read an ``agent_config/`` file verbatim (bytes are the semantic source)."""
    return (AGENT_CONFIG / rel).read_text(encoding="utf-8")


def _read_frontmatter(rel: str) -> tuple[list[str], str]:
    return _split_frontmatter(_read(rel))


# --- renderers ---------------------------------------------------------------


def _render_root_document(target: str, source: str, body: str) -> str:
    """Render one root document: lifecycle frontmatter, generated banner, then the body.

    ``CLAUDE.md`` additionally opens its body with Claude Code's ``@AGENTS.md`` import directive.
    That line is emitted HERE rather than stored in ``agent_config/claude-code.md`` for the same
    reason the Claude agent renderer drops ``mode``/``permission``: it is platform syntax, and the
    neutral source must stay free of any one platform's dialect. opencode has no ``@`` import — its
    root file is listed in ``opencode.json`` instead — so the directive would be noise (or worse, a
    literal ``@AGENTS.md`` line) if it lived in the shared source.
    """
    banner = ROOT_BANNER.format(source=source)
    prologue = ""
    if target == "CLAUDE.md":
        # Claude Code resolves `@path` as an import: CLAUDE.md pulls in the SAME rules AGENTS.md
        # publishes, so the two roots can never disagree — there is only one copy of the text.
        prologue = "@AGENTS.md\n\n"
    return f"---\nstatus: {ROOT_STATUS}\n---\n{banner}\n\n{prologue}{body}"


def render_root() -> dict[str, str]:
    """Render the root instruction surface as ``{repo-relative path: content}``.

    Two documents, one shared source of rules. ``AGENTS.md`` carries the rules verbatim;
    ``CLAUDE.md`` imports them and appends only what is genuinely Claude-specific (the port notes:
    which fields cross the taxonomy and which do not).
    """
    return {
        target: _render_root_document(target, source, _read(source))
        for target, source in ROOT_SOURCES.items()
    }


def render_opencode() -> dict[str, str]:
    """Render the opencode surface as ``{repo-relative path: content}``.

    The neutral ``agent_config/`` frontmatter is already opencode-shaped, so this renderer is a
    verbatim copy: agents keep ``description``/``mode``/``model``/``permission``, commands keep
    ``description``/``agent``/``subtask``, and positional args stay 1-indexed. Because the source
    is neutral (not opencode-specific), this is the *projection* of the neutral schema onto the
    opencode schema — not the definition of the neutral schema.
    """
    out: dict[str, str] = {}

    # 1. Instruction documents → .opencode/instructions/.
    for name in INSTRUCTIONS:
        out[f".opencode/instructions/{name}"] = _read(name)

    # 2. Skills → .opencode/skills/<name>/SKILL.md.
    for name in SKILLS:
        out[f".opencode/skills/{name}/SKILL.md"] = _read(f"skills/{name}.md")

    # 3. Agents.
    for name in AGENTS:
        out[f".opencode/agents/{name}.md"] = _read(f"agents/{name}.md")

    # 4. Commands.
    for name in COMMANDS:
        out[f".opencode/commands/{name}.md"] = _read(f"commands/{name}.md")

    return out


def _render_claude_agent(name: str, fields: list[str], body: str) -> str:
    """Render one Claude Code subagent: only ``name`` + ``description`` survive.

    ``mode``/``model``/``permission`` are opencode-only (verified: Claude's subagent frontmatter
    has no per-capability ``permission`` field and its ``model`` accepts only Claude models); they
    are dropped rather than mis-mapped. The name is derived from the filename (lowercase+hyphens,
    which already satisfies Claude's ``name`` constraint).
    """
    description = _scalar(fields, "description")
    assert description is not None, f"agent {name!r} missing required 'description'"
    return f"---\nname: {name}\ndescription: {description}\n---\n{body}"


def _render_claude_command(fields: list[str], body: str) -> str:
    """Render one Claude Code command: only ``description`` survives; args re-indexed.

    ``agent``/``subtask`` are dropped (no Claude equivalent — docs/claude_code_port.md §2). Positional
    args are re-indexed 1→0: opencode's ``$2`` ("second argument") becomes Claude's ``$1``.
    ``$ARGUMENTS`` is the same token on both platforms and passes through untouched.
    """
    description = _scalar(fields, "description")
    assert description is not None, "command missing required 'description'"
    return f"---\ndescription: {description}\n---\n{_reindex_positional_args(body)}"


def _reindex_positional_args(body: str) -> str:
    """Translate opencode's 1-indexed positional args (``$N``) to Claude's 0-indexed (``$N-1``)."""

    def sub(match: re.Match[str]) -> str:
        return "$" + str(int(match.group(1)) - 1)

    return _POSITIONAL_ARG.sub(sub, body)


def render_claude() -> dict[str, str]:
    """Render the Claude Code surface as ``{repo-relative path: content}``.

    Instructions and skills are schema-identical to opencode (verbatim). Agents and commands are
    projected onto Claude's real schema via the helpers above.
    """
    out: dict[str, str] = {}

    # 1. Instruction documents → .claude/rules/ (unscoped rules — no frontmatter required).
    for name in INSTRUCTIONS:
        out[f".claude/rules/{name}"] = _read(name)

    # 2. Skills → .claude/skills/<name>/SKILL.md (same schema as opencode).
    for name in SKILLS:
        out[f".claude/skills/{name}/SKILL.md"] = _read(f"skills/{name}.md")

    # 3. Agents → name + description only.
    for name in AGENTS:
        fields, body = _read_frontmatter(f"agents/{name}.md")
        out[f".claude/agents/{name}.md"] = _render_claude_agent(name, fields, body)

    # 4. Commands → description only, positional args re-indexed.
    for name in COMMANDS:
        fields, body = _read_frontmatter(f"commands/{name}.md")
        out[f".claude/commands/{name}.md"] = _render_claude_command(fields, body)

    return out


# --- per-target schema validation --------------------------------------------


def validate_root(rendered: dict[str, str]) -> list[str]:
    """Validate the root rendering against the root-document schema. Returns a list of problems.

    The root "schema" is the repository's own doc-lifecycle contract plus the generated-surface
    contract: a ``status`` field drawn from the rec-4 vocabulary (``tests/test_doc_lifecycle.py``
    walks root ``*.md`` and fails without it), the generated banner, and — for ``CLAUDE.md`` — the
    ``@AGENTS.md`` import that keeps the two roots from carrying two copies of the rules.
    """
    errors: list[str] = []
    for path, content in rendered.items():
        fields, body = _split_frontmatter(content)
        status = _scalar(fields, "status")
        if status is None:
            errors.append(f"{path}: missing required 'status' frontmatter (doc-lifecycle)")
        elif status != ROOT_STATUS:
            errors.append(f"{path}: status {status!r} is not the rendered {ROOT_STATUS!r}")
        if "GENERATED by scripts/_gen_instructions.py" not in body:
            errors.append(f"{path}: missing the generated-surface banner")
        if path == "CLAUDE.md" and "@AGENTS.md" not in body:
            errors.append(f"{path}: missing the '@AGENTS.md' import (the roots would diverge)")
    return errors


def validate_opencode(rendered: dict[str, str]) -> list[str]:
    """Validate the opencode rendering against the opencode schema. Returns a list of problems."""
    errors: list[str] = []
    for path, content in rendered.items():
        if path.startswith(".opencode/agents/"):
            fields, _ = _split_frontmatter(content)
            for key in ("description", "mode", "model"):
                if _scalar(fields, key) is None:
                    errors.append(f"{path}: missing required {key!r}")
            if not _has_top_level_key(fields, "permission"):
                errors.append(f"{path}: missing required 'permission' block")
        elif path.startswith(".opencode/commands/"):
            fields, _ = _split_frontmatter(content)
            if _scalar(fields, "description") is None:
                errors.append(f"{path}: missing required 'description'")
        elif path.startswith(".opencode/skills/"):
            fields, _ = _split_frontmatter(content)
            for key in ("name", "description"):
                if _scalar(fields, key) is None:
                    errors.append(f"{path}: missing required {key!r}")
    return errors


def validate_claude(rendered: dict[str, str]) -> list[str]:
    """Validate the Claude rendering against the Claude schema. Returns a list of problems.

    In addition to required-field checks, this REJECTS opencode-only keys (``mode``/``permission``
    on agents, ``agent``/``subtask`` on commands) and any ``model`` that carries an opencode
    ``provider/model`` value (Claude's ``model`` accepts only ``sonnet``/``opus``/``haiku``/
    ``fable``/``inherit`` or a full Claude ID).
    """
    errors: list[str] = []
    for path, content in rendered.items():
        if path.startswith(".claude/agents/"):
            fields, _ = _split_frontmatter(content)
            for key in ("name", "description"):
                if _scalar(fields, key) is None:
                    errors.append(f"{path}: missing required {key!r}")
            for key in OPENCODE_ONLY_AGENT_KEYS:
                if _has_top_level_key(fields, key):
                    errors.append(f"{path}: opencode-only key {key!r} leaked into Claude output")
            model = _scalar(fields, "model")
            if model is not None and "/" in model:
                errors.append(
                    f"{path}: model {model!r} is an opencode provider/model id "
                    "(Claude accepts sonnet|opus|haiku|fable|inherit or a full Claude ID)"
                )
        elif path.startswith(".claude/commands/"):
            fields, _ = _split_frontmatter(content)
            if _scalar(fields, "description") is None:
                errors.append(f"{path}: missing required 'description'")
            for key in OPENCODE_ONLY_COMMAND_KEYS:
                if _has_top_level_key(fields, key):
                    errors.append(f"{path}: opencode-only key {key!r} leaked into Claude output")
        elif path.startswith(".claude/skills/"):
            fields, _ = _split_frontmatter(content)
            for key in ("name", "description"):
                if _scalar(fields, key) is None:
                    errors.append(f"{path}: missing required {key!r}")
    return errors


# --- the whole surface -------------------------------------------------------

#: Directories that contain NOTHING but generated files. Any file found under one of these that
#: the renderers did not emit is an orphan: hand-added, or left behind when its source was renamed
#: or removed. Both ``--check`` and ``tests/test_agent_config_render.py`` read this one list, so
#: "which trees are generated?" has a single answer.
GENERATED_TREES: tuple[str, ...] = (
    ".opencode/instructions",
    ".opencode/skills",
    ".opencode/agents",
    ".opencode/commands",
    ".claude/rules",
    ".claude/skills",
    ".claude/agents",
    ".claude/commands",
)


def render_all() -> dict[str, str]:
    """Every generated surface, as ``{repo-relative path: content}``.

    One mapping for the three renderers is what makes ``--check`` total: drift means "this mapping
    differs from the tree", with no per-target special cases to forget.
    """
    return {**render_root(), **render_opencode(), **render_claude()}


def validate_all(rendered: dict[str, str] | None = None) -> list[str]:
    """Run every per-target validator over a rendering. Returns the combined problem list."""
    rendered = render_all() if rendered is None else rendered
    root = {k: v for k, v in rendered.items() if k in ROOT_SOURCES}
    opencode = {k: v for k, v in rendered.items() if k.startswith(".opencode/")}
    claude = {k: v for k, v in rendered.items() if k.startswith(".claude/")}
    return validate_root(root) + validate_opencode(opencode) + validate_claude(claude)


def find_drift(rendered: dict[str, str] | None = None) -> list[str]:
    """Differences between a rendering and the committed tree, as human-readable lines.

    Three kinds, all real drift and all reported:

    * **missing** — a surface the renderers emit that is not on disk at all.
    * **stale** — a surface whose committed bytes differ from what the renderer now produces
      (someone edited a source without regenerating, or hand-edited the output).
    * **orphan** — a file inside a generated tree that no renderer emits (hand-added, or left over
      from a removed source — the ``system_snapshot.md`` renders were exactly this after p5 dropped
      them from :data:`INSTRUCTIONS`).

    Returns ``[]`` when the tree is exactly the rendering. Never writes anything.
    """
    rendered = render_all() if rendered is None else rendered
    drift: list[str] = []

    for rel, expected in rendered.items():
        target = ROOT / rel
        if not target.exists():
            drift.append(f"missing: {rel}")
        elif target.read_text(encoding="utf-8") != expected:
            drift.append(f"stale:   {rel}")

    generated = set(rendered)
    for tree in GENERATED_TREES:
        for path in sorted((ROOT / tree).rglob("*")):
            if path.is_file():
                rel = str(path.relative_to(ROOT))
                if rel not in generated:
                    drift.append(f"orphan:  {rel}")

    return sorted(drift)


# --- writer ------------------------------------------------------------------


def write_surfaces() -> tuple[int, list[str]]:
    """Write every rendered surface to disk and prune orphans. Returns ``(written, pruned)``.

    Pruning matters because without it the generator is not idempotent in the one direction that
    counts: remove a source (as p5 removed ``system_snapshot.md`` from :data:`INSTRUCTIONS`) and the
    stale render survives forever, still loaded by every session, with ``--check`` red and no
    command that fixes it. The delete is confined to :data:`GENERATED_TREES` — directories that
    contain nothing but this script's output — so it can never reach a hand-authored file. The root
    documents are NOT pruned: they live beside hand-authored docs, so removing a root source is a
    deliberate ``git rm``, not a side effect of running the generator.
    """
    rendered = render_all()
    for rel, content in rendered.items():
        target = ROOT / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    pruned: list[str] = []
    for tree in GENERATED_TREES:
        for path in sorted((ROOT / tree).rglob("*")):
            if path.is_file() and str(path.relative_to(ROOT)) not in rendered:
                path.unlink()
                pruned.append(str(path.relative_to(ROOT)))
    return len(rendered), pruned


# --- CLI ---------------------------------------------------------------------

#: ``--help`` prose. Deliberately describes only what this script does; the previous root
#: ``AGENTS.md`` drift (a retired corpus documented as a live research source) is the reminder that
#: instruction text which nobody regenerates is instruction text nobody keeps true.
_CLI_DESCRIPTION = """\
Render the instruction surfaces from the neutral agent_config/ source.

Outputs (all generated — never hand-edit):
  AGENTS.md, CLAUDE.md          the root instructions (opencode + Claude Code)
  .opencode/{instructions,skills,agents,commands}
  .claude/{rules,skills,agents,commands}

Default (no flags) writes every surface. --check writes nothing and exits 1 on drift.
"""


def main(argv: list[str] | None = None) -> int:
    """Write the surfaces, or (``--check``) report drift without touching the tree."""
    parser = argparse.ArgumentParser(
        prog="_gen_instructions.py",
        description=_CLI_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "do not write; re-render in memory and exit 1 if any generated surface is missing, "
            "stale, or orphaned (the CI gate)"
        ),
    )
    args = parser.parse_args(argv)

    rendered = render_all()
    problems = validate_all(rendered)

    if args.check:
        drift = find_drift(rendered)
        if problems:
            print("SCHEMA FAILURES:")
            for problem in problems:
                print(f"  {problem}")
        if drift:
            print("SURFACE DRIFT — a source changed without regenerating:")
            for line in drift:
                print(f"  {line}")
        if problems or drift:
            print(
                "\nregenerate with `python3 scripts/_gen_instructions.py` "
                "(or `agentic-dynamics surfaces sync`) and commit the result"
            )
            return 1
        print(f"surfaces OK — {len(rendered)} generated files match agent_config/")
        return 0

    written, pruned = write_surfaces()
    print(f"wrote {written} surface files")
    for rel in pruned:
        print(f"pruned (no source renders it): {rel}")
    roots = sum(1 for rel in rendered if rel in ROOT_SOURCES)
    opencode = sum(1 for rel in rendered if rel.startswith(".opencode/"))
    claude = sum(1 for rel in rendered if rel.startswith(".claude/"))
    print(f"root: {roots}, opencode: {opencode}, claude: {claude}")
    print(f"schema: {problems or 'OK'}")
    # A schema failure is a broken surface even when the bytes were written: fail loudly rather
    # than leave an invalid config on disk under a zero exit.
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
