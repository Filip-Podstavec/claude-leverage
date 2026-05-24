# 00 — Vision & scope

## The pivot in one sentence

`claude-leverage` stops claiming to save tokens (it doesn't, per `bench/`) and
becomes **Filip's personal Claude Code + Codex dev stack**: a curated set
of skills, hooks, agents, and conventions that make Filip productive in
both tools, security-conscious by default, and produce code that other
agents can read fluently. Designed to **complement** skills-based
plugins like the official `superpowers` plugin (Filip uses both); does
not try to replace them.

## What stays the same

- **Repo name.** `claude-leverage`. Per user instruction, keep the name; the
  honest history of the failed savings thesis is part of the story.
- **Repo visibility.** Public on GitHub. Commits stay — including the benchmark
  series that disproved the original thesis. This is a credibility asset, not
  a liability.
- **Plugin marketplace machinery.** `.claude-plugin/marketplace.json` and
  `plugin.json` stay so Filip can install the same stack across machines via
  `/plugin install claude-leverage@filip-podstavec`, and so any developer who
  finds it useful can fork it. This is "private collection, public surface".
- **Security hooks.** `block-secrets-precommit`, `block-dangerous-git`,
  `track-delegations` keep working. They are the one component the benchmark
  validated as net-positive on every axis.
- **`/commit-smart`** as an inline commit command. The benchmark made the
  routing decision (inline beats dispatch); the command itself stays.

## What changes

- **Plugin description** in `plugin.json` and `marketplace.json` rewrites to
  reflect the new framing. Keywords lose `model-routing`/`haiku`/`sonnet`;
  gain `ai-first`, `codex`, `security-review`, `repo-map`,
  `agents-md`, `stack-freshness`. (Deliberately no `superpowers`
  keyword — that's the unrelated `obra/superpowers-marketplace` plugin
  that Filip uses alongside this stack.)
- **README** rewrites top-down. Lead with what the stack does for the
  developer, not with cost claims. Bench data moves into a "Honest history"
  section that links to `bench/archive-token-savings-thesis/`.
- **`bench/` directory** moves under `bench/archive-token-savings-thesis/`
  with a `README.md` that frames it as the experiment that motivated the
  pivot. We keep the raw data, charts, and harness — they're scientifically
  honest and they justify the design decisions in 02-05.
- **`extras/` agents** mostly disappear. The benchmark verdict on each is in
  the current README; for v1.0.0 of the pivoted stack we keep only the ones
  whose value is *not* cost:
  - `security-reviewer` (new, see `02-security-first.md`) — non-cost value:
    catches a class of bugs Opus inline won't reliably flag.
  - `flaky-test-isolator` — non-cost value: deterministic statistical signal
    a main-session agent would struggle to produce.
  - Everything else (`code-reviewer`, `test-runner`, `context-gatherer`,
    `repo-explorer`, `research-agent`, `docs-updater`, `git-committer{,-quick}`,
    `impact-mapper`, `output-digester`) gets archived to
    `bench/archive-token-savings-thesis/agents/` with a one-line tombstone
    pointing at the benchmark result that retired it.
- **Skills become the primary user-facing surface.** Currently `skills/` is
  empty. After the pivot it's where most new functionality lives — they're
  loaded on demand, portable across Claude Code and Codex (same SKILL.md
  spec at `agentskills.io`), and don't pay the per-session system-prompt tax
  subagents do.

## What's new (introduced by this pivot)

1. **Statusline** ships in the plugin. Currently lives at
   `~/.claude/statusline-command.sh` on Filip's machine; gets copied into
   `statusline/` in the repo and installed via the plugin so it travels
   across machines.
2. **First-class Codex support.** Until now this repo has been
   Claude-Code-only. The pivot makes Codex a peer:
   - Canonical `AGENTS.md` (Codex reads natively, no import needed).
   - `.codex/` mirror of `.claude/` hook config — both point at the
     same `scripts/hooks/*.sh`, so security hooks fire identically in
     both tools.
   - `scripts/install-codex.sh` (+ `.ps1` for Windows) — Codex has no
     plugin marketplace, so this script is the equivalent of
     `/plugin install`: copies `.codex/agents/*.toml` and
     `.codex/hooks.json` into `~/.codex/`, appends an
     `@<install-path>/AGENTS.md` reference to `~/.codex/AGENTS.md`.
   - **Codex DOES support subagents** (`.codex/agents/*.toml` with
     `name`, `description`, `developer_instructions`, optional `model`,
     `sandbox_mode`, `mcp_servers`). Our `security-reviewer` (and any
     future subagent) ships in both formats — TOML generated from MD
     frontmatter by `scripts/gen-codex-agents.py`.
   - README gets a dedicated **"Install for Codex"** section right
     next to **"Install for Claude Code"**, so the repo doesn't read
     as Claude-only.
3. **`/security-review` skill** with paired `security-reviewer` subagent.
   Detail in `02-security-first.md`.
4. **AI-first writing conventions**, enforced lightly:
   - AIDEV-NOTE/TODO/QUESTION anchor convention documented in `AGENTS.md`.
   - Structured JSON-lines logging spec.
   - Per-directory `AGENTS.md` template for non-trivial modules.
   - Detail in `03-ai-first-code.md`.
5. **`/repo-map` and `/process-diagram` skills** that emit mermaid into
   markdown. Detail in `04-visualization.md`.
6. **`/stack-check` skill + `stack-freshness` SessionStart hook**: 30-day
   nudge to check Claude Code, plugin, and tool-dep versions. Detail in
   `05-stack-freshness.md`.

## What's explicitly out of scope

- **No embedding RAG / vector DB / pre-built semantic index.** Research
  (`research_indexing.md`) shows the industry walked away from this for code
  in 2024-2025; we're not reviving it. The "internal codebase database" the
  user asked about is reframed below.
- **No "internal codebase database" as a separate store.** The codebase
  itself is the database; AIDEV-NOTE anchors + per-directory AGENTS.md +
  Claude Code's native Explore (Haiku) are the index. Maintaining a
  separate vector store buys nothing per Cherny / Sourcegraph data and
  costs continuous freshness work.
- **No Pencil MCP integration for repo diagrams.** Pencil is for UI/UX
  design of .pen files (mobile-app, web-app, landing-page); irrelevant for
  repo or process diagrams. (Confirmed via `research_visualization.md`.)
- **No public marketing pitch.** Plugin description stays honest:
  "Personal AI-dev stack — security hooks, AI-friendly conventions,
  repo-map, stack freshness. Public so I can install it across machines."
- **No paid/closed components.** Everything MIT, everything in the repo.

## Open questions for review

1. **Repo name.** Keep `claude-leverage`. (Confirmed by user 2026-05-24.)
   Deliberately avoid anything with "superpowers" in the name — that
   collides with the official `obra/superpowers-marketplace` plugin Filip
   uses alongside this stack. Branding here is just `claude-leverage`.
2. **Marketplace name.** Keep `filip-podstavec`? Same logic; recommendation
   is keep.
3. **Should the `extras/` agents survive at all** (even archived), or is it
   cleaner to delete them entirely now that they're not shipping? My
   recommendation: archive, don't delete. They're paid-for in commit
   history; archiving costs almost nothing and preserves the option to
   resurrect any of them later if the model-cost math flips.
4. **Bench archive location.** I propose `bench/archive-token-savings-thesis/`
   inside the existing `bench/`. Alternative: move to a `legacy/` top-level
   directory. My recommendation: keep under `bench/` so existing links
   don't break.
