# claude-leverage pivot — design package

**Date:** 2026-05-24
**Status:** Draft for user review
**Author:** Claude (Opus 4.7) at user request

This folder holds the design package for pivoting `claude-leverage` away from a
"save tokens by tier-routing across Sonnet/Haiku" thesis (disproven by our own
benchmarks, see `bench/`) into a **personal Claude Code + Codex dev stack**
for a single professional developer — opinionated hooks, AI-first
conventions, and skills. Complements skills-based plugins like the
official `superpowers` plugin (which we still use); it does not try to
replace them.

The plan is split across files because the topics are partially independent —
each can be reviewed and revised on its own.

| # | File | Topic |
|---|------|-------|
| 00 | [`00-vision.md`](00-vision.md) | What the repo becomes, what we keep/archive, distribution and naming |
| 01 | [`01-architecture.md`](01-architecture.md) | Directory layout, dual Claude+Codex topology, statusline integration |
| 02 | [`02-security-first.md`](02-security-first.md) | Security-review workflow: hooks + on-demand subagent, auto-trigger rules |
| 03 | [`03-ai-first-code.md`](03-ai-first-code.md) | AIDEV-NOTE anchors, structured logging, per-dir AGENTS.md, enforcement hooks |
| 04 | [`04-visualization.md`](04-visualization.md) | Mermaid repo map + process diagrams, freshness story |
| 05 | [`05-stack-freshness.md`](05-stack-freshness.md) | 30-day stack-update check, declarative `stack.toml`, `/stack-check` skill |
| 06 | [`06-roadmap.md`](06-roadmap.md) | Implementation phases in order, what ships first |

Supporting research (already written) lives in [`../research/`](../research/):

- [`research_indexing.md`](../research/research_indexing.md) — codebase indexing approaches
- [`research_ai_first_code.md`](../research/research_ai_first_code.md) — AI-targeted code conventions
- [`research_dual_codex_claude.md`](../research/research_dual_codex_claude.md) — AGENTS.md spec + portability
- [`research_visualization.md`](../research/research_visualization.md) — mermaid + diagram tooling

## How to read

If you only have 5 minutes: read `00-vision.md` and the summary at the top of
`06-roadmap.md`. Everything else is detail you can pull on demand.

If you want to push back, the most opinionated calls are in **00** (keep repo
public, keep marketplace, archive bench/) and **03** (mandate AIDEV-NOTE on
non-obvious code, enforced via PreToolUse warn-not-block). Those are the two
places where my assumptions could be wrong and you'd want to redirect.

## Status convention

Each spec file ends with an **Open questions** section listing what I assumed
and where the answer might want to be different. After your review pass, those
become either confirmed decisions or revised text.
