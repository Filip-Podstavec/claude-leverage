# Code review routing

When the user asks for a code review, audit, security check, or feedback on changes:

- ALWAYS delegate to the `code-reviewer` subagent. Do not review directly in this session.
- The subagent runs on Sonnet with read-only tools (Read, Grep, Glob). It returns structured findings organized by priority.
- After the subagent reports back, present findings to the user and wait for direction before making any changes.
- Apply approved fixes in this session using your full toolset. The subagent never modifies code.
- If the user requests a re-review after fixes, invoke the subagent again with the new scope.

This separation keeps review context isolated from the main session and routes write operations through the model with the most reasoning capacity.

## How to use

Append the rules above to your project's `CLAUDE.md` (or `~/.claude/CLAUDE.md` for user-level). Claude Code reads `CLAUDE.md` at the start of every session.
