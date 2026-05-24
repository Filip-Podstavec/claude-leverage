# claude-leverage

> **v1.0.0 (2026-05-24)** — pivot release. This started as a hypothesis that
> tier-routing across Sonnet/Haiku subagents would save tokens vs vanilla
> Claude Code. Three rounds of rigorous benchmarking on Opus 4.7 disproved
> that thesis (raw data in [`bench/archive-token-savings-thesis/`](bench/archive-token-savings-thesis/)).
> v1.0.0 pivots to a **personal Claude Code + Codex dev stack** focused on
> what the data still supports: deterministic security hooks, AI-first
> conventions, on-demand skills, and a portable statusline.
>
> The honest history lives in the archive — see [Honest history](#honest-history)
> at the bottom of this README.

[![CI](https://github.com/Filip-Podstavec/claude-leverage/actions/workflows/ci.yml/badge.svg)](https://github.com/Filip-Podstavec/claude-leverage/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Claude Code](https://img.shields.io/badge/Claude_Code-compatible-blueviolet)](https://docs.anthropic.com/en/docs/claude-code)
[![Codex CLI](https://img.shields.io/badge/Codex_CLI-compatible-1f6feb)](https://developers.openai.com/codex)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)]()

A small, opinionated dev stack — built for me first, public so I can install
it across machines. **Complements skills-based plugins like the official
`superpowers` plugin; it does not try to replace them.**

## What you get

- **Security hooks** (always-on, deterministic): `block-secrets-precommit`,
  `block-dangerous-git`, `track-delegations`. Run on every Bash tool call,
  cannot be bypassed by prompt injection.
- **`/security-review`** skill + read-only `security-reviewer` subagent
  (Sonnet) for OWASP-Top-10-shaped audits of the current diff.
  Self-contained — no dependency on any other plugin.
- **`/repo-map`** and **`/process-diagram`** skills — generate/update
  mermaid blocks in markdown between idempotent markers.
- **`/stack-check`** skill + 30-day **`stack-freshness`** SessionStart hook
  — local-only timestamp nudge; explicit user-run check actually queries
  versions.
- **`/commit-smart`** — inline secret scan + Conventional Commits message
  + push. All in the main session, no subagent dispatch (benchmark verdict).
- **Portable statusline** — Python-based, no `jq` dep, Windows-friendly.
  Shows 5h/7d rate limits, context %, model, branch, session $ estimate.
- **AI-first code conventions** documented in `AGENTS.md`: AIDEV-NOTE
  anchors, JSON-lines logging spec, per-directory AGENTS.md template.
- **Dual-tool by design**: same `AGENTS.md` for Claude Code (via
  `@AGENTS.md` import in `CLAUDE.md`) and Codex (native read). Hook scripts
  shared via `scripts/hooks/`; agents authored in MD + auto-generated to
  TOML for Codex.

## Install — Claude Code

```
/plugin marketplace add Filip-Podstavec/claude-leverage
/plugin install claude-leverage@filip-podstavec
```

That's it for the plugin. To enable any optional CLAUDE.md routing snippets,
run `/install-snippets` (default install ships no snippets).

For the statusline:
```bash
# Copy into ~/.claude/ — only overwrites if you have no statusline configured
cp statusline/statusline-command.sh ~/.claude/statusline-command.sh
chmod +x ~/.claude/statusline-command.sh
```

Then add to `~/.claude/settings.json`:
```json
"statusLine": { "type": "command", "command": "bash ~/.claude/statusline-command.sh" }
```

## Install — Codex CLI

Codex has no plugin marketplace, so installation is via a script:

```bash
# 1. Install Codex CLI itself (one time)
npm i -g @openai/codex

# 2. Clone this repo to a stable location
git clone https://github.com/Filip-Podstavec/claude-leverage.git ~/.local/share/claude-leverage
cd ~/.local/share/claude-leverage

# 3. Run the installer
bash scripts/install-codex.sh         # macOS / Linux / WSL2
# OR
pwsh scripts/install-codex.ps1        # Windows PowerShell
```

The installer:
1. Resolves repo path into `~/.codex/hooks.json` so security hooks fire in
   every Codex session globally.
2. Appends `@<repo-path>/AGENTS.md` to `~/.codex/AGENTS.md` so the canonical
   guidance loads on every Codex session.
3. Copies `.codex/agents/*.toml` to `~/.codex/agents/`.

Idempotent: re-running detects existing install via marker comments and
updates in place.

## What's inside

| Directory | Purpose |
|-----------|---------|
| [`agents/`](agents/) | Claude Code subagents (Markdown + YAML frontmatter) |
| [`.codex/agents/`](.codex/agents/) | Codex subagents (TOML; generated from `agents/`) |
| [`skills/`](skills/) | Cross-tool skills (`agentskills.io` SKILL.md spec) |
| [`commands/`](commands/) | Claude Code slash commands |
| [`hooks/hooks.json`](hooks/hooks.json) | Claude Code hook config (paths point at `scripts/hooks/`) |
| [`.codex/hooks.json`](.codex/hooks.json) | Codex hook config (template; installer resolves paths) |
| [`.codex/config.toml`](.codex/config.toml) | Codex sandbox/approval defaults |
| [`scripts/hooks/`](scripts/hooks/) | Hook shell scripts, shared by both tools |
| [`scripts/`](scripts/) | Installers (`install-codex.{sh,ps1}`), version checks, generators |
| [`statusline/`](statusline/) | Portable statusline script |
| [`claude-md-snippets/`](claude-md-snippets/) | Opt-in CLAUDE.md routing rules (none in default install) |
| [`bench/archive-token-savings-thesis/`](bench/archive-token-savings-thesis/) | Frozen evidence of the v0.x experiment that motivated the v1.0 pivot |
| [`docs/specs/`](docs/specs/) | Design specs (current and historical) |

## Architecture

<!-- repo-map:start -->
<!-- This block is regenerated by skills/repo-map. Do not hand-edit.    -->
<!-- Re-run /repo-map to refresh after directory structure changes.     -->
```mermaid
flowchart LR
    Filip["Filip"] --> CC["Claude Code session"]
    Filip --> CX["Codex CLI session"]

    CC -- "reads" --> CMD["CLAUDE.md (1 line: @AGENTS.md)"]
    CMD -- "@import expand" --> AMD["AGENTS.md (canonical)"]
    CX -- "reads directly" --> AMD

    CC -- "loads skills from" --> SK["skills/"]
    CX -- "loads skills from" --> SK

    CC -- "hooks via" --> HK["hooks/hooks.json"]
    CX -- "hooks via" --> HKC["~/.codex/hooks.json (installed)"]
    HK -- "exec" --> SHELL["scripts/hooks/*.sh"]
    HKC -- "exec" --> SHELL

    CC -- "subagents" --> A1["agents/*.md (Markdown+YAML)"]
    CX -- "subagents" --> A2[".codex/agents/*.toml (TOML, generated)"]
```
<!-- repo-map:end -->

## Workflow example

Typical session with the default install:

```
1. Edit code                       → Opus inline
2. Run tests inline                → Opus reads pytest output
3. /security-review                → security-reviewer subagent (Sonnet, read-only)
4. /commit-smart                   → inline secret scan + Conventional Commits + push
5. Hooks run silently throughout   → block-secrets-precommit, block-dangerous-git
```

After ≥50 LOC of net-new code without an `AIDEV-NOTE:` anchor, the
`ai-first-nudge` PostToolUse hook prints a one-liner suggestion. After
≥80 LOC of net-new code in security-sensitive paths (auth, crypto, routes,
templates), the `security-nudge` Stop hook suggests `/security-review`. Both
are non-blocking.

When you haven't run `/stack-check` in 30+ days, the `stack-freshness`
SessionStart hook prints a one-liner reminder — local timestamp only, no
network. The actual version check (Claude Code, Codex, plugin, CLI deps)
only fires when you explicitly run `/stack-check`.

## Why this is a single repo for two tools

Per the [research](docs/specs/research/research_dual_codex_claude.md):
`AGENTS.md` is the open spec both tools converge on. Claude Code reads
`CLAUDE.md` natively but its `@<path>` import lets `CLAUDE.md` be a one-line
redirect to `AGENTS.md`. Hook event vocabularies match between the two tools
(`PreToolUse`, `PostToolUse`, `SessionStart`, `Stop`), so the same shell
scripts work for both — only the trigger config differs. Subagents must be
authored twice (MD+YAML for Claude, TOML for Codex), but `scripts/gen-codex-agents.py`
keeps them in sync.

## Update / uninstall

**Claude Code:**
```
/plugin marketplace update
/plugin update claude-leverage
/plugin uninstall claude-leverage@filip-podstavec
```

**Codex:** edit `~/.codex/AGENTS.md` and remove the block between the two
`# claude-leverage: ...` markers; remove `~/.codex/hooks.json` (or replace
with the `.bak` the installer created).

## Honest history

The benchmark series that disproved the v0.x token-savings thesis is in
[`bench/archive-token-savings-thesis/`](bench/archive-token-savings-thesis/) —
charts, raw stream-json transcripts, audit harnesses, the 11 retired
subagents, and the original `extras-README.md` documenting per-agent
verdicts.

Headline finding (Opus 4.7, 2026-05-24):

| Stage | Baseline | Leveraged | Delta |
|---|---:|---:|---:|
| Cold cache, 4 tasks                 | $0.37 | $0.64 | **+73 %** |
| Warm cache, 4-turn workflow         | $0.24 | $0.39 | **+63 %** |
| Warm cache, 12-turn day-in-the-life | $0.51 | $1.11 | **+117 %** |

The plugin model's per-invocation dispatch overhead structurally exceeded
the per-token savings from delegating execution to Sonnet/Haiku. Prompt
caching on Opus 4.7 makes "read large, emit small" cheap inline. v1.0.0 is
what's left after subtracting everything the data killed.

Full design docs for the pivot: [`docs/specs/2026-05-24-pivot/`](docs/specs/2026-05-24-pivot/).

## License

[MIT](LICENSE) — see also [CONTRIBUTING.md](CONTRIBUTING.md).
