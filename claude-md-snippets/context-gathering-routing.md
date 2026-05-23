# Context gathering routing

**Threshold:** Delegate when the task will likely touch 3+ files OR when you don't yet know which files are involved. Inline for single-file changes where you already know the target.

When about to implement a feature or fix a bug that will likely touch 3+ files, delegate context gathering to the `context-gatherer` subagent (Haiku, read-only) instead of exploring the codebase yourself.

The subagent reads relevant files in its own context, returns a structured implementation-ready package (key files, patterns, dependencies, constraints), and your main context window stays clean for actual implementation.

## When to delegate

- Before implementing a feature that touches multiple files or subsystems
- Before fixing a bug where you don't yet know what files are involved
- When you need to understand types, interfaces, and patterns before writing code
- When the task requires knowing what depends on the code you'll change

## When NOT to delegate

- Single-file changes where you already know the target
- Tasks where you've already gathered context earlier in this session
- Pure understanding questions ("how does X work?") — let Opus use Claude Code's built-in `general-purpose` agent, or install the `research-agent` extra
- Pure location lookups ("where is X defined?") — let Opus use Claude Code's built-in `Explore` agent (Haiku, free)

## Good vs bad delegations

**Good:** "/gather-context Add a WebSocket notification system that integrates with the existing event bus in src/events/"
**Good:** "/gather-context Fix the race condition in the job queue where two workers pick up the same task"
**Bad:** "/gather-context Improve the codebase" — too vague, subagent will over-gather or bail early
**Bad:** "/gather-context Change the button color in Header.tsx" — single-file change, just read it directly

## Hard rules

- The subagent is read-only. Don't ask it to "also suggest an approach" — it refuses by design and suggesting approaches anchors your implementation decisions.
- Pass the full task description verbatim. Don't reduce scope — the subagent decides what's relevant.
- After receiving the context package, read the "Files Opus Must Read" section and preload those ranges before implementing.
- If the subagent returns "Task too broad", ask the user to narrow scope. Do not attempt to gather context yourself in that case.

## Why this matters

Exploring a codebase before implementation is the biggest token sink in a typical session. Opus reading 10-30 files to understand context consumes thousands of tokens for information that can be summarized in ~100 lines. The context-gatherer subagent does the exploration in isolation and returns only what you need.

## How to use

Append the rules above to your project's `CLAUDE.md`, or to `~/.claude/CLAUDE.md` for user-level routing across all projects.

This snippet pairs with `agents/context-gatherer.md` and the `/gather-context` command. It is complementary to `research-routing` — research-agent handles "how does X work" understanding, context-gatherer handles "what do I need to implement Y" pre-fetching.
