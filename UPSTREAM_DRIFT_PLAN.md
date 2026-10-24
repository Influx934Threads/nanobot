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
- **Decided 2026-10-24: low risk accepted, brief interruption is fine** — no staged/parallel second-instance rollout. Validate with the CLI/direct-invocation path (`nanobot` commands, not the live gateway) before restarting the real service, then do a real but short-downtime restart rather than standing up parallel infrastructure.
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

### Email attachments via the message tool (`channels/email.py` + `message.py`, ~30 lines) — (a), decided 2026-10-24

Lets the agent attach files (`msg.media`) when sending email through the generic message tool, with MIME type guessing. Confirmed live via `TOOLS.md` (the agent's own documented "email X to Y mid-conversation" capability) — not dead code, but not automation-exercised either (technews/condowatch's own scheduled email features correctly use their own direct `smtplib` senders instead, a deliberate choice — see §7 decision 4 for why). The single-file `channels/email.py` is gone upstream, replaced by a full package (`channels/email/` — `runtime.py`, `validation.py`, a 10-language webui) with its own dedicated attachment test suite (`test_attachment_filenames.py`, `test_attached_message_body.py`). **Verdict: (a) — drop, adopt upstream's more mature native version.**

### Request timeout on providers (`custom_provider.py`, `config/schema.py`) — (a)

Upstream's `ProviderConfig` already has `timeout: float = 120.0` natively. **Verdict: (a) — drop, adopt upstream's default/override mechanism.**

### Ollama "disable thinking" override (`registry.py`, 1 line: `litellm_kwargs={"think": False}`) — (c)

This was a LiteLLM-specific passthrough kwarg, and the whole `litellm_kwargs` mechanism dies with `litellm_provider.py` (see the big finding above). Upstream has a *different*, more general mechanism for thinking-model output (`extract_thinking_blocks` per-provider-spec in `registry.py`, `thinking_enabled` on the Anthropic provider) — but I did not find a direct "suppress Qwen3's chain-of-thought preamble" equivalent. **Verdict: (c) — the goal (don't pay for/show Qwen3's thinking preamble when not wanted) is still real, but the mechanism must be translated to upstream's new thinking-content model, not ported as-is. Needs a decision during Phase 2 on which of upstream's knobs actually achieves the same practical effect.**

### Memory consolidation threshold (`agent/memory.py`, 2 lines) — (a), decided 2026-10-24 during Phase 2

Originally assumed trivial (2 lines, "trigger at 80% of context window instead of 100%"). Turned out not to be: the mechanism it tuned is **gone**. Checked `agent/autocompact.py` on current `origin/main` — the whole idle-consolidation strategy has been replaced: it now triggers purely on **session idle time** (`session_ttl_minutes` — "quiet for N minutes"), not context-window token size at all. Searched the entire codebase for any surviving percentage-of-context-window compaction trigger (`0.7–0.9 * context_window` patterns) — none exists anywhere. There is nothing left to apply an "80% not 100%" tweak *to*.

**Verdict: (a) — drop.** Not "upstream covers it," but the closest real finding here: diff size doesn't predict porting difficulty — a 2-line patch can hinge on an entire strategy that moved, same as a 90-line one can turn out to be a clean drop-in. Inventing a new time-based "safety margin" concept to replicate the old *intent* under the new idle-time model would be solving a problem nobody's reported having since the migration — not worth the invented complexity.

### Runtime-context model tag (`agent/context.py`, 11 lines) — (b, tied to the fallback decision)

Threads an `Active Model` line into the runtime-context block the model sees, sourced from `provider.active_model` — which only means something because `FallbackProvider.active_model` tracks which chain entry is currently live. Once we adopt upstream's own `FallbackProvider` (which upstream's `base.py` already exposes an `active_model`-equivalent concept for, per `ResponseSource.model` in the event system seen in §2.4), this should become "use upstream's existing equivalent," not a from-scratch port. **Verdict: (b), but trivial once the fallback decision lands.**

### "Ops fixes" — read in full 2026-10-23, both reclassified

**`cli/commands.py` (126 insertions/35 deletions) — no new category, it's 100% glue code.** Entirely the construction/wiring for the two already-classified features: `_make_provider_instance`/`_make_fast_provider` build the fallback chain (primary → configured fallbacks → fast model as last resort) and wire `is_background=True`/`fast_provider`/`fast_model` through to `AgentLoop`, `evaluate_response`, and the heartbeat service. **Verdict: not a separate item — gets rewritten as part of rebuilding (b) fast/heavy routing and wiring to upstream's own (a) `FallbackProvider`, not independently.**

