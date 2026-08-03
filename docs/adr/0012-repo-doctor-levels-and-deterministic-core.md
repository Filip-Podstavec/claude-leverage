# 0012. `/repo-doctor` readiness levels and the deterministic-core / advisory-halo split

**Date:** 2026-08-01
**Status:** accepted
**Deciders:** Filip Podstavec

## Context

An external AI review compared this stack to Factory.ai's "agent readiness"
framework (pillars × levels, 80 % gating, cloud readiness reports) and
proposed extending `/repo-doctor` with quality layers beyond presence checks.
Three critiques of Factory's approach hold and constrain the design: presence
≠ quality (existence checks are Goodhart bait), cloud storage + required
`origin` remote is a compliance blocker for client work, and level 5
"Autonomous" is an unverifiable marketing tier. Meanwhile `/repo-doctor`'s
0–100 score is today **reproducible** — same repo state, same score — which
is what makes `--fail-on` usable as a CI gate. Model-judged or
execution-dependent checks would silently destroy that property. An Opus
design review of the first draft reshaped the levels layer (gate formula,
ladder order, no satisfied-by-absence escape hatch).

## Decision

1. **Deterministic core, advisory halo.** The 0–100 score never includes
   model-judged or execution-dependent results. Semantic review
   (`--semantic`, a subagent) and dynamic validation (a separate skill)
   render as separate advisory sections; CI can gate on them only via
   explicit opt-in (`--fail-on semantic`).
2. **Levels L0–L4, gated not averaged.** L0 Ad-hoc → L1 Instructed
   (Foundation) → L2 Maintained (Hygiene) → L3 Explained (Why AND What) →
   L4 Self-consistent (In-code AND Sync), cumulative. **Gate formula
   (canonical):** `deficit = evaluated − points` (✅=1.0, ⚠️=0.5, ❌=0; N/A
   excluded); a group passes iff `deficit ≤ max(0.5, 0.2 × evaluated)` —
   the 80 % rule for groups of ≥3 dims, with a floor so 2-dim groups
   tolerate one ⚠️ but no ❌. A required group with zero evaluated dims
   **blocks** its gate (`not assessable`), never satisfies it. There is no
   L5.
3. **History is local.** One JSON line per full run appended (shell
   redirection, never model-retyped file contents) to
   `$STATE_DIR/repo-doctor/<slug>.jsonl`; records carry `v` (plugin
   version) and `evaluated` (score divisor) so trends across dimension-set
   changes are annotated, not misread. No cloud, no telemetry, no `origin`
   requirement.
4. **CODEOWNERS and issue/PR-template dimensions are rejected** —
   team-process artifacts with weak AI-readiness signal, a high N/A rate on
   solo/client repos, and no counter to the empty-template evasion.
5. **Every dimension documents its own gaming vector** in
   `docs/repo-doctor-gaming.md`. The plugin's own `claude-leverage:` marker
   never scores ✅ on the secret-guardrails dimension — hook enforcement is
   machine-local and unverifiable from the repo; scoring our own marker
   green would be the vendor self-preference this design criticizes.
6. **Dynamic-scope carve-out reserved:** if declared-command execution is
   ever scheduled, it ships as a **separate skill** with its own
   frontmatter. A broad Bash grant must not sit in `/repo-doctor`'s
   always-active `allowed-tools` gated only by prose — prose cannot gate
   frontmatter permissions, and "the model will be careful" is exactly the
   failure mode this stack's deterministic hooks exist to prevent.

## Consequences

### Positive

- The CI number stays stable and reproducible; advisory layers can evolve
  without breaking anyone's gate.
- Levels give a management-facing vocabulary that follows the stack's own
  adoption funnel (`/init-repo` is literally the L1 bootstrap).
- Local trend without vendor lock — works in air-gapped/compliance
  environments, no remote required.
- The deficit formula is stated in points, so nobody recomputes a rounded
  percentage and disagrees with a gate.

### Negative

- Two verdict systems (deterministic + advisory) to explain to users.
- The `max(0.5, …)` floor is opinionated; no override knob in v1.
- Appending dims 21–24 shifts the score's internal weight toward Hygiene
  (6/20 → 10/24 of dimensions). Accepted and documented rather than
  re-weighted, to keep per-dimension arithmetic legible — same call as ADR
  0007's divisor change.
- State file grows one line per run (capped ~100 records by trimming).

## Alternatives considered

- **Merge semantic verdicts into the score** — rejected: breaks
  reproducibility, kills the CI gate.
- **Separate `/readiness` audit skill** — rejected: same "one audit
  command" rationale as ADR 0007.
- **Percentage-stated gates (Factory's 80 %)** — rejected: 2-dim groups can
  only hit 0/50/75/100 %, so an 80 % phrasing demands perfection there.
- **Hygiene-first ladder (L1 "Buildable")** — rejected: labels a
  well-documented legacy repo "Ad-hoc" over test-ratio/logging dims;
  Foundation-first matches the adoption funnel.
- **Satisfied-by-absence for all-N/A groups** — rejected: would award L1 to
  an empty repo; "not assessable" blocks instead.
- **Score re-weighting to equal group weights** — rejected: aligns score
  with levels but makes the per-dim score illegible.
- **Factory's L5 "Autonomous"** — rejected: unverifiable criterion.
- **Cloud report storage / dashboard** — rejected: compliance blocker;
  local JSONL + trend line covers the need.

## References

- Design + implementation plans:
  `docs/specs/2026-08-01-readiness-extension-design.md` and
  `docs/specs/2026-08-01-readiness-plan-{1,2,3}-*.md` (external review and
  Opus design review summarized there).
- Factory agent readiness: <https://docs.factory.ai/> (readiness framework
  marketing; the critique in Context).
- Related ADRs: 0006 (original `/repo-doctor` design), 0007 (Sync
  dimensions; divisor-change precedent), 0009 (severity-split precedent for
  keeping concerns separate). Extends 0006/0007 without superseding them.
