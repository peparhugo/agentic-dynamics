"""Publication as ONE transaction — the receipt, the gates, the consistency check (p6).

The problem this module closes. Publishing the website used to be two ``firebase deploy``
commands typed by hand, with nothing between the data build and the deploy that could say
whether the data was current or whether the pages agreed with it. The observable consequence is
in the repository right now: ``apps/website/index.html`` claims a corpus of 1,067 sessions while
``apps/website/data.js`` — the file the same page loads — says 1,027. Nothing was lying; there
was simply no step whose job was to notice.

The shape of the fix is a *transaction* with a *receipt*:

.. code-block:: text

    verify projections → build data → verify HTML consistency → RECEIPT
      → deploy canonical host → deploy mirror host → record both → post-deploy check

The receipt (``publication/v1``) is the join point. It is produced *after* the artifacts exist
and *before* anything is deployed, it names the tree, the two artifact digests, the headline
corpus number, and the projection frontier the data was derived from — and it is what gets
written to the control database. Every public number on the site is supposed to trace back to
one of those documents.

This module is the *pure* half, in the split the control plane uses everywhere (``control_status``
under ``scripts/control_status.py``, ``lease_watchdog`` under ``scripts/lease_watchdog.py``):
derivations, schemas, and checks that read files and return findings. The impure half — running
``build_data.py``, shelling out to ``firebase``, writing to the database, printing — is
``scripts/publish_release.py``. Keeping the checks here is what makes them testable without a
Firebase project, and what lets the HTML-consistency check run as an ordinary pytest.

Design notes on the two gates:

* **The projection gate** consumes p3's watermarks. It refuses on ``UNKNOWN`` as firmly as on
  ``LAGGING``: publishing data derived from a projector nobody can vouch for is exactly as
  unsafe as publishing from one known to be behind. That is a deliberate fail-closed choice —
  the alternative reads "no news is good news", which is how the 1,067 got there.
* **The HTML-consistency gate** runs two independent checks over every page, described in full
  under :func:`check_site_consistency`. One is exact and mechanical; one is a prose net with a
  declared exemption table. Neither subsumes the other.

See ``workflows/repository/control_db_publication.yaml`` (p6) for the mandate and
``docs/architecture/current/control_plane_vocabulary.md`` for where "publication receipt" sits
among the other things this repo used to call "the index".
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentic_dynamics.control import projection_watermarks as pw
from agentic_dynamics.control.control_db import ControlDB
from agentic_dynamics.core.paths import PROJECT_ROOT

# ── Identity and locations ───────────────────────────────────────────────────────────────────

#: The receipt contract's id. Versioned in the value, like every other schema in the control
#: plane (``control-status/v1``, ``subscription-usage/v3``), so a consumer can branch on it.
SCHEMA_ID = "publication/v1"

#: The website root — the directory Firebase serves (``firebase.json`` lives there with
#: ``public: "."``), and therefore the exact set of files a consistency check must cover.
SITE_ROOT = PROJECT_ROOT / "apps" / "website"

#: The generated data file every page loads. The AUTHORITY for corpus numbers on the site.
DATA_JS = SITE_ROOT / "data.js"

#: The manifest the data chain builds from. Its digest goes in the receipt so a receipt can be
#: tied back to the registry state that produced it.
DATA_MANIFEST = PROJECT_ROOT / "experiments" / "data_manifest.json"

#: Where executed receipts are archived on disk, alongside the control-database row. Two copies
#: of one fact, deliberately: the database is the queryable record, the file is the one that
#: survives a checkout without a database.
RECEIPT_DIR = PROJECT_ROOT / "experiments" / "results" / "publication"


@dataclass(frozen=True)
class FirebaseHost:
    """One of the two Firebase hosting targets the dual-host rule requires.

    The rule (``AGENTS.md``, operational notes): the site is served from two projects and every
    deploy must target BOTH. Encoding them as data rather than as two lines in a runbook is the
    point of p6 — a list can be iterated, counted, and checked; a runbook cannot.
    """

    #: ``canonical`` or ``mirror`` — the role, which is what the control database records.
    role: str
    #: The Firebase project id passed to ``--project`` (omitted for the default target).
    project: str
    #: The public URL, used by the post-deploy check.
    url: str
    #: Human note on why this host exists, surfaced in ``--dry-run`` output.
    note: str


#: The two hosts, canonical first. The canonical URL has already been shared with peers and must
#: never be retired or renamed (``AGENTS.md``); the mirror carries the forward-looking identity.
FIREBASE_HOSTS: tuple[FirebaseHost, ...] = (
    FirebaseHost(
        role="canonical",
        project="ai-finops-rulebook",
        url="https://ai-finops-rulebook.web.app",
        note="canonical — the URL already shared with peers; never retire or rename it",
    ),
    FirebaseHost(
        role="mirror",
        project="agentic-dynamics",
        url="https://agentic-dynamics.web.app",
        note="mirror — the forward-looking identity; must never drift from canonical",
    ),
)


# ── Small shared helpers ─────────────────────────────────────────────────────────────────────


def _now_iso() -> str:
    """UTC, ISO-8601, second precision — the timestamp format the control plane uses."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    """The SHA-256 of a file's bytes, or ``""`` when it does not exist.

    Empty rather than an exception because a missing artifact is a *finding* the caller should
    render (the receipt records ``""`` and the gate refuses), not a traceback that hides which
    of several artifacts was missing.
    """
    if not path.exists():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ── Reading data.js ──────────────────────────────────────────────────────────────────────────

#: ``data.js`` is a JS assignment, not JSON: two comment lines, then
#: ``window.DYNAMICS_DATA = { ... };``. This lifts the object literal out. The generator writes
#: it with ``json.dumps`` (see ``scripts/build_data.py``), so the braces balance and the body is
#: valid JSON — parsing it as JSON is exact, not a heuristic.
_DATA_JS_RE = re.compile(r"window\.DYNAMICS_DATA\s*=\s*(?P<body>\{.*\})\s*;?\s*\Z", re.DOTALL)


class PublicationError(Exception):
    """A publication precondition failed. Raised by the gates; caught by the CLI shell."""


def load_data_js(path: Path | str | None = None) -> dict[str, Any]:
    """Parse ``data.js`` into the ``window.DYNAMICS_DATA`` object.

    :raises PublicationError: when the file is absent or does not carry the expected assignment.
        Both cases mean "there is no authority to check the pages against", which must stop a
        publication rather than let it proceed against an empty dict (an empty dict would make
        every page look consistent — the failure mode this whole module exists to prevent).
    """
    target = Path(path) if path is not None else DATA_JS
    if not target.exists():
        raise PublicationError(f"publication: no data.js at {target} — run build_data.py first")
    match = _DATA_JS_RE.search(target.read_text(encoding="utf-8"))
    if not match:
        raise PublicationError(
            f"publication: {target} does not contain a window.DYNAMICS_DATA assignment "
            "(was it hand-edited? it is generated by scripts/build_data.py)"
        )
    try:
        parsed = json.loads(match.group("body"))
    except json.JSONDecodeError as exc:  # pragma: no cover - only on a corrupted generator
        raise PublicationError(f"publication: {target} body is not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise PublicationError(f"publication: {target} body is not a JSON object")
    return parsed


# ── The corpus stats the site is allowed to assert ───────────────────────────────────────────


@dataclass(frozen=True)
class CorpusStat:
    """One number the website may state, and where its authoritative value comes from.

    ``data_key`` is the dotted path into ``window.DYNAMICS_DATA``; ``fallback_key`` mirrors
    ``app.js``'s own ``||`` fallbacks so this module resolves a stat exactly the way the browser
    does. Where they differ, the browser wins and this table is wrong — which is why the
    resolution is written once here and reused by both checks below.
    """

    #: The ``data-stat`` attribute value, i.e. the key ``app.js`` looks up.
    key: str
    #: Dotted path into the data object, e.g. ``summary.story_sessions``.
    data_key: str
    #: Second path tried when the first is absent or zero, mirroring ``app.js``.
    fallback_key: str = ""
    #: ``count`` renders as a plain integer; ``usd`` renders with two decimals (``fmtUSD``).
    kind: str = "count"
    #: Does ``app.js``'s ``statMap`` know this key? Check A only compares elements whose value
    #: the browser will actually inject — asserting a ``data-stat`` fallback against a key the
    #: runtime cannot render would report agreement between a static number and a value that
    #: never arrives. Non-hydrated stats exist here for the PROSE check, which needs the
    #: authoritative value regardless of whether any markup binds to it.
    hydrated: bool = True


#: The corpus stats this module knows how to resolve. Deliberately a *declared subset* of
#: ``app.js``'s ``statMap``: the model-derived and calculator-derived keys are rendered from
#: nested structures whose resolution would have to be reimplemented here, and a reimplementation
#: that drifts is worse than an honest gap. Unknown keys are skipped by the checks and reported
#: as skipped, never silently treated as passing.
CORPUS_STATS: tuple[CorpusStat, ...] = (
    CorpusStat("sessions", "summary.sessions_total"),
    CorpusStat("story_sessions", "summary.story_sessions", "summary.sessions_total"),
    CorpusStat("stories_total", "summary.stories_total"),
    # Prose-only: app.js has no `stories_unique` statMap entry, so nothing hydrates it. It is
    # here because the site states the unique-cell count in prose ("150 unique cells"), and that
    # number has to reconcile with data.js like any other.
    CorpusStat("stories_unique", "summary.stories_unique", hydrated=False),
    CorpusStat("worktrees", "summary.worktrees_total"),
    CorpusStat("reports", "summary.game_reports"),
    CorpusStat("architectures", "summary.architectures"),
    CorpusStat("variants", "summary.variants"),
    CorpusStat("cost", "summary.total_cost", kind="usd"),
    CorpusStat("story_total_cost", "summary.story_total_cost", "summary.total_cost", kind="usd"),
    CorpusStat("registry_current_records", "summary.registry_current_records"),
    CorpusStat("resolved_measurement_payloads", "summary.resolved_measurement_payloads"),
    CorpusStat("eligible_records", "summary.eligible_records"),
    CorpusStat("records_used", "summary.records_used"),
    CorpusStat("unresolved_waivered", "summary.unresolved_waivered"),
    CorpusStat("canonical_findings", "summary.canonical_findings"),
    CorpusStat("contaminated_tombstones", "summary.contaminated_tombstones"),
    CorpusStat("no_measurement_tombstones", "summary.no_measurement_tombstones"),
    CorpusStat("tombstones_total", "summary.tombstones_total"),
)

_STATS_BY_KEY: dict[str, CorpusStat] = {stat.key: stat for stat in CORPUS_STATS}


def _dig(data: Mapping[str, Any], dotted: str) -> Any:
    """Walk a dotted path through nested mappings, returning ``None`` at the first miss."""
    node: Any = data
    for part in dotted.split("."):
        if not isinstance(node, Mapping) or part not in node:
            return None
        node = node[part]
    return node


def resolve_stat(data: Mapping[str, Any], key: str) -> float | int | None:
    """The authoritative value of one corpus stat, resolved as ``app.js`` resolves it.

    Returns ``None`` for an unknown key or one absent from the data — "I cannot check this",
    which callers must distinguish from "this checks out". The fallback is applied on a falsy
    primary value because that is literally what ``app.js`` does
    (``D.summary.story_sessions || D.summary.sessions_total``).
    """
    stat = _STATS_BY_KEY.get(key)
    if stat is None:
        return None
    value = _dig(data, stat.data_key)
    if not value and stat.fallback_key:
        value = _dig(data, stat.fallback_key)
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _normalise_number(text: str) -> float | None:
    """Parse a number as it appears in prose: ``"1,027"``, ``"$309.17"``, ``"1027"``.

    Thousands separators and a leading currency symbol are stripped before parsing, because the
    check is about the VALUE, not the typography. This matters concretely: ``app.js`` assigns
    the raw number to ``textContent`` (so the browser renders ``1027``) while the static
    fallback in the markup is written ``1,027`` for readability. Comparing the strings would
    fail every page for a formatting difference that no reader can see; comparing the numbers
    catches exactly the disagreements that change what the page claims.
    """
    cleaned = text.strip().replace(",", "").replace("$", "").replace(" ", "")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _values_agree(claimed: float, authoritative: float, *, kind: str) -> bool:
    """Do a page's number and the authoritative one say the same thing?

    Counts must match exactly. USD amounts are compared at the two-decimal precision the site
    displays (``fmtUSD`` → ``toFixed(2)``), so a page showing ``$309.17`` agrees with an
    underlying ``309.1685`` — the page is not wrong, it is rounded, and flagging it would train
    readers to ignore this check.
    """
    if kind == "usd":
        return round(claimed, 2) == round(authoritative, 2)
    return float(claimed) == float(authoritative)


# ── Findings ─────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ConsistencyFinding:
    """One disagreement between a page and the authoritative data.

    Carries enough to fix the page without re-running anything: which file, which line, the
    exact text that disagreed, what it claimed, and what the data says.
    """

    #: ``data_stat_fallback`` (check A) or ``prose_claim`` (check B) — see
    #: :func:`check_site_consistency`.
    check: str
    page: str
    line: int
    stat_key: str
    claimed: float
    authoritative: float
    #: The surrounding text, trimmed — what a human needs to locate it in the page.
    excerpt: str

    def describe(self) -> str:
        """One line, formatted for a terminal report."""
        claimed = f"{self.claimed:g}"
        expected = f"{self.authoritative:g}"
        return (
            f"{self.page}:{self.line}: [{self.check}] {self.stat_key} claims {claimed}, "
            f"data.js says {expected} — {self.excerpt}"
        )


# ── Check A: data-stat fallbacks (exact) ─────────────────────────────────────────────────────

#: ``<span data-stat="story_sessions">1,027</span>`` — the attribute and the literal text between
#: that element's tags. Non-greedy body, no nested tags: every ``data-stat`` element on the site
#: wraps a bare number (verified by the test), and a pattern that tried to handle nesting would
#: quietly match across elements.
_DATA_STAT_RE = re.compile(
    r"<(?P<tag>\w+)[^>]*\bdata-stat=\"(?P<key>[\w-]+)\"[^>]*>(?P<body>[^<>]*)</(?P=tag)>"
)


def check_data_stat_fallbacks(
    html: str, data: Mapping[str, Any], *, page: str
) -> list[ConsistencyFinding]:
    """Check A — every ``data-stat`` element's literal text against ``data.js``. Exact.

    A ``data-stat`` span carries two numbers: the one written into the markup (what a reader
    sees before JavaScript runs, what a scraper reads, what appears with JS disabled) and the one
    ``app.js`` injects at ``DOMContentLoaded``. They are supposed to be the same number. When
    they are not, the page tells two different stories depending on how it is read — and the
    static one is the version that reaches search engines and social-card previews.

    This check is mechanical: the key names the stat, so there is no guessing about what the
    number means. Empty bodies are skipped (an element intentionally left for JS to fill), as
    are keys outside :data:`CORPUS_STATS` (see the note there on the honest gap).
    """
    findings: list[ConsistencyFinding] = []
    for match in _DATA_STAT_RE.finditer(html):
        key = match.group("key")
        body = match.group("body").strip()
        if not body:
            continue  # Intentionally JS-filled; there is no static claim to disagree with.
        authoritative = resolve_stat(data, key)
        if authoritative is None:
            continue  # Unknown or absent stat — reported as skipped, never as passing.
        claimed = _normalise_number(body)
        if claimed is None:
            continue  # Not a number (e.g. the "12/15" tests ratio); not a corpus count.
        stat = _STATS_BY_KEY[key]
        if not stat.hydrated:
            continue  # See CorpusStat.hydrated — nothing injects this key at runtime.
        if not _values_agree(claimed, authoritative, kind=stat.kind):
            findings.append(
                ConsistencyFinding(
                    check="data_stat_fallback",
                    page=page,
                    line=html.count("\n", 0, match.start()) + 1,
                    stat_key=key,
                    claimed=claimed,
                    authoritative=float(authoritative),
                    excerpt=match.group(0)[:120],
                )
            )
    return findings


# ── Check B: prose claims (the net over hard-coded numbers) ──────────────────────────────────

#: Attributes whose VALUES are reader-facing prose and must therefore be scanned: the meta
#: description and the Open Graph / Twitter card text. These are the copies of the corpus claim
#: that no amount of client-side hydration can fix — they are read by crawlers, not browsers —
#: which is precisely why index.html's stale 1,067 survived so long in them.
_META_CONTENT_RE = re.compile(
    r"<meta[^>]*\b(?:name|property)=\"(?P<which>description|og:description|og:title|"
    r"twitter:description|twitter:title)\"[^>]*\bcontent=\"(?P<text>[^\"]*)\"",
    re.IGNORECASE,
)

#: The corpus claims this check knows how to read, as a DECLARED table of phrasings.
#:
#: The first version of this check went the other way — match any "N sessions" and exempt what
#: did not count. That net flagged 52 sentences on the current site, almost all of them correct
#: ("164 sessions with ≥3 reasoning steps", "5 sessions each", "$0.016 per session"): the site
#: talks about sessions constantly, and almost none of those numbers are the corpus total. A
#: gate with that false-positive rate gets switched off, which is worse than no gate.
#:
#: So the table is positive and narrow: each entry is a phrasing that can ONLY mean one corpus
#: total. The cost is honest and stated in :meth:`ConsistencyReport.summary` terms — a claim
#: written in a phrasing not listed here is not checked by this pass. That gap is covered from
#: the other side: the fix for a stale prose number is to wrap it in a ``data-stat`` span, which
#: moves it under check A, where the comparison is exact and needs no pattern at all. This table
#: exists for the claims that CANNOT be hydrated — ``<meta>`` descriptions and Open Graph text,
#: which crawlers read straight from the source and JavaScript never touches.
CORPUS_CLAIM_PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    # ── the story-session total ──────────────────────────────────────────────────────────
    (
        "story_sessions",
        "N [adjective] story sessions",
        re.compile(r"(?P<n>\d[\d,]*)\s+(?:[A-Za-z][\w-]*\s+){0,2}?story sessions\b", re.I),
    ),
    (
        "story_sessions",
        "N-session [linked-story] corpus",
        re.compile(r"(?P<n>\d[\d,]*)[-‑]session\s+(?:[A-Za-z][\w-]*\s+){0,2}?corpus\b", re.I),
    ),
    (
        "story_sessions",
        "N agentic sessions",
        re.compile(r"(?P<n>\d[\d,]*)\s+agentic sessions\b", re.I),
    ),
    (
        "story_sessions",
        "N captured/instrumented [story] sessions",
        re.compile(
            r"(?P<n>\d[\d,]*)\s+(?:captured|instrumented)\s+(?:story\s+)?sessions\b", re.I
        ),
    ),
    (
        "story_sessions",
        "across/from N sessions and M models",
        re.compile(r"(?:across|from)\s+(?P<n>\d[\d,]*)\s+sessions\s+and\s+\d+\s+models\b", re.I),
    ),
    (
        "story_sessions",
        "N story-building runs",
        re.compile(r"(?P<n>\d[\d,]*)\s+story[-‑ ]building runs\b", re.I),
    ),
    # ── the story total ──────────────────────────────────────────────────────────────────
    (
        "stories_total",
        "N linked/executed stories",
        re.compile(r"(?P<n>\d[\d,]*)\s+(?:linked|executed)\s+stories\b", re.I),
    ),
    (
        "stories_total",
        "N stories across ...",
        re.compile(r"(?P<n>\d[\d,]*)\s+stories\s+across\b", re.I),
    ),
    (
        "stories_total",
        "metrics from N stories",
        re.compile(r"metrics\s+from\s+(?P<n>\d[\d,]*)\s+stories\b", re.I),
    ),
    # ── the unique-cell total ────────────────────────────────────────────────────────────
    (
        "stories_unique",
        "N unique cells",
        re.compile(r"(?P<n>\d[\d,]*)\s+unique cells\b", re.I),
    ),
)


#: Tags that do NOT interrupt a sentence. A claim may run through these, because that is how the
#: fix for a stale prose number is written: ``<span data-stat="story_sessions">1,027</span> story
#: sessions`` is one sentence with a hydration point in the middle of it.
_INLINE_TAGS = frozenset(
    {
        "span", "a", "strong", "b", "em", "i", "code", "abbr", "small",
        "sup", "sub", "u", "mark", "time", "cite", "q", "var", "kbd", "samp",
    }
)

#: The character a BLOCK boundary becomes. Chosen because no pattern in
#: :data:`CORPUS_CLAIM_PATTERNS` can match across it — it is neither whitespace nor a word
#: character — so a claim can never be assembled from two different block elements.
#:
#: This is what separates a real sentence from a stat card. The site renders
#: ``<div class="value">347</div><div class="label">Instrumented Sessions</div>``; blanking every
#: tag to a space turns that into the sentence "347 Instrumented Sessions", which the prose check
#: then reads as a corpus claim of 347. It is not a claim, it is a two-cell layout, and no reader
#: would parse it as prose. Block boundaries make the check agree with the reader.
_BLOCK_BREAK = "\x00"


def _strip_tags_with_map(html: str) -> tuple[str, list[int]]:
    """Reduce a page to reader-visible text, with an offset map back into the source.

    Returns ``(text, offsets)`` where ``offsets[i]`` is the index in ``html`` that produced
    ``text[i]`` — which is what lets a finding report the line number in the actual file rather
    than in a transformed copy of it.

    Three transformations, each with a reason:

    * ``<script>``/``<style>`` blocks are dropped entirely — chart code is not prose;
    * an INLINE tag becomes one space, so a sentence survives its own markup;
    * any other tag becomes :data:`_BLOCK_BREAK`, so a sentence cannot be assembled across two
      block elements.
    """
    text: list[str] = []
    offsets: list[int] = []
    cursor = 0
    for match in re.finditer(
        r"<(script|style)\b[^>]*>.*?</\1>|</?(?P<name>[A-Za-z][\w-]*)\b[^>]*/?>",
        html,
        re.DOTALL | re.IGNORECASE,
    ):
        for index in range(cursor, match.start()):
            text.append(html[index])
            offsets.append(index)
        name = (match.group("name") or "").lower()
        # A script/style match has no `name` group -> name == "", which is not in _INLINE_TAGS,
        # so it correctly becomes a block break rather than a joinable space.
        text.append(" " if name in _INLINE_TAGS else _BLOCK_BREAK)
        offsets.append(match.start())
        cursor = match.end()
    for index in range(cursor, len(html)):
        text.append(html[index])
        offsets.append(index)
    return "".join(text), offsets


def _context_window(text: str, start: int, end: int, *, before: int = 60, after: int = 60) -> str:
    """The text around a match, trimmed to one line — the finding's human-locatable excerpt."""
    window = text[max(0, start - before) : min(len(text), end + after)]
    return window.replace(_BLOCK_BREAK, " ").replace("\n", " ").strip()


