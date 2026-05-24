# Workflows

Longer prose guides showing how the agents, skills, hooks, and conventions
in this stack combine into end-to-end patterns — security-conscious feature
development, dual-tool repo setup, AI-first refactoring, parallel-worktree
work with `superpowers` skills layered on top, and similar.

Unlike the atomic building blocks in `agents/`, `skills/`, and `commands/`,
workflows describe how to wire things together for specific scenarios.

## Available workflows

**v1.0.0 ships none yet** — workflows land as they get written based on
real use. Likely candidates:

- `security-first-feature.md` — `/security-review` integrated with the
  PostToolUse `ai-first-nudge` and Stop `security-nudge` hooks, plus
  `/commit-smart` for the final push.
- `dual-tool-setup.md` — bringing both Claude Code and Codex up on a new
  repo (`AGENTS.md` template, `scripts/install-codex.sh`, per-dir AGENTS.md
  for non-trivial modules).
- `repo-map-and-diagrams.md` — running `/repo-map` and `/process-diagram`
  against an existing project; the freshness story; mermaid validation
  loop.
- `complementary-to-superpowers.md` — how this stack layers under the
  `obra/superpowers` plugin (worktrees, brainstorming, planning); what
  belongs in which.

Drop your `.md` files here when you write one. Plain markdown, no
frontmatter required.
