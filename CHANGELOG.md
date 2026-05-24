# Changelog

All notable changes to `claude-leverage` are recorded here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) +
[SemVer](https://semver.org/spec/v2.0.0.html).

## [1.3.1] — 2026-05-24

Discoverability follow-up to v1.3.0. The two new skills (`/adr-new`,
`/session-log`) shipped with descriptions that explained WHAT they did,
not WHEN to use them — meaning Claude Code's skill resolver wouldn't
auto-surface them at the right moment, and v1.3.0 was effectively just
two new commands users had to remember to type.

### Changed

- **`/adr-new` description** rewritten with explicit `USE WHEN ... / Do
  NOT use for ...` trigger pattern. Lists concrete examples that warrant
  an ADR (database choice, framework, auth model, explicit alternative
  rejection) and what to skip (variable naming, one-off fixes, lint
  conventions).
- **`/session-log` description** rewritten same way. Lists trigger
  signals the model should watch for in conversation (user says
  "thanks", "tomorrow", "wrap up"; 3+ commits with no log yet today; or
  explicit summary request) and what NOT to log (quick fixes,
  pure-exploration sessions).
- **`AGENTS.md`** gained a new "When to invoke `/adr-new` and
  `/session-log`" section in "Code conventions". Documents the
  invocation discipline explicitly so it's visible at session start,
  not buried in skill descriptions.

### Added

- **`docs/adr/0004-adr-and-session-log-are-user-invoked-no-auto-fire-hook.md`**
  — records the deliberate decision NOT to auto-fire either skill via a
  hook (Stop ≠ "user is leaving"; SessionStart is too late for the
  previous session's log; auto-detecting "load-bearing decision" from a
  shell hook is infeasible). Future agents proposing a Stop-hook
  variant will find the rationale here.
- **`claude-md-snippets/adr-session-log-discipline.md`** — new snippet
  that carries the convention into adopting projects via `/init-repo`,
  so agents in client repos also see the discipline at session start.
  Includes the recommended "reading order for new agents" so adopting
  projects get progressive-disclosure documentation without
  hand-authoring it.

### Fixed

- Plugin description in `marketplace.json` was still "8 on-demand
  skills" from v1.2.x; bumped to "10 on-demand skills" matching the
  shipped count.
- README install-verification block said `/skill list # confirm 8
  skills`; corrected to 10.
- `scripts/smoke-plugin.sh` skill-count check raised from `>= 8` to
  `>= 10` so a regression that loses a skill gets caught.

Plugin version → **1.3.1** (patch: discoverability fixes for v1.3.0
features + one new snippet + one new ADR; no breaking changes).

## [1.3.0] — 2026-05-24

The "durable memory" release. Adds ADR and session-log conventions plus
the two skills that make them low-friction to maintain.

### Added

- **`docs/adr/`** — Architecture Decision Records directory with MADR-
  flavored template, README index, and three seed ADRs documenting the
  most load-bearing decisions in this repo (the v1.0 pivot, the
  AGENTS.md-canonical pattern, the no-embedding-RAG choice). New
  decisions: `/adr-new`.
- **`docs/sessions/`** — Distilled session-log directory with template
  and convention README. Format: `YYYY-MM-DD-<topic>.md`. Distillate
  (context, what was done, key decisions, open questions, next steps),
  not transcript. New entries: `/session-log`.
- **`/adr-new`** skill — bootstraps a new numbered ADR. Picks next
  number, asks for title + context, fills MADR template, appends to
  index. Immutable status once accepted (`proposed` → `accepted` →
  `deprecated` / `superseded by NNNN`).
- **`/session-log`** skill — at end of a working session, distills the
  current conversation into a journal entry. Pulls branch + recent
  commits from git, model summarizes the chat. Hard cap on length
  (~80 lines) so it stays useful instead of becoming dead weight.
- **AI-specific recommendations section** in `templates/AGENTS.md.example`
  for projects that ship LLM-backed features: Langfuse/Helicone/Phoenix
  for LLM observability, Promptfoo or Langfuse evals for regression
  detection, hard cost caps before LLM calls (not inside), Pydantic/Zod
  for structured outputs, prompt-injection treatment of external data.
- **"Reading order for new agents"** section in both `AGENTS.md` and
  `templates/AGENTS.md.example`: 1) AGENTS.md, 2) docs/adr/, 3) last
  1–3 session logs, 4) specific specs on demand, 5) code via imports.
  Progressive disclosure as explicit policy.

### Changed

- Skill count: 8 → **10** (added `/adr-new`, `/session-log`).
- `templates/AGENTS.md.example` "Project" section now expects a concrete
  domain product description ("what + for whom"), not a generic
  one-liner.