def _scan_prose_claims(
    text: str,
    data: Mapping[str, Any],
    *,
    page: str,
    line_of: Any,
    source_label: str = "",
) -> list[ConsistencyFinding]:
    """Run every declared claim pattern over one block of reader-facing text.

    ``line_of`` maps a character offset in ``text`` back to a line number in the original file.
    It is injected because the caller scans two kinds of text: the tag-stripped body (where
    offsets are preserved by construction — see :func:`check_prose_claims`) and ``<meta>``
    attribute values (which sit at one known line).
    """
    findings: list[ConsistencyFinding] = []
    seen: set[tuple[int, str]] = set()
    for stat_key, description, pattern in CORPUS_CLAIM_PATTERNS:
        for match in pattern.finditer(text):
            authoritative = resolve_stat(data, stat_key)
            if authoritative is None:
                continue  # Stat absent from data.js — unknown, reported as skipped, not passed.
            claimed = _normalise_number(match.group("n"))
            if claimed is None:
                continue
            if _values_agree(claimed, authoritative, kind="count"):
                continue
            # Two patterns can overlap on one phrase ("215 executed stories" matches both the
            # linked/executed rule and, in other copy, the "stories across" rule). Report the
            # position once: a reader fixing the page fixes one number, not two findings.
            fingerprint = (match.start("n"), stat_key)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            context = _context_window(text, match.start(), match.end())
            excerpt = context if not source_label else f"[{source_label}] {context}"
            findings.append(
                ConsistencyFinding(
                    check="prose_claim",
                    page=page,
                    line=line_of(match.start()),
                    stat_key=stat_key,
                    claimed=claimed,
                    authoritative=float(authoritative),
                    excerpt=f"({description}) {excerpt}"[:220],
                )
            )
    return findings


