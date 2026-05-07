# Code review routing

When the user asks for a code review, audit, security check, or feedback on changes:

- **Delegate** to the `code-reviewer` subagent when scope is non-trivial: 3+ files OR over 50 changed lines OR cross-file pattern checks needed.
- **Review inline** (no delegation) when scope is trivial: 1-2 files under 50 lines combined. Delegation overhead exceeds savings on small reviews.
- When delegating, also pass any non-obvious decisions made earlier in the session ("we considered X but went with Y because Z") so the subagent does not waste output re-litigating already-rejected alternatives.
- Present findings to the user and wait for direction before making any changes.
- Apply approved fixes in this session. The subagent never modifies code.

## Note on safety

This snippet routes review work to subagents for token efficiency. For security guardrails (preventing dangerous git operations, secret commits), see `hooks/` - these run at the execution layer regardless of which subagent or session is active.

## How to use

Append the rules above to your project's `CLAUDE.md` (or `~/.claude/CLAUDE.md` for user-level). Claude Code reads `CLAUDE.md` at the start of every session.
