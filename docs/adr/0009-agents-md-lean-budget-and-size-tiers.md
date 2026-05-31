---
status: accepted
date: 2026-05-31
deciders: Filip Podstavec
consulted: a reviewing subagent on the v1.9.0 change set
informed: stack users
---

# 0009. AGENTS.md lean budget (8 KiB target / 32 KiB hard cap) and the stack-check vs repo-doctor severity split

## Context and Problem Statement

`AGENTS.md` is the single highest-leverage artifact this stack installs: it
loads into **every** agent session and shapes how the agent writes code. That
same property makes it the easiest thing to ruin by accretion — every session
that adds "just one more rule" grows the always-on context until the file is
too long to internalize in one pass, and eventually large enough to break.

There is a hard functional ceiling, not just an attention one. Codex assembles
its project doc from the root `AGENTS.md` plus any merged per-directory
`AGENTS.md` files and caps it at `project_doc.max_bytes` (default **32768 =
32 KiB**), **silently dropping** everything past that byte. Content beyond the
cap is invisible to Codex agents with no warning. Because the stack actively
recommends per-directory `AGENTS.md`, the root file and every per-dir file draw
on the *same* shared budget.

[ADR 0008](0008-smart-context-surfacing-via-pretooluse-hook.md) already reduced
the per-session *reading* tax (the agent no longer reads `AGENTS.md`
preemptively for files it never touches). But 0008 does not help here: the
context-surface hook surfaces anchors at edit time, yet Codex still never loads
bytes past the 32 KiB cap, and an over-long always-on file still dilutes
attention regardless of the hook. So a size discipline is a distinct,
complementary decision.

The open questions: what numeric target, and how hard should each tool enforce
it?

## Decision Drivers

- Must respect the Codex 32 KiB hard cap — past it, instructions are silently
  lost, which is a correctness defect, not a preference.
- Should keep the always-on file scannable enough to actually be internalized.
- Must compose with the per-dir AGENTS.md recommendation (shared budget).
- Should push topic *depth* to `docs/`, where ADR 0008's hook can surface it on
  demand, rather than carrying it always-on.
- Tooling severity should match consequence: data loss vs. a soft target are
  not the same thing and should not read the same.

## Considered Options

1. **Only enforce the 32 KiB Codex cap** (status quo before this ADR). Catches
   the hard failure but lets files bloat to 31 KiB unchallenged — by which
   point attention dilution and per-dir budget pressure are already real.
2. **Single soft target, no hard tier.** Loses the "this is actually broken on
   Codex now" signal.
3. **Two tiers: 8 KiB soft target + 32 KiB hard cap. Selected.**

Why **8 KiB** specifically: ~8 KiB is roughly 2,000 tokens / ~150–200 lines of
prose — about the most an always-loaded instruction file can be and still be
read and held in one pass. It sits well clear of the 32 KiB Codex cap, leaving
headroom for the per-dir `AGENTS.md` files that share the budget. It is a
deliberately *aggressive* target: crossing it is the cue to start extracting
depth to `docs/`, long before anything breaks. The number is a judgment call,
not a measured constant (only the 32 KiB cap is sourced) — recorded here so it
is not mistaken for arbitrary.

## Decision Outcome

**Chosen: Option 3 — two tiers, with asymmetric enforcement across the two
auditing skills.**

- The `templates/AGENTS.md.example` and root `AGENTS.md` both document the
  "keep it lean" convention: inline only always-true load-bearing rules; push
  topic depth to `docs/` behind *when-to-read* links (a bare link an agent has
  no reason to open is not progressive disclosure, it is a dead end).
- `/stack-check` reports **both** tiers as advisory and still resets its
  freshness timestamp (it informs; it does not gate).
- `/repo-doctor` Dimension 1 escalates **> 32 KiB to a hard ❌** (it is a
  scored audit usable as a CI `--fail-on` gate; silent data loss on Codex
  warrants a fail) and keeps **> 8 KiB at ⚠️** (a soft target, not a defect).

The split is intentional: `/stack-check` is a periodic freshness nudge,
`/repo-doctor` is a gate-able readiness score. Encoding the same 32 KiB fact at
two severities is correct precisely because the two tools answer different
questions.

### Consequences

**Positive:**
- The bloat failure mode is caught early (8 KiB) instead of only at the point
  of Codex data loss (32 KiB).
- Complements ADR 0008: depth lives in `docs/` and is surfaced on demand, not
  carried always-on.
- Severity matches consequence, so a CI gate on `/repo-doctor` fails on real
  data loss without being noisy about the soft target.

**Negative:**
- This repo's own root `AGENTS.md` is **18.7 KiB** at the time of this ADR — it
  trips the new ⚠️ immediately. Recorded honestly as a deadlined `AIDEV-TODO`
  in `AGENTS.md` rather than hidden or fixed by a risky big-bang refactor in the
  same change; the slimming is a focused follow-up.
- `8 KiB` is a judgment number; if it proves too aggressive in practice it will
  need a follow-up ADR to revise (do not silently retune it — that is the kind
  of unexplained constant this ADR exists to prevent).
- One more place the 32 KiB fact is written (template, root AGENTS.md,
  `/stack-check`, `/repo-doctor`). Each loads independently, so the
  duplication is accepted; this ADR is the canonical rationale they point to.

## References

- [ADR 0008](0008-smart-context-surfacing-via-pretooluse-hook.md) — the
  on-demand surfacing that makes pushing depth to `docs/` viable.
- [ADR 0002](0002-agents-md-canonical-claude-md-import.md) — why AGENTS.md is
  the canonical surface in the first place.
- `templates/AGENTS.md.example` ("Keeping this file lean") — the convention as
  shipped to client repos.
- Codex `project_doc.max_bytes` default (32768) — the source of the 32 KiB cap.
