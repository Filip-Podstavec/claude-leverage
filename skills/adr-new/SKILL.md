---
name: adr-new
description: |
  USE WHEN a load-bearing architectural decision is being made or has just
  been made in the conversation — one that someone is likely to
  re-litigate in six months ("why didn't we use X instead?"). Examples
  that warrant an ADR: choosing a database / framework / integration
  pattern / auth model, OR an explicit rejection of an alternative the
  team will likely revisit, OR a non-obvious tradeoff between
  performance / cost / maintenance / security.

  Bootstraps a new numbered MADR-flavored ADR in `docs/adr/`: picks the
  next sequential number, asks for title + context + decision +
  alternatives + consequences, fills the template, and appends a link
  to `docs/adr/README.md` index. Immutable status once accepted
  (`proposed` → `accepted` → `deprecated` / `superseded by NNNN`).

  Do NOT use for: implementation choices the code itself shows
  (variable naming, function structure); one-off tactical fixes; things
  covered by obvious conventions (lint config, test naming). When in
  doubt, write it — three sentences in `docs/adr/NNNN.md` is cheaper
  than re-arguing the same point in six months.

  Cross-tool (Claude Code and Codex).
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Bash(ls:*)
  - Bash(test:*)
  - Bash(date:*)
argument-hint: "[title] [--status proposed|accepted] [--noninteractive]"
---

# /adr-new

## What it does

Creates a new numbered ADR file in `docs/adr/` and adds an entry to the
index. ADRs are the lightweight memory of *why* the architecture looks
the way it does — without them, six months from now nobody (human or
agent) remembers why we chose A instead of B.

The convention is documented in
[`docs/adr/README.md`](../../docs/adr/README.md): MADR-flavored,
numbered, immutable status (proposed → accepted → deprecated /
superseded).

## Workflow

1. **Find target dir.** Default `docs/adr/` from the current repo root
   (via `git rev-parse --show-toplevel`). If no `docs/adr/` exists,
   ask the user: "create it now?". If yes, also copy
   `templates/adr-template.md` if shipped (the plugin ships its own
   template under `docs/adr/template.md` — useful as a reference even
   when the target repo doesn't have one yet).

2. **Pick next number.** List existing `docs/adr/NNNN-*.md` files,
   parse the leading number, take the max + 1. Pad to 4 digits.

3. **Get the title.**
   - If `$ARGUMENTS` has a positional, use it as the title.
   - If `--noninteractive`, fail if no title was given (we won't
     hallucinate one).
   - Otherwise, prompt the user.
   - Convert to kebab-case for the filename:
     `0042-replace-polling-with-webhooks.md`.

4. **Ask for context** (skip in `--noninteractive`):
   - One-line summary of the problem.
   - The chosen option (one sentence, stated as fact in present
     tense).
   - 1–3 alternatives considered (one line each).
   - Whether to mark `status: proposed` (default) or `accepted` (if
     the team already decided in conversation and just needs the
     record).

5. **Generate the file** at `docs/adr/<NNNN>-<kebab-title>.md` using
   the MADR template (the plugin ships
   [`docs/adr/template.md`](../../docs/adr/template.md) for reference).
   Substitute:
   - `NNNN` → resolved number
   - `Title` → user-provided title
   - `YYYY-MM-DD` → today (`date +%Y-%m-%d`)
   - `Status` → resolved value
   - Context / Decision / Alternatives → user input or
     `<TODO: fill in>` placeholders if user skipped them

6. **Update the index.** Append the new ADR to the bulleted list in
   `docs/adr/README.md` (or create it if it doesn't exist). Preserve
   the existing index style:
   `- [NNNN — Title](NNNN-kebab.md)`

7. **Report.** Print the new file path and remind the user that ADRs
   are immutable once `accepted` — future revisions are *new* ADRs
   superseding the old one, not edits.

## Hard rules

- **Numbers are immutable.** Once shipped, an ADR's number never
  changes. If you regenerate the file (because of typos in the title
  before commit), keep the number.
- **Status is immutable once `accepted`.** Edits to an `accepted` ADR
  should be limited to typos and link fixes. Substantive changes ship
  as a new ADR that explicitly supersedes the old one
  (`Status: superseded by NNNN`).
- **The index is the source of truth for "what ADRs exist."** Always
  update it; never let it drift from the directory contents.
- **Never overwrite an existing ADR.** If the kebab-title collides
  with an existing file, ask the user for a different title.

## Tunables

- `--status accepted` — start the ADR as `accepted` rather than
  `proposed`. Use when the decision is already settled and you're just
  recording it.
- `--noninteractive` — skip prompts; requires a title positional and
  fills the context/decision/alternatives with `<TODO>` placeholders.
- `--dry-run` — print what would be written, write nothing.

## When to write an ADR (and when not to)

**Write an ADR for:**
- Architectural tradeoffs likely to be re-litigated (e.g., "no
  embedding RAG", "AGENTS.md canonical, CLAUDE.md import").
- Decisions that depend on external constraints (a vendor, an open
  issue, a benchmark result).
- Decisions where alternatives are plausible enough that a future
  agent will propose them.

**Don't write an ADR for:**
- Implementation choices the code itself shows (variable names,
  function structure).
- One-off tactical fixes.
- Things covered by an obvious convention (test naming, lint config).

If you're not sure: write it. Three sentences in `docs/adr/0042.md`
is cheap; re-arguing the same point six months later is expensive.

## What this skill does NOT do

- **Doesn't make the decision.** It records a decision you've already
  made. If you don't yet know the decision, you want a `docs/specs/`
  document (or `superpowers:brainstorming`), not an ADR.
- **Doesn't read the conversation context.** You tell it the
  decision in your own words; the skill just structures the file.
- **Doesn't supersede or modify existing ADRs.** Modification is a
  manual edit + new ADR with `Status: superseded by NNNN`.
