---
name: session-log
description: >
  USE WHEN ending a substantial working session — user says
  "thanks/tomorrow/wrap up", or session shipped 3+ commits with no log
  today, or user asks for a summary. Distills the conversation into
  `docs/sessions/YYYY-MM-DD-<topic>.md` (context, what was done, key
  decisions, open questions, next steps). Hard cap ~80 lines.
  Distillate, NOT transcript. See `docs/sessions/README.md`.
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Bash(git rev-parse:*)
  - Bash(git log:*)
  - Bash(git branch:*)
  - Bash(date:*)
  - Bash(ls:*)
argument-hint: "[topic-one-liner] [--noninteractive]"
---

# /session-log

## What it does

At the end of a working session, writes a short distilled summary to
`docs/sessions/YYYY-MM-DD-<topic>.md` following the standard template
(context, what was done, key decisions, open questions, next steps,
references). The next agent — yours tomorrow, or a different agent in a
month — reads it to pick up the thread without re-discovering everything
cold.

This is **not a transcript dump**. Raw chat is noise the next agent
can't usefully consume. A session log is the *distillate*: 30–80 lines
that compress a multi-hour conversation into actionable continuity.

## Workflow

1. **Find target dir.** Default `docs/sessions/` from the current repo
   root (via `git rev-parse --show-toplevel`). If it doesn't exist, ask
   "create it now?" — if yes, create with a stub `README.md` describing
   the convention (mirror the one shipped with this plugin at
   [`docs/sessions/README.md`](../../docs/sessions/README.md)).

2. **Get topic.** If `$ARGUMENTS` has a positional, use it. Otherwise
   ask: "what was this session about, in one line?" Convert to
   kebab-case for the filename: `2026-05-24-pivot-cleanup.md`.

3. **Compute filename.** `YYYY-MM-DD-<kebab-topic>.md`. If a file with
   the same name exists (multiple sessions on the same topic same day),
   suffix with `-2`, `-3`, etc.

4. **Gather facts** from git and the conversation:
   - Current branch: `git rev-parse --abbrev-ref HEAD`.
   - Recent commits this session: `git log --oneline -10`. Use the
     first commit hash *after* the previous session's HEAD if you
     can infer it, otherwise show the last 5–10 with the human
     confirming which ones belong.
   - Conversation summary: distill from the actual chat above (you,
     the model, have access). Categorize into:
     - **What was done** — concrete actions: code shipped, decisions
       recorded, files moved, skills added. Bullet list.
     - **Key decisions** — non-obvious calls made in conversation.
       Link to ADRs if applicable (suggest `/adr-new` for any
       decision likely to be re-litigated).
     - **Open questions** — anything deferred or unresolved.
     - **Next steps** — what should happen first in the next session.

5. **Generate the file** using the template
   ([`docs/sessions/template.md`](../../docs/sessions/template.md)).
   Substitute:
   - Topic, date, branch, participants (you + model name).
   - Each section filled from step 4. Use `<TODO>` for anything you
     genuinely can't infer; better an honest gap than a fabrication.

6. **Hard cap on length.** If your draft is over 80 lines, reduce. Cut
   the "what was done" bullets to the load-bearing 5–8. Move tactical
   detail into commit messages, ADRs, or specs. The session log is
   *pointers + decisions + next-actions*, not a play-by-play.

7. **Report.** Print the file path and one line:
   > "Next session: start by reading `docs/sessions/<filename>` plus
   > the last 1–2 prior session logs."

## Hard rules

- **Distillate, not transcript.** If the user asks "include the full
  conversation," push back. The full conversation is in Claude
  Code's session history; the journal is for future-agent
  consumption.
- **No fabrication.** If you don't know what "was done" because the
  conversation was mostly planning, write that explicitly:
  *"Session was planning-only — no code shipped. Plan landed in
  `docs/specs/<file>`."*
- **Link, don't duplicate.** ADRs, specs, commits get linked by
  number/hash — never copied into the session log body.
- **Pre-existing session logs are immutable.** If you're amending,
  write a new dated file (`-2`, `-3` suffix) rather than editing.

## Tunables

- `--noninteractive` — skip prompts; requires a topic positional.
  Pulls everything else from git + the visible conversation context.
- `--dry-run` — print the generated content to stdout, write nothing.

## When to invoke

- **End of a substantial working session.** Substantial = anything
  that shipped a commit chain or made a load-bearing decision.
- **NOT after a quick one-shot fix.** A 5-minute typo fix doesn't
  need a journal entry; the commit message is enough.
- **NOT after a pure-exploration session.** If you didn't decide
  anything and didn't ship anything, there's no continuity to
  preserve.

A useful rule of thumb: would the next agent benefit from knowing
where this session left off? If yes, write the log. If no, skip.

## Pairs with

- **`/adr-new`** — when a session produces a load-bearing decision,
  record it as an ADR *in addition to* the session log. The session log
  is "what happened this session"; the ADR is "the durable reason for
  the choice."
- **AIDEV-TODO anchors with deadlines** — for "next steps" items that
  bind to specific code paths, anchor them in code with
  `AIDEV-TODO(by: YYYY-MM-DD):` and reference from the session log.

## What this skill does NOT do

- **Doesn't read the future.** The "next steps" section is what *you*
  think should happen, distilled from the conversation. The model
  doesn't predict.
- **Doesn't replace commit messages, ADRs, or specs.** Each layer
  serves a different purpose:
  - Commit message: per-commit *what*.
  - ADR: per-decision *why* (immutable).
  - Spec: per-feature *plan* (lives through implementation).
  - Session log: per-working-period *narrative* (continuity).
