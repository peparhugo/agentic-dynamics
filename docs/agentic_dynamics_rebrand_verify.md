# Agentic Dynamics Rebrand Verification

Verified on the clean `feature/agentic-dynamics-cutover` branch on 2026-08-15.

## Result

**PASS, pending the operational GitHub rename.** All in-scope repository and Firebase source checks pass. The public links intentionally target the future repository slug and will become reachable during cutover.

| Check | Result | Evidence |
|---|---|---|
| Agentic Dynamics is canonical in `README.md` and all eight public HTML pages | **PASS** | `README.md` begins with `# Agentic Dynamics`. The titles and version footers in `index.html`, `methodology.html`, `evidence.html`, `framework.html`, `story.html`, `accelerator.html`, `databricks.html`, and `glossary.html` all name Agentic Dynamics. The automated audit found exactly eight public HTML pages. |
| Canonical definition is accurate and consistent | **PASS** | `README.md`, `index.html`, and `story.html` use the same defining predicate: “the empirical study of how AI agents behave, adapt, interact, recover, and produce outcomes across changing tasks, environments, workflows, and time.” `evidence.html` restates the same scope without broadening the measured evidence. The README explicitly bounds current evidence to coding-agent experiments and does not claim swarm or organizational findings. |
| Remaining AI FinOps references are justified; the old umbrella name is absent | **PASS** | The audit found zero instances of `AI FinOps Dynamics` or `FinOps Dynamics` in `README.md` and the eight public pages. All nine remaining public-surface `FinOps` references are classified below as economics/application language, related work, or historical origin. |
| Public GitHub links use the intended repository slug | **PENDING CUTOVER** | All 19 GitHub `href` values in the eight HTML pages target `https://github.com/peparhugo/agentic-dynamics`. README installation uses `https://github.com/peparhugo/agentic-dynamics.git` and `cd agentic-dynamics`. These targets will return 404 until the repository rename is complete. |
| Website and Open Graph URLs preserve the Firebase host | **PASS** | Each page has the expected page-specific `og:url` under `https://ai-finops-rulebook.web.app`; all eight `og:image` values remain `https://ai-finops-rulebook.web.app/og-image.png`. README links, `robots.txt`, and `sitemap.xml` retain the existing host. No custom domain was acquired or configured. |
| Open Graph artwork uses the new identity | **PASS** | `firebase/public/og-image.png` is 1200 x 630 and displays Agentic Dynamics. The approved square field map is retained as `firebase/public/agentic-dynamics-field-map.png`. |
| Dynamic data, keys, measurements, formulas, and provenance are intact | **PASS** | `firebase/public/data.js` is byte-for-byte identical to `HEAD^` and still defines `window.DYNAMICS_DATA`. Across all eight pages, the pre/post-rebrand multisets of `data-stat`, `data-stat-fmt`, `data-anal`, and `data-anal-model` keys are identical. Numeric literals and `[M]`, `[C]`, `[H]`, `[X]`, and `[P]` provenance tags are unchanged. All 44 formula-bearing HTML lines are byte-for-byte unchanged. |
| Every local HTML `href` resolves | **PASS** | A Python standard-library audit resolved root-relative and page-relative links from all eight pages. It ignored fragment-only, `mailto:`, and external URLs as required and found zero unresolved local targets. |
| Relevant spec and data-integrity tests pass | **PASS** | `python3 -m pytest tests/test_experiment_spec.py tests/test_data_integrity.py -q` reported `24 passed`. Exact invocation and result are below. |

## Canonical Definition

The canonical definition is:

> Agentic Dynamics is the empirical study of how AI agents behave, adapt, interact, recover, and produce outcomes across changing tasks, environments, workflows, and time.

The rebranded surfaces consistently treat economics, verification, recovery, resilience, behavior, coordination, and governance as dimensions or application areas within Agentic Dynamics. They do not present the existing coding-agent instrument as evidence for every part of that broader field.

## Retained FinOps References

Every retained occurrence in `README.md` and the eight public HTML pages was reviewed individually:

| Location | Classification | Justification |
|---|---|---|
| `README.md:46` | Economics | “the FinOps question” asks whether an outcome increases durable system value. It names the economic question, not the umbrella field. |
| `README.md:82` | Related work | `FinOps Foundation` is an external organization's proper name. |
| `README.md:166` | Related work | The Related Work description accurately names the FinOps Foundation. |
| `firebase/public/accelerator.html:166` | Economics/application | “precision FinOps” is presented as an application powered by Agentic Dynamics measurement. |
| `firebase/public/accelerator.html:168` | Economics/application | “Precision FinOps Measurement” names an application capability, not the field. |
| `firebase/public/databricks.html:8` | Related work | `FinOps Foundation` is retained in Open Graph metadata as an external proper name. |
| `firebase/public/evidence.html:233` | Economics | “A FinOps model” refers to financial-operations budgeting for maintenance work. |
| `firebase/public/story.html:6` | Historical origin | The description states that an AI FinOps question broadened into Agentic Dynamics. |
| `firebase/public/story.html:177` | Historical origin | The narrative explicitly identifies AI FinOps as the project's starting question and Agentic Dynamics as the resulting field. |

