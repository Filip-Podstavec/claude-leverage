# Repo-doctor readiness extension — design

> **Status:** Design v2 (2026-08-01, revised after Opus design review — levels
> layer reworked, 12 further findings folded in). Source: external AI review of
> the plugin against Factory's "agent readiness" methodology, evaluated and
> re-scoped for this stack. Next: implementation via Plans 1–3.

**Goal:** Extend `/repo-doctor` from a presence+drift audit into a full
AI-readiness methodology — deterministic presence checks, a levels layer with
local history, an agent-judged semantic quality scope, and (deferred) a dynamic
validation scope — without breaking the skill's deterministic, read-only,
local-only contract.

## Where this came from

An external AI review compared the plugin's goals to Factory.ai's "agent
readiness" framework (pillars × levels, 80 % gating, readiness reports) and
proposed a four-layer local methodology. The review's core critique of Factory
holds and shapes every decision below:

1. **Presence ≠ quality** — existence checks are Goodhart bait (empty file
   passes).
2. **Vendor lock + telemetry** — Factory stores reports in their cloud and
   requires an `origin` remote; a blocker for client/compliance work. Our
   version must stay fully local.
3. **Level 5 "Autonomous" is marketing** — not a verifiable criterion.

## The four-layer model, and what we adopt

| Layer | What it checks | Verdict |
|---|---|---|
| 1. Presence (deterministic) | artifacts/config exist | **Adopt, pruned** — 4 new dims, not 6 (see below) |
| 2. Semantic quality (agent-judged) | do the artifacts tell the truth? | **Adopt** — new `readiness-reviewer` subagent, advisory only |
| 3. Dynamic validation (execution) | do declared commands actually run? | **Defer** — designed (Plan 3), not scheduled |
| 4. Behavioral benchmark (canary task) | does an agent orient well here? | **Reject for the skill** — stays in `bench/eval`; portability is unsolved and the A/B harness already does this for this repo |

## Load-bearing decision: deterministic core, advisory halo

`/repo-doctor`'s 0–100 score is today **reproducible**: same repo state → same
score. That is what makes `--fail-on` usable as a CI gate. Layers 2 and 3 are
model-judged / execution-dependent and therefore non-reproducible.

**Decision:** the deterministic score never includes semantic or dynamic
results. They render as separate report sections with their own verdicts.
CI gating on them is possible but explicitly opt-in (`--fail-on semantic`).
This split gets its own ADR (0012, authored in Plan 1) because it is exactly
the kind of constraint a future agent would "clean up" by merging the scores.
The ADR also reserves the dynamic-scope carve-out: if layer 3 is ever
scheduled, it ships as a **separate skill** with its own frontmatter, because
its broad Bash grant must not sit in `/repo-doctor`'s always-active
`allowed-tools` (prose cannot gate frontmatter permissions — that would be
exactly the "model rationalizes past the guardrail" failure the hooks exist to
prevent).

## Levels layer (replaces Factory's 5 levels)

Four levels, deterministic, computed from per-group results with a gating
mechanic (a fatal gap in one group cannot be averaged away by another). No
level 5 — an unverifiable criterion is not a level. Names are descriptive, not
aspirational, and the ladder follows this stack's own adoption funnel: the
instruction layer first (`/init-repo` is the L1 bootstrap), hygiene second,
rationale third, self-consistency last.

| Level | Name | Gate (all lower gates + …) |
|---|---|---|
| L0 | Ad-hoc | default |
| L1 | Instructed | Foundation passes |
| L2 | Maintained | Hygiene passes |
| L3 | Explained | Why passes AND What passes |
| L4 | Self-consistent | In-code passes AND Sync passes |

**Gate formula (canonical definition lives in ADR 0012):** a group passes iff

```
deficit = evaluated_dims − points        # ✅=1.0, ⚠️=0.5, ❌=0; N/A excluded
passes  ⟺ deficit ≤ max(0.5, 0.2 × evaluated_dims)
```

For groups of ≥3 dimensions this is exactly the 80 % rule; the `max(0.5, …)`
floor keeps 2-dimension groups (Why, What, In-code) from demanding perfection —
they tolerate one ⚠️ but no ❌. Stated in points, not percentages, so nobody
recomputes a rounded percentage and disagrees with the gate.

