"""Generate the `.opencode/` + `.claude/` instruction surfaces from `agent_config/`.

Critique rec 6 / refactor-repair P0-1: `.opencode/` and `.claude/` must not both be manually
authoritative, and — crucially — they must not be byte-identical copies of one another. The two
platforms do NOT share a schema: opencode agents use `mode`/`model`/`permission` frontmatter,
Claude Code agents use `name`/`description` (plus a disjoint optional set) and hold per-capability
permissions at the project level (`.claude/settings.json`), not per-agent; and opencode positional
command args are 1-indexed (`$1` = first) while Claude Code's are 0-indexed (`$0` = first). A
verbatim copy emits invalid Claude configuration even while a byte-equality test stays green.

This module is the single writer: it reads the hand-edited NEUTRAL source `agent_config/` and
renders each platform's REAL format through two independent renderers:

* ``render_opencode()`` — opencode format (neutral agent frontmatter is already opencode-shaped:
  ``description``/``mode``/``model``/``permission``; commands keep ``agent``/``subtask``; positional
  args stay 1-indexed).
* ``render_claude()`` — Claude Code format (agents keep only ``name``/``description``; commands keep
  only ``description``; positional args are re-indexed to 0-based).

``validate_opencode()`` / ``validate_claude()`` assert each rendering against a per-target schema
(required fields present, opencode-only keys rejected in the Claude output), and
``tests/test_agent_config_render.py`` replaces the old byte-equality drift guard with
meaning-equivalence + schema-validity checks.

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

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENT_CONFIG = ROOT / "agent_config"

#: Instruction documents (plain markdown, no frontmatter) mapped to both surfaces.
INSTRUCTIONS = ("mental-model.md", "rules.md", "conventions.md", "system_snapshot.md")

#: The seven skills (name/description frontmatter — the schema is SHARED by both platforms).
SKILLS = ("analyze", "control-room", "instrument", "lab-books", "queue", "review", "run-workflow")

#: The subagent definitions (schema DIVERGES between platforms — see the renderers).
AGENTS = ("data-analysis", "instrument-dev", "pipeline-ops")

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


# --- writer ------------------------------------------------------------------


def write_surfaces() -> None:
    """Write both rendered surfaces to disk (creating parent directories)."""
    written = 0
    for rel, content in {**render_opencode(), **render_claude()}.items():
        target = ROOT / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written += 1
    print(f"wrote {written} surface files")


def main() -> int:
    write_surfaces()
    opencode = render_opencode()
    claude = render_claude()
    print(f"opencode: {len(opencode)} files, claude: {len(claude)} files")
    print(f"opencode schema: {validate_opencode(opencode) or 'OK'}")
    print(f"claude schema:   {validate_claude(claude) or 'OK'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
