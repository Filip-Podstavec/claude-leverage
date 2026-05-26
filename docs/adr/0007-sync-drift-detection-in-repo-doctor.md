# 0007. Sync drift detection in `/repo-doctor` (Dimensions 16–20)

**Date:** 2026-05-26
**Status:** accepted
**Deciders:** Filip Podstavec

## Context

[ADR 0006](0006-repo-doctor-skill-discoverability-and-folded-scalar.md)
shipped `/repo-doctor` as a **completeness audit**: 15 dimensions that
answer "what's missing for AI-first work here?". Filip surfaced a real
gap on the day of release: the skill checks the **presence** of
descriptive artifacts (AGENTS.md, GLOSSARY.md, architecture.yml, …)
but not whether those artifacts are still **synchronized with the
code they describe**.

Concrete failure modes the v1.6.0 doctor cannot catch:

- `architecture.yml`'s `public_surface: [LegacyClient]` survives long
  after `LegacyClient` was renamed to `Client`.
- A `GLOSSARY.md` term `Lead` was load-bearing six months ago; today
  it doesn't appear in code at all, but the glossary still says it
  means "an article lead" — actively misleading.
- A high-frequency new domain identifier (e.g. `Account` introduced
  in v2) appears 47× across 12 files but never made it into the
  glossary.
- A per-dir `AGENTS.md` was last touched in Q1 2026; the dir got 30+
  commits since. The prose still describes the Q1 surface.
- `plugin.json` says `1.6.0` but `CHANGELOG.md` top heading is
  `## [1.5.0]`. The release was bumped without the changelog
  entry.
- README mentions `/old-command` that was removed two minor versions
  ago.

These are real AI-first failure modes: the descriptive layer becomes
**actively misleading**, which is worse than a missing layer. A
missing GLOSSARY.md lets the agent ask. A *stale* GLOSSARY.md gives
the agent confident wrong answers.

`/stack-check` covers time-based staleness (anchor age, markdown
file-path drift in arbitrary `.md` files, AGENTS.md size cap) and
version freshness of installed tools. It does *not* validate
structured artifacts (architecture.yml, GLOSSARY.md) against code, or
per-dir AGENTS.md against dir activity, or CHANGELOG against version
manifest. There was no place that did.

## Decision

We add a **fifth dimension group "Sync" (Dimensions 16–20)** to
`/repo-doctor`, focused on **code ↔ docs drift**. Five checks, all
read-only, all cheap (grep + Read + `git log -1 --format=%ct`):

16. `architecture.yml` ↔ disk (declared paths exist, `public_surface`
    symbols still in code, no orphan source dirs).
17. `GLOSSARY.md` ↔ code (terms still referenced, `Code:` paths
    valid, top-K identifiers not missing from glossary).
18. Per-dir `AGENTS.md` staleness vs dir activity (gap_days > 30).
19. `CHANGELOG.md` top entry vs primary version manifest.
20. `README.md` slash-refs vs available skills/commands.

Every Sync dimension returns **N/A (excluded from score divisor)**
when its target artifact does not exist — drift is meaningless when
there's nothing to drift from. The presence gap is already reported
by the corresponding earlier dimension.

The total dimension count is now **~20**, but the actual score
divisor is `(20 − N/A count)` so a shell-heavy meta-repo without
arch-map / glossary / structured-logging convention is not penalized
for the absence — only the dimensions that apply to *this* repo
contribute to its score.

## Consequences

### Positive

- **Closes the "actively misleading docs" failure mode**, which is
  the highest-cost failure mode in AI-first repos (misleading docs >
  missing docs).
- **Stays in `/repo-doctor`** rather than spawning a separate
  `/sync-check` skill — keeps the user's mental model "one audit
  command tells me what's wrong". Spawning two near-overlapping
  audit skills would have been ergonomic friction.
