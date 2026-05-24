# 05 — Stack freshness (30-day check)

## The feature in one paragraph

The plugin stack depends on Claude Code itself, on Codex CLI, on the plugin
package, and on a handful of CLI tools (`rg`, `jq`, `python`, `git`, optional:
`mmdc`, `node`). These move. If you haven't run a check in a while, you can
be silently behind on security fixes, missing new features, or running against
a CLI version a skill expects. **`stack-freshness` is a SessionStart hook that
prints a single non-blocking line when the last check is older than 30 days;
`/stack-check` is the skill that performs the check and resets the clock.**

## Design constraints

- **Never auto-update.** Per the user's `CLAUDE.md` guidance and the
  system's "executing actions with care" rules, anything that touches
  installed software is the user's call.
- **Never block.** SessionStart hooks that block on network are a
  startup-latency nightmare. The hook only reads a local timestamp
  file.
- **Network only on explicit user opt-in.** `/stack-check` does
  network; the hook does not.
- **Cross-platform.** Windows-first (user's primary OS), but no
  bash-isms that break on macOS/Linux.

## Components

### `scripts/hooks/stack-freshness.sh`

SessionStart hook, runs every session. Does only:

```bash
last_check_file="$HOME/.claude/claude-leverage/.last-stack-check"
threshold_days=30

if [ -f "$last_check_file" ]; then
  last_check=$(cat "$last_check_file")
  age_days=$(( ($(date +%s) - last_check) / 86400 ))
  if [ "$age_days" -lt "$threshold_days" ]; then
    exit 0
  fi
  msg="(claude-leverage: stack last checked ${age_days}d ago — run /stack-check)"
else
  msg="(claude-leverage: stack never checked — run /stack-check)"
fi

echo "$msg" >&2
exit 0
```

That's it. No network, no file writes beyond the marker.

### `stack.toml` (repo root)

Declarative manifest of what the plugin expects:

```toml
# claude-leverage stack manifest — what /stack-check verifies

[plugin]
name = "claude-leverage"
self_marketplace = "filip-podstavec"

[host]
# CLI agents — checked if installed
[[host.tool]]
name = "claude"
min_version = "2.1.0"
check_cmd = "claude --version"
update_hint = "Update via the Claude Code app (Settings → Updates)."

[[host.tool]]
name = "codex"
min_version = "0.40.0"
check_cmd = "codex --version"
update_hint = "npm i -g @openai/codex"
optional = true

[deps]
[[deps.tool]]
name = "git"
min_version = "2.40.0"
check_cmd = "git --version"

[[deps.tool]]
name = "rg"
min_version = "13.0.0"
check_cmd = "rg --version"

[[deps.tool]]
name = "jq"
min_version = "1.6"
check_cmd = "jq --version"
optional = true        # falls back to Python in our hooks

[[deps.tool]]
name = "python"
min_version = "3.10"
check_cmd = "python --version"

[[deps.tool]]
name = "mmdc"
min_version = "10.0.0"
check_cmd = "mmdc --version"
optional = true        # used by /repo-map and /process-diagram validation

[[deps.tool]]
name = "node"
min_version = "20.0.0"
check_cmd = "node --version"
optional = true        # for mmdc + JS-ecosystem repo-map
```

### `skills/stack-check/SKILL.md`

```yaml
---
name: stack-check
description: |
  Checks if Claude Code, Codex CLI, the claude-leverage plugin, and key
  command-line tools are at their expected minimum versions per stack.toml.
  Read-only — reports status and update commands; never installs.
allowed-tools: [Read, Bash(claude --version), Bash(codex --version), Bash(git --version), Bash(rg --version), Bash(jq --version), Bash(python --version), Bash(mmdc --version), Bash(node --version), WebFetch]
disable-model-invocation: false
---
```

Behavior:

1. Load `stack.toml` (use the one in the plugin install directory).
2. For each `[[host.tool]]` and `[[deps.tool]]`:
   - Run `check_cmd`. Parse version. If parse fails, mark "unknown."
   - Compare against `min_version`. Mark ok / outdated / missing.
3. For the plugin itself:
   - Read current version from `.claude-plugin/plugin.json` of installed
     copy.
   - WebFetch the marketplace listing
     `https://raw.githubusercontent.com/Filip-Podstavec/claude-leverage/main/.claude-plugin/plugin.json`
     and compare.
4. For Claude Code itself:
   - The version is already available from `claude --version` output;
     compare to declared `min_version`. We don't WebFetch the absolute
     latest because Anthropic doesn't have a single stable endpoint to
     scrape; instead we trust `min_version` in `stack.toml`, which we
     bump when a new release ships features we depend on.
5. Print a Markdown report:

```markdown
# Stack check — 2026-05-24

| Tool | Installed | Required | Status | Update |
|------|-----------|----------|--------|--------|
| claude (Claude Code) | 2.1.89 | ≥2.1.0 | ok | — |
| codex (Codex CLI) | 0.39.0 | ≥0.40.0 | **outdated** | `npm i -g @openai/codex` |
| claude-leverage (this plugin) | 1.0.0 | latest 1.0.1 | **outdated** | `/plugin update claude-leverage` |
| git | 2.45.0 | ≥2.40.0 | ok | — |
| rg | 14.0.3 | ≥13.0.0 | ok | — |
| jq | (not found) | ≥1.6 (optional) | missing | brew install jq / choco install jq |
| python | 3.12.1 | ≥3.10 | ok | — |
| mmdc | (not found) | ≥10.0.0 (optional) | missing | npm i -g @mermaid-js/mermaid-cli |
| node | 20.10.0 | ≥20.0.0 | ok | — |
```

6. Touch `~/.claude/claude-leverage/.last-stack-check` with current
   epoch time **only if the check actually completed** (no exception
   thrown). Failed checks don't reset the clock.
7. Cache WebFetch results for 24 hours in
   `~/.claude/claude-leverage/.stack-check-cache.json` to avoid hammering
   GitHub on repeated invocations.

## What we deliberately don't do

- **No auto-update.** Never. The skill outputs commands; user runs them.
- **No telemetry / phone-home.** Local file timestamps only.
- **No "auto-bumping" of stack.toml.** That manifest is hand-maintained.
  When the plugin author wants to require a newer Claude Code or rg
  version, they bump it in a commit.
- **No silent network in the SessionStart hook.** Hook reads local file
  only. Network only when user runs `/stack-check`.

## Threshold tunability

The 30-day default is in the hook script. Easy to override per user:
they can edit `scripts/hooks/stack-freshness.sh` directly, or we can
read `STACK_FRESHNESS_DAYS` env var (default 30, 0 disables). I propose
honoring the env var to make the opt-out painless.

## Open questions for review

1. **Should the check also nudge for `superpowers`,
   `frontend-design`, `code-review`, `claude-code-setup` (other
   installed plugins)?** Cleaner answer: stick to our own stack
   freshness; trying to police other plugins' updates is scope creep
   and adds failure modes when their marketplaces change shape.
2. **Should `/stack-check` offer to run the update commands** (with
   user confirmation)? Marginal value, real risk (`npm -g` needs sudo
   on some systems, `/plugin update` is fine but should still be a
   user-typed action). My recommendation: just show the commands.
3. **30 days as the default.** Justified by: most CLI tools have
   sub-monthly minor releases, security fixes ship every few weeks.
   Could be 14 days (more current) or 60 (less noisy). 30 feels
   right; cheap to change.
4. **Are there other things worth checking** beyond CLI versions and
   plugin version? Possibilities: presence of `~/.codex/` setup if
   the user has `codex` installed, presence of `mmdc` if `/repo-map`
   skill is enabled but tool is missing, recent activity in the
   plugin's GitHub release feed. Recommendation for v1.0: ship just
   versions, add the rest based on actual usage friction.
