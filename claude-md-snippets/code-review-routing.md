# Code review routing

When the user asks for a code review, audit, security check, or feedback on changes:

- ALWAYS delegate to the `code-reviewer` subagent. Do not review directly in this session.
- Present findings to the user and wait for direction before making any changes.
- Apply approved fixes in this session. The subagent never modifies code.

## Note on safety

This snippet routes review work to subagents for token efficiency. For security guardrails (preventing dangerous git operations, secret commits), see `hooks/` - these run at the execution layer regardless of which subagent or session is active.

## How to use

Append the rules above to your project's `CLAUDE.md` (or `~/.claude/CLAUDE.md` for user-level). Claude Code reads `CLAUDE.md` at the start of every session.
