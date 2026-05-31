# Session: anti-slop conventions, legacy-onboarding workflow, and AGENTS.md lean budget

**Date:** 2026-05-31
**Branch:** feat/anti-slop-and-legacy-onboarding
**Participants:** Filip Podstavec, Claude Opus 4.8 (1M context)
**Duration:** ~3 hours

## Context

Whole-repo review of the v1.8.3 state, framed by the mission: the plugin must
guide agents to write *sustainable, AI-first* code — not just produce artifacts.
Key diagnosis: every convention the stack documented was **additive** (add
anchors, add logs, add per-dir docs) with no counterweight against AI slop, and
nothing constrained the size of `AGENTS.md` — the one always-loaded, highest-
leverage artifact. Both gaps were closed this session.

## What was done

- Added `Write less, fit in` code-convention (match surrounding code, comments
  explain WHY not WHAT, no speculative abstraction) to `templates/AGENTS.md.example`
  and root `AGENTS.md`. First *subtractive* guidance in the stack.
- Wrote `workflows/onboarding-a-legacy-repo.md` — the canonical "inherit a messy
  repo, make it AI-ready incrementally" guide (the core use case).
- Fixed `/codex-sandbox` stale `--profile staging` argument-hint; expanded the
  thin `/refresh-context-map` SKILL (Hard rules + failure-mode).
- Added `Keeping this file lean` convention + two-tier size checks: `/stack-check`
  warns >8 KiB / flags >32 KiB; `/repo-doctor` Dim 1 fails >32 KiB, warns >8 KiB.
- Two commits shipped, both pushed; version folded into unreleased v1.9.0.

## Key decisions

- 8 KiB soft target / 32 KiB hard cap for AGENTS.md, recorded in
  [ADR 0009](../adr/0009-agents-md-lean-budget-and-size-tiers.md). 32 KiB is the
  Codex `project_doc.max_bytes` truncation point (sourced); 8 KiB is a judgment
  call (recorded so it isn't mistaken for arbitrary).
- Deliberate severity asymmetry: `/stack-check` advisory both tiers,
  `/repo-doctor` gates >32 KiB. Informer vs. gate.
- Both proposal rounds were run through a reviewing subagent before
  implementing, per Filip's requested process.

## Open questions

- Is the Codex 32 KiB cap per-file or aggregate across merged AGENTS.md? Framed
  as aggregate (safer, and the stack recommends per-dir files) — unverified
  against live Codex.
- Whether 8 KiB proves too aggressive in real repos (would need a follow-up ADR
  to revise, not a silent retune).

## Next steps

- **Resolve the dogfooding TODO**: root `AGENTS.md` is 18.7 KiB, over the new
  8 KiB target. `AIDEV-TODO(by: 2026-07-15)` tracks the slimming — extract depth
  to `docs/` with when-to-read links. Focused follow-up PR, not bundled.
- Run `/repo-doctor` on this repo as a real dogfood (expect Dim 1 ⚠️).
- Open a PR for `feat/anti-slop-and-legacy-onboarding` (still unmerged).

## References

- Commits: 8719164 (anti-slop + legacy-onboarding), faff7b8 (lean budget + tiers)
- ADRs added: [0009](../adr/0009-agents-md-lean-budget-and-size-tiers.md);
  relates to [0008](../adr/0008-smart-context-surfacing-via-pretooluse-hook.md)
- Prior session: [2026-05-26 discoverability layer](2026-05-26-discoverability-layer-v1.5-v1.6.md)

---

*Distillate, not transcript.*
