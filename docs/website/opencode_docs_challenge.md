---
status: accepted
---
# OpenCode Docs Refresh — Challenge

A design review of `docs/website/opencode_docs_scope.md`, not a re-verification of its facts.
Where a disagreement turns on a fact the scope doc didn't check, that fact was spot-checked
directly against the repo (commands quoted below); everything else takes the scope's own
line-by-line verification at face value, since re-deriving it here would just be a second
audit of the same ground.

---

## 1. What I agree with, and why

**The "written not proposed" fix (§1.1) is correctly diagnosed and correctly scoped.**
Confirmed directly: `mental-model.md:33` still headers the section "PARTIALLY BUILT" and
line 169 still says "PROPOSED"; `src/instrument/CONTEXT.md:5` still says
`compile_experiment.py` "is **proposed**" one paragraph below correctly calling
`experiment_spec.py` "written." The self-contradiction inside `AGENTS.md` (line 11 vs. 48)
is real and is exactly the kind of load-bearing inconsistency that should block trust in
the rest of the doc set until fixed. Global find/replace-style correction across the 15
confirmed-stale files, driven off the single already-correct source of truth
(`AGENTS.md:11`), is the right mechanism.

**The REFUTED findings are the most valuable part of the scope doc, and the instinct
behind them is correct.** Three separate corrections — Control Room being extensively
documented already (§1.3), `lab-books/SKILL.md` already saying "19" correctly (§1.9),
and `anthropic-sonnet5` being a real key, not a hallucinated one (§1.11) — all reverse a
seed hypothesis that would otherwise have caused the build phase to "fix" things that
aren't broken, or worse, to delete a real provider-pricing key. A doc-refresh task is
unusually vulnerable to a seed hypothesis being trusted wholesale (it's easy to grep for
the word "proposed" and never check whether the surrounding claim is still true); treating
every hypothesis line as falsifiable and checking it against the file is the right
discipline and should carry forward into the build/verify phases too, not just scope.

**The plural `.opencode/agents|commands|skills/` correction (§1.4) is confirmed** —
`ls .opencode/tools/` returns 16 flat `.ts` files, `ls .opencode/commands/` returns 5
`.md` files — and matters concretely: it's the kind of detail a port script would get
wrong silently if it trusted the task-context hint over the actual directory listing.

**Not touching §1.16 (the instrumentation gap) is correct scope discipline.** A doc
wording fix and a missing-field-in-the-data-model are different classes of problem, and
conflating them (marking the ledger gap "resolved" because the surrounding prose now
says "written") would be a real regression. Keeping it as an explicit "still open,
don't touch" line in the acceptance checklist is the right guardrail.

**The lab.md and CONTEXT.md counts are confirmed on direct read**, not just taken from
the scope doc: `lab.md` body literally says "Run a specific lab book analysis from the
14 available labs" and enumerates 13 names; `src/instrument/CONTEXT.md:3` literally says
"33 Python modules." Both fixes are correctly scoped and low-risk.

---

## 2. Disagreements, each with a concrete alternative

### D1. `.opencode/tools/*.ts` → MCP server is the wrong port target

**Where:** §3's taxonomy table, mapping row for custom tools.

**Disagree.** Every `.ts` tool inspected is a thin `Bun.$` subprocess wrapper around a
`scripts/*.py` CLI — confirmed by reading `backfill.ts` (wraps
`python3 scripts/backfill_artifacts.py` with 3 passthrough flags) and `pipeline.ts`
(wraps `python3 scripts/pipeline.py`, translating an `action` enum into flags). None of
the 16 tools do anything an agent with Bash access can't do by invoking the script
directly. Standing up an MCP server — a persistent process, a JSON-RPC schema layer, a
`.mcp.json` config entry, and 16 tool definitions reimplemented in whichever language the
server is written in — to reproduce what Bash + a documented script map already gives for
free is real infrastructure to build and maintain for zero behavioral gain. It's also
exactly the kind of second copy that goes stale silently, which is the disease this whole
doc-refresh exists to cure (see the `AGENTS.md:11` vs. `:48` precedent in §1.1).

