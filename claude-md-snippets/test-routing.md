# Test execution routing

When the user asks to run tests, check for regressions, or diagnose test failures:

- ALWAYS delegate to the `test-runner` subagent. Do not run tests directly in this session.
- Present the subagent's report as-is. Do not paraphrase.
- Wait for user direction before applying any fixes.
- Do not auto-rerun tests after fixes - ask first.

## Note on safety

This snippet routes test work to subagents for token efficiency. For security guardrails (preventing dangerous git operations, secret commits), see `hooks/` - these run at the execution layer regardless of which subagent or session is active.

## How to use

Append the rules above to your project's `CLAUDE.md` (or `~/.claude/CLAUDE.md` for user-level). Pair with `agents/test-runner.md` and `commands/test.md`.