- `templates/AGENTS.md.example` "Repo layout" template now includes the
  full `docs/` substructure (`adr/`, `sessions/`, `specs/`, `runbooks/`,
  `architecture/`, `conventions/`) as the recommended convention.
- `AGENTS.md` (this repo) lists 10 skills, references `/adr-new` and
  `/session-log` in maintenance rules.
- `workflows/maintaining-as-it-grows.md` extended with the "Skills you
  invoke per-decision and per-session (durable memory)" table, plus the
  maintenance-debt cycle diagram now includes the ADR + session-log
  steps.
- `CLAUDE.md` adapter notes how to invoke `/session-log` at session end.
- Plugin version bumped to **1.3.0** (new skills + new conventions; no
  breaking changes).

### Motivation

Inspired by an external conversation about AI-first dev practices that
called out three layers we were under-investing in:

1. **ADRs** as the durable record of *why* the architecture looks the
   way it does. Already had `docs/specs/` for specs; now also `docs/adr/`
   for the rationale layer, which is what stops a plausible-but-wrong
   refactor proposal from a future agent.
2. **Session logs** as the continuity layer between sessions. Without
   them, every session re-discovers context from cold. With them
   (distilled, not raw transcripts), the next agent reads the last 1–3
   logs and picks up the thread.
3. **Progressive-disclosure reading order** in AGENTS.md. The agent
   loads minimum context at session start; fetches deeper docs only when
   relevant. Explicitly documented now in both this repo and the
   template for adopting repos.

## [1.2.1] — 2026-05-24

### Added

- **Mission statement** in both `AGENTS.md` and `README.md` (above the
  "Project" / "What you get" sections). Makes the repo's actual goal —
  *help an AI dev ship secure and long-term-maintainable software for
  clients, working through Claude Code or Codex* — visible to anyone
  (or any agent) opening the repo for the first time. Three guiding
  properties enumerated: security by default, self-maintaining as the
  repo grows, cross-tool by design.
- **`workflows/security-first-feature.md`** — concrete end-to-end
  walkthrough of shipping a sensitive feature with the stack
  (`/init-repo` once → hooks fire passively → `/security-review`
  before commit → `/commit-smart` → `/explain-diff --for pr`).
  Documents what the workflow does and does NOT do for you.
- **`workflows/maintaining-as-it-grows.md`** — the "what the stack
  does automatically vs what I invoke" mental-model document.
  Includes the maintenance-debt cycle diagram (write code →
  ai-first-nudge → per-dir AGENTS.md nudge → security-nudge →
  AIDEV-TODO with deadline → stack-freshness → /stack-check → resolved
  debt) and the full table of tunable env vars per nudge.
- **`claude-md-snippets/security-review-routing.md`** — first actual
  routing snippet: promotes `/security-review` from "Stop hook might
  suggest it" to "project mandates it before commit" on diffs
  touching sensitive paths. Installable via `/init-repo`'s interactive
  flow.

### Changed

- Moved `docs/specs/2026-05-21-synthetic-benchmark-design.md` into
  `bench/archive-token-savings-thesis/` where it belongs (it's the
  design doc for the now-archived benchmark harness).
- `workflows/README.md` and `claude-md-snippets/README.md` updated to
  reflect the actual now-shipped content instead of "no content yet"
  placeholders.
- Plugin version bumped to **1.2.1** (cleanup + documentation, no
  breaking changes, no new skills).

## [1.2.0] — 2026-05-24

### Added

- **Plugin integrity tests** (`tests/test_plugin_integrity.py`):
  end-to-end validation that the shipped manifest references files that
  exist — catches "plugin install silently broke" before push. Adds a
  pytest job covering plugin.json + marketplace.json + hook path
  resolution + skill frontmatter + agent parity + stack.toml sanity.
- **`CHANGELOG.md`** (this file) — Keep-a-Changelog format for users
  running `/plugin update`.
- **Per-directory AGENTS.md nudge** in `scripts/hooks/ai-first-nudge.sh`
  — re-added with proper scoping (only fires inside detected source
  roots like `src/`, `lib/`, `app/`, `apps/`, `pkg/`, `internal/`,
  `services/`, `api/`, `cmd/`, `crates/`, `packages/`, plus monorepo-
  nested variants, AND inside a git repo, AND when the parent dir has
  8+ source files without an existing AGENTS.md in any ancestor —
  override via `CLAUDE_LEVERAGE_DIR_AGENTS_MIN`). The earlier version
  that fired on `/tmp` is fixed by this scoping.
