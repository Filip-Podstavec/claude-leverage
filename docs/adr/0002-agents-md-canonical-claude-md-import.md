# 0002. AGENTS.md canonical; CLAUDE.md is a one-line `@AGENTS.md` import

**Date:** 2026-05-24
**Status:** accepted
**Deciders:** Filip Podstavec

## Context

The plugin targets both Claude Code (which reads `CLAUDE.md`) and Codex
CLI (which reads `AGENTS.md` natively). Without intervention, this is
either:

- Two files with identical content (drift inevitable, two-tool review
  burden), or
- One file with a symlink (works on macOS/Linux; on Windows requires
  Admin/Developer Mode — disqualifying for a Windows-first dev).

Claude Code supports `@<path>` imports in `CLAUDE.md` (research:
`docs/specs/research/research_dual_codex_claude.md`), which expand the
target file into context at session start with 5-hop recursion.

## Decision

`AGENTS.md` is the canonical instruction set. `CLAUDE.md` is a one-line
import (`@AGENTS.md`) plus an optional short Claude-only section below
it. Both tools see identical guidance for everything that matters.

This applies to the plugin's own repo AND to projects that adopt the
stack via `/init-repo`.

## Consequences

### Positive

- One source of truth; impossible to forget to update both.
- Cross-platform — no symlink, no admin requirement.
- Codex parity automatic: Codex reads `AGENTS.md` natively, the import
  in `CLAUDE.md` makes Claude Code see the same content.
- The Claude-only section in `CLAUDE.md` is the right place for
  Claude-Code-specific tips (plan mode, slash command syntax) without
  polluting Codex's view.

### Negative

- `AGENTS.md` is capped at 32 KiB by Codex (silently drops content past
  that). Mitigated by `/stack-check`'s AGENTS.md sanity pass.
- Two files exist, which still looks like duplication to a contributor
  who doesn't read `CLAUDE.md`. Mitigated by the one-line content of
  `CLAUDE.md` and a comment block explaining the relationship.

## Alternatives considered

- **Symlink** — rejected per Windows admin requirement (and Git Bash
  symlink quirks).
- **One file (only `AGENTS.md`), no `CLAUDE.md`** — rejected: Claude
  Code does not (yet) read `AGENTS.md` natively (open issue
  anthropics/claude-code#6235). The `@AGENTS.md` import IS the supported
  pattern.
- **Generate `CLAUDE.md` from `AGENTS.md` via a script** — rejected.
  Generators drift when the generator script itself bit-rots; the one-line
  import is simpler.

## References

- Research: `docs/specs/research/research_dual_codex_claude.md`
- Reference repo: `carlrannaberg/claudekit` (same pattern, symlink variant)
- Open issue: <https://github.com/anthropics/claude-code/issues/6235>
