# CLAUDE.md / AGENTS.md Snippets

Optional fragments meant to be appended to a project's `AGENTS.md` (or
`CLAUDE.md`, or `~/.claude/CLAUDE.md`) to add routing rules or behavioral
guidance that pair with specific skills or subagents from this stack.

## What's here

**v1.0.0 ships no snippets in the default install.** The five v0.x snippets
that paired with the retired token-savings era agents are frozen in
[`../bench/archive-token-savings-thesis/claude-md-snippets/`](../bench/archive-token-savings-thesis/claude-md-snippets/).

New snippets land here per skill as the need arises (e.g. "auto-route
security review when touching auth paths"). When they do, the
[`/init-repo`](../skills/init-repo/SKILL.md) skill picks them up
automatically — its interactive flow lets the user opt-in per snippet
per project.

## Why snippets aren't auto-installed by the plugin

Claude Code plugins install agents, commands, hooks, and skills — but
**not** CLAUDE.md content. (There's no platform hook to auto-append
guidance to the user's `CLAUDE.md`.) `/init-repo` is the workaround at
project scope; for `~/.claude/CLAUDE.md` you copy manually.

For Codex, the equivalent is `scripts/install-codex.sh` — it appends an
`@<repo>/AGENTS.md` reference to `~/.codex/AGENTS.md`. Per-snippet
install would be added later if Codex ends up needing it.
