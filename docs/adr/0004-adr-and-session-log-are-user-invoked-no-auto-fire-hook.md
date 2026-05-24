# 0004. `/adr-new` and `/session-log` are user/agent-invoked, no auto-fire hook

**Date:** 2026-05-24
**Status:** accepted
**Deciders:** Filip Podstavec

## Context

v1.3.0 added two skills for the durable-memory layer: `/adr-new` (record
architectural decisions) and `/session-log` (distillate at session end).
The first question after they shipped was: should one or both auto-fire
via a hook so agents don't forget to invoke them?

The mechanical options for auto-firing in Claude Code:

- **`Stop` hook** — fires after every agent response. For `/session-log`,
  this is wrong: Stop ≠ "user is leaving"; it fires even on tiny
  back-and-forths. Auto-suggesting a session log on every response would
  be nag-grade noise.
- **`SessionStart` hook** — could surface "last session ended 3 days ago,
  do you want to write a log if you didn't?". But by SessionStart the
  previous session is already cold; can't reliably reconstruct what to
  log.
- **Diff-heuristic on Stop** — fire only if session shipped ≥3 commits
  AND no session log today. Better, but still wrong: the agent doesn't
  know whether the user is "done for the day" or "taking a 5-minute
  break before the next request."

For `/adr-new`, the trigger is even harder to detect: there's no
mechanical signal for "a load-bearing decision was just made in
conversation." The model knows; a hook does not.

## Decision

Neither `/adr-new` nor `/session-log` auto-fires. They are
user-invoked OR model-self-invoked based on skill description. The
discipline lives in three places:

1. **Trigger-aware skill descriptions** (USE WHEN ... / Do NOT use for
   ...) so the model picks the right moment when it sees a fitting
   signal in conversation.
2. **AGENTS.md** explicitly documents the convention in a "When to
   invoke /adr-new and /session-log" section, so the agent reads the
   discipline at session start.
3. **`claude-md-snippets/adr-session-log-discipline.md`** carries the
   same instruction into adopting repos via `/init-repo`.

The hook layer continues to cover what hooks reliably CAN detect
(secret in diff, dangerous git op, large net-new code without anchor,
30-day-stale stack check). Memory discipline is left to the human +
agent.

## Consequences

### Positive

- No nag-grade noise from a Stop hook that fires after every response.
- The "should I write an ADR?" question stays in the model's reasoning,
  where it belongs (only the model knows whether the conversation made
  a load-bearing decision).
- The convention is documented in three reinforcing places (skill
  description, AGENTS.md, snippet for adopting repos) so it's hard for
  the agent to miss.

### Negative

- Forgetful invocation is possible. Discipline-based, not enforced.
  Mitigated by: skill descriptions surfacing in Claude Code's skill
  resolver; AGENTS.md being the first thing the agent reads at session
  start; per-project AGENTS.md snippet making the convention visible
  in client projects too.
- If the model misjudges what counts as "load-bearing" or "substantial
  session," it'll either over-invoke (noise) or under-invoke
  (forgotten history). The "Do NOT use for" examples in skill
  descriptions are the calibration mechanism.

## Alternatives considered

- **Stop hook auto-firing `/session-log` when ≥3 commits + no log
  today** — rejected. Stop ≠ "user is leaving"; would fire mid-session.
- **SessionStart hook suggesting "did you write last session's log?"** —
  rejected. By SessionStart the previous context is already cold; the
  log would be hollow.
- **Slack-style `/wrapup` command** as the de-facto end-of-day trigger
  — would work in theory but breaks if the user has multiple
  consecutive sessions in a day (rare for Filip; common for shared
  team repos). User invocation is fine.

If a reliable "session has actually ended" signal appears in a future
Claude Code release (e.g., a `SessionEnd` hook with the proper
semantics), revisit this ADR.

## References

- v1.3.0 release: `aab6312`
- Inspiration: external AI conversation about 2026 AI-first dev
  practices (see session log `2026-05-24-ai-first-durable-memory.md`)
- Related: ADR 0003 (no-RAG, also a "trust the agent, don't try to
  pre-empt with infrastructure" decision)
