# Hooks

This directory holds the Claude Code hook configuration (`hooks.json`). The
actual hook scripts live in [`../scripts/hooks/`](../scripts/hooks/) — they
are shared between Claude Code and Codex, both of which reference them via
their respective hook configs:

- `hooks/hooks.json` — Claude Code (paths use `${CLAUDE_PLUGIN_ROOT}/scripts/hooks/...`)
- `../.codex/hooks.json` — Codex (template; `scripts/install-codex.sh` substitutes the absolute repo path at install time)

## What hooks are

Hooks are shell scripts executed by the host (Claude Code or Codex) at
lifecycle events — primarily `PreToolUse` (fires before a tool call runs),
`PostToolUse` (fires after), `SessionStart` (every new session), and `Stop`
(after the agent finishes responding). A hook can inspect the pending or
completed call and block it by exiting with code 2. Unlike subagents and
slash commands, hooks don't involve the LLM — they are deterministic shell
logic. This is why hooks are the right primary layer for security
guardrails: they work in the main session, inside subagents, and even when
the LLM is told otherwise.

## Three layers of defense

| Layer | Mechanism | Scope | Example |
|-------|-----------|-------|---------|
| Hooks | Deterministic shell scripts | Every tool call, every session | Block secrets in staged diff |
| Slash commands / skills | Workflow that does things the right way by default | When the user invokes | `/security-review` |
| Subagent prompt rules | LLM-level guidance | When that subagent is active | "Never modify code, only report" |

A subagent rule like "never use `--no-verify`" only applies when that
subagent is active. A hook applies to every `Bash` call from any session.
Use hooks for security, prompts for workflow.

## Available hooks

Scripts in `../scripts/hooks/`:

- **`block-secrets-precommit.sh`** (PreToolUse, matcher `Bash`) — Scans
  staged diff before `git commit` for API keys, tokens, and private keys.
  Blocks commit if found. Per-line allowlist via the
  `claude-leverage-allow-secret` marker comment.
- **`block-dangerous-git.sh`** (PreToolUse, matcher `Bash`) — Blocks force
  push, `--no-verify` commits, and hard reset on protected branches
  (`main` / `master`).
- **`ai-first-nudge.sh`** (PostToolUse, matcher `Write|Edit|MultiEdit`) —
  Non-blocking. Prints a one-liner suggestion when ≥50 net-new LOC ship
  in a single non-test file without an `AIDEV-NOTE:` anchor. Frequency-
  capped to once per file per day. Ignores tests, fixtures, generated
  code, and the bench archive.
- **`security-nudge.sh`** (Stop) — Non-blocking. Suggests `/security-review`
  when net-new code (`git diff HEAD`) crosses 80 LOC AND at least one
  changed file matches a sensitive-path pattern (auth, crypto, routes,
  payment, templates, `.env*`, …). Once per branch per day.
- **`stack-freshness.sh`** (SessionStart) — Network-free. Reads only the
  local `~/.local/state/claude-leverage/.last-stack-check` timestamp; if
  >30 days old, emits a `hookSpecificOutput.additionalContext` nudge
  suggesting `/stack-check` (so the model actually sees it — stderr
  from SessionStart is invisible to the model context window). Override
  via `CLAUDE_LEVERAGE_FRESHNESS_DAYS` env var (`=0` disables).
- **`bare-repo-nudge.sh`** (SessionStart) — Network-free. Two-branch
  proactive nudge for the cases where claude-leverage's *convention*
  layer would otherwise be inert:
  - **Branch A** — cwd is NOT inside a git repo (and is not a
    just-opened-terminal location like `$HOME` / `/tmp` / `/etc`).
    Nudge: `git init` + `/init-repo` before writing code.
  - **Branch B** (v1.4.3+) — cwd IS inside a git repo, but the repo
    root has neither `AGENTS.md` nor `CLAUDE.md` AND looks like a real
    project (has a recognizable marker: `package.json`, `pyproject.toml`,
    `Cargo.toml`, `go.mod`, `pom.xml`, `build.gradle[.kts]`, `Gemfile`,
    `composer.json`, `mix.exs`, `*.csproj`, `Package.swift`,
    `CMakeLists.txt`, `requirements.txt`, `setup.py`/`setup.cfg`).
    Nudge: `/init-repo` to drop AGENTS.md so the convention layer
    (AIDEV anchors, structured logging, per-dir AGENTS.md, module
    org) actually gets loaded into model context.

  Rate-limited to one nudge per cwd (branch A) or per repo root
  (branch B) per day so opening multiple terminals in subdirs of the
  same unconfigured repo doesn't double-nudge.