def check_prose_claims(
    html: str, data: Mapping[str, Any], *, page: str
) -> list[ConsistencyFinding]:
    """Check B — hard-coded corpus totals in reader-facing prose and in crawler metadata.

    Runs :data:`CORPUS_CLAIM_PATTERNS` over two surfaces:

    1. the page body with ``<script>``/``<style>`` blocks removed and tags blanked, so
       ``<span data-stat="story_sessions">1,027</span> story sessions`` reads as the sentence a
       human reads rather than as markup;
    2. the ``description``/``og:``/``twitter:`` meta attribute values, which never hydrate and
       are the version of the claim that reaches search results and link previews — the copies
       that no client-side fix can reach, and where index.html's stale 1,067 survived longest.

    Only the declared phrasings are checked; see :data:`CORPUS_CLAIM_PATTERNS` for why the table
    is positive rather than exemption-based, and how check A covers the rest.
    """
    findings: list[ConsistencyFinding] = []

    # Surface 1 — the body, reduced to reader-visible text with an offset map so every finding
    # cites a line of the real file.
    body, offsets = _strip_tags_with_map(html)
    findings.extend(
        _scan_prose_claims(
            body,
            data,
            page=page,
            line_of=lambda off: html.count("\n", 0, offsets[min(off, len(offsets) - 1)]) + 1,
        )
    )

    # Surface 2 — crawler-visible metadata, attributed to the meta tag's own line.
    for meta in _META_CONTENT_RE.finditer(html):
        meta_line = html.count("\n", 0, meta.start()) + 1
        findings.extend(
            _scan_prose_claims(
                meta.group("text"),
                data,
                page=page,
                line_of=lambda _off, line=meta_line: line,
                source_label=meta.group("which"),
            )
        )
    return findings



