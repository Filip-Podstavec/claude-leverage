# Agents

Subagents are specialized agents spawned by your main Claude Code session. Each runs with its own context window, a restricted set of tools, and an explicitly declared model. The main session delegates work to them and receives a structured result back.

## Install

```bash
# User scope (available in all projects)
mkdir -p ~/.claude/agents
cp <agent-file>.md ~/.claude/agents/

# Project scope (committed to repo)
mkdir -p .claude/agents
cp <agent-file>.md .claude/agents/
```

After installing, run `/agents` in a running session to pick up changes without restarting.

## Model strategy

The main session typically runs Opus for orchestration and architecture decisions. Subagents run Sonnet for execution work - code review, implementation, refactoring. Haiku handles cheap exploratory reads and searches. Each subagent declares `model:` explicitly in its frontmatter to avoid inheritance surprises.

## Available agents

- [`code-reviewer.md`](code-reviewer.md) - Read-only code review that produces a structured findings report. Sonnet.
