# Dual-tool repo: Claude Code + OpenAI Codex CLI

Research date: 2026-05-24. Distinguishes **[SPEC]** (documented) from **[CONVENTION]** (community pattern).

## 1. AGENTS.md spec

**[SPEC]** AGENTS.md is "a simple, open format for guiding coding agents" — plain Markdown, no required fields, any headings you like. Originated by OpenAI, hosted at `agents.md` / `github.com/openai/agents.md`, MIT-licensed, now claimed by 20k+ repos. Community sources cite Linux Foundation / "Agentic AI Foundation" stewardship but the GitHub repo itself does not document that governance.

**[SPEC] — Codex specifics** (from `developers.openai.com/codex/guides/agents-md`):
- **Resolution order (concatenated, later wins):**
  1. Global: `~/.codex/AGENTS.override.md` (if present) or `~/.codex/AGENTS.md`
  2. Project: walk git root → cwd, at each level checking `AGENTS.override.md`, then `AGENTS.md`, then `project_doc_fallback_filenames` (e.g. `TEAM_GUIDE.md`)
- **Size limit:** `project_doc_max_bytes` = **32 KiB default**; content beyond the threshold is silently dropped. Tunable in `~/.codex/config.toml`.
- **No imports / @-references.** Codex only concatenates files; there is no `@path/to/other.md` mechanism.
- **Nested files in monorepos** are supported — closer file wins because it appears later in the merged prompt.

**Adoption** (per agents.md & confirmed in Codex/Cursor/Aider docs): Codex CLI, Cursor, Gemini CLI, Windsurf, GitHub Copilot, Aider, Zed, Warp, Roo Code, Jules, Devin, Factory, JetBrains Junie, Amp.

**Recommended sections** (convention, not spec): Project overview, Build/test commands, Code style, Testing instructions, Security, Commit/PR guidelines, Deployment.

## 2. Claude Code: does it read AGENTS.md?

