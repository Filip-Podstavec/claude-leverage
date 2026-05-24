# Commands

Claude Code slash commands shipped by `claude-leverage`. Each command is a
`.md` file invoked with `/<name>` in any Claude Code session.

This `commands-docs/` directory exists as a sibling of `commands/` (not inside
it) because Claude Code's plugin loader registers every `*.md` under
`commands/` as a slash command — a `README.md` inside `commands/` would
become a phantom `/README` command. Same pattern as `agents-docs/`.

## Install

The plugin install registers these automatically. For manual / standalone:

```bash
# User scope (available in all projects)
mkdir -p ~/.claude/commands
cp commands/*.md ~/.claude/commands/

# Project scope
mkdir -p .claude/commands
cp commands/*.md .claude/commands/
```

After install, the command is available as `/<filename>`. Run `/commands` to
reload without restarting.

## Available commands

- [`commit-smart.md`](../commands/commit-smart.md) — Inline secret scan +
  Conventional Commits message + push, all in the main session. No subagent
  dispatch (the v0.x benchmark verdict on inline-vs-delegate for commits).
- [`flaky-test.md`](../commands/flaky-test.md) — Delegates to the
  `flaky-test-isolator` subagent with target, run count, and timeout.
  Validates inputs and applies caps before delegation.
- [`install-snippets.md`](../commands/install-snippets.md) — Interactive
  installer for any CLAUDE.md routing snippets in `claude-md-snippets/`.
  Idempotent — detects drift, offers update-in-place. (Default install ships
  no snippets in v1.0.0.)
- [`leverage-stats.md`](../commands/leverage-stats.md) — Read-only viewer
  over `~/.claude/claude-leverage-stats.jsonl` (written by the
  `track-delegations` hook). Shows lifetime totals, tier breakdown, last-7d
  activity. Useful to see whether subagents are actually getting invoked.

## Coming in later phases (per docs/specs/2026-05-24-pivot/)

- `/security-review` — paired with `agents/security-reviewer.md`.
- `/repo-map`, `/process-diagram` — mermaid generators.
- `/stack-check` — 30-day stack-freshness check.
- The above will land as skills (cross-tool portable via `agentskills.io`
  SKILL.md spec) under `skills/`, not as additional `.md` files here.