**Alternative:** don't build an MCP server for this port. Port the *knowledge* the `.ts`
tools encode — valid flag combinations, plan names, condition lists, which script each
tool wraps — into the Claude Code reference layer (a `.claude/skills/pipeline-ops/`-style
doc, or folded into `.claude/rules/`) that documents the underlying `scripts/*.py`
invocations directly, and let Claude Code call them via Bash, the same way any other
onboarding doc in this repo already tells a human or agent to run `python
scripts/lab_$ARGUMENTS.py`. Reserve MCP for a future case that needs structured,
non-CLI access (e.g., live Redis state queries) — none of the current 16 tools need that,
since they all shell out already.

### D2. Commands → Skills 1:1 is over-fitted; keep the flat shape where it matches

**Where:** §3's mapping row for `.opencode/commands/*.md`.

**Partially disagree.** The scope is right that Claude Code's current docs steer new work
toward `.claude/skills/`, but the 5 opencode commands (`analyze`, `lab`, `new-exp`,
`pipeline`, `run-exp`) are single-file prompt templates with `$ARGUMENTS` substitution and
no bundled supporting files — confirmed by reading `lab.md`, which is 20 lines of
frontmatter + prose, nothing to bundle. Converting all 5 into skill *directories* when
skills' main advantage (bundling supporting files) doesn't apply is directory overhead
with no payoff, especially once D1 removes the one thing that might have been bundled
(a tool script).

**Alternative:** port `.opencode/commands/*.md` → `.claude/commands/*.md` 1:1 — same flat
file, same `$ARGUMENTS`-style templating, and per the scope's own citation, "existing
`.claude/commands/` files keep working." Reserve `.claude/skills/` for porting the 3
files that are already skill-shaped (`.opencode/skills/*/SKILL.md`), which map cleanly
because the source and target shapes already match. Promote a command to a skill later,
individually, only if it grows bundled files that justify the directory.

### D3. New-tool-per-script isn't a real question for *this* port (D1 removes it), but it's a live question for OpenCode's own tool surface, and the scope should say so

The task brief asks whether new tools should be one-per-script or folded into existing
tools with variants. Under D1, the Claude Code port doesn't create new `.ts`/MCP tools at
all, so the question is moot for the port itself. But it's a real, currently-live gap in
this repo's OpenCode tooling that the scope's doc-only framing causes it to miss:

- 6 `backfill_*.py` scripts exist (`backfill_artifacts.py`, `backfill_costs.py`,
  `backfill_deep_metrics.py`, `backfill_sonar.py`, `backfill_story_artifacts.py`,
  `backfill_story_transcripts.py`), but exactly **one** `.ts` tool exists
  (`backfill.ts`), and it wraps only `backfill_artifacts.py`. Three of the other five
  (`backfill_costs.py`, `backfill_deep_metrics.py`, `backfill_story_artifacts.py`) are
  independently confirmed doc-missing by §1.5's own list.
- By contrast, the 5 `review_*`/`*_reviews.py` scripts (`review_stories.py`,
  `review_worker.py`, `trigger_reviews.py`, `enqueue_reviews.py`, `finalize_reviews.py`)
  have **zero** dedicated `.ts` tools; they're only reachable indirectly through
  `pipeline.ts`'s plan phases. That's already the "fold, don't fan out" pattern working
  as intended — a good existing precedent, not a gap.

**Alternative:** the doc-refresh's fix for the 3 undocumented backfill scripts should stay
doc-only (add them to the script map, per §1.5's existing fix direction) — don't let this
observation expand doc-refresh scope into a code change. But the scope doc should record,
as an explicitly out-of-scope follow-up (the same way it flagged `enqueue.ts`'s missing
flags in §1.15/§4-item-21), that `backfill.ts` is a plausible candidate for a `target:
"artifacts" | "costs" | "deep_metrics" | "story_artifacts"` variant argument rather than 3
more near-duplicate tool files, using `pipeline.ts`'s review-folding as the precedent to
follow. Otherwise this observation falls through the crack between "doc scope" and
"code scope" and never gets written down anywhere.

### D4. Two independently-maintained script/lab enumerations is the wrong end state, not just a one-time reconciliation

**Where:** §4 items 7–8 (script map in `mental-model.md` vs. `scripts/CONTEXT.md`) and
item 11 (`lab.md`'s list vs. `lab-books/SKILL.md`'s list).

**Disagree with "reconcile so they don't disagree" as the terminal fix.** §1.5 already
demonstrates that these two docs drifted from each other independently once (disagreeing
on `generate_manifest.py`, `plan.py`, `sync_data.py`, `backfill_sonar.py` even between
themselves, not just against the real script count). Fixing both to agree today doesn't
prevent them from drifting apart again the next time a script is added — there's no
single owner, so the fix has to be repeated by hand every time either file is touched.
The lab-count case is the same shape in miniature: `lab.md` maintains its own inline
enumeration of 19 lab names that's redundant with `lab-books/SKILL.md`'s already-correct
one.

**Alternative:** pick one authoritative location per fact and make the other a pointer,
not a duplicate:
- `scripts/CONTEXT.md` (colocated with `scripts/`, most likely to get touched when a
  script is added/removed) becomes the authoritative full script table.
  `mental-model.md`'s "Script map" collapses to a short categorized summary (by
  subsystem, the level it already uses for the `lab_*.py` collective line) plus an
  explicit "see `scripts/CONTEXT.md` for the full list" pointer, rather than maintaining
  a second full enumeration.