- **AIDEV-TODO deadline syntax**:
  `AIDEV-TODO(by: 2026-08-01): description` is now supported by the
  convention. `/stack-check`'s anchor walk parses the deadline and
  flags overdue items differently from "old" items, so deadlines have
  teeth without manual chasing.

### Changed

- Statusline (`statusline/statusline-command.sh`): removed the trailing
  `$cost` estimate segment. The number was unclear without context
  (currency? which rate card?) and only correct against the Opus per-
  MTok rates. Formula preserved in the statusline README for users who
  want to add it back.
- README badges: removed the empty `[]()` link target on the Platform
  badge that was producing IDE warnings; now image-only.
- Plugin version bumped to **1.2.0** in `plugin.json` and
  `marketplace.json` (new features, no breaking changes).

### Fixed

- Nothing user-facing — the v1.1.1 review-loop fixes (regex foot-gun,
  rust template compile, atomic skills swap, etc.) shipped under
  v1.1.0 because the version wasn't bumped between them. This release
  is the first one with a real version-bump-per-feature-batch
  discipline going forward.

## [1.1.0] — 2026-05-24

### Added

- **Codex skills install**: `scripts/install-codex.sh` and `.ps1` copy
  `skills/*` to `~/.agents/skills/claude-leverage/`. All 8 skills now
  work in Codex sessions, not just Claude Code.
- **`/log-structured`** skill — audit non-structured logging in a
  codebase and suggest spec-compliant replacements per the JSON-lines
  convention.
- **`templates/logging/`** — drop-in starter kits for Python (stdlib
  logging + contextvars), TypeScript (pino + AsyncLocalStorage; native
  no-dep variant included), Go (slog + context), Rust (tracing +
  span-based trace context).
- **`/init-repo`** skill — bootstrap a fresh project with AGENTS.md
  from the per-language template, .gitignore patterns, optional
  logging template, interactive customization, idempotent via marker
  blocks.
- **AIDEV anchor age check** added to `/stack-check`: walks current
  repo for AIDEV-TODO / AIDEV-QUESTION, groups by age (fresh / aging /
  stale >90d), reports stale ones with file:line + last-modified date.
- **AGENTS.md sanity** added to `/stack-check`: file-size check vs
  Codex's 32 KiB cap, broken `@<path>` imports, possibly stale file
  references. Per-directory AGENTS.md files included.
- **Per-language dep graph** in `/repo-map` — opt-in second mermaid
  block via `madge` (JS/TS) or `pydeps` (Python). Skipped silently if
  neither tool is installed.
- **`/explain-diff`** skill — plain-English 3–5 bullet narration of the
  current diff in three audience modes (`--for pr / review / self`).
- **`/codex-sandbox`** skill — interactive helper for per-project
  `.codex/config.toml` sandbox + approval modes. Ships two profiles
  (`dev` / `prod`) plus `custom`.
- **`security-reviewer` extended** with `package.json` /
  `requirements.txt` / `pyproject.toml` / `go.mod` / `Cargo.toml` /
  `Gemfile` deps diff scan: flags typosquatting heuristics (1-char
  distance from popular names) at Important tier, suspicious version
  pins at Nice tier. Out-of-scope section now lists concrete SCA
  commands per ecosystem.
- **Per-OS `update_hint`** fields in `stack.toml` (`update_hint_macos`,
  `update_hint_linux`, `update_hint_windows`) — `manifest_version`
  bumped 1 → 2.
- **`gen-codex-agents.py --dry-run`** — prints WOULD CREATE /
  WOULD UPDATE per file with a unified diff, writes nothing.
- **`templates/AGENTS.md.example`** — per-language Build/test sections
  (Python, TypeScript/Node, Go, Rust) with toolchain-specific
  footguns documented inline.

### Removed

- **`/leverage-stats` slash command** and **`track-delegations.sh` hook**
  — observability over the tracking log no longer fits the personal-
  dev-stack framing.
- **`scripts/hooks/leverage_stats_agg.py`** and its tests — paired
  with the removed hook.
- **`/install-snippets` slash command** — bootstrapping a project is
  now handled by `/init-repo` interactively.
- **`plans/` empty directory** — cruft.

### Fixed

- `scripts/install-codex.sh`: replaced `sed` delimiter substitution
  with `Python str.replace` (sed silently corrupted `~/.codex/hooks.json`
  when REPO_DIR contained `#`).
- `scripts/install-codex.ps1`: replaced PowerShell `-replace` (regex,
  unsafe with `$` in paths) with a Python `str.replace` call mirroring
  the bash variant.
