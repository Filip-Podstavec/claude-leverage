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
- Bump the `version` field in both `.claude-plugin/marketplace.json` and `.claude-plugin/plugin.json` for any changes that should propagate to existing plugin installs. Use semantic versioning. CI verifies the two stay in sync (see below).
- Test the plugin install flow locally before opening a PR: `/plugin marketplace add /path/to/local/clone`.

## CI

PRs and pushes to `main` run `.github/workflows/ci.yml` with three jobs:

1. **`shellcheck`** — lints every script under `hooks/` at `warning` severity. Style noise is filtered out, but real bugs (quoting, unset vars, missing `local`) will fail the build. Run locally with `shellcheck hooks/*.sh` if you have shellcheck installed.
2. **`pytest`** — runs `tests/` against `hooks/leverage_stats_agg.py`. The suite pins output format, tier sorting, and the specific edge cases that triggered v0.9.x patches (float coercion, non-string tiers, malformed JSONL, bad UTF-8 bytes). Run locally with `pytest tests/ -v`.
3. **`version-sync`** — `scripts/check_version_sync.py` asserts that `plugin.json.version` matches the `claude-leverage` entry in `marketplace.json`. Manual two-file bumps drift silently; this job is the safety net. Run locally with `python scripts/check_version_sync.py`.

When adding new bash hooks, write them so they pass shellcheck at warning severity. When changing `leverage_stats_agg.py` output shape, update `tests/test_leverage_stats_agg.py` in the same PR.