- `lab-books/SKILL.md` (already correct, already the more detailed of the two) becomes
  the authoritative lab list. `lab.md` drops its inline enumeration and says "load the
  lab-books skill for the current list" (it already does the first half of this — "First,
  load the 'lab-books' skill" — the fix is deleting the redundant list that follows,
  not maintaining it in parallel).

This is a slightly larger diff than the scope's item 7/8/11 as written, but it's the same
number of files touched, one is just shortened instead of matched — and it removes the
recurring-drift failure mode instead of resetting it to zero once.

### D5. Don't let the 3 newly-documented modules get full descriptions in two places

**Where:** §4 items 3 and 18, both touching `supervisor.py` / `workflow_runner.py` /
`test_runner.py`.

**Disagree with duplicating full descriptions across `mental-model.md`'s architecture
section and `src/instrument/CONTEXT.md`'s module table.** This is the same
two-owners-of-one-fact pattern as D4, just for module docs instead of script docs.
`mental-model.md` is explicitly framed as a high-altitude "mental model," not a module
reference (its own header: "File map, signatures, and dependencies. No theory. No
methodology.") — full one-line-purpose entries for all 38 modules belong in
`src/instrument/CONTEXT.md`'s table (item 18 already requires this). `mental-model.md`'s
architecture section should get at most a one-clause mention of these 3 modules by name,
not a repeated description that can independently drift from the CONTEXT.md version the
next time either file is edited.

### D6. `opencode.json` model-id edits: the risk is lower than the task brief implies, but the verification step is still worth doing cheaply

**Where:** §4 item 17 and the task brief's explicit prompt ("should `small_model` change
at all without confirming the provider id?").

The brief is right to be suspicious in general — `PROVIDER_PRICING`'s own key names
(`anthropic-sonnet5`, `openai-luna`, `openai-sol`, `openai-terra`, confirmed in §1.11) are
internal pricing-table aliases, not literal API model ids, which proves this repo *does*
use human-readable code names in places where a literal provider string would be
required elsewhere. That's a real reason to distrust "grep shows this string everywhere,
therefore it's the correct config value."

But a direct check narrows the risk for this specific case: `opencode.json`'s own
top-level `model` field is already `"deepseek/deepseek-v4-pro"` — same `provider/v4-tier`
shape as the proposed `small_model` fix — and `deepseek/deepseek-v4-flash` /
`deepseek/deepseek-v4-pro` both appear as literal `provider_model` pairs in real
result-file names under `experiments/results/stories/` (e.g.
`notification_service_deepseek_deepseek-v4-flash_clean_24e52cb14f26.json`), which are
generated from actual completed runs, not from doc prose. That's stronger evidence than
a source-code grep: it means an actual call resolved successfully with that string. So
this is not the same situation as the `PROVIDER_PRICING` aliases.

**Alternative:** keep item 17, but tighten its acceptance bar to "confirmed by a
successful run using that provider/model string" (which the result-file evidence above
already satisfies for `deepseek/deepseek-v4-flash`) rather than "grep shows it's used
elsewhere" (which is what the scope's own wording implies today, and which would have
been the wrong bar for a `PROVIDER_PRICING`-style alias). No code change needed to the
checklist item's outcome, just to what counts as having verified it — worth stating
explicitly so a future editor doesn't extend this pattern to a field where the same grep
would be trusting an alias like `anthropic-sonnet5`.