A required group with **zero evaluated dimensions** (all N/A) **blocks** its
gate; the report says e.g. `L2 not assessable (Hygiene: all dimensions N/A)`.
No satisfied-by-absence escape hatch — an earlier draft had one and its
justification did not survive review.

The 0–100 score stays and its per-dimension unweighted sum is unchanged;
levels are a communication layer on top (management-facing), the score stays
the CI number. Note recorded in ADR 0012: appending dims 21–24 shifts the
score's internal weight toward Hygiene (6/20 → 10/24 of dimensions); accepted
and documented rather than re-weighted, to keep the score's arithmetic legible
(same call as ADR 0007's divisor change).

## Local history (replaces Factory's cloud dashboard)

Each full run appends one JSON line to
`$STATE_DIR/repo-doctor/<slug>.jsonl` — same state dir and shell-redirection
write pattern `/stack-check` already uses (`printf '%s\n' '<json>' >> file`,
never model-retyped file contents); never the repo, never the network, no
`origin` required. Record: `{"date","v","evaluated","score","groups","level"}`
— `v` (plugin version) and `evaluated` (score divisor) let the trend logic
annotate deltas that straddle a dimension-set change instead of presenting a
divisor artifact as progress. Slug is derived from the **canonicalized** repo
root path (same `canon()` approach as `skill-cheatsheet.sh`), so worktree/
symlink/case spellings don't fork the history. The report gains a one-line
**Trend** (`score 61 → 67 (+6) since 2026-07-12 · level L1 → L2`).
`--no-history` opts out; file capped at ~100 records.

## New presence dimensions (Layer 1) — adopt 4, reject 2

Adopted, appended as Hygiene dims 21–24 (no renumbering of 1–20). All four
share one explicit N/A predicate, defined once in the SKILL: *"no tracked
files matching the Dim 3 code-extension list → N/A"* (Dim 15's current
✅-on-empty is fixed to N/A in the same pass):

- **21 CI config present** — a CI pipeline is the agent's safety net.
- **22 `.env.example`** — agents need to know required config without secrets.
  N/A when the repo demonstrably reads no env config.
- **23 Reproducible dev environment** — devcontainer / nix / compose /
  tool-version pin; a lockfile alone counts as ✅-with-note (for most stacks a
  lockfile *is* the reproducibility story), not ⚠️.
- **24 Secret-hygiene guardrails** — only **repo-visible, machine-independent**
  mechanisms score ✅ (pre-commit scanner config, `.gitleaks.toml`, CI scanner
  job, in-tree `.githooks`). This stack's own `claude-leverage:` marker caps at
  ⚠️-with-note: it signals adoption, but hook enforcement is machine-local and
  not verifiable from the repo — scoring our own marker ✅ would be the same
  vendor self-preference this design criticizes Factory for.

Rejected from the external proposal:

- **CODEOWNERS** and **issue/PR templates** — GitHub team-process artifacts,
  weak AI-readiness signal, high N/A rate on solo/client repos, and pure
  Goodhart bait (an empty template passes any deterministic check). If demand
  appears, they can ride in a later batch.