Lowercase `ai-finops` remains in `https://ai-finops-rulebook.web.app`. This is the intentionally preserved Firebase infrastructure hostname, not a field-name claim. Legacy strings outside the audited public identity surfaces remain historical evidence or internal technical identifiers and were not globally replaced.

## Commands And Results

All commands ran from the repository root.

### Focused repository tests

The full suite includes experiment and integration workloads unrelated to this content-only cutover. The spec parser and data-integrity tests were run through the available Python 3 interpreter:

```text
$ python3 -m pytest tests/test_experiment_spec.py tests/test_data_integrity.py -q
........................                                                 [100%]
24 passed in 0.81s
```

### Rebrand and link audit

Command: `python3 - <<'PY'` with standard-library assertions over `README.md` and `firebase/public/*.html`. The script asserted the exact eight-page set, canonical titles and footers, shared definition, absence of the retired umbrella name, canonical GitHub targets, page-specific Open Graph URLs, preserved Open Graph image URL, and existence of every non-external local `href` target.

```text
PASS: 8 canonical pages; consistent definition; 19 GitHub hrefs; 8 OG URL/image pairs; 0 broken local hrefs
```

### Retained-term audit

Command: `python3 - <<'PY'` with an explicit allowlist keyed by repository-relative file and line number for every `AI FinOps` or `FinOps` match in `README.md` and `firebase/public/*.html`.

```text
PASS: 9 retained FinOps references classified: {'economics': 2, 'related work': 3, 'economics/application': 2, 'historical origin': 2}; 0 umbrella-field uses
```

### Data and provenance comparison

Command: `python3 - <<'PY'` comparing current public files with `git show HEAD^:<path>`. The script compared `data.js` bytes and HTML multisets for data-binding keys, numeric literals, and provenance tags.

```text
PASS: data.js byte-identical; window.DYNAMICS_DATA present; data keys, numeric literals, and provenance tags unchanged in 8 HTML pages
```

Command: `python3 - <<'PY'` comparing every formula-bearing public HTML line with `HEAD^`.

```text
PASS: 44 formula-bearing HTML lines unchanged from HEAD^
```

### Diff and repository state

```text
$ git diff --check
# No output; exit status 0.

$ git diff --quiet -- firebase/public/data.js
# No output; exit status 0.

$ git remote -v
origin  git@github.com:peparhugo/ai-finops-framework.git (fetch)
origin  git@github.com:peparhugo/ai-finops-framework.git (push)

$ sha256sum firebase/public/og-image.png
a4f966a1bba42dd0901bfdebc377b9c77806cf1c69313d60f198cf3f81072721  firebase/public/og-image.png
```

## Changed-File Summary

The clean cutover changes the following relevant files:

| Files | Summary |
|---|---|
| `README.md` | Made Agentic Dynamics the repository identity and canonical field, updated the intended clone URL and directory, bounded the evidence claims, and retained economics/related-work references. |
| `firebase/public/index.html` | Rebranded title, metadata, navigation, hero, definition, source links, and footer. |
| `firebase/public/methodology.html` | Rebranded instrument prose, clone instructions, metadata, links, CTA, and footer. |
| `firebase/public/evidence.html` | Rebranded metadata and field prose while preserving measurements and reframing related-work claims without conflating concepts. |
| `firebase/public/framework.html` | Rebranded metadata, navigation, concept heading, source links, and footer. |
| `firebase/public/story.html` | Rebranded metadata, narrative, links, and footer while retaining the AI FinOps historical origin. |
| `firebase/public/accelerator.html` | Rebranded the page as Agentic Dynamics applications while retaining precision FinOps as an application. |
| `firebase/public/databricks.html` | Rebranded the related-work framing, metadata, links, and footer while retaining external proper names. |
| `firebase/public/glossary.html` | Rebranded metadata, terminology framing, links, and footer. |
| `firebase/public/app.js`, `firebase/public/base.css` | Updated public source-header comments only; runtime behavior and styling rules were not changed. |
| `firebase/public/og-image.png`, `firebase/public/agentic-dynamics-field-map.png` | Replaced the old social card and retained the approved field-map artwork. |
| `experiments/specs/agentic_dynamics_rebrand.yaml` | Defines the reusable scope, implementation, and verification workflow. |
| `docs/agentic_dynamics_rebrand_plan.md`, `docs/agentic_dynamics_rebrand_verify.md` | Record the scoped implementation and verification evidence. |

`firebase/public/data.js` was not changed. The generated measurements, formulas, bindings, and provenance therefore remain on the same data artifact. Session telemetry is not part of the cutover commit.

## Manual Follow-ups

1. **Rename the GitHub repository.** In GitHub repository settings, rename `peparhugo/ai-finops-framework` to `peparhugo/agentic-dynamics`. After the rename, update the local remote to `git@github.com:peparhugo/agentic-dynamics.git` and verify the public HTTPS URL and clone command. The source links intentionally point at the future slug now; they may return 404 until this operational rename is complete.

Do not acquire or configure a custom domain. Continue using `https://ai-finops-rulebook.web.app` for the site, Open Graph page URLs, Open Graph image URL, sitemap, and robots metadata.
