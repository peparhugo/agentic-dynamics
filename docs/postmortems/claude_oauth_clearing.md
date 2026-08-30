---
status: accepted
---
# claude_oauth_clearing — postmortem + runbook

**Subject:** `~/.claude/.credentials.json` OAuth tokens repeatedly cleared on the operator's host — every `claude` invocation then fails in ~7s at $0 (the dead-auth noise pattern `run_cap_grit_grid.py:105-126` pre-flights against).
**Diagnosed:** 2026-08-30 (evidence below) · **Watcher installed:** same day (`claude-cred-watch.service`, systemd user unit).

---

## 1. THE PLAIN ANSWER

Claude Code itself zeroes the OAuth tokens (`accessToken`/`refreshToken` → `""`, `expiresAt` → `0`) in
`~/.claude/.credentials.json` whenever a token refresh fails. The CLI's own error, captured in story
transcripts (`~/.claude/projects/-tmp-story-4176cbc93890/*.jsonl`, 20:45 run):

```
"error":"authentication_failed"
"Failed to authenticate: OAuth session expired and could not be refreshed"
```

The cleared file keeps its metadata (scopes, `subscriptionType: max`, `rateLimitTier`) — the signature of
the CLI's own "logged out / refresh failed" write, not a file deletion and not a login skeleton.

**The most likely trigger is a refresh-token rotation race:** this host runs many concurrent `claude`
processes (claude_cli story workers, `claude --bg` sessions, supervise passes, fleet smoke tests). OAuth
rotates the refresh token on every refresh; when two processes refresh concurrently with the same token,
the loser gets `invalid_grant` and Claude Code treats the session as unrecoverable and **wipes the file
for everyone**. Server-side revocation from another device (operator's iPhone/Mac on the same tailnet) is
a possible alternative; the watcher's process snapshot disambiguates the next occurrence.

## 2. Evidence trail

| Fact | Evidence |
|---|---|
| File cleared 2026-08-30 18:01:52 CEST, empty tokens, `expiresAt: 0` | `stat ~/.claude/.credentials.json`; token-state inspection |
| Last successful auth ~Aug 28-30 (`refreshTokenExpiresAt` = 2026-09-27 17:21 UTC) | field in the cleared file — the session was NOT date-expired |
| CLI's own failure message | `~/.claude/projects/-tmp-story-4176cbc93890/{68b2b480,ac8a6609,...}.jsonl` — `authentication_failed` on the 20:45 sonnet-5 story runs, all 4 cells ~7s at $0 |
| Network path healthy at diagnosis | `api.anthropic.com` → 401/405 (reachable, auth-gated); `claude.ai/oauth/...` → 200. DNS fine. |
| Not a human on the box | `last` — no local/SSH session near 18:01 (last login Aug 28; operator remote via Tailscale since) |
| Not the fleet smoke containers | they mount `~/.claude` read-only (D-2 auth contract) — cannot write the host file |
| Recurring manual re-login | `~/.bash_history` tail — repeated `claude auth login --claudeai` |

Note: `api.claude.ai` NXDOMAINs from this host and from public DoH — a red herring, the CLI's OAuth
endpoints live on `api.anthropic.com` and `claude.ai` (verified in the binary's endpoint strings).

## 3. The watcher (the fix)

`~/.local/bin/claude_cred_watch.py`, run by systemd user service `claude-cred-watch` (enabled, active,
restart-on-failure):

- polls `~/.claude/.credentials.json` every 3s;
- appends every change as JSONL to `~/.claude/credentials_watch.jsonl` — including a **process snapshot**
  (pid, start time, full args of all claude/opencode/node processes) and `lsof` on the file at the moment
  of change, so the next clear identifies the culprit instead of requiring post-mortem;
- **preserves the last-good state** at `~/.claude/backups/.credentials.good.json` the moment tokens are
  seen non-empty (the live file is currently cleared — the next successful login is snapshotted
  automatically);
- archives a forensics copy on clear: `~/.claude/backups/.credentials.cleared.<ts>.json`.

Verified end-to-end on a throwaway `HOME` (baseline pass → seeded tokens → simulated clear → CLEAR record
with process snapshot → restore). Unit/test invocation:

```bash
~/.local/bin/claude_cred_watch.py --once            # single poll pass
~/.local/bin/claude_cred_watch.py --restore         # restore last-good tokens (dead state archived first)
journalctl --user -u claude-cred-watch -n 50        # after the next incident
```

## 4. Runbook — when `claude` dies with auth errors again

1. Confirm: `claude auth status` → `"loggedIn": false`.
2. Check the watcher log for the CLEAR record + culprit process: `journalctl --user -u claude-cred-watch`.
3. Restore: `~/.local/bin/claude_cred_watch.py --restore` (or re-login: `claude auth login --claudeai`).
4. If the snapshot shows one lone process → server-side revocation suspect (check other devices); if it
   shows concurrent `claude` invocations → rotation race: serialize claude-backed story cells or route
   them through fleet containers (isolated per-cell state).
5. For unattended pipeline runs, prefer `ANTHROPIC_API_KEY` for the `claude_cli` backend over the OAuth
   session — OAuth is the fragile part.
