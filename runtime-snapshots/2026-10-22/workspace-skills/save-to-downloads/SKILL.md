---
name: save-to-downloads
description: Use when the user sends a file/document in chat and asks to
  save it, drop it, or get it onto this machine's Downloads folder — e.g.
  so a local file-watching automation on this box picks it up. Trigger
  on explicit wording ("save this", "drop this in downloads", "put this
  somewhere X picks it up") or on a bare file upload with no other
  instruction when the conversation context makes the intent obvious.
---

# Save to Downloads

A small, generic bridge: the user is remote (phone, another machine) and
wants a file they just sent in chat placed into `~/Downloads/` on *this*
machine, exactly as if they'd saved it there themselves locally. This
skill's only job is that handoff — it has no opinion about what happens
to the file afterward, and no dependency on any other project or
automation. Any local tool that watches `~/Downloads/` (a systemd path
unit, a cron job, a manual check) picks it up the same way either way.

## When a message includes an attached file

The channel has already downloaded the file before your turn starts —
the message content includes a line like `[file: /path/to/it.ext]` or
`[document: /path/to/it.ext]` with the real local path. That path is
NOT in `~/Downloads/` yet (channels keep their own media directory,
e.g. `~/.nanobot/runtime/media/<channel>/`), and its filename there is
an opaque id, not the name the user's device gave it — the original
filename is not recoverable, only the extension survives.

## What to do

1. Confirm the attached path actually exists and is non-empty.
2. Copy (never move — keep the channel's own copy intact) it into
   `~/Downloads/`, naming it something short and descriptive based on
   the conversation (what the user called it, or what it obviously is)
   plus today's date, keeping the original extension from the source
   path. Example: `cp /path/to/abc123.html ~/Downloads/idealista-2026-10-22.html`
3. If a file with that exact name already exists in `~/Downloads/`,
   append a counter or timestamp rather than overwriting it — the user
   may be sending several over time and a silent overwrite could lose
   one.
4. Tell the user plainly: the file is now at `~/Downloads/<name>`, and
   nothing else — don't guess at or report what happens to it next,
   since this skill doesn't know and isn't responsible for that.

## What NOT to do

- Don't inspect, summarize, or act on the file's content — that's
  outside this skill's job; another skill or a local automation handles
  what the file actually is.
- Don't rename or convert the file beyond giving it a sane name — pass
  it through byte-for-byte.
- Don't apply this to a file the user didn't actually send this turn
  (or ask you to re-send) — never go fetch or relocate an unrelated
  file just because a path is mentioned elsewhere in the conversation.

## Example use case (illustrative only — this skill has no dependency on it)

A user tracking real-estate listings might run automated fetches
against several property portals, with this manual path standing in
whenever that automation can't get a page itself — for any reason:
- a site that outright blocks automated fetching with a bot-defense
  service (DataDome, Cloudflare, etc.) no local tool can pass,
- a one-off local failure (network hiccup, a transient block, a
  temporary IP-level rate limit) on a site that's normally fine, or
- any other case where "just go look at it yourself" is faster than
  debugging why the automation didn't get through this time.
In every case the shape is the same: browse the page on a phone or
another machine, save it with a "complete webpage" browser extension,
and send that file to this chat. This skill drops it into
`~/Downloads/`; a separate local tool (unrelated to this skill) that
already watches that folder for new snapshots then picks it up and
processes it — this skill never needs to know that tool exists, or
which of the above reasons triggered the manual save this time.
