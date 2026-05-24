# 0001. Pivot from token-savings thesis to personal dev stack

**Date:** 2026-05-24
**Status:** accepted
**Deciders:** Filip Podstavec

## Context

The v0.x thesis of `claude-leverage` was: routing development work across
Sonnet/Haiku subagents would reduce token cost vs. vanilla Claude Code,
while preserving quality. Three rounds of rigorous benchmarking on Opus 4.7
(`bench/archive-token-savings-thesis/`) disproved this across every
scenario tested — cold cache, warm cache, 12-turn day-in-the-life, and
isolated per-agent audits. Per-invocation `Task`-tool dispatch overhead
structurally exceeded per-token Sonnet/Haiku savings on the current Claude
Code stack.

The repo had a real audience (Filip himself, plus anyone forking) and a
real set of valuable components (security hooks, AI-first conventions,
some skills). Abandoning the repo would discard that value.

## Decision

We pivot the project's positioning from "token savings via subagent
tiering" to **a personal AI-dev stack for Claude Code and Codex** that
helps ship secure and long-term-maintainable software for clients.

The 11 retired token-savings-era subagents are frozen in
`bench/archive-token-savings-thesis/agents/` with tombstone references to
their benchmark verdicts. The two with non-cost value (`security-reviewer`
for deterministic schema, `flaky-test-isolator` for statistical signal)
survive at the top level.

## Consequences

### Positive

- The project's headline matches what it actually delivers.
- The benchmark data becomes a credibility asset (honest evidence) rather
  than a problem to hide.
- Future feature decisions get evaluated against the new mission (secure
  + long-term-maintainable client work via AI agents), not against an
  obsolete cost thesis.

### Negative

- Existing v0.x users running `/plugin update` see a substantial
  behavioral change (subagents disappear, new skills appear). Mitigated by
  the v1.0.0 release tag (semantic versioning communicates the break).
- Some sunk cost on subagent infrastructure that's now archived.

## Alternatives considered

- **Keep iterating on the token-savings thesis** — rejected. The
  benchmark mechanism (per-invocation dispatch tax > per-token savings)
  is structural to how the plugin model interacts with prompt caching on
  Opus 4.7. Not a tuning problem.
- **Abandon the repo and start a new one** — rejected. The security
  hooks, AGENTS.md conventions, and statusline retained real value;
  starting over would lose the commit history that justifies the
  pivot's design decisions.
- **Keep it dual-positioned** — rejected. Inconsistent README undermines
  the technical pivot.

## References

- Benchmark archive: `bench/archive-token-savings-thesis/`
- Design package: `docs/specs/2026-05-24-pivot/`
- Honest history section: top-level `README.md`
