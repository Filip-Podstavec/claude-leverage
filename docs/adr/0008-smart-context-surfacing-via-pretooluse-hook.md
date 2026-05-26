---
status: accepted
date: 2026-05-26
deciders: Filip Podstavec
consulted: claude-leverage's own A/B test harness
informed: stack users
---

# 0008. Smart context surfacing via PreToolUse hook

## Context and Problem Statement

The leverage stack's per-session token tax — measured at **+116%** Sonnet 4.6
cost on a small helper-add task in the coinsense A/B Run-3 experiment — comes
primarily from the agent dutifully reading every leverage artifact (root
`AGENTS.md`, per-dir `AGENTS.md`, files containing `AIDEV-*` anchors)
**preemptively** at orientation time, regardless of whether those artifacts
are relevant to the current task.

Run-1 and Run-2 (endpoint task with the `limit` parameter trap) showed the tax
is worth paying when there's a documented gotcha to catch — the leverage stack
caught a real production bug. Run-3 (helper task without a specific trap)
showed the tax is pure overhead when there isn't.

How do we reduce the tax for non-trap tasks without losing the catch on
trap-bearing ones?

## Decision Drivers

- Tax should approach zero when no relevant context exists for a task.
- Catch rate for documented gotchas (the original value prop) must not drop —
  ideally rises, because surfacing becomes *forced* at the moment of edit
  rather than contingent on the agent choosing to read the right doc.
- Plugin must remain a graceful no-op for users who haven't adopted the
  anchor / `AGENTS.md` / ADR conventions.
- Must work cross-tool (Claude Code + Codex) without separate implementations
  of the actual logic.
- Adding latency on every `Read`/`Edit`/`Write` is dangerous — the agentic
  loop must not feel slower.

## Considered Options

1. **Slim root `AGENTS.md`** — fewer always-on tokens, but loses catches that
   depend on the agent reading conventions before editing.
2. **Skill-based on-demand loading** — agent invokes a skill to surface
   context. Friction; depends on agent volunteering.
3. **PreToolUse hook with manifest-backed lookup** — surface a per-file slice
   of context only when the agent actually touches a relevant file. **Selected.**
4. **Real-time grep in the hook** — same as 3 but without a manifest.
   Rejected on latency grounds: `grep -rn 'AIDEV-' .` on a 10K-file repo per
   tool call exceeds the latency budget.

## Decision Outcome

**Chosen: Option 3.**

A new `scripts/build-context-map.py` walks `git ls-files`, extracts every
`AIDEV-NOTE`/`TODO`/`QUESTION` anchor, and writes
`.claude-leverage-context-map.json` at the repo root. The file maps each
source path to:

- Anchors in the file
- Anchors in sibling files (same directory)
- The walking chain of `AGENTS.md` from `dirname(file)` to repo root
- ADR files that mention the path verbatim (word-boundary match)

A new `scripts/hooks/context-surface.sh` (`PreToolUse` on
`Read|Edit|Write|MultiEdit`) does an O(1) JSON lookup and emits a system
reminder via `hookSpecificOutput.additionalContext`. The hook is silent when
the manifest is missing or the file is unknown — repos that haven't adopted
the convention pay zero cost.

The hook defaults to **anchors-only** output. `CLAUDE_LEVERAGE_CTX_VERBOSE=1`
opts into surfacing the per-dir `AGENTS.md` chain and related ADRs too —
default-off because Run-3 showed those refs are taxed-without-catch in the
common case.

A `/refresh-context-map` skill lets the agent rebuild the manifest when
anchors / ADRs / per-dir docs change. `.gitattributes` adds `merge=ours` for
the manifest so a merge conflict on a 234-entry sorted JSON is never a
hand-resolve chore — keep local, then rebuild.

### Consequences

**Positive:**
- Per-session token tax for non-trap tasks should drop substantially because
  the agent no longer reads `AGENTS.md` preemptively for files it never touches.
- Trap-catch rate stays high — anchors are *forced* into context at the moment
  the agent reads the relevant file. No longer contingent on agent recall of
  `AGENTS.md`.
- Graceful no-op preserves backward compatibility — installing the v1.8.0
  plugin doesn't change behavior in repos without a manifest.
- One shell script serves both Claude Code and Codex thanks to identical
  `hookSpecificOutput.additionalContext` schema in both runtimes (verified in
  research stage of this work).
- AIDEV-NOTE convention gains real teeth — anchors are now load-bearing for
  the in-conversation surfacing, not just for grep.

**Negative:**
- Manifest must be rebuilt when anchors change. Pre-commit hook is the natural
  place; users without one will see stale context until they invoke
  `/refresh-context-map`.
- One more file in the repo root (`.claude-leverage-context-map.json`) for
  users to understand and not git-merge-conflict on.
- Per-tool-call latency adds Python cold-start (~80-150ms typical, up to
  ~300ms p99 on Windows) per `Read/Edit/Write`. Below perceptible threshold
  in interactive use but real.
- ADR cross-ref is word-boundary path match — substring `src/foo.py` in an
  ADR body marks the file as related. False positives still possible in
  prose; acceptable for v1.

## Validation

- The hook must catch the `limit` parameter trap from the coinsense
  experiment (Run-4 of the eval harness — pending).
- Per-session token cost on the helper task (Run-3 analog) should drop by
  at least 30% with no degradation in artifact quality.
- `pytest tests/test_context_surfacing.py` is the regression net (30 tests
  passing as of this ADR's acceptance).
- `bash scripts/smoke-plugin.sh` includes a new gate that runs
  `python scripts/build-context-map.py --check` so a forgotten rebuild
  surfaces in CI exactly the way version-sync drift does.

## References

- `docs/specs/2026-05-26-smart-context-surfacing/PLAN.md` — full implementation plan.
- `coinsense-ab/results/run1/` and `coinsense-ab/results/run2/` — Opus
  endpoint-task A/B data showing the `limit`-trap catch is reproducible with
  the leverage stack on.
- Run-3 evidence (the Sonnet helper-task result with the 116% cost overhead
  that motivated *this* design) lives in the user's Claude Code transcript
  history at `~/.claude/projects/C--Users-filip-Desktop-Python-coinsense-ab-{before,after}/`
  and is reviewable via `coinsense-ab/analyze-runs.py` against either transcript.
- Claude Code PreToolUse hook spec — <https://code.claude.com/docs/en/hooks>
- Codex PreToolUse hook spec — <https://developers.openai.com/codex/hooks>
