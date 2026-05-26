# 0006. `/repo-doctor` skill, folded-scalar SKILL descriptions, and gated skill-cheatsheet hook

**Date:** 2026-05-26
**Status:** accepted
**Deciders:** Filip Podstavec

## Context

Three observations converged on the same root issue: **the plugin's
skills are present but under-used in normal development.**

1. **Discoverability gap.** When a developer (or agent) lands in a
   legacy repo and asks "what's missing for AI-first work?", the
   answer is currently a manual mental walkthrough of ~15 dimensions
   (AGENTS.md, ADRs, sessions, glossary, architecture.yml, AIDEV
   density, tests, structured logging, …). `/init-repo` bootstraps,
   `/stack-check` flags staleness in *existing* artifacts — neither
   answers the completeness question.

2. **SKILL auto-activation is partly broken in the 2026 Claude Code
   runtime.** From multiple field reports (agentengineermaster.com,
   scottspence.com, dev.to): a multi-line `description: |` block
   scalar can have the auto-activation trigger silently stripped — the
   runtime treats only the first line as the matchable trigger in
   roughly 40% of failing cases. Slash invocation (`/<name>`) still
   works; the model's *autonomous* recall of the skill at the right
   moment does not. Our 12 (now 13) skills all used `description: |`.

3. **Session-start awareness.** Skills are listed in the plugin
   manifest but not surfaced in the model's working context on a new
   session unless the model decides to enumerate them. A periodic,
   gated nudge would lift recall without flooding every session with
   marketing copy.

## Decision

We ship three additions in v1.6.0, designed as one coherent
discoverability layer:

1. **`/repo-doctor` skill** — read-only AI-readiness audit. Scores
   ~15 dimensions across Foundation (AGENTS.md, CLAUDE.md, per-dir
   AGENTS.md), Why (ADRs, session logs), What (GLOSSARY.md,
   architecture.yml), In-code (AIDEV anchor density, overdue
   anchors), and Hygiene (tests present, test-to-source LOC ratio,
   structured logging, .gitignore patterns, README quickstart). Each
   gap → concrete fix action (often "invoke /X"). Output is Markdown
   with a `--score` (0–100), `--json`, `--fail-on missing|todo|stale`
   for CI, and `--scope foundation|why|what|hygiene|all` for
   focusing.

2. **All SKILL.md descriptions converted from `|` (literal block
   scalar) to `>` (folded block scalar).** The folded scalar joins
   wrapped lines with spaces, producing a single-string description
   with no internal `\n`. This sidesteps the "runtime parses only
   the first line" failure mode entirely — the entire description
   *is* the first line. Mechanical change across all 13 skills
   (the 12 that existed at the start of v1.6.0 — themselves the 10 in
   v1.4.5 plus `/glossary-init` and `/arch-map` from v1.5.0 — plus
   the newly-added `/repo-doctor`).

3. **`skill-cheatsheet.sh` SessionStart hook** — gated, rate-limited
   nudge listing the high-value skills + their reminders. Fires only
   when:
   - cwd is interesting (not `$HOME`, `/tmp`, `/etc`, system roots),
     AND
   - cwd is inside a git repo with `claude-leverage:` marker in
     `AGENTS.md` (i.e., user has actively adopted this stack — no
     unsolicited nudge in repos that never opted in), AND
   - state file shows last cheatsheet >14 days ago (override via
     `CLAUDE_LEVERAGE_SKILL_HINT_DAYS`, `=0` disables entirely).

## Consequences

### Positive

- **`/repo-doctor` answers the question prose AGENTS.md doesn't
  cheaply answer per session:** "what's missing?". Differentiated
  cleanly from `/init-repo` (one-shot bootstrap, writes files) and
  `/stack-check` (freshness of existing artifacts).
- **Folded-scalar fix is mechanical, atomic, and reversible.** No
  semantic change to the description content; only the YAML
  representation changes. If the matcher behavior turns out to be
  insensitive to this, the fix is still a no-op (just slightly more
  whitespace-normalized descriptions).
- **The cheatsheet hook is gated tight enough to not be spam.** Only
  fires in repos that have adopted the stack; rate-limited to ~26×
  per year max per repo; one-line via SessionStart
  `additionalContext`. Easy opt-out via env var.
- **All three additions are read-only or non-blocking.** No new
  attack surface, no new failure mode that can break a commit.

### Negative

- **One more skill (13 total) to teach users about.** Mitigated by:
  the cheatsheet hook is itself the discoverability vehicle.
- **Folded-scalar is empirically motivated but not empirically
  verified in our environment.** We can't easily A/B-test
  auto-activation rate. We're trusting the published field reports
  and trading a near-zero implementation cost for a hypothesised
  recall lift.
- **The cheatsheet adds one more SessionStart hook script.** Three
  SessionStart hooks now (stack-freshness, bare-repo-nudge,
  skill-cheatsheet). Each is fast and silent on the happy path; the
  combined budget on session open is still < 100ms on a warm cache.
- **`/repo-doctor` reports may grow stale if the user adopts the
  stack mid-project and then doesn't follow through.** This is true
  of every audit tool; the report is advisory, not load-bearing.

## Alternatives considered

- **Merge `/repo-doctor` into `/stack-check`.** Rejected. Audiences
  are different: `/stack-check` is the daily/weekly health pulse for
  a repo you actively work in (freshness, staleness); `/repo-doctor`
  is the "I just inherited this — what's missing?" one-shot. Keeping
  them separate keeps each tightly scoped.
- **Auto-fire `/repo-doctor` from a SessionStart hook on
  first-session-in-repo.** Rejected — too noisy. The
  bare-repo-nudge already handles the "no AGENTS.md at all" case;
  for repos with AGENTS.md but gaps, the cheatsheet hook is the
  lighter touch. Users invoke `/repo-doctor` when they want the
  audit.
- **Move all SKILL descriptions to single-line `description: "..."`.**
  Rejected. Single-line forces an unwieldy 200–500 char string in
  YAML; folded scalar preserves wrapped readability in source while
  yielding a single-string runtime value.
- **Mandatory-skill-activation hook (gist pattern: a PreUserMessage
  hook that lists all skills before each user turn).** Rejected as
  over-engineering — adds a per-turn token tax for a discoverability
  problem solved cheaper by the SessionStart cheatsheet.
- **Per-module skills (with `paths:` glob restriction).** Out of
  scope per ADR 0005's note — AGENTS.md-per-folder + architecture.yml
  + GLOSSARY.md already cover the per-module discoverability case
  with lower maintenance cost.

## References

- agentengineermaster.com, *Skill Auto-Activation Broken*:
  <https://agentengineermaster.com/skills/skill-auto-activation-broken-why-your-claude-code-skill-works-via-slash-command-but-never-fires-automatically>
- scottspence.com, *Claude Code Skills Don't Auto-Activate*:
  <https://scottspence.com/posts/claude-code-skills-dont-auto-activate>
- heyferrante.com, *AI-Enabled Repository Checklist (March 2026)*:
  <https://heyferrante.com/ai-enabled-repository-checklist> — the 7-item
  list from this article informed `/repo-doctor`'s dimensions.
- Count.co, *Repository Health Score*:
  <https://count.co/metric/repository-health-score> — test-to-source LOC
  ratio target 0.5–1.0 used in the Hygiene section.
- Related ADRs: 0002 (AGENTS.md canonical), 0004 (user-invoked, no
  auto-fire), 0005 (structured discoverability layer). This ADR
  continues the same arc: additive, gated, read-only.
