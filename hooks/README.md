# Hooks

## What hooks are

Hooks are shell scripts executed by Claude Code at lifecycle events - primarily `PreToolUse`, which fires before a tool call runs. A hook can inspect the pending call and block it by exiting with code 2. Unlike subagents and slash commands, hooks don't involve the LLM - they are deterministic shell logic. This is why hooks are the right primary layer for security guardrails: they work in the main session, inside subagents, and even when the LLM is told otherwise.

## Why this matters

Defense in depth has three layers, in order of reliability:

1. **Hooks** - deterministic lock, runs on every tool call from every session
2. **Slash commands** - workflow that does things the right way by default
3. **Subagent prompt rules** - last-resort guidance for the LLM

A subagent rule like "never use `--no-verify`" only applies when that subagent is active. A hook applies to every `Bash` call from any session. Use hooks for security, prompts for workflow.

## Available hooks

- `block-secrets-precommit.sh` - Scans staged diff before `git commit` for API keys, tokens, and private keys. Blocks commit if found.
- `block-dangerous-git.sh` - Blocks force push, `--no-verify` commits, and hard reset on protected branches.
- `track-delegations.sh` - PostToolUse observability hook (non-blocking). Logs subagent delegations to `~/.claude/claude-leverage-stats.jsonl` including real token usage extracted from `tool_response.usage.*`. Prints a one-line stderr note like `(claude-leverage: code-reviewer -> sonnet, 13783 tok)` after each delegation.
- `leverage_stats_agg.py` - Helper Python script (not itself a hook). Reads the JSONL log emitted by `track-delegations.sh` and prints pipe-separated tier aggregates. Available for direct shell use, e.g. `STATS_FILE=~/.claude/claude-leverage-stats.jsonl python3 hooks/leverage_stats_agg.py`. **Note:** the `/leverage-stats` slash command uses an inline copy of this same logic (the file-based invocation was unreliable in slash command context); the inline copy and this file must be kept in sync, along with the jq fallback in the same preamble.
- `json_parse.sh` - Helper shell library (not itself a hook). Sourced by all three hooks. Provides `read_stdin`, `has_parser`, and `get_field` with a jq -> python3 -> python fallback chain.

## Known limits (read before relying on hooks for security)

- **JSON parser dependency, fail-open posture.** Hooks need a JSON parser to inspect Claude Code's hook input. They try `jq` first, then `python3`, then `python`. If none are on PATH, the security hooks (`block-secrets-precommit`, `block-dangerous-git`) print a loud warning to stderr and exit 0 (allow). This is intentional — blocking every Bash call when no parser is available would break unrelated work — but the trade-off is that until at least one parser is installed, **the security guardrails are not enforced.** Most macOS/Linux systems already have `python3` preinstalled. Windows users typically need to install one explicitly (`winget install jqlang.jq` for jq, or python.org / Microsoft Store for Python).
- **`track-delegations` degrades gracefully.** The observability hook still logs an anonymous record (subagent="unknown", tier="unknown") when no parser is available — total delegation counts remain accurate, only the per-agent breakdown is missing.
- **Pattern-based detection has false negatives.** Secret patterns are heuristics; custom or novel formats may slip through. Hooks are defense-in-depth, not a substitute for CI-side secret scanning (e.g., gitleaks, trufflehog).
- **False positives have a per-line escape hatch.** When a pattern matches a legitimate value (test fixture, documentation example, mock token), append the literal comment `claude-leverage-allow-secret` on the same line. The secrets hook skips lines containing that marker. Use sparingly — the marker is load-bearing, and future readers may not recognize it.

## Install

### Plugin install (automatic)

If you installed claude-leverage as a plugin (`/plugin install`), hooks are registered automatically via `hooks/hooks.json`. No manual `settings.json` editing needed. The steps below are for standalone copy-paste installs only.

### Step 1: Copy scripts

```bash
mkdir -p ~/.claude/hooks
cp hooks/*.sh hooks/leverage_stats_agg.py ~/.claude/hooks/
chmod +x ~/.claude/hooks/*.sh ~/.claude/hooks/leverage_stats_agg.py
```

### Step 2: Install a JSON parser

Hooks need either `jq` or `python` (3 or 2) on PATH. Most systems already have one — check with:

```bash
command -v jq || command -v python3 || command -v python
```

If nothing prints, install one:

```bash
# macOS - jq is fast, python3 is usually preinstalled
brew install jq

# Ubuntu/Debian - jq lightweight; python3 typically preinstalled
sudo apt install jq

# Windows - via winget or Chocolatey, or python.org
winget install jqlang.jq
```

`jq` is preferred (lower startup cost on every Bash call), but `python` works as a transparent fallback.

### Step 3: Register in settings.json

Add to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "$HOME/.claude/hooks/block-secrets-precommit.sh" },
          { "type": "command", "command": "$HOME/.claude/hooks/block-dangerous-git.sh" }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Task",
        "hooks": [
          { "type": "command", "command": "$HOME/.claude/hooks/track-delegations.sh" }
        ]
      }
    ]
  }
}
```

Restart Claude Code or run `/hooks` in an active session to pick up changes.

## Permissions as a complementary layer

`permissions.deny` in `settings.json` is a declarative complement to hooks. Hooks handle logic (regex matching, conditional checks). Permissions handle static deny lists for specific files and patterns.

```json
{
  "permissions": {
    "deny": [
      { "type": "Read", "pattern": "**/.env" },
      { "type": "Read", "pattern": "**/.env.*" },
      { "type": "Edit", "pattern": "**/.env" },
      { "type": "Edit", "pattern": "**/.env.*" },
      { "type": "Bash", "pattern": "git push --force*" },
      { "type": "Bash", "pattern": "git push -f *" }
    ]
  }
}
```

`permissions.deny` is faster than a hook (no shell startup), but less flexible. Use it for clear-cut deny patterns; use hooks for logic.

## Verify install

```bash
# Test secrets hook with fake AWS key
echo 'aws_key = "AKIAIOSFODNN7EXAMPLE"' > test-secret.txt
git add test-secret.txt
# Ask Claude Code to commit. Hook should block.
git rm --cached test-secret.txt && rm test-secret.txt
```

## Disabling temporarily

When a hook blocks a legitimate commit:

- **Simplest:** run the commit manually outside Claude Code
- **Temporary:** remove the hook entry from `settings.json`, restart session
- **Permanent exception:** fork the hook script and adjust patterns

## Platform notes

- **macOS, Linux, WSL2:** works out of the box
- **Native Windows (PowerShell):** hooks need rewriting to PowerShell. PRs welcome.
