---
name: stack-check
description: |
  Verify that Claude Code, Codex CLI, this plugin, and the CLI deps
  required by claude-leverage hooks/skills are at their expected minimum
  versions per stack.toml. Also flags stale AIDEV-TODO/QUESTION anchors
  and sanity-checks AGENTS.md size + structure in the current repo.
  Read-only — reports status and update commands; never installs anything.
  Touches the freshness timestamp on success so the SessionStart
  `stack-freshness` hook stays quiet for the next N days (default 30).
allowed-tools:
  - Read
  - Write
  - Grep
  - Glob
  - Bash(claude --version)
  - Bash(codex --version)
  - Bash(git --version)
  - Bash(rg --version)
  - Bash(jq --version)
  - Bash(python --version)
  - Bash(python3 --version)
  - Bash(mmdc --version)
  - Bash(node --version)
  - Bash(shellcheck --version)
  - Bash(npm view:*)
  - Bash(touch:*)
  - Bash(date:*)
  - Bash(test:*)
  - Bash(mkdir:*)
  - Bash(git rev-parse:*)
  - Bash(wc:*)
  - Bash(stat:*)
  - WebFetch
---

# /stack-check

## What it does

Walks `stack.toml`, queries each declared dependency's installed version,
optionally fetches the latest available version, and reports a Markdown
table:

```markdown
# Stack check — <YYYY-MM-DD>

| Tool | Installed | Required | Status | Update |
|------|-----------|----------|--------|--------|
| claude (Claude Code) | 2.1.89 | ≥2.1.0 | ok | — |
| codex (Codex CLI) | 0.39.0 | ≥0.40.0 | **outdated** | npm i -g @openai/codex |
| claude-leverage (this plugin) | 1.0.0 | latest 1.0.1 | **outdated** | /plugin update claude-leverage |
| git | 2.45.0 | ≥2.40.0 | ok | — |
| rg | 14.0.3 | ≥13.0.0 | ok | — |
| jq | (not found) | ≥1.6 (optional) | missing | brew install jq |
| python | 3.12.1 | ≥3.10 | ok | — |
| mmdc | (not found) | ≥10.0.0 (optional) | missing | npm i -g @mermaid-js/mermaid-cli |
| node | 20.10.0 | ≥20.0.0 | ok | — |
| shellcheck | (not found) | ≥0.8.0 (optional) | missing | brew install shellcheck |
```

On successful completion (no errors thrown), updates
`~/.local/state/claude-leverage/.last-stack-check` (or
`~/.claude/claude-leverage/.last-stack-check` if XDG state dir is
unavailable) with the current epoch time so the SessionStart hook stays
quiet for the next N days.

## Workflow

1. **Load `stack.toml`.** From the plugin install dir
   (`$CLAUDE_PLUGIN_ROOT/stack.toml`) or, if running standalone, from the
   repo root. If neither exists, STOP and report.

2. **For each `[[host.tool]]` and `[[deps.tool]]`:**
   - Run `check_cmd`. Capture stdout+stderr.
   - Parse the version with a simple regex (`(\d+\.\d+(\.\d+)?)` —
     accept "X.Y" and "X.Y.Z" both). If parse fails or command not
     found, mark "missing" (and "outdated" if `optional = false`).
   - Compare against `min_version` using a tuple compare (split on `.`).
   - Mark: `ok` | `outdated` | `missing` | `unknown (parse failed)`.
   - **Resolve update hint** per-OS: detect platform via `uname -s` (or
     PowerShell `$env:OS` / `$IsWindows`). Prefer `update_hint_macos` /
     `update_hint_linux` / `update_hint_windows` when present and the
     platform matches; otherwise fall back to the generic `update_hint`
     field. This is what stack.toml `manifest_version = 2` introduced.

3. **For the plugin itself:**
   - Read `version` from the installed `.claude-plugin/plugin.json`.
   - WebFetch
     `https://raw.githubusercontent.com/Filip-Podstavec/claude-leverage/main/.claude-plugin/plugin.json`
     and compare to the installed version. Cache the network result for
     24h in `~/.claude/claude-leverage/.stack-check-cache.json` to avoid
     hammering GitHub if the user runs the skill repeatedly.

4. **For Claude Code itself:**
   - `claude --version` is the installed version.
   - We do NOT fetch the latest Claude Code version from the network —
     Anthropic doesn't expose a stable scrapable endpoint. Instead, the
     `min_version` in stack.toml is hand-maintained: bump it when this
     plugin starts depending on a feature only present in a newer CC.