- `scripts/install-codex.sh` skills install: atomic staging-dir swap so
  a copy failure mid-loop doesn't leave users with zero skills.
- `scripts/install-codex.sh` previously had a glob-empty foot-gun on
  `.codex/agents/` — now uses explicit per-file existence check.
- `scripts/hooks/security-nudge.sh`: switched from concatenating
  `git diff --cached` + `git diff` (which double-counted lines in
  partially-staged files) to `git diff HEAD`, which is exactly "working
  tree vs HEAD" without double-counting.
- `scripts/hooks/ai-first-nudge.sh` MultiEdit branch: replaced the
  JSON-blob line counter with a Python pass over `edits[*].new_string`,
  fixing inflated counts that triggered spurious nudges on small
  MultiEdit operations.
- `scripts/hooks/stack-freshness.sh`: defensive guard on `date +%s` for
  strictly POSIX systems.
- `scripts/gen-codex-agents.py`: raise `ValueError` when frontmatter
  has no `tools` field (was silently defaulting to read-only sandbox).
- `templates/logging/rust.md`: added `chrono` feature to the
  `tracing-subscriber` dependency, replaced the broken custom
  `WithService` layer (dead RUST_LOG binding + no-op `on_event`) with
  the actually-working span-based approach.
- `templates/logging/typescript.md`: added `base: null` to pino options
  so the formatter-controlled string `level` is the only level field
  in output (was emitting both numeric and string).
- `skills/codex-sandbox/SKILL.md`: dropped the false "staging" profile
  audit-logging claim (no such Codex config field exists).
- `skills/init-repo/SKILL.md`: documented `--allow-non-git` tunable
  for the opt-in path the previous hard rule referenced but didn't
  define.

### Maintenance

- CI: added `codex-agents-parity` job running `gen-codex-agents.py
  --check`. Catches drift between `agents/*.md` and
  `.codex/agents/*.toml` automatically.
- Plugin description deliberately drops the literal word `superpowers`
  from both `plugin.json` and `marketplace.json` to avoid keyword
  collision with the unrelated `obra/superpowers-marketplace` plugin
  that this stack complements (does not replace).

## [1.0.0] — 2026-05-24

The pivot release. Starts the version line over after the v0.x token-
savings experiment was disproven by the in-repo benchmark series.

### Added

- **Personal Claude Code + Codex dev stack** framing (was: tier-routing
  for token savings).
- **`AGENTS.md`** as canonical guidance; **`CLAUDE.md`** as one-line
  `@AGENTS.md` import; same content for both tools.
- **AIDEV-NOTE / AIDEV-TODO / AIDEV-QUESTION** anchor convention,
  enforced by `ai-first-nudge` PostToolUse hook.
- **Structured JSON-lines logging spec** (documented in AGENTS.md;
  templates land in 1.1.0).
- **`/security-review`** skill + read-only `security-reviewer` Sonnet
  subagent.
- **`/repo-map` and `/process-diagram`** skills for mermaid generation
  with idempotent markers.
- **`/stack-check`** skill + 30-day `stack-freshness` SessionStart hook
  (network-free; local timestamp only).
- **Portable statusline** — Python-based, no `jq` dep, Windows-friendly.
- **Codex parity layer**: `.codex/agents/*.toml` generated from
  `agents/*.md` via `scripts/gen-codex-agents.py`; `scripts/install-codex.sh`
  (+ `.ps1`) replaces the missing plugin marketplace.
- **`templates/AGENTS.md.example`** — generic AGENTS.md drop-in
  (per-language sections added in 1.1.0).

### Kept

- **Security hooks**: `block-secrets-precommit`, `block-dangerous-git`.
  Validated by benchmark as net-positive on every axis.
- **`/commit-smart`**: all-inline, with hard rules (refuse `.env`,
  never force push, never `--no-verify`).
- **`flaky-test-isolator`** subagent: only v0.x agent that survived the
  non-cost-based scrutiny (statistical signal across N runs).

### Removed (archived)

- 11 retired subagents from v0.x (`code-reviewer`, `test-runner`,
  `context-gatherer`, `repo-explorer`, `research-agent`, `docs-updater`,
  `git-committer{,-quick}`, `output-digester`, `impact-mapper`,
  `focused-reviewer`). Frozen in `bench/archive-token-savings-thesis/agents/`
  with tombstone links to benchmark verdicts.
- 4 retired wrapper commands. Same archive.
- 5 retired CLAUDE.md routing snippets. Same archive.
- The benchmark harness itself moved to
  `bench/archive-token-savings-thesis/{fixtures,harness,results}/`
  with a framing README.
- `extras/` directory entirely.
