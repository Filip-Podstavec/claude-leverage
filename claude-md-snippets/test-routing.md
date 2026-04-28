# Test execution routing

When the user asks to run tests, check for regressions, or diagnose test failures:

- ALWAYS delegate to the `test-runner` subagent. Do not run tests directly in this session.
- Present the subagent's report as-is. Do not paraphrase.
- Wait for user direction before applying any fixes.
- Do not auto-rerun tests after fixes - ask first.

## How to use

Append the rules above to your project's `CLAUDE.md` (or `~/.claude/CLAUDE.md` for user-level). Pair with `agents/test-runner.md` and `commands/test.md`.
