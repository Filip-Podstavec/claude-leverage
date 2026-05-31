# Session logs

**Continuity over time.** When you finish a working session with an AI agent,
write a short, distilled session log here. The next session — yours or
another agent's — reads it to pick up the thread.

This is **not a transcript**. Raw chat is noise the agent can't usefully
consume. A session log is the *distillate*: what was solved, what was
decided, what's still open, what should happen next.

## Convention

- One file per session: `YYYY-MM-DD-<topic-kebab-case>.md`.
- Multiple sessions per day are allowed: `YYYY-MM-DD-<topic>-2.md` etc.
- Use the template in [`template.md`](template.md), or invoke the
  `/session-log` skill at the end of a session — it asks for the topic,
  reads the conversation context, and writes the file for you.
- **Distillate, not transcript.** If it's longer than ~80 lines, it's
  probably too long.
- Link to relevant ADRs (`docs/adr/`), specs (`docs/specs/`), and
  commits. The session log is the *connective tissue* — pointers, not
  encyclopedias.
- **Confidential by exclusion.** These files are committed and pushed —
  sometimes to a public repo. Keep secrets, credentials, client names,
  internal business reasoning, and security details *out*. The
  `block-secrets-precommit` hook stops key-shaped secrets at commit time,
  but it can't catch confidential prose — distill the sensitive specific
  out and keep the decision. Gitignore this directory only as a last
  resort in a fully public repo (you lose cross-agent continuity if you do).

## Index

See files in this directory directly — they're naturally chronologically
sorted by filename. Use `ls docs/sessions/ | tail -20` to see recent
ones.

For ongoing-work continuity, the convention is: read the last 2–3
session logs at the start of a new session if the project is in flight.
For a one-off bug fix on a stable codebase, skip.

## Reading order for new agents

If you're an agent opening this repo for the first time:

1. Top-level `AGENTS.md` (canonical guidance).
2. `docs/adr/README.md` (why the architecture looks the way it does).
3. **`docs/sessions/` last 2–3 logs** (where the human + previous agents
   left off — often the most valuable orientation).
4. Specific `docs/specs/` files only when relevant to the current task.

The session log layer is what makes the difference between "the agent
re-discovers context cold every session" and "the agent picks up where
the last one left off."