**`heartbeat/service.py` (70/5) + `templates/HEARTBEAT.md` — reclassifies an earlier (b) down to (a)/drop, and surfaces a real "is this even still needed" question.** Big finding: **the entire `nanobot/heartbeat/` package is gone upstream** — not restructured, deleted. Heartbeat is now "backed by cron" (`HeartbeatConfig` docstring, literally) — registered as a named system cron job (`id="heartbeat"`) whose body is a **pure mechanical check**: does `HEARTBEAT.md` have non-comment text under "Active Tasks"? If yes, run; if no, skip. **There is no LLM "decide" call in the new design at all** — upstream solved "don't waste a call deciding whether to run heartbeat" by removing the decision step entirely, a different (and arguably better) answer to the same cost problem our fast-model-for-decide feature was solving.

That reclassifies the fast-model-for-heartbeat-decide piece from (b) to **(a) — moot, not droppable-because-redundant but droppable-because-the-thing-it-optimized no longer exists.**

The other half of this diff — `_collect_workspace_state()`, injecting per-task `.txt`-file "last run" dates into the heartbeat prompt so the agent knows which of *several* tasks in one `HEARTBEAT.md` are already done today — has no upstream equivalent (upstream's new mechanical check is all-or-nothing for the whole file, no per-task awareness) and is genuinely custom. But checking its only two real data files (`dspm_last_fetch_date.txt`, `dspm_monthly_retro_date.txt`) found both **stale (last updated 2026-10-16)** — because the thing they were gating (DSPM fetch + monthly retro) has since been fully migrated to technews' own systemd timers, built later in this project's own history. **Verdict: (a) — decided 2026-10-24, drop.** Reviewed the workspace .md history (§7, decision 3) before deciding: the date-gate protected against a 30-minute LLM-polling loop re-triggering the same task multiple times per day — a failure mode systemd timers (fire once, no polling judgment call) don't have at all, not a gap they leave open. Confirmed via the files' own commentary, not assumed from staleness alone.

`templates/AGENTS.md` (4 lines) — a standalone, prompt-only instruction ("don't interrupt mid-task to ask permission between steps, only when genuinely blocked"), unrelated to any of the above. Upstream's `AGENTS.md` template still exists in similar form. **Verdict: (b), trivial, zero technical risk, re-apply verbatim.**

`utils/evaluator.py` (8 lines) — exclusively "use the fast provider for this cheap background-response judgment call if configured." Part of the fast/heavy routing feature group, not separate. **Verdict: (b), rebuilt alongside that feature, not independently.**

### Net effect on Phase 2 scope (updated)

Of the local patch's 1,394 changed lines: **~460 collapse to (a)** (fallback chain 92 + litellm rewrite 310 + SSRF 62) **plus now the heartbeat fast-model-decide piece** (part of the 70-line heartbeat diff) — all "delete, adopt upstream's equivalent, re-point one config key" rather than port. **~200 lines of `cli/commands.py` are pure wiring**, rewritten as a side effect of rebuilding fast/heavy routing, not separately. The workspace-state per-task date-gating is a **(c) product question** that may simply not need rebuilding at all given its real-world use case already evaporated. The genuinely custom, must-port remainder is now down to: fast/heavy background-task routing itself, cold-start/queue-full retry tuning, string-boolean tool-arg coercion, email-via-message-tool attachments, the memory consolidation threshold, the AGENTS.md instruction, and the model-tag context line — smaller and clearer than either the original 22-file list or the first-pass Phase 1 estimate suggested.

## 7. Open decisions — these need you, not more investigation

1. ~~Scope of Phase 1~~ — **done** (§6).
2. ~~Scope of the remaining Phase 1 reads~~ — **done** (§6, "ops fixes" section): both read in full, `cli/commands.py` turned out to be pure wiring for already-classified features, `heartbeat/service.py` reclassified one item and surfaced decision #3 below.
3. ~~Workspace-state heartbeat date-gating~~ — **decided: drop, don't port** (2026-10-24). Reviewed the full history in the workspace .md files (`HEARTBEAT.md`'s own migration comment, the archived `HEARTBEAT-dspm-retired.md`, and the original task definition in `HEARTBEAT-old.md`) to confirm the rationale before deciding, not just assuming staleness meant irrelevance. Confirmed: the date-gate existed to stop a **30-minute polling loop** from re-triggering the same daily task multiple times per day via repeated LLM "should I run this?" judgment calls — `HEARTBEAT-old.md`'s own text: "FIX: date file now updated after each run to prevent duplicate fetches." Systemd timers fire exactly once at a scheduled time with no polling judgment call in between, so they don't have the failure mode the date-gate protected against — not "already covered by a different mechanism," genuinely not applicable to how timers work. Also found (bonus, from the same files): even marking a heartbeat task "Paused" in markdown wasn't reliable — "the fast heartbeat model executed them even under a 'Paused' heading" — a second, independent reason this whole LLM-judgment-based gating approach was fragile. No evidence anywhere that heartbeat was ever intended as a timer failsafe/backup. Clean to drop.
4. ~~Email-via-message-tool~~ — **decided: drop, adopt upstream's** (2026-10-24). Confirmed it IS live — documented in `TOOLS.md` as the agent's ad-hoc "email X to Y mid-conversation" capability, distinct from technews'/condowatch's own direct-`smtplib` scheduled senders (different purpose: agent-mediated/ad-hoc vs. fixed/scheduled, and `dspm_notify.py`'s own docstring confirms the direct-smtplib lineage is deliberate — "without going through [nanobot]," so the agent/gateway being down never blocks a scheduled report). Same pattern as fallback-chain/SSRF: upstream's `channels/email/` is now a full package with its own dedicated attachment test coverage (`test_attachment_filenames.py`, `test_attached_message_body.py`) — more mature than our 19-line patch. Drop ours.
5. ~~Risk appetite for Phase 3~~ — **decided: low risk, brief interruption accepted** (2026-10-24). No staged/parallel rollout — a short real restart of the production systemd service is fine.
6. ~~Sync cadence for Phase 4~~ — **decided: monthly** (2026-10-24).

All open decisions closed. Proceeding to Phase 2 (2026-10-24).

## 8. Phase 2 progress log (2026-10-24)

Branch `upstream-rebuild`, forked from `origin/main` at `3c022ad` (today).

**Infrastructure finding, before any porting**: the editable install itself was also stale — `rapidfuzz` (a real declared dependency in current `pyproject.toml`) had never been installed, so none of upstream's current test suite could even run. `pip install -e . --break-system-packages` (matching the system's existing externally-managed-environment install method, not a new pattern) brought the package from `0.1.4.post5` to `0.3.5` and fixed it — `tests/tools/test_filesystem_tools.py` went from an import error to 51/51 passing. **Confirmed safe**: the live `nanobot.service` process (PID running continuously since 2026-09-19) has the old code loaded in memory already; an editable install's on-disk branch/package changes only take effect on the next restart, which hasn't happened. No production disruption from this work so far.

