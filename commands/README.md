# Commands

Slash commands are `.md` files that define reusable prompts invoked with `/<command-name>` in Claude Code.

## Install

```bash
# User scope (available in all projects)
mkdir -p ~/.claude/commands
cp <command-file>.md ~/.claude/commands/

# Project scope (committed to repo)
mkdir -p .claude/commands
cp <command-file>.md .claude/commands/
```

After installing, the command is available as `/<filename>` in any session. Run `/commands` to reload without restarting.

## Available commands

- [`commit-smart.md`](commit-smart.md) - Smart commit routing: trivial changes committed directly, non-trivial delegated to a git-committer subagent to save Opus context.
- [`code-review.md`](code-review.md) - Delegates review to the `code-reviewer` subagent and orchestrates user-confirmed fixes in the main session. Requires `code-reviewer` agent to be installed.
