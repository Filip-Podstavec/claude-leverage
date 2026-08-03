# 0013. `/dynamic-check`: separate skill, layered consent for executing declared commands

**Date:** 2026-08-02
**Status:** accepted
**Deciders:** Filip Podstavec

## Context

The readiness methodology (ADR 0012) leaves one question no read-only layer
can answer: do the build/test/lint commands a repo *declares* (AGENTS.md,
README quickstart) actually run? Answering it means executing repo-declared
commands — arbitrary code execution by indirection (`make setup` can run
anything through scripts no denylist sees). ADR 0012 (f) reserved the
carve-out; this ADR fixes the contract. Load-bearing facts verified against
official Claude Code docs (2026-08-02): skill `allowed-tools` is an
**expansion, not a whitelist** — unlisted tools remain callable under the
session's normal permission flow; the grant is **per-turn scoped** (clears on
the next user message); plain `Bash` ≡ `Bash(*)` pre-approves everything.
`AskUserQuestion` behavior in headless (`-p`) runs is undocumented.

## Decision

1. **Separate skill, never a `/repo-doctor` scope.** `/dynamic-check` ships
   with its own frontmatter. A broad Bash grant must not sit in an
   always-active audit skill gated only by prose — prose cannot gate
   frontmatter permissions. This deliberately reverses ADR 0007's "one audit
   command" argument for this one layer; `/repo-doctor` only cross-references
   the skill.
2. **No broad Bash pre-approval.** The frontmatter pre-approves only
   read-only helpers (`git rev-parse`). Every declared command rides the
   platform's normal permission prompt — per-command consent enforced by the
   platform, not by model self-restraint. Per-turn scoping means nothing
   leaks into the rest of the session.
3. **Declared commands only.** Sources: fenced code blocks under
   build/test/lint/quickstart-shaped headings in root `AGENTS.md`, then
   `README.md`. Nothing inferred from manifests, nothing synthesized, every
   command attributed to `file:line`.
4. **Layered consent, fail-closed.** Four independent layers: (a) sourcing
   (what *can* run), (b) non-skippable preview + explicit batch confirmation
   with per-command exclusion (what the user *lets* run), (c) denylist
   tripwire (what never runs, even confirmed), (d) platform
   permissions/sandbox (what the environment allows). Because headless
   `AskUserQuestion` behavior is undocumented, the contract is written to
   **not depend on it**: in every branch, absence of an explicit affirmative
   user answer means the skill prints the parsed command table, states
   nothing was executed, and exits 0. Silence never executes.
5. **Advisory only.** Results render in the skill's own report and exit code
   (`--fail-on fail` → exit 4); `/repo-doctor`'s deterministic score and
   levels never consume them (ADR 0012).
6. **Codex posture:** commands run under the configured sandbox profile;
   recommend `workspace-write` with network off (see `/codex-sandbox`)
   unless installs are being validated.

## Consequences

### Positive

- The riskiest capability in the plugin requires an explicit, dedicated
  invocation — nobody gets command execution as a side effect of an audit.
- Consent survives hostile conditions: in `bypassPermissions` /
  full-auto runs, layers (b) and (c) still stand; in an interactive session
  all four do.
- The denylist is honestly labeled a tripwire, not a sandbox — the
  indirection gap is documented where users will read it.

### Negative

- Two commands to learn (`/repo-doctor` + `/dynamic-check`) where Factory
  has one — the price of not holding a broad grant open permanently.
- Interactive friction: un-allowlisted commands prompt one by one. That
  friction *is* the consent mechanism; accepted.
- A user can still confirm a malicious declared command in a hostile repo.
  The preview (source `file:line` per command) makes that decision informed;
  it cannot make it for them — same trust boundary as typing the quickstart
  by hand.

## Alternatives considered

- **`--scope dynamic` on `/repo-doctor`** — rejected per ADR 0012 (f).
- **Pre-approving `Bash(*)` in the skill frontmatter** — rejected: removes
  the platform prompt layer, and per official docs plain `Bash` approves
  everything for the turn.
- **Auto-discovering commands from manifests** (`package.json` scripts,
  Makefile targets) — rejected for v1: widens the surface beyond what the
  repo declares *to humans*, and the audit question is "do the documented
  commands work", not "do all commands work".
- **Skipping the confirm step when the platform will prompt anyway** —
  rejected: prompts are absent in bypass/full-auto runs, and the batch
  preview (with source attribution) carries information a per-command
  prompt does not.

## References

- Official docs (verified 2026-08-02):
  code.claude.com/docs/en/skills.md §Pre-approve tools for a skill,
  §Skill content lifecycle; permissions.md §Permission rule syntax;
  permission-modes.md §bypassPermissions.
- Plan: `docs/specs/2026-08-01-readiness-plan-3-dynamic-scope.md`.
- Related ADRs: 0012 (reserved this carve-out; advisory-halo contract),
  0007 (the "one audit command" argument this ADR knowingly reverses for
  execution), 0006 (folded-scalar description convention).