- **`json_parse.sh`** — Helper shell library (not itself a hook). Sourced
  by the security hooks. Provides `read_stdin`, `has_parser`, and
  `get_field` with a `jq` → `python3` → `python` fallback chain.

## Known limits

- **JSON parser dependency, fail-open posture.** Hooks need a JSON parser
  to inspect the host's hook input. They try `jq` first, then `python3`,
  then `python`. If none are on PATH, the security hooks
  (`block-secrets-precommit`, `block-dangerous-git`) print a loud warning
  to stderr and exit 0 (allow). This is intentional — blocking every Bash
  call when no parser is available would break unrelated work — but the
  trade-off is that until at least one parser is installed, **the security
  guardrails are not enforced.** Most macOS/Linux systems already have
  `python3` preinstalled. Windows users typically need to install one
  explicitly (`winget install jqlang.jq` for jq, or python.org / Microsoft
  Store for Python).
- **Pattern-based detection has false negatives.** Secret patterns are
  heuristics; custom or novel formats may slip through. Hooks are
  defense-in-depth, not a substitute for CI-side secret scanning
  (e.g., gitleaks, trufflehog).
- **False positives have a per-line escape hatch.** When a pattern matches
  a legitimate value (test fixture, documentation example, mock token),
  append the literal comment `claude-leverage-allow-secret` on the same
  line. The secrets hook skips lines containing that marker. Use sparingly
  — the marker is load-bearing and future readers may not recognize it.

## Install

### Plugin install (recommended)

Hooks are registered automatically via this `hooks.json`. No manual
`settings.json` editing needed.

### Codex install

`scripts/install-codex.sh` (or `.ps1` on Windows) writes the resolved
`~/.codex/hooks.json` referencing the same shell scripts. Same security
guarantees in Codex sessions as in Claude Code.

### Standalone manual install

```bash
mkdir -p ~/.claude/hooks
cp scripts/hooks/*.sh ~/.claude/hooks/
chmod +x ~/.claude/hooks/*.sh
```

Then add to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          { "type": "command", "command": "$HOME/.claude/hooks/stack-freshness.sh" },
          { "type": "command", "command": "$HOME/.claude/hooks/bare-repo-nudge.sh" }
        ]
      }
    ],
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
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          { "type": "command", "command": "$HOME/.claude/hooks/ai-first-nudge.sh" }
        ]
      }
    ],
    "Stop": [
      { "hooks": [{ "type": "command", "command": "$HOME/.claude/hooks/security-nudge.sh" }] }
    ]
  }
}
```

Restart Claude Code or run `/hooks` in an active session to pick up
changes.

## Permissions as a complementary layer

`permissions.deny` in `settings.json` is a declarative complement to
hooks. Hooks handle logic (regex matching, conditional checks).
Permissions handle static deny lists for specific files and patterns.

```json
{
  "permissions": {
    "deny": [
      "Read(**/.env)",
      "Read(**/.env.*)",
      "Edit(**/.env)",
      "Edit(**/.env.*)",
      "Bash(git push --force*)"
    ]
  }
}
```

`permissions.deny` is faster than a hook (no shell startup), but less
flexible. Use it for clear-cut deny patterns; use hooks for logic.

## Verify install

```bash
echo 'aws_key = "AKIAIOSFODNN7EXAMPLE"' > test-secret.txt
git add test-secret.txt
# Ask Claude Code or Codex to commit. Hook should block.
git rm --cached test-secret.txt && rm test-secret.txt
```

## Disabling temporarily

When a hook blocks a legitimate commit:

- **Simplest:** run the commit manually outside the agent
- **Per-line:** add `claude-leverage-allow-secret` comment to the
  offending line
- **Temporary:** remove the hook entry from `settings.json` /
  `~/.codex/hooks.json`, restart session
- **Permanent exception:** fork the hook script and adjust patterns
- **Disable a single nudge category:** the AI-first and stack-freshness
  hooks honor env vars (`CLAUDE_LEVERAGE_NUDGE_LOC=0`,
  `CLAUDE_LEVERAGE_FRESHNESS_DAYS=0`, `CLAUDE_LEVERAGE_SECURITY_NUDGE_LOC=0`)

## Platform notes

- **macOS, Linux, WSL2:** works out of the box
- **Native Windows (PowerShell):** the shell scripts run under Git Bash /
  MSYS / WSL. Pure PowerShell ports welcome as a PR.
