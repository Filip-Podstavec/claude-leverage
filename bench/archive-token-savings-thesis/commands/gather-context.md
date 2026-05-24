---
description: Gather implementation context before starting a task. Delegates to context-gatherer subagent (Sonnet) to pre-fetch everything Opus needs.
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git branch:*)
argument-hint: "<description of what you're about to implement or fix>"
---

## Context

Branch: !`git branch --show-current`
Status: !`git status --short`
Recent changes: !`git diff --stat HEAD~1 2>/dev/null || echo "no previous commit"`

## Your role

You are orchestrating a context-gathering phase:

- Phase 1: a Sonnet-based subagent explores the codebase and returns a structured context package.
- Phase 2: you (the main session) use that context to implement the task.

You do NOT explore the codebase yourself. The subagent does that. Your job is to delegate with a clear task description, receive the context package, and then use it to guide your implementation.

## Workflow

1. **Determine task scope:**
   - If `$ARGUMENTS` contains a task description, use it directly.
   - If `$ARGUMENTS` is empty, ask the user what they're about to implement.

2. **Invoke the `context-gatherer` subagent** with the task description. Pass it verbatim — do not rephrase or reduce scope.

3. **Present the context package to the user.** Keep it as-is — the subagent's structured output is already optimized for consumption.

4. **Use the context for implementation:**
   - If the context package includes "Suggested starting points" — read those ranges to begin, and expand to other files if you judge them relevant. Treat the list as a starting set, not the closed set.
   - If the subagent indicates this is greenfield (no existing code matches), proceed directly to implementation using the nearest relevant patterns listed in the package.

## Hard rules

- Do not explore the codebase yourself before delegating. That defeats the purpose — the subagent handles exploration.
- Do not ask the subagent to "also write the code" — it is read-only by design.
- If the subagent returns "Task too broad", ask the user to narrow the scope. Do not attempt to gather context yourself.
- If the context package is insufficient for implementation, you may do targeted follow-up reads (specific files the subagent pointed to), but do not re-explore from scratch.
