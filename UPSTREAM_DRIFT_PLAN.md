# Nanobot Upstream Drift — Analysis & Remediation Plan

Written 2026-10-22. Every fact below was pulled directly from `git log`/`git diff` against the live repo and the live `~/.nanobot/` runtime — nothing here is guessed or recalled from memory. Re-verify commit counts/dates before acting on this if much time has passed since.

## 1. Executive summary

This installation is running a fork of `HKUDS/nanobot` that branched **7 months ago** (2026-03-19) and has **2 local commits** on top of that point (last touched 2026-07-07, over 3 months ago). Upstream has moved **3,697 commits** past the fork point in that same window — an average of ~17 commits/day, a genuinely high-velocity project. The files the local patches touch have mostly been **rewritten wholesale** upstream since (one deleted outright, others changed by 1,500-3,000+ lines). A mechanical git rebase/merge is not a realistic path — the conflict surface would be enormous and largely meaningless (comparing old code to code that no longer has the same shape). Closing this gap requires **re-implementing the still-needed custom behavior against current upstream code**, not merging old diffs forward.

The good news, found while investigating: at least two of the local patches appear to have been **substantially superseded by upstream's own evolution** — upstream now has its own native provider-fallback mechanism and its own config-driven SSRF allowlist, which look like they may cover what the local patches were built to do. That shrinks the real porting burden to the pieces that are still genuinely custom.

Separately, and independently of the code-fork question, there is a second, much more tractable layer: **runtime customization in `~/.nanobot/`** (config.json provider/model setup, 6 custom workspace skills, cron jobs). This layer is largely orthogonal to which nanobot code version runs — it needs to be inventoried and carried forward regardless of what happens with the code fork, but it is not itself "drifted" in the same dangerous sense.

## 2. Current state — the facts

### 2.1 Code fork (`~/Build/nanobot`)

- Editable install (`pip install -e .`, package `nanobot-ai` 0.1.4.post5) — whatever branch is checked out **is** what the running `nanobot-gateway` systemd service executes. No separate build/deploy step; a branch switch takes effect on next restart.
- Two remotes: `origin` = `HKUDS/nanobot` (real upstream), `mine` = a personal fork (`Influx934Threads/nanobot`).
- Currently checked out: `local-patches` branch, HEAD `a6723a2`.
- Fork point (shared ancestor of `local-patches`, local `main`, and `origin/main`): `dd7e3e4`, dated **2026-03-19**.
- `local-patches` has exactly 2 commits past that point, the last dated **2026-07-07**:
  - `970f5d6` — config-driven network allowlist for the SSRF guard
  - `a6723a2` — "local patches: provider fallback chain, fast-model routing, ops fixes"
- `origin/main` (after a fresh fetch today) is **3,697 commits** past the same fork point, tip dated **2026-10-22** (today) — an actively, heavily maintained upstream project.
- Local `main` branch itself was never advanced past the original fork point either — it's not just `local-patches` that's stale, the plain tracking branch is too.

### 2.2 What the local patches actually touch (22 files, +1,394/−268 lines)

```
dspm-news-archive-plan.md               (new, unrelated planning doc — stray, see §4)
nanobot/agent/context.py                 11 lines
nanobot/agent/loop.py                    84 lines
nanobot/agent/memory.py                   2 lines
nanobot/agent/tools/filesystem.py        12 lines
nanobot/agent/tools/message.py           11 lines
nanobot/channels/email.py                19 lines (new block)
nanobot/cli/commands.py                 161 lines
nanobot/config/schema.py                 15 lines (new block)
nanobot/heartbeat/service.py             75 lines
nanobot/providers/base.py                56 lines (new block)
nanobot/providers/custom_provider.py      3 lines
nanobot/providers/fallback_provider.py   92 lines (NEW FILE)
nanobot/providers/litellm_provider.py   310 lines (heavy rework)
nanobot/providers/registry.py             1 line
nanobot/security/network.py              62 lines (new block)
nanobot/templates/AGENTS.md               4 lines
nanobot/templates/HEARTBEAT.md           10 lines
nanobot/utils/evaluator.py                8 lines
tests/test_background_routing.py        224 lines (NEW FILE)
tests/test_litellm_kwargs.py            190 lines (rewrite)
tests/test_loop_fast_heavy_routing.py   185 lines (NEW FILE)
```

