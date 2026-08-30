---
status: implemented
implemented_by: feature/kb-producer-factory
---
# R1 + R2 implementation trace — RecordBuilder factory + source_type vocabulary

Implements R1 and R2 from `docs/reviews/restructure.md` (the two highest-leverage KB-local
restructuring items). This document traces each recommendation to the code it landed in, with a
per-item PASS/FAIL and the pytest result that closed it. Commit `3591fc5ab`.

Summary of the two changes:

* **R1** — one shared `RecordBuilder` factory (`src/instrument/record_factory.py`) owns the
  content-hash back-fill ordering (blank `knowledge_id`/`content_hash`/`valid_from`/
  `observed_at`/`indexed_at` → serialize → hash → back-fill) that was previously copy-pasted into
  all nine producer modules. Each producer keeps only its *derivation* and calls the factory.
* **R2** — one `SOURCE_TYPES` registry (`knowledge.py`) is the single owner of the `source_type`
  vocabulary (name → `message_family`/`authority`/`evidence_class`); `message_family()`,
  `OBSERVATION_TYPES`/`ACTUATION_TYPES`, and `scripts/registry.py`'s `--record-type` choices all
  derive from it.

---

## 1. R1 — the shared RecordBuilder factory

`src/instrument/record_factory.py` (188 lines, new) is the single choke point:

| Component | Location | Purpose |
|---|---|---|
| `build_record(*, source_type, source_uri, logical_locator, repository_id, revision, authority, evidence_class, text, extra_fields, now=None)` | `record_factory.py:94` | The factory — computes `entity_id`, builds with placeholder ids, back-fills `content_hash`/`knowledge_id`. Rejects unknown `extra_fields` keys (no silent field drop). |
| `record_to_artifact(record)` | `record_factory.py:67` | The serialization half of the hash-input ordering — blanks the five volatile fields. Moved here so the blanking rule and the builder that relies on it cannot drift apart. |
| `_now_iso(now)` | `record_factory.py:49` | Single timestamp primitive (was re-declared in all nine producers). |
| `_sha256_bytes(data)` | `record_factory.py:58` | Single artifact-hash primitive (was re-declared in all nine producers). |

### The nine producers → factory (PASS/FAIL per module)

Each producer's `build_*`/`derive_*` was rewritten to call the factory, deleting its duplicated
`_now_iso`/`_sha256_bytes`/back-fill tail. `record_to_artifact` remains importable from
`knowledge_ingestion` (re-exported via `knowledge_ingestion.py:45-52`) so existing call sites —
`scripts/kb_worker.py`, `kb_produce*.py`, `supervise.py`, `story.py`, `run.py`,
`finalize_reviews.py` — are untouched.

| Producer | Builder (def) | Delegates to factory at | Status |
|---|---|---|---|
| `knowledge_ingestion.py` (finding) | `build_record` `:215` | `:269` | **PASS** |
| `knowledge_ingestion.py` (phase-finding) | `derive_phase_record` `:432` | `:474` | **PASS** |
| `story_ingestion.py` | `build_story_record` `:124` | `:169` | **PASS** |
| `review_ingestion.py` | `build_review_record` `:77` | `:97` | **PASS** |
| `ledger_ingestion.py` (job) | `build_job_record` `:155` | `:214` | **PASS** |
| `ledger_ingestion.py` (attempt/meta) | `build_attempt_record` `:231` | `:277` | **PASS** |
| `observation_ingestion.py` (observation) | `build_observation_record` `:76` | `:105` | **PASS** |
| `observation_ingestion.py` (flag) | `build_flag_record` `:143` | `:178` | **PASS** |
| `actuation_ingestion.py` | `derive_actuation_record` `:90` | `:138` | **PASS** |
| `code_ingestion.py` | `build_code_record` `:227` | `:258` | **PASS** |
| `quality_ingestion.py` | `build_quality_record` `:130` | `:161` | **PASS** |
| `policy_ingestion.py` | `build_policy_record` `:159` | `:185` | **PASS** |

