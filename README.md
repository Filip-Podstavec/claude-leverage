# claude-leverage

Curated subagents, slash commands, and workflow patterns for Claude Code.

## Why

Claude Code is not a single model - it is an orchestration layer. The most capable model does not need to handle every task. A code review can run on Sonnet while Opus plans architecture. A file search can use Haiku while Sonnet writes implementation. This repo is a collection of building blocks for people who build real things with AI agents as their primary execution layer.

## What's inside

- [`agents/`](agents/) - Specialized subagents with scoped tools and explicit model selection
- [`commands/`](commands/) - Slash commands (`.md` files) for common workflows
- [`skills/`](skills/) - Reusable skills for Claude Code
- [`hooks/`](hooks/) - Shell hooks triggered by Claude Code events
- [`claude-md-snippets/`](claude-md-snippets/) - Copy-paste fragments for your `CLAUDE.md` files
- [`workflows/`](workflows/) - Longer guides on combining primitives into end-to-end patterns

## Install

User scope (available in all projects):

```bash
cp agents/code-reviewer.md ~/.claude/agents/
cp commands/commit-smart.md ~/.claude/commands/
```

Project scope (committed to your repo):

```bash
cp agents/code-reviewer.md .claude/agents/
cp commands/commit-smart.md .claude/commands/
```

After copying, run `/agents` or `/commands` in a running Claude Code session to pick up changes without restarting.

## License

[MIT](LICENSE)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
