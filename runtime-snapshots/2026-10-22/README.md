# Runtime snapshot — 2026-10-22

Phase 0 of `UPSTREAM_DRIFT_PLAN.md`: a point-in-time capture of the
`~/.nanobot/` runtime customization layer, taken before any upgrade
work starts. This is the "config/skills/cron" axis of drift, separate
from the code-fork axis the main plan document addresses.

## What's here

- `config.json` — **secrets redacted** (`***REDACTED***` for every
  key/token/secret/password field that had a real value). The full,
  unredacted file is backed up locally at
  `~/.nanobot/config.json.bak-20261022` (git-ignored territory, never
  committed — same convention as the pre-existing `config.json.bak-20260705`).
- `cron-jobs.json` — raw copy, no secrets in this one.
- `workspace-skills/` — full copy of the 6 custom skills
  (`competitive-analysis`, `md-to-pdf`, `privacy-filter`,
  `save-to-downloads`, `supadata`, `technews-analyst`). No secrets
  found in any of them (checked) — `supadata`'s SKILL.md references
  `$SUPADATA_API_KEY` as an environment variable, never a literal key.

## Findings from this pass

- **2 disabled cron jobs**, both DSPM digest generation (`01dba649`,
  `7529ffc3`) — superseded by technews' own now-timer-driven weekly/
  monthly digest pipeline (confirmed live via `systemctl --user
  list-timers`). Candidates for deletion from the live store, not
  removed yet — flagging for the Phase-0/Phase-1 regroup rather than
  deleting unilaterally.
- No other stale/orphaned entries found in this pass.
