# claude-leverage

Curated subagents, slash commands, hooks, and workflow patterns for Claude Code.

## Why

Claude Code is not a single model - it is an orchestration layer. The most capable model does not need to handle every task. A code review can run on Sonnet while Opus plans architecture. A trivial commit can use Haiku while Sonnet handles complex changes. This repo is a collection of building blocks for people who build real things with AI agents as their primary execution layer.

Security guardrails belong in hooks, not subagent prompts. A prompt rule applies only when that prompt is active - a hook applies to every tool call from every session. Workflow guidance (how to do things well) belongs in subagent prompts and slash commands. This separation is intentional.

## What's inside

- [`hooks/`](hooks/) - Deterministic shell scripts that run before tool calls. The primary layer for security guardrails - they work regardless of which subagent or session is active.
- [`agents/`](agents/) - Specialized subagents with isolated context and explicit model selection. Sonnet for execution work, Haiku for pure plumbing.
- [`commands/`](commands/) - Slash commands that orchestrate workflows. Bash preambles compute context deterministically before the LLM sees the prompt.
- [`claude-md-snippets/`](claude-md-snippets/) - Drop-in rules for your project's CLAUDE.md to route work between models.
- [`skills/`](skills/) - Reusable skills for Claude Code.
- [`workflows/`](workflows/) - Longer patterns and how-to material.

## Install

User scope (available in all projects):

```bash
# Hooks (primary safety layer)
mkdir -p ~/.claude/hooks
cp hooks/*.sh ~/.claude/hooks/
chmod +x ~/.claude/hooks/*.sh
# Then register in ~/.claude/settings.json - see hooks/README.md

# Agents and commands
cp agents/git-committer.md ~/.claude/agents/
cp agents/code-reviewer.md ~/.claude/agents/
cp agents/test-runner.md ~/.claude/agents/
cp commands/commit-smart.md ~/.claude/commands/
cp commands/code-review.md ~/.claude/commands/
cp commands/test.md ~/.claude/commands/
```

Project scope (committed to your repo):

```bash
cp agents/code-reviewer.md .claude/agents/
cp agents/test-runner.md .claude/agents/
cp commands/commit-smart.md .claude/commands/
cp commands/code-review.md .claude/commands/
cp commands/test.md .claude/commands/
```

After copying, run `/agents` or `/commands` in a running Claude Code session to pick up changes without restarting.

## License

[MIT](LICENSE)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
