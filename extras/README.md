# extras/ — opt-in components

These components are **not loaded by the default plugin install.** They live here so they can be installed manually by users who want them, without imposing their cost on everyone.

## Why these are extras

Benchmark data ([`bench/`](../bench/)) showed that each agent in the plugin's system prompt costs ~$0.01 of Opus `cache_creation` per session, paid whether you use it or not. The four agents and two commands here are either:

- **Low-frequency in real use** (`docs-updater`, `flaky-test-isolator`) — most sessions don't need them, but the loading tax is paid every time
- **Structurally duplicative** with Claude Code's built-in `Explore` and `general-purpose` agents (`repo-explorer`, `research-agent`) — built-ins are loaded for free, our copies pay tax

By moving them out of the default install, every leveraged session pays ~$0.04 less in cache_creation tax. Users who *do* need them can opt in.

## What's here

| Component | Use case | Why it's an extra |
|---|---|---|
| `agents/repo-explorer.md` | "Where is X defined?" — file/symbol location lookups | Claude Code built-in `Explore` (Haiku) covers this for free |
| `agents/research-agent.md` | "How does X work?" — cross-file pattern synthesis | Claude Code built-in `general-purpose` covers this |
| `agents/docs-updater.md` | Check README/CHANGELOG freshness after a diff | Low frequency; paired with `commands/docs-sync.md` |
| `agents/flaky-test-isolator.md` | Run a test N times, group failures by signature | Rare use case; paired with `commands/flaky-test.md` |
| `commands/docs-sync.md` | `/docs-sync` — orchestrates `docs-updater` | Requires the agent above |
| `commands/flaky-test.md` | `/flaky-test` — orchestrates `flaky-test-isolator` | Requires the agent above |
| `claude-md-snippets/docs-sync-routing.md` | Optional auto-routing reminder for docs-sync | Requires the command above |
| `claude-md-snippets/research-routing.md` | Routes "how does X work" to research-agent | Requires the agent above |

## How to opt in

After installing the main plugin, copy the extras you want into the same scope (user or project):

```bash
# User scope (~/.claude/)
cp extras/agents/*.md ~/.claude/agents/
cp extras/commands/*.md ~/.claude/commands/

# Or just the ones you want
cp extras/agents/docs-updater.md ~/.claude/agents/
cp extras/commands/docs-sync.md ~/.claude/commands/

# Project scope (.claude/)
cp extras/agents/*.md .claude/agents/
cp extras/commands/*.md .claude/commands/
```

Run `/agents` or `/commands` to verify the new entries appear.

## How to opt out (after opting in)

Remove the file. Run `/agents` or `/commands` to confirm it's gone.

```bash
rm ~/.claude/agents/docs-updater.md ~/.claude/commands/docs-sync.md
```

## Why not just delete them entirely?

The agents themselves work — benchmark data confirms intrinsic efficiency. The problem is the load-tax economics for users who never invoke them. Keeping them here means:

- Anyone who needs them can opt in without forking the repo
- They get the same maintenance as core agents (frontmatter validation, version bumps, etc.)
- If `repo-explorer` or `research-agent` start offering value the built-ins don't, we can promote them back to default

Frontmatter and structural validation still applies via `tests/test_agent_command_frontmatter.py` (which scans both `agents/` and `extras/agents/`).