# ── The site-wide gate ───────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ConsistencyReport:
    """The result of checking every page against ``data.js``."""

    findings: tuple[ConsistencyFinding, ...]
    #: Pages actually scanned, in a stable order — so "it passed" can be distinguished from
    #: "it scanned nothing", which would otherwise look identical.
    pages: tuple[str, ...]
    #: ``data-stat`` keys encountered that this module cannot resolve. Reported rather than
    #: hidden: an unresolvable key is unchecked coverage, and silent unchecked coverage is how a
    #: gate becomes decorative.
    skipped_keys: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        """True when no page disagrees with the data. An empty page list is NOT ok."""
        return not self.findings and bool(self.pages)

    def summary(self) -> str:
        """A short human line for the CLI."""
        if not self.pages:
            return "HTML consistency: no pages scanned (is apps/website/ present?)"
        if self.ok:
            return f"HTML consistency: {len(self.pages)} pages agree with data.js"
        return f"HTML consistency: {len(self.findings)} disagreement(s) across {len(self.pages)} pages"


def site_pages(site_root: Path | str | None = None) -> list[Path]:
    """Every HTML page under the site root, sorted.

    Discovered rather than listed. The mandate says "every HTML page", and a hard-coded page
    list would silently exempt the next page someone adds — which is the same failure as the
    hard-coded number, one level up.
    """
    root = Path(site_root) if site_root is not None else SITE_ROOT
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*.html") if p.is_file())