5. **Walk the current repo for AIDEV anchor health** (if cwd is inside
   a git repo). Grep `git rev-parse --show-toplevel` for
   `AIDEV-(TODO|QUESTION):` matches, group by age:
   - "fresh" (anchor on a file modified in the last 30 days)
   - "aging" (30–90 days)
   - "stale" (>90 days)
   Use `git log -1 --format=%cI -- <file>` for last-modified
   timestamps. Cap walk at 5000 files; skip the bench archive, vendor
   dirs, node_modules, __pycache__, .git.

   Reported after the version table:

   ```markdown
   ## AIDEV anchors (current repo: <name>)

   - 14 AIDEV-TODO total: 3 fresh, 8 aging, **3 stale (>90d)**
   - 5 AIDEV-QUESTION total: 1 fresh, 2 aging, **2 stale (>90d)**

   Stale anchors (consider resolving or removing):
   - `src/billing/charge.py:47` — AIDEV-TODO (last touched 2025-12-03)
   - `src/auth/middleware.py:89` — AIDEV-QUESTION (last touched 2025-11-15)
     ...
   ```

   If not in a git repo, skip this section silently.

6. **Sanity-check AGENTS.md** (if present in cwd or repo root):
   - File size: warn if > 32 KiB (Codex hard cap; content beyond is
     silently dropped).
   - Broken `@<path>` imports: grep for `^@` lines, verify each
     referenced file exists relative to the importer.
   - Stale file references: extract `path/to/file.ext`-shaped strings
     from the body and check existence (best-effort; lots of false
     positives, so report only the obvious ones — e.g. when AGENTS.md
     mentions `scripts/foo.sh` and `scripts/foo.sh` does not exist).
   Per-directory AGENTS.md files (`**/AGENTS.md`, depth ≤ 3) get the
   same size check.

   Reported after the anchors section:

   ```markdown
   ## AGENTS.md sanity

   - `AGENTS.md` — 4.2 KiB, ok
   - `src/billing/AGENTS.md` — 1.1 KiB, ok
   - `src/api/AGENTS.md` — **38.4 KiB, over Codex 32 KiB cap** (Codex
     will silently drop content beyond byte 32768; consider splitting)
   - Broken imports: _none_
   - Possibly stale references: 1 (`scripts/old_runner.sh` mentioned
     but not found)
   ```

7. **Emit the Markdown report** combining version table + anchors +
   AGENTS.md sanity. Tier the version rows: required first, then
   optional. Required-failing rows in bold.

8. **Reset the timestamp.** Only if no row failed with an *error*
   (process crashed, network exception). A failure status (outdated /
   missing / stale anchors / oversized AGENTS.md) is information, not
   an error — reset the timestamp. `touch <state_dir>/.last-stack-check`
   writes mtime; we write the epoch into the file body too (the hook
   reads from the body).

## Hard rules

- **Never install anything.** Output update commands, but never run
  them. The user types whichever they want.
- **Never block.** Read-only network + filesystem.
- **Cache network results for 24h.** If the cache file exists and is
  fresh, use it without hitting the network. Cache key: the
  fully-resolved marketplace.json URL.
- **Network is optional.** If WebFetch fails (offline), report
  "(cannot fetch latest — offline)" for the rows that need network and
  keep the rest of the report.
- **Always run `Bash(... --version)` defensively.** Use `2>&1` and treat
  exit code != 0 OR empty output as "not found".

## Tunables

- `CLAUDE_LEVERAGE_FRESHNESS_DAYS=N` — override the 30-day default for
  the SessionStart hook.
- `CLAUDE_LEVERAGE_FRESHNESS_DAYS=0` — disable the SessionStart nudge
  entirely.
- `CLAUDE_LEVERAGE_STATE_DIR=<path>` — override the state directory.
- `CLAUDE_LEVERAGE_ANCHOR_STALE_DAYS=N` — change the "stale" threshold
  for AIDEV-TODO/QUESTION (default 90).
- `CLAUDE_LEVERAGE_SKIP_ANCHOR_AUDIT=1` — skip the AIDEV anchor walk
  entirely (useful when running outside any project repo).
- `CLAUDE_LEVERAGE_SKIP_AGENTS_MD_AUDIT=1` — skip the AGENTS.md
  sanity pass.

## Codex parity

Same SKILL.md ships in Codex via `scripts/install-codex.sh`. The skill
checks Codex's own version too (if `codex` is on PATH); the row is
optional so a Claude-only user doesn't see a false missing.

## What this skill does NOT do

- **Install or update anything.** Suggest commands; let the user run
  them.
- **Check arbitrary user-installed plugins.** Scope is limited to this
  plugin's own stack. Policing every other plugin's freshness is scope
  creep with bad failure modes (marketplaces change shape, plugins
  uninstall, etc.).
- **Telemetry / phone-home.** All state is local. Only network calls
  are to public GitHub and (optionally) npm registry for plugin/codex
  latest-version lookup, and only when the user explicitly runs this
  skill.