- **`--scope sync`** lets the user run only drift checks ("did my
  last commit invalidate any docs?") cheaply, without doing the
  full 20-dimension walk.
- **N/A semantics protect the score from gratuitous penalties** —
  a repo without `architecture.yml` doesn't get a ❌ for Dim 16; it
  gets N/A and the divisor adjusts. The presence gap is Dim 7's
  job, not Dim 16's.
- **No new tools, no new dependencies** — every Sync check uses the
  same `allowed-tools` already declared. Codex parity automatic.

### Negative

- **Score divisor is now variable.** Pre-v1.7 scores divided by 15
  always; post-v1.7 divides by `(20 − N/A)`. A repo's score may
  *change* between v1.6 and v1.7 even if nothing else changed. We
  document the divisor in the report's summary line so the number
  is interpretable.
- **Heuristic on top-K identifiers not in glossary may produce
  false-positive "missing terms".** A high-frequency identifier
  like `Request` or `Config` is library-shaped, not domain-shaped.
  Dim 17 reuses `/glossary-init`'s filter heuristic (drop common
  framework base classes); same trade-off applies — sometimes a
  genuine domain term will be filtered, sometimes a library type
  will slip through. Acceptable noise floor.
- **Per-dir AGENTS.md staleness threshold of 30 days is opinionated.**
  Some dirs naturally drift faster (active feature work) and
  shouldn't be flagged. Override via
  `CLAUDE_LEVERAGE_AGENTS_MD_DRIFT_DAYS` is the escape hatch; we
  don't auto-tune.
- **CHANGELOG ↔ version check assumes
  [Keep a Changelog](https://keepachangelog.com/) format.** Most
  AI-first repos use it; rare exceptions (CHANGELOG.txt, plain
  prose) silently fall to N/A.

## Alternatives considered

- **Spawn a new `/sync-check` skill, leave `/repo-doctor` at 15
  dimensions.** Rejected. The user's mental model of "one audit
  command" was already proven by /repo-doctor's design intent (ADR
  0006); fragmenting into two audit skills would re-introduce the
  recall problem (which skill do I run when?).
- **Hook-driven prevention** — `PostToolUse(Edit|Write)` hook that
  nudges when an edit touches a name in `architecture.yml`'s
  `public_surface` or `GLOSSARY.md`. Rejected for v1.7 — audit
  first because we need observation data on which drift dimensions
  actually fire before designing a real-time hook. Audit catches
  what already drifted; hook would prevent what's about to drift.
  Audit is higher leverage right now. Candidate for v1.8+.
- **Extend `/stack-check` instead.** Rejected. `/stack-check` is
  time-based ("how stale?"); Sync drift is content-based ("does X
  still describe Y?"). Mixing the two muddies each: a fresh
  AGENTS.md with stale content fails on stack-check's mtime check
  *and* on Sync's content check, but only one of those is the real
  issue.
- **Auto-fix drift** (e.g. auto-add missing glossary terms,
  auto-regenerate `architecture.yml` from disk). Rejected. Same
  rationale as `/glossary-init` (LLM-generated AGENTS-style files
  lose 0.5–2pp on task success vs human-curated, Augment Code 2026
  study). The doctor reports; the user fixes (often by invoking the
  matching bootstrap skill, e.g. `/arch-map`).

## References

- Related ADRs: [0005](0005-structured-discoverability-glossary-and-architecture-yml.md)
  (the artifacts being drift-checked), [0006](0006-repo-doctor-skill-discoverability-and-folded-scalar.md)
  (the original /repo-doctor design). This ADR extends 0006 without
  superseding it.
- Triggered by in-conversation question from Filip after v1.6.0
  shipped, documented in session log
  [2026-05-26](../sessions/2026-05-26-discoverability-layer-v1.5-v1.6.md)
  open-questions list (where it had been flagged as "candidate for
  v1.6.1 or v1.7"). Picked up immediately because the failure mode
  is more central to AI-first mission than the other deferred
  follow-ups.
- [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) — assumed
  format for Dim 19.
