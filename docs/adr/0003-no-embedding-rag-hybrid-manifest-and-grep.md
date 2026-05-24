# 0003. No embedding RAG; hybrid AGENTS.md manifest + on-demand grep

**Date:** 2026-05-24
**Status:** accepted
**Deciders:** Filip Podstavec

## Context

The obvious move for an "AI-first dev stack" is to ship a pre-built
semantic index of the user's codebase (embeddings → vector store →
retrieval at agent query time). This is what Cursor does, what Cody
originally did, and what most "give your agent context" tutorials
recommend.

Research (`docs/specs/research/research_indexing.md`) shows the industry
quietly walked away from pure-embedding RAG for code in 2024–2025:

- Sourcegraph publicly deprecated embeddings for Cody Enterprise.
- Boris Cherny (Claude Code lead, Anthropic): *"agentic search
  outperformed everything. By a lot."*
- Aider keeps its tree-sitter repo-map but only because aider is the
  agent — Claude Code's native `Explore` (Haiku) covers the same
  ground for free.
- An Amazon Science paper (Feb 2026) reported agentic grep hitting >90%
  of RAG quality with zero index.

Staleness is the killer: between commits the index lies, and on a
fast-moving branch the lies compound. On Windows specifically,
tree-sitter language packs are notoriously painful to install.

## Decision

We **do not ship any indexing infrastructure** (no vector store, no
tree-sitter pre-build, no ctags, no precomputed symbol graph).

The "index" is three lightweight things layered together:

1. **AGENTS.md manifest** at root — short conceptual map, conventions,
   commands. Both tools see it.
2. **Per-directory AGENTS.md** in non-trivial modules — Codex merges
   nested files automatically; Claude Code picks them up on Read. The
   `ai-first-nudge` hook flags growing source dirs without one.
3. **AIDEV-NOTE / AIDEV-TODO / AIDEV-QUESTION anchor comments** in
   code — grep-able, agents instructed to scan them first via AGENTS.md.

Discovery beyond the manifest happens via Claude Code's built-in
`Explore` agent (Haiku, free of plugin-side tax) or Codex's equivalent
native grep tool.

## Consequences

### Positive

- Zero indexing infrastructure to install, maintain, or debug.
- Zero staleness — nothing is cached; every query reads fresh.
- Windows-first viable (no tree-sitter pain).
- Maintenance discipline (AIDEV anchors + per-dir AGENTS.md) is
  enforced lightly by hooks, so the "index" stays accurate naturally.

### Negative

- Per-query latency is higher than a hot vector store on huge
  monorepos. Not relevant for typical client repos (<200k LOC).
- Relies on AIDEV-NOTE discipline. Mitigated by the `ai-first-nudge`
  hook flagging missing anchors on large diffs, and the per-dir
  AGENTS.md nudge for growing modules. `/stack-check` reports
  AIDEV-TODO/QUESTION staleness so anchors don't bit-rot.

## Alternatives considered

- **Embedding RAG (Cursor-style)** — rejected per industry pattern
  (Sourcegraph deprecation, Cherny on Claude Code), Windows
  install pain, and the maintenance burden of a stale-prone index.
- **Aider-style tree-sitter repo-map** — rejected as standalone. Worth
  installing IF the user also uses aider as a second agent; for Claude
  Code primary + Codex secondary it duplicates Explore.
- **Pre-built `.repo-map.json` checked in** — rejected: stale on every
  commit; PR diffs would include index churn; staleness debugging is a
  nightmare.

## References

- Research: `docs/specs/research/research_indexing.md`
- Cherny quote: <https://x.com/bcherny/status/2017824286489383315>
- Sourcegraph FAQ on Cody embeddings deprecation
