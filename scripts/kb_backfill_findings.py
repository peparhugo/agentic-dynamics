"""Deterministic backfill of the knowledge-base finding layer (kb_finding_layer k2).

THE PAST ENTERS DETERMINISTICALLY. The completed waves' conclusions (adversarial verdicts,
the 17-spec shift, the evidence-wave results) were never emitted into the KB — the finding
producer was opt-in until k1, so the distilled layer holds only old measured-finding shells
and the waves' distilled conclusions live in ``docs/reviews/`` markdown + the run ledgers.
This script projects those conclusions into the finding layer WITHOUT an LLM: every field is a
deterministic function of the on-disk artifacts.

Source corpus (scanned under ``--root`` / ``--corpus-root``):

* ``docs/reviews/*adversarial*.md`` + ``*_adversary.md`` — the verdict-bearing review docs.
  Verdict lines + finding-table rows are parsed with fixed patterns (no model call).
* ``docs/reviews/*preregistration.md`` — the spec-SHA256 pin for the wave.
* ``docs/reviews/*_known_safe.md`` — the complement ("attacks that did not falsify").
* run ledgers ``experiments/results/workflows/<wave>/*.json`` — terminal run disposition,
  ``git_sha``/``spec_id``, and the run's own conclusion (``ok``/``state``).

Per completed wave, ONE finding record is derived with the shape the k2 mandate fixes:

    {wave name, spec sha, verdict (merge-ready / not / clean), finding count,
     the recorded residual list, the conclusions}

* wave name        — the spec name (frontmatter ``spec:`` of a review doc, else the review-doc
  stem, else the run-ledger ``spec_name``).
* spec sha         — the preregistration's ``Spec SHA256`` pin when the wave has one, else the
  latest run ledger's ``git_sha``, else ``""``.
* verdict          — deterministic classifier over the review doc(s): ``merge-ready`` /
  ``not`` / ``clean`` (see :func:`_classify_verdict`); a wave with no review doc derives its
  verdict from the run ledger's terminal disposition (``succeeded`` -> ``clean``,
  ``failed``/``cancelled`` -> ``not``) so every completed wave gets a value.
* finding count    — the number of finding-table rows / ``F#`` markers in the adversarial doc,
  else ``0`` with the count line recorded verbatim in the text.
* residual list    — the finding-table ``residual scope`` / ``Fix-or-record`` cells and any
  ``Accepted limitations`` rows, joined deterministically.
* conclusions      — the doc's verdict sentence + the clean-sweep/known-safe complement + the
  run's own goal prefix, assembled as the record ``text``.

Identity / idempotence: the record is built through the canonical factory
(``build_record_from_parts``) with ``logical_locator = "wave:<name>"``,
``source_uri`` = the primary review doc (else a ``file://experiments/results/workflows/<wave>/``
namespace locator), ``revision`` = the spec sha, and ``extractor_version`` =
``wave-backfill/v1``. ``knowledge_id`` therefore folds wave name + spec sha + derived content:
re-running against unchanged artifacts yields the same ids, and the emit step skips ids that
are already present in ``registry_index.jsonl`` / the artifact dir (a rerun is a no-op).

Emit path (mirrors ``kb_produce_campaign_evidence``): durable artifact
``experiments/results/kb/<knowledge_id>.json`` FIRST, then the pointer event onto the shared
DB-2 stream (``FINOPS_KB_WRITE=1``), then the compact registry row appended at emit time so the
record is registry-visible immediately (no dependency on a live kb-registry consumer). A
downed Redis stream does NOT fail the backfill: the durable artifact + registry row are the
record; the event is the projection nudge. ``--dry-run`` derives and prints without writing.

Invocation:
    python3 scripts/kb_backfill_findings.py [--root REPO] [--corpus-root REPO] [--dry-run]
        [--limit N] [--only WAVE,...]

``--root`` defaults to this checkout; ``--corpus-root`` defaults to ``--root`` and lets the
phase point the *scan* at the machine-local KB host while emitting into the wave checkout.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from agentic_dynamics.knowledge import knowledge_stream as ks  # noqa: E402
from agentic_dynamics.knowledge.knowledge_ingestion import (  # noqa: E402
    Authority,
    KnowledgeRecord,
    build_record_from_parts,
    record_to_artifact,
    record_to_event,
)

#: Extractor generation for the deterministic wave-conclusion backfill (kb_finding_layer k2).
#: Folds into ``knowledge_id`` so a changed extraction rule re-keys (never silently
#: overwrites) the previous generation's records.
EXTRACTOR_VERSION = "wave-backfill/v1"

#: Redis write-guard env + stream defaults (mirror kb_produce_campaign_evidence).
REDIS_HOST = os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6380"))

#: Review-doc filename suffixes this backfill reads, and the role each plays.
_ADVERSARIAL_SUFFIXES = ("_adversarial.md", "_adversary.md")
_KNOWN_SAFE_SUFFIX = "_known_safe.md"
_PREREG_SUFFIX = "_preregistration.md"

#: Verdict vocabulary the mandate fixes: ``merge-ready`` / ``not`` / ``clean``.
VERDICTS = ("merge-ready", "not-merge-ready", "clean")
#: F1 fix (deep review 2026-09-04): the classifier's bare ``"not"`` rendered as the
#: ambiguous word "not" in every retrieval surface ("verdict not"). The readable label is
#: ``not-merge-ready`` — a retrieval surface should answer with the full disposition, never
#: the truncated classifier token.
VERDICT_LABELS = {"not": "not-merge-ready", "merge-ready": "merge-ready", "clean": "clean"}


# ── Wave discovery (deterministic) ──────────────────────────────


def _doc_role(path: Path) -> str | None:
    """Classify a docs/reviews filename: adversarial | known_safe | prereg | None."""
    name = path.name
    if name.endswith(_ADVERSARIAL_SUFFIXES):
        return "adversarial"
    if name.endswith(_KNOWN_SAFE_SUFFIX):
        return "known_safe"
    if name.endswith(_PREREG_SUFFIX):
        return "prereg"
    return None


def _doc_stem(name: str) -> str:
    """The wave-name carrier of a review doc filename (strip the role suffix)."""
    for suffix in (*_ADVERSARIAL_SUFFIXES, _KNOWN_SAFE_SUFFIX, _PREREG_SUFFIX):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name[: -len(".md")]


def _frontmatter_spec(text: str) -> str:
    """Return the frontmatter ``spec:`` value when present (the canonical wave name)."""
    m = re.search(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return ""
    for line in m.group(1).splitlines():
        mm = re.match(r"^\s*spec\s*:\s*(.+?)\s*$", line)
        if mm:
            return mm.group(1).strip("`\"' ")
    return ""


def discover_review_waves(reviews_dir: Path) -> dict[str, dict[str, Path]]:
    """Map wave name -> {role: review-doc path} from ``docs/reviews`` on disk.

    The wave name is the review doc's frontmatter ``spec:`` when present, else the filename
    stem. Every adversarial/adversary/known_safe/prereg doc names its wave deterministically.
    """
    waves: dict[str, dict[str, Path]] = {}
    if not reviews_dir.is_dir():
        return waves
    for path in sorted(reviews_dir.glob("*.md")):
        role = _doc_role(path)
        if role is None:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        wave = _frontmatter_spec(text) or _doc_stem(path.name)
        waves.setdefault(wave, {})[role] = path
    return waves


def discover_ledger_waves(workflows_dir: Path) -> dict[str, dict[str, Any]]:
    """Map wave name -> ledger summary from ``experiments/results/workflows/<wave>/*.json``.

    A wave is present when its directory holds at least one parseable run ledger. The summary
    keeps the LAST run's ``state``/``ok``/``git_sha``/``spec_id``/``goal`` plus the distinct
    terminal dispositions seen, so a wave whose final run is ``awaiting`` but whose family
    earlier reached a verdict is still recorded honestly.
    """
    waves: dict[str, dict[str, Any]] = {}
    if not workflows_dir.is_dir():
        return waves
    for wave_dir in sorted(workflows_dir.iterdir()):
        if not wave_dir.is_dir():
            continue
        ledgers = sorted(wave_dir.glob("*.json"))
        if not ledgers:
            continue
        summary: dict[str, Any] = {"ledgers": [], "states": set(), "ok_values": set()}
        for ledger in ledgers:
            try:
                payload = json.loads(ledger.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(payload, dict):
                continue
            state = payload.get("state")
            if state:
                summary["states"].add(str(state))
            ok = payload.get("ok")
            if ok is not None:
                summary["ok_values"].add(bool(ok))
            summary["ledgers"].append(
                {
                    "path": str(ledger.relative_to(ledger.parent.parent.parent.parent)),
                    "state": state,
                    "ok": ok,
                    "git_sha": payload.get("git_sha"),
                    "spec_id": payload.get("spec_id"),
                    "goal": (payload.get("goal") or "")[:200],
                }
            )
        if not summary["ledgers"]:
            continue
        summary["states"] = sorted(summary["states"])
        summary["ok_values"] = sorted(summary["ok_values"])
        waves[wave_dir.name] = summary
    return waves


TERMINAL_STATES = {"succeeded", "failed", "cancelled", "awaiting_approval"}


def is_completed_wave(review_docs: dict[str, Path], ledger: dict[str, Any] | None) -> bool:
    """Return True when a wave COMPLETED (a review reached OR a run terminated).

    The backfill derives one finding per COMPLETED wave, so the definition must be
    deterministic and match the spec's "completed waves" count:

    * a wave with an adversarial/adversary review doc reached the review phase — by
      definition it completed (a review is only written after the wave's phases ran);
      a known-safe doc is the PASS-complement of an adversarial review and likewise marks
      completion; a PREREGISTRATION alone does NOT (it pins the wave at launch, before any
      verdict exists — kb_finding_layer's own prereg is the live example);
    * a wave with run ledgers is completed when at least one run recorded a terminal
      disposition (``state`` in the terminal set, or an ``ok`` boolean — older ledgers carry
      ``ok`` instead of ``state``), so a never-finished partial run does NOT fabricate a
      completed finding.

    ``awaiting_approval`` counts as terminal (the run stopped at a designed checkpoint and
    the ledger records it) — the record carries the honest state and the "not" verdict.
    """
    if "adversarial" in review_docs or "known_safe" in review_docs:
        return True
    if not ledger:
        return False
    return bool(ledger.get("states")) or bool(ledger.get("ok_values"))


def union_waves(review_waves: dict, ledger_waves: dict) -> list[str]:
    """Every wave named by a review doc OR present as a run-ledger directory, sorted."""
    return sorted(set(review_waves) | set(ledger_waves))


def completed_waves(
    review_waves: dict[str, dict[str, Path]], ledger_waves: dict[str, dict[str, Any]]
) -> list[str]:
    """The completed-wave set (the count VERIFY (c) asserts N >= against)."""
    return sorted(
        w for w in union_waves(review_waves, ledger_waves)
        if is_completed_wave(review_waves.get(w, {}), ledger_waves.get(w))
    )


# ── Verdict + finding extraction (deterministic, no LLM) ────────


def _verdict_signals(text: str) -> dict[str, bool]:
    """Boolean signal map over a review doc's lowercased text.

    Signals are deliberately coarse and independent: the classifier below combines them in a
    fixed precedence so a doc that says both "PASS" and "not merge-ready" resolves honestly
    (a merge-block outranks a positive re-verification).
    """
    t = text.lower()
    return {
        "merge_ready": bool(re.search(r"merge[- ]?ready", t)),
        "not_merge_ready": bool(re.search(r"not merge[- ]?ready|merge[- ]?blocked", t)),
        "verdict_fail": bool(re.search(r"\bverdict:?\s*fail\b|release verdict[^\n]*fail", t)),
        "verdict_pass": bool(re.search(r"\bverdict:?\s*pass\b|release verdict[^\n]*pass", t)),
        "passfail_fail": bool(re.search(r"pass\s*/\s*fail[^\n]*:\s*fail", t)),
        "passfail_pass": bool(re.search(r"pass\s*/\s*fail[^\n]*:\s*pass", t)),
        "no_failed_finding": bool(re.search(r"no failed finding|0 findings?|no findings?", t)),
        "clean_sweep": bool(re.search(r"clean sweep|failed to falsify|not falsified", t)),
        "blocker": bool(
            re.search(r"merge[- ]?blocker|blocking the merge|blocked on", t)
        ),
    }