This is real, substantial engineering — a provider fallback-chain mechanism, fast/heavy model routing, an SSRF-safe network allowlist, plus assorted operational fixes — not a handful of config tweaks.

### 2.3 How much upstream has independently changed the SAME files since the fork point

```
nanobot/providers/litellm_provider.py   DELETED upstream (−355 lines, file gone)
nanobot/providers/base.py               +1,559 / −60   (net: file nearly 30x longer)
nanobot/agent/loop.py                   +2,623 / −379  (near-total rewrite)
nanobot/cli/commands.py                 +484 / −893    (restructured, net smaller)
nanobot/security/network.py             +253 / −12
```

This is the central finding: the exact files carrying the custom logic have been rewritten at a scale where a line-level merge is not meaningful. `litellm_provider.py` — where 310 of the local patch's 1,394 lines live — **doesn't exist anymore** upstream in any recognizable form.

### 2.4 Signs some local work may now be redundant — CONFIRMED in Phase 1, see §6

First-pass greps from 2026-10-22 (superseded by the verified Phase 1 findings in §6, done 2026-10-23 — kept here only as the original hypothesis record):
- Upstream's current `providers/base.py` has its own fallback-handling fields and logic (`response_is_fallback`, `is_fallback`, fallback-candidate selection) — this may now cover what the local `fallback_provider.py` (92 lines) was built to do from scratch.
- Upstream's current `security/network.py` has its own `configure_ssrf_whitelist(cidrs)` — a config-driven allowlist, the same shape of feature the local patch added.
- No equivalent found upstream for "fast-model routing" (the `fastModel`/`fastProvider` concept visible in `~/.nanobot/config.json`) — this piece looks genuinely still-custom and will need real re-implementation against the new `loop.py`.

### 2.5 Runtime/workspace customization layer (`~/.nanobot/`) — a separate, more tractable axis