### D7. The tool/script flag-parity audit is under-sampled; say so explicitly rather than letting it look complete

**Where:** implicitly, across §1.8, §1.13, §1.15 — three separate spot-checks
(`pipeline.ts` missing `cross_models`, `run_story.ts` missing `late_degrade` and 6 other
flags, `enqueue.ts` missing 2 flags) each independently found real drift between a `.ts`
tool and the script it wraps.

**This is a completeness gap in the drift inventory, not just a nitpick — 3 of the 16
`.ts` tools were checked for flag-parity drift, and all 3 had it.** That's a high hit
rate on a small sample; extrapolating, several of the other 13 unchecked tools
(`analyze_worktrees.ts`, `archive_worktrees.ts`, `backfill.ts`, `batch.ts`,
`build_data.ts`, `dashboard.ts`, `inventory.ts`, `list_stories.ts`, `monitor.ts`,
`run_experiment.ts`, `run_lab.ts`, `sweep.ts`, `worker.ts`) likely have the same class of
drift and it just hasn't been looked for yet. The scope doc's §4 checklist doesn't
mention this as an open item at all, which risks the build/verify phases treating the 3
found instances as the complete list.

**Alternative:** before or during the build phase, run the same check pattern already
applied 3 times (`.ts` tool's exposed args vs. wrapped script's argparse choices) against
the remaining 13 tools, and add whatever's found to the acceptance checklist. If time-
boxing this is preferred, at minimum add one line to §4 flagging it as a known
incomplete-coverage area — consistent with the scope's own practice elsewhere (e.g. item
19's explicit "don't mark this resolved" guard) of naming what wasn't checked, not just
what was.

### D8. The port phase should ship the mapping document, not committed `.claude/*` files — at least not yet

**Where:** §3/§4 leave this ambiguous; item 20 only constrains naming, not deliverable
shape. The task brief explicitly asks this question.

**This repo currently has zero `.claude/` artifacts** (confirmed: `find .claude` and
`ls CLAUDE.md` both return nothing) — so "porting" isn't updating an existing parallel
copy, it's creating one from scratch, in the same phase that's simultaneously rewriting
the exact source docs (`AGENTS.md`, `mental-model.md`, `conventions.md`, the 3
`SKILL.md` files) a port would need to translate. Generating `.claude/*` files now means
porting content that's still moving, and immediately creates a second full copy of every
fact this doc-refresh is fixing — which is precisely the failure mode the whole exercise
exists to correct (the `AGENTS.md:11`/`:48` self-contradiction is what happens when one
fact has two homes and only one gets updated). There is also no signal anywhere in the
repo — no `CLAUDE.md`, no `.claude/` dir, no mention in `README.md` — that Claude Code is
actually a supported second interface for this project today, as opposed to a
hypothetical port target for this task.

**Alternative:** this phase's deliverable should be the mapping document (§3, already
written) plus this challenge doc — not committed `.claude/agents/`, `.claude/commands/`,
or `.claude/skills/` files. Gate actual file generation on two things: (1) the drift-fix
landing first, so there's one stable source to translate instead of two moving targets,
and (2) an explicit decision — from the user, not inferred from this task — that Claude
Code becomes a supported second interface for this repo. If and when that's confirmed,
generate the `.claude/` tree as its own follow-up phase, and prefer generating it
mechanically from the (by-then-fixed) OpenCode sources over hand-authoring a parallel
copy, so it can't drift silently the way `AGENTS.md` line 48 did.

---

## 3. Recommendation for the spec phase

**Proceed to spec for the drift-fix (§1, §4 items 1–19) as scoped — it's well-verified
and low-risk — but change course on the port:** spec should produce the taxonomy mapping
as a design/reference document only (§3, refined per D1/D2 above: no MCP tool
generation, `.opencode/commands/` → `.claude/commands/` not `.claude/skills/`), explicitly
deferring any committed `.claude/*` files to a follow-up phase gated on drift-fix landing
first and an explicit go-ahead on Claude Code as a second supported interface (D8); spec
should also fold in the single-source-of-truth restructuring for script/lab/module
enumerations (D4/D5) instead of the scope's pairwise-reconcile framing, and add the
13-tool flag-parity audit (D7) as an explicit checklist item rather than leaving it
implicit.