def check_site_consistency(
    *,
    site_root: Path | str | None = None,
    data: Mapping[str, Any] | None = None,
    data_js_path: Path | str | None = None,
) -> ConsistencyReport:
    """Verify that every HTML page agrees with ``data.js``. The publication gate's third step.

    Two independent checks run over each page, and neither subsumes the other:

    * **A — ``data-stat`` fallbacks** (:func:`check_data_stat_fallbacks`). Exact: the attribute
      names the stat, so the comparison is unambiguous. Covers the pre-hydration text a scraper
      or a JS-disabled reader sees. Misses claims written in plain prose.
    * **B — prose claims** (:func:`check_prose_claims`). A net over "N sessions"/"N stories"
      phrasings in the body and in crawler metadata, with a declared exemption table for the
      site's other denominators. Covers the editorial copy — which is exactly where the 1,067
      lived — but is necessarily judgement-based where A is mechanical.

    Returns a report rather than raising, so a caller can print every disagreement at once. A
    publication run turns a non-``ok`` report into a refusal (see
    :func:`assert_publication_ready`).
    """
    resolved = data if data is not None else load_data_js(data_js_path)
    pages = site_pages(site_root)
    root = Path(site_root) if site_root is not None else SITE_ROOT
    findings: list[ConsistencyFinding] = []
    skipped: set[str] = set()
    for page in pages:
        html = page.read_text(encoding="utf-8", errors="replace")
        try:
            label = str(page.relative_to(root))
        except ValueError:  # pragma: no cover - page is always under root by construction
            label = page.name
        findings.extend(check_data_stat_fallbacks(html, resolved, page=label))
        findings.extend(check_prose_claims(html, resolved, page=label))
        for match in _DATA_STAT_RE.finditer(html):
            if match.group("key") not in _STATS_BY_KEY and match.group("body").strip():
                skipped.add(match.group("key"))
    return ConsistencyReport(
        findings=tuple(findings),
        pages=tuple(str(p.relative_to(root)) for p in pages),
        skipped_keys=tuple(sorted(skipped)),
    )


