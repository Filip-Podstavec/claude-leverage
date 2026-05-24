# Workflow: what the stack maintains automatically vs what you invoke

This guide answers two questions:
1. **What does the stack do for me without my asking?** (passive
   nudges, hooks, periodic checks)
2. **What do I have to invoke explicitly?** (skills, slash commands)

The intent is to give you the mental model: most maintenance friction
is offloaded to nudges; you only invoke skills when you've decided to
do something concrete.

## Passive — runs without invocation

### Every Bash tool call (`PreToolUse`)

| Hook | What it does | Can it block? |
|------|--------------|---------------|
| `block-secrets-precommit` | Scans staged diff for API keys / tokens / private keys on `git commit` | **YES** (exit 2). Per-line allowlist via `claude-leverage-allow-secret` marker. |
| `block-dangerous-git` | Blocks `git push --force`, `git commit --no-verify`, `git reset --hard` on `main`/`master` | **YES** (exit 2) |

Both fail-open with a loud stderr warning if no JSON parser
(`jq` / `python3` / `python`) is available on PATH.

### Every Write / Edit / MultiEdit (`PostToolUse`)

| Check | Fires when | What you see |
|-------|------------|--------------|
| AIDEV-NOTE missing | ≥50 net-new LOC in a non-test file with no `AIDEV-` anchor in the change | `(claude-leverage: 73 LOC of net-new code in <file> with no AIDEV-NOTE anchor — consider anchoring load-bearing parts)` |
| Per-dir AGENTS.md missing | New file lands in a recognized source root (`src/`, `lib/`, `app/`, `apps/`, `pkg/`, `internal/`, `services/`, `api/`, `cmd/`, `crates/`, `packages/`, plus monorepo-nested) AND parent dir has 8+ source files AND no AGENTS.md in parent or any ancestor up to repo root | `(claude-leverage: <dir> has 11 source files but no AGENTS.md anywhere up to repo root — …)` |

Both are **non-blocking** (always exit 0). Frequency-capped: AIDEV
nudge once per file per day, dir-AGENTS nudge once per dir per day.
Tune the thresholds with `CLAUDE_LEVERAGE_NUDGE_LOC` and
`CLAUDE_LEVERAGE_DIR_AGENTS_MIN`. Disable a category with `=0`.

### After agent finishes responding (`Stop`)

| Hook | Fires when | What you see |
|------|------------|--------------|
| `security-nudge` | Net-new code (`git diff HEAD`) crosses 80 LOC AND at least one changed file matches a sensitive-path pattern (`*auth*`, `*crypto*`, `routes/`, `payment*`, `templates/`, `*.env*`, etc.) | `(claude-leverage: 142 LOC of net-new code touches services/auth/handlers.py — consider running /security-review before commit)` |

Non-blocking. One per branch per day. Override threshold with
`CLAUDE_LEVERAGE_SECURITY_NUDGE_LOC`.

### Every new session (`SessionStart`)

| Hook | Fires when | What you see |
|------|------------|--------------|
| `stack-freshness` | Last `/stack-check` was >30 days ago (or never) | `(claude-leverage: stack last checked 42d ago — run /stack-check to look for updates)` |

**Network-free.** Reads only the local timestamp file
(`~/.local/state/claude-leverage/.last-stack-check`). The actual
version check requires `/stack-check` invocation. Override interval
with `CLAUDE_LEVERAGE_FRESHNESS_DAYS=N` (`=0` disables).

## Active — you invoke explicitly

### Skills you invoke during a feature

| Skill | When to invoke |
|-------|----------------|
| `/security-review` | Before committing changes in auth / crypto / routes / payment / templates. The `security-nudge` Stop hook will suggest this automatically when the threshold is met. |
| `/commit-smart` | When you're ready to commit. Scans for secrets, writes Conventional Commits message, pushes. Inline (no subagent). |
| `/explain-diff` | Before opening a PR (`--for pr`) or when teammate is reviewing (`--for review`). Plain-English diff narration. |
| `/flaky-test <test>` | When a single test fails intermittently — runs it N times, groups failures by signature. |

### Skills you invoke periodically (maintenance)