def classify_verdict(text: str, *, ledger_state: str | None = None) -> str:
    """Deterministic verdict classifier -> one of ``merge-ready`` / ``not`` / ``clean``.

    Fixed precedence (documented in the module docstring):
      1. a merge-block / not-merge-ready / FAIL verdict signal -> ``not``;
      2. a merge-ready signal -> ``merge-ready``;
      3. a PASS / clean-sweep / no-failed-finding signal -> ``clean``;
      4. with no review doc, the run ledger's terminal disposition decides
         (``succeeded`` -> ``clean``, ``failed``/``cancelled`` -> ``not``,
         ``awaiting_approval`` -> ``not`` — a paused run is not a completed verdict);
      5. fallback ``clean`` is NEVER fabricated: no signal at all returns ``clean`` only when
         a positive run disposition backs it, else ``not`` (an unverdictable wave must not
         read as merge-ready).
    """
    signals = _verdict_signals(text)
    if (
        signals["not_merge_ready"]
        or signals["verdict_fail"]
        or signals["passfail_fail"]
        or signals["blocker"]
    ):
        return "not"
    if signals["merge_ready"] and not signals["verdict_fail"]:
        return "merge-ready"
    if signals["verdict_pass"] or signals["passfail_pass"] or signals["clean_sweep"]:
        return "clean"
    if signals["no_failed_finding"]:
        return "clean"
    # No usable signal from prose — consult the run ledger's own disposition.
    if ledger_state == "succeeded":
        return "clean"
    if ledger_state in ("failed", "cancelled"):
        return "not"
    if ledger_state == "awaiting_approval":
        return "not"
    return "not"


