# DSPM News Archive — Shared Repository Plan

## Goal

Make the DSPM news archive maintainable by nanobot and queryable by multiple independent consumers, using GitHub as the distribution layer.

---

## Repository

**Name:** `dspm-news-archive`
**Visibility:** public or private (owner's choice)

---

## Repository Structure

```
dspm-news-archive/
  archive/
    dspm_news_2023-05.jsonl
    dspm_news_2023-08.jsonl
    dspm_news_2024-01.jsonl
    ...                          ← one file per month, append-only
  index.json                     ← lightweight metadata index (no full_text)
  schema.json                    ← field definitions and types
  README.md                      ← auto-updated: article count, date range, latest entry
```

---

## Data Format

### Archive files (`archive/*.jsonl`)

Each line is a JSON object. Fields per the existing schema:

| Field | Type | Notes |
|---|---|---|
| `id` | string | Stable slug, e.g. `2026-02-veeam-agent-commander-launch` |
| `timestamp` | ISO 8601 | Publication date |
| `fetch_date` | ISO 8601 | Date nanobot fetched the entry |
| `vendor` | string | |
| `category` | string | e.g. Product Launch, M&A, Partnership |
| `title` | string | |
| `summary` | string | |
| `full_text` | string | Full article body |
| `source_url` | string | |
| `tags` | string[] | |
| `keywords` | string[] | |
| `embeddings` | null | Not stored in repo — derived data, rebuilt locally |
| `metadata` | object | `date_range`, `source_type`, `lang`, `search_terms_used` |
| `partnership_tags` | string[] | |

### Index file (`index.json`)

Lightweight array of article metadata — no `full_text` or `summary` — for fast querying without loading the full archive. Fields: `id`, `timestamp`, `fetch_date`, `vendor`, `category`, `title`, `source_url`, `tags`, `keywords`.

---

## What Nanobot Maintains

Nanobot's existing daily fetch cron (`dspm_daily_fetch_and_sync.sh`) is extended to:

1. Fetch new articles (existing behavior)
2. Append new entries to the appropriate monthly JSONL file (existing behavior)
3. Regenerate `index.json` from all JSONL files
4. Update `README.md` with current article count, date range, and latest entry
5. `git add / commit / push` to `dspm-news-archive`

The commit message is auto-generated, e.g.:  
`chore: add 3 articles (2026-05-25), total 137`

---

## What Is NOT in the Repository

- **ChromaDB / embeddings database** — binary, 15MB, derived data. Each consumer rebuilds it locally from the JSONL using their preferred embedding model. The `embeddings` field in the JSONL is always `null`.
- **Weekly and monthly digest `.md` files** — these are nanobot's own analysis outputs; consumers generate their own.

---

## Consumer Usage

Consumers can access the archive in two ways:

**Clone/pull** (full access, local querying):
```bash
git clone https://github.com/<owner>/dspm-news-archive
# or, to update:
git pull
```

**GitHub raw URLs** (no clone required, single-file access):
```
https://raw.githubusercontent.com/<owner>/dspm-news-archive/main/index.json
https://raw.githubusercontent.com/<owner>/dspm-news-archive/main/archive/dspm_news_2026-05.jsonl
```

### Example consumer use cases

- Load all JSONL files and run vendor frequency analysis
- Filter by `category` or `tags` to track a specific topic over time
- Use `index.json` as a lightweight feed (poll for new entries by comparing `fetch_date`)
- Rebuild a local vector DB from `full_text` for RAG / semantic search
- Feed articles into a separate LLM pipeline for custom digest or classification

---

## Update Propagation

GitHub is pull-based. Consumers get updates by:

- Polling: `git pull` on a schedule, or fetching `index.json` and comparing the latest `fetch_date`
- GitHub webhooks: subscribe to push events on the repo for near-real-time notification

A dedicated API layer is not needed for a daily-updated news archive.

---

## Open Questions Before Implementation

1. **Visibility** — public repo (anyone can access) or private (shared with specific accounts)?
2. **GitHub account** — push from nanobot's host using a deploy key or a PAT stored in nanobot config?
3. **Backfill** — push the existing 134 articles as the initial commit, or start fresh from a cutoff date?
4. **`index.json` format** — flat array, or grouped by month/vendor for easier partial loading?
5. **README template** — auto-generated stats only, or also include a usage guide for consumers?