Ported so far, each verified before moving on:
- **Memory consolidation threshold — dropped**, see §6 (mechanism it tuned no longer exists).
- **`templates/AGENTS.md` "Multi-Step Tasks" instruction** — clean port, inserted after "Workspace Guidance" and before the current "Scheduled Reminders" section (the file's structure grew a section in between, but the insertion point concept — right after the general guidance intro — still applies). Verified no test asserts the template's literal content.
- **String-boolean tool-arg coercion** (`EditFileTool.replace_all`, `ListDirTool.recursive`) — clean port, same fix, same two call sites still exist under the same names. One adaptation: the JSON schema declared to the model stays `BooleanSchema` (boolean-only) rather than the old patch's `["boolean", "string"]` — upstream's typed schema class has no multi-type option, and the runtime coercion is what actually matters (it's defensive against a model ignoring the schema anyway, which is the original failure mode). `tests/tools/test_filesystem_tools.py`: 51/51 passing after the change.
- **Cold-start / queue-full retry tuning** — the riskiest port so far (shared retry/fallback control flow every provider call goes through), done as two small, separately-targeted additions rather than one bolted-on mechanism, each at the layer that already owns that concern:
  - Checked first what upstream's current `_TRANSIENT_ERROR_MARKERS` already covers — "timeout"/"timed out"/"connection" already catch our old `readtimeout`/`request timed out` strings as substrings, so most of the original marker list turned out to be redundant, not missing.
  - **Genuinely missing, item 1**: `"server is busy"` / `"queue is full"` / `"too many requests in queue"` — added to `FallbackProvider._FALLBACK_ERROR_TOKENS` (the mechanism Phase 1 already decided to adopt wholesale) rather than inventing a new bail-out path in `base.py`. Verified end-to-end against the real `FallbackProvider._should_fallback()` method, not just tuple membership: a `"server is busy"` response now correctly triggers failover, an unrelated error correctly doesn't.
  - **Genuinely missing, item 2**: Ollama's cold-start malformed-empty-body error (`"expecting value: line 1 column 1"`) needs *longer* retry delays on the *same* provider, not a failover — a different concern than item 1, so it stays in `base.py`'s own retry loop. Added `_COLD_START_RETRY_DELAYS = (5, 15, 30)` and `_is_cold_start_error()` alongside the existing `_CHAT_RETRY_DELAYS`/`_is_transient_error()` (same naming convention, same placement), then changed exactly one line in `_run_with_retry` to pick the cold-start delay table instead of the default one when that marker matches — server-provided `Retry-After` still takes priority unchanged, and the attempt-count/exhaustion logic is untouched (both delay tuples happen to be length 3, so attempt budgets stay identical — cold-start gets more *patience* per attempt, not more attempts).
  - `tests/providers/test_provider_retry.py`, `test_provider_retry_after_hints.py`, `test_provider_sdk_retry_defaults.py`, `tests/agent/test_runner_fallback.py`, `test_mcp_transient_retry.py`, `tests/cli/test_interactive_retry_wait.py`: 191/191 passing after both changes.