| Skill | When to invoke | What you get |
|-------|----------------|--------------|
| `/stack-check` | When the SessionStart hook nudges, or every ~30 days | Markdown report covering: Claude Code + Codex + plugin + CLI dep versions (with per-OS install commands); AIDEV-TODO/QUESTION anchor walk grouped by age and deadline status (fresh / aging / stale / due-soon / overdue); AGENTS.md sanity (32 KiB cap, broken `@<path>` imports, possibly stale file references). Resets the freshness timestamp on success. |
| `/repo-map` | After adding/renaming a top-level directory, or before tagging a release | Regenerates the mermaid architecture block in README.md between idempotent markers. Optionally adds a per-language dep graph (`madge` for JS/TS, `pydeps` for Python — opt-in, skipped silently if neither installed). |
| `/process-diagram <name>` | When documenting a non-obvious workflow (commit-smart flow, hook-intercept flow, etc.) | mermaid sequenceDiagram or flowchart, mmdc validation loop, inserted into target markdown between idempotent markers. |
| `/log-structured` | Onboarding to a legacy codebase, or after AGENTS.md adoption to see baseline | Walks codebase, flags print() / console.log() / interpolated logger.X() calls, suggests spec-compliant replacements per file:line. Read-only. |

### Skills you invoke once per repo (setup)

| Skill | When to invoke | What you get |
|-------|----------------|--------------|
| `/init-repo` | First time setting up a new project with this stack | Interactive bootstrap of AGENTS.md (from per-language template), CLAUDE.md (one-line `@AGENTS.md` import), .gitignore patterns for the stack's state dirs, and optional structured-logging template. Idempotent — re-running detects existing install via marker blocks. |
| `/codex-sandbox` | First time using Codex in a project, OR tightening sandbox for prod | Interactive helper for per-project `.codex/config.toml`. Three pre-baked profiles (`dev` / `prod` / `custom`). |

## How the maintenance debt cycle works

Without the stack, maintenance debt accumulates silently. With the stack:

```
write code  ──────►  ai-first-nudge flags missing AIDEV-NOTE
                    (you anchor the load-bearing parts as you go)
                            │
                            ▼
file count grows ─►  per-dir AGENTS.md nudge fires once
                    (you write a module-level AGENTS.md)
                            │
                            ▼
sensitive diff ──►  security-nudge suggests /security-review
                    (you run it; address Critical)
                            │
                            ▼
TODO with deadline ►  AIDEV-TODO(by: 2026-08-01)
                            │
                            ▼
30 days pass ─────►  stack-freshness nudges /stack-check
                    (one report: tool versions + anchor age + AGENTS.md sanity)
                            │
                            ▼
deadline passes ──►  /stack-check flags overdue AIDEV-TODO
                    (you resolve it before it accumulates more dependents)
```

The cumulative effect: maintenance items surface when they're cheap to
fix, not after they've quietly compounded.

## Disabling things you don't want

Every nudge respects an environment variable:

| Variable | Default | `=0` disables |
|----------|---------|---------------|
| `CLAUDE_LEVERAGE_NUDGE_LOC` | 50 | AIDEV-NOTE nudge |
| `CLAUDE_LEVERAGE_DIR_AGENTS_MIN` | 8 | Per-dir AGENTS.md nudge |
| `CLAUDE_LEVERAGE_SECURITY_NUDGE_LOC` | 80 | Security review Stop hook |
| `CLAUDE_LEVERAGE_FRESHNESS_DAYS` | 30 | Stack-freshness SessionStart |
| `CLAUDE_LEVERAGE_ANCHOR_STALE_DAYS` | 90 | (Tunes the "stale" threshold in /stack-check anchor walk) |
| `CLAUDE_LEVERAGE_SKIP_ANCHOR_AUDIT` | (unset) | Set to `1` to skip /stack-check anchor walk entirely |
| `CLAUDE_LEVERAGE_SKIP_AGENTS_MD_AUDIT` | (unset) | Set to `1` to skip /stack-check AGENTS.md sanity |

To disable a security guardrail (block-secrets-precommit,
block-dangerous-git), edit `~/.claude/settings.json` or
`~/.codex/hooks.json` and remove the hook entry — but you should very
rarely want to. The per-line `claude-leverage-allow-secret` marker is
the right escape hatch for false-positive secret matches.

## See also

- [`security-first-feature.md`](security-first-feature.md) — concrete
  walkthrough of one PR-shaped feature using the stack.
- [`../AGENTS.md`](../AGENTS.md) — canonical guidance, including the
  AIDEV-NOTE convention spec and structured-logging spec.
- [`../docs/specs/2026-05-24-pivot/`](../docs/specs/2026-05-24-pivot/)
  — design docs explaining why the stack looks the way it does.
