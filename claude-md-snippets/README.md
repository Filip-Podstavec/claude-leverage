# CLAUDE.md Snippets

Fragments meant to be copied into your project's `CLAUDE.md` or `~/.claude/CLAUDE.md`. These are not standalone files - they are building blocks: orchestration rules, model routing patterns, coding conventions, and guardrails.

Pick what applies, paste it into your `CLAUDE.md`, and adjust to taste.

## Install

No install step. Browse the snippets, copy what you need into your `CLAUDE.md`.

## Available snippets (default install)

- [`code-review-routing.md`](code-review-routing.md) - Scope-conditional review routing: delegate to `code-reviewer` for non-trivial scope (3+ files or 50+ lines), inline for trivial. Pair with `agents/code-reviewer.md` and `commands/code-review.md`.
- [`test-routing.md`](test-routing.md) - Scope-conditional test routing: delegate to `test-runner` for full-suite or multi-file changes, inline for single targeted tests. Pair with `agents/test-runner.md` and `commands/test.md`.
- [`context-gathering-routing.md`](context-gathering-routing.md) - Pre-implementation context routing: delegate to `context-gatherer` (Haiku) when a task will likely touch 3+ files or files are unknown, inline for single-file changes. Pair with `agents/context-gatherer.md` and `commands/gather-context.md`.

## Extras (opt-in) — see [`../extras/`](../extras/README.md)

- `research-routing` (in `extras/claude-md-snippets/`) - pair with `research-agent` extra
- `docs-sync-routing` (in `extras/claude-md-snippets/`) - pair with `docs-updater` + `/docs-sync` extras

## Easier install

The `/install-snippets` slash command (in `commands/`) appends selected snippets here to your `~/.claude/CLAUDE.md` or project `CLAUDE.md` with marker comments for duplicate detection. Use it instead of manual copy-paste once you have the plugin or the slash command installed.
