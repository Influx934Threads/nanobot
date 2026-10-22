---
name: supadata
description: Extract transcripts, metadata, and engagement stats from YouTube, TikTok, Instagram, Facebook, and X videos via the Supadata API. Also supports web scraping and crawling.
homepage: https://supadata.ai
metadata: {"nanobot":{"emoji":"📊","requires":{"env":["SUPADATA_API_KEY"]}}}
---

# Supadata

Extract transcripts, metadata, and structured data from social media videos and web pages.

**Base URL**: `https://api.supadata.ai/v1`
**Auth**: All requests require header `x-api-key: $SUPADATA_API_KEY`
**Sign up**: https://dash.supadata.ai (free tier: 100 credits/month)

Set your key in the environment or in nanobot config before using this skill.

## When to use (trigger phrases)

- "get the transcript of this YouTube/TikTok/Instagram/video"
- "how many views/likes does this video have?"
- "scrape this page / crawl this site"
- "analyze this video" / "extract structured data from this video"
- "what is this video about?" (when a URL is provided)

## Endpoints

### Transcript — `/v1/youtube/transcript`

Get transcript (with timestamps) from a YouTube video.

```bash
curl -s "https://api.supadata.ai/v1/youtube/transcript?url=VIDEO_URL&text=true" \
  -H "x-api-key: $SUPADATA_API_KEY"
```

Parameters:
- `url` — YouTube video URL or ID (required)
- `text=true` — return plain text instead of timestamped JSON
- `lang` — preferred language code (e.g. `en`, `es`); falls back to auto

### Video transcript (all platforms) — `/v1/video/transcript`

Supports YouTube, TikTok, Instagram, Facebook, X, and direct video file URLs.

```bash
curl -s "https://api.supadata.ai/v1/video/transcript?url=VIDEO_URL" \
  -H "x-api-key: $SUPADATA_API_KEY"
```

### YouTube metadata — `/v1/youtube/metadata`

Returns title, description, channel, view count, like count, comment count, duration, upload date.

```bash
curl -s "https://api.supadata.ai/v1/youtube/metadata?url=VIDEO_URL" \
  -H "x-api-key: $SUPADATA_API_KEY"
```

### Video analysis — `/v1/video/analysis`

AI-powered extraction of structured JSON insights from a video (topics, key points, sentiment, etc.).

```bash
curl -s -X POST "https://api.supadata.ai/v1/video/analysis" \
  -H "x-api-key: $SUPADATA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"url": "VIDEO_URL"}'
```

### Web scrape — `/v1/web/scrape`

Extract clean text content from a single web page.

```bash
curl -s "https://api.supadata.ai/v1/web/scrape?url=PAGE_URL" \
  -H "x-api-key: $SUPADATA_API_KEY"
```

### Web crawl — `/v1/web/crawl`

Crawl a site and extract content from multiple pages.

```bash
curl -s -X POST "https://api.supadata.ai/v1/web/crawl" \
  -H "x-api-key: $SUPADATA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"url": "SITE_URL", "limit": 10}'
```

## Usage notes

- All responses are JSON.
- For long transcripts, summarize by default and offer to return the full text on request.
- For engagement stats, present numbers in a readable format (e.g. "1.2M views, 45K likes").
- If `SUPADATA_API_KEY` is not set, ask the user to add it to their environment and point them to https://dash.supadata.ai.
- Credit costs vary by endpoint — transcripts are cheaper than video analysis.

## Integration with Competitive Analysis

When used alongside the competitive-analysis skill, Supadata can:
- Pull transcripts from competitor YouTube channels to analyze messaging and talking points
- Fetch engagement stats to gauge content performance across platforms
- Scrape competitor landing pages or documentation for intelligence gathering (Step 2)
