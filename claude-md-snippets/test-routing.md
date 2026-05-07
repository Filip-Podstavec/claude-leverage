# Test execution routing

When the user asks to run tests, check for regressions, or diagnose test failures:

- **Delegate** to the `test-runner` subagent for full-suite runs, multi-file changes, or when the test framework needs detection.
- **Run inline** when the scope is a single test file or a single targeted command in a project where the framework is already known. Delegation overhead exceeds savings on tiny scope.
- Present the subagent's report as-is. Do not paraphrase.
- Wait for user direction before applying any fixes.
- Do not auto-rerun tests after fixes - ask first.

## Note on safety

This snippet routes test work to subagents for token efficiency. For security guardrails (preventing dangerous git operations, secret commits), see `hooks/` - these run at the execution layer regardless of which subagent or session is active.

## How to use

Append the rules above to your project's `CLAUDE.md` (or `~/.claude/CLAUDE.md` for user-level). Pair with `agents/test-runner.md` and `commands/test.md`.
