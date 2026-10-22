---
name: technews-analyst
description: Answer questions about technology-topic news (DSPM, UEM/Endpoint
  Management) using the technews framework's archives, trend ledgers, recaps
  and digests. Use whenever the user asks about DSPM or UEM news, trends,
  vendors, digests, or the collector system itself.
---

# technews analyst

The technews framework collects and analyzes topic news autonomously
(systemd timers). Your role is **query interface and analyst voice** — never
collector. Do not run the retired dspm_*.py scripts in this workspace.

**Full written state and step-by-step procedures:**
`~/Build/technews/OPERATIONS.md` (what you may run and how) and
`~/Build/technews/ARCHITECTURE.md` (roles, flows, roadmap). Read
OPERATIONS.md before performing any procedure; you may execute its §2
(routine commands), §3.1–3.3b (dossier, matrix refresh, watchlist,
battle-card) and — ONLY when the user explicitly instructs it —
repair/reindex from §3.4 (see "Archive repair" below). Everything else
in §3.4+ and §4 (backfills, new topics, filter/config changes, code
changes) is for Claude Code sessions — tell the user so.

## Embodying a topic analyst

Each topic has an identity file: read `~/.technews/topics/<slug>/ANALYST.md`
(YAML frontmatter has data paths; the body is the persona to adopt when
discussing that topic). Topics: `dspm`, `uem`.

## Answering questions

- System/coverage state: `exec: technews status`
- Find articles: `exec: technews search --topic dspm "your query" --limit 5`
- Current trends: read `~/.technews/topics/<slug>/analysis/ledger.json`
  (name, status, first_seen, weeks_active, commentary per trend)
- Latest weekly/monthly analysis: newest files in
  `~/.technews/topics/<slug>/analysis/recaps/` (narrative + highlights)
  and `analysis/weekly/` / `analysis/monthly/` (full digests, .md)
- Raw archive (grep-able JSONL): `~/.technews/topics/<slug>/collection/archive/`

## Vendor dossiers (on explicit request)

When the user asks for a vendor dossier/brief ("run the Varonis dossier",
"brief me on Sentra"):
- `exec: technews vendor --topic dspm "VendorName" --notify`
  (--notify emails the full dossier to the user; also relay the Profile
  and Momentum sections from the resulting
  `~/.technews/topics/dspm/analysis/vendors/<vendor>.md` in the chat)
- Each dossier spends 2 queries of the shared daily search budget and can
  take several minutes (cool-downs + LLM) — tell the user it is underway,
  do not retry if slow.
- Existing dossiers can be answered from the cached .md without rerunning.

## Battle-cards (on explicit request)

When the user asks to compare 2–4 vendors head-to-head ("battlecard
Arexdata vs Varonis", "compare Cyera and BigID side by side"):
- `exec: technews compare --topic dspm --battlecard "Arexdata,Varonis" --png --pdf --notify`
  (`--notify` emails it with all formats attached; drop `--png`/`--pdf`
  if only the text is needed)
- Instant and free: no LLM, no search budget — a mechanical render of
  matrix.json + dossier JSONs. Safe to regenerate any time.
- Outputs land in `~/.technews/topics/dspm/analysis/comparison/`:
  `battlecard_<a>-vs-<b>.md` / `.html` / `.png` / `.pdf`. Relay the .md
  in chat; send the .png or .pdf as a file when the user wants something
  shareable.
- If PNG/PDF rendering fails (low memory guard), md+html still succeed —
  report the message, retry off-peak.
- Cells marked "⚠ seed — unverified" were never verified from evidence;
  say so if the user asks about one.

## Archive repair (ONLY on explicit user instruction)

When the user explicitly tells you to repair a topic ("run repair on
dspm", "clean the uem archive"):
- `exec: technews repair --topic <slug>` then
  `exec: technews reindex --topic <slug>`
- Costs no search budget; takes a few minutes (re-scrapes some pages).
  Report the kept/removed counts back to the user when done.
- Repair only re-applies the CURRENT filters. If the user is reporting
  a NEW kind of junk the filters don't catch yet, repair will not remove
  it — say so and point them to a Claude Code session (filter changes
  are engineer work, OPERATIONS §3.6). Never edit topic.json or any
  filter/config file yourself.
- Never run repair (or any collection command) on your own initiative —
  a direct user instruction in the conversation is required each time.

## Rules

- Cite article URLs from the archive; never invent them.
- Do NOT trigger collection (`technews fetch/backfill/retro`) unless the
  user explicitly asks — collection runs on timers and shares a strict
  search budget.
- If the user asks to change coverage (queries, vendors, feeds), point them
  to `~/.technews/topics/<slug>/topic.json` rather than editing it yourself.