# ── The projection gate ──────────────────────────────────────────────────────────────────────

#: The projections a publication depends on. ``ledger`` is excluded deliberately: it projects the
#: run ledger, which the website does not read, so gating the site on it would refuse
#: publications for a reason unrelated to what is being published. Named here rather than
#: derived from ``pw.PROJECTIONS`` so the exclusion is a decision on the record.
PUBLICATION_PROJECTIONS: tuple[str, ...] = ("chroma", "neo4j", "registry")


@dataclass(frozen=True)
class ProjectionGate:
    """The verdict of the projection freshness check, with the evidence that produced it."""

    ok: bool
    #: ``pw.projection_report`` entries for the publication projections, in a stable order.
    report: tuple[dict[str, Any], ...]
    #: One line per projection that failed the policy — what the operator must fix.
    blockers: tuple[str, ...] = ()
    #: The lag block that goes into the receipt: ``{registry: 0, chroma: 0, neo4j: 0}``.
    lag: Mapping[str, int | None] = field(default_factory=dict)
    #: The confirmed stream frontier per projection — the receipt's
    #: ``source_event_watermarks``, i.e. the exact point in the event stream this data reflects.
    watermarks: Mapping[str, str] = field(default_factory=dict)


def verify_projections(
    db: ControlDB,
    *,
    projections: Sequence[str] = PUBLICATION_PROJECTIONS,
    max_lag: int = 0,
    allow_unreported: bool = False,
    max_age_seconds: int | None = None,
    now: datetime | None = None,
) -> ProjectionGate:
    """Check that every publication-relevant projection is fresh enough to publish from.

    The default policy is the strict one the mandate names: **lag 0, everywhere**. ``max_lag``
    relaxes it for the case where an operator knowingly publishes ahead of a slow projector; the
    value used is recorded in the receipt, so a relaxed gate is visible afterwards rather than
    indistinguishable from a strict one.

    Three ways to fail, all treated as blocking:

    * ``lagging`` — behind the stream head by more than ``max_lag``;
    * ``stale`` / ``failing`` — the projector has not reported inside the staleness window, or
      reported an error. A ``stale`` projection's recorded lag is *not believed*: a zero written
      four hours ago describes four-hour-old reality;
    * ``unknown`` — never reported, or lag not computable. Refused by default, because
      publishing from a projector nobody can vouch for is not safer than publishing from one
      known to be behind. ``allow_unreported`` exists for a checkout that has genuinely never run
      a projector (a fresh clone building the site locally), and is likewise recorded.
    """
    report = pw.projection_report(
        db, projections=projections, max_age_seconds=max_age_seconds, now=now
    )
    blockers: list[str] = []
    lag: dict[str, int | None] = {}
    watermarks: dict[str, str] = {}
    for entry in report:
        name = entry["projection"]
        health = entry["health"]
        lag[name] = entry["lag_events"]
        watermarks[name] = entry.get("last_event_id") or ""
        if not entry.get("reported"):
            if not allow_unreported:
                blockers.append(
                    f"{name}: never reported (health=unknown) — no projector has confirmed an "
                    "event, so the data's provenance cannot be established"
                )
            continue
        if health in (pw.ProjectionHealth.STALE.value, pw.ProjectionHealth.FAILING.value):
            age = entry.get("age_seconds")
            detail = [f"last success {entry.get('last_success_at') or 'never'}"]
            if age is not None:
                detail.append(f"{age}s ago")
            if entry.get("last_error"):
                detail.append(f"error: {entry['last_error']}")
            blockers.append(
                f"{name}: health={health} ({'; '.join(detail)}) — its recorded lag describes "
                "old reality and must not be believed"
            )
            continue
        events = entry["lag_events"]
        if events is None:
            if not allow_unreported:
                blockers.append(f"{name}: lag is unknown (not computable) — refusing to guess 0")
            continue
        if events > max_lag:
            blockers.append(f"{name}: lag {events} > max_lag {max_lag} — projection is behind")
    return ProjectionGate(
        ok=not blockers,
        report=tuple(report),
        blockers=tuple(blockers),
        lag=lag,
        watermarks=watermarks,
    )


