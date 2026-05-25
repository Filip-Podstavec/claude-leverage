# Commands

Claude Code slash commands shipped by `claude-leverage`. Each command is a
`.md` file invoked with `/<name>` in any Claude Code session.

This `commands-docs/` directory exists as a sibling of `commands/` (not inside
it) because Claude Code's plugin loader registers every `*.md` under
`commands/` as a slash command — a `README.md` inside `commands/` would
become a phantom `/README` command. Same pattern as `agents-docs/`.

In v1.0.0 the **primary user-facing surface is `skills/`**, not this
directory. Slash commands are reserved for Claude-Code-only workflows that
need the `Bash(... :*)` preamble or `argument-hint` features that the
cross-tool SKILL.md spec does not currently expose.

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

- [`flaky-test.md`](../commands/flaky-test.md) — Delegates to the
  `flaky-test-isolator` subagent with target, run count, and timeout.
  Validates inputs and applies caps before delegation.

> **v1.4.4 removed `commit-smart.md`.** It auto-pushed by default, which
> violates the "actions visible to others should require confirmation"
> principle the rest of the stack follows. Vanilla Claude Code commit
> + the `block-secrets-precommit` / `block-dangerous-git` hooks already
> cover everything `/commit-smart` did, without the treacherous auto-push.

Anything else (security review, repo map, process diagrams, stack check,
init-repo, log-structured, explain-diff, codex-sandbox) lives in
[`../skills/`](../skills/) as cross-tool skills.
