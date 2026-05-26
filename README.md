# claude-leverage

[![CI](https://github.com/Filip-Podstavec/claude-leverage/actions/workflows/ci.yml/badge.svg)](https://github.com/Filip-Podstavec/claude-leverage/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Claude Code](https://img.shields.io/badge/Claude_Code-compatible-blueviolet)](https://docs.anthropic.com/en/docs/claude-code)
[![Codex CLI](https://img.shields.io/badge/Codex_CLI-compatible-1f6feb)](https://developers.openai.com/codex)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)
![Version](https://img.shields.io/badge/version-1.6.0-success)

> A small, opinionated **AI-coding-agent suite** for Claude Code and Codex
> CLI. Built for me first, public so I can install it across machines, and
> for anyone else shipping client work primarily through AI agents.
>
> **Complements** skills-based plugins like the official `superpowers` plugin;
> it does not try to replace them.

## Mission

This stack exists for one job: **help an AI dev (me) ship secure and
long-term-maintainable software for clients, working primarily through Claude
Code or Codex.**

Shipping at velocity with AI agents is easy. Shipping in a way that the *next*
agent (human or AI) opening the repo in six months can still safely modify is
the hard part. That second part is what the hooks, conventions, and skills here
automate — not just at session start, but continuously as the repo grows. Three
properties guide every decision in this repo:

1. **Security by default** — deterministic shell hooks block secrets, force
   pushes, and `--no-verify` before any model decision.
2. **Self-maintaining as the repo grows** — non-blocking nudges flag missing
   AIDEV-NOTE anchors on big diffs, missing per-directory `AGENTS.md` on
   growing source dirs, stale-anchor decay (`AIDEV-TODO(by: ...)` deadlines),
   and security-review-worthy changes — so maintenance debt surfaces while it's
   still cheap to fix.
3. **Cross-tool by design** — same `AGENTS.md`, same `SKILL.md` files, same
   hook scripts in Claude Code and Codex. Author once.

## What you get

**Always-on safety (hooks, no setup, no model invocation):**
- `block-secrets-precommit` — refuses `git commit` if staged diff contains
  API keys / tokens / private keys (per-line allowlist via marker comment)
- `block-dangerous-git` — refuses `git push --force`, `--no-verify`,
  `git reset --hard` on protected branches
- `ai-first-nudge` — non-blocking: ≥50 net-new LOC without AIDEV-NOTE on
  non-test files OR new source-dir without AGENTS.md → one-line suggestion
- `security-nudge` — non-blocking Stop hook: ≥80 net-new LOC touching
  sensitive paths → suggests `/security-review`
- `stack-freshness` — non-blocking SessionStart: 30+ days since last
  `/stack-check` → one-line reminder via SessionStart `additionalContext`
  (no network)
- `bare-repo-nudge` — non-blocking SessionStart, two-branch nudge:
  (A) cwd is not a git repo AND not `$HOME`/`/tmp`/system → reminder
  to `git init` + `/init-repo`; (B) cwd IS a git repo but root has no
  `AGENTS.md` / `CLAUDE.md` AND has a project marker file
  (`package.json` / `pyproject.toml` / `Cargo.toml` / `go.mod` / …)
  → reminder to `/init-repo` so the convention layer (AIDEV anchors,
  structured logging, …) actually gets loaded. One-per-day per
  cwd/repo-root.
- `skill-cheatsheet` — non-blocking SessionStart, gated on the repo
  having a `claude-leverage:` marker in `AGENTS.md` (i.e., the user
  has actively adopted the stack). Surfaces a compact list of
  high-value skills + triggers once per 14 days per repo, via
  SessionStart `additionalContext`. Mitigates the documented
  skill-auto-activation gap (`description: |` block scalars where
  the runtime parses only the first line). Override via
  `CLAUDE_LEVERAGE_SKILL_HINT_DAYS` (0 = disabled).

**Security review (skill + dedicated subagent):**
- `/security-review` — audit current diff for OWASP-Top-10-shaped issues +
  `package.json` / `requirements.txt` typosquatting heuristic. Read-only
  Sonnet subagent returns Critical / Important / Nice schema with
  `file:line`. No dependency on any other plugin.

**Repo maintenance (skills you invoke periodically):**
- `/repo-map` — refresh the architecture mermaid block in README between
  idempotent markers; optional dep-graph block via `madge` / `pydeps`
- `/process-diagram <name>` — sequence/flowchart for a named workflow,
  inserted into target markdown between markers, mmdc-validated
- `/stack-check` — Claude Code + Codex + plugin + CLI dep versions vs
  `stack.toml`, plus stale-anchor walk + AGENTS.md sanity audit
- `/log-structured` — audit non-structured logging, suggest spec-compliant
  replacements per the JSON-lines convention

**Setup + handoff (skills per-project / per-decision):**
- `/init-repo` — bootstrap a fresh project: AGENTS.md from per-language
  template, `.gitignore` patterns, optional structured-logging starter
- `/codex-sandbox` — configure per-project `.codex/config.toml` sandbox +
  approval modes (dev / prod / custom)
- `/explain-diff` — plain-English 3–5 bullet diff narration in three
  audience modes (`--for pr / review / self`)
- `/adr-new` — bootstrap a numbered MADR-flavored Architecture Decision
  Record. Immutable status, captures *why* for the next agent in 6 months
- `/session-log` — distill the current session into `docs/sessions/`. The
  continuity layer between sessions — distillate, not transcript
- `/glossary-init` — bootstrap/extend `GLOSSARY.md` at repo root for
  domain terms specific to *this* repo. Surfaces candidates by identifier
  frequency; never invents definitions (the user types them)
- `/arch-map` — bootstrap/refresh `architecture.yml` at repo root —
  machine-readable module metadata (role/stability/public_surface/...);
  hand-curated, `--validate` mode for CI
- `/repo-doctor` — read-only AI-readiness audit. Scores ~15 dimensions
  (AGENTS.md, ADRs, sessions, GLOSSARY.md, architecture.yml, AIDEV
  anchor density, per-dir AGENTS.md, tests + test/source LOC ratio,
  structured logging, .gitignore, README quickstart, language
  manifest). Each gap → concrete fix action. `--score` / `--json` /
  `--fail-on missing|todo|stale` for CI gating

**Workflow commands (Claude Code only — use `!` preamble efficiency):**
- `/flaky-test` — delegates to `flaky-test-isolator` subagent for N-run
  stability analysis

(For commits, the vanilla Claude commit workflow + the
`block-secrets-precommit` / `block-dangerous-git` hooks already cover
secret scanning, Conventional Commits style, refusing `.env`, refusing
`--no-verify`, and refusing force-push. v1.4.4 removed the
`/commit-smart` slash command — it added a treacherous auto-push to
something that should be opt-in. Just commit with vanilla and push
explicitly when you want.)

**Conventions enforced via documentation + nudges:**
- AIDEV-NOTE / AIDEV-TODO / AIDEV-QUESTION anchor comments (with optional
  ISO-8601 deadlines: `AIDEV-TODO(by: 2026-08-01)`)
- JSON-lines structured logging spec with `trace_id` / `span_id` / `attrs`
- Per-directory AGENTS.md for non-trivial modules
- ADRs for load-bearing architectural decisions
- Session logs for continuity between AI sessions

**Cross-tool plumbing:**
- Same `AGENTS.md` for Claude Code (via `@AGENTS.md` import in `CLAUDE.md`)
  and Codex (native read)
- Hook scripts in `scripts/hooks/` shared by both tools
- Skills installed to `~/.agents/skills/` by the Codex installer
- Subagents authored in MD + auto-generated to TOML for Codex parity (CI gate)

## Install — Claude Code

```
/plugin marketplace add Filip-Podstavec/claude-leverage
/plugin install claude-leverage@filip-podstavec
```

That's it for the plugin. **Restart Claude Code** (or run `/skill list` and
`/agents` in a current session) to pick up all 13 skills and 2 subagents.

### Optional: portable statusline

Five segments shown left-to-right: 5-hour rate limit, 7-day rate limit, current
context window %, model name, git branch.

![statusline](statusline/screenshot.png)

Claude-Code-only (Codex has no statusline). Single Python file, no `jq`
dependency, works on Windows under Git Bash. Color thresholds: green <60 %,
yellow 60–84 %, red ≥85 %.

```bash
# 1. Copy into ~/.claude/ (overwrites only if you have no statusline configured)
cp statusline/statusline-command.sh ~/.claude/statusline-command.sh
chmod +x ~/.claude/statusline-command.sh
```

Then add to `~/.claude/settings.json`:

```json
"statusLine": {
  "type": "command",
  "command": "bash ~/.claude/statusline-command.sh"
}
```

Restart Claude Code. To opt out later: delete the `statusLine` block from
`settings.json`.

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

1. Resolves repo path into `~/.codex/hooks.json` so security + nudge hooks
   fire in every Codex session globally.
2. Appends `@<repo-path>/AGENTS.md` to `~/.codex/AGENTS.md` so the canonical
   guidance loads on every Codex session.
3. Copies `.codex/agents/*.toml` to `~/.codex/agents/`.
4. Copies all 13 skills to `~/.agents/skills/claude-leverage/` so they work
   in Codex sessions exactly as in Claude Code.

**Idempotent**: re-running detects existing install via marker comments and
overwrites in place. Atomic skill swap (staging dir + rename) so a copy
failure mid-loop leaves the previous install intact.

## Workflow example

Typical session for a security-sensitive feature, end-to-end:

<!-- process-diagram:security-first-flow:start -->
<!-- Regenerable via: /process-diagram security-first-flow --into README.md -->
```mermaid
sequenceDiagram
    autonumber
    actor User
    participant CC as Claude Code (Opus)
    participant Hook as scripts/hooks/*.sh
    participant SR as security-reviewer<br/>(Sonnet, read-only)
    participant Git

    User->>CC: edit src/auth/handler.py
    CC->>Hook: PostToolUse (Write/Edit)
    Hook-->>User: ai-first-nudge: "73 LOC no AIDEV-NOTE anchor"

    User->>CC: /security-review
    CC->>SR: Task (delegate)
    SR->>Git: git diff --cached
    Git-->>SR: staged diff
    SR-->>CC: Critical / Important / Nice<br/>(file:line citations)
    CC-->>User: relay report verbatim

    User->>CC: /adr-new "use HS256 not RS256 here"
    CC->>CC: write docs/adr/0007-...md (immutable)

    User->>CC: commit this
    CC->>Hook: PreToolUse (Bash: git commit)
    Note right of Hook: block-secrets-precommit<br/>scans staged diff
    Hook-->>CC: allow (no secrets)
    CC->>Git: commit (Conventional Commits)
    Note right of CC: push only when user asks<br/>(no auto-push in v1.4.4+)

    User->>CC: /session-log "wire HS256 auth + middleware"
    CC->>CC: write docs/sessions/YYYY-MM-DD-...md (distillate)

    Note over CC,Hook: Stop hook: security-nudge fires<br/>if sensitive paths touched (1× per branch/day)
```
<!-- process-diagram:security-first-flow:end -->

Reading the diagram: explicit user invocations are solid arrows
(`User -> CC`), automatic hook firings are dashed `Hook -> User`
returns, subagent delegation is one `Task` round-trip. Nothing in the
maintenance layer (ADRs, session logs) is auto-fired — the agent
recognizes the moment from the trigger-aware skill descriptions and
the convention documented in `AGENTS.md`.

If you haven't run `/stack-check` in 30+ days, the SessionStart
`stack-freshness` hook prints a one-line reminder (no network). The
actual version check + AIDEV anchor health + AGENTS.md sanity audit
only fires on explicit invocation.

For deeper walkthroughs see
[`workflows/security-first-feature.md`](workflows/security-first-feature.md)
and [`workflows/maintaining-as-it-grows.md`](workflows/maintaining-as-it-grows.md).

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

## What's inside

| Directory | Purpose |
|-----------|---------|
| [`agents/`](agents/) | Claude Code subagents (Markdown + YAML frontmatter) |
| [`.codex/agents/`](.codex/agents/) | Codex subagents (TOML; auto-generated from `agents/`) |
| [`skills/`](skills/) | 13 cross-tool skills (`agentskills.io` SKILL.md spec) |
| [`commands/`](commands/) | 1 Claude Code slash command (`/flaky-test`) |
| [`hooks/hooks.json`](hooks/hooks.json) | Claude Code hook config (paths point at `scripts/hooks/`) |
| [`.codex/`](.codex/) | Codex hook template + sandbox/approval defaults |
| [`scripts/hooks/`](scripts/hooks/) | Hook shell scripts, shared by both tools |
| [`scripts/`](scripts/) | Installers, generators, version checks, `smoke-plugin.sh` |
| [`statusline/`](statusline/) | Portable statusline script + screenshot |
| [`claude-md-snippets/`](claude-md-snippets/) | Opt-in CLAUDE.md / AGENTS.md routing rules (2 ship by default; installable via `/init-repo`) |
| [`templates/`](templates/) | Per-language AGENTS.md example + structured-logging starter kits (4 languages) |
| [`docs/adr/`](docs/adr/) | Architecture Decision Records (numbered, immutable; 4 seed ADRs + template) |
| [`docs/sessions/`](docs/sessions/) | Distilled session logs (template + 1 demo log) |
| [`docs/specs/`](docs/specs/) | Design specs (the v1.0 pivot package + research) |
| [`workflows/`](workflows/) | End-to-end prose guides combining skills/hooks/conventions |
| [`bench/archive-token-savings-thesis/`](bench/archive-token-savings-thesis/) | Frozen evidence of the v0.x experiment that motivated the v1.0 pivot |

## Why a single repo for two tools

Per the [research](docs/specs/research/research_dual_codex_claude.md):
`AGENTS.md` is the open spec both tools converge on. Claude Code reads
`CLAUDE.md` natively but its `@<path>` import lets `CLAUDE.md` be a one-line
redirect to `AGENTS.md`. Hook event vocabularies match between the two tools
(`PreToolUse`, `PostToolUse`, `SessionStart`, `Stop`), so the same shell
scripts work for both — only the trigger config differs. Subagents must be
authored twice (MD+YAML for Claude, TOML for Codex), but `scripts/gen-codex-agents.py`
keeps them in sync and CI fails on drift.

The full design rationale is in
[`docs/adr/0002-agents-md-canonical-claude-md-import.md`](docs/adr/0002-agents-md-canonical-claude-md-import.md).

## Verifying an install works

Before pushing changes to the plugin, run the bundled smoke check:

```bash
bash scripts/smoke-plugin.sh
```

It runs every pre-push gate in one shot: pytest, version sync, codex agent
parity, shellcheck (if installed), every hook script with empty stdin, plus
an end-to-end install-codex run against a scratch directory. Green exit
means safe to push; red exit prints which gate failed.

If you're a user installing the plugin (not modifying it), the equivalent
verification is:

```
/plugin install claude-leverage@filip-podstavec
/skill list                # confirm 13 skills appear
/agents                    # confirm security-reviewer + flaky-test-isolator
echo 'aws_key = "AKIAIOSFODNN7EXAMPLE"' > /tmp/test.txt && git add /tmp/test.txt
# Ask the agent to commit /tmp/test.txt — block-secrets-precommit should refuse.
```

## Update / uninstall

**Claude Code:**

```
/plugin marketplace update
/plugin update claude-leverage
/plugin uninstall claude-leverage@filip-podstavec
```

**Codex (uninstall):**

```bash
# Linux / macOS / WSL2
rm -rf ~/.agents/skills/claude-leverage
rm    ~/.codex/agents/security-reviewer.toml ~/.codex/agents/flaky-test-isolator.toml
# restore original ~/.codex/hooks.json (the installer leaves a .bak)
mv ~/.codex/hooks.json.pre-claude-leverage.bak ~/.codex/hooks.json 2>/dev/null \
   || rm ~/.codex/hooks.json
# Edit ~/.codex/AGENTS.md and delete the block between the two
# "# claude-leverage:" markers.
```

PowerShell variant:

```powershell
Remove-Item -Recurse -Force $env:USERPROFILE\.agents\skills\claude-leverage
Remove-Item -Force $env:USERPROFILE\.codex\agents\security-reviewer.toml,$env:USERPROFILE\.codex\agents\flaky-test-isolator.toml
$bak = "$env:USERPROFILE\.codex\hooks.json.pre-claude-leverage.bak"
if (Test-Path $bak) { Move-Item -Force $bak "$env:USERPROFILE\.codex\hooks.json" }
else { Remove-Item -Force "$env:USERPROFILE\.codex\hooks.json" }
# Then edit ~/.codex/AGENTS.md and remove the marker block.
```

## Honest history

This repo started in 2026 as a v0.x experiment in tier-routing across
Sonnet/Haiku subagents to save tokens vs. vanilla Claude Code. Earlier
runs done on prior Claude model generations (not preserved in this
repo's archive) showed genuine savings on the order of **+40 % or
more** in the leveraged direction — the thesis was empirically alive
when it was first formed. By the time we were measuring v0.10 / v0.11
under benchmark conditions that *are* captured here, the trade-off had
narrowed to overhead in the tens of percent (best in-repo run:
**+26 %** on a 4-turn warm-cache workflow), but the other benefits of
subagent dispatch (isolated context, structured output, deterministic
schemas) arguably still justified that price.

Opus 4.7 inverted the trade-off. Its prompt caching made "read large,
emit small" inline cheap enough that per-invocation `Task`-dispatch
overhead structurally exceeded any per-token savings from delegating
to Sonnet/Haiku. The pivot was a rational response to a
pricing-structure change, not a confession of a design mistake — but
once the new economics landed, the headline thesis stopped paying for
itself and we said so.

Three rounds of benchmarking on Opus 4.7 captured the post-shift
picture:

| Stage | Overhead vs vanilla |
|---|---:|
| Cold cache, 4 tasks                 | +73 % |
| Warm cache, 4-turn workflow         | +63 % |
| Warm cache, 12-turn day-in-the-life | **+117 %** |

The 12-turn case shows the mechanism. Baseline benefits from prompt
cache reuse every turn within a session; subagent dispatch resets
context per invocation. As Opus 4.7's caching matured, the gap
widened rather than amortizing. Full per-turn breakdown is in the
archived long-session report.

v1.0.0 is what's left after subtracting everything the new economics
killed; v1.1.x through v1.4.x added the dev-stack scaffolding around
the surviving components (security hooks, AI-first conventions,
on-demand skills, durable-memory layer, self-maintenance hardening).

Full data + design: [`bench/archive-token-savings-thesis/`](bench/archive-token-savings-thesis/),
[`docs/specs/2026-05-24-pivot/`](docs/specs/2026-05-24-pivot/),
[`docs/adr/0001-pivot-from-token-savings-to-dev-stack.md`](docs/adr/0001-pivot-from-token-savings-to-dev-stack.md).
Changelog: [`CHANGELOG.md`](CHANGELOG.md).

## License

[MIT](LICENSE) — see also [CONTRIBUTING.md](CONTRIBUTING.md).
