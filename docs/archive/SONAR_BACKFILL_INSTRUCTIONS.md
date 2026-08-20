---
status: superseded
superseded_by: consolidation_release/stage_map §5 (one-time backfill, archived in S3)
---
# SonarQube Backfill Instructions

You have the full project context loaded. Your single task:

Run `python scripts/backfill_sonar.py` to enrich existing experiment results with SonarQube code quality metrics.

## Pre-flight check

```bash
# Verify SonarQube is running
curl -s -o /dev/null -w "%{http_code}" http://localhost:9000
# Expected: 200

# Verify the backfill script exists
ls scripts/backfill_sonar.py
```

If SonarQube isn't running:
```bash
cd /home/drseuss/ai-finops-framework/infrastructure
docker-compose -f docker-compose.sonar.yml up -d
# Wait ~30s for boot, then retry curl check
```

## Run the backfill

```bash
export PATH="$HOME/.local/bin:$PATH"
cd /home/drseuss/ai-finops-framework

# Full backfill (all 205 worktrees, ~100 min):
python scripts/backfill_sonar.py

# Or batch of 20 first to test:
python scripts/backfill_sonar.py --limit 20
```

## What it does (safely)

- Reads `experiments/results/_results_summary.json` (READ ONLY — never modified)
- For each worktree with a `code/` directory, runs Docker-based sonar-scanner
- Fetches quality metrics from the SonarQube API
- **Writes to a NEW file**: `experiments/results/_results_summary_sonar.json`
- Original `_results_summary.json` is **untouched**
- A backup exists at `_results_summary.json.bak`

## After completion

```bash
# Verify output
python3 -c "
import json
d = json.loads(open('experiments/results/_results_summary_sonar.json').read())
entries = d['entries']
enriched = [e for e in entries if e.get('sonar_analyzed')]
print(f'{len(enriched)}/{len(entries)} entries have sonar data')
if enriched:
    e = enriched[0]
    print(f'Example: {e[\"worktree_name\"]} — {e[\"sonar_bugs\"]}b {e[\"sonar_code_smells\"]}s {e[\"sonar_ncloc\"]}loc gate={e[\"sonar_quality_gate\"]} score={e[\"sonar_quality_score\"]:.3f}')
"

# If results look good, you can optionally replace the original:
# cp experiments/results/_results_summary.json experiments/results/_results_summary.json.pre_sonar
# cp experiments/results/_results_summary_sonar.json experiments/results/_results_summary.json
# Rebuild website data: python scripts/build_data.py
# Deploy: firebase deploy --only hosting
```

## Notes

- Each scan takes ~30s per worktree (Docker pull of scanner-cli is cached after first run)
- Some worktrees may fail silently (missing project files, non-code dirs) — these are skipped
- The script shows live progress: `worktree_name... 0b 6s 995loc gate=OK score=0.955`
- All temp scanner files are destroyed because Docker uses `--rm`
- The `sonarsource/sonar-scanner-cli` image is ~500MB (one-time pull)
