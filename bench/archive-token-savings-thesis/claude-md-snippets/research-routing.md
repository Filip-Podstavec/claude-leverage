# Research routing

**Threshold:** Delegate when you would otherwise read 3+ files to synthesize the answer. Inline for 1-2 files.

When you need to understand how something works in the codebase - patterns used, how a flow is structured, how multiple files interact - delegate to the `research-agent` subagent (Sonnet, read-only) instead of reading files directly.

The subagent reads in its own context, returns a structured report, and your main context window stays clean for the actual work.

## When to delegate

- "How does authentication work in this codebase?"
- "What pattern do we use for database transactions?"
- "How is the request lifecycle structured?"
- Before planning a non-trivial change that depends on existing patterns
- Before suggesting a refactor that touches multiple files

## When NOT to delegate

- Trivial single-file lookups (just read it directly)
- Pure location questions ("where is X defined?") - those route to `repo-explorer` if used at all
- Questions about code you've already written in this session - you have that context

## Hard rules

- The subagent is read-only. Don't ask it to "also suggest fixes" - it refuses by design and the request wastes a delegation.
- Pass specific questions, not vague requests. "How does X work?" is good. "Tell me about the codebase" is too broad - the subagent will return surface-level summary that wastes context.
- After receiving the report, present the relevant parts to the user before acting on assumptions.

## Why this matters

Reading files in the main session bloats your context with full file contents - imports, boilerplate, error handling, irrelevant sections. The research subagent reads the same files in isolation, returns a 2-5 sentence answer with file references, and your context stays focused on the work the user actually asked for.

## How to use

Append the rules above to your project's `CLAUDE.md`, or to `~/.claude/CLAUDE.md` for user-level routing across all projects.

This snippet is independent of any specific planning workflow - it applies whenever the main session would otherwise read multiple files to understand the codebase. Pair with `agents/research-agent.md`.
