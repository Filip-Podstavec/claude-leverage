# Architecture Decision Records (ADRs)

Numbered, immutable records of significant architectural decisions in this
repo. Lightweight MADR-flavored format.

## Why ADRs

> "Without them, six months from now nobody (human or agent) remembers why
> we chose A instead of B, and proposes a refactor back to B."

For an AI-first repo this matters double: agents are good at proposing
plausible refactors, and ADRs are the one thing that reliably stops a
plausible-but-wrong refactor by showing the load-bearing constraint behind
the original choice.

## Convention

- One Markdown file per decision, numbered: `NNNN-kebab-case-title.md`.
- **Immutable status**: once accepted, do not rewrite. New decisions
  superseding an old one are NEW ADRs that reference the old by number.
- Statuses: `proposed` | `accepted` | `deprecated` | `superseded by [NNNN]`.
- Use the [`template.md`](template.md) as the starting point.
- New ADR: invoke `/adr-new` — the skill picks the next number, asks for
  title and context, and bootstraps the file.

## Index

- [0001 — Pivot from token-savings thesis to personal dev stack](0001-pivot-from-token-savings-to-dev-stack.md)
- [0002 — AGENTS.md canonical; CLAUDE.md is a one-line `@AGENTS.md` import](0002-agents-md-canonical-claude-md-import.md)
- [0003 — No embedding RAG; hybrid AGENTS.md manifest + on-demand grep](0003-no-embedding-rag-hybrid-manifest-and-grep.md)
- [0004 — `/adr-new` and `/session-log` are user/agent-invoked, no auto-fire hook](0004-adr-and-session-log-are-user-invoked-no-auto-fire-hook.md)
- [0005 — Structured discoverability layer: GLOSSARY.md + architecture.yml](0005-structured-discoverability-glossary-and-architecture-yml.md)
- [0006 — `/repo-doctor` skill, folded-scalar SKILL descriptions, and gated skill-cheatsheet hook](0006-repo-doctor-skill-discoverability-and-folded-scalar.md)
- [0007 — Sync drift detection in `/repo-doctor` (Dimensions 16–20)](0007-sync-drift-detection-in-repo-doctor.md)
- [0008 — Smart context surfacing via PreToolUse hook (cuts per-session token tax)](0008-smart-context-surfacing-via-pretooluse-hook.md)
- [0009 — AGENTS.md lean budget (8 KiB target / 32 KiB hard cap) and stack-check vs repo-doctor severity split](0009-agents-md-lean-budget-and-size-tiers.md)
- [0010 — Naming: detect-and-conform over a prescribed house style](0010-naming-detect-and-conform-over-house-style.md)

(Keep this index in sync with the files in this directory; `/adr-new` will
append to it automatically.)
