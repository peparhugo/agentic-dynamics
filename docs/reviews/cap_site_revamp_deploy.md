# CAP Site Revamp Deploy Log

**Status:** PASS

**Published commit:** `b57e27595` (`data: refresh site publication receipt`)

## Fresh Data Chain

```text
python3 scripts/sync_data.py
Synced: 1067 sessions, 215 stories

python3 scripts/build_data.py
Wrote apps/website/data.js (131656 bytes)

python3 scripts/generate_manifest.py
Written experiments/data_manifest.json
registry: 12152 entities (compacted from registry_index.jsonl)
```

## Firebase Deploys

```text
firebase deploy --only hosting
Project: ai-finops-rulebook
Hosting URL: https://ai-finops-rulebook.web.app
Deploy complete: PASS

firebase deploy --only hosting --project agentic-dynamics
Project: agentic-dynamics
Hosting URL: https://agentic-dynamics.web.app
Deploy complete: PASS
```

## Post-Deploy Verification

```text
curl canonical home: 200
curl mirror home: 200

diff canonical-home-html mirror-home-html
No output: PASS (byte-identical HTML)

canonical home smoke: PASS
  - data.js is loaded
  - design-components.js is loaded
  - the instrument-cycle diagram slot is present

canonical evidence-diagram smoke: PASS
  - app.js is loaded
  - calibration and escalation diagram slots are present
```

The published information architecture did not change in this final refresh, so
`robots.txt`, `sitemap.xml`, and the social-image configuration required no update.
