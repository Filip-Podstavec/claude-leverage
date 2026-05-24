---
name: stack-check
description: |
  Verify that Claude Code, Codex CLI, this plugin, and the CLI deps
  required by claude-leverage hooks/skills are at their expected minimum
  versions per stack.toml. Read-only — reports status and update commands;
  never installs anything. Touches the freshness timestamp on success so
  the SessionStart `stack-freshness` hook stays quiet for the next
  N days (default 30).
allowed-tools:
  - Read
  - Write
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

5. **Emit the Markdown table.** Tier the rows: required first, then
   optional. Required-failing rows go in bold; required-ok rows plain.

6. **Reset the timestamp.** Only if no row failed with an *error*
   (process crashed, network exception). A failure status (outdated /
   missing) is information, not an error — reset the timestamp.
   `touch <state_dir>/.last-stack-check` writes mtime; we write the
   epoch into the file body too (the hook reads from the body).

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
