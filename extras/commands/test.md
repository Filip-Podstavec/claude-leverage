---
description: Delegate test execution to the test-runner subagent (Sonnet) and apply approved fixes in the main session
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(ls:*), Read
argument-hint: "[optional test path or pattern]"
---

## Context

Status: !`git status --short`
Recently changed files: !`git diff --name-only HEAD~1 2>/dev/null || git diff --name-only`

## Your role

You are orchestrating a two-phase test workflow:

- Phase 1: a Sonnet-based subagent runs the tests and returns a structured report.
- Phase 2: you (the main session) apply approved fixes for any failures.

You do NOT run tests yourself. The subagent does that. Your job is to delegate, summarize, get user direction, and then make changes.

## Workflow

1. **Determine test scope:**
   - If `$ARGUMENTS` contains paths or patterns, pass those to the subagent.
   - Otherwise let the subagent decide based on recent changes (its default behavior).

2. **Invoke the `test-runner` subagent** with the scope. Wait for its structured report.

3. **If all tests passed:** relay that to the user briefly and stop. Do not propose unsolicited improvements.

4. **If tests failed:** present the report's Summary and Failures sections to the user. Keep it concise - do not paraphrase the subagent's analysis, just relay it. If the subagent identified shared root causes (Patterns section), highlight that.

5. **Ask for direction.** Offer these options:
   - Apply suggested fixes for all failures
   - Apply fixes for specific failures (user picks)
   - Skip fixes, the user will investigate
   - Re-run a specific subset of tests (delegates back to the subagent)

   Wait for explicit confirmation. Never apply fixes preemptively.

6. **Apply approved fixes** using your full toolset (Edit, Write, Bash). Use the subagent's "Suggested direction" as a starting point, not a prescription - you have the full reasoning context.

7. **After fixes are applied,** ask the user whether to re-run the affected tests. Do not auto-rerun.

## Hard rules

- Do not run tests yourself in the main session. Always delegate to the subagent.
- Do not ask the subagent to "also fix the failures" - it is read-only by design and refusing is its core contract.
- Do not disable or skip failing tests as a workaround unless the user explicitly requests it.
- If the subagent reports a setup/configuration issue (missing deps, broken config), do not try to "work around" by guessing test commands. Address the setup issue first.
