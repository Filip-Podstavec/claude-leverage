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

## Available agents

- [`git-committer.md`](git-committer.md) - Stage, commit, push for non-trivial commits (Sonnet). Reads diff, writes Conventional Commits message matching repo style. Does not modify code.
- [`git-committer-quick.md`](git-committer-quick.md) - Speed-optimized variant for ultra-trivial commits (Haiku, single file, <20 lines). When installed, `/commit-smart` defaults to this for qualifying scope.
- [`code-reviewer.md`](code-reviewer.md) - Read-only code reviewer (Sonnet). Returns structured findings; never modifies code.
- [`test-runner.md`](test-runner.md) - Detects framework, runs tests, returns structured failure analysis (Sonnet, read-only). Never modifies code or test files.
- [`flaky-test-isolator.md`](flaky-test-isolator.md) - Diagnoses flaky tests by running a single target N times sequentially, grouping failures by normalized signature, and returning a stability report (Sonnet, read-only). Hard caps: N≤50, 60s per-run timeout, 30 min wall budget. Distinct from `test-runner` (one-shot diagnosis) — use this for statistical signal across runs.
- [`repo-explorer.md`](repo-explorer.md) - Read-only codebase exploration (Haiku). Finds where things are defined, identifies patterns. Never modifies code.
- [`research-agent.md`](research-agent.md) - Read-only research synthesis (Sonnet). Answers "how does X work" questions by reading multiple files and returning a structured report. Distinct from `repo-explorer` (which handles "where" lookups on Haiku).
- [`context-gatherer.md`](context-gatherer.md) - Pre-fetches implementation context before coding (Sonnet, read-only). Given a task, gathers key files, patterns, dependencies, and constraints into a structured package so the main session does not have to explore itself.
- [`docs-updater.md`](docs-updater.md) - Documentation freshness specialist (Sonnet, read-only). Reads code diff and existing docs (README, CHANGELOG, docstrings on changed funcs), returns confidence-labeled prose-direction suggestions. Main session applies edits fresh from live state.
