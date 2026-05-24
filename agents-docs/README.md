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

Haiku 4.5 has a separate rate pool on Max plans and is significantly faster for pure plumbing tasks (no reasoning, no writing). The `git-committer-quick` agent demonstrates when this trade-off makes sense - for trivial commits where the message can be derived directly from the diff. For commits requiring real understanding of why the code changed, Sonnet remains the right tier.

## Available agents (default install)

- [`git-committer.md`](git-committer.md) - Stage, commit, push for non-trivial commits (Sonnet). Reads diff, writes Conventional Commits message matching repo style. Does not modify code.
- [`git-committer-quick.md`](git-committer-quick.md) - Speed-optimized variant for trivial commits (Haiku, small inline-friendly diffs). When installed, `/commit-smart` defaults to this for qualifying scope.
- [`code-reviewer.md`](code-reviewer.md) - Read-only code reviewer (Sonnet). Returns structured findings; never modifies code.
- [`test-runner.md`](test-runner.md) - Detects framework, runs tests, returns structured failure analysis (Sonnet, read-only). Never modifies code or test files.
- [`context-gatherer.md`](context-gatherer.md) - Pre-fetches implementation context before coding (Haiku, read-only). Given a task, gathers key files, patterns, dependencies, and constraints into a structured package so the main session does not have to explore itself.

## Extras (opt-in, not in default install)

Four agents live in [`../extras/agents/`](../extras/agents/) because they either duplicate Claude Code built-ins or are too low-frequency to justify their loading tax on every session. See [`extras/README.md`](../extras/README.md) for opt-in install.

- `flaky-test-isolator` (Sonnet) - flaky-test diagnostics; low frequency in real use
- `docs-updater` (Sonnet) - README/CHANGELOG freshness; low frequency
- `repo-explorer` (Haiku) - covered by Claude Code built-in `Explore`
- `research-agent` (Sonnet) - covered by Claude Code built-in `general-purpose`
