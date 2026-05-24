# Session: v1.3.0 — durable memory layer (ADR + session log conventions)

**Date:** 2026-05-24
**Branch:** main
**Participants:** Filip, Claude Opus 4.7
**Duration:** ~1 hour

## Context

Repo was at v1.2.1 after a long pivot + extension cycle (v0.x → v1.2.1
across 18 commits, see CHANGELOG). Filip surfaced a conversation he'd
had with another AI about AI-first dev practices in 2026, specifically
calling out three things missing from our stack:

1. **ADR convention** (Architecture Decision Records) — "nejdůležitější"
   per the source conversation, and we had `docs/specs/` but no
   immutable, numbered, MADR-flavored ADR layer.
2. **Session logs** (`docs/sessions/`) — continuity between AI sessions;
   distillate of "what was done + decided + open" rather than raw
   transcript. The agent writes one at end of session; the next agent
   reads it to pick up the thread.
3. **`/docs/` structure** in the AGENTS.md template — agents in adopting
   repos had no guidance on what kind of doc belongs where (specs vs
   adrs vs runbooks vs architecture vs sessions vs conventions).

Plus broader inspiration on LLM observability (Langfuse / Helicone /
Promptfoo evals), hard cost caps, and structured outputs (Pydantic/Zod)
— all relevant for the AI-first projects we'd be helping clients build.

## What was done

- New `docs/adr/` directory: MADR-flavored template, README index, and
  three seed ADRs documenting our most load-bearing decisions:
  - [0001](../adr/0001-pivot-from-token-savings-to-dev-stack.md) — the pivot
  - [0002](../adr/0002-agents-md-canonical-claude-md-import.md) — AGENTS.md canonical
  - [0003](../adr/0003-no-embedding-rag-hybrid-manifest-and-grep.md) — no RAG
- New `docs/sessions/` directory: README + template + this very file.
- New `/adr-new` skill: bootstraps numbered ADRs, immutable status,
  auto-updates index.
- New `/session-log` skill: distills current conversation into a journal
  entry; hard cap on length so it stays useful.
- `templates/AGENTS.md.example` gained:
  - "Reading order for new agents" section (progressive disclosure as
    explicit policy)
  - Expanded `docs/` substructure (adr, sessions, specs, runbooks,
    architecture, conventions)
  - New "AI-specific" section for projects that ship LLM features
    (Langfuse, Promptfoo, hard cost caps, Pydantic/Zod)
- Plugin-repo `AGENTS.md` got the same reading-order section + updated
  layout listing.
- Skill count 8 → 10; CHANGELOG written; version → 1.3.0.

## Key decisions

- **`/adr-new` and `/session-log` ship as skills, not as commands.**
  Skills are cross-tool (Claude + Codex); commands are Claude-only.
  Both belong in the on-demand surface alongside the existing 8 skills.
- **Seed ADRs are real, not placeholders.** Documenting the pivot,
  AGENTS.md choice, and no-RAG choice gives future agents
  load-bearing context AND demonstrates the format. The user can
  always add more.
- **Session logs are distillate, never transcript.** The skill enforces
  this via hard cap on length + "next agent's purpose" framing. No
  raw chat dumps.
- **LLM-specific guidance is a separate AGENTS.md template section** —
  optional, delete-if-not-relevant. Avoids polluting non-AI projects
  with Langfuse mentions they don't need.

## Open questions

- Should `/session-log` AUTO-fire at session end via a hook (Stop hook
  variant), or stay user-invoked? Auto-firing risks low-quality logs;
  user-invoked risks forgotten logs. Leaving as user-invoked for v1.3.
  Will revisit if pattern matures.
- Should we ship a `/adr-list` or `/adr-status` skill for "show me all
  proposed ADRs that need accepting"? Likely not — the index README +
  `ls docs/adr/` is sufficient at this scale.
- The "AI-specific" section in the AGENTS.md template currently
  recommends Langfuse generically. As projects accumulate experience,
  we may want a more opinionated default (e.g., "use Langfuse self-
  hosted; here's the docker-compose").

## Next steps

- (User) Push v1.3.0 to remote when ready. `git push origin main`.
- (Next session) When using the stack on a real client project, dogfood
  `/init-repo` + `/adr-new` + `/session-log` end-to-end and surface any
  rough edges as ADRs or workflow guides.
- (Possible v1.4) Codex-side `MaintenanceDigest` SessionStart hook that
  surfaces the last 1–2 session logs to the agent on every new session.
  Skipped in v1.3 because Codex's hook payload shape for SessionStart
  may not give us what we need without per-tool customization.

## References

- Commits shipping this session: `608a3d9` (v1.2.1 cleanup) →
  current HEAD (v1.3.0).
- ADRs created: 0001, 0002, 0003 (seed set).
- CHANGELOG: `## [1.3.0] — 2026-05-24` section.
- Inspiration: external AI conversation about 2026 AI-first dev
  practices (private, not linked).

---

*Distillate, not transcript. This session covered ~1h of work; the raw
chat ran much longer. The above is the load-bearing 60 lines the next
agent needs to orient.*
