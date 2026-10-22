---
name: competitive-analysis
description: Systematic competitor research framework — tiering, intelligence gathering, gap identification, and ongoing monitoring. No API keys required.
homepage: https://clawhub.ai/JK-0001/competitive-analysis
metadata: {"nanobot":{"emoji":"🔎"}}
---

# Competitive Analysis

A six-step framework for solopreneur-focused competitive intelligence. Instruction-only — no external tools or credentials required.

## When to use (trigger phrases)

Use this skill when the user asks any of:
- "analyze my competitors"
- "competitive analysis for [product/market]"
- "who are my competitors and what are they doing?"
- "find gaps in the market"
- "how do I compare to [competitor]?"

## The Six-Step Framework

Work through these steps in order. Ask the user for their product/market if not already provided.

### Step 1 — Competitor Tiering

Categorize competitors into three tiers:
- **Direct**: same target customer, same problem, similar solution
- **Indirect**: same problem, different solution or different customer segment
- **Aspirational**: where the market is heading; well-funded or category-defining players

Aim for 3–5 per tier. Ask the user to validate or extend the list.

### Step 2 — Intelligence Gathering

For each competitor, collect data across these dimensions:
- **Strategy**: positioning statement, target customer, go-to-market motion
- **Product**: core features, UX quality, integrations, notable limitations
- **Pricing**: tiers, free trial, per-seat vs flat, annual discount
- **Marketing**: primary channels, content themes, SEO keywords, ad presence
- **Customer voice**: reviews on G2, Capterra, Trustpilot, app stores, social media — read **20+ reviews per competitor** to surface genuine pain points
- **Company health**: headcount growth, funding, recent news, job postings (signals investment areas)

Use web search for each competitor. Prioritize review sites for unfiltered customer sentiment.

### Step 3 — Comparison Matrix

Build a side-by-side table with the user's product in column 1 and each competitor in subsequent columns. Rows = the dimensions from Step 2. Mark each cell as ✅ strong / ⚠️ partial / ❌ absent.

### Step 4 — Gap Identification

Scan the matrix for weaknesses shared by **multiple** competitors — these are market gaps, not just one player's oversight. Look for:
- Features consistently rated poorly in reviews
- Customer segments nobody is serving well
- Pricing models that generate frequent complaints
- Support or onboarding issues mentioned across competitors

List each gap with supporting evidence (review quotes, missing features).

### Step 5 — Competitive Wedge

Define a sharp, defensible positioning angle based on the gaps found:
- One primary differentiator (not a list)
- Specific customer segment it targets
- Why it is hard for incumbents to copy quickly (switching cost, model difference, price point, etc.)

State it as a one-sentence wedge: *"For [segment], [product] is the only [category] that [specific differentiator] — unlike [competitors] which [shared weakness]."*

### Step 6 — Ongoing Monitoring

Set up a lightweight tracking cadence:
- **Weekly**: monitor competitor social media, job postings, changelog/release notes
- **Monthly**: check review sites for new sentiment shifts; re-score the comparison matrix
- **Quarterly**: full refresh of Steps 1–5; update positioning if the wedge has eroded

Recommend free tools: Google Alerts for competitor brand names, RSS feeds for their blogs, and the Supadata skill (if installed) for social media engagement tracking.

## Output format

Deliver findings as:
1. Tier list (table)
2. Comparison matrix (table)
3. Top 3 gaps (bullet list with evidence)
4. Wedge statement (one sentence, bold)
5. Monitoring checklist

Keep the tone analytical and direct. Flag when data is thin and more research is needed.