def finding_count(text: str) -> int:
    """Deterministic finding-count extraction from an adversarial review doc.

    Tried in order: an explicit ``Findings: N`` / ``N findings`` line; then the number of
    finding-table rows whose first cell is a ``F#``/``A#``/``R#``/``G#`` marker (wide or
    heading shapes); else 0 (a clean-sweep doc genuinely records none).
    """
    m = re.search(r"findings?:?\s*(\d+)\b", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    table_rows = re.findall(
        r"^\s*\|\s*\*?\*?[A-Za-z]-?A?\d+\s*\*?\*?\|", text, re.MULTILINE
    )
    if table_rows:
        return len(table_rows)
    heading_rows = re.findall(r"^#{2,4}\s+F-?A?\d+\b", text, re.MULTILINE)
    if heading_rows:
        return len(heading_rows)
    return 0


def residual_list(text: str, *, limit: int = 6) -> list[str]:
    """Deterministic residual extraction: finding-table residual cells + accepted limitations.

    Residual signals are captured from the finding table's trailing cells and from
    ``Accepted limitations`` / ``Residual`` / ``Residual risk`` bullets, deduplicated and
    bounded so the record text stays a retrieval surface rather than a transcript dump.
    Table header cells (``Fix-or-record`` / ``Residual scope`` column labels) are never
    residuals — a cell qualifies only when it carries actual prose about a limitation.
    """
    residuals: list[str] = []
    # Words that label a finding-table column but carry no residual substance. A cell that IS
    # exactly (or a bare-bold variant of) one of these labels is a header, never a residual.
    header_labels = {
        "fix-or-record", "residual scope", "residual", "fix or record",
        "disposition", "severity", "re-verification evidence", "residual risk",
        "finding", "attack", "re-verification", "evidence", "result", "#",
        "fix / record", "fix-or-record (decision)",
    }
    # Trailing finding-table cells that name a residual ("RECORD", "accepted limitation",
    # "residual", "Fix-or-record", "not fixed").
    for row in re.findall(
        r"^\s*\|[^\n]*\|[^\n]*\|[^\n]*\|[^\n]*\|[^\n]*\|[^\n]*$", text, re.MULTILINE
    ):
        cells = [c.strip() for c in row.strip("|").split("|")]
        for cell in cells:
            label = cell.lower().strip("*_ `")
            # Drop the header row and any pure-label cell.
            if label in header_labels or len(label) <= 8:
                continue
            low = cell.lower()
            if any(
                k in low
                for k in ("accepted limitation", "record", "residual", "not fixed", "limitation")
            ):
                residuals.append(re.sub(r"\s+", " ", cell)[:220])
    # Accepted-limitations / residual bullets under a section heading.
    for section in re.findall(
        r"^#{2,4}\s*(?:accepted limitations?|residual[^\n]*|re-stated verdict)[^\n]*\n(.*?)(?=^#{1,4}|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    ):
        for line in section.splitlines():
            s = line.strip().lstrip("*-–—>")
            if s and len(s) > 12 and not s.startswith("|"):
                residuals.append(re.sub(r"\s+", " ", s)[:220])
    seen: set[str] = set()
    out: list[str] = []
    for item in residuals:
        key = item[:80]
        if key not in seen:
            seen.add(key)
            out.append(item)
        if len(out) >= limit:
            break
    return out


def spec_sha_from_prereg(path: Path | None) -> str:
    """Extract the pinned spec SHA256 from a preregistration pin table, else ``""``."""
    if path is None or not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"Spec\s+\*\*SHA256\*\*\s*\|\s*`?([0-9a-f]{64})`?", text)
    if m:
        return m.group(1)
    m = re.search(r"SHA256\s*\|\s*`?([0-9a-f]{64})`?", text)
    return m.group(1) if m else ""


def _conclusion_lines(text: str) -> str:
    """Deterministic conclusion extraction: the doc's verdict sentences.

    Two layers, in order:

    1. Explicit verdict markers — a bold ``Verdict:``/``VERDICT:``/``MERGE-READY``/
       ``PASS/FAIL:`` sentence, or an ``Overall adversarial verdict`` line. These are the
       distilled conclusion a retrieval surface should answer with, wherever they sit in the
       doc.
    2. The trailing verdict/LOG region — when no explicit marker exists, the text after the
       LAST ``Release verdict``/``Re-stated verdict``/``Verdict``/``Log`` heading, first
       non-table paragraph, normalized.

    Both are bounded (a finding record is a retrieval surface, not a transcript dump) and
    never hand-written.
    """
    # 1. Explicit verdict sentence: find a bold ``Verdict:``/``VERDICT:``/``MERGE-READY`` /
    #    ``PASS/FAIL:`` marker and capture to the END of the enclosing sentence (the ``—``
    #    continuation after the closing ``**`` belongs to the verdict, not a separate thought).
    #    The capture is bounded so a long release-verdict paragraph still yields the lead.
    marker = re.compile(
        r"\*\*?\s*(?:VERDICT|Verdict|Release verdict|Overall adversarial verdict)\s*:\s*"
        r"(?:PASS|FAIL|merge-ready|not merge-ready|failed to falsify)",
        re.IGNORECASE,
    )
    m = marker.search(text)
    if m:
        return _bounded_lead(text[m.start():])
    m = re.search(r"\*\*?\s*MERGE-READY", text, re.IGNORECASE)
    if m:
        return _bounded_lead(text[m.start():])
    m = re.search(r"\*\*?\s*PASS/FAIL:\s*PASS", text, re.IGNORECASE)
    if m:
        return _bounded_lead(text[m.start():])

    # Trailing region after the LAST verdict-family heading.
    heads = list(
        re.finditer(
            r"^#{2,3}\s+\d*\.?\s*(Release verdict|Re-stated verdict|Verdict|Log)",
            text,
            re.MULTILINE | re.IGNORECASE,
        )
    )
    # Trailing region after the LAST verdict-family heading (else the whole doc).
    region = text[heads[-1].start():] if heads else text
    # First non-empty, non-table paragraph after the heading.
    for para in region.split("\n\n")[1:]:
        lines = [ln.strip() for ln in para.splitlines() if ln.strip()]
        if not lines or lines[0].startswith("|"):
            continue
        cleaned = re.sub(r"\s+", " ", para).strip()
        if len(cleaned) <= 480:
            return cleaned
        break
    # Nothing parseable — last ~300 chars of the whole doc.
    tail = re.sub(r"\s+", " ", text[-500:]).strip()
    return tail if len(tail) <= 480 else f"{tail[:480]}…"


def _bounded_lead(text: str) -> str:
    """The normalized lead of ``text`` up to the first sentence boundary (bounded ~480).

    A verdict paragraph may run past the closing ``**`` onto a ``—`` continuation (e.g.
    ``**Verdict: FAIL** — merge-blocked on …``): the lead must keep that continuation. The
    first sentence ends at a ``.``/``!``/``?`` followed by whitespace (or a table row / the
    paragraph end); the result is normalized to one line and bounded.
    """
    boundary = re.search(r"[.!?](?:\s|$)", text)
    cut = boundary.end() if boundary else min(len(text), 480)
    lead = re.sub(r"\s+", " ", text[:cut]).strip().strip("*")
    return lead if len(lead) <= 480 else f"{lead[:480]}…"


def derive_wave_record(
    wave: str,
    *,
    review_docs: dict[str, Path],
    ledger: dict[str, Any] | None,
    root: Path,
) -> KnowledgeRecord:
    """Derive ONE finding record for a completed wave (pure; no writes)."""
    adv = review_docs.get("adversarial")
    known_safe = review_docs.get("known_safe")
    prereg = review_docs.get("prereg")

    adv_text = adv.read_text(encoding="utf-8", errors="replace") if adv else ""
    known_text = (
        known_safe.read_text(encoding="utf-8", errors="replace") if known_safe else ""
    )

    # Spec sha: prereg pin first (authoritative 64-hex), else the latest run's git_sha.
    sha = spec_sha_from_prereg(prereg)
    ledger_state = None
    if ledger and ledger.get("ledgers"):
        last = ledger["ledgers"][-1]
        ledger_state = str(last.get("state") or "")
        if not sha and last.get("git_sha"):
            sha = str(last["git_sha"])
    if not sha:
        sha = ""

    # Verdict: adversarial doc decides; known_safe alone is a PASS-complement; the ledger
    # state is the fallback when neither doc carries a usable signal.
    if adv_text:
        verdict = classify_verdict(adv_text, ledger_state=ledger_state)
    elif known_text:
        verdict = classify_verdict(known_text, ledger_state=ledger_state)
    else:
        verdict = classify_verdict("", ledger_state=ledger_state)

    # F1 fix: the retrieval-facing label (never the bare classifier token "not").
    verdict = VERDICT_LABELS.get(verdict, verdict)

    count = finding_count(adv_text) if adv_text else 0
    residuals = residual_list(adv_text) if adv_text else []

    # Conclusions: adversarial verdict sentence, complemented by the known-safe PASS line
    # (when the wave has one), then the run's own goal prefix.
    parts: list[str] = []
    if adv_text:
        conc = _conclusion_lines(adv_text)
        if conc:
            parts.append(conc)
    if known_text:
        ks_conc = _conclusion_lines(known_text)
        if ks_conc and ks_conc not in parts:
            parts.append(ks_conc)
    conclusion = " || ".join(parts)

    # Source locator: the primary review doc when one exists (stable, git-tracked), else a
    # namespace URI on the wave's run-ledger directory (the machine-local wave case).
    if adv:
        source_uri = f"file://docs/reviews/{adv.name}"
    elif prereg:
        source_uri = f"file://docs/reviews/{prereg.name}"
    elif known_safe:
        source_uri = f"file://docs/reviews/{known_safe.name}"
    else:
        source_uri = f"file://experiments/results/workflows/{wave}/"

    goal_prefix = ""
    if ledger and ledger.get("ledgers"):
        goal_prefix = str(ledger["ledgers"][-1].get("goal") or "")[:140]

    # F2 fix (deep review 2026-09-04): the retrieval text must carry the CONCLUSION —
    # before this, the conclusion lived only in the payload dict (never embedded/indexed),
    # so retrieval returned shells ("findings 0, residuals 0") with the substance absent.
    text = (
        f"wave {wave} -> verdict {verdict}, spec_sha {sha or 'unpinned'}, "
        f"findings {count}, residuals {len(residuals)}"
    )
    if conclusion:
        text += f" :: {conclusion}"
    if residuals:
        text += f" :: residuals: {' | '.join(str(r)[:200] for r in residuals[:3])}"
    payload: dict[str, Any] = {
        "wave": wave,
        "spec_sha": sha,
        "verdict": verdict,
        "finding_count": count,
        "residuals": residuals,
        "conclusion": conclusion,
        "review_docs": sorted(review_docs),
        "ledger_state": ledger_state,
        "goal": goal_prefix,
    }
    if residuals:
        text += f" :: residuals: {'; '.join(residuals[:3])}"
    if conclusion:
        clipped = conclusion if len(conclusion) <= 480 else f"{conclusion[:480]}…"
        text += f" :: conclusion {clipped}"
    text += f" :: {json.dumps(payload, sort_keys=True)}"

    return build_record_from_parts(
        source_type="finding",
        source_uri=source_uri,
        logical_locator=f"wave:{wave}",
        repository_id=f"wave:{wave}",
        revision=sha or f"wave:{wave}",
        authority=Authority.DERIVED,
        evidence_class="[C]",
        text=text,
        extra_fields={
            "extractor_version": EXTRACTOR_VERSION,
            "acl_scope": f"wave:{wave}",
            "worktree_id": f"wave:{wave}",
            "outcome_id": wave,
            "commit_sha": sha,
            "observed_at": "",
        },
    )


# ── Emit (durable artifact + registry row + best-effort event) ──


def load_existing_ids(root: Path) -> set[str]:
    """knowledge_ids already present in the registry index (rerun-safety)."""
    existing: set[str] = set()
    reg = root / "experiments" / "results" / "registry_index.jsonl"
    if not reg.exists():
        return existing
    with reg.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            kid = row.get("knowledge_id")
            if kid:
                existing.add(kid)
    return existing


def emit_record(record: KnowledgeRecord, *, root: Path) -> str:
    """Write one finding record: artifact first, then event, then the registry row.

    Returns ``"new"`` when the record was emitted, ``"exists"`` when its knowledge_id was
    already present (rerun-safe no-op), ``"dry"`` in dry-run mode.
    """
    artifact_dir = root / "experiments" / "results" / "kb"
    artifact_path = artifact_dir / f"{record.knowledge_id}.json"
    if artifact_path.exists():
        return "exists"

    artifact = record_to_artifact(record)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path.write_bytes(artifact)

    # Best-effort projection event — a downed stream must never fail the backfill (the
    # artifact + registry row above are the record; the event is the projection nudge).
    try:
        os.environ.setdefault("FINOPS_KB_WRITE", "1")
        r = ks.connect(host=REDIS_HOST, port=REDIS_PORT)
        ks.publish_event(
            r, record_to_event(record), source_type=record.source_type
        )
    except Exception as exc:  # noqa: BLE001 — best-effort projection, documented above
        print(f"  [warn] event publish skipped for {record.knowledge_id[:12]}: {exc}")

    line = {
        "knowledge_id": record.knowledge_id,
        "entity_id": record.entity_id,
        "source_type": record.source_type,
        "logical_locator": record.logical_locator,
        "source_uri": record.source_uri,
        "lifecycle_state": "current",
        "observed_at": record.observed_at,
        "indexed_at": record.indexed_at,
        "supersedes": record.supersedes,
        "causes": record.causes,
        "reason": "",
    }
    reg = root / "experiments" / "results" / "registry_index.jsonl"
    reg.parent.mkdir(parents=True, exist_ok=True)
    with reg.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line) + "\n")
    return "new"


