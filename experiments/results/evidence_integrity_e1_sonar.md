# e1 — Sonar revision identity (cap_evidence_integrity)

Date: 2026-08-25 · Branch: feature/cap-evidence-integrity

## The fix (design §5.2)

1. **Revision-scoped project key** (`sonar.py`): `run_sonar_analysis` gains a `revision`
   parameter; when no explicit `project_key` is given, the key is scoped as
   `<base>_<revision[:12]>` (`exp_src_<sha[:12]>`), so a fetch for that key can only ever
   return that revision's analysis. `quality_ingestion.py` now passes the injected `revision`
   instead of calling `run_sonar_analysis(str(codebase_path))` unscoped.
2. **Stale-refusal, fail-closed**: a fetch-first result whose analysis revision cannot be
   CONFIRMED to match the requested revision is REFUSED — `SonarMetrics.status` =
   `stale-refused`, the record carries the true (or unrecorded) `analyzed_sha`, and is never
   stamped with the current commit. Confirmation is by (a) the revision-scoped key contract or
   (b) the server recording the matching revision (`/api/project_analyses/search`). An
   unrecorded revision (this server runs `sonar.scm.disabled=true`) confirms nothing.
3. **Typed analyzer metadata** (`SonarMetrics` + `_sonar_text`): `tool_version` (scanner
   version), `config_hash` (sha256 of the scanner props used), `analyzed_sha`, `coverage` ride
   as a **typed JSON payload inside `text`** (`{"kind": "sonar-quality/v1", ...}`) — the
   `record_factory` surface is unchanged, no ad hoc schema. Status enum
   `available` / `unavailable` / `stale-refused`.
4. Status enum + zero dependent counts: a `stale-refused` Sonar record emits the status fact;
   when the analyzer did not run, the signal is skipped with a note (never None-as-zero).

## The tests

- `tests/test_sonar.py` (new): revision-scoped key derivation, stale-refusal on legacy key +
  unrecorded revision, stale-refusal on captured mismatch, available when confirmed (scoped key
  or matching captured revision), legacy no-revision behavior unchanged, fresh-scan stamps
  revision + config_hash + tool_version, coverage parsing, unavailable when no scanner.
- `tests/test_quality_ingestion.py` (updated): typed-JSON payload assertions; new
  `test_stale_refused_sonar_emits_status_fact_never_current_stamp`.

22 passed.

## Live probe (against the running SonarQube at localhost:9000)

```
requested revision (HEAD): 4eb563816f002bc073541aa886508e4aeebae0fb

probe 1 — legacy unscoped key 'exp_src' + current revision requested:
  status        = stale-refused
  analyzed      = True
  analyzed_sha  = ''  (server recorded no SCM revision — scm.disabled)
  bugs/smells   = 8/85  (the 2026-08-16 analysis)
  => REFUSED: the live exp_src analysis IS detected as stale; no current-commit stamp.

probe 2 — revision-scoped key (new default):
  project_key   = exp_src_4eb563816f00
  status        = available
  analyzed_sha  = 4eb563816f002bc073541aa886508e4aeebae0fb
  tool_version  = 6.2.1.4610
  config_hash   = <sha256 of the scanner props used>
  coverage      = 0.0
  bugs/smells   = 8/125
  => current-commit analysis recorded ONLY under the revision-scoped key.
```

## Verdict

**PASS** — stale-refusal path unit-tested and live-proven; no fabricated analysis; the record
never claims a revision it did not analyze.
