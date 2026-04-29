# Contributing

## Adding content

| Type | Directory | Frontmatter required |
|------|-----------|---------------------|
| Subagent | `agents/` | `name`, `description`, `tools`, `model` |
| Slash command | `commands/` | `description`, optionally `allowed-tools` |
| Skill | `skills/` | `name`, `description` |
| Hook | `hooks/` | Describe trigger event and action |
| CLAUDE.md snippet | `claude-md-snippets/` | None - plain markdown |
| Workflow guide | `workflows/` | None - plain markdown |

Place your `.md` file in the matching directory. Each file should be self-contained and copy-pasteable.

## Style guide

- Dry, technically precise tone. No marketing language, no emoji in headers.
- Short paragraphs, concrete examples. Code blocks must be directly copy-pasteable.
- No version notes, date stamps, or "tested with" disclaimers.
- Use short dash `-`, not em dash.

## PR checklist

- [ ] File is in the correct directory
- [ ] Required frontmatter fields are present
- [ ] Code examples are copy-pasteable and tested
- [ ] No version-specific references or date stamps
- [ ] Directory README updated to list the new item

## Plugin development

This repo is both a copy-pasteable component collection and a Claude Code plugin marketplace. When contributing:

- New agents, commands, or hooks are automatically picked up by the plugin manifest - no need to update `plugin.json` to list each file.
- If you change hook configuration (matchers, lifecycle events), update `hooks/hooks.json` accordingly.
- Bump the `version` field in both `.claude-plugin/marketplace.json` and `.claude-plugin/plugin.json` for any changes that should propagate to existing plugin installs. Use semantic versioning.
- Test the plugin install flow locally before opening a PR: `/plugin marketplace add /path/to/local/clone`.