# ── The receipt ──────────────────────────────────────────────────────────────────────────────

#: The receipt's mandated fields, in the order the mandate lists them.
RECEIPT_REQUIRED_KEYS: tuple[str, ...] = (
    "schema",
    "repo_sha",
    "data_manifest_sha256",
    "data_js_sha256",
    "sessions_total",
    "generated_at",
    "source_event_watermarks",
)

#: The same contract as JSON Schema, for consumers that have ``jsonschema`` available. Kept
#: beside :func:`validate_receipt` on purpose: two independent encodings of one contract, so a
#: receipt that satisfies only the validator written by the same hand as the builder cannot pass.
PUBLICATION_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": SCHEMA_ID,
    "type": "object",
    "required": list(RECEIPT_REQUIRED_KEYS),
    "properties": {
        "schema": {"const": SCHEMA_ID},
        "repo_sha": {"type": "string", "minLength": 7},
        "data_manifest_sha256": {"type": "string"},
        "data_js_sha256": {"type": "string", "minLength": 64, "maxLength": 64},
        # Integer or null — null means "the build did not report it". Never 0: a zero corpus
        # that reads as measured is the exact lie this receipt exists to prevent.
        "sessions_total": {"type": ["integer", "null"], "minimum": 0},
        "generated_at": {"type": "string", "minLength": 10},
        "source_event_watermarks": {
            "type": "object",
            "required": list(PUBLICATION_PROJECTIONS),
            "properties": {p: {"type": ["string", "null"]} for p in PUBLICATION_PROJECTIONS},
            "additionalProperties": {"type": ["string", "null"]},
        },
        # Optional, additive: the policy the gate ran under and what it saw. Not in the mandated
        # field list, but a receipt that cannot say whether its gate was strict or relaxed is a
        # receipt you have to trust rather than check.
        "projection_lag": {"type": "object"},
        "projection_policy": {"type": "object"},
        "html_consistency": {"type": "object"},
        "hosts": {"type": "array"},
        "operator": {"type": "string"},
        "run_id": {"type": "string"},
        "dry_run": {"type": "boolean"},
    },
}