**Anti-Goodhart companion doc:** `docs/repo-doctor-gaming.md` — one row per
dimension: how it's gamed, what counters it (or "residual risk accepted").
Linked from SKILL.md behind a when-to-read line rather than inlined (SKILL.md
is already ~510 lines; AGENTS.md's lean rule pushes topic depth to `docs/`).
This operationalizes the honest-history ethos: every metric documents its own
evasion.

## Semantic scope (Layer 2)

New subagent `agents/readiness-reviewer.md` (Sonnet, read-only — same pattern,
tool list, and prompt-injection defenses as `security-reviewer`), dispatched by
`/repo-doctor --semantic`. A dedicated flag, **not** a `--scope` value: it is
not a subset of the deterministic dimension set, and the flag surface should
mirror the ADR 0012 firewall (`--scope all` stays truthfully "all
deterministic dims"). Five judged dimensions:

- **S1 AGENTS.md actionability** — commands/conventions concrete and plausible
  (referenced files exist), not boilerplate.
- **S2 README truthfulness** — quickstart references resolve; claims match
  manifest/code (spot-check).
- **S3 ADR substance** — real decision + alternatives + consequences, not
  template placeholders.
- **S4 Instruction conflicts** — AGENTS.md vs CLAUDE.md vs per-dir vs
  `conventions.yml` contradictions.
- **S5 Glossary informativeness** — non-circular, non-TODO, matches code usage.

Output is a JSON schema (verdict pass/attention/fail + confidence + evidence
`file:line` + concrete fix), rendered as its own report section. Never enters
the 0–100 score or the level (ADR 0012). Requires the `Task` tool in
`/repo-doctor`'s `allowed-tools` (precedent: `/security-review`). **Codex
caveat, stated honestly in the SKILL's parity section:** subagent dispatch is
Claude-Code-shaped; in Codex, `--semantic` reports "unavailable" and the
deterministic scopes are unaffected.

## Dynamic scope (Layer 3) — designed, deferred

`--scope dynamic` executes the build/test/lint commands the repo *declares*
(AGENTS.md fenced blocks + README quickstart) and reports pass/fail/timeout per
command. Deferred because: it breaks the read-only contract (needs an explicit
carve-out), its safety story (denylist, timeouts, sandbox posture per tool) is
the hardest part, and Plans 1–2 deliver most of the value. Plan 3 records the
full design — including the decision that it ships as a **separate skill**, so
its broad Bash grant never lands in `/repo-doctor`'s frontmatter — so
implementation is a scheduling decision, not a design session. Trigger to
schedule it: first real case of "AGENTS.md declares commands that don't run"
slipping past the semantic scope.

## `--fix` mode

Thin orchestration, not remediation: `--fix [N]` steps through the top-N
recommended actions, asks per item, and invokes the mapped bootstrap skill
(`/init-repo`, `/arch-map`, `/glossary-init`, …) which carries its own
confirmation flow. The doctor itself still writes nothing in the repo. This is
deliberately *better* than Factory's single generic fix-agent: each gap maps to
a specialized, user-confirmed skill. Two honesty caveats from review: the
skill-invokes-skill mechanism has no in-repo precedent and must be verified in
a scratch run before Plan 1 commits to it — the specified fallback is printing
the exact slash command per item; and `--fix` is ignored with a warning in
non-interactive runs (`--score`, `--json`, CI).

## Non-goals

- No cloud storage, telemetry, or `origin` requirement — everything local.
- No canary-benchmark productization (stays in `bench/eval`).
- No auto-fix that writes repo files from within `/repo-doctor`.
- No level 5 / "autonomous" tier.
- No CODEOWNERS / issue-template dimensions (this round).
- No score re-weighting (per-dim unweighted sum stays; see levels section).

## Phasing

- **Plan 1 (v1.14.0):** ADR 0012 + dims 21–24 + `docs/repo-doctor-gaming.md`
  + levels + history/trend (`--no-history` opt-out) + `--fix` + SKILL
  consistency fixes surfaced by review (stale "~15 dimensions", missing
  `Bash(git log:*)`, `--scope` list normalization incl. `incode`/`sync`)
  + regex integrity tests. Purely deterministic, no new agents.
- **Plan 2 (v1.15.0):** `readiness-reviewer` subagent + `--semantic`
  + Codex parity artifacts and honest degradation.
- **Plan 3 (unscheduled):** dynamic validation as a separate skill, per
  recorded design.

## Maintenance artifacts touched (per `docs/maintaining.md`)

README what's-inside + dims counts (L104/L309 "~20 dimensions") + subagent
badge and counts (Plan 2), `skills/README.md`, `agents-docs/README.md`
(Plan 2), `workflows/onboarding-a-legacy-repo.md` (dims count, read-only
wording), `scripts/install-codex.sh` + `.ps1` uninstall hints (Plan 2),
CHANGELOG entries (incl. the scoring-weight note), version bump in both
plugin manifests + `gen-codex-plugin.py` regen, `gen-codex-agents.py` regen
(Plan 2), `pytest tests/`, `smoke-plugin.sh` before push.