**[SPEC] No, not natively** (confirmed in `code.claude.com/docs/en/memory`, May 2026). Claude Code reads `CLAUDE.md`, not `AGENTS.md`. GitHub issue [anthropics/claude-code#6235](https://github.com/anthropics/claude-code/issues/6235) is still open requesting it.

**[SPEC] Official Anthropic workaround** (quoted from docs):
```markdown
# CLAUDE.md
@AGENTS.md

## Claude Code
Use plan mode for changes under `src/billing/`.
```
The `@path` import expands the target file into context at session start, with recursion up to 5 hops. Imports work for both relative paths and `~/` paths. Symlink (`ln -s AGENTS.md CLAUDE.md`) also works on macOS/Linux; on Windows it requires Admin/Developer Mode, so prefer `@AGENTS.md` import there.

**[SPEC]** Running `/init` in a repo that already has `AGENTS.md` will read it (and `.cursorrules`, `.windsurfrules`) and incorporate parts into the generated `CLAUDE.md`.

**Verdict:** A single `AGENTS.md` cannot fully replace `CLAUDE.md`, but a one-line `CLAUDE.md` consisting only of `@AGENTS.md` makes it effectively a redirect. Put shared/tool-agnostic content in `AGENTS.md`, append Claude-only content below the import in `CLAUDE.md`.

## 3. Skills, subagents, commands — portability

| Concept | Claude Code | Codex CLI | Portable? |
|---|---|---|---|
| **Skills** (SKILL.md) | `.claude/skills/<name>/SKILL.md`, YAML frontmatter (`name`, `description`, `disable-model-invocation`, `allowed-tools`, `paths`, `model`, `context: fork`, …) | `.agents/skills/<name>/SKILL.md` + `~/.agents/skills`, `/etc/codex/skills`. Same YAML frontmatter shape (`name`, `description` required). | **Body portable, path is not.** Claude docs confirm conformance to "Agent Skills" open standard at `agentskills.io`. Symlink or duplicate the directory: `ln -s .claude/skills .agents/skills`. |
| **Subagents** | `.claude/agents/*.md` — Markdown + YAML frontmatter | `~/.codex/agents/*.toml` or `.codex/agents/*.toml` — **TOML**, fields: `name`, `description`, `developer_instructions`, optional `model`, `sandbox_mode`, `mcp_servers`, `skills.config` | **Not portable.** Different file format (MD vs TOML) and different field names. Must author twice or generate one from the other. |
| **Slash commands** | Merged into skills (`.claude/skills/<name>/SKILL.md` with `disable-model-invocation: true`). Legacy `.claude/commands/*.md` still works. | Codex CLI custom commands live in agents/skills; no separate "commands" namespace. | **Use skills as the common substrate.** A skill with `disable-model-invocation: true` behaves like a slash command in both tools. |
| **Hooks** | `.claude/settings.json` `hooks` block | `~/.codex/hooks.json` or inline `[hooks]` in `config.toml` (project: `.codex/hooks.json` / `.codex/config.toml`) | **Same event names, different config files.** Hook *scripts* (the shell programs) are reusable; config wrappers must be duplicated. |

## 4. Hook equivalents

**[SPEC]** Codex hook events (verbatim from `developers.openai.com/codex/hooks`): `SessionStart`, `SubagentStart`, `PreToolUse`, `PermissionRequest`, `PostToolUse`, `PreCompact`, `PostCompact`, `UserPromptSubmit`, `SubagentStop`, `Stop`.

The event vocabulary is **near-identical to Claude Code's** (Claude also has `InstructionsLoaded`; otherwise the lists overlap). Example PreToolUse from Codex docs:
```json
{
  "matcher": "^Bash$",
  "hooks": [{
    "type": "command",
    "command": "/usr/bin/python3 \"$(git rev-parse --show-toplevel)/.codex/hooks/pre_tool_use_policy.py\"",
    "statusMessage": "Checking Bash command"
  }]
}
```
**Trust model:** Codex records the hook's hash and re-prompts trust on every change (`--dangerously-bypass-hook-trust` is the override). Project-scoped `.codex/config.toml` and `.codex/hooks.json` only load if the project is trusted.

**Practical pattern:** keep the hook *implementation* in one place (`scripts/hooks/`), reference the same script from both `.claude/settings.json` and `.codex/hooks.json` with matching event matchers. Pre-commit / lefthook git hooks remain the tool-agnostic guardrail layer for anything you want enforced regardless of which agent runs.

## 5. Real-world dual-tool repos

**Best concrete example:** [`carlrannaberg/claudekit`](https://github.com/carlrannaberg/claudekit) — `CLAUDE.md` is a symlink to `AGENTS.md`; subagents live in `src/agents/` and `.claude/commands/` symlinks back to `src/commands/`. Single source of truth for guidance, dual-format author for tool-specific definitions.

**Apache Superset pattern** (mentioned in claude-code#6235): maintains `LLMs.md` as canonical, with `CLAUDE.md` / `GEMINI.md` / `.cursorrules` symlinks. Pre-`@import` workaround.

**SessionStart hook pattern** (from claude-code#6235 comments): a hook that `find`s every `AGENTS.md` in the repo and prepends them to context — lets you skip `CLAUDE.md` entirely while keeping monorepo locality.

## Recommended layout for a new dual-tool repo

```
repo/
├── AGENTS.md                       # canonical, tool-agnostic guidance (<32 KiB for Codex)
├── CLAUDE.md                       # one line: @AGENTS.md   (+ optional Claude-only blocks)
├── .claude/
│   ├── settings.json               # Claude hooks → ../scripts/hooks/*.sh
│   ├── agents/*.md                 # Claude subagents
│   └── skills/<name>/SKILL.md      # Claude skills
├── .codex/
│   ├── config.toml                 # Codex sandbox/approval + [hooks] → ../scripts/hooks/*.sh
│   └── agents/*.toml               # Codex subagents (separate authoring)
├── .agents/skills -> ../.claude/skills    # symlink so Codex finds the same skills
└── scripts/hooks/                  # shared hook implementations
```

Skills become the portable substrate (SKILL.md frontmatter is identical). Subagents are the unavoidable double-authoring cost. Hooks reuse shell scripts, duplicate only the trigger config.

## Sources

- [agents.md](https://agents.md/) — open spec home
- [Codex AGENTS.md guide](https://developers.openai.com/codex/guides/agents-md)
- [Codex hooks](https://developers.openai.com/codex/hooks)
- [Codex subagents](https://developers.openai.com/codex/subagents)
- [Codex skills](https://developers.openai.com/codex/skills)
- [Claude Code memory docs](https://code.claude.com/docs/en/memory) — quotes "Claude Code reads `CLAUDE.md`, not `AGENTS.md`" with the @AGENTS.md workaround
- [Claude Code skills docs](https://code.claude.com/docs/en/skills) — cites `agentskills.io` open standard
- [anthropics/claude-code#6235](https://github.com/anthropics/claude-code/issues/6235) — feature request thread with workarounds
- [carlrannaberg/claudekit](https://github.com/carlrannaberg/claudekit/blob/main/AGENTS.md) — symlink reference implementation
