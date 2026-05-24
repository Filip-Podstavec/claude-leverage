# Skills

Cross-tool skills following the open `agentskills.io` SKILL.md spec. Skills
are loaded on demand (unlike subagents, which add to every session's system
prompt), and they work in both Claude Code and Codex without re-authoring —
the same `SKILL.md` file is what each tool reads.

This is the **primary user-facing surface** of `claude-leverage` v1.0.0.
Subagents (`agents/`) are kept as the implementation detail behind specific
skills; users invoke skills, not subagents directly.

## Available skills

| Skill | What it does |
|---|---|
| [`security-review/`](security-review/SKILL.md) | OWASP-Top-10-shaped audit of the current diff, delegated to read-only `security-reviewer` subagent. Returns Critical / Important / Nice schema with file:line. |
| [`repo-map/`](repo-map/SKILL.md) | Generate/update the architecture mermaid block in `README.md` between idempotent markers. Optionally appends a per-language dependency graph when `madge` / `pydeps` is installed. |
| [`process-diagram/`](process-diagram/SKILL.md) | Sequence or flowchart mermaid for a named workflow, with mmdc validation loop and idempotent markers. |
| [`stack-check/`](stack-check/SKILL.md) | Verify Claude Code, Codex, plugin, and CLI dep versions per `stack.toml`; also walks repos for stale AIDEV-TODO/QUESTION anchors and AGENTS.md size against Codex's 32 KiB cap. |
| [`init-repo/`](init-repo/SKILL.md) | Bootstrap a fresh project with `AGENTS.md` (from per-language template), recommended `.gitignore` patterns, and optional structured-logging starter. |
| [`log-structured/`](log-structured/SKILL.md) | Walk a codebase, flag non-structured logging, suggest spec-compliant replacements. Read-only — never auto-rewrites. |
| [`explain-diff/`](explain-diff/SKILL.md) | Plain-English 3–5 bullet narration of `git diff HEAD` for use before a PR or review request. |
| [`codex-sandbox/`](codex-sandbox/SKILL.md) | Interactive helper to configure per-project `.codex/config.toml` sandbox + approval modes. |

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

For Codex, `scripts/install-codex.sh` (and `.ps1`) copies all skills into
`~/.agents/skills/claude-leverage/` automatically. Codex's skills resolver
finds them there.

## Why skills (vs subagents or commands)?

| Dimension | Skill | Subagent | Slash command |
|-----------|-------|----------|---------------|
| Cross-tool (Claude+Codex) | Same SKILL.md works in both | Authored twice (MD vs TOML) | Claude-only |
| Loading cost | Loaded on demand | Adds to every session's system prompt | Loaded on invocation |
| Tool restriction | `allowed-tools` frontmatter | `tools` frontmatter | `allowed-tools` frontmatter |
| Invocation | Model picks based on description, OR user types `/<name>` | Model picks based on description, OR `@<name>` | User types `/<name>` only |

Rule of thumb: **prefer skills**, fall back to subagents when the work
needs an isolated context window or deterministic output schema (e.g.,
`security-reviewer`), fall back to slash commands when something is
Claude-Code-only or needs the `argument-hint` / `Bash(...)` preamble
features that skills don't expose.
