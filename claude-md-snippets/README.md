# CLAUDE.md Snippets

Fragments meant to be copied into your project's `CLAUDE.md` or `~/.claude/CLAUDE.md`. These are not standalone files - they are building blocks: orchestration rules, model routing patterns, coding conventions, and guardrails.

Pick what applies, paste it into your `CLAUDE.md`, and adjust to taste.

## Install

No install step. Browse the snippets, copy what you need into your `CLAUDE.md`.

## Available snippets

- [`code-review-routing.md`](code-review-routing.md) - Routes review requests to the `code-reviewer` subagent and applies fixes in the main session. Pair with `agents/code-reviewer.md` and `commands/code-review.md`.
- [`test-routing.md`](test-routing.md) - Routes test requests to the `test-runner` subagent and applies fixes in the main session. Pair with `agents/test-runner.md` and `commands/test.md`.
