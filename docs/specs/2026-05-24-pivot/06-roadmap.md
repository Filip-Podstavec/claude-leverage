# 06 — Implementation roadmap

## Shape

The pivot ships as `v1.0.0`. The roadmap is **five phases**, each ending
with a working state and a commit that could itself be a release. Phase 0
is the destructive cleanup; phases 1-4 are additive.

Each phase has a rough effort estimate assuming Filip + Claude pair on it,
no parallel work; one focused half-day = one chunk. These are time-to-
working-commits, not time-to-polish.

## Phase 0 — Cleanup & pivot framing (½–1 day)

Goal: repo no longer claims to save tokens. Bench archived. New
plugin metadata in place. Layout ready for skills.

- Move `bench/` content into `bench/archive-token-savings-thesis/` and
  write the framing `README.md` there.
- Archive retired `extras/agents/*.md` into
  `bench/archive-token-savings-thesis/agents/` with one-line tombstones
  pointing at the benchmark verdict.
- Rewrite top-level `README.md`. New top-of-file framing; "Honest
  history" section at the bottom linking to bench archive.
- Bump `plugin.json` / `marketplace.json` to `1.0.0`, update
  description and keywords (per `01-architecture.md`).
- Replace stale `AGENTS.md` (currently a bad-search-and-replace copy
  of CLAUDE.md) with the new canonical AGENTS.md.
- Make `CLAUDE.md` a one-line `@AGENTS.md` import + Claude-only block
  (per `01-architecture.md`).
- Move existing `hooks/*.sh` to `scripts/hooks/`. Update
  `hooks/hooks.json` paths.
- Create `.codex/config.toml` and `.codex/hooks.json` mirroring the
  Claude hook config.
- Create `scripts/install-codex.sh` and `scripts/install-codex.ps1` —
  Codex equivalent of `/plugin install` (copies `.codex/` into
  `~/.codex/`, appends `@<install-path>/AGENTS.md` reference).
- Add **"Install for Codex"** section to top-level `README.md`
  alongside "Install for Claude Code". Both sections at the same
  visual weight; document `scripts/install-codex.sh` and the
  prerequisite `npm i -g @openai/codex`.
- Empty out `extras/` (or remove the directory entirely; check no
  marketplace consumers expect it).

**Commit:** `chore(v1.0.0): pivot to personal dev stack, bench archived, dual Claude+Codex layout`.

## Phase 1 — Statusline + AI-first conventions (1 day)

Goal: the conventions that need to exist before any new skill ships are
documented and lightly enforced.

- Copy `~/.claude/statusline-command.sh` into `statusline/` and
  document install in its README.
- Extend `/install-snippets` to optionally install the statusline.
- Document AIDEV-NOTE / AIDEV-TODO / AIDEV-QUESTION convention in
  `AGENTS.md` (the "Code conventions" section).
- Document structured JSON-lines logging spec in `AGENTS.md`.
- Document per-directory AGENTS.md template + when to add one.
- Add `scripts/hooks/ai-first-nudge.sh` (PostToolUse on
  `Write|Edit|MultiEdit`, the LOC + anchor + module check from
  `03-ai-first-code.md`).
- Wire the new hook in `hooks/hooks.json` and `.codex/hooks.json`.

**Commit:** `feat(v1.1.0): statusline + AI-first conventions + ai-first-nudge hook`.

## Phase 2 — Security review skill (1 day)

- Create `agents/security-reviewer.md` (Sonnet, read-only).
- Generate `.codex/agents/security-reviewer.toml` from it.
- Create `skills/security-review/SKILL.md` with the report-shape
  contract from `02-security-first.md`.
- Add `scripts/hooks/security-nudge.sh` (Stop hook, LOC + sensitive-path
  threshold).
- Wire in `hooks/hooks.json` and `.codex/hooks.json`.
- Test on a real diff in this repo (the cleanup commits make a fine
  fixture; the script should NOT find anything Critical).

**Commit:** `feat(v1.2.0): /security-review skill + security-reviewer subagent + Stop nudge`.

## Phase 3 — Visualization skills (1–1½ days)

- Create `skills/repo-map/SKILL.md`. Walker + mermaid emitter +
  marker insertion. Optional `mmdc` validation loop.
- Create `skills/process-diagram/SKILL.md`. Generator with retry loop
  on `mmdc` errors.
- Update `skills/docs-sync/SKILL.md` (migrated from `extras/`) to flag
  stale architecture diagrams.
- Run `/repo-map` against this repo as dogfooding; commit the
  generated mermaid block in README.

**Commit:** `feat(v1.3.0): /repo-map and /process-diagram skills`.

## Phase 4 — Stack freshness (½–1 day)

- Create `stack.toml` with current dep versions.
- Create `scripts/hooks/stack-freshness.sh` (SessionStart, local-only).
- Create `skills/stack-check/SKILL.md`.
- Wire SessionStart hook in `hooks/hooks.json` and `.codex/hooks.json`.
- Smoke test by `touch -d '2 months ago' ~/.claude/claude-leverage/.last-stack-check`
  and starting a new session — nudge should fire.
- Run `/stack-check`, confirm clock resets.

**Commit:** `feat(v1.4.0): stack-freshness hook + /stack-check skill`.

## Out of phases — ongoing maintenance

- **Codex parity script** (`scripts/sync-codex-skills.sh` and
  `scripts/gen-codex-agents.py`) run by `/install-snippets` and in CI.
  Build incrementally as Phase 2-3 land actual skills/agents.
- **CI** updates: existing CI runs hook tests; add a job that runs
  `python scripts/gen-codex-agents.py --check` and fails on drift, and
  one that runs `mmdc -i README.md` if Node is available to catch
  syntax errors in repo-map output.
- **Per-repo AGENTS.md template** as `templates/AGENTS.md.example` —
  documented in the new top-level README. v1.1 candidate; not blocking
  for v1.0.

## Total effort estimate

Honestly: **4–5 focused half-days** to ship v1.0.0 end-to-end if Filip
and Claude are working together and not getting distracted. Calendar
time more realistic at ~2 weeks of evenings.

## What ships first if time-boxed to one weekend

If only one weekend is available: **Phase 0 + Phase 1**. That gets the
repo honestly reframed, the AGENTS.md / CLAUDE.md story right, the
statusline portable, and the AI-first conventions documented + lightly
enforced. Everything else can ship as 1.x patches without re-pivoting.

## Open questions for review

1. **Phase ordering.** I put visualization before stack-freshness
   because /repo-map produces a visible artifact on day one. Alternative:
   stack-freshness first because it's smaller. Recommendation: keep
   as-is unless the user has a usage preference.
2. **Version numbering.** I propose 1.0.0 for the pivot baseline, then
   1.x.0 minor bumps per phase. Alternative: ship all phases as 1.0.0
   and tag intermediate states. Recommendation: ship as separate minor
   bumps — keeps CHANGELOG honest, lets Filip roll back to a known
   good phase if something regresses.
3. **Should we keep the `extras/` directory** as a public "graveyard"
   pointing at the bench verdicts, or fully remove? I lean toward
   removing — the bench archive already tells that story; an empty or
   tombstone-filled `extras/` is just clutter.
