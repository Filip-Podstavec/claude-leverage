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

## Available commands (default install)

- [`commit-smart.md`](commit-smart.md) - Three-tier commit routing: ultra-trivial → Haiku `git-committer-quick`, trivial → main session inline, non-trivial → Sonnet `git-committer` subagent. Falls through gracefully if cheaper tiers not installed.
- [`code-review.md`](code-review.md) - Scope-conditional review delegation. Non-trivial scope (3+ files OR 50+ lines) → `code-reviewer` subagent (Sonnet); trivial scope → inline review. Optionally passes session decisions to subagent so review does not re-litigate settled choices. Requires `code-reviewer` agent.
- [`test.md`](test.md) - Delegates test execution to the `test-runner` subagent and orchestrates user-confirmed fixes in the main session. Requires `test-runner` agent.
- [`gather-context.md`](gather-context.md) - Pre-fetches implementation context via the `context-gatherer` subagent (Haiku) before non-trivial implementation. Returns structured package; main session uses it to begin coding without exploring itself. Requires `context-gatherer` agent.
- [`install-snippets.md`](install-snippets.md) - Interactive installer for the CLAUDE.md routing snippets in `claude-md-snippets/`. Closes the gap that Claude Code plugins do not auto-install CLAUDE.md content. Appends selected snippets to user-level or project CLAUDE.md with marker comments for duplicate detection.
- [`leverage-stats.md`](leverage-stats.md) - Reads the `track-delegations` log at `~/.claude/claude-leverage-stats.jsonl` and prints lifetime totals, breakdown by tier (Sonnet/Haiku/other) and subagent, plus last-7-days activity. Read-only observability — answers "did the routing actually save anything?".

## Extras (opt-in) — see [`../extras/`](../extras/README.md)

- `/flaky-test` (`extras/commands/flaky-test.md`) - requires `flaky-test-isolator` extra
- `/docs-sync` (`extras/commands/docs-sync.md`) - requires `docs-updater` extra
