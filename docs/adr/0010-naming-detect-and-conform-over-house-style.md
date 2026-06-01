---
status: accepted
date: 2026-06-01
deciders: Filip Podstavec
consulted: Claude Opus 4.8 (brainstorming session)
informed: stack users
---

# 0010. Naming convention: detect-and-conform, not a prescribed house style

## Context and Problem Statement

The stack documents how code should be *shaped* (`Write less, fit in`) but
says almost nothing about how identifiers should be *named*, beyond a single
clause — "Naming … should look like the rest of the module." Naming is one of
the highest-signal factors in whether the *next* agent can safely modify a
codebase, and AI agents have a specific, repeatable failure mode here:

1. **Casing drift.** A model carries a strong language-default prior
   (Python → `snake_case`, JS → `camelCase`). Dropped into a client repo that
   deviates from that default, it silently imposes its own style, so new code
   reads as "the AI-written part" and the repo's casing fragments.
2. **Wrong granularity.** Generated names land at the wrong altitude — either
   too vague (`get()`, `data()`, `handle()`) or implementation-leaking and
   verbose (`getting_data_from_mobile()`). Both make the call site harder to
   read than a name pitched at the function's actual intent.

The open question is **what kind** of naming guidance the stack should carry:
its own opinionated rules, or a discipline for conforming to whatever the
target repo already does.

## Decision Drivers

- The stack's north star is **"fit in"** — new code should be
  indistinguishable from the surrounding module. A house style that overrides
  the repo's existing convention directly contradicts that.
- Client repos are heterogeneous: the same agent works in `camelCase`,
  `snake_case`, and `kebab-case` repos in the same week. A single prescribed
  style would be wrong in most of them.
- Even within one repo, casing legitimately differs **by kind** (types
  `PascalCase`, functions `camelCase`/`snake_case`, constants `UPPER_SNAKE`),
  so a flat global rule cannot be right.
- Must stay lean per [ADR 0009](0009-agents-md-lean-budget-and-size-tiers.md):
  inline only the always-true principle; push depth to `docs/`.

## Considered Options

1. **Prescribed house style.** The stack ships a naming-rules table every repo
   must follow. Rejected: directly violates "fit in", and is wrong in any repo
   whose existing convention differs — which is most of them.
2. **Stay implicit.** Rely on the existing "Naming should look like the rest of
   the module" clause. Rejected: it states the goal but not the *discipline*
   (detect first, don't impose your default) and ignores the granularity axis
   entirely, so both failure modes above survive.
3. **Detect-and-conform discipline + a universal quality principle. Selected.**
   Casing/separator style is treated as repo-specific — the agent must *detect*
   the existing convention (per kind, per local module) and conform, never
   impose its language default. Granularity/clarity is treated as a universal
   principle — name to the function's intent, neither vague nor rambling.

## Decision Outcome

**Chosen: Option 3.** Two layers, with deliberately different epistemics:

- **Casing / separator → descriptive.** There is no stack-wide "correct"
  style; the correct style is whatever the surrounding code already uses. The
  agent detects it (scan sibling files / nearby identifiers; in a mixed repo,
  match the *local* module over the global majority) and conforms per kind.
- **Granularity / clarity → universal.** Independent of the repo: a name states
  intent at the right altitude — neither `get()` nor
  `getting_data_from_mobile()`. This is the one prescriptive bit, and it is
  about *quality*, not *style*.

Anchored as a tight `Name to fit in` bullet inline in the `Write less, fit in`
section of both the root `AGENTS.md` and the shipped
`templates/AGENTS.md.example`, with the detection mechanics and worked examples
in [`docs/conventions.md`](../conventions.md) per the ADR 0009 lean budget.

### Consequences

**Positive:**
- Closes both AI naming failure modes (casing drift, wrong granularity) with a
  rule that reinforces "fit in" instead of fighting it.
- Correct across heterogeneous client repos by construction — there is no
  global style to be wrong about.

**Negative / costs:**
- "Detect the convention" is softer than a lookup table; in a genuinely
  inconsistent repo the agent must exercise judgment about which local example
  to follow. Accepted — that judgment is the point, and a wrong-but-uniform
  house style would be worse.
- One more always-on bullet in `AGENTS.md` (~0.3 KiB), kept within the 8 KiB
  budget by housing the depth in `docs/conventions.md`.

## References

- [ADR 0009](0009-agents-md-lean-budget-and-size-tiers.md) — the lean budget
  that dictates inline-principle / docs-depth placement.
- [ADR 0002](0002-agents-md-canonical-claude-md-import.md) — why AGENTS.md is
  the canonical surface the principle lands in.
- `AGENTS.md` ("Write less, fit in") and `docs/conventions.md` ("Naming") — the
  convention as carried in this repo.
- `templates/AGENTS.md.example` — the convention as shipped to client repos.