- `config.json`: `agents`, `channels`, `providers`, `gateway`, `tools` — includes the fallback-chain and fast/heavy model config that depends on the custom code above actually existing.
- 6 custom workspace skills: `competitive-analysis`, `md-to-pdf`, `privacy-filter`, `save-to-downloads`, `supadata`, `technews-analyst` — pure markdown + scripts, no dependency on the forked code, portable regardless of what happens to the fork.
- Cron jobs (`~/.nanobot/cron/jobs.json`) — at least one disabled stale job found (a DSPM weekly-digest job, `enabled: false`, superseded by technews' own now-timer-driven digest pipeline) — worth pruning as part of this effort, not just migrating blindly.
- One dated backup (`config.json.bak-20260705`) — the only evidence of a manual edit history; no broader backup/changelog discipline for this file exists.

## 3. Why this matters — risk of doing nothing

- **Security**: 7 months of upstream commits on an actively developed project almost certainly include security fixes this install doesn't have. The local SSRF-allowlist patch addresses one specific class of risk the local engineer identified — it says nothing about whatever else upstream has hardened since.
- **Bit-rot risk compounds with time, not linearly**: every month this goes unaddressed, the next attempt's merge surface gets harder, not easier — upstream isn't slowing down (3,697 commits in ~7 months, no sign of deceleration from the dates checked).
- **Single point of institutional knowledge**: the local patches' *intent* (why fallback chains, why fast/heavy routing) lives only in the two commit messages and this session's own reasoning about them — there's no design doc. If this drifts further, reconstructing *why* the fork diverged gets harder, not just *how* to re-converge.
- **Conversely — no urgency to rush**: the fork, as it stands, is reportedly working in daily production (nanobot gateway running, Telegram/skills functioning). This is a real, if diminishing, asset — not a fire.

## 4. Tradeoffs between paths

| Option | What it means | Pros | Cons |
|---|---|---|---|
| **A. Freeze as-is** | Keep running `local-patches` at `a6723a2` indefinitely, no further upstream sync | Zero immediate work; nothing breaks that isn't already broken | Security/feature gap only grows; eventually a hard wall if something *forces* an upgrade (a dependency, a breaking API change in a provider nanobot talks to) |
| **B. Mechanical rebase/merge** | `git rebase local-patches onto origin/main`, resolve conflicts file by file | Preserves full commit history | Not realistic given §2.3 — `litellm_provider.py` doesn't exist to merge into; `loop.py`'s diff is nearly a full rewrite. Conflict resolution here means re-deriving the patch's *intent* anyway, so this path doesn't actually save effort over Option C, it just dresses re-implementation up as a merge |
| **C. Re-implement on current upstream** | Start a new branch from fresh `origin/main`; port forward only the features confirmed still-needed (§2.4) against the current architecture; treat `local-patches` as a reference spec, not a diff to apply | Clean result; forces the useful feature-parity audit (§2.4) as a side effect; avoids inheriting 7 months of upstream bugs that got fixed along the way | Real work — re-understanding and re-implementing "fast/heavy model routing" against a `loop.py` that grew by 2,600+ lines is not a copy-paste job |
| **D. Ongoing sync discipline going forward** | Whichever of A/C is chosen, establish a recurring (e.g. monthly) check against `origin/main` so this gap never reaches 7 months again | Prevents recurrence | Requires actual discipline/a real recurring task, not just a one-time fix |

**Recommendation**: **C, followed by D.** Option A just defers the same work with compounding interest. Option B is a false economy — it looks like less work than C but isn't, because the files are gone/rewritten, so "merging" collapses into "re-implementing" anyway, just with extra git-conflict overhead on top. C is the honest version of the same effort.

## 5. Phased plan

**Phase 0 — Freeze and inventory (no risk, start here)**
- Tag the current state before touching anything: `git tag pre-upgrade-2026-10-22 local-patches` (and push the tag to `mine`, the personal fork, as a safety net).
- Snapshot `~/.nanobot/config.json`, the cron jobs file, and the skills directory into this repo's own history (or a dated backup) — right now the only historical record is one `.bak` file from July.
- Remove or relocate `dspm-news-archive-plan.md` from the nanobot repo root — it's a stray technews-era planning doc that doesn't belong in nanobot's own tree (found during this audit, not part of the actual patches).

**Phase 1 — Verify the feature-parity hypothesis (§2.4), before writing any new code**
- Confirm (don't assume) whether upstream's native fallback mechanism in `base.py` actually covers the local `fallback_provider.py`'s behavior — read both implementations side by side, not just grep for keywords.
- Same check for the SSRF allowlist (`configure_ssrf_whitelist` vs. the local `security/network.py` patch).
- Produce a short, explicit list: which of the 22 touched files/features are (a) now redundant and droppable, (b) still needed and must be ported, (c) ambiguous and need a product decision (not just an engineering one).

**Phase 2 — Re-implement the confirmed-still-needed pieces on a fresh branch**
- Branch from current `origin/main`, not from `local-patches`.
- Port forward only the Phase-1 "(b)" list — most likely "fast-model routing" plus whatever operational fixes in `cli/commands.py`/`heartbeat/service.py`/`channels/email.py` are still relevant to the current architecture.
- Carry the 2026-07-07 commit's intent forward, not its diff.

**Phase 3 — Validate before cutover**
- Run the new branch in parallel or on a staging config before pointing the real systemd service at it — this is a production assistant (Telegram, cron jobs, skills all live), so a cutover mistake is user-visible, not just a code review nit.
- Re-verify the 6 workspace skills and cron jobs still behave correctly against the new code (they're markdown/config, not code, but the agent loop that interprets them has been rewritten upstream — worth confirming, not assuming).

**Phase 4 — Cutover + establish ongoing sync**
- Switch the systemd service to the new branch; keep `local-patches` and its tag around as rollback, don't delete history.
- Set a recurring check (a dated reminder, a cron job, or a periodic manual session) to re-diff against `origin/main` on a real cadence — monthly is a reasonable starting point for a project moving this fast — so this report never again needs to describe a 7-month gap.

## 6. Phase 1 findings (2026-10-23) — verified, not grepped

Read both sides (local diff vs. current upstream source) for every item below — not keyword matching. Classified as **(a) droppable/redundant**, **(b) still needed, must port**, or **(c) ambiguous/needs a product decision**.

### The big one: upstream independently abandoned LiteLLM too — (a)

`litellm_provider.py` (310 of the local patch's 1,394 changed lines — the single biggest piece) rewrote the provider to use the `openai` SDK directly for OpenAI-compatible endpoints, lazy-importing LiteLLM only for genuinely incompatible providers (Anthropic). Checked upstream: **zero `import litellm` anywhere in the current codebase.** Upstream has independently gone further in the same direction — the single `litellm_provider.py` file is gone, replaced by a per-provider-family architecture: `anthropic_provider.py`, `azure_openai_provider.py`, `bedrock_provider.py`, `openai_compat_provider.py` (almost certainly upstream's own version of exactly what we built), `github_copilot_provider.py`, `openai_codex_provider.py`, `xai_grok_provider.py`, plus a new `openai_responses/` subpackage. **Verdict: (a) — drop the entire local rewrite.** Not because upstream copied us; both arrived at the same architectural call independently, and upstream's version is more complete (OAuth flows, image generation, transcription, a dedicated `routing.py`). Phase 2 should confirm `openai_compat_provider.py` actually covers our specific registry of bases (openrouter/groq/deepseek/moonshot/minimax/siliconflow/aihubmix/volcengine/byteplus/gemini/zhipu/dashscope/ollama/vllm) before fully retiring the old file, but the direction is clear.

### Fallback chain (`fallback_provider.py`, 92 lines) — (a)

Upstream's own `FallbackProvider` (same class name, same file path) is a strict superset: error-*kind* classification (only fails over on timeout/connection/rate-limit/overload — correctly skips failover for errors no other provider would fix either, e.g. invalid-request or content-filter — our version blindly retries the *whole chain* on any `finish_reason == "error"`), a circuit breaker on the primary (3 failures → 60s cooldown — ours has none), auth-error detection with reauth hints, and stream-aware partial-output resumption. **Verdict: (a) — drop, adopt upstream's.** Config: our `fallback_chain: list[{provider, model}]` maps conceptually to upstream's `fallback_models: list[FallbackCandidate]` (a `FallbackCandidate` is either a model-preset name or an inline config — more flexible than our pair-only shape).

### SSRF allowlist (`security/network.py`, 62 lines) — (a)

Upstream's `configure_ssrf_whitelist(cidrs)` does the identical allowlist-exempts-from-private-block check, wired at config-load time (`config/loader.py:136`, reading `config.tools.ssrf_whitelist` — just a different config key name than our `tools.networkAllowlist`) with comprehensive test coverage (6 test files). Upstream additionally normalizes IPv6-mapped-IPv4 addresses correctly (`::ffff:127.0.0.1` ≡ `127.0.0.1`), which ours doesn't handle. **Verdict: (a) — drop, re-point `config.json`'s key name during Phase 2/4.**

### Fast/heavy background-task routing (`loop.py`, part of the 84-line diff) — (b)

Searched thoroughly (not just loop.py — the whole tree): zero hits for `fast_model`/`fast_provider`/anything resembling background-task-type routing anywhere upstream. **Verdict: (b) — still fully custom, must be re-implemented** against the new `loop.py` (which itself grew +2,623/−379 lines, so this is a real re-implementation, not a line-paste).

### Cold-start / queue-full retry tuning (`providers/base.py`, 56-line new block) — (b)

Specific, hard-won tuning for this exact production setup: detects Ollama's queue-full response (skip retries entirely rather than worsening congestion) and Ollama's cold-start malformed-JSON response when paging a model back into memory (retry with longer 5/15/30s delays instead of the standard 1/2/4s). This is deployment-specific knowledge upstream has no reason to replicate — it doesn't know about this box's Ollama behavior. **Verdict: (b) — must port**, re-applied against whatever upstream's new per-provider retry hook looks like.

### String-boolean tool-arg coercion (`filesystem.py`, 12 lines) — (b)

Fix for models that sometimes emit `"true"`/`"false"` as JSON strings instead of booleans in tool calls (`replace_all`, `recursive`). Checked upstream's `BooleanSchema` (`agent/tools/schema.py`): it only emits `{"type": "boolean"}` to the model — no generic string-coercion exists. **Verdict: (b) — still needed if this failure mode still occurs with current models/providers**, small and easy to re-apply once the relevant tool file is located in the restructured tree.

### Email attachments via the message tool (`channels/email.py` + `message.py`, ~30 lines) — (b)

Lets the agent attach files (`msg.media`) when sending email through the generic message tool, with MIME type guessing. No upstream equivalent found (no "email" references in upstream's current `message.py`). **Verdict: (b) — still needed if this path is actually used** (note: technews/condowatch's own recent email features use their own direct `smtplib` senders, not nanobot's message tool — worth confirming this nanobot-level path is actually exercised by anything before spending porting effort on it).

### Request timeout on providers (`custom_provider.py`, `config/schema.py`) — (a)

Upstream's `ProviderConfig` already has `timeout: float = 120.0` natively. **Verdict: (a) — drop, adopt upstream's default/override mechanism.**

### Ollama "disable thinking" override (`registry.py`, 1 line: `litellm_kwargs={"think": False}`) — (c)

This was a LiteLLM-specific passthrough kwarg, and the whole `litellm_kwargs` mechanism dies with `litellm_provider.py` (see the big finding above). Upstream has a *different*, more general mechanism for thinking-model output (`extract_thinking_blocks` per-provider-spec in `registry.py`, `thinking_enabled` on the Anthropic provider) — but I did not find a direct "suppress Qwen3's chain-of-thought preamble" equivalent. **Verdict: (c) — the goal (don't pay for/show Qwen3's thinking preamble when not wanted) is still real, but the mechanism must be translated to upstream's new thinking-content model, not ported as-is. Needs a decision during Phase 2 on which of upstream's knobs actually achieves the same practical effect.**

### Memory consolidation threshold (`agent/memory.py`, 2 lines) — (b)

Trivial, standalone: trigger token-based consolidation at 80% of the context window instead of 100%, for safety margin. Low risk, easy to re-apply wherever this logic now lives. **Verdict: (b).**

### Runtime-context model tag (`agent/context.py`, 11 lines) — (b, tied to the fallback decision)

Threads an `Active Model` line into the runtime-context block the model sees, sourced from `provider.active_model` — which only means something because `FallbackProvider.active_model` tracks which chain entry is currently live. Once we adopt upstream's own `FallbackProvider` (which upstream's `base.py` already exposes an `active_model`-equivalent concept for, per `ResponseSource.model` in the event system seen in §2.4), this should become "use upstream's existing equivalent," not a from-scratch port. **Verdict: (b), but trivial once the fallback decision lands.**

### Not yet classified — deferred to Phase 2 itself, not abstractly here

`cli/commands.py` (126 insertions/35 deletions) and `heartbeat/service.py` (70/5) — both labeled "ops fixes" in the original commit message but not yet read line-by-line. Given `cli/commands.py` alone was restructured upstream by 893 deletions/484 insertions, these need a direct read against current upstream *at porting time*, not a classification from a diff stat alone — doing that abstractly now without full context of what each hunk does would be guessing, not verifying. Same honesty standard applies to `templates/AGENTS.md` (4 lines, trivial) and `templates/HEARTBEAT.md` (10 lines, a net *removal* — worth understanding why before assuming it's still wanted) and `utils/evaluator.py` (8 lines) — all small enough to be low-risk either way, but not yet actually read.

### Net effect on Phase 2 scope

Of the local patch's 1,394 changed lines, roughly **~460 lines (fallback chain 92 + litellm rewrite 310 + SSRF 62, minus overlap)** collapse from "port this" to "delete this, adopt upstream's equivalent, re-point one config key." The genuinely-custom remainder — fast/heavy routing, cold-start/queue-full tuning, bool coercion, email attachments, the memory threshold, the model-tag context line — is real but meaningfully smaller than the original file list suggested, plus ~200 lines of `cli.py`/`heartbeat.py` ops fixes still to be read directly during Phase 2.

## 7. Open decisions — these need you, not more investigation

1. ~~Scope of Phase 1~~ — **done** (§6).
2. **Scope of the remaining Phase 1 reads**: `cli/commands.py` and `heartbeat/service.py` (~200 lines of "ops fixes," not yet read line-by-line) — read them now before Phase 2 starts, or fold that reading into Phase 2 itself as the first step of actually porting?
3. **Email-via-message-tool**: worth confirming whether nanobot's own message-tool email path (as opposed to technews'/condowatch's direct `smtplib` senders) is actually used by anything before deciding whether to port it.
4. **Risk appetite for Phase 3**: is a brief service interruption during cutover acceptable, or does this need a more careful staged rollout (e.g. a second nanobot instance/config to test against before touching the production systemd service)?
5. **Sync cadence for Phase 4**: monthly is my default suggestion given upstream's velocity — is that the right interval for how much you rely on this running correctly day to day?