def run_backfill(
    *,
    root: Path,
    corpus_root: Path | None = None,
    dry_run: bool = False,
    only: set[str] | None = None,
) -> tuple[int, int, int]:
    """Derive + emit one finding record per completed wave.

    Returns ``(derived, emitted_new, already_present)``. ``derived`` is the number of waves
    found (each maps to exactly one record); ``emitted_new`` counts records written by this
    run; ``already_present`` counts rerun-safe skips.
    """
    root = root.resolve()
    corpus = (corpus_root or root).resolve()

    review_waves = discover_review_waves(corpus / "docs" / "reviews")
    ledger_waves = discover_ledger_waves(corpus / "experiments" / "results" / "workflows")
    waves = completed_waves(review_waves, ledger_waves)
    if only:
        waves = [w for w in waves if w in only]

    existing = set() if dry_run else load_existing_ids(root)
    emitted_new = 0
    already = 0

    for wave in waves:
        review_docs = review_waves.get(wave, {})
        ledger = ledger_waves.get(wave)
        record = derive_wave_record(wave, review_docs=review_docs, ledger=ledger, root=corpus)
        if dry_run:
            print(
                f"  [dry] {record.knowledge_id[:12]}  {record.source_type}"
                f"  wave:{wave}  verdict in text"
            )
            emitted_new += 1
            continue
        if record.knowledge_id in existing or (root / "experiments" / "results" / "kb" / f"{record.knowledge_id}.json").exists():
            already += 1
            continue
        outcome = emit_record(record, root=root)
        if outcome == "new":
            emitted_new += 1
            print(
                f"  [emit] {record.knowledge_id[:12]}  wave:{wave}  "
                f"verdict={json.loads(record.text.split(' :: ')[-1]).get('verdict')}"
            )
        else:
            already += 1

    return len(waves), emitted_new, already


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Deterministic backfill of the KB finding layer from review artifacts + "
        "run ledgers (kb_finding_layer k2). No LLM — every field is a deterministic function "
        "of on-disk docs; rerun-safe knowledge_ids make a re-run a no-op.",
    )
    parser.add_argument("--root", type=Path, default=REPO, help="emit root (default: this checkout)")
    parser.add_argument(
        "--corpus-root", type=Path, default=None,
        help="scan root for docs/reviews + run ledgers (default: --root)",
    )
    parser.add_argument("--dry-run", action="store_true", help="derive + print, write nothing")
    parser.add_argument("--limit", type=int, default=0, help="cap on waves processed (0 = all)")
    parser.add_argument("--only", default="", help="comma-separated wave names to process")
    args = parser.parse_args(argv)

    only = {w.strip() for w in args.only.split(",") if w.strip()} if args.only else None
    derived, emitted, already = run_backfill(
        root=args.root, corpus_root=args.corpus_root, dry_run=args.dry_run, only=only,
    )
    mode = "dry-run" if args.dry_run else "emit"
    print(f"{mode}: waves={derived} emitted_new={emitted} already_present={already}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
