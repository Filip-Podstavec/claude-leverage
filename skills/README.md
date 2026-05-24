# Skills

Cross-tool skills following the open `agentskills.io` SKILL.md spec. Skills
are loaded on demand (unlike subagents, which add to every session's system
prompt), and they work in both Claude Code and Codex without re-authoring —
the same `SKILL.md` file is what each tool reads.

This is the **primary user-facing surface** of `claude-leverage` v1.0.0.
Subagents (`agents/`) are kept as the implementation detail behind specific
skills; users invoke skills, not subagents directly.

## Available skills

**v1.0.0 ships none yet** — skills are added per phase as the v1.0.0 plan
rolls out (see [`../docs/specs/2026-05-24-pivot/06-roadmap.md`](../docs/specs/2026-05-24-pivot/06-roadmap.md)):

- Phase 2: `security-review/` — paired with `agents/security-reviewer.md`.
- Phase 3: `repo-map/`, `process-diagram/` — mermaid generators.
- Phase 4: `stack-check/` — 30-day stack-freshness check.
- Possible migration: `commit-smart/`, `install-snippets/` may move here
  from `commands/` for cross-tool portability.

## Install

The plugin install registers skills automatically (Claude Code reads
`.claude/skills/` by convention). Manual / standalone:

```bash
# User scope (available in all projects)
mkdir -p ~/.claude/skills
cp -r skills/<skill-name> ~/.claude/skills/

# Project scope
mkdir -p .claude/skills
cp -r skills/<skill-name> .claude/skills/
```

For Codex, `scripts/install-codex.sh` (added in v1.0.0) handles the
equivalent dance — Codex reads `~/.agents/skills/` by convention; the
installer keeps it in sync with what's in this repo.

## Why skills (vs subagents or commands)?

| Dimension | Skill | Subagent | Slash command |
|-----------|-------|----------|---------------|
| Cross-tool (Claude+Codex) | Same SKILL.md works in both | Authored twice (MD vs TOML) | Claude-only |
| Loading cost | Loaded on demand | Adds to every session's system prompt | Loaded on invocation |
| Tool restriction | `allowed-tools` frontmatter | `tools` frontmatter | `allowed-tools` frontmatter |
| Invocation | Model picks based on description, OR user types `/<name>` | Model picks based on description, OR `@<name>` | User types `/<name>` only |

For v1.0.0, the rule of thumb: **prefer skills**, fall back to subagents
when the work needs an isolated context window or deterministic output
schema (e.g., `security-reviewer`), fall back to slash commands when
something is Claude-Code-only or needs the `argument-hint`/`Bash(...)`
preamble features that skills don't expose.