def build_receipt(
    *,
    repo_sha: str,
    data: Mapping[str, Any] | None = None,
    data_js_path: Path | str | None = None,
    manifest_path: Path | str | None = None,
    projection_gate: ProjectionGate | None = None,
    consistency: ConsistencyReport | None = None,
    operator: str = "",
    run_id: str = "",
    dry_run: bool = False,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Assemble the ``publication/v1`` receipt.

    Built AFTER the artifacts exist and BEFORE anything is deployed — that ordering is the whole
    point. The receipt describes a tree that has already been built and checked, so what gets
    deployed and what got recorded cannot diverge.

    ``sessions_total`` comes from the data file rather than from an argument, for the same
    reason the control-database row derives its columns from the receipt: one number, one
    source. It is ``None``, never ``0``, when the data does not carry it.
    """
    js_path = Path(data_js_path) if data_js_path is not None else DATA_JS
    manifest = Path(manifest_path) if manifest_path is not None else DATA_MANIFEST
    resolved = data if data is not None else load_data_js(js_path)
    sessions = resolve_stat(resolved, "sessions")
    receipt: dict[str, Any] = {
        "schema": SCHEMA_ID,
        "repo_sha": repo_sha,
        "data_manifest_sha256": sha256_file(manifest),
        "data_js_sha256": sha256_file(js_path),
        "sessions_total": int(sessions) if sessions is not None else None,
        "generated_at": generated_at or _now_iso(),
        "source_event_watermarks": dict(projection_gate.watermarks) if projection_gate else {
            p: None for p in PUBLICATION_PROJECTIONS
        },
    }
    if projection_gate is not None:
        receipt["projection_lag"] = dict(projection_gate.lag)
        receipt["projection_policy"] = {"ok": projection_gate.ok}
    if consistency is not None:
        receipt["html_consistency"] = {
            "ok": consistency.ok,
            "pages": len(consistency.pages),
            "findings": len(consistency.findings),
            "skipped_keys": list(consistency.skipped_keys),
        }
    receipt["hosts"] = [
        {"role": h.role, "project": h.project, "url": h.url} for h in FIREBASE_HOSTS
    ]
    if operator:
        receipt["operator"] = operator
    if run_id:
        receipt["run_id"] = run_id
    if dry_run:
        receipt["dry_run"] = True
    return receipt


def validate_receipt(receipt: Mapping[str, Any]) -> list[str]:
    """Validate a receipt against ``publication/v1`` WITHOUT requiring ``jsonschema``.

    The dependency-free half of the contract, mirroring ``control_status.validate_packet``. A
    gate that could only run where an optional dependency happens to be installed is a gate that
    is off in exactly the environment nobody checked.

    Returns a list of human-readable problems; empty means valid.
    """
    problems: list[str] = []
    if not isinstance(receipt, Mapping):
        return ["receipt is not an object"]
    for key in RECEIPT_REQUIRED_KEYS:
        if key not in receipt:
            problems.append(f"missing required key: {key}")
    if receipt.get("schema") != SCHEMA_ID:
        problems.append(f"schema must be {SCHEMA_ID!r}, got {receipt.get('schema')!r}")
    repo_sha = receipt.get("repo_sha")
    if not isinstance(repo_sha, str) or len(repo_sha) < 7:
        problems.append("repo_sha must be a sha string of at least 7 characters")
    js_sha = receipt.get("data_js_sha256")
    if not isinstance(js_sha, str) or len(js_sha) != 64:
        problems.append("data_js_sha256 must be a 64-character sha256 hex digest")
    sessions = receipt.get("sessions_total")
    if sessions is not None and (not isinstance(sessions, int) or isinstance(sessions, bool)):
        problems.append("sessions_total must be an integer or null (never a string)")
    generated = receipt.get("generated_at")
    if not isinstance(generated, str) or len(generated) < 10:
        problems.append("generated_at must be an ISO-8601 timestamp string")
    watermarks = receipt.get("source_event_watermarks")
    if not isinstance(watermarks, Mapping):
        problems.append("source_event_watermarks must be an object")
    else:
        for projection in PUBLICATION_PROJECTIONS:
            if projection not in watermarks:
                problems.append(f"source_event_watermarks missing projection: {projection}")
            else:
                value = watermarks[projection]
                if value is not None and not isinstance(value, str):
                    problems.append(
                        f"source_event_watermarks.{projection} must be a string or null"
                    )
    return problems


def receipt_sha256(receipt: Mapping[str, Any]) -> str:
    """The digest of the canonical serialisation — the receipt's own identity."""
    return hashlib.sha256(serialise_receipt(receipt).encode("utf-8")).hexdigest()


def serialise_receipt(receipt: Mapping[str, Any]) -> str:
    """Canonical JSON for a receipt: sorted keys, two-space indent, trailing newline.

    Canonical because the digest is taken over it and because two receipts describing the same
    publication should be byte-identical — a diff between them should mean a difference in what
    was published, never a difference in key order.
    """
    return json.dumps(receipt, indent=2, sort_keys=True) + "\n"


def write_receipt(receipt: Mapping[str, Any], *, directory: Path | str | None = None) -> Path:
    """Archive a receipt on disk, named by its own digest. Returns the path written.

    Content-addressed, so re-writing an identical receipt is idempotent and two different
    publications can never collide on a filename.
    """
    target_dir = Path(directory) if directory is not None else RECEIPT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"publication_{receipt_sha256(receipt)[:16]}.json"
    path.write_text(serialise_receipt(receipt), encoding="utf-8")
    return path


# ── The composed gate ────────────────────────────────────────────────────────────────────────


def assert_publication_ready(
    *,
    projection_gate: ProjectionGate,
    consistency: ConsistencyReport,
    receipt: Mapping[str, Any],
) -> None:
    """Raise :class:`PublicationError` unless all three preconditions hold.

    The single choke point every publication path goes through, so "was this verified?" has one
    answer rather than one per caller. Every failure is reported together — an operator fixing a
    stale projection should learn about a contradictory page in the same run, not on the next
    attempt.
    """
    problems: list[str] = []
    if not projection_gate.ok:
        problems.append(
            "projections are not publishable:\n  - " + "\n  - ".join(projection_gate.blockers)
        )
    if not consistency.ok:
        if not consistency.pages:
            problems.append("HTML consistency: no pages were scanned")
        else:
            problems.append(
                f"{len(consistency.findings)} page(s) contradict data.js:\n  - "
                + "\n  - ".join(f.describe() for f in consistency.findings)
            )
    receipt_problems = validate_receipt(receipt)
    if receipt_problems:
        problems.append("receipt is not valid publication/v1:\n  - " + "\n  - ".join(receipt_problems))
    if problems:
        raise PublicationError("\n".join(problems))


def format_consistency_report(report: ConsistencyReport, *, limit: int | None = None) -> str:
    """Render a consistency report for a terminal, newest problems first.

    ``limit`` truncates the finding list but always says how many were hidden — a truncated list
    that does not admit it is truncated reads as a complete one.
    """
    lines = [report.summary()]
    findings: Sequence[ConsistencyFinding] = report.findings
    shown = findings if limit is None else findings[:limit]
    lines.extend(f"  - {finding.describe()}" for finding in shown)
    if limit is not None and len(findings) > limit:
        lines.append(f"  ... and {len(findings) - limit} more")
    if report.skipped_keys:
        lines.append(
            "  note: data-stat keys not modelled by this check (unverified coverage): "
            + ", ".join(report.skipped_keys)
        )
    return "\n".join(lines)


def format_projection_gate(gate: ProjectionGate) -> str:
    """Render the projection gate for a terminal."""
    lines = ["Projections: " + ("OK" if gate.ok else "BLOCKED")]
    for entry in gate.report:
        lines.append(
            f"  - {entry['projection']}: health={entry['health']} "
            f"lag={entry['lag_events']} last_success={entry.get('last_success_at') or 'never'}"
        )
    lines.extend(f"  ! {blocker}" for blocker in gate.blockers)
    return "\n".join(lines)


__all__ = [
    "CORPUS_CLAIM_PATTERNS",
    "CORPUS_STATS",
    "DATA_JS",
    "DATA_MANIFEST",
    "FIREBASE_HOSTS",
    "PUBLICATION_PROJECTIONS",
    "PUBLICATION_SCHEMA",
    "RECEIPT_DIR",
    "RECEIPT_REQUIRED_KEYS",
    "SCHEMA_ID",
    "SITE_ROOT",
    "ConsistencyFinding",
    "ConsistencyReport",
    "CorpusStat",
    "FirebaseHost",
    "ProjectionGate",
    "PublicationError",
    "assert_publication_ready",
    "build_receipt",
    "check_data_stat_fallbacks",
    "check_prose_claims",
    "check_site_consistency",
    "format_consistency_report",
    "format_projection_gate",
    "load_data_js",
    "receipt_sha256",
    "resolve_stat",
    "serialise_receipt",
    "sha256_file",
    "site_pages",
    "validate_receipt",
    "verify_projections",
    "write_receipt",
]
