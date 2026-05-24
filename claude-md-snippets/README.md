# CLAUDE.md / AGENTS.md Snippets

Optional fragments meant to be appended to a project's `AGENTS.md` (or
`CLAUDE.md`, or `~/.claude/CLAUDE.md`) to add routing rules or behavioral
guidance that pair with specific skills or subagents from this stack.

## What's here

**v1.0.0 ships no snippets in the default install.** The five v0.x snippets
that paired with the retired token-savings era agents are frozen in
[`../bench/archive-token-savings-thesis/claude-md-snippets/`](../bench/archive-token-savings-thesis/claude-md-snippets/).

New snippets land here per phase as the v1.0.0 plan rolls out (see
`docs/specs/2026-05-24-pivot/06-roadmap.md`). When they do, the
`/install-snippets` slash command picks them up automatically.

## Install

Use the `/install-snippets` slash command for idempotent installs with
update-in-place when a snippet drifts. See
[`../commands/install-snippets.md`](../commands/install-snippets.md).

Manual install: copy the block between the `<!-- claude-leverage:<name> START -->`
and `<!-- claude-leverage:<name> END -->` markers into your target file.

## Why snippets aren't auto-installed by the plugin

Claude Code plugins install agents, commands, hooks, and skills — but
**not** CLAUDE.md content. (Open feature request: there's no platform hook
to auto-append guidance to the user's `CLAUDE.md`.) `/install-snippets` is
the workaround.

For Codex, the equivalent is `scripts/install-codex.sh` — it appends an
`@<repo>/AGENTS.md` reference to `~/.codex/AGENTS.md`. Per-snippet install
would be added later if Codex ends up needing it.