Notes on the two producers that still reference `_now_iso` directly: `observation_ingestion` and
`actuation_ingestion` fold the producer timestamp into their *identity* (`assessment_id`/
`actuation_id`), so they `from .record_factory import _now_iso` (single definition) rather than
re-declaring it — their derivation genuinely needs the timestamp, the mechanical back-fill does not.

---

## 2. R2 — the single source_type vocabulary

| Component | Location | Purpose | Status |
|---|---|---|---|
| `SourceTypeSpec(message_family, authority, evidence_class)` | `knowledge.py:105` | Frozen per-type provenance record. | **PASS** |
| `SOURCE_TYPES: dict[str, SourceTypeSpec]` | `knowledge.py:125` | The 12-entry vocabulary (round-1 `finding`/`code`/`report`/`policy` + round-2 `story`/`review`/`ledger_job`/`ledger_attempt`/`observation`/`flag`/`meta_session`/`actuation`). | **PASS** |
| `OBSERVATION_TYPES` | `knowledge.py:146` | Derived projection (family == `"observation"`). | **PASS** |
| `ACTUATION_TYPES` | `knowledge.py:155` | Derived projection (family == `"actuation"`; still the single-member `{"actuation"}` allowlist). | **PASS** |
| `message_family(source_type)` | `knowledge.py:160` | Keys off `SOURCE_TYPES`; unregistered → `"observation"` (closed-by-default preserved). | **PASS** |
| `scripts/registry.py` — `RECORD_TYPES` | `registry.py:62` (`from instrument.knowledge import SOURCE_TYPES` `:52`; `--record-type` choices `:263`) | `RECORD_TYPES = tuple(SOURCE_TYPES)` — no more hard-coded exclusion of round-1 types. | **PASS** |
| `src/instrument/__init__.py` — exports | `SOURCE_TYPES`/`SourceTypeSpec` `:96-97`; `build_record_from_parts` `:109`; `__all__` `:493`, `:553` | Barrel re-exports the new vocabulary + factory. | **PASS** |

---

## 3. Pytest results

| Gate | Command | Result |
|---|---|---|
| Targeted (VERIFY list) | `pytest tests/test_knowledge.py tests/test_story_ingestion.py tests/test_review_ingestion.py tests/test_ledger_ingestion.py tests/test_observation_ingestion.py tests/test_actuation_ingestion.py tests/test_code_ingestion.py -q` | **127 passed** |
| KB/producer cluster | adds `test_knowledge_ingestion`, `test_policy_ingestion`, `test_quality_ingestion`, `test_record_factory`, `test_registry_cli`, `test_knowledge_stream`, `test_kb_worker`, `test_kb_produce_registry`, `test_retrieval` | **238 passed** |
| Full suite | `pytest tests/ -m "not external" -q` | **1046 passed, 101 deselected** |
| Backward-compat invariant | `KnowledgeRecord.from_dict` over every `experiments/results/kb/*.json` | **1913 / 1913 parsed, 0 failures** |

Byte-identity ("no re-key") is guarded by golden-value assertions in
`tests/test_record_factory.py:147-306` — one per producer, each asserting the refactored
`knowledge_id` equals the exact pre-refactor string (captured before the R1 change). The R2
vocabulary is guarded by `tests/test_knowledge.py:349-384` (`SOURCE_TYPES` membership,
derived-frozenset projection, nominal provenance, `message_family` keying, frozen spec).

---

## 4. Verdict

**R1: PASS** — factory landed; all nine producers delegate to it; no re-key (byte-identical ids
across the refactor, plus 1,913/1,913 on-disk artifacts still `from_dict`-parseable).

**R2: PASS** — `SOURCE_TYPES` is the single vocabulary owner; `message_family()`,
`OBSERVATION_TYPES`/`ACTUATION_TYPES`, `scripts/registry.py`, and the barrel all derive from it.

Full suite green (1,046 passed, no `not external` failures).
