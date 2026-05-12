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

- [`commit-smart.md`](commit-smart.md) - Three-tier commit routing: ultra-trivial → Haiku `git-committer-quick`, trivial → main session inline, non-trivial → Sonnet `git-committer` subagent. Falls through gracefully if cheaper tiers not installed.
- [`code-review.md`](code-review.md) - Scope-conditional review delegation. Non-trivial scope (3+ files OR 50+ lines) → `code-reviewer` subagent (Sonnet); trivial scope → inline review. Optionally passes session decisions to subagent so review does not re-litigate settled choices. Requires `code-reviewer` agent.
- [`test.md`](test.md) - Delegates test execution to the `test-runner` subagent and orchestrates user-confirmed fixes in the main session. Requires `test-runner` agent.
- [`flaky-test.md`](flaky-test.md) - Diagnoses a flaky test by delegating to the `flaky-test-isolator` subagent (Sonnet). Args: `<test-target> [--runs N=10] [--timeout SECONDS=60]`. Pre-flight validates the target and caps N at 50 / per-run timeout at 300s before delegating. Requires `flaky-test-isolator` agent.
- [`gather-context.md`](gather-context.md) - Pre-fetches implementation context via the `context-gatherer` subagent (Sonnet) before non-trivial implementation. Returns structured package; main session uses it to begin coding without exploring itself. Requires `context-gatherer` agent.
- [`docs-sync.md`](docs-sync.md) - Delegates documentation freshness check to the `docs-updater` subagent (Sonnet). Returns confidence-labeled prose-direction suggestions; main session applies approved edits fresh from live state. Requires `docs-updater` agent.
- [`install-snippets.md`](install-snippets.md) - Interactive installer for the CLAUDE.md routing snippets in `claude-md-snippets/`. Closes the gap that Claude Code plugins do not auto-install CLAUDE.md content. Appends selected snippets to user-level or project CLAUDE.md with marker comments for duplicate detection.
- [`leverage-stats.md`](leverage-stats.md) - Reads the `track-delegations` log at `~/.claude/claude-leverage-stats.jsonl` and prints lifetime totals, breakdown by tier (Sonnet/Haiku/other) and subagent, plus last-7-days activity. Read-only observability — answers "did the routing actually save anything?".
