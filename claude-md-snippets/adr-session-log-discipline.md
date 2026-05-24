# ADR + session-log discipline

Drop-in CLAUDE.md / AGENTS.md snippet that codifies the durable-memory
convention into a project so the agent working there remembers to
invoke `/adr-new` and `/session-log` at the right moments.

`/init-repo` offers this snippet for projects expected to be touched by
multiple agents over many months.

## Why install this

The two skills (`/adr-new`, `/session-log`) ship in claude-leverage with
trigger-aware descriptions, so Claude Code's skill resolver will surface
them when a conversation matches. **But the agent still has to recognize
the moment** — neither skill is fired by a hook (see ADR 0004 in the
plugin repo for the reasoning).

Dropping this snippet into a project's `AGENTS.md` puts the discipline
in front of the agent at session start, increasing the odds it gets
invoked at the appropriate point.

## Snippet

Append the block between the markers below into your project's
`AGENTS.md` (preferred — both Claude Code and Codex see it) or
`CLAUDE.md`. Markers are load-bearing; preserve byte-identically.

```markdown
<!-- claude-leverage:adr-session-log-discipline START -->

## Durable memory: ADRs and session logs

This project uses claude-leverage's ADR + session-log conventions to
preserve *why* and *continuity* across AI sessions. Two skills, both
user/agent-invoked:

- **`/adr-new`** — when a load-bearing architectural decision is being
  made or has just been made in conversation (one likely to be
  re-litigated in 6 months without the rationale), invoke this to
  record it as a numbered MADR-flavored ADR in `docs/adr/`. Examples:
  choosing a database / framework / integration pattern / auth model;
  OR explicit rejection of an alternative the team will revisit.

- **`/session-log`** — at the end of a substantial working session
  (commits shipped, multiple decisions made, open questions surfaced),
  invoke this to write a distilled journal entry to
  `docs/sessions/YYYY-MM-DD-<topic>.md`. Distillate (~80 lines max),
  NOT transcript. The next agent reads it to pick up the thread.

**Neither auto-fires.** The agent working in this project is expected
to recognize the moment and invoke. The trigger-aware descriptions in
each skill's frontmatter help Claude Code's resolver surface them at
the right time, but the agent's judgment is the actual gate.

### Reading order for new agents

When opening this repo for the first time, read in this order
(progressive disclosure):

1. This `AGENTS.md`
2. `docs/adr/README.md` — skim index, read ADRs relevant to your task
3. `docs/sessions/` — last 1–3 session logs (where the previous
   session left off — often the highest-leverage orientation per token)
4. Specific `docs/specs/` only when starting on that topic
5. The code itself — by following imports from the relevant entrypoint

<!-- claude-leverage:adr-session-log-discipline END -->
```

## When to install

- Any client project expected to be touched by multiple agents over
  multiple months.
- Any project where decisions accumulate (architecture, tooling
  choices, vendor selections) and a future maintainer will need to
  understand why.
- Any handoff scenario (new contractor, ownership change).

## When NOT to install

- Throwaway scripts / spikes / one-off experiments — the discipline
  costs more than the continuity is worth.
- Repos with strict no-doc policies imposed by team conventions
  (rare, but exists).
- Projects already using a different decision-record system (RFCs,
  Notion pages, etc.) — pick one; don't ship both.
