---
description: Delegate code review to the code-reviewer subagent (Sonnet, read-only) and apply approved fixes in the main session
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git log:*)
argument-hint: "[optional file paths to review]"
---

## Context

Status: !`git status --short`
Staged shortstat: !`git diff --cached --shortstat`
Unstaged shortstat: !`git diff --shortstat`
Recent commits: !`git log --oneline -5`

## Your role

You are orchestrating a two-phase code review:

- Phase 1: a Sonnet-based subagent reviews the code and returns structured findings.
- Phase 2: you (the main session) apply approved fixes.

You do NOT review the code yourself. The subagent does that. Your job is to delegate, summarize, get user direction, and then make changes.

## Workflow

1. **Determine review scope:**
   - If `$ARGUMENTS` contains file paths, review those.
   - Otherwise, if there are staged changes, review the staged diff.
   - Otherwise, if there are unstaged changes, review those.
   - If nothing is changed, ask the user what they want reviewed.

2. **Invoke the `code-reviewer` subagent** with a clear scope. Pass the relevant context (file paths or "the staged changes"). Wait for its structured report.

3. **Present findings to the user.** Keep your summary concise. Use the subagent's priority sections (Critical / Important / Nice to have). Do not editorialize - the subagent already prioritized.

4. **Ask for direction.** Offer these options:
   - Apply all critical and important findings
   - Apply specific findings (user picks which)
   - Skip fixes, the user will handle it

   Wait for explicit confirmation. Never apply fixes preemptively.

5. **Apply approved fixes** using your full toolset (Edit, Write, Bash). The subagent has no write tools and is not involved in this phase.

## Hard rules

- Do not review the code yourself in the main session. Always delegate to the subagent.
- Do not ask the subagent to "also apply the fixes" - it is read-only by design and refusing is its core contract.
- If the subagent's findings are ambiguous, ask the user clarifying questions before editing.
- Do not run a fresh review after applying fixes unless the user requests it.
